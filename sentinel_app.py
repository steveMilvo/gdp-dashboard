"""Aged Care Sentinel — Phase 0 prototype (Streamlit).

A camera-free, per-resident early-warning dashboard running on simulated ambient-sensing
data. Demonstrates the live board, per-resident baseline/drift + watchlist, tiered
alerts, role-typed LLM reports, onboarding, and the self-improving feedback loop.

Run:   streamlit run sentinel_app.py
Optional LLM reports:   export ANTHROPIC_API_KEY=sk-...   (otherwise templated fallback)
"""

from __future__ import annotations

import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from sentinel import alerts, data, presence, reports, signals, simulator
from sentinel.baseline import BASELINE_DAYS
from sentinel.signals import TIER_EMOJI, TIER_RANK

# Wing floor layout (grid coordinates per room) for the floor-plan map.
COORDS = {"A-101": (0, 1), "A-102": (1, 1), "A-103": (2, 1), "A-104": (3, 1),
          "A-105": (0, 0), "A-106": (1, 0), "A-107": (2, 0)}
TIER_COLOR = {"GREEN": "#3ba55d", "YELLOW": "#e3c037", "AMBER": "#e08e2b", "RED": "#d23c3c"}

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


@st.cache_data
def load_interactions():
    return simulator.interactions()


snap, assessments = load_state()
interactions = load_interactions()
st.session_state.setdefault("feedback", [])   # self-improving loop: outcome labels
st.session_state.setdefault("acks", set())    # acknowledged alerts


# ----------------------------------------------------------------------- charts
def floor_map():
    """Colour-coded wing map — situational awareness at a glance."""
    df = pd.DataFrame([
        {"room": r.room, "x": COORDS[r.room][0], "y": COORDS[r.room][1],
         "status": assessments[r.id].status, "name": r.name}
        for r in data.roster()
    ])
    color = alt.Color("status:N", scale=alt.Scale(
        domain=list(TIER_COLOR), range=list(TIER_COLOR.values())), legend=None)
    base = alt.Chart(df)
    tiles = base.mark_square(size=5200, stroke="white", strokeWidth=2).encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-0.5, 3.5])),
        y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-0.6, 1.6])),
        color=color, tooltip=["room", "name", "status"])
    labels = base.mark_text(color="white", fontSize=13, fontWeight="bold", dy=-6).encode(
        x="x:Q", y="y:Q", text="room")
    names = base.mark_text(color="white", fontSize=10, dy=10).encode(
        x="x:Q", y="y:Q", text="status")
    return (tiles + labels + names).properties(height=240).configure_view(strokeWidth=0)


def baseline_band_chart(hist, metric, meta):
    """Resident's own baseline as a shaded ±2σ band; recent breaches marked red,
    with a dashed rule where the drift began ('caught it early')."""
    base_win = hist.iloc[:BASELINE_DAYS][metric]
    mean = float(base_win.mean())
    sd = float(base_win.std(ddof=0)) or 1e-6
    hi, lo = mean + 2 * sd, mean - 2 * sd
    d = hist[["date", metric]].rename(columns={metric: "value"}).copy()
    d["breach"] = d["value"] > hi if meta["bad"] == "high" else d["value"] < lo
    d["lo"], d["hi"] = lo, hi

    band = alt.Chart(d).mark_area(opacity=0.15, color="#3b82f6").encode(
        x=alt.X("date:T", title=None), y="lo:Q", y2="hi:Q")
    line = alt.Chart(d).mark_line(color="#666").encode(
        x="date:T", y=alt.Y("value:Q", title=meta["unit"]))
    pts = alt.Chart(d).mark_point(filled=True, size=55).encode(
        x="date:T", y="value:Q",
        color=alt.condition("datum.breach", alt.value("#d23c3c"), alt.value("#666")))
    layers = [band, line, pts]
    breaches = d[d["breach"]]
    if not breaches.empty:
        rule = alt.Chart(pd.DataFrame({"date": [breaches["date"].iloc[0]]})).mark_rule(
            color="#d23c3c", strokeDash=[4, 4]).encode(x="date:T")
        layers.append(rule)
    return alt.layer(*layers).properties(height=180, title=meta["label"])


# --------------------------------------------------------------------------- views
@st.fragment(run_every="2s")
def _live_banner():
    st.markdown(
        f"<span style='color:#3ba55d;font-weight:bold'>● LIVE</span> &nbsp; "
        f"feed updated {datetime.now():%H:%M:%S} · mesh streaming",
        unsafe_allow_html=True)


@st.fragment(run_every="3s")
def _node_health():
    df = simulator.node_health()
    online = (df["status"] == "🟢 online").sum()
    st.caption(f"Mesh telemetry — {online}/{len(df)} nodes online (refreshes live)")
    st.dataframe(df, use_container_width=True, hide_index=True)


@st.fragment(run_every="1s")
def _live_vitals(rid, hr, br):
    df = simulator.vitals_trace(rid, time.time(), hr, br)
    st.markdown(
        f"<span style='color:#3ba55d;font-weight:bold'>● LIVE</span> "
        f"chest-displacement waveform (breathing + heartbeat) · {datetime.now():%H:%M:%S}",
        unsafe_allow_html=True)
    st.line_chart(df.set_index("seconds_ago")[["chest displacement"]], height=160)


def live_board():
    st.title("🛰️ Sentinel — Wing A live board")
    st.caption("Camera-free ambient monitoring · per-resident early warning · simulated feed")
    _live_banner()

    counts = {"RED": 0, "AMBER": 0, "YELLOW": 0, "GREEN": 0}
    for r in data.roster():
        counts[assessments[r.id].status] += 1
    c = st.columns(4)
    c[0].metric("🔴 Red (life-safety)", counts["RED"])
    c[1].metric("🟠 Amber (clinical)", counts["AMBER"])
    c[2].metric("🟡 Yellow (watch)", counts["YELLOW"])
    c[3].metric("🟢 Green", counts["GREEN"])

    st.subheader("Wing floor map")
    st.altair_chart(floor_map(), use_container_width=True)

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
                f"{rt['presence']} · {rt['motion']}"
                + ("  \n👥 2+ in room"
                   if rt.get("occupancy", {}).get("count", 1) > 1 else ""))

    st.subheader("Co-presence / security")
    any_cp = False
    for r in data.roster():
        ca = presence.copresence_alert(snap[r.id]["realtime"])
        if ca:
            any_cp = True
            st.warning(f"{TIER_EMOJI[ca['tier']]} **{r.room} {r.name}** — {ca['title']}: {ca['action']}")
    if not any_cp:
        st.caption("All co-presence accounted for (staff badges identified). "
                   "Interactions are logged for care-minute evidence.")

    st.subheader("Node / mesh health")
    _node_health()


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
    occ_label = presence.occupants_label(rt)
    if occ_label:
        st.info(f"👥 {occ_label}")
    cp = presence.copresence_alert(rt)
    if cp:
        st.warning(f"⚠️ {cp['title']} — {cp['action']}")
    _live_vitals(rid, rt["heart_rate"], rt["breathing_rate"])

    st.subheader("Today's care interactions")
    st.caption("Auto-logged from staff badges — evidences AN-ACC care minutes.")
    sub = interactions[interactions["resident_id"] == rid]
    total = int(sub["minutes"].sum())
    rn = int(sub[sub["role"].isin({"RN", "EN"})]["minutes"].sum())
    mc = st.columns(2)
    mc[0].metric("Care minutes today", total, f"target {presence.CARE_MINUTE_TARGET}",
                 delta_color="off")
    mc[1].metric("RN minutes", rn, f"target {presence.RN_MINUTE_TARGET}", delta_color="off")
    log = sub[["start", "end", "activity", "staff", "role", "minutes"]].rename(
        columns={"start": "Start", "end": "End", "activity": "Activity",
                 "staff": "Staff", "role": "Role", "minutes": "Mins"})
    st.dataframe(log, use_container_width=True, hide_index=True)
    by_act = (sub.groupby("activity")["minutes"].sum().sort_values(ascending=False)
              .rename("minutes"))
    st.caption("Minutes by activity")
    st.bar_chart(by_act, height=180)

    st.subheader("Trends vs baseline (14 days)")
    st.caption("Shaded band = this resident's own normal (±2σ). Red points breach it; "
               "the dashed line marks when the drift began.")
    show = ["night_bathroom_trips", "resting_hr", "sleep_fragmentation", "gait_speed"]
    tc = st.columns(2)
    for i, m in enumerate(show):
        with tc[i % 2]:
            st.altair_chart(baseline_band_chart(hist, m, data.METRICS[m]),
                            use_container_width=True)

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


def care_minutes_view():
    st.title("Care minutes — AN-ACC evidence")
    st.caption(f"Auto-tallied from staff-badge interactions. Target "
               f"{presence.CARE_MINUTE_TARGET} min/resident/day, including "
               f"{presence.RN_MINUTE_TARGET} RN minutes.")
    summ = presence.care_minutes_summary(interactions)
    under = int((summ["Status"] == "⚠️ under").sum())
    m = st.columns(2)
    m[0].metric("Residents at/above target", len(summ) - under)
    m[1].metric("Residents below target", under)
    st.dataframe(summ, use_container_width=True, hide_index=True)
    st.caption("Staff tracking is consent-based and framed for care-minute evidence and "
               "lone-worker safety — not surveillance. Access is role-scoped.")


def _shift_timeline(log):
    d = log.copy()
    d["start_dt"] = pd.to_datetime("2026-05-31 " + d["start"])
    d["end_dt"] = pd.to_datetime("2026-05-31 " + d["end"])
    return alt.Chart(d).mark_bar(cornerRadius=3, height=18).encode(
        x=alt.X("start_dt:T", title="Time of day"),
        x2="end_dt:T",
        y=alt.Y("room:N", title="Room", sort="-x"),
        color=alt.Color("activity:N", title="Activity"),
        tooltip=["start", "end", "room", "resident", "activity", "minutes"],
    ).properties(height=260)


def staff_view():
    st.title("Staff & shifts — manager view")
    st.caption("Per-staff movement and interaction trail across the shift, from staff "
               "badges. Consent-based and role-scoped — framed as care-minute evidence "
               "and lone-worker safety, not surveillance.")

    st.subheader("Shift summary (all staff)")
    st.dataframe(presence.staff_summary(interactions),
                 use_container_width=True, hide_index=True)

    st.subheader("Staff movement trail")
    staff_map = interactions[["staff_id", "staff", "role"]].drop_duplicates()
    opts = {f"{row.staff} ({row.role})": row.staff_id for row in staff_map.itertuples()}
    sid = opts[st.selectbox("Staff member", list(opts))]
    log = presence.staff_shift_log(interactions, sid)

    mc = st.columns(3)
    mc[0].metric("Active minutes", int(log["minutes"].sum()))
    mc[1].metric("Rooms visited", log["room"].nunique())
    mc[2].metric("Residents seen", log["resident"].nunique())
    st.altair_chart(_shift_timeline(log), use_container_width=True)
    st.dataframe(
        log.rename(columns={"start": "Start", "end": "End", "room": "Room",
                            "resident": "Resident", "activity": "Activity",
                            "minutes": "Mins"}),
        use_container_width=True, hide_index=True)


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
    "🧑‍⚕️ Care minutes": care_minutes_view,
    "🧑‍💼 Staff & shifts": staff_view,
    "📄 Reports": reports_view,
    "➕ Onboarding": onboarding_view,
    "ℹ️ How it works": about_view,
}
choice = st.sidebar.radio("View", list(VIEWS))
st.sidebar.caption("Phase 0 prototype · simulated data · no hardware")
VIEWS[choice]()
