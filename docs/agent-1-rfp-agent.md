# Agent 1: RFP / Security Questionnaire Agent

Demo narrative: hand it a whole RFP/security questionnaire, watch it read, decompose, retrieve,
draft, and route, live in `adk web`, question by question. The point isn't polish on any single
answer, it's showing the full chain running end to end with nothing hidden behind a single
"summarize this doc" call.

## Pipeline

A `SequentialAgent` (ADK's workflow agent for a fixed step order) with one `LlmAgent`/tool per
step. State moves between steps via ADK session state, so each step's output is visible in the
`adk web` trace, and that visibility is the demo.

1. **Intake** (`FunctionTool`): parse the uploaded file (`.docx`/`.xlsx`/`.pdf`/`.csv`) into raw
   text. Format detection by extension, nothing clever.
2. **Decompose** (`LlmAgent`): turn raw text into a structured list of discrete questions:
   `{id, question, section}`. RFPs are inconsistently formatted (numbered lists, tables, prose
   buried in a paragraph), so this is the step that's actually hard to fake with regex, and worth
   showing.
3. **Retrieve** (`FunctionTool`, called once per question): `search_corpus(query, k=3)` hits the
   local chromadb index of past answers and product docs, returns top-k snippets with source file
   names so every draft answer is traceable to something real.
4. **Draft** (`LlmAgent`): one answer per question, grounded only in retrieved snippets, each
   tagged with a confidence (`high`/`medium`/`low`) and a `needs_sme_review` flag when nothing in
   the corpus actually answers it. A confident answer with an empty source is the failure mode to
   guard against.
5. **Package** (`FunctionTool`): assemble everything into one markdown doc: per question, the
   draft, confidence, sources, and (for flagged ones) which team to route to, from a small
   static `category -> owner` map (security to "Security team", pricing to "Sales Ops", etc.).
   That routing map is a fixture, not a real Slack/Jira integration; say so if asked.

## Layout

```text
agents/rfp_agent/
  agent.py               # root_agent = SequentialAgent(sub_agents=[...])
  prompt.py               # instructions for the decompose + draft LlmAgents
  tools/
    intake.py             # parse_document()
    retrieval.py           # search_corpus(), chromadb PersistentClient
    packaging.py           # assemble_draft()
  data/
    corpus/                 # seed fixtures: past_answers/*.md, product_docs/*.md
    sample_rfp.docx          # seed input for the demo
    routing_map.json         # category -> owner
  .env.example
```

## Corpus seeding

If you don't hand me real past answers or product docs, I'll write a small fictional-product
corpus (roughly 15 to 20 short markdown files: a handful of past Q&A pairs plus product doc
snippets covering the usual RFP categories: security/compliance, data handling, SSO/auth,
uptime/SLA, pricing model). Good enough to make retrieval look sharp on a curated demo
questionnaire; not meant to survive contact with a real one.

## Demo script (rough)

1. Open `adk web`, select `rfp_agent`.
2. Upload/paste the sample questionnaire.
3. Narrate the trace as it runs: decomposed question list appears, then per-question retrieval
   hits with source citations, then drafts with confidence tags.
4. Point at one `needs_sme_review` flag, that's the "no customer-facing risk" pitch: the agent
   knows what it doesn't know and hands it off instead of guessing.
5. Show the final packaged markdown doc as the artifact presales would actually receive.

## Setup

```bash
cd agents/rfp_agent
uv sync
cp .env.example .env    # set GOOGLE_API_KEY
uv run adk web ../.. --port 8080 --reload_agents   # serves all agents/ subfolders
```

## Resolved

- Model: AI Studio Gemini key, see `plan.md` for the OpenAI-compatible fallback via LiteLLM.
- Demo content: fabricated corpus and sample questionnaire, since no real client material was
  handed off. Swap in real files under `data/` any time before the demo.
