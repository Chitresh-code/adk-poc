"""Shared model access for every agent.

MODEL_PROVIDER switches between Gemini via AI Studio (default) and any
ChatGPT-API-compatible endpoint via ADK's LiteLLM integration. See
docs/plan.md for why this lives in one place instead of a hardcoded model
string per agent.
"""

from __future__ import annotations

import os

from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

_DEFAULT_GOOGLE_MODEL = "gemini-2.5-flash"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# 429/5xx are already in genai's default retryable status codes; this just
# bounds how hard we retry a transient burst before giving up. It can't fix
# a genuinely exhausted free-tier daily quota (retrying won't help until the
# quota resets), only smooth over short-lived rate-limit spikes.
_RETRY_OPTIONS = types.HttpRetryOptions(attempts=3, initial_delay=2.0, max_delay=30.0)


def get_model() -> Gemini | LiteLlm:
    """Returns the model value to pass as `LlmAgent(model=...)`.

    Reads MODEL_PROVIDER (default "google"):
    - "google": a Gemini model with retry/backoff on transient errors
      (429, 5xx). ADK talks to it directly using GOOGLE_API_KEY (AI
      Studio). Set GOOGLE_GENAI_USE_VERTEXAI=1 plus GOOGLE_CLOUD_PROJECT
      later to move to Vertex; this function doesn't need to change for
      that.
    - "openai": a LiteLlm wrapper honoring OPENAI_API_KEY, OPENAI_MODEL, and
      OPENAI_BASE_URL (or LITELLM_BASE_URL), so it works for real OpenAI or
      any ChatGPT-API-compatible endpoint. OPENAI_REASONING_EFFORT, if set,
      is passed through as-is; reasoning models that don't support function
      tools alongside reasoning on the chat completions endpoint need this
      set to "none" (the provider's error message says so explicitly).

    Raises:
        RuntimeError: if a required env var for the selected provider is
            missing, or MODEL_PROVIDER is set to something unrecognized.
    """
    provider = os.environ.get("MODEL_PROVIDER", "google").strip().lower()

    if provider == "google":
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get(
            "GOOGLE_GENAI_USE_VERTEXAI"
        ):
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Get one at "
                "https://aistudio.google.com/apikey and put it in your .env, "
                "or set GOOGLE_GENAI_USE_VERTEXAI=1 with GOOGLE_CLOUD_PROJECT "
                "to use Vertex AI instead."
            )
        model_name = os.environ.get("GOOGLE_MODEL", _DEFAULT_GOOGLE_MODEL)
        return Gemini(model=model_name, retry_options=_RETRY_OPTIONS)

    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Required when MODEL_PROVIDER=openai."
            )
        model_name = os.environ.get("OPENAI_MODEL", _DEFAULT_OPENAI_MODEL)
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get(
            "LITELLM_BASE_URL"
        )
        reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT")
        kwargs: dict[str, str] = {}
        if base_url:
            kwargs["api_base"] = base_url
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        return LiteLlm(model=f"openai/{model_name}", **kwargs)

    raise RuntimeError(
        f"Unknown MODEL_PROVIDER={provider!r}. Expected 'google' or 'openai'."
    )
