# Agent 1: RFP / Security Questionnaire Agent

Give it a whole RFP or security questionnaire and it reads, decomposes, retrieves, drafts, and routes it end to end in `adk web`, question by question. Each step's output is visible in the trace rather than hidden behind a single summarize-this-document call, so the reasoning at each stage is inspectable, not just the final answer.

## Example

Paste or upload a questionnaire and the agent runs the full pipeline on it unattended:

- Question 1 of the sample questionnaire (`data/sample_rfp.md`) asks "Are you SOC 2 certified? If so, which trust principles are covered and can you provide the report?" Decompose tags that as category `security_compliance`, retrieve pulls the matching snippet from `data/corpus/past_answers/soc2.md` (a SOC 2 Type II report covering Security and Availability, not yet Confidentiality or Privacy), and draft turns that into a grounded answer tagged confidence `high` with that file listed as its source.
- Ask something the corpus doesn't cover, like an on-premise deployment option, and the draft comes back tagged confidence `low` with `needs_sme_review` set instead of an invented answer.

## Pipeline

A `SequentialAgent` (ADK's workflow agent for a fixed step order, see `plan.md` for why not the newer `Workflow` graph API) with one `LlmAgent` per step. State moves between steps via ADK session state, so each step's output is visible in the `adk web` trace.

- Three steps (intake, retrieve, package) are an `LlmAgent` that calls exactly one deterministic tool and nothing else. Each one forces that call via `generate_content_config`'s `tool_config` (`function_calling_config` mode `ANY`, which ADK maps to `tool_choice="required"` on OpenAI-compatible providers), instead of just asking for it in the instruction: a weaker or free model can otherwise respond in plain text and skip the call, which leaves the state key the next step's instruction depends on unset. Each of those three tools also sets `skip_summarization` on every return path, so a turn is always exactly one model call, forcing the tool never risks a second forced call looping on itself.
- Decompose and draft are pure structured-output LLM calls (`output_schema` + `output_key`, no tool).

1. **Intake** (`parse_document` tool): reads the questionnaire from the current chat turn, either an attached file (`.docx`/`.xlsx`/`.pdf`/`.csv`/`.txt`/`.md`, by MIME type) or text pasted directly, into raw text. Format detection by MIME type/extension, nothing clever.
2. **Decompose** (`LlmAgent`, structured output): turns raw text into a list of discrete questions: `{id, question, section, category}`. RFPs are inconsistently formatted (numbered lists, tables, prose burying a question in a paragraph), so this is the step that's actually hard to fake with regex.
3. **Retrieve** (`retrieve_context` tool): loops over every decomposed question and runs `search_corpus(query, k=3)` against the local chromadb index of past answers and product docs, attaching top-k snippets with source filenames to each question so every draft answer is traceable to something real.
4. **Draft** (`LlmAgent`, structured output): one answer per question in a single batched call, grounded only in that question's retrieved snippets, each tagged with a confidence (`high`/`medium`/`low`) and a `needs_sme_review` flag when nothing in the corpus actually answers it. A confident answer with an empty source is the failure mode this step guards against.
5. **Package** (`assemble_draft` tool): assembles everything into one markdown doc: per question, the draft, confidence, sources, and (for flagged ones) which team to route to, from a small static `category -> owner` map (`security_compliance`/`data_handling` to "Security team", `pricing` to "Sales Ops", etc., see `data/routing_map.json`). That routing map is a fixture, not a real Slack/Jira integration. This step sets ADK's `skip_summarization`, so the markdown reaches the chat pane verbatim instead of an LLM paraphrase of it, since the packaged doc is the deliverable.

## Layout

```text
agents/
  pyproject.toml, .venv/, .env         # shared across every agent, see plan.md
  rfp_agent/
    agent.py               # root_agent = SequentialAgent(sub_agents=[...])
    prompt.py                # instructions for the decompose + draft LlmAgents
    schemas.py                # Question, Draft pydantic models
    tools/
      intake.py               # parse_document()
      retrieval.py             # search_corpus(), retrieve_context(), chromadb PersistentClient
      packaging.py             # assemble_draft()
    data/
      corpus/                   # seed fixtures: past_answers/*.md, product_docs/*.md
      sample_rfp.md               # sample input to try the agent with
      routing_map.json             # category -> owner
    tests/
      test_tools.py                 # self-check for deterministic tool logic
```

## Corpus seeding

Shipped a fictional-product corpus for a product called "Northbound":

- 16 short markdown files under `data/corpus/`: 8 past Q&A pairs, 8 product doc snippets, covering the RFP categories used for routing (`security_compliance`, `data_handling`, `sso_auth`, `uptime_sla`, `pricing`).
- A 20-question sample questionnaire at `data/sample_rfp.md`.
- Two of its questions (on-premise deployment, carbon offset policy) are deliberately not covered by the corpus, so `needs_sme_review` has something real to fire on rather than only ever seeing happy-path questions.
- Good enough to make retrieval look sharp on this sample questionnaire; not meant to survive contact with a real one. Swap in real material under `data/` any time, no code changes needed.

## Try it out

1. Open `adk web`, select `rfp_agent`.
2. Upload or paste the sample questionnaire (`data/sample_rfp.md`).
3. Watch the trace as it runs: the decomposed question list appears, then retrieval attaches corpus snippets with source citations to every question, then drafts appear with confidence tags.
4. Questions 19 and 20 aren't covered by the corpus, so they come back tagged `needs_sme_review`: the agent knows what it doesn't know and hands it off instead of guessing.
5. The final packaged markdown doc is what presales would actually hand off to whoever owns the response.

## Setup

```bash
cd agents
uv sync --python 3.12
cp .env.example .env    # set GOOGLE_API_KEY
uv run adk web . --port 8080 --reload_agents   # serves every agents/ subfolder
```

## Verification status

Confirmed by running:

- Pipeline wiring imports cleanly against the installed `google-adk` 2.6.3 (sub-agent order, tool/output_key wiring, function-tool schema generation).
- The deterministic tool logic (file parsing per format, markdown assembly, routing lookup) passes `tests/test_tools.py`.
- A live end-to-end run against the sample questionnaire (`data/sample_rfp.md`) completed all five steps and produced a routed markdown draft with real Gemini calls at every step, including corpus retrieval.

That live run surfaced two real bugs, both fixed:

- chromadb's `GoogleGenerativeAiEmbeddingFunction` depended on the deprecated `google-generativeai` package, which isn't in `pyproject.toml`, so retrieval failed before ever reaching the corpus.
- The model name it was pinned to, `text-embedding-004`, no longer exists on the current API.

Retrieval now goes through chromadb's `GoogleGeminiEmbeddingFunction` (built on `google-genai`, already a dependency of `google-adk`, no new package needed), with the model configurable via `GOOGLE_EMBEDDING_MODEL` in `.env` (default `gemini-embedding-001`) instead of hardcoded, so a future model swap is a config change, not a code change.

Two more issues came up after that first live run, both addressed but not yet re-confirmed with a fresh end-to-end run (the Gemini free-tier quota below was exhausted by the time they were fixed):

- **429 quota errors on the Gemini path.** The AI Studio free tier caps `gemini-3.6-flash` (and likely other free-tier models) at 20 requests per day. A single questionnaire run through this pipeline uses roughly 8 to 10 requests, since each tool-using step calls the model twice: once to decide to call the tool, once to respond after. `get_model()` now attaches `retry_options` (`types.HttpRetryOptions`, 3 attempts, exponential backoff) to the Gemini model, which smooths over short-lived rate-limit bursts. It cannot fix a genuinely exhausted daily quota; a `429 RESOURCE_EXHAUSTED` that keeps recurring across retries means the quota, not a pipeline bug.
- **A weak or free chat model skipping the tool call entirely.** Tested against `MODEL_PROVIDER=openai` pointed at an OpenRouter free-tier model, intake never called `parse_document`, leaving `raw_text` unset in state and the decompose step's instruction template failing the same way the retrieval bug did. Fixed by forcing the tool call at the API level instead of relying on the model choosing to comply, see the Pipeline section above. That same debugging run also hit an unrelated `AuthenticationError` ("Missing Authentication header") from the OpenRouter endpoint, which looks like an account or key issue on the OpenRouter side rather than anything in this pipeline; worth checking `OPENAI_API_KEY` and `OPENAI_BASE_URL` in `.env` directly against OpenRouter before assuming the agent is at fault.
