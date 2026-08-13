"""Structured payloads passed between pipeline steps via session state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
RiskTier = Literal["high", "medium", "low"]
NoteType = Literal["qbr_prep", "cross_sell"]


class AccountNote(BaseModel):
    account_id: str
    note_type: NoteType
    summary: str
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: Confidence
    needs_review: bool


# LlmAgent.output_schema for the draft step is this wrapper, not a bare
# list[AccountNote]: OpenAI's structured-outputs mode requires an object at
# the schema root, and ADK's LiteLLM integration silently drops the schema
# constraint for a plain list[...] generic
# (google.adk.models.lite_llm._to_litellm_response_format has no branch for
# it), which would otherwise let the model return whatever shape it felt
# like. assemble_account_packet unwraps "items" back into a plain list in
# session state.
class AccountNoteList(BaseModel):
    items: list[AccountNote]
