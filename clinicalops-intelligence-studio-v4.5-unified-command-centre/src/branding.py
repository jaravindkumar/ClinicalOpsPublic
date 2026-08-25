import streamlit as st

def inject_enterprise_css():
    _ = st.markdown("""
    <style>
    :root {
      --bg:#070B12; --panel:#0D1420; --panel2:#111A2A; --border:#1E2A3A;
      --text:#E5EEF8; --muted:#94A3B8; --primary:#7DD3FC; --accent:#38BDF8;
      --success:#34D399; --warning:#FBBF24; --danger:#FB7185; --purple:#A78BFA;
    }
    html, body, .stApp {
      background: radial-gradient(circle at top left, rgba(56,189,248,.12), transparent 30%),
                  radial-gradient(circle at top right, rgba(167,139,250,.10), transparent 24%),
                  linear-gradient(180deg,#070B12 0%,#0A0F1A 100%) !important;
      color: var(--text) !important;
    }
    .main .block-container { padding-top:1.6rem; padding-bottom:3rem; max-width:1220px; }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#060914 0%,#0A1020 100%) !important; border-right:1px solid #172033; }
    [data-testid="stSidebar"] * { color:#DDEAFE !important; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select {
      background:#0D1420 !important; border:1px solid #243246 !important; color:#E5EEF8 !important;
    }
    /* Production fail-safe: never expose Streamlit/Python internals in the shared sidebar. */
    [data-testid="stSidebar"] pre,
    [data-testid="stSidebar"] code,
    [data-testid="stSidebar"] [data-testid="stCodeBlock"],
    [data-testid="stSidebar"] [data-testid="stException"],
    [data-testid="stSidebar"] [data-testid*="Help"] {
      display:none !important;
    }
    h1,h2,h3,h4,h5,h6 { color:#E5EEF8 !important; letter-spacing:-.03em; }
    h1 { font-size:2.2rem !important; font-weight:850 !important; }
    h2 { font-size:1.36rem !important; font-weight:800 !important; margin-top:1.25rem !important; }
    h3 { font-size:1.04rem !important; font-weight:780 !important; }
    .stMarkdown, .stText, .stCaption, p, li { color:#CBD5E1; }
    .hero {
      padding:30px 32px; border:1px solid rgba(125,211,252,.22); border-radius:24px;
      background: radial-gradient(circle at 88% 10%,rgba(56,189,248,.22),transparent 28%),
                  radial-gradient(circle at 16% 0%,rgba(167,139,250,.16),transparent 26%),
                  linear-gradient(135deg,rgba(13,20,32,.96),rgba(17,26,42,.94));
      box-shadow:0 22px 60px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.05);
      margin-bottom:22px;
    }
    .hero-kicker {
      display:inline-block; padding:6px 11px; border-radius:999px; background:rgba(56,189,248,.12);
      color:#7DD3FC; border:1px solid rgba(125,211,252,.28); font-size:.76rem; font-weight:800;
      margin-bottom:12px; text-transform:uppercase; letter-spacing:.04em;
    }
    .hero-title { font-size:2.35rem; line-height:1.02; font-weight:900; color:#F8FAFC; letter-spacing:-.055em; margin:3px 0 12px 0; }
    .hero-subtitle { font-size:1rem; color:#AEBBD0; line-height:1.58; max-width:850px; }
    .enterprise-card {
      padding:18px 20px; border:1px solid #1E2A3A; border-radius:18px;
      background:linear-gradient(180deg,rgba(17,26,42,.92),rgba(13,20,32,.96));
      box-shadow:0 16px 42px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.035);
      min-height:120px; margin-bottom:12px;
    }
    .card-title { font-size:.96rem; font-weight:850; color:#E5EEF8; margin-bottom:7px; }
    .card-body { font-size:.88rem; color:#AEBBD0; line-height:1.48; }
    .step {
      display:flex; gap:13px; align-items:flex-start; padding:15px 17px;
      background:linear-gradient(180deg,rgba(17,26,42,.92),rgba(13,20,32,.96));
      border:1px solid #1E2A3A; border-radius:16px; margin-bottom:11px; box-shadow:0 12px 32px rgba(0,0,0,.22);
    }
    .step-num {
      width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,#38BDF8,#A78BFA);
      color:#06101C; display:inline-flex; align-items:center; justify-content:center; font-weight:900; font-size:.82rem; flex:0 0 auto;
    }
    .step-title { color:#F8FAFC; font-weight:850; margin-bottom:3px; }
    .step-copy { color:#AEBBD0; font-size:.88rem; line-height:1.45; }
    .status-pill {
      display:inline-block; padding:5px 10px; border-radius:999px; font-size:.76rem; font-weight:800;
      margin:3px 5px 3px 0; border:1px solid transparent;
    }
    .pill-danger { background:rgba(251,113,133,.11); color:#FDA4AF; border-color:rgba(251,113,133,.28); }
    .pill-warning { background:rgba(251,191,36,.11); color:#FCD34D; border-color:rgba(251,191,36,.28); }
    .pill-info { background:rgba(125,211,252,.10); color:#7DD3FC; border-color:rgba(125,211,252,.25); }
    .pill-success { background:rgba(52,211,153,.10); color:#86EFAC; border-color:rgba(52,211,153,.25); }
    .small-muted { color:#94A3B8; font-size:.82rem; line-height:1.4; }
    .demo-panel {
      background:linear-gradient(180deg,rgba(17,26,42,.95),rgba(13,20,32,.98));
      border:1px solid #1E2A3A; border-radius:20px; padding:21px;
      box-shadow:0 18px 46px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.035); min-height:330px;
    }
    .glass-panel { background:rgba(13,20,32,.76); backdrop-filter:blur(18px); border:1px solid rgba(125,211,252,.18); border-radius:18px; padding:18px; box-shadow:0 18px 45px rgba(0,0,0,.28); }
    .stButton > button {
      border-radius:11px; font-weight:800; background:linear-gradient(135deg,#38BDF8,#7DD3FC) !important;
      color:#06101C !important; border:0 !important; box-shadow:0 10px 24px rgba(56,189,248,.20);
    }
    input, textarea, select {
      background-color:#0D1420 !important; color:#E5EEF8 !important; border:1px solid #243246 !important; border-radius:10px !important;
    }
    /* Streamlit/BaseWeb select widgets: keep the selected value readable after selection. */
    div[data-baseweb="select"] > div {
      background:#0D1420 !important;
      border-color:#243246 !important;
      color:#E5EEF8 !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] [role="combobox"],
    div[data-baseweb="select"] [role="combobox"] *,
    div[data-baseweb="select"] div[aria-selected="true"] {
      color:#F8FAFC !important;
      -webkit-text-fill-color:#F8FAFC !important;
      opacity:1 !important;
    }
    /* Multiselect selected tags/chips must remain visible in dark mode. */
    div[data-baseweb="tag"],
    div[data-baseweb="tag"] span,
    div[data-baseweb="tag"] * {
      background-color:#17324A !important;
      color:#F8FAFC !important;
      -webkit-text-fill-color:#F8FAFC !important;
      opacity:1 !important;
    }
    div[data-baseweb="select"] [data-baseweb="tag"] {
      border:1px solid #38BDF8 !important;
      border-radius:8px !important;
    }
    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] [role="listbox"] {
      background:#0D1420 !important;
      color:#E5EEF8 !important;
    }
    div[data-baseweb="popover"] [role="option"] {
      color:#E5EEF8 !important;
      background:#0D1420 !important;
    }
    div[data-baseweb="popover"] [role="option"]:hover {
      background:#172235 !important;
      color:#FFFFFF !important;
    }
    [data-testid="stTextArea"] textarea { background-color:#0D1420 !important; color:#E5EEF8 !important; border:1px solid #243246 !important; }
    [data-testid="stDataFrame"] { border:1px solid #1E2A3A; border-radius:14px; overflow:hidden; background:#0D1420; }
    div[data-testid="stMetric"] {
      background:linear-gradient(180deg,rgba(17,26,42,.94),rgba(13,20,32,.98));
      border:1px solid #1E2A3A; border-radius:16px; padding:15px 16px; box-shadow:0 14px 34px rgba(0,0,0,.24);
    }
    div[data-testid="stMetricLabel"] { color:#94A3B8 !important; font-size:.78rem !important; font-weight:750; }
    div[data-testid="stMetricValue"] { color:#F8FAFC !important; font-size:1.45rem !important; font-weight:900 !important; }
    .stAlert { border-radius:14px !important; }
    details { background:rgba(13,20,32,.80) !important; border:1px solid #1E2A3A !important; border-radius:14px !important; padding:6px 10px !important; }
    code, pre { background:#050812 !important; color:#E2E8F0 !important; border:1px solid #1E2A3A !important; border-radius:12px !important; }
    hr { border-color:#1E2A3A !important; }
    </style>
    """, unsafe_allow_html=True)
    _ = render_global_copilot()
    return None

def render_global_copilot():
    """Persistent sidebar copilot available from every page.

    It can answer grounded study-operations questions and turn a plain-language
    population request into an editable Cohort Builder draft.
    """
    with st.sidebar:
        try:
            from src.batch_jobs import active_jobs
            jobs = active_jobs()
            if jobs:
                j=jobs[0]
                _ = st.info(f"MedGemma {j.get('status','running').lower()} · {j.get('processed',0)}/{j.get('total',0)} · {j.get('stage','processing')}")
        except Exception:
            pass
        _ = st.markdown("---")
        with st.expander("✨ Ask Clinical Ops", expanded=False):
            _ = st.caption("Ask about study risk, sites, workload, or describe a test cohort to build.")
            q = st.text_area("Ask", key="global_ops_question_v11", height=84, placeholder="e.g. Build a test cohort of adults 55–75 with diabetes, excluding CKD")
            c1, c2 = st.columns(2)
            ask = c1.button("Ask", key="global_ops_ask_v11", use_container_width=True)
            draft = c2.button("Build cohort draft", key="global_ops_draft_v11", use_container_width=True)
            if draft and q.strip():
                from src.copilot import parse_cohort_request
                d = parse_cohort_request(q)
                st.session_state["copilot_cohort_draft_v11"] = d
                _ = st.success("Draft created. Open Cohort Builder to review and apply it.")
                _ = st.page_link("pages/2_Cohort_Builder.py", label="Open Cohort Builder →")
            if ask and q.strip():
                try:
                    from src.trial_ops import ensure_trial, build_grounded_context
                    from src.gemma_ops_client import ollama_health, grounded_ops_answer, deterministic_fallback
                    if ensure_trial():
                        ctx = build_grounded_context(q)
                        if ollama_health():
                            ans = grounded_ops_answer(q, ctx)
                        else:
                            ans = deterministic_fallback(q, ctx)
                        st.session_state["global_ops_answer_v11"] = ans
                    else:
                        st.session_state["global_ops_answer_v11"] = "The trial operations layer has not been built yet. You can still describe a cohort and use Build cohort draft."
                except Exception as e:
                    st.session_state["global_ops_answer_v11"] = f"Could not answer from the current study data: {e}"
            if st.session_state.get("global_ops_answer_v11"):
                _ = st.markdown(st.session_state["global_ops_answer_v11"])
    return None

def hero(title: str, subtitle: str, kicker: str = "Enterprise clinical workflow AI"):
    _ = st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">{kicker}</div>
      <div class="hero-title">{title}</div>
      <div class="hero-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def enterprise_card(title: str, body: str):
    _ = st.markdown(f"""
    <div class="enterprise-card">
      <div class="card-title">{title}</div>
      <div class="card-body">{body}</div>
    </div>
    """, unsafe_allow_html=True)

def workflow_step(number: int, title: str, body: str):
    _ = st.markdown(f"""
    <div class="step">
      <div class="step-num">{number}</div>
      <div><div class="step-title">{title}</div><div class="step-copy">{body}</div></div>
    </div>
    """, unsafe_allow_html=True)

def pill(text: str, tone: str = "info") -> str:
    cls = {"danger":"pill-danger","warning":"pill-warning","success":"pill-success","info":"pill-info"}.get(tone, "pill-info")
    return f'<span class="status-pill {cls}">{text}</span>'

def render_pills(items, tone="info", empty="None detected"):
    if not items:
        _ = st.markdown(f'<span class="small-muted">{empty}</span>', unsafe_allow_html=True)
        return
    _ = st.markdown("".join([pill(str(x), tone) for x in items]), unsafe_allow_html=True)
