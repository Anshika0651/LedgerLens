import streamlit as st


def setup():
    st.set_page_config(page_title="LedgerLens", page_icon="L", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
    :root { --paper:#f7f2e5; --ink:#1a1b18; --muted:#77766f; --line:#e8e3d8; --lime:#a3e873; --deep:#141512; --pink:#f2c6df; --yellow:#f3de78; --olive:#bbc47a; --blue:#b9c9ea; }
    .stApp { background:var(--paper); color:var(--ink); }
    section.main > div.block-container { max-width:1480px; padding-top:1.5rem; padding-bottom:3rem; }
    [data-testid="stSidebar"] { background:var(--deep); border-right:0; }
    [data-testid="stSidebar"] * { color:#f7f4eb; }
    [data-testid="stSidebar"] [data-testid="stExpander"] { border-color:#33342f; }
    [data-testid="stSidebar"] hr { border-color:#383a33; }
    [data-testid="stSidebar"] [role="radiogroup"] label { border-radius:10px; padding:.42rem .6rem; }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background:#2a2d26; }
    h1,h2,h3 { color:var(--ink)!important; letter-spacing:-.035em; }
    h1 { font-size:2rem!important; font-weight:650!important; }
    h2 { font-size:1.36rem!important; }
    .ll-kicker { color:#77766f; text-transform:uppercase; letter-spacing:.13em; font-size:.68rem; font-weight:700; margin:.45rem 0; }
    .ll-subtle { color:var(--muted); font-size:.88rem; }
    .ll-metric { min-height:116px; padding:18px 20px; background:#fffefa; border:1px solid var(--line); border-radius:18px; box-shadow:0 2px 8px #25231808; }
    .ll-metric-green { background:var(--lime); border-color:#a0dc70; }
    .ll-metric-pink { background:var(--pink); border-color:#e7b8d2; }
    .ll-metric-yellow { background:var(--yellow); border-color:#e7d36e; }
    .ll-metric-blue { background:var(--blue); border-color:#aabbdc; }
    .ll-metric-label { color:#5f6259; font-size:.78rem; font-weight:650; }
    .ll-metric-value { color:var(--ink); font-size:1.8rem; font-weight:650; line-height:1.4; }
    .ll-metric-note { color:#5f6259; font-size:.75rem; }
    .ll-welcome-step { min-height:122px; background:#fffefa; border:1px solid var(--line); border-radius:18px; padding:18px 20px; box-shadow:0 2px 8px #25231808; }
    .ll-welcome-step-green { background:var(--lime); border-color:#a0dc70; }
    .ll-welcome-step-pink { background:var(--pink); border-color:#e7b8d2; }
    .ll-welcome-step-yellow { background:var(--yellow); border-color:#e7d36e; }
    .ll-welcome-step span { display:block; color:#425438; font:600 .75rem 'IBM Plex Mono',monospace; margin-bottom:10px; }
    .ll-welcome-step b { font-size:1rem; }
    .ll-welcome-step p { color:#555850; font-size:.85rem; margin:.45rem 0 0; }
    .ll-status-good,.ll-status-warn,.ll-status-bad,.ll-status-neutral { display:inline-block; padding:4px 9px; border-radius:999px; font-size:.75rem; font-weight:650; }
    .ll-status-good { color:#1d5225; background:#c7ed9e; }
    .ll-status-warn { color:#695318; background:#f4e39a; }
    .ll-status-bad { color:#7c3439; background:#f1cada; }
    .ll-status-neutral { color:#4c5149; background:#e8e7dd; }
    .stButton>button { border-radius:999px; min-height:2.45rem; }
    .stButton>button[kind="primary"] { color:#173113; background:#9be267; border-color:#9be267; font-weight:700; }
    .stButton>button[kind="primary"]:hover { color:#10270d; background:#8ed653; border-color:#8ed653; }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
    [data-testid="stFileUploader"] section { background:#fffefa; border:1px dashed #c8c6b9; border-radius:16px; }
    [data-testid="stExpander"] { background:#fffefa; border:1px solid var(--line); border-radius:14px; }
    [data-testid="stStatusWidget"] { border-radius:14px; }
    .stAlert { border-radius:12px; }
    @media (max-width:800px) { .ll-metric { min-height:96px; padding:14px; } .ll-metric-value { font-size:1.5rem; } }
    </style>
    """, unsafe_allow_html=True)
