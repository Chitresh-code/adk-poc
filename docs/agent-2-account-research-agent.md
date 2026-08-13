# Agent 2: Account Research & Outreach

Watches for buying signals on target accounts, researches each account against fixture CRM data and a product proof-point corpus, maps the signal to the right buyer personas, and drafts personalized outreach for a rep to review, never sends anything itself.

## Example

A rep opens `adk web`, selects `account_research_agent`, and asks it to check for new signals:

- "Check for new buying signals" pulls pending messages off the local Pub/Sub emulator topic. Say one comes back: `Meridian Health, job_posting, "VP of Platform Engineering" role opened`. Research looks up Meridian Health's fixture account record (industry: healthcare, segment: mid-market, no open deal) and pulls a matching case study snippet from the corpus (a healthcare customer's platform-migration story). Buyer mapping resolves `job_posting` to the `eng_leadership` persona and returns the two contacts at Meridian tagged with that role. Draft produces one outreach email per contact, grounded in the case study, with a short rationale for why this signal and this contact.
- A signal for an account with no matching corpus material (say a niche vertical Northbound has no case study for) still gets a draft, but flagged `needs_review` instead of citing a proof point that doesn't exist, the same honesty discipline Agent 1 uses when the RFP corpus doesn't cover a question.

## Pipeline

A `SequentialAgent` with one `LlmAgent` per step, the same shape as Agent 1: tool-only steps force their single call via `generate_content_config` (`function_calling_config` mode `ANY`) and set `skip_summarization` on every return path, so a weak model can't skip the call and a turn is never more than one model call. See [agent-1-rfp-agent.md](agent-1-rfp-agent.md#pipeline) for why that pattern exists; it isn't re-derived per agent.

1. **Signal intake** (`pull_signals` tool): pulls pending messages from the Pub/Sub emulator subscription that a separate fixture script publishes to (`{account_id, signal_type, detail, timestamp}`), acks them, and writes the normalized list to state.
2. **Account research** (`research_account` tool): for each signal, looks up the account's fixture CRM record (firmographic data, current deal stage if any) and runs the same chromadb semantic search Agent 1 uses, against a small corpus of product proof points and case studies, to find material relevant to that account's industry and the signal itself. No match means the next step gets told there's nothing to cite, not a made-up citation.
3. **Buyer mapping** (`map_buyers` tool): looks up the account's fixture contacts and filters them against a static `signal_type -> target_titles` map (the same pattern as Agent 1's `category -> owner` routing map), so a job-posting signal reaches engineering leadership and a funding-round signal reaches finance, not everyone at the account.
4. **Draft** (`LlmAgent`, structured output, no tool): one outreach draft per mapped contact, `{contact, subject, body, confidence, needs_review}`, grounded only in the retrieved proof point and the signal detail. This step has no send capability at all, by omission, not by a runtime check: there is no email or CRM-write tool defined anywhere in this agent, so nothing it produces can leave the draft stage without a human copying it out.
5. **Package** (`assemble_outreach_packet` tool): assembles the drafts for a signal batch into one markdown packet, grouped by account, for the rep to scan and approve.

## Layout

```text
agents/
  account_research_agent/
    agent.py                    # root_agent = SequentialAgent(sub_agents=[...])
    prompt.py                     # instructions for each step's LlmAgent
    schemas.py                     # OutreachDraft pydantic model
    tools/
      signals.py                    # pull_signals(), Pub/Sub emulator client
      research.py                    # research_account(), reuses Agent 1's chromadb pattern
      buyers.py                       # map_buyers()
      packaging.py                     # assemble_outreach_packet()
    data/
      fixtures/
        accounts.json                  # fictional target accounts
        contacts.json                   # contacts per account, with titles
      signal_category_map.json           # signal_type -> target_titles
      corpus/                             # case studies / proof points, chromadb-indexed
    scripts/
      publish_fake_signals.py             # publishes fake signal messages to the emulator topic
    tests/
      test_tools.py                        # self-check for deterministic tool logic
```

## Data and signal fixtures

- `data/fixtures/accounts.json`: a handful of fictional target accounts (industry, segment, current deal stage if any), continuing the "Northbound" product fiction from Agent 1's corpus.
- `data/fixtures/contacts.json`: two to four contacts per account with a title, so buyer mapping has real names and roles to filter against.
- `data/signal_category_map.json`: signal types (`job_posting`, `funding_round`, `executive_change`, `pricing_page_visit`, `competitor_mention`) mapped to the buyer personas each one should reach.
- `data/corpus/`: a small set of case-study and proof-point snippets, indexed the same way as Agent 1's `data/corpus/`, so draft answers cite something real instead of an invented customer story.
- `scripts/publish_fake_signals.py`: publishes a batch of fake signal messages to the Pub/Sub emulator topic, standing in for a real intent-data vendor per `docs/plan.md`. Docker Compose runs it automatically once per emulator lifecycle. The native workflow can still run it directly.

## Try it out

1. Run `docker compose up --build` from the repository root. Compose waits for the Pub/Sub emulator healthcheck, runs the one-shot signal seeder, and starts ADK after the seeder exits successfully.
2. Open `http://localhost:8080`, select `account_research_agent`, and ask: `Check for new buying signals and prepare the outreach packet.`
3. Watch the trace: five pulled signals, account research and proof-point matches, buyer mapping, one draft per matching contact, then the assembled packet.

`pull_signals` acknowledges every message it pulls, so the seeded batch is consumed in one run. Run `docker compose down` followed by `docker compose up --build` to recreate the in-memory emulator and automatically seed a fresh batch. Repeated `up` commands against the same emulator do not duplicate signals.

## Native setup

Docker users do not need the Google Cloud SDK or Java locally. For native development, install and run the emulator separately:

```bash
# once, for the emulator this agent needs. The emulator is Java-based and
# needs a real JRE on PATH; macOS's bundled `java` is a stub that only
# prompts to install one, check with `java -version` and `brew install
# openjdk` (add its bin dir to PATH, it's keg-only) if that fails.
gcloud components install pubsub-emulator
gcloud beta emulators pubsub start --project=adk-poc-local --host-port=localhost:8085

# in another terminal, pointed at the emulator
export PUBSUB_EMULATOR_HOST=localhost:8085
export PUBSUB_PROJECT_ID=adk-poc-local

# seed the native emulator before running the agent
cd agents
uv run python account_research_agent/scripts/publish_fake_signals.py
```

`google-cloud-pubsub` is a new dependency this agent adds to `agents/pyproject.toml`; nothing else in the shared environment changes.
