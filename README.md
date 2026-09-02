# AidRadar

**An AI agent that finds government benefits you didn't know you qualified for.**

Over $60 billion in federal benefits go unclaimed every year — not because people don't need them, but because they don't know they exist or find the system too complex to navigate. AidRadar asks 10 plain-language questions about your household, cross-references your answers against 8 federal benefit programs across all 50 states using real policy microsimulation, and tells you exactly what you qualify for, how much you'd receive monthly, and where to apply.

Built with [Strands Agents SDK](https://github.com/strands-agents) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Track.

**Live demo:** [https://aid-radar.streamlit.app](https://aid-radar.streamlit.app)

---

## Architecture

[View Architecture Diagram](docs/architecture.html)

AidRadar is a **4-agent pipeline** where each agent has a single responsibility and no agent does more than it should:

```
User
 │
 ▼
[Intake Agent]         Conversational interview — extracts structured household profile
 │                     from natural language. No tools. Manages multi-turn dialogue,
 │                     handles corrections, confirms before proceeding.
 │
 ▼
[Pipeline]             Calls PolicyEngine directly (deterministic, no LLM).
 │                     Eligibility results are authoritative — never parsed from text.
 │
 ▼
[Eligibility Agent]    Receives PolicyEngine results in prompt. Tool: application_finder.
 │                     Decides which programs to look up (eligible only). Gets state-specific
 │                     URLs + required documents. Identifies cascading eligibility chains.
 │
 ▼
[Recommendation Agent] Tool: estimate_cliff_effect. Decides which eligible programs warrant
 │                     a cliff analysis (benefit ≥ $50/month). Calls PolicyEngine at
 │                     income + $500 to detect benefit cliffs. Renders plain-English report.
 │
 ▼
[Monitor Agent]        Tools: get_profile_history + check_policy_change. Calls history
                       to detect sustained trends vs one-time changes. Calls changelog
                       to determine if change was policy-driven or situation-driven.
                       Triggered by EventBridge on a schedule.
```

The pipeline (`src/pipeline/runner.py`) owns orchestration — agents never call each other directly. The What If simulator bypasses the LLM entirely and calls PolicyEngine directly for sub-second results.

---

## How It Works

### 1. Intake Agent
The user has a conversation with the Intake Agent. It asks about income, household composition, state of residence, age, disability status, veteran status, and citizenship. When it has enough information, it presents a structured summary and asks the user to confirm before proceeding.

**What makes it different:** The agent handles corrections mid-conversation ("actually I have 3 kids, not 2"), enforces hard stops for unsupported states rather than silently computing wrong results, and stores declined fields as `null`/`false` rather than ambiguous strings.

### 2. Eligibility Agent
The pipeline calls PolicyEngine directly first — deterministic, no LLM involved. The Eligibility Agent receives those results in its prompt and calls `application_finder` for each eligible program to get state-specific URLs and required documents. It decides which programs to look up (eligible programs only), identifies cascading eligibility chains, and builds structured output for the Recommendation Agent.

**Why this separation matters:** PolicyEngine results are authoritative and never parsed from LLM text. The agent does what LLMs are good at — synthesis, cascading logic, plain-English structuring — not math.

- **PolicyEngine** (pipeline, not agent) — Runs the household profile through [PolicyEngine](https://policyengine.org), an open-source tax and benefit microsimulation engine. Returns eligibility and estimated monthly benefit for all 8 programs in a single deterministic call.
- **`application_finder`** (agent tool) — Looks up state-specific application URLs, required documents, and deadlines from a curated JSON dataset.

Before PolicyEngine runs, `validate_profile` scrubs PII patterns (account numbers), normalizes state names ("California" → "CA"), bounds-checks income (≤ $500k/yr), and enforces household structure rules:

- **Adults=0 guard** — if all collected members are children (household size equals child count), the validator raises an error and the intake prompt catches this conversationally before it reaches the pipeline.
- **Elderly headcount check** — the intake now collects `elderly_count` (how many people in the household are 65+, not just yes/no). If `elderly_count > 0` and none of the listed adults are 65+, the validator checks that household size accounts for all elderly members. Fails with a user-friendly message if not.
- **Invalid state hard stop** — if the user's state is not a recognized US state code or name, validation raises `ProfileValidationError` immediately. The intake agent asks the user to clarify. No silent fallback, no wrong results.
- **Citizenship normalization** — free-text LLM output ("US citizen", "green card", "unauthorized") is mapped to canonical values (`us_citizen`, `permanent_resident`, `qualified_immigrant`, `undocumented`). Unrecognized values (DACA, refugee, TPS) default to `qualified_immigrant` — the broadest eligible non-citizen category — rather than `us_citizen`, avoiding false eligibility grants.
- **Child age clamping** — children from the `under_5` bucket are clamped to ages 0–4 and `K-12` children to 5–18, catching any intake agent misclassification before PolicyEngine sees the profile.
- **Flag wiring** — `has_disabled_member`, `has_pregnant_member`, and `elderly_count` are validated and passed through to PolicyEngine. `is_ssi_disabled` (required for SSI — `is_disabled` alone is not sufficient in PolicyEngine) is set alongside `is_disabled`. `is_pregnant` is set on the appropriate adult with an age guard (12–55). If `elderly_count > 0` but fewer than that many adults are 65+, the exact number of missing elderly members are injected as synthetic 70-year-olds — giving PolicyEngine the correct household size for FPL threshold calculation, not just a single placeholder.

If validation fails, the error surfaces to the user with a "Go Back and Correct" prompt rather than producing a wrong answer silently.

### 3. Recommendation Agent
Receives the structured eligibility output and renders the final report. Has one tool: `estimate_cliff_effect`. For eligible programs with a meaningful benefit (≥ $50/month), the agent decides whether to run a cliff analysis — calling PolicyEngine at income + $500 to check whether a small raise would eliminate the benefit. The agent makes this call per-program based on the household's income and benefit size.

The report includes:
- Programs you qualify for, with estimated monthly benefit
- Cliff effect warnings where relevant ("a $500/month raise may eliminate this benefit")
- Programs you don't qualify for, with a brief reason
- Documents you'll need to apply
- Cascading benefits (e.g., SNAP eligibility often unlocks free school meals)
- Direct application links

### 4. Monitor Agent
On a schedule (AWS EventBridge → Lambda), the system re-runs eligibility for saved profiles, diffs the new results against the stored DynamoDB snapshot, and passes the diff to the Monitor Agent. The agent has two tools:

- **`get_profile_history`** — fetches the last 3 eligibility snapshots from DynamoDB. Lets the agent distinguish a sustained trend (benefit declining across 3 checks) from a one-time fluctuation.
- **`check_policy_change`** — queries a curated policy changelog JSON for rule changes since the last check. Lets the agent determine whether an eligibility change was caused by a federal rule update (not the user's fault) vs. the user's situation changing (they may need to act). These produce fundamentally different notifications.

The agent only runs when there is an actual change; it does not send "nothing changed" noise.

### What If Simulator
The results page has income and household size sliders. Each slider change calls PolicyEngine directly (no LLM, no agent) and re-renders eligibility results in under a second. This lets users explore "what if I take a second job?" or "what if I have another child?" without re-running the full pipeline.

### Notification Preference (UI)
The results page includes a notification preference widget where users can register an email or phone number for change alerts. The preference is stored in session state — actual SNS delivery is a Stage 2 feature, but the UI and data model are in place.

---

## Programs Covered

| Program | What It Provides | States | Engine |
|---------|-----------------|--------|--------|
| SNAP | Monthly grocery funds on EBT card | All 50 states | PolicyEngine |
| Medicaid | Free/low-cost health coverage | All 50 states | PolicyEngine |
| WIC | Nutrition support for pregnant women & children under 5 | All 50 states | PolicyEngine |
| TANF | Temporary cash assistance for families | All 50 states | PolicyEngine |
| LIHEAP | Heating & cooling bill assistance | All 50 states | FPL threshold |
| Free School Meals | Free breakfast & lunch for K-12 | All 50 states | PolicyEngine |
| Lifeline | Phone/internet discount ($9.25/mo) | All 50 states | PolicyEngine |
| SSI | Monthly cash for elderly/disabled | All 50 states | PolicyEngine |

States: **All 50 US states** — state-specific application portals and program names included for every state.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | [Strands Agents SDK](https://github.com/strands-agents) (Python) |
| LLM (primary) | DeepSeek V3.2 via Amazon Bedrock Mantle (OpenAI-compatible endpoint) |
| LLM (fallback chain) | Amazon Nova Lite → xAI Grok 4.3 — automatic failover on 502/503 after retries |
| Eligibility engine | [PolicyEngine](https://policyengine.org) — open-source microsimulation |
| Frontend | Streamlit (hero, chat intake, results dashboard, What If simulator) |
| Storage | Amazon DynamoDB — household profiles + eligibility snapshots, 90-day TTL; table auto-created on first run if it doesn't exist |
| Scheduling | AWS EventBridge — triggers Monitor Agent on a recurring schedule |
| Validation | Custom guardrails layer (`profile_validator.py`) — PII scrubbing, state normalization, bounds checking |
| PDF generation | fpdf2 — branded PDF export of the full eligibility report |

---

## Project Structure

```
aid-radar/
├── main.py                         # CLI entry point
├── monitor_runner.py               # Monitor Agent Lambda/cron runner (EventBridge target)
├── src/
│   ├── app.py                      # Streamlit UI — hero, chat, results dashboard
│   ├── config.py                   # Mantle endpoint, Boto3 session factory
│   ├── agents/
│   │   ├── intake.py               # Intake Agent factory
│   │   ├── eligibility.py          # Eligibility Agent factory (tool-calling)
│   │   ├── recommendation.py       # Recommendation Agent factory
│   │   └── monitor.py              # Monitor Agent factory (narrative only)
│   ├── pipeline/
│   │   ├── runner.py               # run_pipeline(), run_whatif(), profile helpers
│   │   └── monitor_pipeline.py     # run_monitor_check(), _diff_snapshots()
│   ├── tools/
│   │   ├── eligibility_checker.py  # PolicyEngine-backed eligibility for all 8 programs
│   │   ├── application_finder.py   # State-specific URLs + required documents
│   │   ├── cliff_effect.py         # Benefit cliff detection (income + $500 scenario)
│   │   ├── profile_history.py      # Last 3 eligibility snapshots from DynamoDB
│   │   └── policy_change.py        # Policy changelog lookup (rule change vs situation change)
│   ├── db/
│   │   └── profile_store.py        # DynamoDB — save/load/update profiles + snapshots
│   ├── models/
│   │   └── eligibility_output.py   # Pydantic schema for eligibility agent structured output
│   ├── guardrails/
│   │   └── profile_validator.py    # Input validation, state normalization, PII scrubbing
│   ├── prompts/                    # Agent system prompts (txt files, one per agent)
│   └── data/
│       ├── programs/               # Per-program JSON (URLs, documents, state overrides)
│       └── policy_changelog.json   # Curated log of federal/state rule changes (used by check_policy_change)
├── tests/
│   ├── unit/                       # 115 unit tests — all dependencies mocked
│   │   ├── test_profile_validator.py
│   │   ├── test_profile_validator_extended.py
│   │   ├── test_eligibility_checker.py
│   │   ├── test_eligibility_output.py
│   │   ├── test_application_finder.py
│   │   ├── test_pipeline_runner.py
│   │   ├── test_monitor_pipeline.py
│   │   └── test_monitor_pipeline_extended.py
│   └── integration/                # 16 integration tests — real PolicyEngine + real DynamoDB
│       ├── test_eligibility_integration.py
│       └── test_profile_store_integration.py
├── evals/
│   └── evals.py                    # Eval suite — 10 household profiles × tool accuracy + agent quality
├── pyproject.toml
├── requirements.txt
└── .env                            # MANTLE_API_KEY, MODEL_ID, AWS_REGION
```

---

## Testing

AidRadar has three testing layers: unit tests, integration tests, and evals. Each layer serves a different purpose.

### Unit Tests — 115 tests, no external dependencies

All unit tests mock LLM calls, DynamoDB, and PolicyEngine. They run offline in under 10 seconds.

```bash
pytest tests/unit/ -v
```

| File | What it covers | Tests |
|------|---------------|-------|
| `test_profile_validator.py` | Valid profiles pass, invalid profiles raise typed errors, unsupported state raises | 11 |
| `test_profile_validator_extended.py` | Edge cases: non-list adults/children, household > 20, income bounds, PII scrubbing, state name normalization, citizenship normalization (DACA, refugee, green card), unsupported state raises | 22 |
| `test_eligibility_checker.py` | Tool return shape, program keys, error paths, validation integration, out-of-state returns error | 10 |
| `test_application_finder.py` | URL lookup, document list shape, unknown state/program handling | 6 |
| `test_pipeline_runner.py` | Pipeline orchestration: eligibility failure, timeout error, rec prompt includes eligibility_profile JSON, What If path, profile conversion | 13 |
| `test_monitor_pipeline.py` | `_diff_snapshots()`: gained, lost, changed, no-change, small-change threshold, missing programs | 8 |
| `test_monitor_pipeline_extended.py` | `run_monitor_check()`: eligibility failure → error, gained/lost triggers agent, DynamoDB update, income preservation, invalid state raises | 7 |
| `test_eligibility_output.py` | `parse_eligibility_output()`: valid fenced/bare JSON, missing fields, extra fields stripped, empty eligible programs, None benefit fields | 8 |
| `test_cliff_effect.py` | Cliff detection, no-cliff path, projected income calculation, invalid inputs, deep copy safety, unknown program_id | 8 |
| `test_policy_change.py` | Date filtering, ALL-states wildcard, state-specific matching, unknown program, invalid date format, empty program | 8 |
| `test_profile_history.py` | Returns current + history, empty history, profile not found, empty/None string guards, missing history key | 6 |

### Unit Test Coverage

Coverage on the testable logic modules (entrypoints and UI are excluded by design):

| Module | Coverage |
|--------|----------|
| `monitor_pipeline.py` | 98% |
| `application_finder.py` | 94% |
| `eligibility_checker.py` | 90% |
| `profile_validator.py` | 89% |
| `profile_store.py` | 80% |
| `pipeline/runner.py` | 76% (LLM call sites are intentionally uncoverable without live inference) |

> `app.py`, `main.py`, and `monitor_runner.py` are UI and entrypoint files — they depend on a running browser, live LLM, or AWS environment and are excluded from unit coverage targets. This is standard practice.

### Integration Tests — 16 tests, real PolicyEngine + real DynamoDB

Integration tests hit the real PolicyEngine microsimulation engine (no mocks). DynamoDB tests auto-skip if AWS credentials are not available.

```bash
# PolicyEngine integration (no AWS needed)
pytest tests/integration/test_eligibility_integration.py -v

# DynamoDB integration (requires AWS credentials)
pytest tests/integration/test_profile_store_integration.py -v

# All integration tests
pytest tests/integration/ -v
```

| File | What it covers |
|------|---------------|
| `test_eligibility_integration.py` | CA family qualifies for SNAP, TX high-income does not, FL elderly Medicaid present, all 8 program keys always returned, veteran flag propagated |
| `test_profile_store_integration.py` | Save profile returns ID, load returns saved data, snapshot included, update overwrites, nonexistent ID returns None, snapshot history appends, caps at 3, history key present |

### Evals — 10 household profiles

The eval suite (`evals/evals.py`) tests end-to-end accuracy against known expected outcomes. Each profile has a ground-truth set of programs it should and should not qualify for.

```bash
python -m evals.evals
```

Profiles tested (10 profiles × tool accuracy):
- CA low-income family (2 adults, 2 kids, $1,800/mo) — expects SNAP, Medicaid, WIC, free school meals, LIHEAP
- TX elderly disabled adult (68yo, $900/mo) — expects Medicaid, LIHEAP, Lifeline
- NY higher-income single ($4,500/mo) — expects ineligibility for most programs
- FL undocumented family — citizenship override blocks restricted programs
- NY pregnant low-income — expects WIC, Medicaid, SNAP
- CA veteran mid-income — veteran flag propagated, cliff effect tested
- TX large family (2 adults, 4 kids) — FPL shifts with household size
- FL single parent (2 school-age kids) — free school meals, no WIC
- NY near-threshold single — income at SNAP boundary
- CA mixed-citizenship household — qualified immigrant rules

Agent evals (6 evals):
1. **Intake Agent** — extracts complete profile, correct state and income values
2. **Eligibility Agent** — calls `application_finder` for eligible programs, does not call `eligibility_checker`
3. **Recommendation Agent** — mentions eligible programs, includes application guidance
4. **Recommendation Agent (cliff effect)** — cliff warning present for near-threshold profile
5. **Monitor Agent** — identifies gained programs, includes action guidance
6. **Monitor Agent (policy change)** — calls `check_policy_change`, references policy context in narrative

### Run all tests

```bash
# Unit only (fast, offline)
pytest tests/unit/ -v

# Integration (requires PolicyEngine install)
pytest tests/integration/ -v

# All tests + coverage report
pytest tests/ --cov=src --cov-report=term-missing -v
```

---

## Setup

```bash
# Clone the repo
git clone https://github.com/NithinBR-AI/aid-radar.git
cd aid-radar

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
AWS_REGION=us-east-1
AWS_PROFILE=personal
MANTLE_API_KEY=your-bedrock-mantle-api-key
MODEL_ID=deepseek.v3.2
EOF

# Run the Streamlit web app
streamlit run src/app.py

# Run the CLI pipeline (interactive intake)
python -m src.main

# Run unit tests
pytest tests/unit/ -v

# Run evals (10 profiles × tool accuracy + agent quality checks)
python -m evals.evals
```

---

## Model Access

AidRadar uses Amazon Bedrock Mantle's OpenAI-compatible endpoint (`/v1/chat/completions`). The Strands Agents SDK is configured with a custom base URL pointing at Mantle, making any Mantle-available model a drop-in replacement.

> Anthropic Claude models may be blocked on AISPL/India AWS accounts. DeepSeek V3.2 is the default — it handles tool calling reliably and is available without Marketplace subscriptions.

Models tested on Mantle:

| Model ID | Notes |
|----------|-------|
| `deepseek.v3.2` | Default — reliable tool calling |
| `deepseek.v3.1` | Previous version, also works |
| `google.gemma-3-12b-it` | Lighter, faster |
| `qwen.qwen3-235b-a22b-2507` | Largest, slowest |
| `mistral.mistral-large-3-675b-instruct` | Good instruction following |

---

## What's Next

### Stage 1 — Hackathon MVP (current)
- Streamlit UI, all 50 states, 8 federal programs
- DynamoDB profile store with 90-day TTL
- Monitor Agent with real PolicyEngine diff
- What If simulator for income/household exploration
- Mock notification preference UI (email/SMS) with session state storage
- 115 unit tests + 16 integration tests + 10-profile eval suite

### Stage 2 — Pilot Product
- React/Next.js frontend — mobile-first, accessible on low-end devices and slow connections (the population most likely to need these benefits)
- Real notifications — email/SMS delivery via Amazon SNS when the Monitor Agent detects eligibility changes (the UI and data model are already in place)
- User accounts — persistent profiles across sessions with opt-in notification preferences
- Expand to 10+ states, 15+ programs (CHIP, EITC, Section 8/HCV, utility disconnection protection)
- Caseworker dashboard — social workers manage multiple client profiles and track application status in bulk
- **Feedback loop** — thumbs up/down on eligibility results stored in DynamoDB; low-rated results flagged for human review and promoted to the eval suite; periodic re-evaluation measures whether prompt or data changes improved accuracy over time. Since PolicyEngine handles the eligibility math, improvement means better prompts, better application data, and better intake question clarity — not model fine-tuning.

### Stage 3 — Scale
- All 50 states
- Multilingual support — Spanish, Mandarin, Vietnamese (languages most common among eligible non-English speakers)
- Application assistance — pre-fill forms using the household profile collected during intake
- API layer for integration with government portals and nonprofit CRMs
- Anonymized aggregate data to help policymakers understand where benefits go unclaimed and why

### Data Architecture Evolution

Profiles and eligibility snapshots are stored as **native DynamoDB maps** (not JSON strings), making individual fields queryable without a full-table scan. This was a deliberate decision from day one — it unblocks Stage 2 features like querying all profiles in a given state, filtering by income range for the caseworker dashboard, and building aggregate policy insights without an ETL step.

| Stage | Storage | Rationale |
|-------|---------|-----------|
| 1 — MVP | DynamoDB (native maps, queryable fields) | Zero ops, pay-per-request, fits hackathon scale; native map storage avoids a migration wall later |
| 2 — Pilot | DynamoDB + PostgreSQL (RDS) | Postgres for user accounts, caseworker relationships, and application tracking; DynamoDB retained for ephemeral eligibility snapshots |
| 3 — Scale | PostgreSQL (primary) + DynamoDB (cache) + Redshift/Athena (analytics) | Full relational model for transactional data, separate analytics layer for policy insights and aggregate reporting |

---

## License

MIT

## Disclaimer

AidRadar provides estimates based on PolicyEngine's open-source microsimulation model and publicly available program data. Actual eligibility is determined by the administering agency. This tool is not a substitute for professional benefits counseling.
