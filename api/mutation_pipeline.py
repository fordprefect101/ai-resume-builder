"""Main V2 mutation pipeline: interpret → validate → execute → version."""

from __future__ import annotations

from facts import ensure_facts
from interpreter import interpret_mutation
from op_executor import execute_operations
from op_validator import ValidationError, validate_operations
from operations import MutationResult
from payload_normalize import normalize_payload


def run_mutation(payload: dict, user_text: str) -> tuple[MutationResult, dict]:
    """
    Full pipeline. Returns MutationResult and trace dict for observability.
    Does NOT persist — caller handles DB.
    """
    payload = ensure_facts(normalize_payload(payload))
    trace: dict = {"input": user_text, "steps": []}

    proposal, interpret_trace = interpret_mutation(payload, user_text)
    trace["interpret"] = interpret_trace
    trace["steps"].append("interpret")

    if proposal.clarification and not proposal.operations:
        return (
            MutationResult(
                payload=payload,
                applied=[],
                skipped=[],
                clarification=proposal.clarification,
            ),
            trace,
        )

    ops = [op.model_dump() if hasattr(op, "model_dump") else dict(op) for op in proposal.operations]
    if not ops and proposal.clarification:
        return (
            MutationResult(
                payload=payload,
                applied=[],
                skipped=[],
                clarification=proposal.clarification,
            ),
            trace,
        )

    try:
        validated = validate_operations(payload, ops)
        trace["validated"] = validated
        trace["steps"].append("validate")
    except ValidationError as err:
        trace["validationError"] = str(err)
        return (
            MutationResult(
                payload=payload,
                applied=[],
                skipped=ops,
                clarification=err.clarification or str(err),
            ),
            trace,
        )

    new_payload, applied, diffs = execute_operations(payload, validated)
    new_payload = ensure_facts(normalize_payload(new_payload))
    trace["applied"] = applied
    trace["diffs"] = diffs
    trace["steps"].append("execute")

    return (
        MutationResult(
            payload=new_payload,
            applied=applied,
            skipped=[],
            diff=diffs,
        ),
        trace,
    )
