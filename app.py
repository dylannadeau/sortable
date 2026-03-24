"""Main Streamlit entry point — page config, global CSS, API key state, and tab routing."""

import streamlit as st

from ui.shared import render_provider_selector
from ui.tab_bucketing import render_bucketing_tab
from ui.tab_standardization import render_standardization_tab

# -- Page config --------------------------------------------------------------

st.set_page_config(
    page_title="Categorization Tool",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -- Global CSS ---------------------------------------------------------------

st.markdown(
    """
    <style>
    /* ── Google Fonts ──────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    /* ── CSS Variables ─────────────────────────────────────────────── */
    :root {
        --bg: #F7F6F2;
        --surface: #FFFFFF;
        --border: #E2E0D8;
        --text-primary: #1A1917;
        --text-secondary: #6B6860;
        --accent: #2D5BE3;
        --accent-light: #EEF2FD;
        --success: #1A7F5A;
        --warning: #C47B1E;
        --error: #C0392B;
    }

    /* ── Global typography ─────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
        color: var(--text-primary);
    }

    /* ── Warm background ───────────────────────────────────────────── */
    .stApp, .main .block-container {
        background-color: var(--bg);
    }

    /* ── Remove default top padding ────────────────────────────────── */
    .block-container {
        padding-top: 2rem !important;
    }

    /* ── Dataframe / table styling ─────────────────────────────────── */
    .stDataFrame, .stDataFrame table,
    [data-testid="stDataFrame"] * {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* ── Tab bar styling ───────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 500;
        color: var(--text-secondary);
        border-bottom: 2px solid transparent;
        background-color: transparent;
        padding: 0.75rem 1.5rem;
    }

    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
        background-color: transparent !important;
    }

    /* ── Buttons ────────────────────────────────────────────────────── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: var(--accent);
        color: #FFFFFF;
        border: none;
        border-radius: 0;
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 600;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #2349B8;
        color: #FFFFFF;
    }

    .stDownloadButton > button {
        background-color: var(--surface);
        color: var(--text-primary);
        border: 1px solid var(--border);
        border-radius: 0;
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 500;
    }

    .stDownloadButton > button:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    /* ── Expanders ──────────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 600;
        color: var(--text-primary);
    }

    details[data-testid="stExpander"] {
        border: none !important;
        border-left: 3px solid var(--accent) !important;
        border-radius: 0 !important;
        background-color: var(--surface);
        padding-left: 0.5rem;
    }

    /* ── Inputs ─────────────────────────────────────────────────────── */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        font-family: 'IBM Plex Sans', sans-serif;
        border-color: var(--border);
        border-radius: 0;
    }

    .stTextInput input:focus, .stSelectbox select:focus, .stNumberInput input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 1px var(--accent);
    }

    /* ── Slider accent ─────────────────────────────────────────────── */
    .stSlider [data-baseweb="slider"] [role="slider"] {
        background-color: var(--accent);
    }

    /* ── Metrics ────────────────────────────────────────────────────── */
    [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace;
        color: var(--text-primary);
    }

    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Sans', sans-serif;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.8rem;
    }

    /* ── Dividers ───────────────────────────────────────────────────── */
    hr {
        border-color: var(--border);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -- App header ---------------------------------------------------------------

st.markdown(
    '<h1 style="font-family: \'IBM Plex Sans\', sans-serif; color: #1A1917; '
    'font-weight: 700; margin-bottom: 0;">Categorization Tool</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="font-family: \'IBM Plex Sans\', sans-serif; color: #6B6860; '
    'font-size: 1.1rem; margin-top: 0.25rem;">Group and normalize lists of any kind</p>',
    unsafe_allow_html=True,
)
st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1.5rem;'>", unsafe_allow_html=True)

# -- AI provider --------------------------------------------------------------

render_provider_selector()
st.divider()

# -- Tabs ---------------------------------------------------------------------

tab_bucketing, tab_standardization = st.tabs(
    ["🗂️ Keyword Bucketing", "🔗 Entity Standardization"]
)

with tab_bucketing:
    render_bucketing_tab()

with tab_standardization:
    render_standardization_tab()

# -- Footer -------------------------------------------------------------------

_provider = st.session_state.get("llm_provider", "ollama")
_footer = "Powered by Ollama (local)" if _provider == "ollama" else "Powered by Claude · Keys are session-only and never stored"
st.markdown(
    f'<p style="font-family: \'IBM Plex Sans\', sans-serif; color: #6B6860; '
    f'font-size: 0.75rem; text-align: center; margin-top: 3rem; padding-bottom: 1rem;">'
    f"{_footer}</p>",
    unsafe_allow_html=True,
)
