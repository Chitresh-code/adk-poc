"""Account Research & Outreach Agent: signals -> research -> buyers -> draft -> package.

See docs/agent-2-account-research-agent.md for the pipeline design.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.genai import types

from common.model import get_model

from . import prompt
from .schemas import OutreachDraftList
from .tools.buyers import map_buyers
from .tools.packaging import assemble_outreach_packet
from .tools.research import research_account
from .tools.signals import pull_signals

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
    tools=[pull_signals],
    generate_content_config=_FORCE_TOOL_CALL,
)

research_agent = LlmAgent(
    name="research",
    model=get_model(),
    instruction=prompt.RESEARCH_INSTRUCTION,
    tools=[research_account],
    generate_content_config=_FORCE_TOOL_CALL,
)

buyers_agent = LlmAgent(
    name="buyers",
    model=get_model(),
    instruction=prompt.BUYERS_INSTRUCTION,
    tools=[map_buyers],
    generate_content_config=_FORCE_TOOL_CALL,
)

draft_agent = LlmAgent(
    name="draft",
    model=get_model(),
    instruction=prompt.DRAFT_INSTRUCTION,
    output_schema=OutreachDraftList,
    output_key="drafts",
)

package_agent = LlmAgent(
    name="package",
    model=get_model(),
    instruction=prompt.PACKAGE_INSTRUCTION,
    tools=[assemble_outreach_packet],
    generate_content_config=_FORCE_TOOL_CALL,
)

root_agent = SequentialAgent(
    name="account_research_agent",
    description=(
        "Pulls pending buying signals, researches each account, maps the "
        "right buyer contacts, and drafts grounded outreach for a rep to "
        "review before anything gets sent."
    ),
    sub_agents=[
        signals_agent,
        research_agent,
        buyers_agent,
        draft_agent,
        package_agent,
    ],
)
