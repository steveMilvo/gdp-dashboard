"""Aged Care Sentinel — Phase 0 prototype (Streamlit).

A camera-free, per-resident early-warning dashboard running on simulated ambient-sensing
data. Demonstrates the live board, per-resident baseline/drift + watchlist, tiered
alerts, role-typed LLM reports, onboarding, and the self-improving feedback loop.

Run:   streamlit run sentinel_app.py
Optional LLM reports:   export ANTHROPIC_API_KEY=sk-...   (otherwise templated fallback)
"""

from __future__ import annotations

import streamlit as st

from sentinel import alerts, data, reports, signals, simulator
from sentinel.signals import TIER_EMOJI, TIER_RANK

st.set_page_config(page_title="Aged Care Sentinel", page_icon="🛰️", layout="wide")


@st.cache_data
def load_state():
    """Simulated feed + per-resident assessment for the whole wing (cached)."""
    snap = simulator.snapshot()
    assessments = {
        r.id: signals.assess(r, snap[r.id]["history"], snap[r.id]["realtime"])
        for r in data.roster()
    }
    return snap, assessments


snap, assessments = load_state()
st.session_state.setdefault("feedback", [])   # self-improving loop: outcome labels
st.session_state.setdefault("acks", set())    # acknowledged alerts


# --------------------------------------------------------------------------- views
def live_board():
    st.title("🛰️ Sentinel — Wing A live board")
    st.caption("Camera-free ambient monitoring · per-resident early warning · simulated feed")

    counts = {"RED": 0, "AMBER": 0, "YELLOW": 0, "GREEN": 0}
    for r in data.roster():
        counts[assessments[r.id].status] += 1
    c = st.columns(4)
    c[0].metric("🔴 Red (life-safety)", counts["RED"])
    c[1].metric("🟠 Amber (clinical)", counts["AMBER"])
    c[2].metric("🟡 Yellow (watch)", counts["YELLOW"])
    c[3].metric("🟢 Green", counts["GREEN"])

    st.subheader("Needs attention this shift")
    ranked = sorted(data.roster(),
                    key=lambda r: TIER_RANK[assessments[r.id].status], reverse=True)
    any_attention = False
    for r in ranked:
        a = assessments[r.id]
        if a.status in ("GREEN", "YELLOW"):
            continue
        any_attention = True
        top = a.alerts[0].title if a.alerts else a.flags[0].title
        pol = alerts.policy(a.status)
        col = st.columns([6, 2])
        col[0].markdown(
            f"{TIER_EMOJI[a.status]} **{r.name}** · {r.room} — {top}  \n"
            f"<span style='color:gray'>{pol['channel']}</span>", unsafe_allow_html=True)
        key = f"ack-{r.id}"
        if pol["ack_required"]:
            if r.id in st.session_state.acks:
                col[1].success("Acknowledged")
            elif col[1].button("Acknowledge", key=key):
                st.session_state.acks.add(r.id)
                st.rerun()
    if not any_attention:
        st.success("No residents currently need attention.")

    st.subheader("All rooms")
    cols = st.columns(4)
    for i, r in enumerate(data.roster()):
        a = assessments[r.id]
        rt = snap[r.id]["realtime"]
        with cols[i % 4]:
            st.markdown(
                f"### {TIER_EMOJI[a.status]} {r.room}\n"
                f"**{r.name}**, {r.age}  \n"
                f"HR {rt['heart_rate']} · {rt['breathing_rate']}/min  \n"
                f"{rt['presence']} · {rt['motion']}")


def resident_detail():
    st.title("Resident detail")
    names = {f"{r.name} — {r.room}": r.id for r in data.roster()}
    label = st.selectbox("Resident", list(names))
    rid = names[label]
    r = data.get_resident(rid)
    a = assessments[rid]
    hist = snap[rid]["history"]
    rt = snap[rid]["realtime"]

    st.header(f"{TIER_EMOJI[a.status]} {r.name} · {r.room} · status {a.status}")
    st.caption(f"{r.profile.care_level} care · mobility {r.profile.mobility} · "
               f"{'dementia · ' if r.profile.dementia else ''}"
               f"{'fall history · ' if r.profile.fall_history else ''}"
               f"meds: {', '.join(r.profile.medications) or 'none'}")

    if a.alerts:
        for al in a.alerts:
            st.error(f"🔴 **{al.title}** — {al.detail}\n\nAction: {al.action}")

    st.subheader("Things to watch for")
    if a.watchlist:
        for w in a.watchlist:
            st.markdown(f"- {TIER_EMOJI[w['tier']]} **{w['title']}** — {w['action']}")
    else:
        st.write("Nothing flagged — within this resident's normal baseline.")

    st.subheader("Real-time")
    rc = st.columns(4)
    rc[0].metric("Heart rate", f"{rt['heart_rate']} bpm")
    rc[1].metric("Breathing", f"{rt['breathing_rate']} /min")
    rc[2].metric("Presence", rt["presence"])
    rc[3].metric("Motion", rt["motion"])

    st.subheader("Trends vs baseline (14 days)")
    show = ["night_bathroom_trips", "resting_hr", "sleep_fragmentation", "gait_speed"]
    tc = st.columns(2)
    for i, m in enumerate(show):
        with tc[i % 2]:
            st.caption(data.METRICS[m]["label"])
            st.line_chart(hist.set_index("date")[[m]], height=160)

    if a.flags:
        st.subheader("Trend flags & feedback (self-improving loop)")
        st.caption("Labelling outcomes trains the per-resident baseline and the signal "
                   "library. Life-safety thresholds never auto-tune without clinical review.")
        for j, f in enumerate(a.flags):
            st.markdown(f"**{TIER_EMOJI[f.tier]} {f.title}**")
            for rat in f.rationale:
                st.markdown(f"  - {rat}")
            outcome = st.radio(
                "Outcome", ["— not reviewed —", "Confirmed", "False alarm", "No action needed"],
                key=f"fb-{rid}-{j}", horizontal=True)
            if outcome != "— not reviewed —":
                record = {"resident": r.name, "flag": f.title, "outcome": outcome}
                if record not in st.session_state.feedback:
                    st.session_state.feedback.append(record)


def reports_view():
    st.title("Reports")
    if not __import__("os").getenv("ANTHROPIC_API_KEY"):
        st.info("No `ANTHROPIC_API_KEY` set — reports use a deterministic template. "
                "Set the key for Claude-written narratives.")

    tab1, tab2 = st.tabs(["Per-resident", "Management"])
    with tab1:
        names = {f"{r.name} — {r.room}": r.id for r in data.roster()}
        rid = names[st.selectbox("Resident", list(names), key="rep-res")]
        kind = st.radio("Report type", ["Carer shift-handoff", "Doctor / clinical", "Incident"],
                        horizontal=True)
        if st.button("Generate report"):
            r = data.get_resident(rid)
            a = assessments[rid]
            with st.spinner("Writing report…"):
                if kind == "Carer shift-handoff":
                    out = reports.carer_report(r, a)
                elif kind == "Doctor / clinical":
                    out = reports.doctor_report(r, a, snap[rid]["history"])
                else:
                    out = reports.incident_report(r, a, snap[rid]["realtime"])
            st.markdown(out)

    with tab2:
        if st.button("Generate management summary"):
            with st.spinner("Writing summary…"):
                st.markdown(reports.management_report(assessments))


def onboarding_view():
    st.title("Onboarding a resident")
    st.caption("Intake + consent + node binding. Baseline is seeded from the profile and "
               "cohort priors, then personalises over ~1–2 weeks.")
    with st.form("intake"):
        c = st.columns(2)
        name = c[0].text_input("Name")
        room = c[1].text_input("Room", "A-108")
        age = c[0].number_input("Age", 60, 110, 82)
        care = c[1].selectbox("Care level", ["Low", "Medium", "High"])
        mobility = c[0].selectbox("Mobility", ["Independent", "Cane", "Walker", "Wheelchair"])
        continence = c[1].selectbox("Continence", ["Continent", "Occasional", "Incontinent"])
        dementia = c[0].checkbox("Dementia")
        falls = c[1].checkbox("History of falls")
        meds = st.text_input("Medications (comma-separated)")
        node = st.text_input("Node binding (tap NFC tag / enter node ID)", "NODE-A108-01")
        consent = st.checkbox("Consent captured (resident or guardian)", value=True)
        submitted = st.form_submit_button("Register resident")
    if submitted:
        if not name or not consent:
            st.error("Name and consent are required.")
        else:
            st.success(f"Registered **{name}** in {room}, bound to `{node}`. "
                       "Baseline seeding from profile + cohort priors; personal baseline "
                       "will form over the next ~1–2 weeks.")
            st.caption("(Prototype — not persisted to the demo roster.)")


def about_view():
    st.title("How Sentinel works")
    st.markdown(
        "**One engine, many views.** A per-resident baseline (\"digital twin\") plus drift "
        "detection feeds the live board, the role-typed reports, and the watchlist. "
        "See `PLAN.md` for the full architecture and the hardware/deployment design.")
    st.subheader("Self-improving loop — captured outcomes")
    if st.session_state.feedback:
        st.dataframe(st.session_state.feedback, use_container_width=True)
        st.caption("These labels would refine per-resident baselines and the clinical signal "
                   "library (human-in-the-loop; life-safety thresholds gated on clinical review).")
    else:
        st.write("No outcomes labelled yet — review trend flags on the Resident detail page.")
    st.subheader("Important")
    st.warning("Wellness / early-warning aid, not a medical or emergency device. "
               "Camera-free and consent-based. All flags warrant clinical judgement.")


# --------------------------------------------------------------------------- nav
VIEWS = {
    "🛰️ Live board": live_board,
    "👤 Resident detail": resident_detail,
    "📄 Reports": reports_view,
    "➕ Onboarding": onboarding_view,
    "ℹ️ How it works": about_view,
}
choice = st.sidebar.radio("View", list(VIEWS))
st.sidebar.caption("Phase 0 prototype · simulated data · no hardware")
VIEWS[choice]()
