# AidRadar

**An AI agent that finds government benefits you didn't know you qualified for.**

Over $60 billion in federal benefits go unclaimed every year — not because people don't need them, but because they don't know they exist. AidRadar asks 10 simple questions about your household, cross-references your answers against 8 federal benefit programs across 4 states, and tells you exactly what you qualify for, how much you'd receive, and how to apply.

Built with [Strands Agents SDK](https://github.com/strands-agents) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Track.

## Architecture

[View Architecture Diagram](docs/architecture.html)

## How It Works

1. **Intake Agent** — Conversational interview collects household details (income, size, state, age, etc.)
2. **Eligibility Agent** — Calls the eligibility_checker tool (PolicyEngine) to evaluate all 8 programs, then calls application_finder for each eligible program to get URLs and documents
3. **Recommendation Agent** — Generates an actionable, 6th-grade reading level report: eligible programs, estimated monthly benefit, documents needed, cascading benefits, and direct application links
4. **Monitor Agent** — Runs on a schedule (AWS EventBridge), loads your saved profile from DynamoDB, re-runs PolicyEngine, diffs the new results against your stored snapshot, and notifies you only when eligibility actually changes — without you doing anything
5. **What If Simulator** — Sliders on the results page let you explore how income or household size changes would affect your eligibility, using the same real PolicyEngine calculation with no LLM involved


## Programs Covered

| Program | What It Provides | Engine |
|---------|-----------------|--------|
| SNAP (Food Stamps) | Monthly grocery funds on EBT card | PolicyEngine |
| Medicaid | Free/low-cost health coverage | PolicyEngine |
| WIC | Nutrition support for pregnant women & children under 5 | PolicyEngine |
| TANF | Temporary cash assistance for families | PolicyEngine |
| LIHEAP | Heating & cooling bill assistance | FPL fallback |
| Free School Meals | Free breakfast & lunch for K-12 students | PolicyEngine |
| Lifeline | Phone/internet discount ($9.25/mo) | PolicyEngine |
| SSI | Monthly cash for disabled/elderly | PolicyEngine |

## States Supported

California, Texas, New York, Florida (covering ~100M people)

## Tech Stack

- **Agent Framework**: Strands Agents SDK (Python)
- **LLM**: DeepSeek V3.2 via Amazon Bedrock Mantle (OpenAI-compatible endpoint)
- **Eligibility Engine**: [PolicyEngine](https://policyengine.org) (open-source tax & benefit microsimulation)
- **Frontend**: Streamlit (hero landing, chat intake, results dashboard, monitor demo)
- **Data**: Application URLs and document requirements (JSON), PolicyEngine for eligibility math
- **Storage**: Amazon DynamoDB (household profiles + eligibility snapshots, 90-day TTL)
- **Monitoring**: AWS EventBridge (scheduled Monitor Agent runs)

## Project Structure

```
aid-radar/
├── main.py                         # CLI entry point
├── monitor_runner.py               # Monitor Agent cron runner (EventBridge target)
├── src/
│   ├── app.py                      # Streamlit UI — hero, chat, results dashboard (UI only)
│   ├── main.py                     # CLI pipeline logic
│   ├── config.py                   # Mantle endpoint, Boto3 session factory
│   ├── agents/
│   │   ├── intake.py               # Intake Agent (conversational, no tools)
│   │   ├── eligibility.py          # Eligibility Agent (eligibility_checker + application_finder)
│   │   ├── recommendation.py       # Recommendation Agent (report generation, no tools)
│   │   └── monitor.py              # Monitor Agent (narrative only, no tools)
│   ├── pipeline/
│   │   ├── runner.py               # run_pipeline(), run_whatif(), profile conversion helpers
│   │   └── monitor_pipeline.py     # run_monitor_check(), snapshot diff logic
│   ├── tools/
│   │   ├── eligibility_checker.py  # PolicyEngine-backed eligibility for all 8 programs
│   │   └── application_finder.py   # State-specific application URLs and documents
│   ├── db/
│   │   └── profile_store.py        # DynamoDB — save/load/update profiles + snapshots
│   ├── guardrails/
│   │   └── profile_validator.py    # Input validation, state normalization, PII scrubbing
│   ├── prompts/                    # Agent system prompts (txt files)
│   ├── data/
│   │   └── programs/               # Per-program JSON (URLs, documents, state overrides)
│   └── config/                     # Reference YAML configs (programs, states, monitor schedule)
├── evals/
│   └── evals.py                    # 10-profile eval suite (tool accuracy + 3 agent quality evals)
├── pyproject.toml
├── requirements.txt
└── .env                            # MANTLE_API_KEY, MODEL_ID, AWS_REGION
```

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

# Run evals (10 profiles × tool accuracy + 3 agent quality checks)
python -m evals.evals
```

## Model Access

AidRadar uses Amazon Bedrock Mantle's OpenAI-compatible endpoint (`/v1/chat/completions`). Anthropic Claude models are available in Mantle but may be blocked on AISPL/India AWS accounts. DeepSeek V3.2 is the current default — it handles tool calling reliably and is available without Marketplace subscriptions.

Available models tested on Mantle:
- `deepseek.v3.2` (current default)
- `deepseek.v3.1`
- `google.gemma-3-12b-it`
- `qwen.qwen3-235b-a22b-2507`
- `mistral.mistral-large-3-675b-instruct`

## What's Next

AidRadar was built for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon but the problem it solves is real and ongoing.

### Stage 1 — Hackathon MVP (current)
- Streamlit UI, 4 states, 8 federal programs
- DynamoDB profile store with 90-day TTL
- Monitor Agent with real PolicyEngine diff
- What If simulator for income/household exploration

### Stage 2 — Pilot Product
- React/Next.js frontend — mobile-first, accessible on low-end devices and slow connections (the population most likely to need these benefits)
- Real notifications — email/SMS delivery via Amazon SNS when the Monitor Agent detects eligibility changes
- User accounts — persistent profiles across sessions with opt-in notification preferences
- Expand to 10+ states, 15+ programs (CHIP, EITC, Section 8/HCV, utility disconnection protection)
- Caseworker dashboard — social workers manage multiple client profiles and track application status in bulk

### Stage 3 — Scale
- All 50 states
- Multilingual support — Spanish, Mandarin, Vietnamese (languages most common among eligible non-English speakers)
- Application assistance — pre-fill forms using the household profile collected during intake
- API layer for integration with government portals and nonprofit CRMs
- Anonymized aggregate data to help policymakers understand where benefits go unclaimed and why

### Data Architecture Evolution

| Stage | Storage | Rationale |
|---|---|---|
| 1 — MVP | DynamoDB | Zero ops, pay-per-request, fits hackathon scale |
| 2 — Pilot | DynamoDB + PostgreSQL (RDS) | Postgres for user accounts, caseworker relationships, and application tracking; DynamoDB retained for ephemeral eligibility snapshots |
| 3 — Scale | PostgreSQL (primary) + DynamoDB (cache) + Redshift/Athena (analytics) | Full relational model for transactional data, separate analytics layer for policy insights and aggregate reporting |

## License

MIT

## Disclaimer

AidRadar provides estimates based on PolicyEngine's open-source microsimulation model and publicly available program data. Actual eligibility is determined by the administering agency. This tool is not a substitute for professional benefits counseling.
