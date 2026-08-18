"""Deterministic, bounded context selection for chat and Realtime."""

import re
from typing import Any

from section_registry import get_section_profile

MAX_CANDIDATES = 6
MAX_STRING_CHARS = 500
MAX_LIST_ITEMS = 8

STOP_WORDS = {
    "a",
    "an",
    "and",
    "from",
    "hide",
    "include",
    "item",
    "my",
    "of",
    "on",
    "please",
    "remove",
    "resume",
    "show",
    "the",
    "to",
    "with",
}

SECTION_HINTS = {
    "experience": {
        "experience",
        "experiences",
        "job",
        "jobs",
        "role",
        "roles",
        "work",
    },
    "projects": {"project", "projects", "portfolio"},
    "education": {
        "college",
        "degree",
        "education",
        "school",
        "university",
    },
    "achievements": {
        "achievement",
        "achievements",
        "award",
        "awards",
        "honor",
        "honors",
    },
}


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9+#.-]+", value.lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def _search_text(item: dict) -> str:
    parts: list[str] = []
    for key, value in item.items():
        if key in {"id", "status"}:
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(entry) for entry in value if isinstance(entry, str))
    return " ".join(parts).lower()


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_STRING_CHARS]
    if isinstance(value, list):
        return [
            _compact_value(entry)
            for entry in value[:MAX_LIST_ITEMS]
            if isinstance(entry, (str, int, float, bool))
        ]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def _compact_item(item: dict, on_resume: bool) -> dict:
    compact = {
        "id": item.get("id"),
        "onResume": on_resume,
        "status": item.get("status"),
    }
    for key, value in item.items():
        if key in {"id", "status"}:
            continue
        compact_value = _compact_value(value)
        if compact_value not in (None, "", []):
            compact[key] = compact_value
    return compact


def resume_context_summary(payload: dict) -> dict:
    """Tiny initial context: section counts and current view, never full items."""
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections") or {}
    resume = payload.get("resume") or {}
    included_map = resume.get("includedIds") or {}
    return {
        "sectionOrder": resume.get("sectionOrder") or [],
        "sections": {
            key: {
                "title": (bag or {}).get("title")
                or get_section_profile(key).get("title")
                or key,
                "itemCount": len((bag or {}).get("items") or []),
                "includedCount": len(included_map.get(key) or []),
            }
            for key, bag in sections.items()
        },
        "skills": list(inventory.get("skills") or [])[:20],
    }


def select_resume_context(
    payload: dict,
    query: str,
    *,
    section: str | None = None,
    max_candidates: int = MAX_CANDIDATES,
) -> dict:
    """Select a bounded set of exact resume entities relevant to a user query."""
    inventory = payload.get("inventory") or {}
    sections = inventory.get("sections") or {}
    resume = payload.get("resume") or {}
    included_map = resume.get("includedIds") or {}

    if section and section not in sections:
        raise ValueError(f"unknown section: {section}")

    query_text = str(query or "").strip()
    query_tokens = _tokens(query_text)
    hinted_sections = {
        key
        for key, hints in SECTION_HINTS.items()
        if any(token in hints for token in _tokens(query_text))
    }
    if section:
        hinted_sections = {section}

    scored: list[tuple[int, str, dict]] = []
    for section_key, bag in sections.items():
        if section and section_key != section:
            continue
        included = set(included_map.get(section_key) or [])
        for item in (bag or {}).get("items") or []:
            item_id = str(item.get("id") or "")
            haystack = _search_text(item)
            words = set(_tokens(haystack))
            score = 0
            if item_id and item_id.lower() in query_text.lower():
                score += 100
            if section_key in hinted_sections:
                score += 3
            for token in query_tokens:
                if token in words:
                    score += 4
                elif token in haystack:
                    score += 1
            if score > 0:
                scored.append(
                    (
                        score,
                        section_key,
                        _compact_item(item, item_id in included),
                    )
                )

    scored.sort(key=lambda entry: (-entry[0], entry[1], str(entry[2].get("id"))))

    # If the user named only a section, include a bounded set from that section.
    if not scored and hinted_sections:
        for section_key in hinted_sections:
            bag = sections.get(section_key) or {}
            included = set(included_map.get(section_key) or [])
            for item in (bag.get("items") or [])[:max_candidates]:
                item_id = str(item.get("id") or "")
                scored.append(
                    (1, section_key, _compact_item(item, item_id in included))
                )

    selected = scored[: max(1, min(max_candidates, 12))]
    top_score = selected[0][0] if selected else 0
    close_top_matches = [
        entry for entry in selected if top_score and top_score - entry[0] <= 1
    ]

    return {
        "query": query_text,
        "sectionOrder": resume.get("sectionOrder") or [],
        "hintedSections": sorted(hinted_sections),
        "candidates": [
            {"section": section_key, "score": score, **item}
            for score, section_key, item in selected
        ],
        "ambiguous": len(close_top_matches) > 1,
        "totalCandidatesConsidered": len(scored),
    }
