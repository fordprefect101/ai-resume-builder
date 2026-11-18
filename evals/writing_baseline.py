"""Today's one-pass tidy-up, as the baseline the writing team is measured against.

Today the voice assistant squeezes what the person said into short raw bullets, then
polish_item_bullets (api/enrichment.py) tidies them in a single model call with nothing
checking its work. The squeezing step cannot be reproduced offline, so the story is split
into its sentences and those are handed to the tidy-up as the raw bullets. That is a fair
stand-in: it gives the old path all the words, the way the team gets them.

The app module is imported only when tidy() is called, so importing this file reads no
settings.
"""

from __future__ import annotations

import re


def sentences(story: list[dict]) -> list[str]:
    text = " ".join(str(c.get("text", "")) for c in story)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def tidy(case: dict) -> list[str]:
    """The points today's path would produce for one test story. Makes one model call."""
    import enrichment

    entry = case["entry"]
    item = {
        "id": f"baseline_{case['id']}",
        "title": entry.get("title", ""),
        "company": entry.get("company", ""),
        "name": entry.get("name", ""),
        "bullets": sentences(case["story"]),
    }
    return enrichment.polish_item_bullets(entry["section"], item).get("bullets", [])
