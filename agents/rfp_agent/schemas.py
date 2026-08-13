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


# LlmAgent.output_schema for the decompose/draft steps is this wrapper, not
# a bare list[Question]/list[Draft]: OpenAI's structured-outputs mode
# requires an object at the schema root, and ADK's LiteLLM integration
# silently drops the schema constraint for a plain list[...] generic
# (google.adk.models.lite_llm._to_litellm_response_format has no branch for
# it), which used to let the model return whatever shape it felt like. The
# corresponding tool that consumes each key unwraps "items" back into a
# plain list in session state.
class QuestionList(BaseModel):
    items: list[Question]


class Draft(BaseModel):
    id: str
    answer: str
    confidence: Confidence
    needs_sme_review: bool
    sources: list[str] = Field(default_factory=list)


class DraftList(BaseModel):
    items: list[Draft]
