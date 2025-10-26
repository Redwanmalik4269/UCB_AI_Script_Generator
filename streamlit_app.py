# -*- coding: utf-8 -*-
"""
AI Script Generator (Bangla) — External-only (no in-code samples)
- Style exemplars: Google Doc (ID or link) -> DOCX export -> extracted paragraphs
- Intent/Product samples: Google Sheet (ID or link) -> CSV export -> (intent, product, script)
- Elaborated, varied generation with anti-copy & no-facts-echo
"""

import os, re, io, time, random, difflib, requests
import pandas as pd
import streamlit as st
from urllib.parse import urlparse, parse_qs
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from docx import Document
import gdown

# =========================
# 🔧 OPTIONAL CONFIG (can leave blank and use the UI)
# =========================
MASTER_DOC_ID   = ""   # e.g. "1AbCdEfG..." (Google Doc ID) — leave "" to supply in UI
MASTER_DOC_LINK = ""   # e.g. full GDoc link OR a direct .docx URL — leave "" to supply in UI
GSHEET_ID       = ""   # e.g. "1Xyz..." (Google Sheet ID) — leave "" to supply in UI
GSHEET_LINK     = ""   # e.g. full Google Sheet link — leave "" to supply in UI
GSHEET_GID      = "0"  # Sheet tab gid (if using GSHEET_ID)
MODEL_NAME      = "google/flan-t5-small"  # lightweight for Streamlit Cloud / Py3.13

# =========================
# Product facts (verbatim at the end)
# =========================
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
    },
    "UCB Taqwa Growth Fund": {
        "indicative_return": "শরীয়াহসম্মত ইকুইটি—দীর্ঘমেয়াদে বাজারনির্ভর",
        "exit_load": "স্কিম তথ্যপত্র অনুযায়ী এক্সিট লোড",
        "sip": "SIP: ন্যূনতম ৳৩,০০০/মাস",
        "non_sip": "Non-SIP: ন্যূনতম 500 unit",
        "tax": "শরীয়াহ অনুগত; প্রযোজ্য ক্ষেত্রে কর-সুবিধা"
    }
}

# =========================
# Utils
# =========================
def _paragraphize(txt: str) -> str:
    if not isinstance(txt, str): return ""
    txt = re.sub(r'(?m)^\s*[•\-\u2022]+\s*', '', txt)  # bullets
    txt = re.sub(r'(?m)^\s*\d+\.\s*', '', txt)         # 1. 2. 3.
    txt = txt.replace('— — —', ' ')
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def _len_ok(s: str, n: int = 420) -> bool:
    return bool(s and len(s) >= n)

def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()

def _sheet_id_and_gid(url_or_id: str):
    s = (url_or_id or "").strip()
    if "/" not in s and len(s) > 20:  # pure ID
        return s, "0"
    u = urlparse(s)
    parts = [p for p in u.path.split("/") if p]
    sid = parts[3] if len(parts) > 3 and parts[2] == "d" else parts[-1]
    gid = parse_qs(u.query).get("gid", ["0"])[0]
    return sid, gid

def facts_for(product: str) -> str:
    f = PRODUCT_FACTS.get(product or "", {})
    if not f: return ""
    return " | ".join([
        f"রিটার্ন: {f['indicative_return']}",
        f"এক্সিট লোড: {f['exit_load']}",
        f"{f['sip']}", f"{f['non_sip']}", f"{f['tax']}"
    ])

# =========================
# External loaders (Doc/Sheet)
# =========================
def download_docx_from_gdoc_id(doc_id: str, out_path: str) -> str:
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
    return gdown.download(url, out_path, quiet=True)

def download_docx_from_link(link: str, out_path: str) -> str:
    # Convert Google Doc view link to export if needed
    if "docs.google.com/document/d/" in link and "export?format=docx" not in link:
        try:
            doc_id = link.split("/document/d/")[1].split("/")[0]
            link = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
        except Exception:
            pass
    r = requests.get(link, timeout=30)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path

def extract_style_shots_from_docx(doc_path: str, max_shots: int = 4):
    if not os.path.exists(doc_path): return []
    doc = Document(doc_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    cleaned = []
    for p in paragraphs:
        pp = _paragraphize(p)
        if len(pp) >= 180 and not re.match(r"^[•\-\d]+", pp):
            cleaned.append(pp)
    if not cleaned: return []
    if len(cleaned) <= max_shots: return cleaned
    step = max(1, len(cleaned)//max_shots)
    return [cleaned[i] for i in range(0, len(cleaned), step)][:max_shots]

def load_gsheet_df(url_or_id: str, gid_hint: str = "0") -> pd.DataFrame:
    sid, gid = _sheet_id_and_gid(url_or_id)
    gid = gid or gid_hint or "0"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    return pd.read_csv(csv_url)

def samples_from_df(df: pd.DataFrame):
    cols = {c.lower().strip(): c for c in df.columns}
    need = {"intent", "product", "script"}
    if not need.issubset(set(cols.keys())):
        raise ValueError(f"Sheet must contain columns: {sorted(need)}. Found: {list(df.columns)}")
    recs = df[[cols["intent"], cols["product"], cols["script"]]].fillna("")
    samples = {}
    for _, row in recs.iterrows():
        intent  = str(row[cols["intent"]]).strip()
        product = str(row[cols["product"]]).strip() or "—"
        script  = _paragraphize(str(row[cols["script"]]))
        if not intent or not script:
            continue
        samples.setdefault(intent, []).append({"product": product, "script": script})
    if not samples:
        raise ValueError("No valid rows (need non-empty intent + script).")
    return samples

# ---------------- Model / Generator (local-or-remote) ----------------
import os, sys, json, time
import requests
import streamlit as st

MODEL_NAME = "google/flan-t5-small"
HF_API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
HF_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")

def _have_torch() -> bool:
    try:
        import torch  # noqa
        return True
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def get_generator():
    """
    Returns a callable generate(prompt, **params) that abstracts away
    local vs remote inference.
    """
    if _have_torch():
        # --- Local pipeline (fastest if torch exists) ---
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
        tok = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        pipe = pipeline("text2text-generation", model=mdl, tokenizer=tok, device_map="cpu")

        def _gen_local(prompt, max_new_tokens=500, temperature=0.8, top_p=0.95, top_k=50, repetition_penalty=1.05):
            out = pipe(
                prompt,
                max_new_tokens=int(max_new_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                top_k=int(top_k),
                repetition_penalty=float(repetition_penalty),
            )[0]["generated_text"]
            return out

        st.info("⚙️ Using local Transformers pipeline (PyTorch detected).", icon="⚙️")
        return _gen_local

    # --- Remote inference (no torch needed) ---
    headers = {"Accept": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    def _gen_remote(prompt, max_new_tokens=500, temperature=0.8, top_p=0.95, top_k=50, repetition_penalty=1.05):
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": int(max_new_tokens),
                "temperature": float(temperature),
                "top_p": float(top_p),
                "repetition_penalty": float(repetition_penalty),
            },
            "options": {"wait_for_model": True, "use_cache": True}
        }
        try:
            r = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            # API returns a list of dicts with 'generated_text'
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"]
            # Some endpoints use {'generated_text': '...'}
            if isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            # Or {'error': '...'}
            if isinstance(data, dict) and "error" in data:
                raise RuntimeError(data["error"])
            return json.dumps(data, ensure_ascii=False)
        except requests.exceptions.ReadTimeout:
            raise RuntimeError("HF inference timeout. Try again or reduce max tokens.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HF inference error: {e}")

    st.warning("🌐 Using Hugging Face Inference API (no PyTorch). "
               "Add a HUGGINGFACEHUB_API_TOKEN in app secrets for better reliability.", icon="🌐")
    return _gen_remote





# =========================
# Prompting (two-pass + anti-copy + variability)
# =========================
def _facts_block(product: str, include: bool) -> str:
    if not include:
        return ""
    ftxt = facts_for(product)
    return f"\n[FACTS]\n{ftxt}\n[/FACTS]\n" if ftxt else ""

def pick_style_shots(style_shots: list, k: int = 3) -> list:
    """Randomly rotate which style exemplars are used to avoid sameness."""
    if not style_shots:
        return []
    k = max(1, min(k, len(style_shots)))
    return random.sample(style_shots, k)

def build_body_prompt(
    selected_shots,
    intent_sample,
    product,
    client_type,
    horizon,
    risk,
    extra,
    tone,
    include_facts=True,
    nonce=""
):
    styled = ""
    if selected_shots:
        blocks = [f"উদাহরণ {i} (স্টাইল মাত্র; কপি করবেন না):\n{s}\n" for i, s in enumerate(selected_shots, 1)]
        styled = "\n".join(blocks)

    ex = _paragraphize(intent_sample or "")

    tone_rule = {
        "Factual": "সংক্ষিপ্ত, তথ্যনির্ভর ও নিরপেক্ষ থাকুন।",
        "Elaborated": "ব্যাখ্যামূলক, সহানুভূতিশীল ও শিক্ষামূলক; ১–২টি উদাহরণ/সিনারিও দিন।",
        "Sales Pitch": "আস্থাজনক ও প্ররোচিত; গ্রাহকের সুবিধা স্পষ্ট করুন, তবু বাড়াবাড়ি নয়।"
    }.get(tone, "ব্যাখ্যামূলক টোন।")

    rules = [
        "ভাষা: খাঁটি বাংলা; কথোপকথনমূলক প্যারাগ্রাফ।",
        "দৈর্ঘ্য: ৪৫০–৭৫০ শব্দ; একাধিক প্যারাগ্রাফ।",
        "কাঠামো: শুভেচ্ছা+ডিসকভারি → প্রোডাক্ট ব্যাখ্যা → ঝুঁকি-রিটার্ন → উদাহরণ/সিনারিও → শুরু করার ধাপ → CTA।",
        "নিচের [FACTS] ব্লক কেবল রেফারেন্স; কোনো অবস্থায় [FACTS]/[/FACTS] বা 'পণ্য-তথ্য' শব্দগুচ্ছ বডিতে লিখবেন না।",
        "‘গ্যারান্টি’ বা ‘ঝুঁকি নেই’ ধরনের দাবি করবেন না।",
        "বাক্য/অনুচ্ছেদ কপি করা যাবে না—নিজস্ব শব্দে নতুনভাবে লিখতে হবে।",
        tone_rule,
        f"ভিন্ন ভঙ্গিতে উপস্থাপন করুন (রূপান্তর আইডি: {nonce})."
    ]

    # ✅ Prebuild strings so there are no backslashes inside { ... } expressions.
    nl = "\n"
    extra_hint = f"অতিরিক্ত স্টাইল হিন্ট (কপি নয়):{nl}{ex}" if ex else ""
    facts_txt = _facts_block(product, include_facts)
    rules_joined = nl.join(rules)

    # Build final prompt (no backslashes inside {...})
    prompt = (
        "আপনি একজন অভিজ্ঞ মিউচুয়াল ফান্ড RM। নিচের উদাহরণগুলোর স্টাইল অনুসরণ করুন কিন্তু কপি করবেন না—"
        "নিজস্ব শব্দে, নতুন বাক্য গঠন ব্যবহার করে একটি পূর্ণাঙ্গ বাংলা স্ক্রিপ্ট লিখুন।"
        f"{nl}{nl}"
        f"{styled}{nl if styled else ''}"
        f"{extra_hint}{nl if extra_hint else ''}{nl}"
        f"{facts_txt}{nl if facts_txt else ''}"
        "নির্দেশনা:"
        f"{nl}- {rules_joined}"
        f"{nl}{nl}"
        "ইনপুট:"
        f"{nl}- ক্লায়েন্ট টাইপ: {client_type}"
        f"{nl}- পণ্য: {product}"
        f"{nl}- সময়সীমা: {horizon}"
        f"{nl}- ঝুঁকি: {risk}"
        f"{nl}- নোট: {extra}"
        f"{nl}{nl}"
        "আউটপুট:\nশুধু কথোপকথনমূলক বডি লিখুন; 'পণ্য-তথ্য' অংশটি এখন লিখবেন না।"
    ).strip()

    return prompt


def _fallback_body(prod, horizon):
    greeting = "আসসালামু আলাইকুম। আমি ইউসিবি অ্যাসেট ম্যানেজমেন্ট থেকে বলছি।"
    discovery = "আপনার লক্ষ্য, সময়সীমা ও ঝুঁকি পছন্দ বুঝে নিয়ে উপযুক্ত পরিকল্পনা সাজাবো।"
    explain = f"{prod} সম্পর্কে সংক্ষেপে—পেশাদার টিম ঝুঁকি–রিটার্নের ভারসাম্য বজায় রেখে বিনিয়োগ করে; {horizon} দিগন্তে চিন্তা করলে সম্ভাবনার পরিসর পরিষ্কার হয়।"
    risk_note = "বাজারে ওঠানামা স্বাভাবিক; পরিকল্পিত SIP/লাম্পসাম মিলিয়ে চললে লক্ষ্যপূরণ সহজ হয় (গ্যারান্টি নয়)।"
    steps = "ধাপ: (১) KYC/ফর্ম (২) ব্যাংক ট্রান্সফার বা SIP সেটআপ (৩) কনফার্মেশন ও স্টেটমেন্ট (৪) রিভিউ।"
    cta = "আজ কি ন্যূনতম অংকে শুরু করবো? আমি এখনই ব্রোশিওর/লিংক পাঠিয়ে দিচ্ছি এবং একটি ফলো-আপ কল সেট করছি।"
    return "\n\n".join([greeting, discovery, explain, risk_note, steps, cta])

def _too_similar_to_any(body: str, shots: list, thresh: float = 0.78) -> bool:
    if not body or not shots: return False
    return any(_similar(body, s) >= thresh for s in shots)

def _too_similar_to_recent(body: str, history: list, thresh: float = 0.76) -> bool:
    for prev in history[-5:]:
        if _similar(body, prev) >= thresh:
            return True
    return False

def generate_script(style_shots, intent_sample, ct, prod, horizon, risk, extra, temp, max_tok, include_facts, tone):
    def _run(prompt, temperature):
        params = dict(
            max_new_tokens=int(max_tok),
            temperature=float(temperature),
            top_p=0.92,
            top_k=60,
            do_sample=True,
            repetition_penalty=1.12,
            no_repeat_ngram_size=4
        )
        return gen(prompt, **params)[0]["generated_text"].strip()

    # rotate style exemplars + add nonce per run
    selected = pick_style_shots(style_shots, k=min(3, len(style_shots) or 1))
    nonce = f"{int(time.time()*1000) % 100000}-{random.randint(100,999)}"

    body_prompt = build_body_prompt(selected, intent_sample, prod, ct, horizon, risk, extra, tone, include_facts, nonce=nonce)

    tries = 0
    body = ""
    while tries < 2:
        tries += 1
        try:
            body = _run(body_prompt, temp if tries == 1 else max(1.05, float(temp) + 0.25))
        except Exception:
            body = ""

        bad = (
            not _len_ok(body) or
            "[FACTS]" in body or "[/FACTS]" in body or
            "পণ্য-তথ্য" in body or
            _too_similar_to_any(body, (style_shots or []) + ([intent_sample] if intent_sample else []), 0.78) or
            _too_similar_to_recent(body, st.session_state.GEN_HISTORY, 0.76)
        )
        if not bad:
            break

        body_prompt += "\n\nপুনর্লিখন নির্দেশ: আগের সংস্করণ থেকে আলাদা কাঠামো, অনুচ্ছেদ ও উদাহরণ ব্যবহার করুন—ভিন্ন শব্দচয়ন ও বাক্যগঠন বজায় রাখুন।"

    if (not _len_ok(body) or
        "[FACTS]" in body or "[/FACTS]" in body or
        "পণ্য-তথ্য" in body or
        _too_similar_to_any(body, (style_shots or []) + ([intent_sample] if intent_sample else []), 0.78) or
        _too_similar_to_recent(body, st.session_state.GEN_HISTORY, 0.76)):
        body = _fallback_body(prod, horizon)

    body = re.sub(r"\[/?FACTS\]", "", body, flags=re.I)

    # Append facts & disclaimer (verbatim)
    tail = ""
    if include_facts:
        tail += "\n\nপণ্য-তথ্য (হুবহু): " + facts_for(prod)
    tail += "\n\nনোট: মিউচুয়াল ফান্ড বাজারনির্ভর; পূর্বের আয় ভবিষ্যতের নিশ্চয়তা নয়।"

    final = (body.strip() + tail)

    # remember this body so the next run avoids repeating it
    st.session_state.GEN_HISTORY.append(body.strip())
    if len(st.session_state.GEN_HISTORY) > 6:
        st.session_state.GEN_HISTORY = st.session_state.GEN_HISTORY[-6:]

    return final

# =========================
# Session state init
# =========================
if "STYLE_SHOTS" not in st.session_state: st.session_state.STYLE_SHOTS = []
if "SAMPLES" not in st.session_state:     st.session_state.SAMPLES = {}
if "GEN_HISTORY" not in st.session_state: st.session_state.GEN_HISTORY = []
# --- previews for UX ---
if "STYLE_PREVIEW" not in st.session_state: st.session_state.STYLE_PREVIEW = ""
if "SHEET_PREVIEW" not in st.session_state: st.session_state.SHEET_PREVIEW = {"intent": "", "product": "", "script": ""}

def ensure_style_loaded(doc_id: str, doc_link: str):
    out_path = "master_style.docx"
    if doc_id:
        download_docx_from_gdoc_id(doc_id, out_path)
    elif doc_link:
        download_docx_from_link(doc_link, out_path)
    else:
        return False
    if os.path.exists(out_path):
        st.session_state.STYLE_SHOTS = extract_style_shots_from_docx(out_path, max_shots=4)
        return bool(st.session_state.STYLE_SHOTS)
    return False

def ensure_samples_loaded(sheet_id: str, sheet_link: str, gid: str = "0"):
    if sheet_id:
        df = load_gsheet_df(sheet_id, gid_hint=gid or "0")
    elif sheet_link:
        df = load_gsheet_df(sheet_link, gid_hint="0")
    else:
        return False
    st.session_state.SAMPLES = samples_from_df(df)
    return True

# =========================
# UI
# =========================
st.set_page_config(page_title="AI Script Generator (Bangla)", layout="wide")
st.title("🤖 AI Script Generator (Bangla)")
st.caption("External-only: style from Google Doc, samples from Google Sheet")

with st.expander("🔗 Connect your sources", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        doc_in = st.text_input("Google Doc ID or direct DOCX link", value=MASTER_DOC_ID or MASTER_DOC_LINK)
        if st.button("Load Style (Docx)"):
            with st.spinner("Fetching DOCX..."):
                ok = ensure_style_loaded(
                    doc_id=doc_in if "/" not in (doc_in or "") else "",
                    doc_link=doc_in if "/" in (doc_in or "") else ""
                )
            if ok:
                n = len(st.session_state.STYLE_SHOTS)
                st.session_state.STYLE_PREVIEW = (st.session_state.STYLE_SHOTS[0] or "")[:400]
                st.success(f"✅ Loaded {n} style paragraph{'s' if n>1 else ''}.")
            else:
                st.session_state.STYLE_PREVIEW = ""
                st.error("❌ Failed to load style — ensure the Doc is shared: ‘Anyone with the link → Viewer’.")
            st.rerun()
    with c2:
        sheet_in = st.text_input("Google Sheet ID or link (headers: intent, product, script)", value=GSHEET_ID or GSHEET_LINK)
        gid_in   = st.text_input("Sheet gid (tab id, default 0)", value=GSHEET_GID or "0")
        if st.button("Load Samples (Sheet)"):
            with st.spinner("Fetching Sheet..."):
                try:
                    ok = ensure_samples_loaded(
                        sheet_id=sheet_in if "/" not in (sheet_in or "") else "",
                        sheet_link=sheet_in if "/" in (sheet_in or "") else "",
                        gid=gid_in or "0"
                    )
                except Exception as e:
                    ok = False
                    st.error(f"❌ Error while loading sheet: {e}")
            if ok:
                total_rows = sum(len(v) for v in st.session_state.SAMPLES.values())
                intents = len(st.session_state.SAMPLES)
                first_intent = next(iter(st.session_state.SAMPLES.keys()))
                first_row = st.session_state.SAMPLES[first_intent][0]
                st.session_state.SHEET_PREVIEW = {
                    "intent": first_intent,
                    "product": first_row.get("product", ""),
                    "script": (first_row.get("script", "") or "")[:400],
                }
                st.success(f"✅ Loaded {intents} intents / {total_rows} rows from sheet.")
            else:
                st.session_state.SHEET_PREVIEW = {"intent":"", "product":"", "script":""}
                st.warning("⚠️ Could not load sheet — confirm link/ID and public sharing.")
            st.rerun()

# Status + previews
st.info(f"Style shots: {len(st.session_state.STYLE_SHOTS)} | Intents: {len(st.session_state.SAMPLES)}")

with st.expander("👀 Loaded content preview", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Master style (from Google Doc)**")
        if st.session_state.STYLE_PREVIEW:
            st.code(st.session_state.STYLE_PREVIEW, language="markdown")
        else:
            st.info("No style loaded yet.")
    with c2:
        st.markdown("**Sample row (from Google Sheet)**")
        sp = st.session_state.SHEET_PREVIEW
        if sp.get("intent"):
            st.write(f"**Intent:** {sp['intent']}")
            st.write(f"**Product:** {sp['product']}")
            st.code(sp["script"], language="markdown")
        else:
            st.info("No sheet loaded yet.")

# Controls (enabled only when both sources exist)
can_generate = bool(st.session_state.STYLE_SHOTS and st.session_state.SAMPLES)

with st.sidebar:
    st.header("⚙️ Controls")
    if can_generate:
        ct = st.selectbox("ক্লায়েন্ট টাইপ", list(st.session_state.SAMPLES.keys()))
        products = [r.get("product","—") for r in st.session_state.SAMPLES.get(ct, [])]
        prod = st.selectbox("পণ্য/ফোকাস", products or ["—"])
        intent_sample = next((r.get("script","") for r in st.session_state.SAMPLES.get(ct, []) if r.get("product")==prod), "") \
                        or st.session_state.SAMPLES.get(ct, [{}])[0].get("script","")
    else:
        ct = prod = intent_sample = ""

    horizon = st.selectbox("সময়সীমা", ["৬–১২ মাস","১–৩ বছর","৩+ বছর"])
    risk = st.radio("ঝুঁকি", ["কম","মধ্যম","উচ্চ"], horizontal=True)
    extra = st.text_area("অতিরিক্ত নোট", "SIP অগ্রাধিকার, শরীয়াহ পছন্দ ইত্যাদি")
    tone = st.selectbox("Script Tone", ["Elaborated","Factual","Sales Pitch"])
    temp = st.slider("Temperature", 0.3, 1.5, 0.95, 0.05)
    max_tok = st.slider("Max tokens", 450, 900, 700, 50)
    include_facts = st.checkbox("পণ্য-তথ্য যোগ করুন (হুবহু)", value=True)
    force_variant = st.checkbox("🔁 Force a fresh variant", value=False)

st.markdown("### ✨ Generated Script")
btn = st.button("Generate Script", disabled=not can_generate)
if not can_generate:
    st.warning("Connect both: a Google Doc (style) and a Google Sheet (samples) to enable generation.")

if btn and can_generate:
    with st.spinner("AI generating your script..."):
        out = generate_script(
            style_shots=st.session_state.STYLE_SHOTS,
            intent_sample=intent_sample,
            ct=ct, prod=prod, horizon=horizon, risk=risk, extra=extra,
            temp=(temp + 0.25 if force_variant else temp),
            max_tok=max_tok, include_facts=include_facts, tone=tone
        )
        st.text_area("Generated Script", out, height=600)
        st.download_button("⬇️ Download .txt", out.encode("utf-8"), "script.txt")

st.markdown("---")
st.caption("© UCB Asset Management Ltd | External-data-driven — no in-code samples")





