"""LLM interpreter: natural language → structured career operations."""

from __future__ import annotations

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from context_selector import resume_context_summary, select_resume_context
from operations import OperationProposal

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_ENRICH_MODEL", "gpt-4.1-mini"))

SYSTEM = """You translate user requests into structured career database operations.
Return ONLY valid JSON matching this shape:
{
  "operations": [
    {
      "type": "ADD|UPDATE|DELETE|REORDER|MOVE|CLARIFY",
      "target": {
        "entityType": "skill|experience|project|education|achievement|item|summary",
        "entityId": "optional stable id if known",
        "section": "experience|projects|education|achievements",
        "query": "optional search phrase for entity resolution"
      },
      "changes": {},
      "data": {},
      "reason": "brief"
    }
  ],
  "clarification": null,
  "confidence": 0.0-1.0
}

Rules:
- Propose operations; do NOT invent facts the user did not state.
- Use UPDATE with changes.bullets.add for new achievement bullets.
- Use UPDATE with changes.technologies.add for new technologies.
- For skill changes use entityType skill with ADD/DELETE/REORDER.
- If ambiguous, return a single CLARIFY operation with data.message explaining options.
- Prefer entityId from context candidates when confident.
- Never modify personal basics (name, email, phone, location, links).
- Multiple operations are allowed in one response.
"""


def interpret_mutation(payload: dict, user_text: str) -> tuple[OperationProposal, dict]:
    """Returns proposal and trace metadata."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    context = select_resume_context(payload, user_text)
    summary = resume_context_summary(payload)

    user_content = json.dumps(
        {
            "resumeSummary": summary,
            "candidates": context.get("candidates"),
            "ambiguous": context.get("ambiguous"),
            "skills": (payload.get("inventory") or {}).get("skills"),
            "userRequest": user_text,
        }
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)

    proposal = OperationProposal(
        operations=data.get("operations") or [],
        clarification=data.get("clarification"),
        confidence=float(data.get("confidence") or 0.8),
    )

    trace = {
        "model": MODEL,
        "context": context,
        "summary": summary,
        "rawProposal": data,
    }
    return proposal, trace
