"""Assembles the final account health packet from scored accounts and drafts."""

from __future__ import annotations

import json

from google.adk.tools import ToolContext

_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


def _render_account(account: dict, note: dict | None, heading: str) -> list[str]:
    lines = [f"### {heading}"]
    for point in account["rationale"]:
        lines.append(f"- {point}")
    lines.append("")
    if note is None:
        lines.append("_No draft generated for this account._")
    else:
        lines.append(note["summary"])
        lines.append("")
        lines.append("**Recommended actions:**")
        for action in note["recommended_actions"]:
            lines.append(f"- {action}")
        lines.append("")
        lines.append(f"**Confidence:** {note['confidence']}")
        if note["needs_review"]:
            lines.append("**Needs review:** yes, no matching playbook material in corpus")
    lines.append("")
    return lines


async def assemble_account_packet(tool_context: ToolContext) -> dict | str:
    """Builds the packaged markdown doc from state["scored_accounts"] and state["drafts"].

    Sets skip_summarization on every path so this becomes the chat's final
    response verbatim: the packaged packet is exactly what a CSM would
    review before acting on it, not a paraphrase of it, and the LLM is
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

    scored_raw = tool_context.state.get("scored_accounts")
    drafts = tool_context.state.get("drafts")
    if isinstance(drafts, dict):
        # draft's output_schema wraps the list (see schemas.AccountNoteList);
        # normalize back to a plain list before use.
        drafts = drafts.get("items", [])
        tool_context.state["drafts"] = drafts
    if not scored_raw:
        return {"error": "No scored accounts in state. Run risk scoring first."}

    scored = json.loads(scored_raw)
    notes_by_account = {d["account_id"]: d for d in (drafts or [])}

    at_risk = sorted(
        (a for a in scored if a["note_type"] == "qbr_prep"),
        key=lambda a: _RISK_ORDER[a["risk_tier"]],
    )
    expansion = [a for a in scored if a["note_type"] == "cross_sell"]
    stable = [a for a in scored if a["note_type"] is None]

    lines = ["# Account Health Packet", "", "## At risk: QBR prep", ""]
    if not at_risk:
        lines.append("_No accounts flagged at risk this cycle._")
        lines.append("")
    for account in at_risk:
        heading = f"{account['name']} (risk: {account['risk_tier']})"
        lines.extend(_render_account(account, notes_by_account.get(account["account_id"]), heading))

    lines.append("## Expansion candidates: cross-sell")
    lines.append("")
    if not expansion:
        lines.append("_No expansion candidates this cycle._")
        lines.append("")
    for account in expansion:
        lines.extend(_render_account(account, notes_by_account.get(account["account_id"]), account["name"]))

    lines.append("## Stable: no action needed")
    lines.append("")
    if not stable:
        lines.append("_Every watched account is flagged this cycle._")
    for account in stable:
        lines.append(f"- {account['name']}")
    lines.append("")

    markdown = "\n".join(lines)
    tool_context.state["final_document"] = markdown
    return markdown
