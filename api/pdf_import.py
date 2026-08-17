import json
import os
import re
import uuid
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

from section_registry import BUILTIN_SECTION_ORDER, SECTION_REGISTRY

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
        item_id = str(item.get("id") or _slug_id(prefix, label))
        base = item_id
        n = 2
        while item_id in seen:
            item_id = f"{base}_{n}"
            n += 1
        seen.add(item_id)
        item["id"] = item_id
        item.setdefault("status", "active")
        if prefix == "proj":
            item.setdefault("categories", [])
            item.setdefault("skills", [])
            item.setdefault("technologies", [])
            item.setdefault("bullets", [])
            item.setdefault("url", "")
            item.setdefault("description", "")
        if prefix == "exp":
            item.setdefault("categories", [])
            item.setdefault("skills", [])
            item.setdefault("bullets", [])
            item.setdefault("location", "")
            item.setdefault("startDate", "")
            item.setdefault("endDate", "")
        if prefix == "edu":
            item.setdefault("details", [])
            item.setdefault("location", "")
            item.setdefault("startDate", "")
            item.setdefault("endDate", "")
        if prefix == "ach":
            item.setdefault("date", "")
            item.setdefault("description", "")
        out.append(item)
    return out


def normalize_imported_payload(data: dict) -> dict:
    inventory_in = data.get("inventory") if isinstance(data.get("inventory"), dict) else data
    if not isinstance(inventory_in, dict):
        inventory_in = {}

    basics = inventory_in.get("basics") or data.get("basics") or {}
    if not isinstance(basics, dict):
        basics = {}

    sections_in = inventory_in.get("sections")
    if not isinstance(sections_in, dict):
        sections_in = {}

    def section_items(section: str) -> list:
        bag = sections_in.get(section)
        if isinstance(bag, dict) and isinstance(bag.get("items"), list):
            return bag["items"]
        items = inventory_in.get(section) or data.get(section) or []
        return items if isinstance(items, list) else []

    experience = _ensure_item_ids(
        section_items("experience"),
        "exp",
        ("company", "title"),
    )
    projects = _ensure_item_ids(
        section_items("projects"),
        "proj",
        ("name",),
    )
    education = _ensure_item_ids(
        section_items("education"),
        "edu",
        ("institution", "degree"),
    )
    achievements = _ensure_item_ids(
        section_items("achievements"),
        "ach",
        ("title",),
    )

    skills = inventory_in.get("skills") or data.get("skills") or []
    if not isinstance(skills, list):
        skills = []

    item_map = {
        "experience": experience,
        "projects": projects,
        "education": education,
        "achievements": achievements,
    }
    sections = {
        section: {
            "title": (
                (sections_in.get(section) or {}).get("title")
                if isinstance(sections_in.get(section), dict)
                else None
            )
            or SECTION_REGISTRY[section]["title"],
            "items": item_map[section],
        }
        for section in BUILTIN_SECTION_ORDER
    }

    inventory = {
        "basics": {
            "fullName": basics.get("fullName") or basics.get("name") or "",
            "email": basics.get("email") or "",
            "phone": basics.get("phone") or "",
            "location": basics.get("location") or "",
            "links": basics.get("links") if isinstance(basics.get("links"), list) else [],
        },
        "skills": [str(s) for s in skills],
        "sections": sections,
    }

    resume_in = data.get("resume") if isinstance(data.get("resume"), dict) else {}
    summary = resume_in.get("summary") or data.get("summary") or ""
    requested_order = resume_in.get("sectionOrder")
    if not isinstance(requested_order, list):
        requested_order = []
    section_order: list[str] = []
    for section in requested_order:
        if section in BUILTIN_SECTION_ORDER and section not in section_order:
            section_order.append(section)
    section_order.extend(
        section for section in BUILTIN_SECTION_ORDER if section not in section_order
    )

    return {
        "schemaVersion": 3,
        "intake": {
            "status": "complete",
            "basicsConfirmed": True,
            "skillsConfirmed": True,
            "confirmedSkippedSections": [
                section
                for section in BUILTIN_SECTION_ORDER
                if not item_map[section]
            ],
            "source": "pdf",
        },
        "inventory": inventory,
        "resume": {
            "title": resume_in.get("title") or "Imported Resume",
            "summary": summary if isinstance(summary, str) else "",
            "includedIds": {
                section: [item["id"] for item in items]
                for section, items in item_map.items()
            },
            "sectionOrder": section_order,
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
                    "Return ONLY valid JSON for schemaVersion 3. The exact top-level "
                    "shape is {schemaVersion: 3, inventory, resume}. inventory contains "
                    "basics {fullName, email, phone, location, links[]}, skills[], and "
                    "sections. sections contains experience, projects, education, and "
                    "achievements; each is {title, items[]}. resume contains title, "
                    "summary, includedIds (a map with those four section keys), and "
                    "sectionOrder. Experience items use company, title, location, "
                    "startDate, endDate, bullets[], categories[], skills[], status. "
                    "Project items use name, description, technologies[], bullets[], "
                    "url, categories[], skills[], status. Education items use institution, "
                    "degree, location, startDate, endDate, details[], status; do not put "
                    "research or awards into education. Achievement items use title, date, "
                    "description, status. Give every item a stable string id. Include all "
                    "extracted item ids in the matching includedIds list. Do not invent "
                    "facts. Use empty arrays or strings when the source omits a field."
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