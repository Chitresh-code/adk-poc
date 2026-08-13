# ADK Agent Suite

A set of agents built on Google's Agent Development Kit (ADK), each one handling a specific piece of a go-to-market workflow:

- Reading and answering RFPs
- Researching accounts
- Watching for churn risk
- Keeping the CRM clean
- Coaching sales calls

Agents are added one at a time. See [`docs/plan.md`](docs/plan.md) for what's built, what's planned, and the architecture decisions that apply across all of them, [`docs/agent-1-rfp-agent.md`](docs/agent-1-rfp-agent.md) for how the RFP agent works, and [`docs/agent-2-account-research-agent.md`](docs/agent-2-account-research-agent.md) for the account research and outreach agent.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey), or an OpenAI-compatible endpoint (see [Model provider](#model-provider) below)
- The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) with the Pub/Sub emulator component, needed only for `account_research_agent` (its signal intake reads from a local emulator instead of a real event stream, see [`docs/agent-2-account-research-agent.md`](docs/agent-2-account-research-agent.md)): `brew install --cask google-cloud-sdk && gcloud components install pubsub-emulator`. The emulator is Java-based; run `java -version` first, macOS's bundled `java` is a stub, `brew install openjdk` if that fails.

## Setup

All agents share one environment: one `pyproject.toml`, one venv, one `.env`, all under `agents/`.

```bash
cd agents
uv sync --python 3.12
cp .env.example .env
```

Open `agents/.env` and set `GOOGLE_API_KEY`. Retrieval (corpus search) needs this key regardless of which model provider you pick, since embeddings always go through Gemini.

## Running the UI

```bash
cd agents
uv run adk web . --port 8080 --reload_agents
```

Open `http://localhost:8080`, pick an agent from the dropdown, and go from there. Each agent's own doc under `docs/` walks through what it does and how to try it.

## Pub/Sub emulator (account_research_agent only)

`account_research_agent`'s signal intake pulls from a local Pub/Sub emulator instead of a real event stream, see [`docs/agent-2-account-research-agent.md`](docs/agent-2-account-research-agent.md). It needs its own terminal, running alongside `adk web`:

```bash
export PATH="$HOME/google-cloud-sdk/bin:/opt/homebrew/opt/openjdk/bin:$PATH"   # if not already on PATH
gcloud beta emulators pubsub start --project=adk-poc-local --host-port=localhost:8085
```

The `beta` prefix is required on current `gcloud` versions; the non-beta `gcloud emulators` group only covers firestore and spanner. In a third terminal, with `PUBSUB_EMULATOR_HOST=localhost:8085` and `PUBSUB_PROJECT_ID=adk-poc-local` exported (see `agents/.env.example`), seed it with fake signals before asking the agent to check for new ones:

```bash
cd agents
uv run python account_research_agent/scripts/publish_fake_signals.py
```

## Model provider

Every agent reads its model through `agents/common/model.py`'s `get_model()`, controlled by `MODEL_PROVIDER` in `agents/.env`:

- `MODEL_PROVIDER=google` (default): Gemini via AI Studio, needs `GOOGLE_API_KEY`.
- `MODEL_PROVIDER=openai`: any ChatGPT-API-compatible endpoint via LiteLLM, needs `OPENAI_API_KEY` and optionally `OPENAI_MODEL` / `OPENAI_BASE_URL`.

See `agents/.env.example` for the full list of variables.

## How it's organized

- Each agent lives in its own folder under `agents/` with an `agent.py` that ADK's UI picks up automatically, so adding a new agent is just adding a new folder, no changes to how the UI runs.
- Agents don't call out to real external systems (CRM, ticketing, call recording); each one reads seeded local data from its own `data/` folder instead, so the whole suite runs standalone without any accounts or credentials beyond a model API key.

```text
agents/
  pyproject.toml, .venv/, .env       # shared across every agent
  common/
    model.py                         # get_model(), shared model access
    retrieval.py                     # shared chromadb helper
  rfp_agent/                         # see docs/agent-1-rfp-agent.md
  account_research_agent/            # see docs/agent-2-account-research-agent.md
  tests/                             # live end-to-end tests, one per agent, see Tests below
docs/
  plan.md                            # roadmap and architecture decisions
  agent-1-rfp-agent.md               # RFP agent design and walkthrough
  agent-2-account-research-agent.md  # account research agent design and walkthrough
```

## Tests

Two layers:

- **Deterministic tool logic** (parsing, assembly, mapping, no LLM call involved): each agent's own `tests/test_tools.py`. Run one directly, for example:

  ```bash
  cd agents
  uv run python rfp_agent/tests/test_tools.py
  ```

- **Live, end-to-end runs** against real APIs, real model calls included: `agents/tests/`, one `test_<agent>.py` per agent plus `run_all.py` to run every one and print a summary. These spend real quota (each full run is roughly 5 model calls) and, for `account_research_agent`, need a running Pub/Sub emulator; they skip cleanly instead of failing when a prerequisite isn't met. Not something to run on every save.

  ```bash
  cd agents
  uv run python tests/run_all.py            # everything
  uv run python tests/test_rfp_agent.py      # one agent
  ```
