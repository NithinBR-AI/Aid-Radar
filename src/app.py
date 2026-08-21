"""
AidRadar — Streamlit web app.
Run with: streamlit run src/app.py
"""

import json
import os
import re
import sys

# Streamlit Cloud runs files from the repo root — ensure it's on sys.path
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from src.agents import create_intake_agent
from src.pipeline.runner import extract_json_profile, build_eligibility_profile, run_pipeline, run_whatif
from src.pipeline.monitor_pipeline import run_monitor_check


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
        background: linear-gradient(165deg, #EEF1F5 0%, #E5EAF2 40%, #F8F7F4 100%);
        border-radius: 0 0 24px 24px;
        margin: -1rem -1rem 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    .hero h1 {
        font-size: 3.2rem;
        margin-bottom: 0.4rem;
        color: #1B3A5C;
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
        color: #1B3A5C;
        font-weight: 700;
        margin-bottom: 2rem;
        display: inline-block;
        background: rgba(27, 58, 92, 0.08);
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
        background: linear-gradient(135deg, #1B3A5C 0%, #2A5480 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(27, 58, 92, 0.3);
    }
    .pipeline-step.done {
        background: #D6E4F0;
        color: #1B3A5C;
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
        color: #1B3A5C;
        letter-spacing: -0.01em;
    }
    .benefit-card .eligible-badge {
        display: inline-block;
        background: linear-gradient(135deg, #FEF0D0, #FDDFA0);
        color: #7A5000;
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
        background: linear-gradient(135deg, #1B3A5C 0%, #142D48 50%, #0D1E30 100%);
        border-radius: 20px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(27, 58, 92, 0.35);
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
        background: rgba(244, 164, 42, 0.06);
        border-radius: 50%;
    }
    .big-number .value {
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.02em;
        color: #F4A42A;
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
        border-left: 4px solid #1B3A5C;
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
if "state_is_fallback" not in st.session_state:
    st.session_state.state_is_fallback = False
if "state_original" not in st.session_state:
    st.session_state.state_original = None


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
    st.markdown("### How it works")
    st.markdown("""
    <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.5rem;">
        <div style="flex:1;min-width:180px;background:white;border:1px solid #E8E8E4;border-radius:14px;padding:1.2rem;text-align:center;">
            <div style="font-size:1.6rem;margin-bottom:0.4rem;">💬</div>
            <div style="font-weight:700;color:#1A1A18;margin-bottom:0.3rem;">1. Intake Agent</div>
            <div style="color:#666;font-size:0.85rem;">Asks 10 questions about your household — income, size, state, age. No SSN needed.</div>
        </div>
        <div style="flex:0;display:flex;align-items:center;color:#ccc;font-size:1.4rem;padding:0 0.2rem;">→</div>
        <div style="flex:1;min-width:180px;background:white;border:1px solid #E8E8E4;border-radius:14px;padding:1.2rem;text-align:center;">
            <div style="font-size:1.6rem;margin-bottom:0.4rem;">⚙️</div>
            <div style="font-weight:700;color:#1A1A18;margin-bottom:0.3rem;">2. Eligibility Agent</div>
            <div style="color:#666;font-size:0.85rem;">Runs your profile through PolicyEngine — the same open-source engine used by governments — across 8 programs.</div>
        </div>
        <div style="flex:0;display:flex;align-items:center;color:#ccc;font-size:1.4rem;padding:0 0.2rem;">→</div>
        <div style="flex:1;min-width:180px;background:white;border:1px solid #E8E8E4;border-radius:14px;padding:1.2rem;text-align:center;">
            <div style="font-size:1.6rem;margin-bottom:0.4rem;">📋</div>
            <div style="font-weight:700;color:#1A1A18;margin-bottom:0.3rem;">3. Recommendation Agent</div>
            <div style="color:#666;font-size:0.85rem;">Generates your report: estimated monthly benefit, documents needed, and direct application links.</div>
        </div>
        <div style="flex:0;display:flex;align-items:center;color:#ccc;font-size:1.4rem;padding:0 0.2rem;">→</div>
        <div style="flex:1;min-width:180px;background:#EEF1F5;border:1px solid #B0C4D8;border-radius:14px;padding:1.2rem;text-align:center;">
            <div style="font-size:1.6rem;margin-bottom:0.4rem;">🔔</div>
            <div style="font-weight:700;color:#1B3A5C;margin-bottom:0.3rem;">4. Monitor Agent</div>
            <div style="color:#2A5480;font-size:0.85rem;">Runs every January on AWS EventBridge. Re-checks your saved profile when FPL guidelines update. Notifies you only if something changed.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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

    # Progress indicator — count non-greeting assistant messages as answered questions
    answered = max(0, sum(1 for m in st.session_state.messages if m["role"] == "user"))
    total_questions = 10
    pct = min(answered / total_questions, 1.0)
    st.progress(pct, text=f"Question {min(answered + 1, total_questions)} of {total_questions}")

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

        profile = extract_json_profile(agent_text)
        if profile and "state" in profile and "monthly_income" in profile:
            st.session_state.profile = profile
            st.session_state.stage = "processing"
            st.rerun()
        elif profile and ("state" not in profile or "monthly_income" not in profile):
            missing = [f for f in ("state", "monthly_income") if f not in profile]
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

    status = st.status("Running AidRadar pipeline...", expanded=True)
    try:
        status.write("🤖 **Intake Agent** — profile collected ✓")
        status.write("⚙️ **Eligibility Agent** — calling PolicyEngine across 8 programs...")
        status.write("📋 **Recommendation Agent** — generating your benefits report...")

        result = run_pipeline(st.session_state.profile)

        if not result.success:
            # Validation errors mean bad intake data — send user back to correct it
            if result.error and result.error.startswith("validation_error:"):
                validation_msg = result.error.replace("validation_error:", "")
                status.update(label="Profile issue detected", state="error", expanded=False)
                st.warning(f"**We found an issue with your answers:** {validation_msg}")
                st.info("Please go back and correct your answers so we can check your eligibility accurately.")
                if st.button("Go Back and Correct", type="primary"):
                    st.session_state.stage = "intake"
                    st.session_state.profile = None
                    st.rerun()
                return
            raise RuntimeError(result.error)

        st.session_state.eligibility_results = result.eligibility_text
        st.session_state.report = result.report_text
        st.session_state.baseline_programs = result.programs
        st.session_state.profile_id = result.profile_id
        st.session_state.state_is_fallback = result.state_is_fallback
        st.session_state.state_original = result.state_original

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
            for key in ["stage", "messages", "intake_agent", "profile", "eligibility_results",
                        "report", "monitor_notifications", "whatif_results", "baseline_programs", "profile_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


# ---------------------------------------------------------------------------
# What If simulator helpers
# ---------------------------------------------------------------------------
def _show_whatif_section(base_profile: dict, original_programs: dict):
    st.markdown("---")
    st.markdown("### What If Simulator")
    st.markdown(
        "Adjust your household details below and see how your eligibility changes — instantly, "
        "using the same real benefit calculation engine."
    )

    orig_income = base_profile.get("monthly_income", 0)

    # intake profile uses children_under_5 + children_k12, not a pre-built children list
    _under5 = base_profile.get("children_under_5") or []
    _k12 = base_profile.get("children_k12") or []
    _children_list = base_profile.get("children") or []
    orig_children = len(_under5) + len(_k12) if (_under5 or _k12) else len(_children_list)

    # intake profile may not have a pre-built adults list — infer from household_size and children
    _adults_list = base_profile.get("adults") or []
    if _adults_list:
        orig_adults = len(_adults_list)
    else:
        orig_adults = max(1, base_profile.get("household_size", 1) - orig_children)

    col1, col2, col3 = st.columns(3)
    with col1:
        wi_income = st.slider("Monthly Income ($/mo)", min_value=0, max_value=10000, value=int(orig_income), step=100, key="wi_income")
        st.caption(f"Current: ${int(orig_income):,}/mo")
    with col2:
        wi_adults = st.slider("Number of Adults", 1, 4, orig_adults, key="wi_adults")
        st.caption(f"Current: {orig_adults}")
    with col3:
        wi_children = st.slider("Number of Children", 0, 6, orig_children, key="wi_children")
        st.caption(f"Current: {orig_children}")

    changed = (wi_income != int(orig_income)) or (wi_adults != orig_adults) or (wi_children != orig_children)

    if changed:
        if st.button("Recalculate Eligibility", type="primary", use_container_width=True, key="wi_calc"):
            with st.spinner("Running eligibility check..."):
                st.session_state.whatif_results = run_whatif(base_profile, wi_income, wi_adults, wi_children)
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
                <div class="benefit-card" style="border-left:4px solid #F4A42A;">
                    <span class="eligible-badge">NOW ELIGIBLE</span>
                    <h4>{name}{amt_str}</h4>
                </div>
                """, unsafe_allow_html=True)
        if changed_amount:
            for name, orig_amt, mod_amt in changed_amount:
                delta = mod_amt - orig_amt
                sign = "+" if delta > 0 else ""
                color = "#1B3A5C" if delta > 0 else "#C0392B"
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
# Notification preference (mock — wired to session state only)
# ---------------------------------------------------------------------------
def _show_notification_preference():
    if "notification_saved" not in st.session_state:
        st.session_state.notification_saved = False
    if "notification_channel" not in st.session_state:
        st.session_state.notification_channel = "email"

    if st.session_state.notification_saved:
        channel = st.session_state.get("notification_value", "")
        st.markdown(f"""
        <div style="background:#EEF1F5;border:1px solid #B0C4D8;border-radius:8px;
                    padding:0.6rem 1rem;margin-bottom:1rem;font-size:0.85rem;color:#1B3A5C;">
            ✅ Notification preference saved — we'll alert <strong>{channel}</strong> if your eligibility changes.
        </div>
        """, unsafe_allow_html=True)
        return

    with st.expander("Set up change notifications", expanded=False):
        st.markdown(
            "<div style='font-size:0.88rem;color:#555;margin-bottom:0.6rem;'>"
            "AidRadar will notify you when the Monitor Agent detects a change in your eligibility "
            "— for example when federal poverty guidelines update each January."
            "</div>",
            unsafe_allow_html=True,
        )
        col_ch, col_val, col_btn = st.columns([1.2, 2.5, 1])
        with col_ch:
            channel = st.selectbox(
                "Notify via",
                ["Email", "Phone (SMS)"],
                label_visibility="collapsed",
                key="notif_channel_select",
            )
        with col_val:
            placeholder = "you@example.com" if channel == "Email" else "+1 (555) 000-0000"
            value = st.text_input(
                "Contact",
                placeholder=placeholder,
                label_visibility="collapsed",
                key="notif_value_input",
            )
        with col_btn:
            if st.button("Save", use_container_width=True, key="save_notification"):
                if value.strip():
                    st.session_state.notification_saved = True
                    st.session_state.notification_value = value.strip()
                    st.rerun()
                else:
                    st.warning("Please enter a value first.")


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

    # Surface out-of-area fallback so the intake promise is kept end-to-end
    if st.session_state.get("state_is_fallback"):
        state_orig = st.session_state.get("state_original") or "your state"
        st.info(
            f"**Note:** AidRadar currently covers California, Texas, New York, and Florida. "
            f"Since you're in **{state_orig}**, your results are based on federal program "
            f"thresholds — state-specific benefit amounts may vary when you apply."
        )

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

        st.markdown("""
        <div style="background:#EEF1F5;border:1px solid #B0C4D8;border-radius:12px;padding:0.9rem 1.2rem;margin-bottom:0.6rem;display:flex;align-items:center;gap:0.8rem;">
            <div style="font-size:1.4rem;">🔔</div>
            <div>
                <div style="font-weight:700;color:#1B3A5C;font-size:0.95rem;">Your profile is saved — AidRadar is watching</div>
                <div style="color:#2A5480;font-size:0.85rem;margin-top:0.2rem;">
                    Every January, federal poverty guidelines update. If your eligibility changes,
                    the Monitor Agent will catch it automatically — no forms to re-fill.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Notification preference
        _show_notification_preference()

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
                cliff_detected = prog.get("cliff_detected", False)

                amount_html = f'<div class="amount">${monthly:,.2f}/mo</div>' if monthly else '<div class="amount">Coverage (no $ estimate)</div>'
                apply_html = f'<div style="margin-top:0.5rem;"><a href="{url}" target="_blank" style="color:#1B3A5C;font-weight:600;">Apply here &rarr;</a></div>' if url else ""

                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid #F4A42A;">
                    <span class="eligible-badge">ELIGIBLE</span>
                    <h4>{name}</h4>
                    {amount_html}
                    {apply_html}
                </div>
                """, unsafe_allow_html=True)

                if cascading:
                    cascade_names = ", ".join(c.replace("_", " ").title() for c in cascading)
                    st.caption(f"\U0001f517 Unlocks: {cascade_names}")

                if cliff_detected:
                    st.warning(
                        f"⚠️ **Benefit cliff detected for {name}:** earning $500/month more could make you ineligible. "
                        "Consider timing income increases carefully.",
                        icon=None,
                    )

        # Ineligible programs
        ineligible = eligibility_data.get("ineligible_programs", [])
        if ineligible:
            st.markdown("### Not Eligible")
            for prog in ineligible:
                name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").replace("_", " ").upper()
                reason = prog.get("reason", "")
                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid #CCCCCC;">
                    <span class="ineligible-badge">NOT ELIGIBLE</span>
                    <h4>{name}</h4>
                    <div style="color:#666;font-size:0.9rem;">{reason}</div>
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
        "Every January, federal poverty guidelines update — and millions of families silently become "
        "eligible for programs they didn't qualify for before. AidRadar's Monitor Agent runs on a "
        "schedule via AWS EventBridge, re-checks every saved profile against the latest PolicyEngine "
        "rules, and **notifies only the people whose eligibility actually changed**. "
        "No login needed. No forms to re-fill."
    )

    st.caption(
        "Your profile is saved in DynamoDB. Click below to simulate a scheduled Monitor Agent run — "
        "it re-checks your eligibility against the latest PolicyEngine rules and reports any changes."
    )

    if st.button("Run Monitor Agent", type="primary", use_container_width=True, key="run_monitor"):
        _run_monitor_demo()

    if st.session_state.monitor_notifications is not None:
        _render_monitor_notifications()

    # Actions
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Over", use_container_width=True):
            for key in ["stage", "messages", "intake_agent", "profile",
                        "eligibility_results", "report", "monitor_notifications", "whatif_results",
                        "baseline_programs", "profile_id", "notification_saved",
                        "notification_value", "notification_channel"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("View Household Profile", use_container_width=True):
            p = st.session_state.profile or {}
            under5 = p.get("children_under_5") or []
            k12 = p.get("children_k12") or []
            total_children = len(under5) + len(k12)
            elderly = p.get("elderly_count", 1 if p.get("has_elderly_65_plus") else 0)
            state_display = p.get("state_original") or p.get("state", "—")
            income_note = " (approximate)" if p.get("income_is_approximate") else ""
            citizenship_map = {
                "us_citizen": "US Citizen",
                "permanent_resident": "Permanent Resident",
                "qualified_immigrant": "Qualified Immigrant",
                "undocumented": "Undocumented",
            }
            citizenship = citizenship_map.get(p.get("citizenship_status", ""), p.get("citizenship_status", "—"))
            current_programs = p.get("current_programs") or []

            st.markdown("**Your Household Profile**")
            st.markdown(f"""
- **State:** {state_display}
- **Household size:** {p.get("household_size", "—")}
- **Monthly income:** ${int(p.get("monthly_income", 0)):,}{income_note}
- **Applicant age:** {p.get("applicant_age", "—")}
- **Children under 5:** {len(under5)} {"— ages: " + ", ".join(str(c.get("age","?")) for c in under5) if under5 else ""}
- **Children in K–12:** {len(k12)} {"— ages: " + ", ".join(str(c.get("age","?")) for c in k12) if k12 else ""}
- **Adults 65 or older:** {elderly if elderly else "None"}
- **Disability in household:** {"Yes" if p.get("has_disabled_member") else "No"}
- **Pregnant member:** {"Yes" if p.get("has_pregnant_member") else "No"}
- **Veteran in household:** {"Yes" if p.get("veteran_in_household") else "No"}
- **Citizenship status:** {citizenship}
- **Currently enrolled in:** {", ".join(current_programs) if current_programs else "None"}
""")


# ---------------------------------------------------------------------------
# Monitor Agent demo
# ---------------------------------------------------------------------------
def _run_monitor_demo():
    status = st.status("Monitor Agent running scheduled check...", expanded=True)
    status.write("Loading saved profile from DynamoDB...")
    status.write("Re-running PolicyEngine eligibility check against current federal guidelines...")
    status.write("Comparing against stored eligibility snapshot...")

    result = run_monitor_check(
        profile_id=st.session_state.profile_id,
        intake_profile=st.session_state.profile,
        baseline_programs=st.session_state.get("baseline_programs", {}),
    )

    if result.error:
        status.update(label="Monitor check failed", state="error")
        st.error(result.error)
        return

    status.update(label="Monitor Agent: check complete", state="complete", expanded=False)

    st.session_state.monitor_notifications = {
        "original_income": result.original_income,
        "new_income": result.new_income,
        "gained": result.gained,
        "lost": result.lost,
        "changed": result.changed,
        "agent_output": result.agent_output,
        "profile_id": result.profile_id,
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
