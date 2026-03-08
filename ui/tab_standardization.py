"""Standardization tab UI — parameter controls, data preview, run trigger, and results display."""

from __future__ import annotations

import streamlit as st

from modules.standardization import find_canonical
from ui.shared import (
    render_column_selector,
    render_download_buttons,
    render_file_uploader,
)
from utils.file_parser import parse_upload
from utils.output_builder import build_metadata
from utils.seed import get_seed


def render_standardization_tab() -> None:
    """Render the complete Entity Standardization tab."""

    # -- Header ---------------------------------------------------------------
    st.markdown(
        '<h2 style="font-family: \'IBM Plex Sans\', sans-serif; color: #1A1917; '
        'margin-bottom: 0.25rem;">Entity Standardization</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; color: #6B6860; '
        'margin-bottom: 1.5rem;">'
        "Upload a list of names that may be spelled differently or formatted "
        "inconsistently, and we'll normalize them to a single standard form.</p>",
        unsafe_allow_html=True,
    )

    # -- Two-column file uploaders --------------------------------------------
    col_input, col_master = st.columns(2)

    with col_input:
        st.markdown(
            '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
            'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
            'margin-bottom: 0.25rem;">Your list to standardize</p>',
            unsafe_allow_html=True,
        )
        df_input, _input_warnings = render_file_uploader(tab_key="std_input")

    with col_master:
        st.markdown(
            '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
            'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
            'margin-bottom: 0.25rem;">Master list (optional)</p>',
            unsafe_allow_html=True,
        )
        master_uploaded = st.file_uploader(
            "Upload master list",
            type=["csv", "xlsx", "xls", "txt"],
            key="file_upload_std_master",
            label_visibility="collapsed",
            help=(
                "Have a list of correct, canonical names? Upload it here and "
                "we'll match your list to it. Leave empty to let the tool find "
                "the most common form automatically."
            ),
        )

        df_master = None
        if master_uploaded is not None:
            prev_name = st.session_state.get("_upload_name_std_master")
            if prev_name == master_uploaded.name and "parsed_df_std_master" in st.session_state:
                df_master = st.session_state["parsed_df_std_master"]
                master_warnings = st.session_state.get("parsed_warnings_std_master", [])
            else:
                df_master, master_warnings = parse_upload(master_uploaded)
                st.session_state["parsed_df_std_master"] = df_master
                st.session_state["parsed_warnings_std_master"] = master_warnings
                st.session_state["_upload_name_std_master"] = master_uploaded.name

            if df_master is None:
                for msg in master_warnings:
                    st.error(msg)
            else:
                for msg in master_warnings:
                    st.warning(msg)
                st.dataframe(df_master.head(5), use_container_width=True)
                st.markdown(
                    f'<p style="color: #1A7F5A; font-family: \'IBM Plex Sans\', sans-serif;">'
                    f"&#10003; Master list &mdash; {len(df_master):,} entries</p>",
                    unsafe_allow_html=True,
                )

    if df_input is None:
        return

    # -- Column selectors -----------------------------------------------------
    input_col = render_column_selector(df_input, key="std_input")
    if input_col is None:
        return

    master_col = None
    canonical_list = None
    if df_master is not None:
        master_col = render_column_selector(df_master, key="std_master")
        if master_col is not None:
            canonical_list = df_master[master_col].dropna().astype(str).tolist()

    names: list[str] = df_input[input_col].dropna().astype(str).tolist()

    # -- Settings expander ----------------------------------------------------
    with st.expander("⚙️ Settings", expanded=False):
        # Match strictness
        strictness = st.slider(
            "Match strictness",
            min_value=1,
            max_value=5,
            value=3,
            key="std_strictness",
            help=(
                "How closely two names must match to be considered the same. "
                "Low = more lenient matching. High = requires very close similarity."
            ),
        )
        label_left, label_center, label_right = st.columns(3)
        with label_left:
            st.caption("Lenient")
        with label_center:
            st.caption("Balanced")
        with label_right:
            st.markdown(
                '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.8rem; '
                'color: #6B6860; text-align: right; margin-top: -0.5rem;">Strict</p>',
                unsafe_allow_html=True,
            )

        # Strip suffixes
        strip_suffixes = st.checkbox(
            "Ignore business type labels",
            value=True,
            key="std_strip_suffixes",
            help=(
                "When on, words like LLC, Inc, Corp, and Ltd are ignored when "
                "comparing names. Useful for company lists where these vary."
            ),
        )

        # Consistent results
        consistent = st.checkbox(
            "Consistent results across runs",
            value=True,
            key="std_consistent",
            help="When on, running the tool twice on the same file gives the same results.",
        )

    # -- Run button -----------------------------------------------------------
    api_key = st.session_state.get("api_key")
    can_run = api_key is not None

    if not can_run:
        st.info("Enter and validate your API key at the top of the page to enable standardization.")

    run_clicked = st.button(
        "Run Standardization",
        disabled=not can_run,
        key="std_run",
        type="primary",
    )

    # -- Execution ------------------------------------------------------------
    if run_clicked and can_run:
        seed = get_seed(consistent)

        progress = st.progress(0)
        status = st.empty()

        try:
            status.text("Cleaning names...")
            progress.progress(10)

            status.text("Finding matches...")
            progress.progress(30)

            status.text("Resolving close calls...")
            progress.progress(50)

            result_df = find_canonical(
                names=names,
                canonical_list=canonical_list,
                strictness=strictness,
                seed=seed,
                api_key=api_key,
                strip_suffixes=strip_suffixes,
            )

            status.text("Done!")
            progress.progress(100)

            # Build metadata
            params = {
                "strictness": strictness,
                "strip_suffixes": strip_suffixes,
                "consistent_results": consistent,
                "master_list": "provided" if canonical_list else "auto-detect",
            }
            metadata = build_metadata("standardization", params, len(result_df))

            st.session_state["std_results"] = result_df
            st.session_state["std_metadata"] = metadata

            # Success summary
            method_counts = result_df["method"].value_counts()
            matched = int((result_df["method"] != "none").sum())
            unmatched = int((result_df["method"] == "none").sum())
            st.success(
                f"Standardization complete: {matched:,} matched, "
                f"{unmatched:,} unmatched out of {len(result_df):,} total."
            )

        except RuntimeError as exc:
            progress.empty()
            status.empty()
            st.error(str(exc))
            return
        except Exception as exc:
            progress.empty()
            status.empty()
            st.error(
                f"Something went wrong during standardization. Please try again. ({exc})"
            )
            return

    # -- Results display ------------------------------------------------------
    result_df = st.session_state.get("std_results")
    metadata = st.session_state.get("std_metadata")

    if result_df is None or metadata is None:
        return

    st.divider()

    # Summary stats
    matched = int((result_df["method"] != "none").sum())
    unmatched = int((result_df["method"] == "none").sum())

    col_matched, col_unmatched = st.columns(2)
    with col_matched:
        st.metric(label="Matched", value=f"{matched:,}")
    with col_unmatched:
        st.metric(label="Unmatched", value=f"{unmatched:,}")

    # Method breakdown
    method_counts = result_df["method"].value_counts()
    method_labels = {
        "exact": "Exact match",
        "fuzzy": "Close spelling",
        "semantic": "Similar meaning",
        "ai-resolved": "AI-resolved",
        "none": "No match found",
    }
    breakdown = (
        method_counts
        .rename(index=method_labels)
        .reset_index()
    )
    breakdown.columns = ["Method", "Count"]

    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
        'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
        'margin-top: 1rem; margin-bottom: 0.25rem;">Match breakdown</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(breakdown, use_container_width=True, hide_index=True)

    # Full results table
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
        'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
        'margin-top: 1rem; margin-bottom: 0.25rem;">Results</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    # Downloads
    render_download_buttons(result_df, metadata, filename_base="standardized_entities")
