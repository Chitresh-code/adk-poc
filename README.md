# ADK Agent Suite

A set of agents built on Google's Agent Development Kit (ADK), each one handling a specific piece of a go-to-market workflow:

- Reading and answering RFPs
- Researching accounts
- Watching for churn risk
- Keeping the CRM clean
- Coaching sales calls

Agents are added one at a time. See [`docs/plan.md`](docs/plan.md) for what's built, what's planned, and the architecture decisions that apply across all of them, [`docs/rfp-agent.md`](docs/rfp-agent.md) for how the RFP agent works, [`docs/account-research-agent.md`](docs/account-research-agent.md) for the account research and outreach agent, [`docs/churn-agent.md`](docs/churn-agent.md) for the CS churn and expansion agent, [`docs/revops-agent.md`](docs/revops-agent.md) for the RevOps CRM hygiene and forecasting agent, and [`docs/call-coaching-agent.md`](docs/call-coaching-agent.md) for the call analysis and coaching agent.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) for the recommended Docker workflow
- A Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey), required for corpus embeddings even when chat uses an OpenAI-compatible endpoint (see [Model provider](#model-provider) below)
- [`uv`](https://docs.astral.sh/uv/) and the Google Cloud SDK are needed only for the native workflow below

## Docker setup

Create the shared environment file once and fill in the required API keys:

```bash
cp agents/.env.example agents/.env
```

Then start everything:

```bash
docker compose up --build
```

Open `http://localhost:8080`. Compose starts the Pub/Sub and Firestore emulators, waits for both to become healthy, seeds the fixture buying signals and CRM records once per emulator lifecycle, and starts ADK only after both seeders succeed. API keys are loaded from `agents/.env` at container runtime; the file, local virtual environments, ADK session data, and chromadb indexes are excluded from the image. `call_coaching_agent`'s local Whisper model downloads from Hugging Face the first time you attach audio in a given container, so that first transcription needs outbound network access; the cache isn't persisted across `docker compose down`, so a fresh container re-downloads it once.

The account research agent acknowledges the five signals when it processes them. To recreate the in-memory emulator and automatically seed a fresh batch:

```bash
docker compose down
docker compose up --build
```

## Native setup

All agents share one environment: one `pyproject.toml`, one venv, one `.env`, all under `agents/`.

```bash
cd agents
uv sync --python 3.12
cp .env.example .env
```

Open `agents/.env` and set `GOOGLE_API_KEY`. Retrieval (corpus search) needs this key regardless of which model provider you pick, since embeddings always go through Gemini.

### Running the UI

```bash
cd agents
uv run adk web . --port 8080 --reload_agents
```

Open `http://localhost:8080`, pick an agent from the dropdown, and go from there. Each agent's own doc under `docs/` walks through what it does and how to try it.

### Emulators (native workflow only)

Docker Compose starts and seeds every emulator automatically; these are only needed when running
`adk web` natively.

#### Pub/Sub emulator (account_research_agent only)

`account_research_agent`'s signal intake pulls from a local Pub/Sub emulator instead of a real event stream, see [`docs/account-research-agent.md`](docs/account-research-agent.md). It needs its own terminal, running alongside `adk web`:

```bash
export PATH="$HOME/google-cloud-sdk/bin:/opt/homebrew/opt/openjdk/bin:$PATH"   # if not already on PATH
gcloud beta emulators pubsub start --project=adk-poc-local --host-port=localhost:8085
```

The `beta` prefix is required on current `gcloud` versions; the non-beta `gcloud emulators` group only covers firestore and spanner. In a third terminal, with `PUBSUB_EMULATOR_HOST=localhost:8085` and `PUBSUB_PROJECT_ID=adk-poc-local` exported (see `agents/.env.example`), seed it with fake signals before asking the agent to check for new ones:

```bash
cd agents
uv run python account_research_agent/scripts/publish_fake_signals.py
```

#### Firestore emulator (revops_agent and call_coaching_agent)

`revops_agent`'s CRM read step reads from a local Firestore emulator instead of a real CRM, see [`docs/revops-agent.md`](docs/revops-agent.md). `call_coaching_agent` reads and writes the same collections, matching calls against the same CRM data instead of seeding a second copy, see [`docs/call-coaching-agent.md`](docs/call-coaching-agent.md). It needs its own terminal, running alongside `adk web`:

```bash
export PATH="$HOME/google-cloud-sdk/bin:/opt/homebrew/opt/openjdk/bin:$PATH"   # if not already on PATH
gcloud emulators firestore start --project=adk-poc-local --host-port=localhost:8090
```

In a third terminal, with `FIRESTORE_EMULATOR_HOST=localhost:8090` and `FIRESTORE_PROJECT_ID=adk-poc-local` exported (see `agents/.env.example`), seed it with the fixture accounts and deals before asking the agent to sweep the CRM:

```bash
cd agents
uv run python revops_agent/scripts/seed_firestore.py
```

## Model provider

Every agent reads its model through `agents/common/model.py`'s `get_model()`, controlled by `MODEL_PROVIDER` in `agents/.env`:

- `MODEL_PROVIDER=google` (default): Gemini via AI Studio, needs `GOOGLE_API_KEY`.
- `MODEL_PROVIDER=openai`: any ChatGPT-API-compatible endpoint via LiteLLM, needs `OPENAI_API_KEY` and optionally `OPENAI_MODEL` / `OPENAI_BASE_URL`.

See `agents/.env.example` for the full list of variables.

## How it's organized

- Each agent lives in its own folder under `agents/` with an `agent.py` that ADK's UI picks up automatically, so adding a new agent is just adding a new folder, no changes to how the UI runs.
- Agents don't call out to real external SaaS systems (CRM, ticketing, call recording); each one reads seeded local data from its own `data/` folder instead, so the whole suite runs standalone without any accounts or credentials beyond a model API key. `call_coaching_agent`'s audio transcription is the one exception worth naming: it's real local model inference (faster-whisper), not a fixture, but it's local, not a hosted transcription API.

```text
agents/
  pyproject.toml, .venv/, .env       # shared across every agent
  common/
    model.py                         # get_model(), shared model access
    retrieval.py                     # shared chromadb helper
  rfp_agent/                         # see docs/rfp-agent.md
  account_research_agent/            # see docs/account-research-agent.md
  churn_agent/                       # see docs/churn-agent.md
  revops_agent/                      # see docs/revops-agent.md
  call_coaching_agent/               # see docs/call-coaching-agent.md
  tests/                             # live end-to-end tests, one per agent, see Tests below
docs/
  plan.md                     # roadmap and architecture decisions
  rfp-agent.md                # RFP agent design and walkthrough
  account-research-agent.md   # account research agent design and walkthrough
  churn-agent.md              # CS churn and expansion agent design and walkthrough
  revops-agent.md             # RevOps CRM hygiene and forecasting agent design and walkthrough
  call-coaching-agent.md      # call analysis and coaching agent design and walkthrough
```

## Tests

Two layers:

- **Deterministic tool logic** (parsing, assembly, mapping, no LLM call involved): each agent's own `tests/test_tools.py`. Run one directly, for example:

  ```bash
  cd agents
  uv run python rfp_agent/tests/test_tools.py
  ```

- **Live, end-to-end runs** against real APIs, real model calls included: `agents/tests/`, one `test_<agent>.py` per agent plus `run_all.py` to run every one and print a summary. These spend real quota (most full runs are roughly 5 model calls; `call_coaching_agent`'s is 2) and need a running Pub/Sub emulator (`account_research_agent`) or Firestore emulator (`revops_agent`, `call_coaching_agent`); they skip cleanly instead of failing when a prerequisite isn't met. `call_coaching_agent`'s test also runs a real local Whisper transcription (no API key needed for that part) if a `say`-style TTS command is available to synthesize a throwaway clip. Not something to run on every save.

  ```bash
  cd agents
  uv run python tests/run_all.py            # everything
  uv run python tests/test_rfp_agent.py      # one agent
  ```
