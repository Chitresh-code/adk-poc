"""RevOps CRM Hygiene & Forecasting Agent: crm -> hygiene -> forecast -> draft -> package.

See docs/revops-agent.md for the pipeline design.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.genai import types

from common.model import get_model

from . import prompt
from .schemas import HygieneNoteList
from .tools.crm import load_crm_records
from .tools.forecast import sharpen_forecast
from .tools.hygiene import sweep_crm_hygiene
from .tools.packaging import assemble_hygiene_report

# Forces a function call instead of relying on the model choosing to call
# the tool on its own: weaker/free models otherwise sometimes just respond
# in text, which leaves the state key the next step's instruction expects
# unset. Translates to Gemini's function_calling_config mode="ANY" or, via
# ADK's LiteLLM integration, tool_choice="required" for OpenAI-compatible
# providers.
_FORCE_TOOL_CALL = types.GenerateContentConfig(
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode="ANY")
    )
)

crm_agent = LlmAgent(
    name="crm",
    model=get_model(),
    instruction=prompt.CRM_INSTRUCTION,
    tools=[load_crm_records],
    generate_content_config=_FORCE_TOOL_CALL,
)

hygiene_agent = LlmAgent(
    name="hygiene",
    model=get_model(),
    instruction=prompt.HYGIENE_INSTRUCTION,
    tools=[sweep_crm_hygiene],
    generate_content_config=_FORCE_TOOL_CALL,
)

forecast_agent = LlmAgent(
    name="forecast",
    model=get_model(),
    instruction=prompt.FORECAST_INSTRUCTION,
    tools=[sharpen_forecast],
    generate_content_config=_FORCE_TOOL_CALL,
)

draft_agent = LlmAgent(
    name="draft",
    model=get_model(),
    instruction=prompt.DRAFT_INSTRUCTION,
    output_schema=HygieneNoteList,
    output_key="drafts",
)

package_agent = LlmAgent(
    name="package",
    model=get_model(),
    instruction=prompt.PACKAGE_INSTRUCTION,
    tools=[assemble_hygiene_report],
    generate_content_config=_FORCE_TOOL_CALL,
)

root_agent = SequentialAgent(
    name="revops_agent",
    description=(
        "Sweeps the CRM for missing, stale, or duplicate data, flags "
        "stalled deals, sharpens the forecast, and drafts recommended "
        "fixes for a RevOps manager to review. Read-only: it never edits "
        "or merges CRM records itself."
    ),
    sub_agents=[
        crm_agent,
        hygiene_agent,
        forecast_agent,
        draft_agent,
        package_agent,
    ],
)
