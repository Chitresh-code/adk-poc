# ADK Agent Suite

A set of agents built on Google's Agent Development Kit (ADK), each one handling a specific piece of a go-to-market workflow:

- Reading and answering RFPs
- Researching accounts
- Watching for churn risk
- Keeping the CRM clean
- Coaching sales calls

Agents are added one at a time. See [`docs/plan.md`](docs/plan.md) for what's built, what's planned, and the architecture decisions that apply across all of them, and [`docs/agent-1-rfp-agent.md`](docs/agent-1-rfp-agent.md) for how the first one, the RFP agent, actually works.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey), or an OpenAI-compatible endpoint (see [Model provider](#model-provider) below)

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
  pyproject.toml, .venv/, .env   # shared across every agent
  common/
    model.py                     # get_model(), shared model access
  rfp_agent/                     # the RFP agent, see docs/agent-1-rfp-agent.md
docs/
  plan.md                        # roadmap and architecture decisions
  agent-1-rfp-agent.md           # RFP agent design and walkthrough
```

## Tests

Each agent's deterministic tool logic, the parsing and assembly code that isn't an LLM call, has a self-check under `tests/`. Run one directly, for example:

```bash
cd agents
uv run python rfp_agent/tests/test_tools.py
```
