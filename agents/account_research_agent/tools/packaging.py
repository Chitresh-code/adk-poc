"""Assembles the final outreach packet from mapped signals and drafts."""

from __future__ import annotations

import json

from google.adk.tools import ToolContext


async def assemble_outreach_packet(tool_context: ToolContext) -> dict | str:
    """Builds the packaged markdown doc from state["mapped_signals"] and state["drafts"].

    Sets skip_summarization on every path so this becomes the chat's final
    response verbatim: the packaged packet is exactly what a rep would
    review before sending anything, not a paraphrase of it, and the LLM is
    forced to call this tool (see agent.py), which would otherwise force a
    second, pointless tool-call attempt on a follow-up summarization turn.

    Returns the markdown as a plain string on success, not wrapped in a
    dict: ADK's function-response handling only promotes a plain string
    verbatim into the turn's visible text part, a dict gets JSON-dumped
    instead, see google/adk/flows/llm_flows/functions.py.

    Returns:
        The markdown string, or a dict with "error" if a required pipeline
        step hasn't run yet.
    """
    tool_context.actions.skip_summarization = True

    mapped_signals = tool_context.state.get("mapped_signals")
    drafts = tool_context.state.get("drafts")
    if isinstance(drafts, dict):
        # draft's output_schema wraps the list (see schemas.OutreachDraftList);
        # normalize back to a plain list before use.
        drafts = drafts.get("items", [])
        tool_context.state["drafts"] = drafts
    if not mapped_signals:
        return {"error": "No mapped signals in state. Run buyer mapping first."}
    if not drafts:
        return {"error": "No drafts in state. Run draft first."}

    signals = json.loads(mapped_signals)
    drafts_by_account: dict[str, list[dict]] = {}
    for draft in drafts:
        drafts_by_account.setdefault(draft["account_id"], []).append(draft)

    lines = ["# Outreach Packet", ""]

    for signal in signals:
        account = signal.get("account")
        account_name = account["name"] if account else signal["account_id"]
        lines.append(f"## {account_name}")
        lines.append(f"*Signal: {signal['signal_type']}: {signal['detail']}*")
        lines.append("")

        account_drafts = drafts_by_account.get(signal["account_id"], [])
        if not account_drafts:
            lines.append("_No draft generated for this signal._")
            lines.append("")
            continue

        for draft in account_drafts:
            lines.append(f"### {draft['contact_name']} ({draft['contact_title']})")
            lines.append(f"**Subject:** {draft['subject']}")
            lines.append("")
            lines.append(draft["body"])
            lines.append("")
            lines.append(f"**Confidence:** {draft['confidence']}")
            if draft["needs_review"]:
                lines.append("**Needs review:** yes, no matching proof point in corpus")
            lines.append("")

    markdown = "\n".join(lines)
    tool_context.state["final_document"] = markdown
    return markdown
