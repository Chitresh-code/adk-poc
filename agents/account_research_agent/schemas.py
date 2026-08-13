"""Structured payloads passed between pipeline steps via session state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Confidence = Literal["high", "medium", "low"]


class OutreachDraft(BaseModel):
    account_id: str
    contact_name: str
    contact_title: str
    subject: str
    body: str
    confidence: Confidence
    needs_review: bool
