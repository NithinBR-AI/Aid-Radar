# AidRadar

**An AI agent that finds government benefits you didn't know you qualified for.**

Over $60 billion in federal benefits go unclaimed every year — not because people don't need them, but because they don't know they exist. AidRadar asks 10 simple questions about your household, cross-references your answers against 8 federal benefit programs across 4 states, and tells you exactly what you qualify for, how much you'd receive, and how to apply.

Built with [Strands Agents SDK](https://github.com/strands-agents) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Track.

## How It Works

1. **Intake Agent** — Conversational interview collects household details (income, size, state, age, etc.)
2. **Eligibility Agent** — Runs a PolicyEngine simulation to check all programs at once, with LIHEAP as a fallback
3. **Recommendation Agent** — Generates an actionable report: eligible programs, estimated monthly benefit, documents needed, and direct application links
4. **Monitor Agent** — Runs monthly in the background, re-checks when thresholds update, and notifies you only when your eligibility changes

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
- **LLM**: Amazon Bedrock (Claude 3.5 Sonnet)
- **Eligibility Engine**: [PolicyEngine](https://policyengine.org) (open-source tax & benefit microsimulation)
- **Frontend**: Streamlit
- **Data**: Application URLs and document requirements (JSON), PolicyEngine for eligibility math
- **Storage**: Amazon S3
- **Monitoring**: Strands `cron` tool / AWS EventBridge

## Project Structure

```
aid-radar/
├── src/
│   ├── app.py                    # Streamlit web app
│   ├── main.py                   # CLI entry point
│   ├── config.py                 # Environment config
│   ├── monitor_runner.py         # Monitor Agent standalone runner
│   ├── config/
│   │   ├── programs.yaml         # Toggle programs on/off
│   │   ├── states.yaml           # Supported states
│   │   └── monitor.yaml          # Monitor schedule & notification settings
│   ├── agents/                   # Agent definitions (TBD)
│   ├── tools/
│   │   ├── eligibility_checker.py  # PolicyEngine-backed eligibility for all programs
│   │   └── application_finder.py   # Application URLs and document requirements
│   ├── prompts/                  # Agent system prompts
│   │   ├── intake.txt
│   │   ├── eligibility.txt
│   │   ├── recommendation.txt
│   │   └── monitor.txt
│   ├── data/
│   │   └── programs/            # Application URLs, documents, state program names
│   └── output/                  # Report generation
├── tests/
│   └── test_policyengine.py     # PolicyEngine integration test
├── requirements.txt
└── .streamlit/config.toml       # Custom theme
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

# Configure AWS credentials
aws configure
# Set region to us-east-1

# Create .env file
echo AWS_REGION=us-east-1 > .env
echo S3_BUCKET=your-bucket-name >> .env

# Run the web app
streamlit run src/app.py
```

## License

MIT

## Disclaimer

AidRadar provides estimates based on PolicyEngine's open-source microsimulation model and publicly available program data. Actual eligibility is determined by the administering agency. This tool is not a substitute for professional benefits counseling.
