"""Verify generated claims against available career facts."""

from __future__ import annotations

import re

from facts import fact_by_id, search_facts


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9+#.-]+", text.lower())
        if len(t) > 2
    }


def verify_claim(payload: dict, claim_content: str, supported_by: list[str]) -> dict:
    """
    Returns status: supported | partial | unsupported
    Uses fact linkage + token overlap as deterministic baseline.
    """
    content = str(claim_content or "").strip()
    if not content:
        return {"status": "unsupported", "reason": "empty claim", "coverage": 0.0}

    linked_facts = [fact_by_id(payload, fid) for fid in supported_by]
    linked_facts = [f for f in linked_facts if f]

    if not linked_facts:
        linked_facts = search_facts(payload, content, limit=8)

    if not linked_facts:
        return {
            "status": "unsupported",
            "reason": "no supporting facts found",
            "coverage": 0.0,
        }

    claim_tokens = _tokens(content)
    if not claim_tokens:
        return {"status": "partial", "reason": "claim too short to verify", "coverage": 0.5}

    fact_tokens: set[str] = set()
    for fact in linked_facts:
        fact_tokens |= _tokens(str(fact.get("content") or ""))

    if not fact_tokens:
        return {"status": "unsupported", "reason": "facts have no tokens", "coverage": 0.0}

    overlap = claim_tokens & fact_tokens
    coverage = len(overlap) / max(len(claim_tokens), 1)

    # Flag inflated language not in facts
    inflation_words = {
        "millions",
        "billions",
        "enterprise",
        "large-scale",
        "petabyte",
        "global",
    }
    claim_lower = content.lower()
    for word in inflation_words:
        if word in claim_lower and word not in " ".join(fact_tokens):
            return {
                "status": "unsupported",
                "reason": f"inflated term '{word}' not in evidence",
                "coverage": coverage,
            }

    if coverage >= 0.6:
        status = "supported"
    elif coverage >= 0.25:
        status = "partial"
    else:
        status = "unsupported"

    return {
        "status": status,
        "reason": f"token coverage {coverage:.0%}",
        "coverage": coverage,
        "matchedFacts": [f.get("id") for f in linked_facts if f.get("id")],
    }
