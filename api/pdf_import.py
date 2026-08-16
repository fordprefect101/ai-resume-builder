import json
import os
import re
import uuid
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini"))

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIN_EXTRACTED_CHARS = 40
MAX_RESUME_SOURCE_CHARS = 100_000


class PdfImportError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise PdfImportError("file_too_large")

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as err:
        raise PdfImportError(f"invalid_pdf: {err}") from err

    parts = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(parts).strip()

    if len(text) < MIN_EXTRACTED_CHARS:
        raise PdfImportError(
            "insufficient_text — scanned/image PDFs are not supported yet"
        )

    if len(text) > MAX_RESUME_SOURCE_CHARS:
        text = text[:MAX_RESUME_SOURCE_CHARS]

    return text


def _slug_id(prefix: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")
    slug = (slug[:24] or uuid.uuid4().hex[:8])
    return f"{prefix}_{slug}"


def _ensure_item_ids(items: list, prefix: str, name_keys: tuple[str, ...]) -> list:
    seen: set[str] = set()
    out = []
    for raw in items or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        label = next((str(item.get(k) or "") for k in name_keys if item.get(k)), "")
        item_id = item.get("id") or _slug_id(prefix, label)
        base = item_id
        n = 2
        while item_id in seen:
            item_id = f"{base}_{n}"
            n += 1
        seen.add(item_id)
        item["id"] = item_id
        item.setdefault("status", "active")
        item.setdefault("categories", [])
        item.setdefault("skills", [])
        if prefix == "proj":
            item.setdefault("technologies", [])
            item.setdefault("bullets", [])
            item.setdefault("url", "")
            item.setdefault("description", "")
        if prefix == "exp":
            item.setdefault("bullets", [])
            item.setdefault("location", "")
        if prefix == "edu":
            item.setdefault("details", [])
        out.append(item)
    return out


def normalize_imported_payload(data: dict) -> dict:
    inventory_in = data.get("inventory") if isinstance(data.get("inventory"), dict) else data
    if not isinstance(inventory_in, dict):
        inventory_in = {}

    basics = inventory_in.get("basics") or data.get("basics") or {}
    if not isinstance(basics, dict):
        basics = {}

    experience = _ensure_item_ids(
        inventory_in.get("experience") or data.get("experience") or [],
        "exp",
        ("company", "title"),
    )
    projects = _ensure_item_ids(
        inventory_in.get("projects") or data.get("projects") or [],
        "proj",
        ("name",),
    )
    education = _ensure_item_ids(
        inventory_in.get("education") or data.get("education") or [],
        "edu",
        ("institution", "degree"),
    )
    achievements = _ensure_item_ids(
        inventory_in.get("achievements") or data.get("achievements") or [],
        "ach",
        ("title",),
    )

    skills = inventory_in.get("skills") or data.get("skills") or []
    if not isinstance(skills, list):
        skills = []

    inventory = {
        "basics": {
            "fullName": basics.get("fullName") or basics.get("name") or "",
            "email": basics.get("email") or "",
            "phone": basics.get("phone") or "",
            "location": basics.get("location") or "",
            "links": basics.get("links") if isinstance(basics.get("links"), list) else [],
        },
        "skills": [str(s) for s in skills],
        "experience": experience,
        "projects": projects,
        "education": education,
        "achievements": achievements,
    }

    resume_in = data.get("resume") if isinstance(data.get("resume"), dict) else {}
    summary = resume_in.get("summary") or data.get("summary") or ""

    return {
        "schemaVersion": 2,
        "inventory": inventory,
        "resume": {
            "title": resume_in.get("title") or "Imported Resume",
            "summary": summary if isinstance(summary, str) else "",
            "includedExperienceIds": [e["id"] for e in experience],
            "includedProjectIds": [p["id"] for p in projects],
            "includedEducationIds": [e["id"] for e in education],
            "includedAchievementIds": [a["id"] for a in achievements],
            "sectionOrder": resume_in.get("sectionOrder")
            or ["experience", "projects", "education", "achievements"],
        },
    }


def structure_resume_text(text: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise PdfImportError("OPENAI_API_KEY is not set", status_code=500)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract a structured resume from the user's text. "
                    "Return ONLY valid JSON with inventory + resume for schemaVersion 2. "
                    "inventory: basics (fullName, email, phone, location, links[]), "
                    "skills[], experience[], projects[], education[], achievements[]. "
                    "Give each item a stable string id, status 'active', categories[], skills[]. "
                    "Do not invent facts not in the source. Use empty arrays/strings when unknown."
                ),
            },
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise PdfImportError("model_json_invalid", status_code=500)
    return normalize_imported_payload(data)


def import_pdf_bytes(file_bytes: bytes) -> dict:
    text = extract_text_from_pdf(file_bytes)
    return structure_resume_text(text)