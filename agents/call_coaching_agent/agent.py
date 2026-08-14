"""Call Analysis & Coaching Agent: intake -> deal context -> analyze -> draft -> package.

See docs/call-coaching-agent.md for the pipeline design.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.genai import types

from common.model import get_model

from . import prompt
from .schemas import CallAnalysis, CoachingNote
from .tools.crm import load_deal_context
from .tools.intake import load_call
from .tools.packaging import update_crm_and_package

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

intake_agent = LlmAgent(
    name="intake",
    model=get_model(),
    instruction=prompt.INTAKE_INSTRUCTION,
    tools=[load_call],
    generate_content_config=_FORCE_TOOL_CALL,
)

crm_agent = LlmAgent(
    name="crm",
    model=get_model(),
    instruction=prompt.CRM_INSTRUCTION,
    tools=[load_deal_context],
    generate_content_config=_FORCE_TOOL_CALL,
)

analyze_agent = LlmAgent(
    name="analyze",
    model=get_model(),
    instruction=prompt.ANALYZE_INSTRUCTION,
    output_schema=CallAnalysis,
    output_key="analysis",
)

draft_agent = LlmAgent(
    name="draft",
    model=get_model(),
    instruction=prompt.DRAFT_INSTRUCTION,
    output_schema=CoachingNote,
    output_key="coaching_note",
)

package_agent = LlmAgent(
    name="package",
    model=get_model(),
    instruction=prompt.PACKAGE_INSTRUCTION,
    tools=[update_crm_and_package],
    generate_content_config=_FORCE_TOOL_CALL,
)

root_agent = SequentialAgent(
    name="call_coaching_agent",
    description=(
        "Takes one sales call (an uploaded audio file, an uploaded "
        "transcript, or pasted transcript text), transcribes audio locally "
        "when needed, scores it against a MEDDPICC-style methodology, "
        "surfaces competitor mentions and deal risk, and, for calls on a "
        "matched deal that come back flagged, writes a coaching summary "
        "back to the CRM."
    ),
    sub_agents=[
        intake_agent,
        crm_agent,
        analyze_agent,
        draft_agent,
        package_agent,
    ],
)
