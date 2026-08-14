"""Structured payloads passed between pipeline steps via session state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

MethodologyElement = Literal[
    "metrics",
    "economic_buyer",
    "decision_criteria",
    "decision_process",
    "paper_process",
    "identify_pain",
    "champion",
    "competition",
]
MethodologyTier = Literal["strong", "adequate", "weak"]
RiskLevel = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]


class CallAnalysis(BaseModel):
    matched_account_id: str | None
    matched_account_name: str | None
    matched_deal_id: str | None
    matched_deal_stage: str | None
    elements_covered: list[MethodologyElement]
    elements_missing: list[MethodologyElement]
    methodology_tier: MethodologyTier
    competitor_mentions: list[str]
    risk_level: RiskLevel
    risk_rationale: str


class CoachingNote(BaseModel):
    summary: str
    coaching_actions: list[str]
    confidence: Confidence
    needs_review: bool
