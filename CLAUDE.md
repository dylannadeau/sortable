# CLAUDE.md — Keyword Categorization Tool

This file defines the design principles, architecture, and coding standards for this project.
Claude Code should read and follow this file on every session.

---

## Project Overview

A local Streamlit application with two modules:
1. **Keyword Bucketing** — clusters a list of items into thematic groups
2. **Entity Standardization** — normalizes variations of the same entity to a canonical name

Target users are non-technical internal users running the app locally on their own devices.
The app is driven by the Claude API (Anthropic). Each user supplies their own API key per session.

---

## Design Principles

### Aesthetic Direction: Refined Utilitarian
This app is a professional internal tool — it should feel like precision software, not a consumer app.
Think: editorial clarity, generous whitespace, confident typography, understated color.

**Typography**
- Use `IBM Plex Sans` for body/UI text (via Google Fonts import in any custom CSS)
- Use `IBM Plex Mono` for data previews, column selectors, and output tables
- Avoid Inter, Roboto, Arial, or any system font fallback as the primary face

**Color Palette (CSS variables to define early and reuse)**
- `--bg`: #F7F6F2 (warm off-white — not pure white)
- `--surface`: #FFFFFF
- `--border`: #E2E0D8
- `--text-primary`: #1A1917
- `--text-secondary`: #6B6860
- `--accent`: #2D5BE3 (electric blue — used sparingly: CTAs, active states, links)
- `--accent-light`: #EEF2FD
- `--success`: #1A7F5A
- `--warning`: #C47B1E
- `--error`: #C0392B

**Spacing & Layout**
- Generous internal padding on cards and panels
- Clear visual hierarchy: section headers are small-caps, slightly tracked, muted color
- Dividers over nested containers where possible
- Tables use alternating row shading with monospace font

**Interactions & States**
- Validation states must be visually unambiguous: green checkmark, red inline error, amber warning
- Loading states must show a spinner with a short, human-readable status message
- Disabled states must be clearly visually distinct (not just grayed text)

**Tone of Copy**
- All UI labels, tooltips, and helper text should be written in plain English
- No technical jargon (no mention of K-Means, HDBSCAN, cosine similarity, embeddings, etc.)
- Tooltips use the `ℹ️` icon and explain the *effect* of a parameter, not its mechanism
- Error messages should say what went wrong AND what the user should do

---

## Architecture

```
/
├── CLAUDE.md               ← This file
├── app.py                  ← Main Streamlit entry point (tab router only)
├── requirements.txt
├── README.md
├── .env.example            ← Template for optional local env (no secrets committed)
├── modules/
│   ├── __init__.py
│   ├── bucketing.py        ← Keyword bucketing logic
│   ├── standardization.py  ← Entity standardization logic
│   └── llm.py              ← All Claude API calls (centralized)
├── ui/
│   ├── __init__.py
│   ├── shared.py           ← Shared UI components (API key input, file uploader, etc.)
│   ├── tab_bucketing.py    ← Bucketing tab UI
│   └── tab_standardization.py ← Standardization tab UI
└── utils/
    ├── __init__.py
    ├── file_parser.py      ← CSV / Excel / text ingestion + validation
    ├── output_builder.py   ← Standardized output formatting + Excel/CSV export
    └── seed.py             ← Reproducibility seed management
```

---

## Module Responsibilities

### `app.py`
- Page config (title, icon, layout)
- Google Fonts import via `st.markdown`
- Global CSS injection
- API key state management
- Tab rendering (calls ui/tab_*.py)
- Nothing else — keep it thin

### `modules/llm.py`
- Single source of truth for all Claude API calls
- Accepts an `api_key` parameter — never reads from environment in production flow
- Functions: `label_clusters()`, `resolve_ambiguous_entities()`, `validate_api_key()`
- Handles rate limiting, retries (max 3), and error normalization
- Returns structured dicts, never raw API responses

### `modules/bucketing.py`
- `embed_items(items)` → numpy array
- `cluster_auto(embeddings, sensitivity)` → cluster labels (HDBSCAN)
- `cluster_fixed(embeddings, n_buckets, seed)` → cluster labels (K-Means)
- `build_bucket_df(items, labels)` → DataFrame with original_item, bucket_id, bucket_label, confidence_score

### `modules/standardization.py`
- `preprocess_names(names)` → cleaned list (lowercase, strip suffixes, normalize punctuation)
- `find_canonical(names, canonical_list=None, strictness=3, seed=None)` → mapping DataFrame
- Output columns: original_name, canonical_name, match_score, method

### `utils/file_parser.py`
- `parse_upload(file)` → returns `(df, warnings)` tuple
- Supports: .csv, .xlsx, .xls, plain text (one item per line)
- Validates: not empty, not >50K rows, detects encoding issues, checks for usable columns
- Returns structured warnings (not exceptions) so UI can display them gracefully

### `utils/output_builder.py`
- `to_csv(df)` → bytes
- `to_excel(df, metadata: dict)` → bytes with formatted headers + metadata sheet
- Excel output: bold headers, auto-width columns, alternating row fill, metadata tab

---

## Coding Standards

- Python 3.10+
- All functions have type hints and a one-line docstring
- No hardcoded strings in logic files — UI copy lives in ui/ files only
- No `st.*` calls outside of `ui/` and `app.py`
- Use `st.session_state` for: api_key, uploaded data, last run results
- Never write API keys or user data to disk
- All errors caught and surfaced via `st.error()` with user-friendly messages
- Use `@st.cache_resource` for model loading (sentence-transformers), `@st.cache_data` for embeddings

---

## Parameter Definitions (for UI implementation)

### Bucketing Tab

| Internal Name | UI Label | Type | Default | Range/Options |
|---|---|---|---|---|
| `n_buckets` | "Number of groups" | int or "Auto" | "Auto" | Auto, 2–50 |
| `sensitivity` | "Grouping sensitivity" | slider | 3 | 1–5 |
| `label_style` | "Group label style" | select | "Descriptive" | Short / Descriptive / Technical |
| `consistent_results` | "Consistent results across runs" | checkbox | True | — |

Sensitivity mapping (internal): 1=very broad, 5=very granular (maps to HDBSCAN min_cluster_size or K-Means distance threshold)

### Standardization Tab

| Internal Name | UI Label | Type | Default | Range/Options |
|---|---|---|---|---|
| `canonical_upload` | "Master list (optional)" | file upload | None | CSV/Excel/text |
| `strictness` | "Match strictness" | slider | 3 | 1–5 |
| `strip_suffixes` | "Ignore legal suffixes (LLC, Inc, etc.)" | checkbox | True | — |
| `consistent_results` | "Consistent results across runs" | checkbox | True | — |

---

## File Validation Rules

Applied in `utils/file_parser.py` and surfaced in UI before Run is enabled:

- ✅ File must be .csv, .xlsx, .xls, or .txt
- ✅ Must contain at least 2 rows of data
- ✅ Must not exceed 50,000 rows
- ✅ If CSV/Excel: must have at least one column with >50% non-null string values
- ⚠️ Warn (don't block) if: duplicate items detected, very short items (<2 chars), mixed languages detected
- ❌ Block if: file is empty, file is corrupted/unreadable, all columns are numeric

---

## Output Spec

### Bucketing Output

| Column | Description |
|---|---|
| `original_item` | Exactly as uploaded |
| `bucket_id` | Integer, 0-indexed |
| `bucket_label` | Human-readable name generated by Claude |
| `confidence_score` | Float 0–1, how strongly item belongs to bucket |

### Standardization Output

| Column | Description |
|---|---|
| `original_name` | Exactly as uploaded |
| `canonical_name` | Normalized/resolved name |
| `match_score` | Float 0–1 |
| `method` | One of: `exact`, `fuzzy`, `semantic`, `ai-resolved` |

### Excel Export (both modules)
- Sheet 1: Results (formatted)
- Sheet 2: `run_metadata` — timestamp, module used, parameters, row count, model used

---

## README Instructions (for non-technical users)

The README should include:
1. One-paragraph plain English description of what the tool does
2. Prerequisites: Python 3.10+, how to get an Anthropic API key (link to console.anthropic.com)
3. Setup: exactly two commands (`pip install -r requirements.txt` and `streamlit run app.py`)
4. A note that the API key is never saved
5. Brief description of each tab
6. Troubleshooting: common errors in plain English
