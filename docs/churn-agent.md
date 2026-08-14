# Agent 3: CS Churn & Expansion

Watches product usage, open support tickets, and sentiment across accounts, flags churn risk early using deterministic scoring rules (not a model call), and drafts grounded QBR prep notes for at-risk accounts and cross-sell notes for expansion candidates, for a CSM to review before acting.

## Example

A CSM opens `adk web`, selects `churn_agent`, and asks it to check account health:

- "Check account health and prepare QBR and cross-sell notes" pulls this cycle's fixture usage, ticket, and sentiment data for every tracked account. Meridian Health's monthly active users dropped 39% and it has an open critical ticket about a failing nightly data sync, so scoring tags it risk `high`. Research finds a matching retention play (a healthcare account saved from a near-identical sync failure), and draft writes a QBR prep note grounded in that play, tagged confidence `high`.
- Pinecrest Robotics shows the same shape of decline (usage down, an open high-severity ticket), but its industry has no matching retention play in the corpus. The draft still gets written, but with a generic recommendation and `needs_review` set instead of an invented play, the same honesty discipline Agents 1 and 2 use when their corpora don't cover something.
- Brightline Logistics has no risk signals at all: usage grew 37% with no open tickets and positive sentiment. Scoring tags it as an expansion candidate instead, and draft writes a cross-sell note grounded in a logistics upsell play.
- Solace Media's usage, tickets, and sentiment are all flat and unremarkable. Scoring flags nothing for it, and it shows up in the final packet's "stable" list with no note at all: not every watched account needs a draft.

## Pipeline

A `SequentialAgent` with one `LlmAgent` per step, the same shape as Agents 1 and 2: tool-only steps force their single call via `generate_content_config` (`function_calling_config` mode `ANY`) and set `skip_summarization` on every return path, so a weak model can't skip the call and a turn is never more than one model call. See [rfp-agent.md](rfp-agent.md#pipeline) for why that pattern exists; it isn't re-derived per agent.

1. **Signal intake** (`load_account_signals` tool): reads this agent's own fixture account, usage, ticket, and sentiment data and joins them into one record per account.
2. **Risk scoring** (`score_churn_risk` tool): ordinary Python, not a model call. An account is `high` risk when usage declined 15%+ *and* it has an open critical/high ticket or negative sentiment; `medium` when exactly one of those three signals fires on its own; `low` otherwise. A `low`-risk account with 15%+ usage growth and no negative signal is an expansion candidate. High/medium risk gets routed to a QBR-prep note, expansion candidates to a cross-sell note, and everything else gets no note at all. Scoring stays deterministic and reproducible from the same fixture data every run, which is the point of doing it in code instead of asking a model to eyeball it.
3. **Playbook research** (`research_playbook` tool): for every account flagged in step 2, runs `search_corpus(query, k=2)` against a local chromadb index of retention and expansion plays, the same chromadb helper Agent 1 and Agent 2 use (`common/retrieval.py`), pointed at this agent's own corpus. Unflagged accounts pass through with empty context.
4. **Draft** (`LlmAgent`, structured output): one note per flagged account, grounded only in its retrieved playbook context, tagged confidence (`high`/`medium`/`low`) and a `needs_review` flag when nothing in the corpus actually supports it. Unflagged accounts are skipped entirely by instruction, not by a runtime filter.
5. **Package** (`assemble_account_packet` tool): assembles the scored accounts and their notes into one markdown packet with three sections: at-risk accounts (sorted by risk tier) with QBR prep notes, expansion candidates with cross-sell notes, and stable accounts listed with no note. This step sets ADK's `skip_summarization`, so the markdown reaches the chat pane verbatim instead of an LLM paraphrase of it.

## Layout

```text
agents/
  churn_agent/
    agent.py                    # root_agent = SequentialAgent(sub_agents=[...])
    prompt.py                     # instructions for each step's LlmAgent
    schemas.py                     # AccountNote pydantic model
    tools/
      signals.py                    # load_account_signals()
      scoring.py                     # score_churn_risk(), deterministic, no model call
      research.py                     # research_playbook(), reuses common/retrieval.py
      packaging.py                     # assemble_account_packet()
    data/
      fixtures/
        accounts.json                  # tracked accounts (industry, segment, ARR, CSM owner)
        usage.json                      # monthly active users, prior vs. current period
        tickets.json                     # open/closed support tickets per account
        sentiment.json                    # sentiment score, trend, and a CSM note per account
      corpus/
        retention_plays/                  # case studies and playbooks for at-risk accounts
        expansion_plays/                   # case studies and playbooks for expansion candidates
    tests/
      test_tools.py                        # self-check for deterministic tool logic
```

## Data and playbook fixtures

- `data/fixtures/accounts.json`: five accounts continuing the "Northbound" product fiction from Agents 1 and 2, reusing the same account IDs and names as Agent 2's target accounts, now modeled as existing paying customers.
- `data/fixtures/usage.json`, `tickets.json`, `sentiment.json`: monthly active users, open and closed support tickets, and a sentiment score/trend/note per account, joined by `account_id` in the signal intake step.
- `data/corpus/retention_plays/` and `data/corpus/expansion_plays/`: seven markdown case studies and playbooks, indexed the same way as Agent 1's and Agent 2's corpora. Healthcare, financial services, and logistics scenarios are deliberately covered; the fixture data's one robotics manufacturing account is deliberately not, so `needs_review` has something real to fire on rather than only ever seeing happy-path accounts.

## Try it out

1. Open `adk web`, select `churn_agent`.
2. Ask: `Check account health and prepare QBR and cross-sell notes.`
3. Watch the trace: joined account signals appear, then risk tiers with their rationale, then playbook context attached to every flagged account, then notes with confidence tags.
4. Pinecrest Robotics comes back tagged `needs_review`: the agent knows what it doesn't know and hands it off instead of guessing.
5. The final packaged markdown groups accounts into at-risk, expansion, and stable sections, the same triage a CSM would want before their next round of QBRs.

## Setup

No new dependency and no emulator: this agent reads local JSON fixtures the same way Agent 1 reads its corpus, and reuses the already-shared `common/retrieval.py` for playbook search.

```bash
cd agents
uv sync --python 3.12
cp .env.example .env    # set GOOGLE_API_KEY
uv run adk web . --port 8080 --reload_agents   # serves every agents/ subfolder
```
