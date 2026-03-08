"""Bucketing tab UI — parameter controls, data preview, run trigger, and results display."""

from __future__ import annotations

import streamlit as st

from modules.bucketing import (
    build_bucket_df,
    cluster_auto,
    cluster_fixed,
    compute_confidence,
    embed_items,
    reduce_dimensions,
)
from modules.llm import label_clusters
from ui.shared import (
    render_column_selector,
    render_download_buttons,
    render_file_uploader,
)
from utils.output_builder import build_metadata
from utils.seed import apply_seed, get_seed


def render_bucketing_tab() -> None:
    """Render the complete Keyword Bucketing tab."""

    # -- Header ---------------------------------------------------------------
    st.markdown(
        '<h2 style="font-family: \'IBM Plex Sans\', sans-serif; color: #1A1917; '
        'margin-bottom: 0.25rem;">Keyword Bucketing</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-family: \'IBM Plex Sans\', sans-serif; color: #6B6860; '
        'margin-bottom: 1.5rem;">'
        "Upload a list of items and we'll automatically group them into meaningful themes.</p>",
        unsafe_allow_html=True,
    )

    # -- File upload ----------------------------------------------------------
    df, _warnings = render_file_uploader(tab_key="bucketing")
    if df is None:
        return

    # -- Column selector ------------------------------------------------------
    selected_col = render_column_selector(df, key="bucketing")
    if selected_col is None:
        return

    items: list[str] = df[selected_col].dropna().astype(str).tolist()

    # -- Settings expander ----------------------------------------------------
    with st.expander("⚙️ Settings", expanded=False):
        # Number of groups
        group_mode = st.radio(
            "Number of groups",
            options=["Auto (recommended)", "I'll choose"],
            index=0,
            key="bucketing_group_mode",
            help=(
                "Auto lets the tool find natural groupings in your data. "
                "Choose a number if you know exactly how many groups you want."
            ),
            horizontal=True,
        )

        n_buckets: int | None = None
        if group_mode == "I'll choose":
            n_buckets = st.number_input(
                "How many groups?",
                min_value=2,
                max_value=50,
                value=10,
                step=1,
                key="bucketing_n_buckets",
            )

        # Sensitivity
        sensitivity = st.slider(
            "Grouping sensitivity",
            min_value=1,
            max_value=5,
            value=3,
            key="bucketing_sensitivity",
            help=(
                "Controls how similar items need to be to share a group. "
                "Low = fewer, broader groups. High = more, tighter groups."
            ),
        )
        label_left, label_center, label_right = st.columns(3)
        with label_left:
            st.caption("Broad")
        with label_center:
            st.caption("Balanced")
        with label_right:
            st.markdown(
                '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.8rem; '
                'color: #6B6860; text-align: right; margin-top: -0.5rem;">Precise</p>',
                unsafe_allow_html=True,
            )

        # Label style
        label_style = st.selectbox(
            "Group label style",
            options=["Short", "Descriptive", "Technical"],
            index=1,
            key="bucketing_label_style",
            help=(
                "How group names are written. "
                "Short: 1\u20133 word tags. Descriptive: natural phrases. Technical: precise terms."
            ),
        )

        # Consistent results
        consistent = st.checkbox(
            "Consistent results across runs",
            value=True,
            key="bucketing_consistent",
            help="When on, running the tool twice on the same file gives the same results.",
        )

    # -- Run button -----------------------------------------------------------
    api_key = st.session_state.get("api_key")
    can_run = api_key is not None

    if not can_run:
        st.info("Enter and validate your API key at the top of the page to enable grouping.")

    run_clicked = st.button(
        "Run Grouping",
        disabled=not can_run,
        key="bucketing_run",
        type="primary",
    )

    # -- Execution ------------------------------------------------------------
    if run_clicked and can_run:
        seed = get_seed(consistent)
        apply_seed(seed)

        progress = st.progress(0)
        status = st.empty()

        try:
            # Step 1: Embed
            status.text("Analyzing your items...")
            progress.progress(10)
            embeddings = embed_items(items)

            # Step 2: Reduce dimensions
            status.text("Finding patterns...")
            progress.progress(30)
            reduced = reduce_dimensions(embeddings, seed=seed)

            # Step 3: Cluster
            progress.progress(50)
            if n_buckets is not None:
                labels = cluster_fixed(reduced, n_buckets=n_buckets, seed=seed)
            else:
                labels = cluster_auto(reduced, sensitivity=sensitivity)

            # Step 4: Confidence
            progress.progress(60)
            confidence = compute_confidence(reduced, labels)

            # Step 5: Label clusters via LLM
            status.text("Naming groups...")
            progress.progress(70)

            unique_labels = sorted(set(int(l) for l in labels if l != -1))
            cluster_samples: dict[int, list[str]] = {}
            for cid in unique_labels:
                members = [items[i] for i, l in enumerate(labels) if l == cid]
                cluster_samples[cid] = members[:10]

            cluster_names = label_clusters(api_key, cluster_samples, label_style)

            # Step 6: Build DataFrame
            status.text("Done!")
            progress.progress(100)

            result_df = build_bucket_df(items, labels, confidence, cluster_names)

            # Store results
            params = {
                "n_buckets": n_buckets or "Auto",
                "sensitivity": sensitivity,
                "label_style": label_style,
                "consistent_results": consistent,
            }
            metadata = build_metadata("bucketing", params, len(result_df))
            st.session_state["bucketing_results"] = result_df
            st.session_state["bucketing_metadata"] = metadata

            n_groups = len(unique_labels)
            noise_count = int((labels == -1).sum())
            msg = f"Found {n_groups} group{'s' if n_groups != 1 else ''} across {len(items):,} items."
            if noise_count > 0:
                msg += f" {noise_count:,} item{'s' if noise_count != 1 else ''} didn't fit a group."
            st.success(msg)

        except RuntimeError as exc:
            progress.empty()
            status.empty()
            st.error(str(exc))
            return
        except Exception as exc:
            progress.empty()
            status.empty()
            st.error(
                f"Something went wrong while grouping your items. Please try again. ({exc})"
            )
            return

    # -- Results display ------------------------------------------------------
    result_df = st.session_state.get("bucketing_results")
    metadata = st.session_state.get("bucketing_metadata")

    if result_df is None or metadata is None:
        return

    st.divider()

    n_groups = result_df["bucket_id"].nunique()
    if -1 in result_df["bucket_id"].values:
        n_groups -= 1
    st.markdown(
        f'<p style="font-family: \'IBM Plex Sans\', sans-serif; color: #1A1917; '
        f'font-size: 1.1rem; font-weight: 600;">'
        f"Found {n_groups} group{'s' if n_groups != 1 else ''} "
        f"across {len(result_df):,} items</p>",
        unsafe_allow_html=True,
    )

    # Results table
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    # Bar chart — item count per group
    chart_data = (
        result_df[result_df["bucket_id"] != -1]
        .groupby("bucket_label", sort=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .set_index("bucket_label")
    )
    if not chart_data.empty:
        st.markdown(
            '<p style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 0.85rem; '
            'color: #6B6860; letter-spacing: 0.05em; text-transform: uppercase; '
            'margin-top: 1rem; margin-bottom: 0.25rem;">Items per group</p>',
            unsafe_allow_html=True,
        )
        st.bar_chart(chart_data)

    # Downloads
    render_download_buttons(result_df, metadata, filename_base="keyword_groups")
