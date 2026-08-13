"""Structured payloads passed between pipeline steps via session state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
Category = Literal[
    "security_compliance",
    "data_handling",
    "sso_auth",
    "uptime_sla",
    "pricing",
    "other",
]


class Question(BaseModel):
    id: str
    question: str
    section: str
    category: Category


class Draft(BaseModel):
    id: str
    answer: str
    confidence: Confidence
    needs_sme_review: bool
    sources: list[str] = Field(default_factory=list)
