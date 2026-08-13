"""Deterministic forecast sharpening: adjusts each open deal's forecast
category based on the hygiene flags from sweep_crm_hygiene, and compares the
rep-submitted total against the sharpened total per category.

Ordinary Python, not a model call, for the same reason as hygiene.py: a
forecast number needs to be reproducible from the same CRM snapshot, not a
model's best guess.
"""

from __future__ import annotations

import json

from google.adk.tools import ToolContext

_TIERS = ["commit", "best_case", "pipeline"]
_UNFORECASTABLE = "unforecastable"


def _sharpen_category(deal: dict) -> str:
    issue_types = deal["issue_types"]
    if "missing_fields" in issue_types and (deal.get("amount") is None or deal.get("close_date") is None):
        return _UNFORECASTABLE
    if "stale" in issue_types or "stalled" in issue_types:
        current = deal["forecast_category"]
        index = _TIERS.index(current) if current in _TIERS else len(_TIERS) - 1
        return _TIERS[min(index + 1, len(_TIERS) - 1)]
    return deal["forecast_category"]


def _totals(deals: list[dict], category_key: str) -> dict[str, int]:
    totals = {tier: 0 for tier in _TIERS}
    for deal in deals:
        category = deal[category_key]
        amount = deal.get("amount")
        if category in totals and amount is not None:
            totals[category] += amount
    return totals


async def sharpen_forecast(tool_context: ToolContext) -> dict:
    """Adjusts each open deal's forecast category and totals rep vs. sharpened.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.

    Returns:
        A dict with "deal_count", or "error" if state["swept_deals"] is
        missing (run sweep_crm_hygiene first).
    """
    tool_context.actions.skip_summarization = True

    swept_raw = tool_context.state.get("swept_deals")
    if not swept_raw:
        tool_context.state["forecast"] = json.dumps(
            {"deals": [], "rep_totals": {}, "sharpened_totals": {}, "unforecastable_deal_ids": []}
        )
        return {"error": "No swept deals in state. Run sweep_crm_hygiene first."}

    swept = json.loads(swept_raw)
    forecast_deals = []
    unforecastable_ids = []
    for deal in swept:
        sharpened = _sharpen_category(deal)
        if sharpened == _UNFORECASTABLE:
            unforecastable_ids.append(deal["deal_id"])
        forecast_deals.append(
            {
                "deal_id": deal["deal_id"],
                "account_name": deal["account_name"],
                "amount": deal.get("amount"),
                "forecast_category": deal["forecast_category"],
                "sharpened_category": sharpened,
            }
        )

    rep_totals = _totals(
        [{**d, "forecast_category": d["forecast_category"]} for d in forecast_deals], "forecast_category"
    )
    sharpened_totals = _totals(forecast_deals, "sharpened_category")

    forecast = {
        "deals": forecast_deals,
        "rep_totals": rep_totals,
        "sharpened_totals": sharpened_totals,
        "unforecastable_deal_ids": unforecastable_ids,
    }
    tool_context.state["forecast"] = json.dumps(forecast)
    return {"deal_count": len(forecast_deals)}
