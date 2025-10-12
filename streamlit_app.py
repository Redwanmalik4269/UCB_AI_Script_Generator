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
import transformers
st.write("Transformers version:", transformers.__version__)
st.write("Available modules:", dir(transformers)[:15])

# ============ Utility functions ============
def _paragraphize(txt):
    if not isinstance(txt, str): return ""
    txt = re.sub(r'(?m)^\s*[•\-\u2022]+\s*', '', txt)
    txt = re.sub(r'(?m)^\s*\d+\.\s*', '', txt)
    txt = txt.replace('— — —', ' ')
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

# ============ Default samples ============
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

# ============ Product Facts ============
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
    return " | ".join([f"রিটার্ন: {f['indicative_return']}",
                       f"এক্সিট লোড: {f['exit_load']}",
                       f"{f['sip']}", f"{f['non_sip']}", f"{f['tax']}"])

# ============ Model ============
MODEL_NAME = "google/flan-t5-small"
st.cache_resource(show_spinner=False)
def load_model():
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    pipe = pipeline("text2text-generation", model=mdl, tokenizer=tok, device_map="auto")
    return pipe
gen = load_model()

# ============ Prompt & Generation ============
def _facts_block(product, include):
    if not include: return ""
    ftxt = facts_for(product)
    return f"\n\nপণ্য-তথ্য (হুবহু ব্যবহার করুন): {ftxt}\n" if ftxt else ""

def build_prompt(client_type, product, horizon, risk, extra, include_facts=True):
    shots = SAMPLES.get(client_type, [])
    ex = _paragraphize(shots[0]["script"]) if shots else ""
    rules = [
        "ভাষা: খাঁটি বাংলা।",
        "দৈর্ঘ্য: ৩৫০–৬০০ শব্দ; উদাহরণ ও বাস্তব প্রেক্ষাপটসহ।",
        "পণ্য-তথ্য ব্লক হুবহু রাখুন; কোনো পরিবর্তন নয়।"
    ]
    prompt = f"""আপনি একজন অভিজ্ঞ মিউচুয়াল ফান্ড RM।
উদাহরণ:
{ex}
{_facts_block(product, include_facts)}
নির্দেশনা:
{chr(10).join(rules)}
ইনপুট:
- ক্লায়েন্ট টাইপ: {client_type}
- পণ্য: {product}
- সময়সীমা: {horizon}
- ঝুঁকি: {risk}
- নোট: {extra}
আউটপুট (Bangla স্ক্রিপ্ট):"""
    return prompt

def generate_script(ct, prod, horizon, risk, extra, temp, max_tok, include_facts):
    prompt = build_prompt(ct, prod, horizon, risk, extra, include_facts)
    params = dict(max_new_tokens=int(max_tok), temperature=float(temp),
                  top_p=0.95, top_k=50, repetition_penalty=1.05)
    res = gen(prompt, **params)[0]["generated_text"]
    if "পণ্য-তথ্য" not in res and include_facts:
        res += "\n\nপণ্য-তথ্য (হুবহু): " + facts_for(prod)
    res += "\n\nনোট: মিউচুয়াল ফান্ড বাজারনির্ভর; পূর্বের আয় ভবিষ্যতের নিশ্চয়তা নয়।"
    return res

# ============ Loaders ============
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

# ============ Streamlit App Layout ============
st.set_page_config(page_title="AI Script Generator (Bangla)", layout="wide")

st.title("🤖 AI Script Generator (Bangla)")
st.caption("Generate investor-facing call scripts with product facts intact — by UCB AML")

with st.sidebar:
    st.header("⚙️ Controls")
    ct = st.selectbox("ক্লায়েন্ট টাইপ", CLIENT_TYPES)
    prod = st.selectbox("পণ্য/ফোকাস", [x["product"] for x in SAMPLES[ct]])
    horizon = st.selectbox("সময়সীমা", ["৬–১২ মাস","১–৩ বছর","৩+ বছর"])
    risk = st.radio("ঝুঁকি", ["কম","মধ্যম","উচ্চ"], horizontal=True)
    extra = st.text_area("অতিরিক্ত নোট", "SIP অগ্রাধিকার, শরীয়াহ পছন্দ ইত্যাদি")
    temp = st.slider("Temperature", 0.3, 1.5, 0.8, 0.05)
    max_tok = st.slider("Max tokens", 200, 900, 500, 50)
    include_facts = st.checkbox("পণ্য-তথ্য যোগ করুন (হুবহু)", value=True)

st.markdown("### ✨ Script Output")
if st.button("Generate Script"):
    with st.spinner("AI generating..."):
        output = generate_script(ct, prod, horizon, risk, extra, temp, max_tok, include_facts)
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
st.caption("© UCB Asset Management Ltd | For internal demo and training use")

