"""CS Churn & Expansion Agent: signals -> score -> research -> draft -> package.

See docs/churn-agent.md for the pipeline design.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.genai import types

from common.model import get_model

from . import prompt
from .schemas import AccountNoteList
from .tools.packaging import assemble_account_packet
from .tools.research import research_playbook
from .tools.scoring import score_churn_risk
from .tools.signals import load_account_signals

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

signals_agent = LlmAgent(
    name="signals",
    model=get_model(),
    instruction=prompt.SIGNALS_INSTRUCTION,
    tools=[load_account_signals],
    generate_content_config=_FORCE_TOOL_CALL,
)

scoring_agent = LlmAgent(
    name="scoring",
    model=get_model(),
    instruction=prompt.SCORING_INSTRUCTION,
    tools=[score_churn_risk],
    generate_content_config=_FORCE_TOOL_CALL,
)

research_agent = LlmAgent(
    name="research",
    model=get_model(),
    instruction=prompt.RESEARCH_INSTRUCTION,
    tools=[research_playbook],
    generate_content_config=_FORCE_TOOL_CALL,
)

draft_agent = LlmAgent(
    name="draft",
    model=get_model(),
    instruction=prompt.DRAFT_INSTRUCTION,
    output_schema=AccountNoteList,
    output_key="drafts",
)

package_agent = LlmAgent(
    name="package",
    model=get_model(),
    instruction=prompt.PACKAGE_INSTRUCTION,
    tools=[assemble_account_packet],
    generate_content_config=_FORCE_TOOL_CALL,
)

root_agent = SequentialAgent(
    name="churn_agent",
    description=(
        "Watches product usage, support tickets, and sentiment across "
        "accounts, flags churn risk early, and drafts QBR prep and "
        "cross-sell notes for a CSM to review before acting."
    ),
    sub_agents=[
        signals_agent,
        scoring_agent,
        research_agent,
        draft_agent,
        package_agent,
    ],
)
