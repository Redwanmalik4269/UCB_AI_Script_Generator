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
# --------------------------------------------
# Defaults (now seeded from the uploaded master script)
# --------------------------------------------
SAMPLES_DEFAULT = {
    # Generic master flow (used as a universal style shot)
    "ইনকামিং কল — মাস্টার স্টাইল গাইড": [{
        "product": "—",
        "script": """আসসালামু আলাইকুম, ইউসিবি অ্যাসেট ম্যানেজমেন্ট থেকে (আপনার নাম) বলছি। আপনাকে কীভাবে সহযোগিতা করতে পারি?

প্রথমে আপনার লক্ষ্যটা একটু বুঝে নিই—আপনি কি ট্যাক্স বাঁচাতে চান, ব্যাংক এফডিআর/সঞ্চয়পত্রের মতো স্থিতিশীল আয় চান, দীর্ঘমেয়াদে সম্পদ গড়তে চান, নাকি শরীয়াহসম্মত বিনিয়োগ দেখতে চান?

আপনার উত্তরের ভিত্তিতে আমি সমাধান সাজিয়ে বলছি। আলোচনা চলবে ধাপে ধাপে: (১) শুভেচ্ছা ও প্রয়োজন বোঝা, (২) প্রোডাক্ট কিভাবে কাজ করে, (৩) ঝুঁকি–রিটার্ন ব্যাখ্যা, (৪) বাস্তব উদাহরণ/সিনারিও, (৫) কীভাবে শুরু করবেন—KYC, SIP/লাম্পসাম, রিডেম্পশন, (৬) CTA ও পরবর্তী পদক্ষেপ।

প্রয়োজনে জটিল প্রশ্ন বা বড় অঙ্কের বিনিয়োগের ক্ষেত্রে আমি আপনাকে আমাদের সিনিয়র ইনভেস্টমেন্ট স্পেশালিস্ট/রিলেশনশিপ ম্যানেজারের সাথে যুক্ত করবো, যাতে আপনি সর্বোত্তম নির্দেশনা পান।"""
    }],

    # Intent 1: নিরাপদ/স্থিতিশীল আয় (সঞ্চয়পত্রের বিকল্প)
    "নিরাপদ ও স্থিতিশীল আয় (সঞ্চয়পত্রের বিকল্প)": [{
        "product": "UCB Income Plus Fund",
        "script": """আপনারা যারা নিরাপদ বিনিয়োগ পছন্দ করেন এবং কষ্টার্জিত টাকায় ঝুঁকি কম রাখতে চান, তাদের জন্য ‘UCB Income Plus Fund’ বাস্তবসম্মত সমাধান। ফান্ডের বড় অংশ সরকারি ট্রেজারি বিল/বন্ডে বিনিয়োগ হওয়ায় ডিফল্টের ঝুঁকি কম—অনেকটা সঞ্চয়পত্রের মতো নিরাপত্তা, তবে কিছু গুরুত্বপূর্ণ সুবিধা বাড়তি।

উদাহরণস্বরূপ:
• আয়ের সম্ভাবনা: সুদের পরিবেশ ও মার্কেট কন্ডিশন অনুযায়ী আকর্ষণীয় নেট রিটার্নের সম্ভাবনা থাকে (গ্যারান্টি নয়)।
• কোনো স্ল্যাব নেই: ইউনিটভিত্তিক একই হার—বড়/ছোট বিনিয়োগে হার আলাদা হয় না।
• তারল্য: সাধারণত ১০০ দিন পর রিডেম্পশনে চার্জ থাকে না—প্রয়োজন হলে সহজে তুলতে পারেন।
• কর-সুবিধা: প্রযোজ্য বিধি অনুযায়ী আয়কর রিবেট পাওয়ার সম্ভাবনা থাকে।

আমরা প্রথমে আপনার প্রয়োজনটা ম্যাপ করি—মাসিক আয়ের টার্গেট, কতদিন রাখতে চান, এবং ব্যাংক অ্যাকাউন্ট/BEFTN এর মাধ্যমে কীভাবে সহজে SIP বা লাম্পসাম সেটআপ করবেন। চাইলে শুরু থেকে শেষ পর্যন্ত আমি ডকুমেন্টেশন, KYC এবং রিডেম্পশন প্রসেস বুঝিয়ে দেব।

শেষে CTA: আপনার সুবিধা হলে আজই ন্যূনতম অংকে শুরু করতে পারেন, পরে ধীরে ধীরে বাড়াতে পারবেন। চাইলে আমি এখনই ব্রোশিওর/ফ্যাক্টশিট ইমেইল/হোয়াটসঅ্যাপে পাঠিয়ে দিচ্ছি এবং একটি ফলো-আপ কল শিডিউল করছি।"""
    }],

    # Intent 2: দীর্ঘমেয়াদে সম্পদ গঠন (ইকুইটি-অরিয়েন্টেড)
    "দীর্ঘমেয়াদে সম্পদ গঠন (ইকুইটি-অরিয়েন্টেড)": [{
        "product": "UCB AML First Mutual Fund",
        "script": """যারা শেয়ারবাজারের প্রবৃদ্ধির সাথে থেকে দীর্ঘমেয়াদে সম্পদ গড়তে চান, তাদের জন্য ‘UCB AML First Mutual Fund’ একটি কার্যকর বিকল্প। আমরা আপনার হয়ে গবেষণাভিত্তিকভাবে মানসম্পন্ন/ব্লু-চিপ কোম্পানিতে বিনিয়োগ করি—যেমন টেকসই নগদপ্রবাহ, শক্তিশালী ব্যালান্স শিট ও প্রতিযোগিতামূলক সুবিধা থাকা ব্যবসা।

এখানে বোঝার বিষয়:
• স্বল্পমেয়াদে ওঠানামা স্বাভাবিক; তাই সময়সীমা ৩–৫ বছর বা তদূর্ধ্ব হলে সম্ভাব্য ফল ভালো দেখা যায় (গ্যারান্টি নয়)।
• নিয়মিত SIP বাজারের ভোলাটিলিটি গড়িয়ে দেয়; দামের উত্থান-পতনে গড় ক্রয়মূল্য নিয়ন্ত্রিত হয়।
• পোর্টফোলিও রিভিউ: লাইফ-ইভেন্ট বা বাজার পরিবর্তনে আমরা পুনর্বিন্যাস করি—ঝুঁকি/লক্ষ্য অনুযায়ী।

কীভাবে শুরু করবেন: (১) KYC/ফর্ম, (২) ব্যাংক ট্রান্সফার বা SIP standing instruction, (৩) কনফার্মেশন ও ট্রান্স্যাকশন স্টেটমেন্ট, (৪) ত্রৈমাসিক রিভিউ কল। আজ কি আমরা একটি ছোট SIP (ধরা যাক ৳৩–১০ হাজার/মাস) দিয়ে শুরু করি? পরে আপনার সুবিধামত বাড়ানো যাবে।"""
    }],

    # Intent 3: শরীয়াহসম্মত/হালাল বিনিয়োগ
    "শরীয়াহসম্মত হালাল বিনিয়োগ": [{
        "product": "UCB Taqwa Growth Fund",
        "script": """আপনি যদি ইসলামী শরীয়াহ নীতিমালা মেনে হালাল উপায়ে বিনিয়োগ করতে চান, ‘UCB Taqwa Growth Fund’ সেই উদ্দেশ্যে তৈরি। ফান্ডটি কেবল শরীয়াহ-সম্মত কোম্পানিতে বিনিয়োগ করে; সুদভিত্তিক ব্যাংক/তামাক ইত্যাদি সেক্টর এড়ানো হয়। 

আস্থা বাড়ায় যে বিষয়গুলো:
• শরীয়াহ স্ক্রিনিং: ব্যবসার প্রকৃতি, ঋণ অনুপাত ইত্যাদি মানদণ্ড পূরণ করেই নির্বাচন।
• ডিভিডেন্ড পিউরিফিকেশন: অনিচ্ছাকৃত আয়ের অংশ দাতব্যে প্রদান—আয়কে হালাল রাখতে।
• দীর্ঘমেয়াদে প্রবৃদ্ধি-কেন্দ্রিক ভাবনা; স্বল্পমেয়াদে ওঠানামা স্বাভাবিক, তাই লক্ষ্য/সময়সীমা গুরুত্বপূর্ণ।

অনবোর্ডিং সহজ: ন্যূনতম ইউনিট ক্রয়, BEFTN/ব্যাংক ট্রান্সফার, এবং নিয়মিত স্টেটমেন্ট। ইচ্ছা হলে আমি এখনই ফান্ডের শরীয়াহ বোর্ড নীতিমালা ও ফ্যাক্টশিট পাঠিয়ে দেই—তারপর আপনার সুবিধামতো একটি বিস্তারিত আলোচনার স্লট ঠিক করি।"""
    }],

    # Intent 4: FAQ/হ্যান্ডওভার/CTA স্টাইলে
    "FAQ / হ্যান্ডওভার / CTA ফ্লো": [{
        "product": "—",
        "script": """সাধারণ প্রশ্নের উত্তর:
• শুরুতে কী লাগবে? — NID (আপনি ও নমিনি), ছবি, ব্যাংক চেক পাতার ছবি, ফর্ম; দরকার হলে BO একাউন্ট আমরা খুলতে সহায়তা করি।
• টাকা তুলবো কীভাবে? — রিডেম্পশন ফর্ম ইমেইল/হোয়াটসঅ্যাপে দিলেই হবে; আমরা আপনার ব্যাংক অ্যাকাউন্টে পাঠাই। Income Plus-এ সাধারণত ১০০ দিন পর চার্জ থাকে না (টার্মস প্রযোজ্য)।
• BO একাউন্ট নেই? — সমস্যা নয়; পার্টনার ব্রোকারেজের মাধ্যমে খোলায় সহায়তা করি।

হ্যান্ডওভার (প্রয়োজনে): “আপনার প্রশ্নটি গুরুত্বপূর্ণ। বিষয়টি সর্বোত্তমভাবে সমাধানের জন্য আমি এখনই আপনাকে আমাদের সিনিয়র ইনভেস্টমেন্ট স্পেশালিস্ট/রিলেশনশিপ ম্যানেজারের সাথে যুক্ত করছি।”

CTA/পরবর্তী পদক্ষেপ: “আপনার অনুমতি পেলে আমি এখনই ব্রোশিওর/লিংক পাঠাচ্ছি। আজ কি আমরা একটি ছোট SIP দিয়ে শুরু করবো, নাকি লাম্পসাম? আপনার জন্য কখন একটি ফলো-আপ কল সুবিধাজনক?”"""
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

