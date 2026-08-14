# AidRadar

**An AI agent that finds government benefits you didn't know you qualified for.**

Over $60 billion in federal benefits go unclaimed every year — not because people don't need them, but because they don't know they exist. AidRadar asks 10 simple questions about your household, cross-references your answers against 8 federal benefit programs across 4 states, and tells you exactly what you qualify for, how much you'd receive, and how to apply.

Built with [Strands Agents SDK](https://github.com/strands-agents) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Track.

## How It Works

1. **Intake Agent** — Conversational interview collects household details (income, size, state, age, etc.)
2. **Eligibility Agent** — Calls the eligibility_checker tool (PolicyEngine) to evaluate all 8 programs, then calls application_finder for each eligible program to get URLs and documents
3. **Recommendation Agent** — Generates an actionable, 6th-grade reading level report: eligible programs, estimated monthly benefit, documents needed, cascading benefits, and direct application links
4. **Monitor Agent** — Runs on a schedule (AWS EventBridge), re-checks eligibility when FPL thresholds or program rules change, and surfaces notifications only when your eligibility status shifts — without you doing anything

## Pipeline Status

- [x] Intake Agent — working (multi-turn conversational interview)
- [x] Eligibility Agent — working (calls eligibility_checker + application_finder tools)
- [x] Recommendation Agent — working (generates structured benefits report)
- [x] Monitor Agent — integrated in Streamlit UI (simulates 2027 FPL threshold update)
- [x] End-to-end CLI pipeline — working (`python -m src.main`)
- [x] E2E test with pre-filled profiles — working (`python -m tests.test_pipeline_e2e`)
- [x] Streamlit UI — working (`streamlit run src/app.py`): hero landing, chat intake, pipeline tracker, results dashboard, Monitor Agent demo
- [x] Program display names — proper names in all tool output (SNAP, SSI, LIHEAP, etc.)
- [ ] "What if" simulator — tweak income/household and see eligibility shift instantly
- [ ] Guardrails layer — input validation, PII protection
- [ ] DynamoDB profile store — persist profiles for Monitor Agent
- [ ] Tests — unit tests for tools, integration tests for agents
- [ ] Evals — LLM quality benchmarks across scenarios

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
- **Storage**: Amazon S3
- **Monitoring**: Strands `cron` tool / AWS EventBridge

## Project Structure

```
aid-radar/
├── src/
│   ├── app.py                      # Streamlit web app (hero, chat intake, results dashboard, monitor demo)
│   ├── main.py                     # CLI entry point (3-agent pipeline)
│   ├── config.py                   # Environment config (Mantle endpoint + API key)
│   ├── monitor_runner.py           # Monitor Agent standalone runner
│   ├── agents/
│   │   ├── intake.py               # Intake Agent (conversational, no tools)
│   │   ├── eligibility.py          # Eligibility Agent (eligibility_checker + application_finder)
│   │   ├── recommendation.py       # Recommendation Agent (report generation, no tools)
│   │   └── monitor.py              # Monitor Agent (background re-checker)
│   ├── tools/
│   │   ├── eligibility_checker.py  # PolicyEngine-backed eligibility for all 8 programs
│   │   └── application_finder.py   # State-specific application URLs and documents
│   ├── prompts/                    # Agent system prompts
│   │   ├── intake.txt
│   │   ├── eligibility.txt
│   │   ├── recommendation.txt
│   │   └── monitor.txt
│   ├── data/
│   │   └── programs/              # Per-program JSON (URLs, documents, state overrides)
│   └── output/                    # Report generation
├── tests/
│   ├── test_policyengine.py       # PolicyEngine integration test
│   └── test_pipeline_e2e.py       # End-to-end pipeline test (3 pre-filled profiles)
├── requirements.txt
└── .env                           # MANTLE_API_KEY, MODEL_ID, AWS_REGION
```

## Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/aid-radar.git
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

# Run the E2E test (skip intake, use pre-filled profile)
python -m tests.test_pipeline_e2e                     # default: ca_family_low_income
python -m tests.test_pipeline_e2e tx_single_adult     # disabled veteran in TX
python -m tests.test_pipeline_e2e ny_large_family     # family of 6 in NY
```

## Model Access

AidRadar uses Amazon Bedrock Mantle's OpenAI-compatible endpoint (`/v1/chat/completions`). Anthropic Claude models are available in Mantle but may be blocked on AISPL/India AWS accounts. DeepSeek V3.2 is the current default — it handles tool calling reliably and is available without Marketplace subscriptions.

Available models tested on Mantle:
- `deepseek.v3.2` (current default)
- `deepseek.v3.1`
- `google.gemma-3-12b-it`
- `qwen.qwen3-235b-a22b-2507`
- `mistral.mistral-large-3-675b-instruct`

## License

MIT

## Disclaimer

AidRadar provides estimates based on PolicyEngine's open-source microsimulation model and publicly available program data. Actual eligibility is determined by the administering agency. This tool is not a substitute for professional benefits counseling.
