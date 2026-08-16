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