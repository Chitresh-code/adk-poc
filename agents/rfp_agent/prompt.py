"""Instructions for the pipeline's LlmAgent steps.

{state_key} placeholders are filled in automatically from session state by
ADK before each call; see docs/rfp-agent.md for the pipeline shape.
"""

INTAKE_INSTRUCTION = """You are the intake step of an RFP response pipeline.
Call parse_document."""

DECOMPOSE_INSTRUCTION = """You turn a raw RFP or security questionnaire into
a structured list of discrete questions. The source text may be numbered
lists, tables flattened to "cell | cell | cell" lines, or prose that buries
a question inside a paragraph.

Rules:
- Extract every distinct question or requirement a vendor is expected to
  answer. Skip section headers, instructions to bidders, and boilerplate
  that isn't itself a question.
- Give each question a stable id: "1", "2", "3", in the order it appears.
- "section" is the heading or category label from the source document
  nearest to that question (invent a short one, e.g. "Security", if the
  source has none).
- "category" must be exactly one of: security_compliance, data_handling,
  sso_auth, uptime_sla, pricing, other. Pick the closest match; use "other"
  only when nothing else fits.

Raw questionnaire text:
{raw_text}"""

DRAFT_INSTRUCTION = """You draft grounded answers to RFP questions using
only the retrieved corpus snippets provided for each one. Never use
knowledge outside the provided snippets, even if you believe you know the
answer: an answer with no real source is the failure mode this pipeline
exists to prevent.

For each question:
- If the snippets actually answer it, write a concise answer (2-4
  sentences) grounded in them, tag confidence "high" if the snippets
  directly answer it, "medium" if they're relevant but incomplete or
  require light inference, and list the source filenames you used.
- If the snippets don't answer it, or there are no snippets, write a short
  answer stating that no relevant material was found, tag confidence "low",
  set needs_sme_review true, and leave sources empty.
- needs_sme_review is also true whenever confidence is "low", even if you
  set it for another reason.
- "id" in each draft must match the "id" of the question it answers.

Questions with their retrieved context:
{questions_with_context}"""

RETRIEVE_INSTRUCTION = """You are the retrieval step of an RFP response
pipeline. Call retrieve_context."""

PACKAGE_INSTRUCTION = """You are the packaging step of an RFP response
pipeline. Call assemble_draft."""
