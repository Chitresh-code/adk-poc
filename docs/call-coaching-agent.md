# Agent 5: Call Analysis & Coaching Agent

Takes one sales call, transcribing audio locally when needed, scores it against a MEDDPICC-style
methodology, surfaces competitor mentions and deal risk, and, when the call is on a deal it can
confidently identify and comes back flagged, writes a coaching summary back to the CRM. The first
agent in this suite that writes: every step before the package step only ever reads.

## Example

A rep pastes, uploads, or records the call for `adk web` to review:

- Pinecrest Robotics' renewal call (`data/fixtures/pinecrest_robotics_negotiation_call.md`) covers
  nearly every methodology element well: quantified time savings, an engaged economic buyer, a
  clear decision process, and the rep proactively addressing a competitor by name. Analysis tags
  it `methodology_tier: strong`, but the prospect is comparing the renewal price against Vantage
  Ops, so `risk_level` still comes back `high`: strong coverage doesn't protect a late-stage deal
  from a competitor in the room. The coaching note gets `needs_review: true`, a competitive threat
  is a judgment call for a manager, not a data fact.
- Brightline Logistics' call (`data/fixtures/brightline_logistics_negotiation_call.md`) is thin: no
  economic buyer, no decision process, no metrics, and the prospect mentions they're also
  evaluating Vantage Ops. `methodology_tier: weak` plus a competitor mention in a negotiation-stage
  deal is also `risk_level: high`, for a different, coaching-relevant reason than Pinecrest's.
- Meridian Health's call (`data/fixtures/meridian_health_negotiation_call.md`) covers pain, metrics,
  the economic buyer, and the paper process with no competitor mentioned: `methodology_tier: strong`,
  `risk_level: medium`, `needs_review: false`. The coaching note is a concrete, objective ask, not a
  judgment call, so the CRM update goes through without a human gate.

## Pipeline

A `SequentialAgent` with one `LlmAgent` per step, the same shape as Agents 1 through 4: tool-only
steps force their single call via `generate_content_config` (`function_calling_config` mode `ANY`)
and set `skip_summarization` on every return path. See
[rfp-agent.md](rfp-agent.md#pipeline) for why that pattern exists; it isn't re-derived per agent.

1. **Intake** (`load_call` tool): reads the call from the current chat turn, one of three ways,
   converging on the same plain transcript text regardless of which: an attached audio file,
   transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (an
   open-weight Whisper reimplementation, no cloud speech API, no audio ever leaves the machine
   running the agent); an attached transcript file (`.txt`/`.md`); or text pasted directly into
   the chat. Same MIME-type dispatch pattern as `rfp_agent`'s intake step.
2. **Deal context** (`load_deal_context` tool): reads every account and deal from the same
   Firestore emulator `revops_agent` uses (see [revops-agent.md](revops-agent.md)), reusing that
   agent's collection names and `project_id()` instead of redefining them, so the two agents can't
   drift apart on what the CRM's collections are called. Builds the candidate deal list the next
   step matches the call against.
3. **Analyze** (`LlmAgent`, structured output): grounded only in the transcript and the candidate
   deals, this is the step doing the actual scoring. Unlike Agent 3's risk scoring or Agent 4's
   hygiene sweep, this can't be deterministic Python: the input is free-form call text, not
   structured fixture facts, so identifying which deal the call is about, and how well it covers
   eight MEDDPICC elements (metrics, economic buyer, decision criteria, decision process, paper
   process, pain, champion, competition), requires actually reading the transcript. Coverage of 6
   or more elements is `methodology_tier: strong`, 4 to 5 is `adequate`, 3 or fewer is `weak`.
   Competitor names actually said in the call are collected separately from methodology coverage,
   a call can address competition well and still have a competitor in it. `risk_level` combines
   the matched deal's stage with methodology tier and competitor mentions: weak coverage or a
   competitor mention in a `proposal`/`negotiation` deal is `high`; the same in an earlier-stage
   deal, or without a stage at all, is `medium`; otherwise `low`.
4. **Draft** (`LlmAgent`, structured output): one coaching note, grounded only in the prior step's
   structured analysis, never the raw transcript again. `needs_review` is true whenever the
   analysis has a competitor mention (a qualitative call a manager should weigh in on) and false
   otherwise (a methodology gap alone is a concrete, objective coaching ask), the same
   objective-fix-versus-human-judgment split `revops_agent`'s deal notes versus duplicate-account
   notes already use.
5. **CRM update and package** (`update_crm_and_package` tool): the one write in the pipeline. If
   the call matched a real deal and came back `risk_level` `high` or `medium`, this writes a
   `call_coaching_notes` document and updates that deal's `last_call_risk_level` /
   `last_call_summary` / `last_coached_at` fields. A `low`-risk call, or one that couldn't be
   confidently matched to a deal, gets a report with no CRM write, stated plainly in the report
   rather than silently skipped. This step also assembles the final markdown report and sets
   `skip_summarization`, so it reaches the chat pane verbatim.

## Layout

```text
agents/
  call_coaching_agent/
    agent.py                    # root_agent = SequentialAgent(sub_agents=[...])
    prompt.py                     # instructions for each step's LlmAgent
    schemas.py                     # CallAnalysis, CoachingNote pydantic models
    tools/
      intake.py                     # load_call(), MIME dispatch, local faster-whisper transcription
      crm.py                          # load_deal_context(), reads revops_agent's Firestore collections
      packaging.py                     # update_crm_and_package(), the pipeline's one write
    data/
      fixtures/                          # sample call transcripts to paste or attach, text only
    tests/
      test_tools.py                        # self-check for deterministic tool logic
```

## Data and call fixtures

- `data/fixtures/`: five short fictional call transcripts continuing the "Northbound" product
  fiction and the Meridian/Brightline/Fernwood/Pinecrest/Solace accounts from Agents 3 and 4, one
  per methodology/competitor/risk combination: strong coverage with no competitor, weak coverage
  with a competitor, adequate coverage with no competitor, weak coverage at an earlier deal stage,
  and strong coverage with a competitor anyway.
- Text only, no audio fixtures: real sales-call recordings freely licensed for redistribution
  turned out not to exist (real speaker audio and real deal specifics, checked before assuming
  otherwise), and generating synthetic audio added work without adding anything the transcript
  fixtures don't already cover. The audio-upload path itself is real, working code, exercised in
  `agents/tests/test_call_coaching_agent.py` against a locally synthesized clip; bring your own
  recording to try it against something the repo didn't script.
- This agent doesn't seed its own copy of the CRM: it reads the same `revops_accounts` /
  `revops_deals` collections `revops_agent` seeds (see [revops-agent.md](revops-agent.md)), since
  Firestore is this repo's one shared CRM system of record from Agent 4 onward, not a per-agent
  fixture store.

## Try it out

1. Run `docker compose up --build` from the repository root. Compose seeds the same Firestore CRM
   `revops_agent` uses before starting ADK; this agent reads that data as-is, nothing extra to seed.
2. Open `http://localhost:8080`, select `call_coaching_agent`.
3. Paste the contents of one of `data/fixtures/*.md`, or attach it as a file, or attach your own
   short audio recording of a call.
4. Watch the trace: the transcript (or transcription) is read, the CRM's open deals are loaded,
   the methodology and risk analysis appears, then the coaching note, then the final report.
5. For a call that matches a real deal and comes back flagged, the report's last section confirms
   the CRM write; open `revops_agent` afterward and sweep the CRM again to see the updated deal.

## Native setup

Uses the same Firestore emulator as `revops_agent`; see
[revops-agent.md](revops-agent.md#native-setup) for how to start and seed it, nothing agent-specific
to add there.

`faster-whisper` downloads its model weights from Hugging Face on first use (a few hundred MB for
the default `base` model), then caches them under `~/.cache/huggingface`; every run after the
first works offline. Set `WHISPER_MODEL_SIZE` in `agents/.env` to trade accuracy for speed
(`tiny`, `base`, `small`, `medium`, `large-v3`); `base` is the default. Runs on CPU with `int8`
quantization, no GPU required, and needs no system `ffmpeg` install, decoding goes through the
`av` package's bundled libraries.
