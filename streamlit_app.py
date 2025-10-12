# -*- coding: utf-8 -*-
"""
AI Script Generator (Bangla) — Streamlit version
Author: UCB Asset Management (UCB AML)
"""

import os, re
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
# Defaults (will be overwritten by Google Sheet if you load it)
# --------------------------------------------
SAMPLES_DEFAULT = {
    "নিরাপদ ও নিশ্চিত রিটার্ন (সঞ্চয়পত্রের বিকল্প)": [{
        "product": "UCB Income Plus Fund",
        "script": "যারা নিরাপদ বিনিয়োগ পছন্দ করেন..."
    }],
    "দীর্ঘমেয়াদে সম্পদ গঠন (ইকুইটি-অরিয়েন্টেড)": [{
        "product": "UCB AML First Mutual Fund",
        "script": "দীর্ঘমেয়াদি সম্পদ গঠনের জন্য..."
    }]
}

# Put samples into session state so we can replace them at runtime
if "SAMPLES" not in st.session_state:
    st.session_state.SAMPLES = SAMPLES_DEFAULT

def client_types():
    return list(st.session_state.SAMPLES.keys())

def products_for(ct: str):
    rows = st.session_state.SAMPLES.get(ct, [])
    return [r.get("product","—") for r in rows] or ["—"]

# --------------------------------------------
# Product facts (static for now)
# --------------------------------------------
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
MODEL_NAME = "google/flan-t5-small"  # small = faster on Streamlit Cloud

@st.cache_resource(show_spinner=False)
def load_model():
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    return pipeline("text2text-generation", model=mdl, tokenizer=tok)

gen = load_model()

# --------------------------------------------
# Prompting (two-pass: body then facts)
# --------------------------------------------
def _facts_block(product: str, include: bool) -> str:
    if not include: return ""
    ftxt = facts_for(product)
    return f"\n[FACTS]\n{ftxt}\n[/FACTS]\n" if ftxt else ""

def build_body_prompt(client_type, product, horizon, risk, extra, tone, include_facts=True):
    shots = st.session_state.SAMPLES.get(client_type, [])
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
        "গুরুত্বপূর্ণ: নিচের [FACTS] তথ্যগুলো কেবল রেফারেন্স; বডিতে [FACTS] ব্লকটি প্রিন্ট করবেন না।",
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
    greeting = "আসসালামু আলাইকুম। আমি ইউসিবি অ্যাসেট ম্যানেজমেন্ট থেকে বলছি।"
    discovery = "আপনার লক্ষ্য, সময়সীমা ও ঝুঁকি পছন্দ বুঝে নিতে চাই—তারপর উপযুক্ত পরিকল্পনা সাজাবো।"
    explain = f"{prod} নিয়ে সংক্ষেপে বলি—এই ফান্ডটি পেশাদার টিম দ্বারা পরিচালিত হয় এবং ঝুঁকি-রিটার্নের ভারসাম্য রাখার চেষ্টা করে।"
    risk_note = "বাজারে ওঠানামা থাকেই; স্বল্পমেয়াদে ভোলাটিলিটি সম্ভব, কিন্তু পরিকল্পিতভাবে বিনিয়োগ করলে লক্ষ্যপূরণ সহজ হয়।"
    steps = "শুরু করার ধাপ: (১) KYC/ফর্ম পূরণ (২) ব্যাংক ট্রান্সফার/SIP সেটআপ (৩) কনফার্মেশন (৪) পর্যায়ক্রমে রিভিউ।"
    cta = "আপনি চাইলে আজই SIP শুরু করতে পারি—আমি সব ডকুমেন্ট/লিংক পাঠিয়ে দিচ্ছি।"
    return "\n\n".join([greeting, discovery, explain, risk_note, steps, cta])

def generate_script(ct, prod, horizon, risk, extra, temp, max_tok, include_facts, tone):
    # Pass A: write body (facts hidden from output)
    body_prompt = build_body_prompt(ct, prod, horizon, risk, extra, tone, include_facts)
    params = dict(max_new_tokens=int(max_tok), temperature=float(temp),
                  top_p=0.95, top_k=50, repetition_penalty=1.05)
    try:
        body = gen(body_prompt, **params)[0]["generated_text"].strip()
    except Exception:
        body = ""
    if "[FACTS]" in body or "পণ্য-তথ্য" in body or not _len_ok(body):
        body = _fallback_body(ct, prod, horizon, risk, extra)
    body = re.sub(r"\[/?FACTS\]", "", body, flags=re.I)

    # Pass B: append facts verbatim + disclaimer
    tail = ""
    if include_facts:
        tail += "\n\nপণ্য-তথ্য (হুবহু): " + facts_for(prod)
    tail += "\n\nনোট: মিউচুয়াল ফান্ড বাজারনির্ভর; পূর্বের আয় ভবিষ্যতের নিশ্চয়তা নয়।"
    return body.strip() + tail

# --------------------------------------------
# Google Sheet / Doc helpers
# --------------------------------------------
def _sheet_id_and_gid(url_or_id: str):
    s = (url_or_id or "").strip()
    if "/" not in s and len(s) > 20:
        return s, "0"
    u = urlparse(s)
    parts = [p for p in u.path.split("/") if p]
    sid = parts[3] if len(parts) > 3 and parts[2] == "d" else parts[-1]
    gid = parse_qs(u.query).get("gid", ["0"])[0]
    return sid, gid

def load_gsheet(url_or_id: str) -> pd.DataFrame:
    sid, gid = _sheet_id_and_gid(url_or_id)
    return pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}")

def apply_samples_from_df(df: pd.DataFrame):
    """
    Accepts a DataFrame with headers: intent, product, script.
    Groups rows by intent; allows multiple products/scripts per intent.
    Updates st.session_state.SAMPLES and triggers a rerun.
    """
    cols = {c.lower().strip(): c for c in df.columns}
    need = {"intent", "product", "script"}
    if not need.issubset(set(cols.keys())):
        raise ValueError(f"Sheet must contain columns: {sorted(need)}. Found: {list(df.columns)}")

    # Normalize and build structure
    recs = df[[cols["intent"], cols["product"], cols["script"]]].fillna("")
    samples = {}
    for _, row in recs.iterrows():
        intent = str(row[cols["intent"]]).strip()
        product = str(row[cols["product"]]).strip() or "—"
        script = _paragraphize(str(row[cols["script"]]))
        if not intent or not script:
            continue
        samples.setdefault(intent, []).append({"product": product, "script": script})

    if not samples:
        raise ValueError("No valid rows found (need non-empty intent and script).")

    st.session_state.SAMPLES = samples
    # Reset any cached selections so the sidebar updates cleanly
    st.session_state.pop("ct_sel", None)
    st.session_state.pop("prod_sel", None)
    st.success(f"Loaded {sum(len(v) for v in samples.values())} samples across {len(samples)} intents.")
    st.rerun()

def load_docx(file_path):
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

# --------------------------------------------
# UI
# --------------------------------------------
st.set_page_config(page_title="AI Script Generator (Bangla)", layout="wide")

st.title("🤖 AI Script Generator (Bangla)")
st.caption("Generate elaborated, persuasive investor-facing scripts — by UCB AML")

with st.sidebar:
    st.header("⚙️ Controls")
    # use keys so they get reset when samples are reloaded
    ct = st.selectbox("ক্লায়েন্ট টাইপ", client_types(), key="ct_sel")
    prod = st.selectbox("পণ্য/ফোকাস", products_for(ct), key="prod_sel")
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
    gsheet_url = st.text_input("Google Sheet URL / ID", placeholder="Paste a view link or file ID")
    if st.button("Load from Google Sheet"):
        try:
            df = load_gsheet(gsheet_url)
            st.write(df.head())
            apply_samples_from_df(df)   # <-- THIS replaces SAMPLES and refreshes UI
        except Exception as e:
            st.error(f"Failed to load sheet: {e}")

with col2:
    gdoc_id = st.text_input("Google Doc ID")
    if st.button("Load from Google Doc (.docx export)"):
        try:
            path = gdown.download(
                f"https://docs.google.com/document/d/{gdoc_id}/export?format=docx",
                "temp.docx", quiet=True
            )
            text = load_docx(path)
            st.text_area("Doc Preview", text[:2000])
            st.success("Google Doc loaded successfully.")
        except Exception as e:
            st.error(f"Failed: {e}")

st.markdown("---")
st.caption("© UCB Asset Management Ltd | Internal demo & training use")
