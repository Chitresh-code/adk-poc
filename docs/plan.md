# Roadmap and Architecture Decisions

Agents are built one at a time: each one has to actually work end to end in `adk web` before work starts on the next, so nothing gets parallelized until the current agent is solid.

## Agents

| # | Agent | What it does | Status |
|---|-------|---------------|--------|
| 1 | RFP / Security Questionnaire | Reads an incoming RFP or security questionnaire, breaks it into individual questions, and drafts grounded answers from past responses and product docs for presales to review. | **built, verified end to end against a live model call**, see [rfp-agent.md](rfp-agent.md) |
| 2 | Account Research & Outreach | Watches for buying signals, researches accounts, maps buyers, and drafts personalized outreach for a rep to approve before anything gets sent. | **built, Pub/Sub emulator round trip verified, live model run not yet verified**, see [account-research-agent.md](account-research-agent.md) |
| 3 | CS Churn & Expansion | Watches product usage, support tickets, and sentiment, flags churn risk early, and drafts QBR prep and cross-sell notes. | **built, verified end to end against a live model call**, see [churn-agent.md](churn-agent.md) |
| 4 | RevOps CRM Hygiene & Forecasting | Sweeps the CRM for missing, stale, or duplicate data, flags stalled deals, and sharpens the forecast, starting read-only and earning write access over time. | **built, verified end to end against a live model call and the Firestore emulator**, see [revops-agent.md](revops-agent.md) |
| 5 | Call Analysis & Coaching | Transcribes and scores sales calls against a methodology, surfaces competitor mentions and deal risks, and updates the CRM. | **built, verified end to end against a live model call, local Whisper transcription, and the Firestore emulator**, see [call-coaching-agent.md](call-coaching-agent.md) |

Each agent gets its own doc under `docs/` when its turn comes, following the same template as agent 1's.

## Decisions that apply to every agent

These are settled and shouldn't need re-deriving per agent; revisit only if a specific agent genuinely needs something different.

**Stack**:

- Python plus [`google-adk`](https://github.com/google/adk-python), served with [`adk web`](https://github.com/google/adk-web) for the UI.
- Python over Go/Java/TypeScript because it's what every `adk-samples` reference agent uses, which means less risk of hitting an undocumented corner while building.

**Model access**: Gemini via an AI Studio API key (`GOOGLE_API_KEY`) by default, one env var, no GCP project, billing, or IAM setup required. Every agent picks its model through one shared `get_model()` helper (`agents/common/model.py`) instead of hardcoding a model string, so the provider is a config switch, not a code change:

- `MODEL_PROVIDER=google` (default): plain Gemini model string (`gemini-2.5-flash`), reads `GOOGLE_API_KEY`. Move to real Vertex later with `GOOGLE_GENAI_USE_VERTEXAI=1` plus `GOOGLE_CLOUD_PROJECT`; ADK reads that itself, `get_model()` doesn't change.
- `MODEL_PROVIDER=openai`: routes through ADK's built-in [LiteLLM](https://adk.dev/agents/models/litellm/index.md) wrapper (`LiteLlm(model=f"openai/{OPENAI_MODEL}")`), which honors `OPENAI_API_KEY` and `OPENAI_BASE_URL`, so it works for real OpenAI or any ChatGPT-API-compatible endpoint (self-hosted, another vendor's compatible API) by pointing the base URL elsewhere. `litellm` is a dependency for this; nothing else in the pipeline cares which provider is live.

**Repo layout**:

- One `adk web` process serves every agent folder under `agents/`.
- `adk web` auto-discovers any subfolder with an `agent.py` exposing `root_agent`, so new agents just get dropped in as new folders with zero re-plumbing of the UI.
- One shared environment for all of them, not a `pyproject.toml`/venv per agent: `agents/pyproject.toml` holds every agent's dependencies, `agents/.venv` is the one venv, `agents/.env` is the one config file.
- ADK's dotenv loader walks up from `agents/<name>/` to find `.env`, so it's picked up automatically, no per-agent copy needed.
- One `uv sync`, one `.env` to fill in, nothing to keep in sync across folders.

```text
agents/
  pyproject.toml        # shared deps for every agent
  .venv/                 # shared venv (uv sync, run from agents/)
  .env                    # shared config, copy from .env.example
  common/
    model.py               # get_model(), shared across all agents
    retrieval.py             # shared chromadb helper, one collection per agent
  rfp_agent/
    agent.py                # root_agent = SequentialAgent(...)
    prompt.py
    schemas.py
    tools/
    data/
      corpus/                # seeded past-answers + product-doc fixtures
    tests/
      test_tools.py            # self-check for deterministic tool logic
  account_research_agent/
    agent.py                # same SequentialAgent shape, see agent-2 doc
    tools/
    data/
      fixtures/                # account/contact fixtures
      corpus/                   # case-study proof points, chromadb-indexed
    scripts/
      publish_fake_signals.py   # seeds the Pub/Sub emulator topic
    tests/
      test_tools.py
  churn_agent/
    agent.py                # same SequentialAgent shape, see agent-3 doc
    tools/
      scoring.py               # deterministic risk scoring, no model call
    data/
      fixtures/                # account/usage/ticket/sentiment fixtures
      corpus/                   # retention/expansion plays, chromadb-indexed
    tests/
      test_tools.py
  revops_agent/
    agent.py                # same SequentialAgent shape, see agent-4 doc
    tools/
      hygiene.py               # deterministic hygiene sweep, no model call
      forecast.py                # deterministic forecast sharpening, no model call
    data/
      seed/                     # account/deal fixtures loaded into Firestore
    scripts/
      seed_firestore.py          # loads the fixtures into the Firestore emulator
    tests/
      test_tools.py
  call_coaching_agent/
    agent.py                # same SequentialAgent shape, see agent-5 doc
    tools/
      intake.py                # load_call(), local faster-whisper transcription
      crm.py                     # load_deal_context(), reads revops_agent's Firestore collections
      packaging.py                # update_crm_and_package(), the pipeline's one write
    data/
      fixtures/                    # sample call transcripts, text only
    tests/
      test_tools.py
web/                     # branded frontend (vendored google/adk-web), see docs/web-ui.md
docs/
  plan.md                # this file
  rfp-agent.md
```

**Fixture data, not live SaaS integrations**:

- None of the agents get wired to a real Salesforce, Gong, Zendesk, or HubSpot instance; there isn't one to point at, and OAuth plumbing is a lot of work that buys nothing at this stage.
- Every agent reads seeded local fixtures (CSV/JSON/markdown) that look like CRM records, call transcripts, usage events, and so on, standing in for what a live integration would return.
- This is documented clearly rather than left for someone to assume it's live.
- Exception, not a contradiction: Agent 5's audio transcription is real, local model inference (faster-whisper, open Whisper weights), not a fixture standing in for one. What's still fixture data is the CRM it matches calls against and the sample call transcripts shipped in `data/`; no agent calls a hosted transcription API (Gong, Otter, or otherwise).

**Local Docker startup**:

- `docker compose up --build` builds ADK with its locked dependencies, loads API keys from the ignored `agents/.env` file at runtime, and serves the UI on port 8080.
- Compose waits for the Pub/Sub emulator healthcheck, runs a one-shot signal seeder, and starts ADK only after seeding succeeds. Automatic seeding runs once per emulator lifecycle so repeated startup does not duplicate signals.
- Build context excludes environment files, virtual environments, ADK session data, and chromadb indexes, so local secrets and runtime state are not copied into the image.

**Google Cloud emulators**: what's actually real, what's emulated, what's skipped. Gemini itself has no local emulator; every agent always calls the real API, that part can't be faked. Emulators only make sense for the infra around the model:

- **Firestore emulator** (`gcloud emulators firestore start`): stands in for the system of record starting at Agent 4 (RevOps CRM hygiene), where the read-only-then-write story is the whole point. Agent 3 can reuse it for account state if useful. Agent 5 reads the same collections Agent 4 seeds rather than standing up a second copy, and is the one that actually writes to a deal record, not just reads.
- **Pub/Sub emulator** (`gcloud beta emulators pubsub start`, still under the beta command track as of gcloud 580.0.0; needs a real Java 7+ JRE on `PATH`, macOS's bundled `java` stub doesn't count, `brew install openjdk` if `java -version` fails): stands in for a buying-signal event stream starting at Agent 2; a small local script publishes fake signals instead of a real intent-data vendor.
- **Agent 1 uses neither.** It's local files in, drafted answers out: no database, no message queue, no state that needs to survive between runs. That's not a gap to fill later, it's the correct amount of infra for what the agent does.

**Retrieval**:

- [chromadb](https://docs.trychroma.com/) running embedded/on-disk (`PersistentClient`, no server to stand up).
- Embeddings come from Gemini through chromadb's `GoogleGeminiEmbeddingFunction`, model configurable via `GOOGLE_EMBEDDING_MODEL` (defaults to `gemini-embedding-001`).
- First used by Agent 1's corpus search, reused by any later agent that needs semantic search over docs, tickets, or transcripts.
- Not Vertex AI Search or Vector Search: that's the right call for a real production system, not for a corpus of a few dozen documents; adding it later is a swap of one tool implementation, not a redesign.

**Workflow orchestration**: `SequentialAgent` (fixed step order, one `LlmAgent` per pipeline step).

- The installed `google-adk` (2.6.3) marks `SequentialAgent` deprecated in favor of a new graph-based `Workflow`/`Node` API (`google.adk.workflow`), built for durable, checkpointed, dynamically-scheduled execution.
- That's real capability but far more surface area than a fixed 5-step linear pipeline needs, and unlike `SequentialAgent` it isn't yet what `adk-samples` reference agents or the wider ADK docs demonstrate in depth.
- `SequentialAgent` still runs correctly; deprecated here means there's a newer tool, not that it's broken or scheduled for removal.
- Revisit if a later agent's step needs branching, retries, or a dynamic fan-out that `SequentialAgent` can't express.

## Setup (do this once)

Recommended Docker workflow:

```bash
cp agents/.env.example agents/.env    # fill in required API keys
docker compose up --build
```

Native workflow:

```bash
# uv, the package manager every adk-samples agent uses
curl -LsSf https://astral.sh/uv/install.sh | sh

# one shared environment for every agent
cd agents
uv sync --python 3.12
cp .env.example .env    # fill in GOOGLE_API_KEY

# Google Cloud SDK, only needed once we reach an agent that uses an emulator (Agent 2+)
brew install --cask google-cloud-sdk
gcloud components install cloud-firestore-emulator pubsub-emulator

# the Pub/Sub emulator is Java-based; macOS doesn't ship a real JRE by
# default, only a stub that prompts to install one
java -version || brew install openjdk
```
