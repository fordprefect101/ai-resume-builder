import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini")


def enrich_project(project: dict) -> dict:
    """
    Returns enrichment fields only: categories, skills.
    Does not invent ids or overwrite user bullets.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {"categories": [], "skills": []}

    prompt = {
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "technologies": project.get("technologies") or [],
        "bullets": project.get("bullets") or [],
    }

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You classify resume projects for retrieval and filtering. "
                    "Return ONLY valid JSON with keys categories (string[]) and skills (string[]). "
                    "categories: 2-5 short kebab-case themes (e.g. backend, audio, side-project). "
                    "skills: concrete technologies/skills implied by the project. "
                    "Do not invent experience the user did not describe."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt),
            },
        ],
        text={"format": {"type": "json_object"}},
    )

    raw = response.output_text
    data = json.loads(raw)

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

def polish_project_bullets(project: dict) -> dict:
    """
    Turn rough notes into ATS-style bullets.
    Does not invent employers, metrics, or technologies the user did not mention.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {"bullets": list(project.get("bullets") or [])}

    prompt = {
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "technologies": project.get("technologies") or [],
        "rawBullets": project.get("bullets") or [],
    }

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You polish resume PROJECT bullets for ATS-friendly scanning. "
                    "Return ONLY valid JSON: {\"bullets\": string[]}. "
                    "Rules: "
                    "- Start with strong action verbs. "
                    "- Be concrete and scannable; prefer impact + tech when the user stated them. "
                    "- Do NOT invent metrics, employers, tools, or outcomes not in the input. "
                    "- Do NOT write education or personal-detail content. "
                    "- Keep 2-6 bullets. Preserve the user's meaning. "
                    "- Plain text only; no markdown."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
        text={"format": {"type": "json_object"}},
    )

    data = json.loads(response.output_text)
    bullets = data.get("bullets") or []
    if not isinstance(bullets, list):
        bullets = project.get("bullets") or []

    cleaned = [str(b).strip() for b in bullets if str(b).strip()]
    if not cleaned:
        cleaned = [str(b).strip() for b in (project.get("bullets") or []) if str(b).strip()]

    return {"bullets": cleaned[:6]}