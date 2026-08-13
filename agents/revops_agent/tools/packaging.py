"""Assembles the swept deals, duplicate accounts, forecast, and drafted
notes into one markdown report.
"""

from __future__ import annotations

import json

from google.adk.tools import ToolContext

_TIER_LABELS = {"commit": "Commit", "best_case": "Best case", "pipeline": "Pipeline"}


def _render_note(note: dict | None) -> list[str]:
    if note is None:
        return ["_No note drafted for this item._"]
    lines = [note["summary"], "", f"**Recommended fix:** {note['recommended_fix']}"]
    lines.append(f"**Confidence:** {note['confidence']}")
    if note["needs_review"]:
        lines.append("**Needs review:** yes, requires a human decision before acting")
    return lines


async def assemble_hygiene_report(tool_context: ToolContext) -> dict:
    """Builds the final markdown CRM hygiene and forecast report.

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

    swept_raw = tool_context.state.get("swept_deals")
    duplicate_pairs_raw = tool_context.state.get("duplicate_pairs")
    forecast_raw = tool_context.state.get("forecast")
    drafts = tool_context.state.get("drafts")
    if isinstance(drafts, dict):
        drafts = drafts.get("items", [])
        tool_context.state["drafts"] = drafts

    if not swept_raw or not forecast_raw:
        return {"error": "No swept deals or forecast in state. Run the sweep and forecast steps first."}

    swept = json.loads(swept_raw)
    duplicate_pairs = json.loads(duplicate_pairs_raw or "[]")
    forecast = json.loads(forecast_raw)
    notes_by_subject = {(d["subject_type"], d["subject_id"]): d for d in (drafts or [])}

    flagged_deals = [d for d in swept if d["issue_types"]]
    clean_deals = [d for d in swept if not d["issue_types"]]

    lines = ["# CRM Hygiene & Forecast Report", ""]

    lines.append("## Data quality issues")
    lines.append("")
    if not flagged_deals:
        lines.append("_No open deals with missing, stale, or stalled data this cycle._")
        lines.append("")
    for deal in flagged_deals:
        lines.append(f"### {deal['account_name']} - {deal['name']}")
        lines.extend(f"- {point}" for point in deal["rationale"])
        lines.append("")
        lines.extend(_render_note(notes_by_subject.get(("deal", deal["deal_id"]))))
        lines.append("")

    lines.append("## Possible duplicate accounts")
    lines.append("")
    if not duplicate_pairs:
        lines.append("_No possible duplicate accounts found this cycle._")
        lines.append("")
    for pair in duplicate_pairs:
        subject_id = f"{pair['account_id_a']}|{pair['account_id_b']}"
        lines.append(f"### {pair['account_name_a']} / {pair['account_name_b']}")
        lines.append(f"- Both accounts share the domain `{pair['domain']}`.")
        lines.append("")
        lines.extend(_render_note(notes_by_subject.get(("account_pair", subject_id))))
        lines.append("")

    lines.append("## Forecast: rep-submitted vs. sharpened")
    lines.append("")
    for tier, label in _TIER_LABELS.items():
        rep_amount = forecast["rep_totals"].get(tier, 0)
        sharpened_amount = forecast["sharpened_totals"].get(tier, 0)
        lines.append(f"- **{label}:** rep-submitted ${rep_amount:,} -> sharpened ${sharpened_amount:,}")
    unforecastable = forecast["unforecastable_deal_ids"]
    if unforecastable:
        lines.append(f"- **Unforecastable:** {len(unforecastable)} deal(s) missing amount or close date, excluded from the sharpened total.")
    lines.append("")

    lines.append("## Clean deals")
    lines.append("")
    if not clean_deals:
        lines.append("_No clean open deals this cycle._")
    for deal in clean_deals:
        lines.append(f"- {deal['account_name']} - {deal['name']}")

    markdown = "\n".join(lines)
    tool_context.state["final_document"] = markdown
    return {"markdown": markdown}
