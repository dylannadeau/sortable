"""Centralized Claude API interface — all LLM calls, retries, and error handling."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic

MODEL = "claude-sonnet-4-6"
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


def _call_claude(api_key: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Send a message to Claude and return the text response, with retry logic."""
    client = anthropic.Anthropic(api_key=api_key)
    last_err: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as exc:
            last_err = exc
            time.sleep(_BASE_DELAY * (2 ** attempt))
        except anthropic.APIStatusError as exc:
            raise RuntimeError(
                f"The API returned an error (status {exc.status_code}). "
                "Please check your API key and try again."
            ) from exc
        except anthropic.APIConnectionError as exc:
            last_err = exc
            time.sleep(_BASE_DELAY * (2 ** attempt))
        except Exception as exc:
            raise RuntimeError(
                f"An unexpected error occurred while contacting the API: {exc}"
            ) from exc

    raise RuntimeError(
        "The API is temporarily unavailable after multiple attempts. "
        "Please wait a moment and try again."
    ) from last_err


def _parse_json(text: str, expected_type: type) -> Any:
    """Extract and parse the first JSON object or array from a text response."""
    # Strip markdown fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else 3
        cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Find the first { or [ depending on expected type
    start_char = "{" if expected_type is dict else "["
    end_char = "}" if expected_type is dict else "]"
    start = cleaned.find(start_char)
    end = cleaned.rfind(end_char)
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No valid JSON {expected_type.__name__} found in response")

    return json.loads(cleaned[start : end + 1])


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """Verify that an API key is valid by making a minimal API call."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return True, ""
    except anthropic.AuthenticationError:
        return False, "This API key is invalid. Please check it and try again."
    except anthropic.APIConnectionError:
        return False, "Could not connect to the Anthropic API. Please check your internet connection."
    except anthropic.APIStatusError as exc:
        return False, f"The API returned an error (status {exc.status_code}). Please try again later."
    except Exception as exc:
        return False, f"Could not validate the API key: {exc}"


def label_clusters(api_key: str, clusters: dict[int, list[str]], style: str) -> dict[int, str]:
    """Generate a human-readable label for each cluster using Claude."""
    style_guidance = {
        "Short": "Use 1-2 words per label. Be concise.",
        "Descriptive": "Use 3-6 words per label. Be clear and descriptive.",
        "Technical": "Use precise, domain-specific terminology for each label.",
    }

    system = (
        "You are a labeling assistant. You will be given groups of related items. "
        "Your job is to generate a short, human-readable label for each group.\n\n"
        f"Style: {style_guidance.get(style, style_guidance['Descriptive'])}\n\n"
        "Respond with ONLY a JSON object mapping each group ID (as a string) to its label. "
        "No extra text, no explanation."
    )

    cluster_desc = "\n".join(
        f"Group {cid}: {', '.join(items[:10])}"
        for cid, items in sorted(clusters.items())
    )
    user = f"Label these groups:\n\n{cluster_desc}"

    text = _call_claude(api_key, system, user)

    try:
        raw = _parse_json(text, dict)
        return {int(k): str(v) for k, v in raw.items()}
    except (ValueError, KeyError, TypeError):
        return {cid: f"Group {cid}" for cid in clusters}


def resolve_ambiguous_entities(api_key: str, pairs: list[dict]) -> list[dict]:
    """Ask Claude whether each ambiguous entity pair refers to the same entity."""
    if not pairs:
        return []

    system = (
        "You are an entity resolution assistant. You will be given pairs of names "
        "with a similarity score. For each pair, decide if they refer to the same "
        "real-world entity (True) or not (False).\n\n"
        "Respond with ONLY a JSON array of booleans in the same order as the input. "
        "No extra text, no explanation."
    )

    pair_lines = "\n".join(
        f'{i+1}. "{p["original"]}" vs "{p["candidate"]}" (score: {p["score"]:.2f})'
        for i, p in enumerate(pairs)
    )
    user = f"Are these the same entity?\n\n{pair_lines}"

    text = _call_claude(api_key, system, user)

    try:
        results = _parse_json(text, list)
        if len(results) != len(pairs):
            raise ValueError("Length mismatch")
        return [{**p, "ai_match": bool(r)} for p, r in zip(pairs, results)]
    except (ValueError, TypeError):
        # Conservative fallback: treat ambiguous pairs as non-matches
        return [{**p, "ai_match": False} for p in pairs]
