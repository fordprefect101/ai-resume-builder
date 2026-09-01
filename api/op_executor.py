"""Execute validated career operations via deterministic resume_ops."""

from __future__ import annotations

from facts import add_fact, sync_facts_from_item
from resume_ops import (
    add_item,
    archive_item,
    exclude_from_resume,
    get_item,
    include_on_resume,
    reorder_items,
    reorder_sections,
    reorder_skills,
    set_skills_edit,
    set_summary,
    update_item,
)


def execute_operations(payload: dict, operations: list[dict]) -> tuple[dict, list[dict], list[str]]:
    """Apply operations sequentially. Returns (payload, applied, diff_lines)."""
    applied: list[dict] = []
    diffs: list[str] = []

    for op in operations:
        op_type = str(op.get("type") or "").upper()
        target = op.get("target") or {}
        changes = op.get("changes") or {}
        data = op.get("data") or {}

        if op_type == "ADD":
            section = target.get("section")
            if section == "skills" or target.get("entityType") == "skill":
                skill = data.get("skill") or changes.get("skill") or data.get("name")
                skills = list((payload.get("inventory") or {}).get("skills") or [])
                if skill and skill not in skills:
                    skills.append(skill)
                    payload = set_skills_edit(payload, skills)
                    diffs.append(f"+ skill: {skill}")
                    applied.append({"type": op_type, "skill": skill})
                continue

            fields = {**data, **changes}
            payload, new_id = add_item(payload, section, fields)
            item = get_item(payload, section, new_id)
            payload = sync_facts_from_item(payload, section, item)
            diffs.append(f"+ {section} item: {new_id}")
            applied.append({"type": op_type, "section": section, "itemId": new_id})

        elif op_type == "UPDATE":
            section = target["section"]
            entity_id = target["entityId"]
            if section == "skills" or target.get("entityType") == "skill":
                if changes.get("skills") or data.get("skills"):
                    payload = set_skills_edit(
                        payload, changes.get("skills") or data.get("skills")
                    )
                    diffs.append("~ skills updated")
                continue

            if target.get("entityType") == "summary" or section == "summary":
                payload = set_summary(payload, changes.get("summary") or data.get("summary") or "")
                diffs.append("~ summary updated")
                applied.append({"type": op_type, "target": "summary"})
                continue

            payload = update_item(payload, section, entity_id, {**data, **changes})
            item = get_item(payload, section, entity_id)
            payload = sync_facts_from_item(payload, section, item)
            diffs.append(f"~ {section}/{entity_id} updated")
            applied.append({"type": op_type, "section": section, "itemId": entity_id})

        elif op_type == "DELETE":
            if target.get("entityType") == "skill" or target.get("section") == "skills":
                skill = changes.get("skill") or data.get("skill") or target.get("query")
                skills = [
                    s
                    for s in (payload.get("inventory") or {}).get("skills") or []
                    if str(s).lower() != str(skill or "").lower()
                ]
                payload = set_skills_edit(payload, skills)
                diffs.append(f"- skill: {skill}")
                applied.append({"type": op_type, "skill": skill})
                continue
            section = target["section"]
            entity_id = target["entityId"]
            payload = archive_item(payload, section, entity_id)
            diffs.append(f"- archived {section}/{entity_id}")
            applied.append({"type": op_type, "section": section, "itemId": entity_id})

        elif op_type == "REORDER":
            if changes.get("sectionOrder"):
                payload = reorder_sections(payload, changes["sectionOrder"])
                diffs.append("~ section order")
                applied.append({"type": op_type, "sectionOrder": changes["sectionOrder"]})
            elif changes.get("itemIds") and changes.get("section"):
                payload = reorder_items(
                    payload, changes["section"], changes["itemIds"]
                )
                diffs.append(f"~ reordered {changes['section']} items")
                applied.append({"type": op_type, "section": changes["section"]})
            elif changes.get("skills"):
                payload = reorder_skills(payload, changes["skills"])
                diffs.append("~ skills reordered")
                applied.append({"type": op_type, "skills": changes["skills"]})

        elif op_type == "MOVE":
            # MOVE = include/exclude between view and inventory visibility
            section = target.get("section")
            entity_id = target.get("entityId")
            dest = (changes.get("to") or data.get("to") or "").lower()
            if dest == "resume":
                payload = include_on_resume(payload, section, entity_id)
                diffs.append(f"+ included {section}/{entity_id} on resume")
            else:
                payload = exclude_from_resume(payload, section, entity_id)
                diffs.append(f"- excluded {section}/{entity_id} from resume")
            applied.append({"type": op_type, "section": section, "itemId": entity_id})

    return payload, applied, diffs
