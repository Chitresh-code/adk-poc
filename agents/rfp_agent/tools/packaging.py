"""Assembles the final answer markdown from decomposed questions and drafts."""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

_ROUTING_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "routing_map.json"


def _load_routing_map() -> dict[str, str]:
    return json.loads(_ROUTING_MAP_PATH.read_text(encoding="utf-8"))


async def assemble_draft(tool_context: ToolContext) -> dict | str:
    """Builds the packaged markdown doc from state["questions"] and state["drafts"].

    Sets skip_summarization on every path so this becomes the chat's final
    response verbatim: the packaged markdown is exactly what presales would
    hand off, not a paraphrase of it, and the LLM is forced to call this
    tool (see agent.py), which would otherwise force a second, pointless
    tool-call attempt on a follow-up summarization turn.

    Returns the markdown as a plain string on success, not wrapped in a
    dict: ADK's function-response handling only promotes a plain string
    verbatim into the turn's visible text part, a dict gets JSON-dumped
    instead, see google/adk/flows/llm_flows/functions.py.

    Returns:
        The markdown string, or a dict with "error" if a required pipeline
        step hasn't run yet.
    """
    tool_context.actions.skip_summarization = True

    questions = tool_context.state.get("questions")
    drafts = tool_context.state.get("drafts")
    if isinstance(drafts, dict):
        # draft's output_schema wraps the list (see schemas.DraftList);
        # normalize back to a plain list before use.
        drafts = drafts.get("items", [])
        tool_context.state["drafts"] = drafts
    if not questions:
        return {"error": "No questions in state. Run decompose first."}
    if not drafts:
        return {"error": "No drafts in state. Run draft first."}

    routing_map = _load_routing_map()
    drafts_by_id = {d["id"]: d for d in drafts}

    source_filename = tool_context.state.get("source_filename", "the uploaded questionnaire")
    lines = ["# RFP Response Draft", "", f"Source: {source_filename}", ""]

    review_queue: list[tuple[str, str]] = []

    for question in questions:
        draft = drafts_by_id.get(question["id"])
        lines.append(f"## {question['id']}. {question['question']}")
        lines.append(f"*Section: {question['section']}*")
        lines.append("")

        if draft is None:
            lines.append("_No draft generated for this question._")
            lines.append("")
            continue

        lines.append(draft["answer"])
        lines.append("")
        lines.append(f"**Confidence:** {draft['confidence']}")

        if draft["sources"]:
            lines.append(f"**Sources:** {', '.join(draft['sources'])}")
        else:
            lines.append("**Sources:** none found in corpus")

        if draft["needs_sme_review"]:
            owner = routing_map.get(question["category"], routing_map["other"])
            lines.append(f"**Needs SME review:** yes, route to {owner}")
            review_queue.append((question["id"], owner))

        lines.append("")

    if review_queue:
        lines.append("## Routing summary")
        for question_id, owner in review_queue:
            lines.append(f"- Q{question_id} -> {owner}")
        lines.append("")

    markdown = "\n".join(lines)
    tool_context.state["final_document"] = markdown
    return markdown
