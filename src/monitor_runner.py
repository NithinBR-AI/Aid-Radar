"""
AidRadar — Monitor Agent standalone runner.
Run with: python -m src.monitor_runner

This script runs independently of the web app. It:
- Loads all saved user profiles
- Re-checks eligibility against current program thresholds
- Compares results to previous eligibility snapshots
- Sends notifications only when something changed

Intended to be triggered by:
- AWS EventBridge Scheduler (production)
- Manual invocation for demo: python -m src.monitor_runner --run-now
- Strands cron tool within a long-running agent process
"""
