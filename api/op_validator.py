"""Validate structured career operations before execution."""

from __future__ import annotations

from section_registry import get_section_profile
from resume_ops import _find_item, _sections
from retrieval import retrieve_evidence


ALLOWED_TYPES = {"ADD", "UPDATE", "DELETE", "REORDER", "MOVE", "RESTORE", "CLARIFY"}


class ValidationError(Exception):
    def __init__(self, message: str, *, clarification: str | None = None):
        super().__init__(message)
        self.clarification = clarification


def validate_operations(payload: dict, operations: list[dict]) -> list[dict]:
    """Return validated ops or raise ValidationError with clarification."""
    if not operations:
        raise ValidationError("no operations proposed")

    validated: list[dict] = []
    for op in operations:
        op_type = str(op.get("type") or "").upper()
        if op_type not in ALLOWED_TYPES:
            raise ValidationError(f"unknown operation type: {op_type}")

        if op_type == "CLARIFY":
            msg = op.get("data", {}).get("message") or op.get("reason") or "Please clarify."
            raise ValidationError("clarification required", clarification=msg)

        target = op.get("target") or {}
        section = target.get("section")
        entity_id = target.get("entityId") or target.get("parentEntityId")

        if op_type == "ADD":
            section = section or _infer_section(target.get("entityType"))
            if not section:
                raise ValidationError("ADD requires target.section or entityType")
            profile = get_section_profile(section)
            data = {**(op.get("data") or {}), **(op.get("changes") or {})}
            missing = [
                f
                for f in (profile.get("requiredFields") or [])
                if not data.get(f)
            ]
            if missing and section != "skill":
                raise ValidationError(
                    f"ADD {section} missing required fields: {', '.join(missing)}"
                )
            validated.append({**op, "type": op_type, "target": {**target, "section": section}})

        elif op_type == "UPDATE":
            resolved = _resolve_entity(payload, target, op)
            validated.append({**op, "type": op_type, "target": resolved})

        elif op_type == "DELETE":
            if target.get("entityType") == "skill" or section == "skills":
                validated.append({**op, "type": op_type})
            else:
                resolved = _resolve_entity(payload, target, op, allow_ambiguous=False)
                validated.append({**op, "type": op_type, "target": resolved})

        elif op_type == "REORDER":
            changes = op.get("changes") or op.get("data") or {}
            if not changes.get("sectionOrder") and not changes.get("itemIds"):
                raise ValidationError("REORDER requires sectionOrder or itemIds")
            validated.append({**op, "type": op_type})

        elif op_type == "RESTORE":
            version = (op.get("data") or {}).get("version")
            if version is None:
                raise ValidationError("RESTORE requires data.version")
            validated.append({**op, "type": op_type})

        else:
            validated.append({**op, "type": op_type})

    return validated


def _infer_section(entity_type: str | None) -> str | None:
    mapping = {
        "experience": "experience",
        "project": "projects",
        "projects": "projects",
        "education": "education",
        "achievement": "achievements",
        "achievements": "achievements",
        "skill": "skills",
    }
    return mapping.get(str(entity_type or "").lower())


def _resolve_entity(
    payload: dict,
    target: dict,
    op: dict,
    *,
    allow_ambiguous: bool = True,
) -> dict:
    section = target.get("section")
    entity_id = target.get("entityId")
    query = target.get("query") or op.get("reason") or ""

    if entity_id and section:
        sections = _sections(payload)
        if section not in sections:
            raise ValidationError(f"unknown section: {section}")
        bag = sections[section]
        if _find_item(bag.get("items") or [], entity_id) is None:
            raise ValidationError(f"entity not found: {entity_id} in {section}")
        return {**target, "section": section, "entityId": entity_id}

    if entity_id and not section:
        found = _find_entity_anywhere(payload, entity_id)
        if not found:
            raise ValidationError(f"entity not found: {entity_id}")
        return {**target, **found}

    if query or target.get("entityType"):
        retrieval = retrieve_evidence(payload, query or str(target.get("entityType")), section=section)
        items = [e for e in retrieval["evidence"] if e.get("kind") == "inventory_item"]
        if not items:
            raise ValidationError(
                f"no matching entity for: {query or target.get('entityType')}",
                clarification=f"I couldn't find anything matching '{query}'. Can you be more specific?",
            )
        if retrieval.get("ambiguous") and len(items) > 1 and allow_ambiguous:
            lines = "\n".join(
                f"{i + 1}. {it.get('label')}" for i, it in enumerate(items[:5])
            )
            raise ValidationError(
                "ambiguous entity",
                clarification=f"I found multiple matches:\n{lines}\n\nWhich one do you mean?",
            )
        top = items[0]
        return {
            **target,
            "section": top.get("section"),
            "entityId": top.get("itemId"),
        }

    raise ValidationError("target requires entityId or query for resolution")


def _find_entity_anywhere(payload: dict, entity_id: str) -> dict | None:
    for section, bag in _sections(payload).items():
        if _find_item(bag.get("items") or [], entity_id):
            return {"section": section, "entityId": entity_id}
    return None
