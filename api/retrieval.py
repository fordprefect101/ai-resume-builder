"""Hybrid career evidence retrieval — structured baseline with optional semantic scoring."""

from __future__ import annotations

from context_selector import select_resume_context
from facts import search_facts


def retrieve_evidence(
    payload: dict,
    query: str,
    *,
    section: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Structured retrieval over inventory items + facts.
    Returns ranked evidence with direct/partial classification hints.
    """
    context = select_resume_context(payload, query, section=section, max_candidates=limit)
    fact_hits = search_facts(payload, query, limit=limit)

    evidence: list[dict] = []

    for candidate in context.get("candidates") or []:
        evidence.append(
            {
                "kind": "inventory_item",
                "section": candidate.get("section"),
                "itemId": candidate.get("id"),
                "score": candidate.get("score", 0),
                "label": _item_label(candidate),
                "source": "structured",
            }
        )

    for fact in fact_hits:
        evidence.append(
            {
                "kind": "fact",
                "factId": fact.get("id"),
                "content": fact.get("content"),
                "score": 5,
                "context": fact.get("context"),
                "source": "structured",
            }
        )

    # Dedupe and sort
    seen: set[str] = set()
    ranked: list[dict] = []
    for item in sorted(evidence, key=lambda x: -x.get("score", 0)):
        key = item.get("factId") or f"{item.get('section')}:{item.get('itemId')}"
        if key in seen:
            continue
        seen.add(key)
        ranked.append(item)

    return {
        "query": query,
        "ambiguous": context.get("ambiguous", False),
        "evidence": ranked[:limit],
        "method": "structured",
    }


def _item_label(candidate: dict) -> str:
    for key in ("company", "title", "name", "institution", "degree"):
        if candidate.get(key):
            other = candidate.get("title") if key == "company" else candidate.get("company")
            if key == "company" and candidate.get("title"):
                return f"{candidate['company']} — {candidate['title']}"
            if key == "institution" and candidate.get("degree"):
                return f"{candidate['degree']} @ {candidate['institution']}"
            return str(candidate[key])
    return str(candidate.get("id") or "item")
