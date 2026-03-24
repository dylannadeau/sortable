"""Entity standardization logic — name preprocessing and canonical resolution."""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.metrics.pairwise import cosine_similarity

from modules.bucketing import embed_items
from modules.llm import LLMConfig, resolve_ambiguous_entities

_LEGAL_SUFFIXES: list[str] = [
    "LLC", "Inc", "Corp", "Corporation", "Ltd", "Limited", "Co", "Company",
    "LP", "LLP", "PLLC", "PC", "PA", "Group", "Holdings", "Enterprises",
    "International", "Solutions", "Services", "Technologies", "Tech",
]

# Build a regex that strips any of these suffixes (with optional trailing period)
# at the end of a string, preceded by optional comma/space.
_SUFFIX_PATTERN: re.Pattern = re.compile(
    r"[,\s]+(?:" + "|".join(re.escape(s) for s in _LEGAL_SUFFIXES) + r")\.?\s*$",
    re.IGNORECASE,
)

_STRICTNESS_TO_THRESHOLD: dict[int, float] = {
    1: 0.60,
    2: 0.70,
    3: 0.80,
    4: 0.88,
    5: 0.95,
}


def preprocess_names(names: list[str], strip_suffixes: bool = True) -> list[str]:
    """Lowercase, strip punctuation, remove legal suffixes, and collapse whitespace."""
    result: list[str] = []
    for name in names:
        cleaned = name.lower().strip()
        if strip_suffixes:
            cleaned = _SUFFIX_PATTERN.sub("", cleaned)
        # Remove remaining punctuation except alphanumerics, spaces, hyphens, ampersands
        cleaned = re.sub(r"[^\w\s\-&]", "", cleaned)
        # Collapse whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        result.append(cleaned)
    return result


def _exact_match(
    preprocessed: list[str],
    candidate_map: dict[str, str],
) -> dict[int, tuple[str, float, str]]:
    """Return index → (canonical, score, method) for exact preprocessed matches."""
    matches: dict[int, tuple[str, float, str]] = {}
    for i, name in enumerate(preprocessed):
        if name in candidate_map:
            matches[i] = (candidate_map[name], 1.0, "exact")
    return matches


def _fuzzy_match(
    preprocessed: list[str],
    unmatched_indices: list[int],
    candidates: list[str],
    original_candidates: list[str],
    threshold: float,
) -> dict[int, tuple[str, float, str]]:
    """Return index → (canonical, score, method) for fuzzy matches above threshold."""
    try:
        matches: dict[int, tuple[str, float, str]] = {}
        for i in unmatched_indices:
            best_score = 0.0
            best_candidate = ""
            for j, cand in enumerate(candidates):
                score = fuzz.token_sort_ratio(preprocessed[i], cand) / 100.0
                if score > best_score:
                    best_score = score
                    best_candidate = original_candidates[j]
            if best_score >= threshold:
                matches[i] = (best_candidate, round(best_score, 4), "fuzzy")
        return matches
    except Exception:
        raise RuntimeError(
            "Something went wrong while comparing names. "
            "Please check your file for unusual characters and try again."
        )


def _semantic_match(
    original_names: list[str],
    unmatched_indices: list[int],
    original_candidates: list[str],
    config: LLMConfig,
) -> dict[int, tuple[str, float, str]]:
    """Return index → (canonical, score, method) for semantic and AI-resolved matches."""
    if not unmatched_indices or not original_candidates:
        return {}

    unmatched_texts = [original_names[i] for i in unmatched_indices]

    try:
        emb_names = embed_items(unmatched_texts)
        emb_candidates = embed_items(original_candidates)
        sim_matrix = cosine_similarity(emb_names, emb_candidates)
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError(
            "Something went wrong while analyzing name similarity. "
            "Please try again or adjust your settings."
        )

    matches: dict[int, tuple[str, float, str]] = {}
    ambiguous_pairs: list[dict] = []
    ambiguous_index_map: list[int] = []  # maps ambiguous_pairs position → unmatched_indices position

    for row, idx in enumerate(unmatched_indices):
        best_col = int(np.argmax(sim_matrix[row]))
        best_score = float(sim_matrix[row, best_col])
        best_candidate = original_candidates[best_col]

        if best_score >= 0.85:
            matches[idx] = (best_candidate, round(best_score, 4), "semantic")
        elif best_score >= 0.70:
            ambiguous_pairs.append({
                "original": original_names[idx],
                "candidate": best_candidate,
                "score": round(best_score, 4),
            })
            ambiguous_index_map.append(idx)

    # Resolve ambiguous pairs via Claude
    if ambiguous_pairs:
        resolved = resolve_ambiguous_entities(config, ambiguous_pairs)
        for pair, orig_idx in zip(resolved, ambiguous_index_map):
            if pair.get("ai_match", False):
                matches[orig_idx] = (pair["candidate"], pair["score"], "ai-resolved")

    return matches


def _pick_canonical_from_group(group_names: list[str]) -> str:
    """Choose the most common original form as the canonical name for a group."""
    counts = Counter(group_names)
    return counts.most_common(1)[0][0]


def find_canonical(
    names: list[str],
    canonical_list: Optional[list[str]],
    strictness: int,
    seed: Optional[int],
    config: LLMConfig,
    strip_suffixes: bool = True,
) -> pd.DataFrame:
    """Run the full entity standardization pipeline and return a results DataFrame."""
    threshold = _STRICTNESS_TO_THRESHOLD.get(strictness, 0.80)
    preprocessed = preprocess_names(names, strip_suffixes=strip_suffixes)

    # Build candidate pool
    if canonical_list is not None:
        original_candidates = canonical_list
        preprocessed_candidates = preprocess_names(canonical_list, strip_suffixes=strip_suffixes)
    else:
        original_candidates = names
        preprocessed_candidates = preprocessed

    # Map preprocessed candidate → original candidate (first occurrence wins)
    candidate_map: dict[str, str] = {}
    for prep, orig in zip(preprocessed_candidates, original_candidates):
        if prep not in candidate_map:
            candidate_map[prep] = orig

    # -- Step 1: Exact match --------------------------------------------------
    all_matches: dict[int, tuple[str, float, str]] = _exact_match(preprocessed, candidate_map)

    # -- Step 2: Fuzzy match --------------------------------------------------
    unmatched = [i for i in range(len(names)) if i not in all_matches]
    fuzzy = _fuzzy_match(preprocessed, unmatched, preprocessed_candidates, original_candidates, threshold)
    all_matches.update(fuzzy)

    # -- Step 3: Semantic + AI match ------------------------------------------
    unmatched = [i for i in range(len(names)) if i not in all_matches]
    semantic = _semantic_match(names, unmatched, original_candidates, config)
    all_matches.update(semantic)

    # -- Step 4: Build results ------------------------------------------------
    results: list[dict] = []
    for i, name in enumerate(names):
        if i in all_matches:
            canonical, score, method = all_matches[i]
            results.append({
                "original_name": name,
                "canonical_name": canonical,
                "match_score": score,
                "method": method,
            })
        else:
            results.append({
                "original_name": name,
                "canonical_name": name,
                "match_score": 0.0,
                "method": "none",
            })

    df = pd.DataFrame(results, columns=["original_name", "canonical_name", "match_score", "method"])

    # -- Step 5: If no canonical list, pick most common form per group --------
    if canonical_list is None:
        groups: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            canon = row["canonical_name"]
            groups.setdefault(canon, []).append(row["original_name"])
        group_canonical: dict[str, str] = {
            key: _pick_canonical_from_group(members) for key, members in groups.items()
        }
        df["canonical_name"] = df["canonical_name"].map(
            lambda c: group_canonical.get(c, c)
        )

    return df
