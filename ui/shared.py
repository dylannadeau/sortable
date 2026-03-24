"""Shared UI components — provider selector, file uploader, validation display."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from modules.llm import (
    LLMConfig,
    _CLAUDE_MODEL,
    list_ollama_models,
    validate_api_key,
    validate_ollama,
)
from utils.file_parser import parse_upload
from utils.output_builder import to_csv, to_excel


# ---------------------------------------------------------------------------
# Provider selector (Ollama default, Claude alternative)
# ---------------------------------------------------------------------------


def render_provider_selector() -> None:
    """Render provider toggle and the appropriate config panel."""
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
        'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
        'margin-bottom: 0.25rem;">AI Provider</p>',
        unsafe_allow_html=True,
    )

    provider = st.radio(
        "AI Provider",
        options=["Local (Ollama)", "Claude API"],
        index=0 if st.session_state.get("llm_provider", "ollama") == "ollama" else 1,
        key="provider_radio",
        label_visibility="collapsed",
        horizontal=True,
    )

    # Map radio label to internal key
    chosen = "ollama" if provider == "Local (Ollama)" else "claude"

    # Clear other provider's validation when switching
    prev = st.session_state.get("llm_provider")
    if prev != chosen:
        if chosen == "claude":
            st.session_state.pop("ollama_validated", None)
        else:
            st.session_state.pop("api_key", None)
            st.session_state.pop("_api_key_raw", None)
            st.session_state.pop("_api_key_error", None)
    st.session_state["llm_provider"] = chosen

    if chosen == "ollama":
        _render_ollama_config()
    else:
        _render_api_key_input()


def _render_ollama_config() -> None:
    """Render Ollama model selector and connection verifier."""
    models, error = list_ollama_models()

    if error:
        st.error(error)
        return

    if not models:
        st.warning(
            "Ollama is running but has no models installed. "
            "Open your terminal and run `ollama pull llama3` to get started."
        )
        return

    # Already validated and model unchanged
    prev_model = st.session_state.get("ollama_model")
    if st.session_state.get("ollama_validated") and prev_model in models:
        default_idx = models.index(prev_model)
    else:
        default_idx = 0

    selected = st.selectbox(
        "Model",
        options=models,
        index=default_idx,
        key="ollama_model_select",
        help="Pick a locally installed model. We recommend llama3 for a good balance of speed and quality.",
    )

    # Model changed — clear validation
    if selected != st.session_state.get("ollama_model"):
        st.session_state.pop("ollama_validated", None)
        st.session_state["ollama_model"] = selected

    if st.session_state.get("ollama_validated"):
        st.markdown(
            f'<p style="color: #1A7F5A; font-family: \'IBM Plex Sans\', sans-serif;">'
            f"&#10003; Connected to Ollama &mdash; using {selected}</p>",
            unsafe_allow_html=True,
        )
        return

    if st.button("Verify connection", key="validate_ollama_btn"):
        with st.spinner("Checking Ollama connection..."):
            valid, err_msg = validate_ollama(selected)
        if valid:
            st.session_state["ollama_validated"] = True
            st.session_state["ollama_model"] = selected
            st.rerun()
        else:
            st.error(err_msg)


def _render_api_key_input() -> None:
    """Render the API key input field with validation feedback."""
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
        'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
        'margin-bottom: 0.25rem;">API Key</p>',
        unsafe_allow_html=True,
    )

    raw_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-ant-...",
        key="api_key_input",
        label_visibility="collapsed",
    )

    # Already validated and key unchanged
    if (
        st.session_state.get("api_key")
        and st.session_state.get("_api_key_raw") == raw_key
    ):
        st.markdown(
            '<p style="color: #1A7F5A; font-family: \'IBM Plex Sans\', sans-serif;">'
            "&#10003; API key verified</p>",
            unsafe_allow_html=True,
        )
        return

    # Key changed — clear old validation
    if st.session_state.get("_api_key_raw") != raw_key:
        st.session_state.pop("api_key", None)
        st.session_state.pop("_api_key_validated", None)
        st.session_state["_api_key_raw"] = raw_key

    if not raw_key:
        st.markdown(
            '<p style="color: #6B6860; font-family: \'IBM Plex Sans\', sans-serif; '
            'font-size: 0.85rem;">'
            "Your key is used only this session and never saved.</p>",
            unsafe_allow_html=True,
        )
        return

    # Show validation error from previous attempt
    prev_error = st.session_state.get("_api_key_error")
    if prev_error:
        st.markdown(
            f'<p style="color: #C0392B; font-family: \'IBM Plex Sans\', sans-serif;">'
            f"{prev_error}</p>",
            unsafe_allow_html=True,
        )

    if st.button("Validate key", key="validate_api_key_btn"):
        with st.spinner("Checking your API key..."):
            valid, error_msg = validate_api_key(raw_key)

        if valid:
            st.session_state["api_key"] = raw_key
            st.session_state["_api_key_raw"] = raw_key
            st.session_state["_api_key_error"] = None
            st.rerun()
        else:
            st.session_state["_api_key_error"] = error_msg
            st.session_state.pop("api_key", None)
            st.rerun()


# ---------------------------------------------------------------------------
# Config reader (called by tab modules)
# ---------------------------------------------------------------------------


def get_llm_config() -> LLMConfig | None:
    """Build an LLMConfig from current session state, or None if not ready."""
    provider = st.session_state.get("llm_provider", "ollama")

    if provider == "claude":
        api_key = st.session_state.get("api_key")
        if not api_key:
            return None
        return LLMConfig(provider="claude", model=_CLAUDE_MODEL, api_key=api_key)

    # Ollama
    if st.session_state.get("ollama_validated"):
        model = st.session_state.get("ollama_model", "")
        if model:
            return LLMConfig(provider="ollama", model=model)
    return None


# ---------------------------------------------------------------------------
# File upload & column selection
# ---------------------------------------------------------------------------


def render_file_uploader(tab_key: str) -> tuple[Optional[pd.DataFrame], list[str]]:
    """Render a file upload widget with validation and preview."""
    upload_key = f"file_upload_{tab_key}"
    data_key = f"parsed_df_{tab_key}"
    warnings_key = f"parsed_warnings_{tab_key}"

    uploaded = st.file_uploader(
        "Upload your data file",
        type=["csv", "xlsx", "xls", "txt"],
        key=upload_key,
        help="Accepted formats: CSV, Excel (.xlsx / .xls), or plain text (one item per line).",
    )

    if uploaded is None:
        st.session_state.pop(data_key, None)
        st.session_state.pop(warnings_key, None)
        return None, []

    # Only re-parse if file changed
    prev_name = st.session_state.get(f"_upload_name_{tab_key}")
    if prev_name == uploaded.name and data_key in st.session_state:
        df = st.session_state[data_key]
        warnings = st.session_state.get(warnings_key, [])
    else:
        df, warnings = parse_upload(uploaded)
        st.session_state[data_key] = df
        st.session_state[warnings_key] = warnings
        st.session_state[f"_upload_name_{tab_key}"] = uploaded.name

    # Hard errors — df is None
    if df is None:
        for msg in warnings:
            st.error(msg)
        return None, warnings

    # Soft warnings
    for msg in warnings:
        st.warning(msg)

    # Preview
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
        'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
        'margin-top: 1rem; margin-bottom: 0.25rem;">Preview</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(df.head(5), use_container_width=True)

    st.markdown(
        f'<p style="color: #1A7F5A; font-family: \'IBM Plex Sans\', sans-serif;">'
        f"&#10003; File looks good &mdash; {len(df):,} items ready</p>",
        unsafe_allow_html=True,
    )

    return df, warnings


def render_column_selector(df: pd.DataFrame, key: str) -> Optional[str]:
    """Render a column selector, showing only columns with >50% string values."""
    valid_cols: list[str] = []
    for col in df.columns:
        str_count = df[col].apply(lambda v: isinstance(v, str) and len(v.strip()) > 0).sum()
        if str_count / len(df) > 0.5:
            valid_cols.append(col)

    if not valid_cols:
        st.error(
            "No usable text column found in this file. "
            "Please upload a file with at least one column of text data."
        )
        return None

    if len(valid_cols) == 1:
        return valid_cols[0]

    selected = st.selectbox(
        "Which column contains the items to process?",
        options=valid_cols,
        key=f"col_select_{key}",
        help="Pick the column that holds the text items you want to group or standardize.",
    )
    return selected


def render_download_buttons(
    df: pd.DataFrame, metadata: dict, filename_base: str
) -> None:
    """Render side-by-side CSV and Excel download buttons."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    col_csv, col_xlsx = st.columns(2)

    with col_csv:
        st.download_button(
            label="Download CSV",
            data=to_csv(df),
            file_name=f"{filename_base}_{timestamp}.csv",
            mime="text/csv",
            key=f"dl_csv_{filename_base}",
        )

    with col_xlsx:
        st.download_button(
            label="Download Excel",
            data=to_excel(df, metadata),
            file_name=f"{filename_base}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_xlsx_{filename_base}",
        )
