"""Registry-driven enrichment / bullet polish for list-section items."""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from section_registry import get_section_profile

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini")


def _item_prompt(item: dict, profile: dict) -> dict:
    """Compact JSON for the model: label fields + common content fields."""
    keys = list(profile.get("labelFields") or [])
    for key in (
        "description",
        "technologies",
        "bullets",
        "company",
        "title",
        "name",
        "location",
        "startDate",
        "endDate",
        "institution",
        "degree",
        "date",
    ):
        if key not in keys:
            keys.append(key)
    out = {}
    for key in keys:
        if key in item:
            out[key] = item.get(key)
    return out


def enrich_item(section: str, item: dict) -> dict:
    """
    Return categories + skills when the section profile allows enrich.
    No-op (empty) when enrich is false or no API key.
    """
    profile = get_section_profile(section)
    if not profile.get("enrich"):
        return {}

    if not os.getenv("OPENAI_API_KEY"):
        return {"categories": [], "skills": []}

    kind = profile.get("kind") or section
    title = profile.get("title") or section
    prompt = _item_prompt(item, profile)

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    f"You classify resume {title} items (kind={kind}) for retrieval. "
                    "Return ONLY valid JSON: "
                    '{"categories": string[], "skills": string[]}. '
                    "categories: 2-5 short kebab-case themes. "
                    "skills: concrete skills implied by the item. "
                    "Do not invent facts the user did not describe."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
        text={"format": {"type": "json_object"}},
    )

    data = json.loads(response.output_text)
    categories = data.get("categories") or []
    skills = data.get("skills") or []
    if not isinstance(categories, list):
        categories = []
    if not isinstance(skills, list):
        skills = []

    return {
        "categories": [str(c) for c in categories][:8],
        "skills": [str(s) for s in skills][:12],
    }


def polish_item_bullets(section: str, item: dict) -> dict:
    """
    Polish bullets when the section profile allows polishBullets.
    No-op (empty dict) when polish is false.
    """
    profile = get_section_profile(section)
    if not profile.get("polishBullets"):
        return {}

    raw = list(item.get("bullets") or [])
    if not os.getenv("OPENAI_API_KEY"):
        return {"bullets": raw}

    kind = profile.get("kind") or section
    title = profile.get("title") or section
    prompt = {
        **_item_prompt(item, profile),
        "rawBullets": raw,
    }

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    f"You polish resume {title} bullets (kind={kind}) for ATS scanning. "
                    'Return ONLY valid JSON: {"bullets": string[]}. '
                    "Action verbs, concrete, scannable. "
                    "Do NOT invent metrics, tools, or outcomes not in the input. "
                    "Keep 2-6 bullets. Plain text only."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
        text={"format": {"type": "json_object"}},
    )

    data = json.loads(response.output_text)
    bullets = data.get("bullets") or []
    if not isinstance(bullets, list):
        bullets = raw

    cleaned = [str(b).strip() for b in bullets if str(b).strip()]
    if not cleaned:
        cleaned = [str(b).strip() for b in raw if str(b).strip()]

    return {"bullets": cleaned[:6]}


def enrich_section_item(section: str, item: dict) -> dict:
    """Run enrich + polish per registry flags; merge into one patch dict."""
    enrichment: dict = {}
    enrichment.update(enrich_item(section, item))
    enrichment.update(polish_item_bullets(section, item))
    return enrichment
