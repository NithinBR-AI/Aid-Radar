"""
AidRadar — Streamlit web app.
Run with: streamlit run src/app.py
"""

import io
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
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@700;800&display=swap" rel="stylesheet">
<style>
    /* Hide default streamlit branding */
    #MainMenu, footer, header {visibility: hidden;}

    /* Override chat colors to match navy design system */
    [data-testid="stChatMessageAvatarAssistant"] {
        background-color: #1B3A5C !important;
    }
    [data-testid="stChatMessageAvatarUser"] {
        background-color: white !important;
        border: 2px solid #1B3A5C !important;
        box-sizing: border-box !important;
    }
    [data-testid="stChatMessageAvatarUser"] * {
        color: #1B3A5C !important;
        fill: #1B3A5C !important;
    }

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
        font-family: 'Sora', sans-serif;
        font-size: 3.4rem;
        margin-bottom: 0.4rem;
        color: #1B3A5C;
        letter-spacing: -0.03em;
        font-weight: 800;
    }
    .hero .tagline {
        font-size: 1.25rem;
        color: #444;
        margin-bottom: 0.8rem;
        font-weight: 400;
    }
    .hero .stat {
        font-size: 1rem;
        color: white;
        font-weight: 700;
        margin-bottom: 2rem;
        display: inline-block;
        background: #1B3A5C;
        padding: 0.5rem 1.4rem;
        border-radius: 2rem;
        letter-spacing: 0.01em;
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
        background: #1B3A5C;
        color: white;
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
        padding: 2.8rem 2rem;
        margin-top: -1rem;
        background: linear-gradient(135deg, #1B3A5C 0%, #142D48 50%, #0D1E30 100%);
        border-radius: 24px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(27, 58, 92, 0.4);
        position: relative;
        overflow: hidden;
    }
    .big-number::before {
        content: '';
        position: absolute;
        top: -40%;
        right: -10%;
        width: 280px;
        height: 280px;
        background: rgba(244, 164, 42, 0.08);
        border-radius: 50%;
    }
    .big-number::after {
        content: '';
        position: absolute;
        bottom: -50%;
        left: -10%;
        width: 200px;
        height: 200px;
        background: rgba(255,255,255,0.03);
        border-radius: 50%;
    }
    .big-number .value {
        font-family: 'Sora', sans-serif;
        font-size: 4.2rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.03em;
        color: #F4A42A;
        position: relative;
    }
    .big-number .label {
        font-size: 1.05rem;
        opacity: 0.85;
        font-weight: 500;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.8rem;
    }
    .big-number .sub {
        font-size: 0.92rem;
        opacity: 0.7;
        margin-top: 0.6rem;
        position: relative;
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
if "wi_reset_counter" not in st.session_state:
    st.session_state.wi_reset_counter = 0
if "error_programs" not in st.session_state:
    st.session_state.error_programs = []
if "correction_mode" not in st.session_state:
    st.session_state.correction_mode = False
if "is_correction_session" not in st.session_state:
    st.session_state.is_correction_session = False


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

    st.markdown("""
    <div style="margin:-0.5rem 0 1.2rem;padding:1.8rem 2rem;background:white;border-radius:16px;border:1px solid #D6E4F0;">
        <!-- Row 1: Pipeline flow -->
        <div style="display:flex;align-items:stretch;justify-content:center;gap:1rem;margin-bottom:1.4rem;flex-wrap:wrap;">
            <div style="text-align:center;padding:1rem 1.2rem;background:#EEF1F5;border:1px solid #D6E4F0;border-radius:12px;min-width:100px;">
                <div style="font-size:1.6rem;margin-bottom:0.3rem;">👨‍👩‍👧</div>
                <div style="font-size:0.72rem;color:#1B3A5C;font-weight:700;letter-spacing:0.05em;">YOUR HOUSEHOLD</div>
            </div>
            <div style="color:#D6E4F0;font-size:1.8rem;line-height:1;">→</div>
            <div style="text-align:center;padding:1rem 1.4rem;background:linear-gradient(135deg,#1B3A5C 0%,#2A5480 100%);border-radius:12px;min-width:100px;">
                <div style="font-size:1.6rem;margin-bottom:0.3rem;">💬</div>
                <div style="font-size:0.72rem;color:white;font-weight:700;letter-spacing:0.05em;">INTAKE</div>
                <div style="font-size:0.62rem;color:#A8C4DC;margin-top:0.15rem;">10 questions</div>
            </div>
            <div style="color:#D6E4F0;font-size:1.8rem;line-height:1;">→</div>
            <div style="text-align:center;padding:1rem 1.4rem;background:linear-gradient(135deg,#1B3A5C 0%,#2A5480 100%);border-radius:12px;min-width:100px;">
                <div style="font-size:1.6rem;margin-bottom:0.3rem;">⚙️</div>
                <div style="font-size:0.72rem;color:white;font-weight:700;letter-spacing:0.05em;">ELIGIBILITY</div>
                <div style="font-size:0.62rem;color:#A8C4DC;margin-top:0.15rem;">PolicyEngine</div>
            </div>
            <div style="color:#D6E4F0;font-size:1.8rem;line-height:1;">→</div>
            <div style="text-align:center;padding:1rem 1.4rem;background:linear-gradient(135deg,#1B3A5C 0%,#2A5480 100%);border-radius:12px;min-width:100px;">
                <div style="font-size:1.6rem;margin-bottom:0.3rem;">📋</div>
                <div style="font-size:0.72rem;color:white;font-weight:700;letter-spacing:0.05em;">REPORT</div>
                <div style="font-size:0.62rem;color:#A8C4DC;margin-top:0.15rem;">Action plan</div>
            </div>
            <div style="color:#D6E4F0;font-size:1.8rem;line-height:1;">→</div>
            <div style="text-align:center;padding:1rem 1.4rem;background:linear-gradient(135deg,#142D48 0%,#1B3A5C 100%);border-radius:12px;min-width:100px;border:1px solid #2A5480;">
                <div style="font-size:1.6rem;margin-bottom:0.3rem;">🔔</div>
                <div style="font-size:0.72rem;color:white;font-weight:700;letter-spacing:0.05em;">MONITOR</div>
                <div style="font-size:0.62rem;color:#A8C4DC;margin-top:0.15rem;">Annual re-check</div>
            </div>
        </div>
        <!-- Divider label -->
        <div style="text-align:center;font-size:0.7rem;color:#B0C4D8;font-weight:600;letter-spacing:0.08em;margin-bottom:1rem;">8 PROGRAMS CHECKED IN ONE RUN</div>
        <!-- Row 2: Programs -->
        <div style="display:flex;gap:0.5rem;justify-content:center;flex-wrap:wrap;">
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">SNAP</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">Medicaid</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">WIC</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">SSI</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">Lifeline</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">TANF</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">LIHEAP</div>
            <div style="background:#EEF1F5;border-left:3px solid #1B3A5C;border-radius:6px;padding:0.3rem 0.9rem;font-size:0.75rem;color:#1B3A5C;font-weight:600;">Free School Meals</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.2rem;'></div>", unsafe_allow_html=True)
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

    st.markdown('<h3 style="font-family:\'Sora\',sans-serif;color:#1B3A5C;letter-spacing:-0.02em;margin-bottom:0.2rem;">Tell us about your household</h3>', unsafe_allow_html=True)

    # Correction mode: user came back from the confirmation screen to fix something.
    # Kick off a fresh agent pre-loaded with the existing profile so they only need
    # to say what changed — not re-answer all 10 questions.
    if st.session_state.get("correction_mode") and not st.session_state.messages:
        existing = st.session_state.get("profile") or {}
        import json as _json
        correction_seed = (
            "SYSTEM NOTE (not shown to user): The user reviewed their profile and wants to correct something. "
            "Here is the profile we captured so far:\n"
            f"{_json.dumps(existing, indent=2)}\n\n"
            "Ask the user ONE question: 'Which part of your profile would you like to correct? '  "
            "Once they tell you what to fix, ask only the follow-up questions needed to update that field. "
            "When everything is corrected, output the full updated profile JSON block as usual."
        )
        st.session_state.intake_agent = create_intake_agent()
        with st.spinner("Loading your profile for correction..."):
            result = st.session_state.intake_agent(correction_seed)
        agent_text = str(result)
        st.session_state.messages.append({"role": "assistant", "content": agent_text})
        st.session_state.correction_mode = False
        st.session_state.is_correction_session = True
        st.rerun()

    # Progress indicator
    if st.session_state.get("is_correction_session"):
        st.caption("✏️ Correcting your profile — tell us what to fix")
    else:
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

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # On the very first user message in a normal intake (state answer), prepend context
                # so the agent doesn't re-greet or skip household_size.
                # Skip this priming in correction mode — the agent already has context.
                user_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
                if user_count == 1 and not st.session_state.get("is_correction_session"):
                    primed_input = (
                        "SYSTEM NOTE (not from user): You already greeted the user and asked "
                        "what state they live in. Their answer follows. Do NOT re-greet. "
                        "After processing their state, your NEXT question MUST be household size: "
                        "'How many people total live in your household, including yourself?' "
                        "Do not skip this question.\n\n"
                        f"USER: {user_input}"
                    )
                    result = st.session_state.intake_agent(primed_input)
                else:
                    result = st.session_state.intake_agent(user_input)
                agent_text = str(result)

        st.session_state.messages.append({"role": "assistant", "content": agent_text})

        profile = extract_json_profile(agent_text)
        if profile and "state" in profile and "monthly_income" in profile:
            # Headcount sanity check — catch impossible households before confirmation
            _under5 = len(profile.get("children_under_5") or [])
            _k12 = len(profile.get("children_k12") or [])
            _elderly = int(profile.get("elderly_count") or 0)
            _hsize = int(profile.get("household_size") or 1)
            _min_needed = _under5 + _k12 + _elderly + 1  # +1 for applicant
            if _hsize < _min_needed:
                feedback = (
                    f"I noticed a mismatch in your household numbers: you listed "
                    f"{_under5} child{'ren' if _under5 != 1 else ''} under 5, "
                    f"{_k12} school-age child{'ren' if _k12 != 1 else ''}, and "
                    f"{_elderly} elderly member{'s' if _elderly != 1 else ''} — "
                    f"that's at least {_min_needed} people including yourself, "
                    f"but you said your household size is {_hsize}. "
                    f"Can you confirm the total number of people in your household?"
                )
                st.session_state.messages.append({"role": "assistant", "content": feedback})
                with st.chat_message("assistant"):
                    st.markdown(feedback)
                st.rerun()
            else:
                st.session_state.profile = profile
                st.session_state.stage = "confirm_profile"
                st.rerun()
        elif profile and ("state" not in profile or "monthly_income" not in profile):
            missing = [f for f in ("state", "monthly_income") if f not in profile]
            with st.chat_message("assistant"):
                st.warning(f"Profile captured but missing required fields: {', '.join(missing)}. Continuing interview...")
            st.rerun()
        else:
            st.rerun()


# ---------------------------------------------------------------------------
# Profile confirmation diff — structured review before pipeline runs
# ---------------------------------------------------------------------------
def show_confirm_profile():
    profile = st.session_state.get("profile", {})
    render_pipeline("eligibility")
    st.markdown("#### Does this look right?")
    st.caption("We parsed your answers into the profile below. Confirm to run the eligibility check, or go back to correct anything.")

    children_under_5 = profile.get("children_under_5") or []
    children_k12 = profile.get("children_k12") or []
    total_children = len(children_under_5) + len(children_k12)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("State", profile.get("state", "—"))
        st.metric("Household size", profile.get("household_size", "—"))
        st.metric("Monthly income", f"${profile.get('monthly_income', 0):,.0f}" + (" (approx)" if profile.get("income_is_approximate") else ""))
        st.metric("Applicant age", profile.get("applicant_age", "—"))
    with col2:
        st.metric("Children", total_children)
        st.metric("Elderly members (65+)", profile.get("elderly_count", 0))
        st.metric("Veteran in household", "Yes" if profile.get("veteran_in_household") else "No")
        st.metric("Citizenship", (profile.get("citizenship_status") or "not provided").replace("_", " ").title())

    flags = []
    if profile.get("has_disabled_member"):
        flags.append("Disabled member")
    if profile.get("has_pregnant_member"):
        flags.append("Pregnant member")
    if profile.get("current_programs"):
        flags.append(f"Currently enrolled: {', '.join(profile['current_programs'])}")
    if flags:
        st.info(" · ".join(flags))

    col_confirm, col_back = st.columns([1, 1])
    with col_confirm:
        if st.button("✓ Looks right — check my eligibility", type="primary", use_container_width=True):
            st.session_state.stage = "processing"
            st.rerun()
    with col_back:
        if st.button("← Something's wrong — go back", use_container_width=True):
            st.session_state.stage = "intake"
            st.session_state.correction_mode = True
            st.session_state.intake_agent = None
            st.session_state.messages = []
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
        st.session_state.error_programs = result.error_programs

        status.update(label="Pipeline complete!", state="complete", expanded=False)
        st.session_state.stage = "results"
        st.rerun()

    except Exception as e:
        logger.error("show_processing pipeline_error error=%s", e)
        status.update(label="Pipeline error", state="error", expanded=False)
        st.error(
            "The eligibility check failed — this is usually a temporary issue with the AI model. "
            "Click below to try again."
        )
        if st.button("Retry", type="primary"):
            st.rerun()
        if st.button("Start Over"):
            for key in ["stage", "messages", "intake_agent", "profile", "eligibility_results",
                        "report", "monitor_notifications", "whatif_results", "baseline_programs",
                        "profile_id", "error_programs", "notification_saved", "notification_value",
                        "notification_channel", "wi_reset_counter", "correction_mode", "is_correction_session"]:
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

    orig_income = base_profile.get("monthly_income") or 0

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

    _rc = st.session_state.wi_reset_counter
    col1, col2, col3 = st.columns(3)
    with col1:
        wi_income = st.slider("Monthly Income ($/mo)", min_value=0, max_value=10000, value=int(orig_income), step=100, key=f"wi_income_{_rc}")
        st.caption(f"Current: ${int(orig_income):,}/mo")
    with col2:
        wi_adults = st.slider("Number of Adults", 1, 4, orig_adults, key=f"wi_adults_{_rc}")
        st.caption(f"Current: {orig_adults}")
    with col3:
        wi_children = st.slider("Number of Children", 0, 6, orig_children, key=f"wi_children_{_rc}")
        st.caption(f"Current: {orig_children}")

    changed = (wi_income != int(orig_income)) or (wi_adults != orig_adults) or (wi_children != orig_children)

    col_calc, col_reset = st.columns([3, 1])
    with col_calc:
        if changed:
            if st.button("Recalculate Eligibility", type="primary", use_container_width=True, key="wi_calc"):
                with st.spinner("Running eligibility check..."):
                    result = run_whatif(base_profile, wi_income, wi_adults, wi_children)
                if not result:
                    st.error("Could not calculate eligibility for this scenario — please try different values.")
                else:
                    st.session_state.whatif_results = result
                    st.rerun()
        else:
            st.caption("Adjust the sliders above to explore different scenarios.")
    with col_reset:
        if changed:
            if st.button("Reset", use_container_width=True, key="wi_reset"):
                st.session_state.wi_reset_counter += 1
                st.session_state.whatif_results = None
                st.rerun()

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
# PDF report generation
# ---------------------------------------------------------------------------
def _build_pdf_report(profile: dict, eligibility_data: dict, report_text: str) -> bytes:
    from fpdf import FPDF

    NAV = (27, 58, 92)       # brand navy
    NAV_LIGHT = (238, 241, 245)  # light navy tint
    GREEN = (46, 125, 50)    # eligible green
    GREY = (120, 120, 120)   # ineligible grey
    WHITE = (255, 255, 255)
    DARK = (30, 30, 30)

    class _PDF(FPDF):
        def header(self):
            self.set_fill_color(*NAV)
            self.rect(0, 0, 210, 22, "F")
            self.set_y(5)
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*WHITE)
            self.cell(0, 8, "AidRadar", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(180, 200, 220)
            self.cell(0, 5, "Benefits Eligibility Report", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_y(26)
            self.set_text_color(*DARK)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*GREY)
            self.cell(0, 6, "Generated by AidRadar  ·  For informational purposes only  ·  Verify eligibility with official program offices", align="C")

        def section_title(self, text: str):
            self.ln(3)
            self.set_fill_color(*NAV_LIGHT)
            self.set_draw_color(*NAV)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*NAV)
            self.set_x(15)
            self.cell(0, 7, text, border="L", fill=True, new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*DARK)
            self.ln(2)

        def kv_row(self, label: str, value: str):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*GREY)
            self.set_x(18)
            self.cell(52, 6, label.upper(), new_x="END", new_y="TOP")
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*DARK)
            self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")

    def _safe(text: str) -> str:
        """Strip/replace characters outside Latin-1 so Helvetica doesn't choke."""
        return (str(text)
                .replace("—", " - ").replace("–", " - ")
                .replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("•", "-").replace("…", "...")
                .encode("latin-1", errors="replace").decode("latin-1"))

    pdf = _PDF()
    pdf.set_margins(15, 28, 15)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # ── Big number summary banner ──────────────────────────────────────────
    total_monthly = eligibility_data.get("total_estimated_monthly_benefit", 0) or 0
    total_annual = eligibility_data.get("total_estimated_annual_benefit", 0) or 0
    eligible_count = len(eligibility_data.get("eligible_programs", []))

    pdf.set_fill_color(*NAV_LIGHT)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAV)
    pdf.cell(0, 12, f"${total_monthly:,.0f}/month", align="C", fill=False, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _safe(f"${total_annual:,.0f}/year  -  {eligible_count} eligible program{'s' if eligible_count != 1 else ''}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Household summary ─────────────────────────────────────────────────
    pdf.section_title("Household Summary")
    state_display = profile.get("state", "N/A")
    under5 = len(profile.get("children_under_5") or [])
    k12 = len(profile.get("children_k12") or [])
    elderly = int(profile.get("elderly_count") or 0)
    disability = "Yes" if profile.get("has_disabled_member") else "No"
    pregnant = "Yes" if profile.get("has_pregnant_member") else "No"
    veteran = "Yes" if profile.get("veteran_in_household") else "No"
    citizenship = _safe(str(profile.get("citizenship_status") or "Not provided").replace("_", " ").title())
    current_programs = profile.get("current_programs") or []
    enrolled = _safe(", ".join(current_programs) if current_programs else "None")

    pdf.kv_row("State", _safe(str(state_display)))
    pdf.kv_row("Household size", _safe(str(profile.get("household_size", "N/A"))))
    pdf.kv_row("Monthly income", f"${int(profile.get('monthly_income') or 0):,}")
    pdf.kv_row("Applicant age", _safe(str(profile.get("applicant_age", "N/A"))))
    pdf.kv_row("Children under 5", str(under5))
    pdf.kv_row("Children in K-12", str(k12))
    pdf.kv_row("Adults 65 or older", str(elderly))
    pdf.kv_row("Disability in household", disability)
    pdf.kv_row("Pregnant member", pregnant)
    pdf.kv_row("Veteran in household", veteran)
    pdf.kv_row("Citizenship status", citizenship)
    pdf.kv_row("Currently enrolled in", enrolled)

    # ── Eligible programs ─────────────────────────────────────────────────
    eligible = eligibility_data.get("eligible_programs", [])
    pdf.section_title(f"Eligible Programs ({eligible_count})")

    if eligible:
        for prog in eligible:
            name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").upper()
            monthly = prog.get("estimated_monthly_benefit")
            url = prog.get("apply_url") or prog.get("application_url", "")
            docs = prog.get("required_documents") or []
            cascading = prog.get("cascading_benefits") or []

            # Green accent bar
            pdf.set_fill_color(*GREEN)
            pdf.rect(15, pdf.get_y(), 2, 10, "F")

            pdf.set_x(19)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*GREEN)
            amt_str = f"  -  ${monthly:,.2f}/mo" if monthly else "  -  Coverage benefit"
            pdf.cell(0, 6, _safe(f"{name}{amt_str}"), new_x="LMARGIN", new_y="NEXT")

            if url:
                pdf.set_x(19)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(*NAV)
                pdf.multi_cell(0, 4, _safe(f"Apply: {url}"), new_x="LMARGIN", new_y="NEXT")

            if docs:
                pdf.set_x(19)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(0, 4, _safe(f"Documents: {', '.join(docs)}"), new_x="LMARGIN", new_y="NEXT")

            if cascading:
                pdf.set_x(19)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*GREY)
                names = ", ".join(c.replace("_", " ").title() for c in cascading)
                pdf.multi_cell(0, 4, _safe(f"Unlocks: {names}"), new_x="LMARGIN", new_y="NEXT")

            pdf.set_text_color(*DARK)
            pdf.ln(2)
    else:
        pdf.set_x(18)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(0, 6, "No eligible programs found.", new_x="LMARGIN", new_y="NEXT")

    # ── Ineligible programs ───────────────────────────────────────────────
    ineligible = eligibility_data.get("ineligible_programs", [])
    if ineligible:
        pdf.section_title(f"Not Currently Eligible ({len(ineligible)})")
        for prog in ineligible:
            name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").upper()
            reason = prog.get("reason", "")
            pdf.set_x(19)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*GREY)
            pdf.cell(0, 5, _safe(name + (f"  -  {reason}" if reason else "")), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*DARK)

    # Full narrative page intentionally omitted — page 1 program cards are the complete output.

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Results dashboard
# ---------------------------------------------------------------------------
def _parse_eligibility_json(text: str) -> dict | None:
    # Try fenced blocks first
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match)
            if "eligible_programs" in data or "programs" in data:
                return data
        except json.JSONDecodeError:
            continue
    # Fallback: plain JSON string (e.g. from model_dump_json())
    try:
        data = json.loads(text)
        if isinstance(data, dict) and ("eligible_programs" in data or "programs" in data):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def show_results():
    render_pipeline("recommendation")

    eligibility_data = _parse_eligibility_json(st.session_state.eligibility_results or "")

    _err_progs = st.session_state.get("error_programs") or []
    if _err_progs:
        st.warning(
            f"**Note:** {', '.join(p.upper() for p in _err_progs)} could not be assessed due to a calculation error. "
            "Contact a benefits counselor to check eligibility for these programs."
        )

    if not eligibility_data:
        st.info("Could not parse structured eligibility data — showing the full agent report below.")
        st.markdown(st.session_state.report or st.session_state.eligibility_results or "")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start Over", use_container_width=True, key="fallback_start_over"):
                for key in ["stage", "messages", "intake_agent", "profile",
                            "eligibility_results", "report", "monitor_notifications",
                            "whatif_results", "baseline_programs", "profile_id",
                            "error_programs", "notification_saved", "notification_value",
                            "notification_channel", "wi_reset_counter", "correction_mode", "is_correction_session"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        return

    # Big number header
    if eligibility_data:
        total_monthly = eligibility_data.get("total_estimated_monthly_benefit", 0)
        total_annual = eligibility_data.get("total_estimated_annual_benefit", 0)
        eligible_count = len(eligibility_data.get("eligible_programs", []))

        if total_monthly and total_monthly > 0:
            hero_value = f"${total_monthly:,.0f}/month"
            hero_sub = f"${total_annual:,.0f}/year across {eligible_count} program{'s' if eligible_count != 1 else ''}"
        else:
            prog_word = "program" if eligible_count == 1 else "programs"
            hero_value = f"{eligible_count} {prog_word}"
            hero_sub = "Coverage benefits — apply to confirm amounts"

        st.markdown(f"""
        <div class="big-number">
            <div class="label">You may be eligible for</div>
            <div class="value">{hero_value}</div>
            <div class="sub">{hero_sub}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Estimates based on PolicyEngine microsimulation — verify eligibility with the program office before applying.")

        st.markdown("""
        <div style="background:#EEF1F5;border:1px solid #B0C4D8;border-radius:12px;padding:0.9rem 1.2rem;margin-bottom:0.6rem;display:flex;align-items:center;gap:0.8rem;">
            <div style="width:2rem;height:2rem;flex-shrink:0;display:flex;align-items:center;justify-content:center;">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#1B3A5C" width="22" height="22"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6V11c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
            </div>
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
                url = prog.get("apply_url") or prog.get("application_url", "")
                cascading = prog.get("cascading_benefits") or []
                docs = prog.get("required_documents") or []

                amount_html = f'<div class="amount">${monthly:,.2f}/mo</div>' if monthly else '<div style="font-size:0.9rem;color:#666;margin-top:0.4rem;">Coverage benefit — no $ estimate available</div>'
                apply_html = f'<div style="margin-top:0.6rem;"><a href="{url}" target="_blank" style="color:#1B3A5C;font-weight:700;text-decoration:none;">Apply here &rarr;</a></div>' if url else ""

                # Cascading benefits as inline chips
                if cascading:
                    chip_html = "".join(
                        f'<span style="display:inline-block;background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7;border-radius:20px;padding:0.1rem 0.55rem;font-size:0.72rem;font-weight:600;margin:0.15rem 0.15rem 0 0;">{c.replace("_"," ").title()}</span>'
                        for c in cascading
                    )
                    cascade_html = f'<div style="margin-top:0.5rem;"><span style="font-size:0.75rem;color:#888;margin-right:0.3rem;">Unlocks</span>{chip_html}</div>'
                else:
                    cascade_html = ""

                st.markdown(f"""
                <div class="benefit-card" style="border-left:4px solid #1B3A5C;">
                    <span class="eligible-badge">ELIGIBLE</span>
                    <h4>{name}</h4>
                    {amount_html}
                    {apply_html}
                    {cascade_html}
                </div>
                """, unsafe_allow_html=True)

                # Required documents — expandable, doesn't bloat the card
                if docs:
                    with st.expander(f"Documents needed for {name}", expanded=False):
                        for doc in docs:
                            st.markdown(f"- {doc}")

        # Ineligible programs
        ineligible = eligibility_data.get("ineligible_programs", [])
        if ineligible:
            st.markdown("### Not Eligible")
            cols_in = st.columns(2)
            for i, prog in enumerate(ineligible):
                with cols_in[i % 2]:
                    name = prog.get("display_name") or prog.get("program_name") or prog.get("program_id", "").replace("_", " ").upper()
                    reason = prog.get("reason", "")
                    st.markdown(f"""
                    <div class="benefit-card" style="border-left:4px solid #CCCCCC;">
                        <span class="ineligible-badge">NOT ELIGIBLE</span>
                        <h4>{name}</h4>
                        <div style="color:#666;font-size:0.9rem;">{reason}</div>
                    </div>
                    """, unsafe_allow_html=True)


    # What If simulator callout — anchors it visually before the fold
    if st.session_state.profile:
        st.markdown("""
        <div id="whatif-anchor" style="background:#EEF1F5;border:1px solid #B0C4D8;border-radius:12px;
                    padding:0.8rem 1.2rem;margin:0.5rem 0 0;display:flex;align-items:center;gap:0.8rem;">
            <div style="font-size:1.4rem;">🔢</div>
            <div>
                <div style="font-weight:700;color:#1B3A5C;font-size:0.95rem;">What If Simulator — below</div>
                <div style="color:#2A5480;font-size:0.85rem;margin-top:0.1rem;">
                    Change your income, household size, or number of children to instantly see how your eligibility shifts.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        original_programs = st.session_state.get("baseline_programs") or {}
        _show_whatif_section(st.session_state.profile, original_programs)

    # Full report
    st.markdown("---")
    with st.expander("Full Benefits Report", expanded=False):
        st.markdown(st.session_state.report)

    # Monitor Agent demo
    st.markdown("---")
    st.markdown("### Monitor Agent")
    st.info(
        "**What this does:** Re-runs your eligibility check against the latest federal poverty guidelines "
        "and alerts you if anything changed — the same check that runs automatically every January on AWS EventBridge. "
        "Click below to simulate it now.",
        icon="🔔",
    )

    if st.button("Run Monitor Agent", type="primary", use_container_width=True, key="run_monitor"):
        _run_monitor_demo()

    if st.session_state.monitor_notifications is not None:
        _render_monitor_notifications()

    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Start Over", use_container_width=True):
            for key in ["stage", "messages", "intake_agent", "profile",
                        "eligibility_results", "report", "monitor_notifications", "whatif_results",
                        "baseline_programs", "profile_id", "error_programs", "notification_saved",
                        "notification_value", "notification_channel", "correction_mode", "is_correction_session"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if eligibility_data and st.session_state.profile:
            try:
                pdf_bytes = _build_pdf_report(
                    st.session_state.profile,
                    eligibility_data,
                    st.session_state.report or "",
                )
                st.download_button(
                    "Download Report (PDF)",
                    data=pdf_bytes,
                    file_name="aidradar_benefits_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as _pdf_err:
                st.button("Download Report (PDF)", disabled=True, use_container_width=True, help=f"PDF error: {_pdf_err}")
    with col3:
        if st.button("View Household Profile", use_container_width=True):
            p = st.session_state.profile or {}
            under5 = p.get("children_under_5") or []
            k12 = p.get("children_k12") or []
            total_children = len(under5) + len(k12)
            elderly = p.get("elderly_count", 1 if p.get("has_elderly_65_plus") else 0)
            state_display = p.get("state", "—")
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
- **Monthly income:** ${int(p.get("monthly_income") or 0):,}{income_note}
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
        <div style="color:#555;font-size:0.85rem;margin-top:0.3rem;">
            Profile re-checked at <strong>${orig:,}/mo</strong> · PolicyEngine re-run against current rules · Diff against stored snapshot.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        for name in gained:
            st.markdown(f"""
            <div class="notif-card">
                <div class="notif-tier low">NEWLY ELIGIBLE</div>
                <h4>{name}</h4>
                <p>You are now eligible. Apply as soon as possible.</p>
            </div>
            """, unsafe_allow_html=True)
        for name, prev_amt, curr_amt in changed:
            delta = curr_amt - prev_amt
            sign = "+" if delta > 0 else ""
            st.markdown(f"""
            <div class="notif-card medium">
                <div class="notif-tier medium">AMOUNT CHANGED</div>
                <h4>{name}</h4>
                <p>${prev_amt:,.0f}/mo → ${curr_amt:,.0f}/mo ({sign}${delta:,.0f})</p>
            </div>
            """, unsafe_allow_html=True)
    with col2:
        for name in lost:
            st.markdown(f"""
            <div class="notif-card high">
                <div class="notif-tier high">LOST ELIGIBILITY</div>
                <h4>{name}</h4>
                <p>You may no longer qualify. Update your profile if your situation changed.</p>
            </div>
            """, unsafe_allow_html=True)

    if not gained and not lost and not changed:
        st.info("No eligibility changes — your current programs are unaffected by the latest federal guidelines.")

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
    elif stage == "confirm_profile":
        show_confirm_profile()
    elif stage == "processing":
        show_processing()
    elif stage == "results":
        show_results()


if __name__ == "__main__":
    main()
