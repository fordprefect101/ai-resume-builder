"""Structured career operations — LLM proposes, app validates and executes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OperationType = Literal[
    "ADD", "UPDATE", "DELETE", "REORDER", "MOVE", "RESTORE", "CLARIFY"
]

EntityType = Literal[
    "skill",
    "experience",
    "project",
    "education",
    "achievement",
    "section",
    "item",
    "summary",
    "variant",
]


class OperationTarget(BaseModel):
    entityType: str
    entityId: str | None = None
    section: str | None = None
    parentEntityId: str | None = None
    query: str | None = None


class CareerOperation(BaseModel):
    type: str
    target: OperationTarget
    changes: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class OperationProposal(BaseModel):
    operations: list[CareerOperation] = Field(default_factory=list)
    clarification: str | None = None
    confidence: float = 1.0


class MutationResult(BaseModel):
    payload: dict
    applied: list[dict]
    skipped: list[dict]
    clarification: str | None = None
    diff: list[str] = Field(default_factory=list)
