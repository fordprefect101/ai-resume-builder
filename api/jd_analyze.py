"""Job description analysis and evidence-grounded variant generation."""

from __future__ import annotations

import json
import os
import uuid

from openai import OpenAI
from dotenv import load_dotenv

from claim_verify import verify_claim
from claims import add_claim
from facts import search_facts
from retrieval import retrieve_evidence

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini"))


def extract_requirements(jd_text: str) -> list[dict]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract job requirements from the description. "
                    'Return JSON: {"requirements": [{"text": string, "category": string}]}'
                ),
            },
            {"role": "user", "content": jd_text[:12000]},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content or "{}")
    reqs = data.get("requirements") or []
    return [r for r in reqs if isinstance(r, dict) and r.get("text")]


def assess_requirement(payload: dict, requirement: str) -> dict:
    evidence = retrieve_evidence(payload, requirement, limit=8)
    fact_hits = search_facts(payload, requirement, limit=8)
    fact_ids = [f.get("id") for f in fact_hits if f.get("id")]

    items = [e for e in evidence.get("evidence") or [] if e.get("kind") == "inventory_item"]
    req_lower = requirement.lower()

    # Direct: requirement term appears in evidence label/content
    direct = []
    partial = []
    for item in items:
        label = str(item.get("label") or "").lower()
        if any(token in label for token in req_lower.split() if len(token) > 3):
            direct.append(item)
        else:
            partial.append(item)

    if direct:
        level = "direct"
    elif partial or fact_ids:
        level = "partial"
    else:
        level = "none"

    return {
        "requirement": requirement,
        "level": level,
        "directEvidence": direct[:5],
        "partialEvidence": partial[:5],
        "factIds": fact_ids[:8],
    }


def analyze_job_description(payload: dict, jd_text: str) -> dict:
    requirements = extract_requirements(jd_text)
    assessments = [assess_requirement(payload, r.get("text", "")) for r in requirements]
    return {
        "requirements": requirements,
        "assessments": assessments,
    }


def generate_grounded_bullet(payload: dict, fact_ids: list[str], jd_context: str = "") -> dict:
    facts = [f for f in (payload.get("facts") or []) if f.get("id") in fact_ids]
    if not facts:
        facts = search_facts(payload, jd_context, limit=6)

    fact_contents = [str(f.get("content") or "") for f in facts if f.get("content")]
    if not fact_contents:
        return {"bullet": "", "status": "unsupported", "supportedBy": []}

    if not os.getenv("OPENAI_API_KEY"):
        bullet = fact_contents[0]
        supported = [f.get("id") for f in facts if f.get("id")][:4]
        return {"bullet": bullet, "status": "supported", "supportedBy": supported}

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Write ONE resume bullet from ONLY the provided facts. "
                    'Return JSON: {"bullet": string}. Do not invent metrics or tools.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"facts": fact_contents, "context": jd_context[:2000]}),
            },
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content or "{}")
    bullet = str(data.get("bullet") or "").strip()
    supported = [f.get("id") for f in facts if f.get("id")][:6]
    verification = verify_claim(payload, bullet, supported)
    return {
        "bullet": bullet,
        "status": verification.get("status"),
        "supportedBy": supported,
        "verification": verification,
    }


def create_job_variant(payload: dict, jd_text: str, name: str | None = None) -> dict:
    analysis = analyze_job_description(payload, jd_text)
    variant_id = f"variant_{uuid.uuid4().hex[:8]}"
    variant_name = name or "Job-specific resume"

    # Select items with direct/partial evidence
    included: dict[str, list[str]] = {
        "experience": [],
        "projects": [],
        "education": [],
        "achievements": [],
    }
    generated_claims: list[dict] = []

    for assessment in analysis.get("assessments") or []:
        if assessment.get("level") == "none":
            continue
        for ev in (assessment.get("directEvidence") or []) + (
            assessment.get("partialEvidence") or []
        ):
            section = ev.get("section")
            item_id = ev.get("itemId")
            if section and item_id and item_id not in (included.get(section) or []):
                included.setdefault(section, []).append(item_id)

    # Fallback: include all if nothing matched
    if not any(included.values()):
        resume = payload.get("resume") or {}
        included = dict(resume.get("includedIds") or {})

    # Generate summary from top facts
    top_facts = []
    for a in analysis.get("assessments") or []:
        top_facts.extend(a.get("factIds") or [])
    bullet_result = generate_grounded_bullet(
        payload, top_facts[:6], jd_context=jd_text[:1500]
    )

    variants = dict(payload.get("variants") or {})
    variants[variant_id] = {
        "id": variant_id,
        "name": variant_name,
        "summary": bullet_result.get("bullet") or "",
        "includedIds": included,
        "sectionOrder": list((payload.get("resume") or {}).get("sectionOrder") or []),
        "jdAnalysis": analysis,
        "generatedClaims": [],
    }

    payload = {**payload, "variants": variants}
    if bullet_result.get("bullet"):
        payload = add_claim(
            payload,
            bullet_result["bullet"],
            bullet_result.get("supportedBy") or [],
            variant_id=variant_id,
            status=bullet_result.get("status") or "pending",
        )
        variants[variant_id]["generatedClaims"] = [
            (payload.get("claims") or [])[-1]["id"]
        ]
        payload["variants"] = variants

    return payload
