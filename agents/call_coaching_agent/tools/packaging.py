"""Writes the coaching result back to the CRM (when a deal was matched and
the call is actually flagged) and assembles the final markdown report.

This is the one write in the whole pipeline: every step before this only
ever reads. Firestore collection names/project_id are imported from
revops_agent.tools.crm, same as tools/crm.py, so both agents agree on what
the CRM's deals collection is called.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from google.adk.tools import ToolContext

from revops_agent.tools.crm import DEALS_COLLECTION, project_id

CALL_COACHING_COLLECTION = "call_coaching_notes"

_FLAGGED_RISK_LEVELS = {"high", "medium"}


def _write_crm_update(analysis: dict, note: dict, transcript_text: str) -> str:
    """Writes a call_coaching_notes doc and updates the matched deal.

    Returns a short human-readable status line for the report; never
    raises, callers decide whether to attempt this at all.
    """
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return "CRM update skipped: FIRESTORE_EMULATOR_HOST is not set."

    from google.cloud import firestore

    now = datetime.now(timezone.utc)
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    client = firestore.Client(project=project_id())

    client.collection(CALL_COACHING_COLLECTION).document(call_id).set(
        {
            "call_id": call_id,
            "deal_id": analysis["matched_deal_id"],
            "account_id": analysis["matched_account_id"],
            "methodology_tier": analysis["methodology_tier"],
            "competitor_mentions": analysis["competitor_mentions"],
            "risk_level": analysis["risk_level"],
            "risk_rationale": analysis["risk_rationale"],
            "coaching_summary": note["summary"],
            "coaching_actions": note["coaching_actions"],
            "transcript_text": transcript_text,
            "coached_at": now.isoformat(),
        }
    )
    client.collection(DEALS_COLLECTION).document(analysis["matched_deal_id"]).update(
        {
            "last_call_risk_level": analysis["risk_level"],
            "last_call_summary": note["summary"],
            "last_coached_at": now.isoformat(),
        }
    )
    return (
        f"CRM updated: wrote {CALL_COACHING_COLLECTION}/{call_id} and set "
        f"{analysis['matched_account_name']}'s deal "
        f"{analysis['matched_deal_id']}'s last_call_risk_level to "
        f"{analysis['risk_level']!r}."
    )


def _render_markdown(analysis: dict, note: dict, source: str, crm_status: str) -> str:
    lines = ["# Call Coaching Report", "", f"**Source:** {source}", ""]

    lines.append("## Deal match")
    lines.append("")
    if analysis["matched_deal_id"]:
        lines.append(
            f"{analysis['matched_account_name']} - stage: {analysis['matched_deal_stage']} "
            f"(deal {analysis['matched_deal_id']})"
        )
    else:
        lines.append("_No CRM deal could be confidently matched to this call._")
    lines.append("")

    lines.append("## Methodology coverage (MEDDPICC)")
    lines.append("")
    lines.append(f"**Tier:** {analysis['methodology_tier']}")
    covered = ", ".join(analysis["elements_covered"]) or "none"
    missing = ", ".join(analysis["elements_missing"]) or "none"
    lines.append(f"- Covered: {covered}")
    lines.append(f"- Missing: {missing}")
    lines.append("")

    lines.append("## Competitor mentions")
    lines.append("")
    if analysis["competitor_mentions"]:
        lines.extend(f"- {name}" for name in analysis["competitor_mentions"])
    else:
        lines.append("_No competitors mentioned._")
    lines.append("")

    lines.append("## Deal risk")
    lines.append("")
    lines.append(f"**Risk level:** {analysis['risk_level']}")
    lines.append(analysis["risk_rationale"])
    lines.append("")

    lines.append("## Coaching note")
    lines.append("")
    lines.append(note["summary"])
    lines.append("")
    lines.append("**Recommended actions:**")
    for action in note["coaching_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    lines.append(f"**Confidence:** {note['confidence']}")
    if note["needs_review"]:
        lines.append("**Needs review:** yes, competitor mentioned, a manager should weigh in")
    lines.append("")

    lines.append("## CRM update")
    lines.append("")
    lines.append(crm_status)

    return "\n".join(lines)


async def update_crm_and_package(tool_context: ToolContext) -> dict:
    """Writes the CRM update (if warranted) and builds the final markdown report.

    Sets skip_summarization so the markdown reaches the chat pane verbatim
    instead of an LLM paraphrase of it, matching every other package step
    in this repo.

    Args:
        tool_context: injected by ADK, gives access to session state.

    Returns:
        A dict with "markdown", or "error" if a prior step's state is
        missing.
    """
    tool_context.actions.skip_summarization = True

    analysis = tool_context.state.get("analysis")
    note = tool_context.state.get("coaching_note")
    if not analysis or not note:
        return {"error": "No analysis or coaching note in state. Run the analyze and draft steps first."}

    transcript_text = tool_context.state.get("transcript_text", "")
    source = tool_context.state.get("call_source", "unknown")

    should_write = analysis["risk_level"] in _FLAGGED_RISK_LEVELS and analysis["matched_deal_id"]
    if should_write:
        crm_status = _write_crm_update(analysis, note, transcript_text)
    elif analysis["matched_deal_id"]:
        crm_status = "CRM update skipped: risk level is low, nothing to flag on the deal."
    else:
        crm_status = "CRM update skipped: no deal was matched to this call."

    markdown = _render_markdown(analysis, note, source, crm_status)
    tool_context.state["final_document"] = markdown
    return {"markdown": markdown}
