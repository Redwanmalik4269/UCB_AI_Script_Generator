# -*- coding: utf-8 -*-
"""
AI Script Generator (Bangla) — Streamlit version
Author: UCB Asset Management (UCB AML)
"""

import os, re, io
import pandas as pd
import streamlit as st
from urllib.parse import urlparse, parse_qs
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from docx import Document
import gdown

# --------------------------------------------
# Utility
# --------------------------------------------
def _paragraphize(txt: str) -> str:
    if not isinstance(txt, str): return ""
    txt = re.sub(r'(?m)^\s*[•\-\u2022]+\s*', '', txt)   # bullets
    txt = re.sub(r'(?m)^\s*\d+\.\s*', '', txt)          # 1. 2. 3.
    txt = txt.replace('— — —', ' ')
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def _len_ok(s: str, n: int = 280) -> bool:
    return bool(s and len(s) >= n)

# --------------------------------------------
# Defaults
# --------------------------------------------
SAMPLES = {
    "নিরাপদ ও নিশ্চিত রিটার্ন (সঞ্চয়পত্রের বিকল্প)": [{
        "product": "UCB Income Plus Fund",
        "script": "যারা নিরাপদ বিনিয়োগ পছন্দ করেন..."
    }],
    "দীর্ঘমেয়াদে সম্পদ গঠন (ইকুইটি-অরিয়েন্টেড)": [{
        "product": "UCB AML First Mutual Fund",
        "script": "দীর্ঘমেয়াদি সম্পদ গঠনের জন্য..."
    }]
}
CLIENT_TYPES = list(SAMPLES.keys())

PRODUCT_FACTS = {
    "UCB Income Plus Fund": {
        "indicative_return": "বর্তমান বাজারে ইঙ্গিতমাত্র নেট ~৯–১১% (গ্যারান্টি নয়)",
        "exit_load": "প্রথম ১০০ দিন রিডেম্পশনে চার্জ; এরপর সাধারণত চার্জমুক্ত",
        "sip": "SIP: ন্যূনতম ৳৫,০০০/মাস",
        "non_sip": "Non-SIP: ন্যূনতম ৳১০,০০০",
        "tax": "কর রিবেটের সম্ভাবনা (আয়কর বিধি অনুযায়ী)"
    },
    "UCB AML First Mutual Fund": {
        "indicative_return": "ইকুইটি-অরিয়েন্টেড—দীর্ঘমেয়াদে বাজারনির্ভর",
        "exit_load": "এক্সিট লোড স্কিম তথ্যপত্র অনুযায়ী",
        "sip": "SIP: ন্যূনতম ৳৩,০০০/মাস",
        "non_sip": "Non-SIP: ন্যূনতম ৳১০,০০০",
        "tax": "প্রযোজ্য হলে আয়কর রিবেট"
    }
}
def facts_for(product: str) -> str:
    f = PRODUCT_FACTS.get(product or "", {})
    if not f: return ""
    return " | ".join([
        f"রিটার্ন: {f['indicative_return']}",
        f"এক্সিট লোড: {f['exit_load']}",
        f"{f['sip']}", f"{f['non_sip']}", f"{f['tax']}"
    ])

# --------------------------------------------
# Model
# --------------------------------------------
MODEL_NAME = "google/flan-t5-small"  # keep small for Streamlit Cloud

@st.cache_resource(show_spinner=False)
def load_model():
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    return pipeline("text2text-generation", model=mdl, tokenizer=tok)

gen = load_model()

# --------------------------------------------
# Prompting (two-pass)
# --------------------------------------------
def _facts_block(product: str, include: bool) -> str:
    if not include: return ""
    ftxt = facts_for(product)
    return f"\n[FACTS]\n{ftxt}\n[/FACTS]\n" if ftxt else ""

def build_body_prompt(client_type, product, horizon, risk, extra, tone, include_facts=True):
    """
    IMPORTANT: We *show* facts in a [FACTS] block but *forbid* printing that block.
    The model must write the conversational body only.
    """
    shots = SAMPLES.get(client_type, [])
    ex = _paragraphize(shots[0]["script"]) if shots else ""

    tone_rule = {
        "Factual": "সংক্ষিপ্ত, তথ্যনির্ভর ও নিরপেক্ষ থাকুন।",
        "Elaborated": "ব্যাখ্যামূলক, সহানুভূতিশীল ও শিক্ষামূলক টোন ব্যবহার করুন; বাস্তব উদাহরণ দিন।",
        "Sales Pitch": "আস্থাজনক ও প্ররোচিত টোন রাখুন; গ্রাহকের লাভ ও সুবিধা স্পষ্ট করুন।"
    }.get(tone, "ব্যাখ্যামূলক টোন।")

    rules = [
        "ভাষা: খাঁটি বাংলা; কথোপকথনমূলক প্যারাগ্রাফ।",
        "দৈর্ঘ্য: কমপক্ষে ৩৫০–৬০০ শব্দ।",
        "কাঠামো: (১) শুভেচ্ছা+ডিসকভারি (২) পণ্য কীভাবে কাজ করে (৩) ঝুঁকি-রিটার্ন ব্যাখ্যা (৪) উদাহরণ/সিনারিও (৫) কীভাবে শুরু করবেন—ধাপে ধাপে (৬) CTA।",
        "গুরুত্বপূর্ণ: নিচের [FACTS] তথ্যগুলো কেবলমাত্র রেফারেন্স হিসেবে ব্যবহার করবেন; মূল বডিতে [FACTS] ব্লকটি হুবহু বা আংশিকভাবে প্রিন্ট করবেন না।",
        "‘গ্যারান্টি’ বা ‘ঝুঁকি নেই’ ধরনের দাবি করা যাবে না।",
        tone_rule,
    ]

    prompt = f"""
আপনি একজন অভিজ্ঞ মিউচুয়াল ফান্ড RM। নিচের উদাহরণের স্টাইল মাথায় রেখে একটি পূর্ণাঙ্গ বাংলা স্ক্রিপ্ট লিখুন।

উদাহরণ (স্টাইল মাত্র):
{ex}

{_facts_block(product, include_facts)}

নির্দেশনা:
- {chr(10).join(rules)}

ইনপুট:
- ক্লায়েন্ট টাইপ: {client_type}
- পণ্য: {product}
- সময়সীমা: {horizon}
- ঝুঁকি: {risk}
- নোট: {extra}

আউটপুট:
শুধু কথোপকথনমূলক বডি লিখুন; "পণ্য-তথ্য" অংশটি এখন লিখবেন না।
""".strip()
    return prompt

def _fallback_body(ct, prod, horizon, risk, extra):
    # Simple, safe template if model returns too little
    greeting = "আসসালামু আলাইকুম। আমি ইউসিবি অ্যাসেট ম্যানেজমেন্ট থেকে বলছি।"
    discovery = "আপনার লক্ষ্য, সময়সীমা ও ঝুঁকি পছন্দ বুঝে নিতে চাই—তারপর উপযুক্ত পরিকল্পনা সাজাবো।"
    explain = f"{prod} নিয়ে সংক্ষেপে বলি—এই ফান্ডটি পেশাদার টিম দ্বারা পরিচালিত হয় এবং ঝুঁকি-রিটার্নের ভারসাম্য রাখার চেষ্টা করে।"
    risk_note = "বাজারে ওঠানামা থাকেই; স্বল্পমেয়াদে ভোলাটিলিটি সম্ভব, কিন্তু পরিকল্পিতভাবে বিনিয়োগ করলে লক্ষ্যপূরণ সহজ হয়।"
    steps = "শুরু করার ধাপ: (১) KYC/ফর্ম পূরণ (২) ব্যাংক ট্রান্সফার/SIP সেটআপ (৩) কনফার্মেশন (৪) পর্যায়ক্রমে রিভিউ।"
    cta = "আপনি চাইলে আজই SIP শুরু করতে পারি—আমি সব ডকুমেন্ট/লিংক পাঠিয়ে দিচ্ছি।"
    return "\n\n".join([greeting, discovery, explain, risk_note, steps, cta])

def generate_script(ct, prod, horizon, risk, extra, temp, max_tok, include_facts, tone):
    # ---- Pass A: body only (facts hidden from output)
    body_prompt = build_body_prompt(ct, prod, horizon, risk, extra, tone, include_facts)
    params = dict(
        max_new_tokens=int(max_tok),
        temperature=float(temp),
        top_p=0.95,
        top_k=50,
        repetition_penalty=1.05
    )
    try:
        body = gen(body_prompt, **params)[0]["generated_text"].strip()
    except Exception as e:
        body = ""

    # If the model echoed facts or produced too little, fallback
    if "[FACTS]" in body or "পণ্য-তথ্য" in body or not _len_ok(body):
        body = _fallback_body(ct, prod, horizon, risk, extra)

    # Remove any accidental facts echoes
    body = re.sub(r"\[/?FACTS\]", "", body, flags=re.I)

    # ---- Pass B: append verbatim facts + disclaimer
    tail = ""
    if include_facts:
        tail += "\n\nপণ্য-তথ্য (হুবহু): " + facts_for(prod)
    tail += "\n\nনোট: মিউচুয়াল ফান্ড বাজারনির্ভর; পূর্বের আয় ভবিষ্যতের নিশ্চয়তা নয়।"

    return body.strip() + tail

# --------------------------------------------
# Google Sheet / Doc helpers (optional loaders UI)
# --------------------------------------------
def _sheet_id_and_gid(url):
    s = url.strip()
    if "/" not in s and len(s) > 20: return s, "0"
    u = urlparse(s)
    parts = [p for p in u.path.split("/") if p]
    sid = parts[3] if len(parts)>3 and parts[2]=="d" else parts[-1]
    gid = parse_qs(u.query).get("gid",["0"])[0]
    return sid,gid

def load_gsheet(url):
    sid,gid=_sheet_id_and_gid(url)
    df=pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}")
    return df

def load_docx(file_path):
    doc = Document(file_path)
    lines=[p.text for p in doc.paragraphs]
    return "\n".join(lines)

# --------------------------------------------
# UI
# --------------------------------------------
st.set_page_config(page_title="AI Script Generator (Bangla)", layout="wide")

st.title("🤖 AI Script Generator (Bangla)")
st.caption("Generate elaborated, persuasive investor-facing scripts — by UCB AML")

with st.sidebar:
    st.header("⚙️ Controls")
    ct = st.selectbox("ক্লায়েন্ট টাইপ", CLIENT_TYPES)
    prod = st.selectbox("পণ্য/ফোকাস", [x["product"] for x in SAMPLES[ct]])
    horizon = st.selectbox("সময়সীমা", ["৬–১২ মাস","১–৩ বছর","৩+ বছর"])
    risk = st.radio("ঝুঁকি", ["কম","মধ্যম","উচ্চ"], horizontal=True)
    extra = st.text_area("অতিরিক্ত নোট", "SIP অগ্রাধিকার, শরীয়াহ পছন্দ ইত্যাদি")
    tone = st.selectbox("Script Tone", ["Elaborated","Factual","Sales Pitch"])
    temp = st.slider("Temperature", 0.3, 1.5, 0.9, 0.05)
    max_tok = st.slider("Max tokens", 300, 900, 600, 50)
    include_facts = st.checkbox("পণ্য-তথ্য যোগ করুন (হুবহু)", value=True)

st.markdown("### ✨ Generated Script")
if st.button("Generate Script"):
    with st.spinner("AI generating your script..."):
        output = generate_script(ct, prod, horizon, risk, extra, temp, max_tok, include_facts, tone)
        st.text_area("Generated Script", output, height=600)
        st.download_button("⬇️ Download .txt", output.encode("utf-8"), "script.txt")

st.markdown("---")
st.markdown("#### 📥 Load Samples from Google Sheet or Doc (Optional)")
col1, col2 = st.columns(2)
with col1:
    gsheet_url = st.text_input("Google Sheet URL / ID")
    if st.button("Load from Google Sheet"):
        try:
            df = load_gsheet(gsheet_url)
            st.write(df.head())
            st.success(f"Loaded {len(df)} rows from Sheet.")
        except Exception as e:
            st.error(f"Failed: {e}")
with col2:
    gdoc_id = st.text_input("Google Doc ID")
    if st.button("Load from Google Doc"):
        try:
            path = gdown.download(f"https://docs.google.com/document/d/{gdoc_id}/export?format=docx",
                                  "temp.docx", quiet=True)
            text = load_docx(path)
            st.text_area("Doc Preview", text[:2000])
            st.success("Google Doc loaded successfully.")
        except Exception as e:
            st.error(f"Failed: {e}")

st.markdown("---")
st.caption("© UCB Asset Management Ltd | Internal demo & training use")
