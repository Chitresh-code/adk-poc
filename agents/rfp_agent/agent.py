"""RFP / Security Questionnaire Agent: intake -> decompose -> retrieve -> draft -> package.

See docs/rfp-agent.md for the pipeline design and demo script.
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.genai import types

from common.model import get_model

from . import prompt
from .schemas import DraftList, QuestionList
from .tools.intake import parse_document
from .tools.packaging import assemble_draft
from .tools.retrieval import retrieve_context

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
    tools=[parse_document],
    generate_content_config=_FORCE_TOOL_CALL,
)

decompose_agent = LlmAgent(
    name="decompose",
    model=get_model(),
    instruction=prompt.DECOMPOSE_INSTRUCTION,
    output_schema=QuestionList,
    output_key="questions",
)

retrieve_agent = LlmAgent(
    name="retrieve",
    model=get_model(),
    instruction=prompt.RETRIEVE_INSTRUCTION,
    tools=[retrieve_context],
    generate_content_config=_FORCE_TOOL_CALL,
)

draft_agent = LlmAgent(
    name="draft",
    model=get_model(),
    instruction=prompt.DRAFT_INSTRUCTION,
    output_schema=DraftList,
    output_key="drafts",
)

package_agent = LlmAgent(
    name="package",
    model=get_model(),
    instruction=prompt.PACKAGE_INSTRUCTION,
    tools=[assemble_draft],
    generate_content_config=_FORCE_TOOL_CALL,
)

root_agent = SequentialAgent(
    name="rfp_agent",
    description=(
        "Reads an RFP or security questionnaire, decomposes it into "
        "questions, drafts grounded answers from the corpus, and packages "
        "a routed markdown draft for presales."
    ),
    sub_agents=[
        intake_agent,
        decompose_agent,
        retrieve_agent,
        draft_agent,
        package_agent,
    ],
)
