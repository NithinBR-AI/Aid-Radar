"""
AidRadar — Streamlit web app.
Run with: streamlit run src/app.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from src.agents import (
    create_intake_agent,
    create_eligibility_agent,
    create_recommendation_agent,
    create_monitor_agent,
)
from src.main import _extract_json_profile, _build_eligibility_profile


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AidRadar — Government Benefit Finder",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Hide default streamlit branding */
    #MainMenu, footer, header {visibility: hidden;}

    /* Hero section */
    .hero {
        text-align: center;
        padding: 3.5rem 1rem 2.5rem;
        background: linear-gradient(165deg, #F0FAF4 0%, #E8F5EC 40%, #FAFAF8 100%);
        border-radius: 0 0 24px 24px;
        margin: -1rem -1rem 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    .hero h1 {
        font-size: 3.2rem;
        margin-bottom: 0.4rem;
        color: #1A1A18;
        letter-spacing: -0.02em;
        font-weight: 800;
    }
    .hero .tagline {
        font-size: 1.25rem;
        color: #444;
        margin-bottom: 0.6rem;
        font-weight: 400;
    }
    .hero .stat {
        font-size: 1.15rem;
        color: #2D7A4F;
        font-weight: 700;
        margin-bottom: 2rem;
        display: inline-block;
        background: rgba(45, 122, 79, 0.08);
        padding: 0.4rem 1.2rem;
        border-radius: 2rem;
    }

    /* Value prop cards */
    .value-card {
        background: white;
        border: 1px solid #E8E8E4;
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .value-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .value-card .icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .value-card h3 {
        margin: 0 0 0.4rem;
        font-size: 1.05rem;
        color: #1A1A18;
    }
    .value-card p {
        margin: 0;
        color: #666;
        font-size: 0.88rem;
        line-height: 1.45;
    }

    /* Pipeline tracker */
    .pipeline {
        display: flex;
        justify-content: center;
        gap: 0.5rem;
        margin: 1.5rem 0;
        flex-wrap: wrap;
    }
    .pipeline-step {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.55rem 1.1rem;
        border-radius: 2rem;
        font-size: 0.9rem;
        font-weight: 600;
        background: #F0F0EC;
        color: #999;
        transition: all 0.3s;
    }
    .pipeline-step.active {
        background: linear-gradient(135deg, #2D7A4F 0%, #3A9963 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(45, 122, 79, 0.3);
    }
    .pipeline-step.done {
        background: #D4EDDA;
        color: #155724;
    }
    .pipeline-arrow {
        display: flex;
        align-items: center;
        color: #ccc;
        font-size: 1.2rem;
    }

    /* Metric cards */
    .benefit-card {
        background: white;
        border: 1px solid #E8E8E4;
        border-radius: 14px;
        padding: 1.3rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.15s;
    }
    .benefit-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .benefit-card h4 {
        margin: 0.3rem 0 0.3rem;
        color: #1A1A18;
        font-size: 1.05rem;
    }
    .benefit-card .amount {
        font-size: 1.5rem;
        font-weight: 800;
        color: #2D7A4F;
        letter-spacing: -0.01em;
    }
    .benefit-card .eligible-badge {
        display: inline-block;
        background: linear-gradient(135deg, #D4EDDA, #C8E6C9);
        color: #155724;
        padding: 0.2rem 0.7rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .benefit-card .ineligible-badge {
        display: inline-block;
        background: #F8D7DA;
        color: #721C24;
        padding: 0.2rem 0.7rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Big number */
    .big-number {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #2D7A4F 0%, #1B6E40 50%, #145533 100%);
        border-radius: 20px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(45, 122, 79, 0.25);
        position: relative;
        overflow: hidden;
    }
    .big-number::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 200px;
        height: 200px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
    }
    .big-number .value {
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.02em;
    }
    .big-number .label {
        font-size: 1rem;
        opacity: 0.9;
        font-weight: 500;
    }
    .big-number .sub {
        font-size: 0.88rem;
        opacity: 0.75;
        margin-top: 0.4rem;
    }

    /* Cascade visualization */
    .cascade-box {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFF3CD 100%);
        border: 1px solid #FFE082;
        border-radius: 14px;
        padding: 1.2rem;
        margin: 1rem 0;
    }
    .cascade-box h4 {
        margin: 0 0 0.5rem;
        color: #E65100;
    }

    /* Monitor notification cards */
    .notif-card {
        background: white;
        border-left: 4px solid #2D7A4F;
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .notif-card.high {
        border-left-color: #E53935;
    }
    .notif-card.medium {
        border-left-color: #FB8C00;
    }
    .notif-card .notif-tier {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 0.8rem;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.4rem;
    }
    .notif-card .notif-tier.high {
        background: #FFCDD2;
        color: #B71C1C;
    }
    .notif-card .notif-tier.medium {
        background: #FFE0B2;
        color: #E65100;
    }
    .notif-card .notif-tier.low {
        background: #C8E6C9;
        color: #1B5E20;
    }
    .notif-card h4 {
        margin: 0.3rem 0;
        color: #1A1A18;
    }
    .notif-card p {
        margin: 0.3rem 0 0;
        color: #555;
        font-size: 0.9rem;
        line-height: 1.4;
    }

    /* Footer styling */
    .footer-text {
        text-align: center;
        color: #999;
        font-size: 0.82rem;
        padding: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "landing"  # landing, intake, processing, results
if "messages" not in st.session_state:
    st.session_state.messages = []
if "intake_agent" not in st.session_state:
    st.session_state.intake_agent = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "eligibility_results" not in st.session_state:
    st.session_state.eligibility_results = None
if "report" not in st.session_state:
    st.session_state.report = None
if "monitor_notifications" not in st.session_state:
    st.session_state.monitor_notifications = None


# ---------------------------------------------------------------------------
# Pipeline tracker component
# ---------------------------------------------------------------------------
def render_pipeline(current_stage: str):
    stages = [
        ("intake", "Interview"),
        ("eligibility", "Eligibility Check"),
        ("recommendation", "Your Report"),
    ]
    stage_order = [s[0] for s in stages]
    current_idx = stage_order.index(current_stage) if current_stage in stage_order else -1

    html_parts = []
    for i, (key, label) in enumerate(stages):
        if i < current_idx:
            css = "done"
            icon = "&#10003;"
        elif i == current_idx:
            css = "active"
            icon = "&#9679;"
        else:
            css = ""
            icon = str(i + 1)
        html_parts.append(f'<div class="pipeline-step {css}">{icon}&nbsp;{label}</div>')
        if i < len(stages) - 1:
            html_parts.append('<div class="pipeline-arrow">&#8594;</div>')

    st.markdown(f'<div class="pipeline">{"".join(html_parts)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------
def show_landing():
    st.markdown("""
    <div class="hero">
        <h1>AidRadar</h1>
        <div class="tagline">Find government benefits you didn't know you qualified for</div>
        <div class="stat">$60 billion in federal benefits go unclaimed every year</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="value-card">
            <div class="icon">&#128172;</div>
            <h3>10 Simple Questions</h3>
            <p>A 2-minute conversational interview about your household. No SSN or sensitive data needed.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="value-card">
            <div class="icon">&#9989;</div>
            <h3>8 Programs Checked</h3>
            <p>SNAP, Medicaid, WIC, TANF, SSI, LIHEAP, Lifeline, Free School Meals — all at once.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="value-card">
            <div class="icon">&#128640;</div>
            <h3>Instant Action Plan</h3>
            <p>Estimated benefits, required documents, application links, and which program to apply for first.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("Find My Benefits", type="primary", use_container_width=True):
            st.session_state.stage = "intake"
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "Welcome to AidRadar! I'll ask you a few quick questions about your "
                    "household so we can check your eligibility across 8 federal benefit programs.\n\n"
                    "Let's start — **what state do you live in?** (e.g. California, Texas, New York, Florida)"
                ),
            })
            st.rerun()

    st.markdown("""
    <div class="footer-text">
        Covers California, Texas, New York, and Florida — ~100M people.<br>
        Built with Strands Agents SDK &bull; Amazon Bedrock &bull; PolicyEngine
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Intake chat
# ---------------------------------------------------------------------------
def show_intake():
    render_pipeline("intake")

    st.markdown("#### Tell us about your household")
    st.caption("Answer a few questions and we'll check your eligibility across 8 benefit programs.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Type your answer..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        if st.session_state.intake_agent is None:
            with st.spinner("Starting intake agent..."):
                st.session_state.intake_agent = create_intake_agent()
                st.session_state.intake_agent(
                    "You already greeted the user with: 'Welcome to AidRadar! I'll ask you a few "
                    "quick questions about your household so we can check your eligibility across "
                    "8 federal benefit programs. Let's start — what state do you live in?' "
                    "The user's reply is coming next. Do NOT re-greet or re-ask the state question. "
                    "Process their state answer and move to question 2 (household size)."
                )

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = st.session_state.intake_agent(user_input)
                agent_text = str(result)

        st.session_state.messages.append({"role": "assistant", "content": agent_text})

        profile = _extract_json_profile(agent_text)
        if profile and "state" in profile and "monthly_income" in profile:
            st.session_state.profile = profile
            st.session_state.stage = "processing"
            st.rerun()
        elif profile and ("state" not in profile or "monthly_income" not in profile):
            missing = []
            if "state" not in profile:
                missing.append("state")
            if "monthly_income" not in profile:
                missing.append("monthly_income")
            with st.chat_message("assistant"):
                st.warning(f"Profile captured but missing required fields: {', '.join(missing)}. Continuing interview...")
            st.rerun()
        else:
            st.rerun()


# ---------------------------------------------------------------------------
# Processing (eligibility + recommendation)
# ---------------------------------------------------------------------------
def show_processing():
    render_pipeline("eligibility")

    st.markdown("#### Analyzing your eligibility...")

    profile = st.session_state.profile
    eligibility_profile = _build_eligibility_profile(profile)

    status = st.status("Running AidRadar pipeline...", expanded=True)

    try:
        # Step 1: Eligibility Agent
        status.write("**Step 1/2** — Eligibility Agent checking 8 programs via PolicyEngine...")
        agent = create_eligibility_agent()
        prompt = (
            "Here is the household profile from the Intake Agent. "
            "Call the eligibility_checker tool with this profile, then call "
            "application_finder for each eligible program. "
            "Output the structured eligibility results.\n\n"
            f"```json\n{json.dumps(eligibility_profile, indent=2)}\n```"
        )
        result = agent(prompt)
        eligibility_text = str(result)
        st.session_state.eligibility_results = eligibility_text
        status.write("Eligibility check complete.")

        # Step 2: Recommendation Agent
        status.write("**Step 2/2** — Recommendation Agent generating your benefits report...")
        rec_agent = create_recommendation_agent()
        rec_prompt = (
            "Here is the household profile and eligibility results. "
            "Generate the full benefits report following your instructions.\n\n"
            f"**Household Profile:**\n```json\n{json.dumps(profile, indent=2)}\n```\n\n"
            f"**Eligibility Results:**\n{eligibility_text}"
        )
        result = rec_agent(rec_prompt)
        report_text = str(result)
        st.session_state.report = report_text

        status.update(label="Pipeline complete!", state="complete", expanded=False)

        st.session_state.stage = "results"
        st.rerun()

    except Exception as e:
        status.update(label="Pipeline error", state="error", expanded=True)
        status.write(f"Something went wrong: {e}")
        st.error(
            "The eligibility check failed — this is usually a temporary issue with the AI model. "
            "Click below to try again."
        )
        if st.button("Retry", type="primary"):
            st.rerun()
        if st.button("Start Over"):
            for key in ["stage", "messages", "intake_agent", "profile",
                        "eligibility_results", "report", "monitor_notifications"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


# ---------------------------------------------------------------------------
# Results dashboard
# ---------------------------------------------------------------------------
def _parse_eligibility_json(text: str) -> dict | None:
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match)
            if "eligible_programs" in data or "programs" in data:
                return data
        except json.JSONDecodeError:
            continue
    return None


def show_results():
    render_pipeline("recommendation")

    eligibility_data = _parse_eligibility_json(st.session_state.eligibility_results or "")

    if not eligibility_data:
        st.info("Could not parse structured eligibility data — showing the full agent report below.")
        st.markdown(st.session_state.report or st.session_state.eligibility_results or "")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start Over", use_container_width=True, key="fallback_start_over"):
                for key in ["stage", "messages", "intake_agent", "profile",
                            "eligibility_results", "report", "monitor_notifications"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        return

    # Big number header
    if eligibility_data:
        total_monthly = eligibility_data.get("total_estimated_monthly_benefit", 0)
        total_annual = eligibility_data.get("total_estimated_annual_benefit", 0)
        eligible_count = len(eligibility_data.get("eligible_programs", []))

        st.markdown(f"""
        <div class="big-number">
            <div class="label">You may be eligible for</div>
            <div class="value">${total_monthly:,.0f}/month</div>
            <div class="sub">${total_annual:,.0f}/year across {eligible_count} programs</div>
        </div>
        """, unsafe_allow_html=True)

        # Program cards
        st.markdown("### Eligible Programs")

        eligible = eligibility_data.get("eligible_programs", [])
        cols = st.columns(2)
        for i, prog in enumerate(eligible):
            with cols[i % 2]:
                name = prog.get("program_name", prog.get("program_id", ""))
                monthly = prog.get("estimated_monthly_benefit")
                url = prog.get("apply_url", "")
                cascading = prog.get("cascading_benefits", [])

                amount_html = f'<div class="amount">${monthly:,.2f}/mo</div>' if monthly else '<div class="amount">Coverage (no $ estimate)</div>'
                cascade_html = ""
                if cascading:
                    cascade_names = ", ".join(c.replace("_", " ").title() for c in cascading)
                    cascade_html = f'<div style="margin-top:0.5rem;font-size:0.8rem;color:#F57F17;">&#x1F517; Unlocks: {cascade_names}</div>'

                apply_html = f'<div style="margin-top:0.5rem;"><a href="{url}" target="_blank" style="color:#2D7A4F;font-weight:600;">Apply here &rarr;</a></div>' if url else ""

                st.markdown(f"""
                <div class="benefit-card">
                    <span class="eligible-badge">ELIGIBLE</span>
                    <h4>{name}</h4>
                    {amount_html}
                    {apply_html}
                    {cascade_html}
                </div>
                """, unsafe_allow_html=True)

        # Ineligible programs
        ineligible = eligibility_data.get("ineligible_programs", [])
        if ineligible:
            st.markdown("### Not Eligible")
            for prog in ineligible:
                name = prog.get("program_name", prog.get("program_id", ""))
                reason = prog.get("reason", "")
                st.markdown(f"""
                <div class="benefit-card">
                    <span class="ineligible-badge">NOT ELIGIBLE</span>
                    <h4>{name}</h4>
                    <div style="color:#666;font-size:0.9rem;">{reason}</div>
                </div>
                """, unsafe_allow_html=True)

        # Cascading benefits
        cascading_programs = [p for p in eligible if p.get("cascading_benefits")]
        if cascading_programs:
            st.markdown("""
            <div class="cascade-box">
                <h4>&#x1F4A1; Cascading Benefits</h4>
                <div>Applying for one program can automatically qualify you for others — saving time and paperwork.</div>
            </div>
            """, unsafe_allow_html=True)

    # Full report
    st.markdown("---")
    with st.expander("Full Benefits Report", expanded=False):
        st.markdown(st.session_state.report)

    # Monitor Agent demo
    st.markdown("---")
    st.markdown("### Monitor Agent")
    st.markdown(
        "AidRadar doesn't stop here. The Monitor Agent runs automatically on a schedule "
        "(AWS EventBridge) and re-checks your eligibility when **program thresholds change** "
        "— so you never miss a benefit you've become eligible for."
    )
    st.caption(
        "Click below to simulate the 2027 Federal Poverty Level update. "
        "Your profile stays the same — only the government's rules change."
    )

    run_monitor = st.button(
        "Simulate: 2027 FPL Guidelines Update (+4.2%)",
        type="primary",
        use_container_width=True,
    )

    if run_monitor:
        _run_monitor_demo()

    if st.session_state.monitor_notifications is not None:
        _render_monitor_notifications()

    # Actions
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Over", use_container_width=True):
            for key in ["stage", "messages", "intake_agent", "profile",
                        "eligibility_results", "report", "monitor_notifications"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("View Household Profile", use_container_width=True):
            st.json(st.session_state.profile)


# ---------------------------------------------------------------------------
# Monitor Agent demo
# ---------------------------------------------------------------------------
def _run_monitor_demo():
    """Simulate a 2027 FPL threshold increase and run the Monitor Agent."""
    profile = st.session_state.profile
    fpl_increase_pct = 4.2

    status = st.status("Monitor Agent running scheduled check...", expanded=True)
    status.write("**January 2027** — New Federal Poverty Level guidelines published.")
    status.write(f"FPL increased by **{fpl_increase_pct}%** across all household sizes.")
    status.write("Re-checking eligibility with the same household profile against new thresholds...")

    agent = create_monitor_agent()
    prompt = (
        "You are running a scheduled eligibility re-check. The user's profile has NOT changed. "
        "What changed is the **Federal Poverty Level guidelines for 2027**, which increased by 4.2%.\n\n"
        "This means income thresholds for programs like SNAP, TANF, LIHEAP, and Free School Meals "
        "have all risen — some households that were previously just above the cutoff may now qualify.\n\n"
        f"**User profile (unchanged):**\n```json\n{json.dumps(profile, indent=2)}\n```\n\n"
        f"**Previous eligibility results (2026 thresholds):**\n{st.session_state.eligibility_results}\n\n"
        "Call eligibility_checker with the user's profile to get the CURRENT results. "
        "Then compare against the previous results above.\n\n"
        "For this simulation, assume the 4.2% FPL increase means:\n"
        "- Programs where the user was close to the income threshold (within 10%) may now show as eligible\n"
        "- Benefit amounts for already-eligible programs may have increased slightly\n"
        "- Programs where the user was well below the threshold are unchanged\n\n"
        "Report ONLY meaningful changes as notifications. Use proper program display names "
        "(SNAP, Medicaid, SSI, TANF, WIC, LIHEAP, Lifeline, Free School Meals). "
        "For each change, explain that the 2027 FPL increase caused the threshold to rise. "
        "Output a JSON array of notifications following your notification format."
    )

    result = agent(prompt)
    agent_text = str(result)

    status.update(label="Monitor Agent: scheduled check complete", state="complete", expanded=False)

    st.session_state.monitor_notifications = {
        "scenario": "2027 Federal Poverty Level guidelines increased by 4.2%",
        "fpl_increase": fpl_increase_pct,
        "agent_output": agent_text,
    }
    st.rerun()


def _render_monitor_notifications():
    """Render the Monitor Agent's notifications."""
    data = st.session_state.monitor_notifications
    scenario = data["scenario"]

    st.markdown(f"""
    <div class="notif-card" style="border-left-color:#1565C0;background:#E3F2FD;">
        <div style="font-weight:700;color:#0D47A1;margin-bottom:0.3rem;">
            Scheduled Check — January 2027
        </div>
        <div style="color:#1A1A18;">{scenario}</div>
        <div style="color:#555;font-size:0.85rem;margin-top:0.3rem;">
            Your profile was unchanged. The Monitor Agent detected the threshold update
            and re-evaluated your eligibility automatically.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Monitor Agent Analysis", expanded=True):
        st.markdown(data["agent_output"])


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def main():
    stage = st.session_state.stage

    if stage == "landing":
        show_landing()
    elif stage == "intake":
        show_intake()
    elif stage == "processing":
        show_processing()
    elif stage == "results":
        show_results()


if __name__ == "__main__":
    main()
