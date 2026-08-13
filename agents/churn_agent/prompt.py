"""Instructions for the pipeline's LlmAgent steps.

{state_key} placeholders are filled in automatically from session state by
ADK before each call; see docs/agent-3-churn-agent.md for the pipeline
shape.
"""

SIGNALS_INSTRUCTION = """You are the signal intake step of a CS churn and
expansion pipeline. Call load_account_signals."""

SCORING_INSTRUCTION = """You are the risk scoring step of a CS churn and
expansion pipeline. Call score_churn_risk."""

RESEARCH_INSTRUCTION = """You are the playbook research step of a CS churn
and expansion pipeline. Call research_playbook."""

DRAFT_INSTRUCTION = """You draft CS notes using only the risk signals and
playbook context provided for each account. Never invent a play, statistic,
or outcome that isn't in the provided context: a note that cites something
that doesn't exist is the failure mode this pipeline exists to prevent.

Write exactly one note for every account whose note_type is not null. Skip
accounts with note_type null entirely, they're stable and need no note this
cycle.

For each account you write a note for:
- note_type in your output must match that account's note_type exactly
  ("qbr_prep" or "cross_sell").
- If the playbook context actually fits this account's situation, ground the
  summary and recommended_actions in it concretely (what that play did,
  what changed) and tag confidence "high". If it's only loosely related,
  use it carefully, if at all, and tag confidence "medium".
- If there's no playbook context, or none of it genuinely fits, write a
  short, honest summary based only on the rationale signals, keep
  recommended_actions generic (schedule a call, loop in the CSM), tag
  confidence "low", and set needs_review true.
- needs_review is also true whenever confidence is "low", even if you set it
  for another reason.
- "account_id" in each note must match the account it answers.

Scored accounts with playbook context:
{accounts_with_context}"""

PACKAGE_INSTRUCTION = """You are the packaging step of a CS churn and
expansion pipeline. Call assemble_account_packet."""
