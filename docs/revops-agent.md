# Agent 4: RevOps CRM Hygiene & Forecasting

Sweeps the CRM for deals with missing fields, stale activity, or a stalled stage, flags accounts that look like duplicates, sharpens the sales forecast against those signals, and drafts recommended fixes for a RevOps manager to review. Read-only: it only ever reads from the CRM, it never edits or merges a record itself.

## Example

A RevOps manager opens `adk web`, selects `revops_agent`, and asks it to sweep the CRM:

- "Sweep the CRM for hygiene issues and sharpen the forecast" reads every account and open deal from the fixture CRM data. Pinecrest Robotics' renewal is missing both an amount and a close date, so hygiene flags it `missing_fields` and forecast marks it `unforecastable`, excluded from the sharpened total until a rep fills those in.
- Fernwood Capital's add-on deal has sat in the `proposal` stage for 50 days against a 25-day threshold for that stage, so hygiene flags it `stalled`, and forecast downgrades its category from the rep's `best_case` to `pipeline`.
- Brightline Logistics' upsell deal has had no activity in 35 days against a 21-day threshold, so hygiene flags it `stale`, and forecast downgrades it from `commit` to `best_case`.
- "Meridian Health" and "Meridian Healthcare Group" turn out to share the same domain, so hygiene flags them as a possible duplicate account pair. The draft step recommends which one looks like the primary record and asks a human to confirm and merge, `needs_review` is always true here: merging accounts is a data-integrity decision, not something this pipeline decides on its own.
- Meridian Health's own expansion deal and Solace Media's renewal have no issues at all and show up in the final report's clean section with no note: not every deal needs a fix.

## Pipeline

A `SequentialAgent` with one `LlmAgent` per step, the same shape as Agents 1 through 3: tool-only steps force their single call via `generate_content_config` (`function_calling_config` mode `ANY`) and set `skip_summarization` on every return path, so a weak model can't skip the call and a turn is never more than one model call. See [rfp-agent.md](rfp-agent.md#pipeline) for why that pattern exists; it isn't re-derived per agent.

1. **CRM read** (`load_crm_records` tool): reads every account and open deal from the local Firestore emulator and joins each deal to its account's name, industry, and segment.
2. **Hygiene sweep** (`sweep_crm_hygiene` tool): ordinary Python, not a model call, for the same reason Agent 3's risk scoring is: hygiene flags need to be explainable and reproducible from the same CRM snapshot every run. Only open deals are swept, closed ones are done and flagging them would be noise. A deal is `missing_fields` when its amount, close date, or next step is unset; `stale` when its last activity is older than 21 days; `stalled` when it's been in its current stage longer than that stage's threshold (21 days for discovery and qualification, 25 for proposal, 20 for negotiation). Separately, any two accounts that share a normalized domain are flagged as a possible duplicate pair, an account-level issue kept apart from deal-level flags so a duplicate account's otherwise-clean deals don't get miscategorized.
3. **Forecast sharpening** (`sharpen_forecast` tool): also deterministic. A deal missing its amount or close date becomes `unforecastable`, excluded from any total. A stale or stalled deal gets its forecast category downgraded one tier (`commit` to `best_case`, `best_case` to `pipeline`). Everything else keeps the rep's own category. The step totals both the rep-submitted and the sharpened numbers per category so the gap is visible, not just the sharpened result on its own.
4. **Draft** (`LlmAgent`, structured output): one note per flagged deal and one per duplicate account pair, grounded only in that item's own hygiene rationale. Deal notes get a concrete, specific ask, high confidence, and `needs_review` false: these are data-entry or follow-up asks, not judgment calls. Duplicate-pair notes always get `needs_review` true, matching the read-only design: the pipeline can point at two accounts that look like the same company, but only a human confirms and merges them.
5. **Package** (`assemble_hygiene_report` tool): assembles the swept deals, duplicate pairs, forecast totals, and drafted notes into one markdown report with four sections: data quality issues, possible duplicate accounts, forecast (rep-submitted vs. sharpened per category), and clean deals. This step sets ADK's `skip_summarization`, so the markdown reaches the chat pane verbatim instead of an LLM paraphrase of it.

## Layout

```text
agents/
  revops_agent/
    agent.py                    # root_agent = SequentialAgent(sub_agents=[...])
    prompt.py                     # instructions for each step's LlmAgent
    schemas.py                     # HygieneNote pydantic model
    tools/
      crm.py                        # load_crm_records(), Firestore emulator client
      hygiene.py                     # sweep_crm_hygiene(), deterministic, no model call
      forecast.py                     # sharpen_forecast(), deterministic, no model call
      packaging.py                     # assemble_hygiene_report()
    data/
      seed/
        accounts.json                  # fixture accounts, one is a deliberate duplicate
        deals.json                      # fixture deals, day-offsets not absolute dates
    scripts/
      seed_firestore.py                 # loads the fixtures into the Firestore emulator
    tests/
      test_tools.py                      # self-check for deterministic tool logic
```

## Data and CRM fixtures

- `data/seed/accounts.json`: six accounts continuing the "Northbound" product fiction from Agents 2 and 3, reusing the same five account IDs and names, plus a sixth, "Meridian Healthcare Group", that shares Meridian Health's domain on purpose so duplicate detection has something real to catch.
- `data/seed/deals.json`: seven deals, one per account plus a closed one, engineered so each open deal hits exactly one branch of the hygiene and forecast logic: clean, missing fields, stalled, stale, and the duplicate account's own otherwise-clean deal. Dates are stored as day-offsets from seed time (`stage_entered_days_ago`, `last_activity_days_ago`, `close_date_days_from_now`), not fixed calendar dates, so the staleness and stalled-stage math stays correct no matter when the fixtures are seeded.
- `scripts/seed_firestore.py`: converts those offsets into absolute timestamps and loads both collections into the Firestore emulator, overwriting on every run so the demo data always matches what the design doc describes. Docker Compose runs it automatically before starting ADK.

## Try it out

1. Run `docker compose up --build` from the repository root. Compose waits for the Firestore emulator healthcheck, runs the one-shot CRM seeder, and starts ADK after the seeder exits successfully.
2. Open `http://localhost:8080`, select `revops_agent`, and ask: `Sweep the CRM for hygiene issues and sharpen the forecast.`
3. Watch the trace: CRM records read, hygiene flags with their rationale, forecast categories sharpened against those flags, one note per flagged item, then the assembled report.
4. The Meridian duplicate pair comes back tagged `needs_review`: the agent points at the problem and hands the merge decision to a human instead of acting on it.

`load_crm_records` only ever reads; run `docker compose down` followed by `docker compose up --build` to reset the emulator and reseed the same fixtures from scratch.

## Native setup

Docker users do not need the Google Cloud SDK or Java locally. For native development, install and run the emulator separately:

```bash
# once, for the emulator this agent needs. The emulator is Java-based and
# needs a real JRE on PATH; macOS's bundled `java` is a stub that only
# prompts to install one, check with `java -version` and `brew install
# openjdk` (add its bin dir to PATH, it's keg-only) if that fails.
gcloud components install cloud-firestore-emulator
gcloud emulators firestore start --project=adk-poc-local --host-port=localhost:8090

# in another terminal, pointed at the emulator
export FIRESTORE_EMULATOR_HOST=localhost:8090
export FIRESTORE_PROJECT_ID=adk-poc-local

# seed the native emulator before running the agent
cd agents
uv run python revops_agent/scripts/seed_firestore.py
```

`google-cloud-firestore` is a new dependency this agent adds to `agents/pyproject.toml`; nothing else in the shared environment changes.
