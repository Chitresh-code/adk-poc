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


# LlmAgent.output_schema for the draft step is this wrapper, not a bare
# list[OutreachDraft]: OpenAI's structured-outputs mode requires an object
# at the schema root, and ADK's LiteLLM integration silently drops the
# schema constraint for a plain list[...] generic
# (google.adk.models.lite_llm._to_litellm_response_format has no branch for
# it), which used to let the model return whatever shape it felt like.
# assemble_outreach_packet unwraps "items" back into a plain list in state.
class OutreachDraftList(BaseModel):
    items: list[OutreachDraft]
