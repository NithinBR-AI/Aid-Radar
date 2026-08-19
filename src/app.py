"""
AidRadar — Streamlit web app.
Run with: streamlit run src/app.py
"""

import json
import os
import re

import streamlit as st

from src.agents import (
    create_intake_agent,
    create_eligibility_agent,
    create_recommendation_agent,
    create_monitor_agent,
)
from src.main import _extract_json_profile, _build_eligibility_profile
from src.tools.eligibility_checker import eligibility_checker
from src.tools.profile_store import save_profile, get_profile, update_snapshot


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
if "whatif_results" not in st.session_state:
    st.session_state.whatif_results = None
if "baseline_programs" not in st.session_state:
    st.session_state.baseline_programs = {}
if "profile_id" not in st.session_state:
    st.session_state.profile_id = None


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

        # Store raw tool output for What If baseline + DynamoDB
        try:
            raw = eligibility_checker(json.dumps(eligibility_profile))
            if raw.get("status") == "success":
                programs = raw["content"][0]["json"]["programs"]
                st.session_state.baseline_programs = programs
                # Persist to DynamoDB for Monitor Agent
                try:
                    st.session_state.profile_id = save_profile(profile, programs)
                except Exception:
                    st.session_state.profile_id = None
        except Exception:
            st.session_state.baseline_programs = {}

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
                        "eligibility_results", "report", "monitor_notifications", "whatif_results",
                        "baseline_programs", "profile_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


# ---------------------------------------------------------------------------
# What If simulator helpers
# ---------------------------------------------------------------------------
def _run_whatif(modified_profile: dict) -> dict:
    """Run eligibility_checker directly on a modified profile. No LLM involved."""
    import json as _json
    result = eligibility_checker(_json.dumps(modified_profile))
    if result.get("status") != "success":
        return {}
    return result["content"][0]["json"]["programs"]


def _build_whatif_profile(base_profile: dict, monthly_income: int, num_adults: int, num_children: int) -> dict:
    """Build a modified profile copy without mutating the original."""
    import copy
    p = copy.deepcopy(base_profile)
    p["monthly_income"] = monthly_income

    annual = monthly_income * 12
    existing_adults = p.get("adults", [])
    new_adults = []
    for i in range(num_adults):
        age = existing_adults[i]["age"] if i < len(existing_adults) else 35
        new_adults.append({"age": age, "income": annual if i == 0 else 0})
    p["adults"] = new_adults

    existing_children = p.get("children", [])
    new_children = []
    for i in range(num_children):
        age = existing_children[i]["age"] if i < len(existing_children) else 5
        new_children.append({"age": age})
    p["children"] = new_children

    return p


def _show_whatif_section(base_profile: dict, original_programs: dict):
    st.markdown("---")
    st.markdown("### What If Simulator")
    st.markdown(
        "Adjust your household details below and see how your eligibility changes — instantly, "
        "using the same real benefit calculation engine."
    )

    orig_income = base_profile.get("monthly_income", 0)
    orig_adults = len(base_profile.get("adults", [{"age": 30}]))
    orig_children = len(base_profile.get("children", []))

    col1, col2, col3 = st.columns(3)
    with col1:
        wi_income = st.slider(
            "Monthly Income ($)",
            min_value=0,
            max_value=10000,
            value=int(orig_income),
            step=100,
            key="wi_income",
        )
    with col2:
        wi_adults = st.slider("Number of Adults", 1, 4, orig_adults, key="wi_adults")
    with col3:
        wi_children = st.slider("Number of Children", 0, 6, orig_children, key="wi_children")

    changed = (wi_income != int(orig_income)) or (wi_adults != orig_adults) or (wi_children != orig_children)

    if changed:
        if st.button("Recalculate Eligibility", type="primary", use_container_width=True, key="wi_calc"):
            with st.spinner("Running eligibility check..."):
                modified = _build_whatif_profile(base_profile, wi_income, wi_adults, wi_children)
                st.session_state.whatif_results = _run_whatif(modified)
            st.rerun()
    else:
        st.caption("Adjust the sliders above to explore different scenarios.")

    if st.session_state.whatif_results:
        _render_whatif_comparison(original_programs, st.session_state.whatif_results)


def _render_whatif_comparison(original: dict, modified: dict):
    all_ids = set(original.keys()) | set(modified.keys())

    gained, lost, changed_amount, unchanged = [], [], [], []
    for pid in all_ids:
        orig = original.get(pid, {})
        mod = modified.get(pid, {})
        orig_elig = orig.get("eligible", False)
        mod_elig = mod.get("eligible", False)
        name = mod.get("display_name") or orig.get("display_name") or pid.upper()

        if not orig_elig and mod_elig:
            gained.append((name, mod))
        elif orig_elig and not mod_elig:
            lost.append((name, mod))
        elif orig_elig and mod_elig:
            orig_amt = (orig.get("estimated_benefit") or {}).get("monthly", 0) or 0
            mod_amt = (mod.get("estimated_benefit") or {}).get("monthly", 0) or 0
            if abs(orig_amt - mod_amt) > 1:
                changed_amount.append((name, orig_amt, mod_amt))
            else:
                unchanged.append(name)

    st.markdown("#### Impact")

    if not gained and not lost and not changed_amount:
        st.info("No eligibility changes with these settings.")
        return

    col1, col2 = st.columns(2)

    with col1:
        if gained:
            for name, prog in gained:
                amt = (prog.get("estimated_benefit") or {}).get("monthly")
                amt_str = f" — ${amt:,.0f}/mo" if amt else ""
                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid #2D7A4F;">
                    <span class="eligible-badge">NOW ELIGIBLE</span>
                    <h4>{name}{amt_str}</h4>
                </div>
                """, unsafe_allow_html=True)
        if changed_amount:
            for name, orig_amt, mod_amt in changed_amount:
                delta = mod_amt - orig_amt
                sign = "+" if delta > 0 else ""
                color = "#2D7A4F" if delta > 0 else "#C0392B"
                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid {color};">
                    <span class="eligible-badge">AMOUNT CHANGED</span>
                    <h4>{name}</h4>
                    <div style="color:{color};font-weight:700;">{sign}${delta:,.0f}/mo</div>
                    <div style="color:#666;font-size:0.82rem;">${orig_amt:,.0f} → ${mod_amt:,.0f}/mo</div>
                </div>
                """, unsafe_allow_html=True)

    with col2:
        if lost:
            for name, _ in lost:
                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid #C0392B;">
                    <span class="ineligible-badge">NO LONGER ELIGIBLE</span>
                    <h4>{name}</h4>
                </div>
                """, unsafe_allow_html=True)
        if unchanged:
            st.markdown(
                f"<div style='color:#888;font-size:0.82rem;margin-top:0.5rem;'>"
                f"Unchanged: {', '.join(unchanged)}</div>",
                unsafe_allow_html=True
            )


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
                name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").replace("_", " ").upper()
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
                name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").replace("_", " ").upper()
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

    # What If simulator
    if st.session_state.profile:
        original_programs = st.session_state.get("baseline_programs") or {}
        _show_whatif_section(st.session_state.profile, original_programs)

    # Full report
    st.markdown("---")
    with st.expander("Full Benefits Report", expanded=False):
        st.markdown(st.session_state.report)

    # Monitor Agent demo
    st.markdown("---")
    st.markdown("### Monitor Agent")
    st.markdown(
        "AidRadar doesn't stop here. The Monitor Agent runs on a schedule via AWS EventBridge — "
        "weekly or monthly — loads your saved profile from DynamoDB, re-runs the real PolicyEngine "
        "eligibility calculation, and sends you a notification **only when something actually changes**. "
        "No login needed. No forms to re-fill. You get an email or SMS the moment you become eligible "
        "for a new program, or when a benefit amount changes."
    )

    orig_income = st.session_state.profile.get("monthly_income", 2000) if st.session_state.profile else 2000
    st.caption(
        f"Simulate a life event: your income dropped. "
        f"Your current income is **${orig_income:,}/month**. "
        "Adjust the slider and run the Monitor Agent to see real eligibility changes."
    )

    monitor_income = st.slider(
        "Simulated new monthly income ($)",
        min_value=0,
        max_value=int(orig_income),
        value=max(0, int(orig_income) - 1000),
        step=100,
        key="monitor_income_slider",
    )

    if st.button("Run Monitor Agent", type="primary", use_container_width=True, key="run_monitor"):
        _run_monitor_demo(monitor_income)

    if st.session_state.monitor_notifications is not None:
        _render_monitor_notifications()

    # Actions
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Over", use_container_width=True):
            for key in ["stage", "messages", "intake_agent", "profile",
                        "eligibility_results", "report", "monitor_notifications", "whatif_results",
                        "baseline_programs", "profile_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("View Household Profile", use_container_width=True):
            st.json(st.session_state.profile)


# ---------------------------------------------------------------------------
# Monitor Agent demo — real DynamoDB-backed before/after
# ---------------------------------------------------------------------------
def _run_monitor_demo(new_monthly_income: int):
    """
    Real Monitor Agent demo:
    1. Load saved profile + snapshot from DynamoDB
    2. Build modified profile with new income
    3. Re-run eligibility_checker (PolicyEngine) — real calculation
    4. Diff new vs stored snapshot — real changes
    5. Run Monitor Agent with both snapshots to generate notifications
    """
    import copy

    profile_id = st.session_state.profile_id
    original_profile = st.session_state.profile  # intake format

    status = st.status("Monitor Agent running scheduled check...", expanded=True)

    # Load from DynamoDB
    status.write("Loading saved profile from DynamoDB...")
    saved = get_profile(profile_id) if profile_id else None
    if not saved:
        saved = {
            "profile": original_profile,
            "eligibility_snapshot": st.session_state.baseline_programs,
        }
        status.write("(Using in-session baseline — DynamoDB profile not found)")

    previous_snapshot = saved["eligibility_snapshot"]

    # Build modified eligibility profile (correct format for PolicyEngine)
    base_eligibility = _build_eligibility_profile(original_profile)
    modified_profile = copy.deepcopy(base_eligibility)
    modified_profile["monthly_income"] = new_monthly_income
    if modified_profile.get("adults"):
        modified_profile["adults"][0]["income"] = new_monthly_income * 12

    orig_monthly = base_eligibility.get("monthly_income", original_profile.get("monthly_income", 0))
    status.write(f"Income changed: **${orig_monthly:,}/mo → ${new_monthly_income:,}/mo**")
    status.write("Re-running PolicyEngine eligibility check with new income...")

    # Real eligibility re-check
    raw = eligibility_checker(json.dumps(modified_profile))
    if raw.get("status") != "success":
        status.update(label="Eligibility check failed", state="error")
        return

    new_snapshot = raw["content"][0]["json"]["programs"]

    # Update DynamoDB with new snapshot
    if profile_id:
        update_snapshot(profile_id, new_snapshot)

    status.write("Comparing against stored eligibility snapshot...")

    # Run Monitor Agent with BOTH real snapshots
    agent = create_monitor_agent()
    # Build a compact diff summary so the LLM focuses on narrative, not recalculation
    diff_gained = []
    diff_lost = []
    diff_changed = []
    for pid in set(previous_snapshot) | set(new_snapshot):
        prev = previous_snapshot.get(pid, {})
        curr = new_snapshot.get(pid, {})
        name = curr.get("display_name") or prev.get("display_name") or pid.upper()
        prev_elig = prev.get("eligible", False)
        curr_elig = curr.get("eligible", False)
        if not prev_elig and curr_elig:
            diff_gained.append(name)
        elif prev_elig and not curr_elig:
            diff_lost.append(name)
        else:
            prev_amt = (prev.get("estimated_benefit") or {}).get("monthly", 0) or 0
            curr_amt = (curr.get("estimated_benefit") or {}).get("monthly", 0) or 0
            if abs(curr_amt - prev_amt) > 5:
                diff_changed.append(f"{name}: ${prev_amt:,.0f}/mo → ${curr_amt:,.0f}/mo")

    prompt = (
        "You are the AidRadar Monitor Agent running a scheduled eligibility re-check.\n\n"
        f"**Life event:** The user's income dropped from "
        f"${orig_monthly:,}/month to ${new_monthly_income:,}/month.\n\n"
        "**Eligibility changes (already calculated by PolicyEngine — do NOT recalculate):**\n"
        f"- Newly eligible: {', '.join(diff_gained) if diff_gained else 'none'}\n"
        f"- Lost eligibility: {', '.join(diff_lost) if diff_lost else 'none'}\n"
        f"- Benefit amounts changed: {', '.join(diff_changed) if diff_changed else 'none'}\n\n"
        "Write a short, human-friendly notification summary (3-5 sentences) explaining what changed "
        "and what the user should do next. Use plain language, no JSON, no technical jargon. "
        "Focus on actionable next steps for each changed program."
    )

    result = agent(prompt)
    agent_text = str(result)

    # Use diff already computed above for the prompt
    gained = diff_gained
    lost = diff_lost
    # Reparse diff_changed into (name, prev_amt, curr_amt) tuples for rendering
    changed = []
    for pid in set(previous_snapshot) | set(new_snapshot):
        prev = previous_snapshot.get(pid, {})
        curr = new_snapshot.get(pid, {})
        prev_elig = prev.get("eligible", False)
        curr_elig = curr.get("eligible", False)
        if prev_elig and curr_elig:
            prev_amt = (prev.get("estimated_benefit") or {}).get("monthly", 0) or 0
            curr_amt = (curr.get("estimated_benefit") or {}).get("monthly", 0) or 0
            if abs(curr_amt - prev_amt) > 5:
                name = curr.get("display_name") or prev.get("display_name") or pid.upper()
                changed.append((name, prev_amt, curr_amt))

    status.update(label="Monitor Agent: check complete", state="complete", expanded=False)

    st.session_state.monitor_notifications = {
        "original_income": orig_monthly,
        "new_income": new_monthly_income,
        "gained": gained,
        "lost": lost,
        "changed": changed,
        "agent_output": agent_text,
        "profile_id": profile_id,
    }
    st.rerun()


def _render_monitor_notifications():
    data = st.session_state.monitor_notifications
    orig = data["original_income"]
    new = data["new_income"]
    gained = data["gained"]
    lost = data["lost"]
    changed = data["changed"]
    profile_id = data.get("profile_id")

    pid_str = f" · Profile `{profile_id[:8]}...`" if profile_id else ""

    st.markdown(f"""
    <div class="notif-card" style="border-left-color:#1565C0;background:#E3F2FD;">
        <div style="font-weight:700;color:#0D47A1;margin-bottom:0.3rem;">
            Scheduled Check — Monitor Agent
        </div>
        <div style="color:#1A1A18;">Income changed: <strong>${orig:,}/mo → ${new:,}/mo</strong></div>
        <div style="color:#555;font-size:0.85rem;margin-top:0.3rem;">
            Profile loaded from DynamoDB. Eligibility re-calculated by PolicyEngine.
            Diff computed against stored snapshot.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        for name in gained:
            st.markdown(f"""
            <div class="notif-card">
                <div class="notif-tier low">NEW — Tier 1</div>
                <h4>{name}</h4>
                <p>You are now eligible. Apply as soon as possible.</p>
            </div>
            """, unsafe_allow_html=True)
        for name, prev_amt, curr_amt in changed:
            delta = curr_amt - prev_amt
            sign = "+" if delta > 0 else ""
            st.markdown(f"""
            <div class="notif-card medium">
                <div class="notif-tier medium">CHANGED — Tier 3</div>
                <h4>{name}</h4>
                <p>${prev_amt:,.0f}/mo → ${curr_amt:,.0f}/mo ({sign}${delta:,.0f})</p>
            </div>
            """, unsafe_allow_html=True)
    with col2:
        for name in lost:
            st.markdown(f"""
            <div class="notif-card high">
                <div class="notif-tier high">LOST — Tier 2</div>
                <h4>{name}</h4>
                <p>You may no longer qualify. Update your profile if your situation changed.</p>
            </div>
            """, unsafe_allow_html=True)

    if not gained and not lost and not changed:
        st.info("No eligibility changes detected with this income level.")

    with st.expander("Monitor Agent Full Analysis", expanded=False):
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
