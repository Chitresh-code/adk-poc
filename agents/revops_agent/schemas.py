"""Structured payloads passed between pipeline steps via session state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
IssueType = Literal["missing_fields", "stale", "stalled", "possible_duplicate"]
SubjectType = Literal["deal", "account_pair"]


class HygieneNote(BaseModel):
    subject_type: SubjectType
    subject_id: str
    issue_types: list[IssueType]
    summary: str
    recommended_fix: str
    confidence: Confidence
    needs_review: bool


# LlmAgent.output_schema for the draft step is this wrapper, not a bare
# list[HygieneNote]: OpenAI's structured-outputs mode requires an object at
# the schema root, and ADK's LiteLLM integration silently drops the schema
# constraint for a plain list[...] generic
# (google.adk.models.lite_llm._to_litellm_response_format has no branch for
# it). assemble_hygiene_report unwraps "items" back into a plain list in
# session state.
class HygieneNoteList(BaseModel):
    items: list[HygieneNote] = Field(default_factory=list)
