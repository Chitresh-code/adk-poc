# ADK Demo: Build Plan

Client demo, one day out. Five agents pitched, one repo, built incrementally: agent 1 has to
actually work in `adk web` before any code for agent 2 gets written. Don't parallelize the build;
parallelize nothing until agent 1 demos clean.

## Order (per your framing)

| # | Agent | Proves | Status |
|---|-------|--------|--------|
| 1 | RFP / Security Questionnaire | multi-step agentic work, zero customer-facing risk | **building**, see [agent-1-rfp-agent.md](agent-1-rfp-agent.md) |
| 2 | Account Research & Outreach | research compression + human-on-the-send-button | not started |
| 3 | CS Churn & Expansion | continuous monitoring at a scale humans can't | not started |
| 4 | RevOps CRM Hygiene & Forecasting | read-only-first as the safe path to write access | not started |
| 5 | Call Analysis & Coaching | agent value depends on the human workflow around it | not started |

Each agent gets its own doc under `docs/` when its turn comes, following the same template as
agent 1's.

## Locked-in decisions (apply to every agent, so this isn't re-litigated each time)

**Stack**: Python plus [`google-adk`](https://github.com/google/adk-python), served with
[`adk web`](https://github.com/google/adk-web) for the UI. Python over Go/Java/TypeScript because
it's what every `adk-samples` reference agent uses: least risk of hitting an undocumented corner
the night before a demo.

**Model access**: Gemini via an AI Studio API key (`GOOGLE_API_KEY`) by default, one env var, no
GCP project, billing, or IAM setup required. Every agent picks its model through one shared
`get_model()` helper (`agents/common/model.py`) instead of hardcoding a model string, so the
provider is a config switch, not a code change:

- `MODEL_PROVIDER=google` (default): plain Gemini model string (`gemini-2.5-flash`), reads
  `GOOGLE_API_KEY`. Flip to real Vertex later with `GOOGLE_GENAI_USE_VERTEXAI=1` plus
  `GOOGLE_CLOUD_PROJECT`; ADK reads that itself, `get_model()` doesn't change.
- `MODEL_PROVIDER=openai`: routes through ADK's built-in [LiteLLM](https://adk.dev/agents/models/litellm/index.md)
  wrapper (`LiteLlm(model=f"openai/{OPENAI_MODEL}")`), which honors `OPENAI_API_KEY` and
  `OPENAI_BASE_URL`, so it works for real OpenAI or any ChatGPT-API-compatible endpoint
  (self-hosted, another vendor's compatible API) by pointing the base URL elsewhere. `litellm`
  gets added as a dependency for this; nothing else in the pipeline cares which provider is live.

**Repo layout**: one `adk web` process serves every agent folder under `agents/`. `adk web`
auto-discovers any subfolder with an `agent.py` exposing `root_agent`, so agents 2 to 5 just get
dropped in as new folders with zero re-plumbing of the UI:

```text
agents/
  common/
    model.py           # get_model(), shared across all agents
  rfp_agent/
    agent.py            # root_agent = SequentialAgent(...)
    prompt.py
    tools/
    data/
      corpus/            # seeded past-answers + product-doc fixtures
    .env.example
  (account_research_agent/, churn_agent/, revops_agent/, call_coaching_agent/: later)
docs/
  plan.md                # this file
  agent-1-rfp-agent.md
```

**Fixture data, not live SaaS integrations**: none of the five agents get wired to a real
Salesforce, Gong, Zendesk, or HubSpot instance for tomorrow; there isn't one to point at, and
OAuth plumbing is a day of work that buys nothing for a demo. Every agent reads seeded local
fixtures (CSV/JSON/markdown) that *look like* CRM records, call transcripts, usage events, and so
on. The pitch is "here's the reasoning and the workflow," not "here's a production integration."
Say so explicitly to the client rather than let them assume it's live.

**Google Cloud emulators: what's actually real, what's emulated, what's skipped**.
Gemini itself has no local emulator; every agent always calls the real API, that part can't be
faked. Emulators only make sense for the infra *around* the model:

- **Firestore emulator** (`gcloud emulators firestore start`): stands in for "the system of
  record" starting at Agent 4 (RevOps CRM hygiene), where the read-only-then-write story is the
  whole point. Agent 3 can reuse it for account state if useful.
- **Pub/Sub emulator** (`gcloud emulators pubsub start`): stands in for a "buying signal" event
  stream starting at Agent 2; a small local script publishes fake signals instead of a real
  intent-data vendor.
- **Agent 1 uses neither.** It's local files in, drafted answers out: no database, no message
  queue, no state that needs to survive between demo runs. That's not a gap to fill later, it's
  the correct amount of infra for what the agent does, and it doubles as part of the "zero
  customer-facing risk" pitch.

**Retrieval**: [chromadb](https://docs.trychroma.com/) running embedded/on-disk (`PersistentClient`,
no server to stand up), embeddings from Gemini's `text-embedding-004`. First used by Agent 1's
corpus search, reused by any later agent that needs semantic search over docs, tickets, or
transcripts. Not Vertex AI Search or Vector Search: that's the right call for a real product, not
for a demo corpus of a few dozen documents; adding it later is a swap of one tool implementation,
not a redesign.

## Setup (do this once)

```bash
# uv, the package manager every adk-samples agent uses
curl -LsSf https://astral.sh/uv/install.sh | sh

# Google Cloud SDK, only needed once we reach an agent that uses an emulator (Agent 2+)
brew install --cask google-cloud-sdk
gcloud components install cloud-firestore-emulator pubsub-emulator
```

## Resolved

- Model: AI Studio Gemini key by default, OpenAI-compatible endpoint via LiteLLM as a swappable
  alternative (see above). Need from you: drop a `GOOGLE_API_KEY` into `agents/rfp_agent/.env`
  before running (get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).
- Demo content: fabricated. Agent 1 ships with a fictional-product corpus and sample
  questionnaire so building isn't blocked on real client material; swap in real files under
  `agents/rfp_agent/data/` any time before the demo, no code changes needed.
