# Sentinel — Demo Walkthrough (Director of Nursing / facility decision-maker)

A ~12-minute guided walkthrough of the Phase 0 prototype. Audience: a Director of
Nursing, facility manager, or provider executive (Australian residential aged care).
Goal: land the value, be honest about what's simulated, and end on a pilot.

> Run it first: `python -m streamlit run sentinel_app.py`
> (Set `ANTHROPIC_API_KEY` beforehand if you want live Claude-written reports.)

---

## 0. Frame it (30 sec, before you touch the screen)

> "This is camera-free, wearable-free monitoring. Small sensors in each room read
> WiFi-signal disturbance to sense movement, breathing and presence — plus a cheap
> badge so we know who's a resident and who's staff. It doesn't replace your nurse-call
> system; for this pilot it runs entirely on what the sensors and badges see. Let me
> show you what that gives you."

Set expectations: **the data here is simulated** to demonstrate the workflow; in a
pilot it's live sensor data.

---

## 1. Group portfolio (1 min) — start at the top

Open **🏢 Group portfolio**.

- "If you run multiple homes, this is the exec view — every home's care-minute
  compliance, falls, incidents, open alerts, ranked worst-first."
- Point at the compliance bar chart vs the 85% line.
- "Riverside — Wing A is live. Let's drill in." → switch to the wing.

## 2. Live board (1.5 min) — "it's actually live"

Open **🛰️ Live board**.

- The **● LIVE** stamp ticking, the **floor map** colour-coded, the **node/mesh
  health** panel refreshing (one node offline = "we see faults too").
- "Two reds and ambers right now. The system already ranked who needs attention."
- Co-presence line: "it knows who's in each room."

## 3. The early warning — the headline (2.5 min)

Open **👤 Resident detail → Arthur Bell (A-102)**.

- "Arthur's flagged amber — *possible UTI developing*. Look why:" point at the
  **baseline-band chart** — night bathroom trips breaching his own normal, with the
  **dashed line where it started 3 days ago**.
- "A UTI in someone with dementia often shows up as confusion and a fall — *after*
  it's bad. We're flagging it **3 days early**, while it's still treatable, before the
  fall and the hospital transfer."
- Show the **live vitals waveform** + the **watchlist** (plain-language "what to watch
  for"). "Your night staff don't read charts — they read this."

## 4. The fall + co-presence (1 min)

**Resident detail → Dorothy Klein (A-103)**.

- Red **fall alert**. "Detected, no button pressed."
- Note the co-presence: *resident + Jane Okafor (RN)* — "and because staff carry a
  badge, the system already knows the RN is in the room responding — so it won't
  false-alarm on the carer leaning over the bed, and it logs who attended."

## 5. Care minutes — the compliance money (2 min)

Open **🧑‍⚕️ Care minutes**.

- "Every staff–resident interaction is logged from the badge — automatically. Here's
  AN-ACC care minutes per resident vs the 215-minute target, including RN minutes."
- "This is the number you currently fight to evidence. It's just… here. Audit-ready."
- Drill to a resident's interaction log: timed activities (e.g. *Personal care /
  bathing 08:03–08:35*) and the minutes-by-activity chart.

## 6. Staff movement (1 min)

Open **🧑‍💼 Staff & shifts**.

- Shift summary, then pick a carer → their **movement trail** across the shift.
- "Workforce visibility for managers — coverage, workload, where time goes."

## 7. Responsiveness — the safety gut-punch (2 min)

Open **🚨 Responsiveness**.

- "Here's the one that matters most. Overnight, the sensors raised attention events —
  out of bed, restlessness, **and a fall**. Cross-referenced against staff badge
  movement:"
- Read the red exception aloud: *"4 sensed events including a fall went unattended
  00:12–03:55 while the rostered night carer showed a large gap in room visits."*
- "No bell needed. This is the scenario every DON fears — and it's exactly what's
  SIRS-reportable. The system surfaces it with timestamped evidence, to verify against
  the badge trail before you act."
- Point at the timeline: the cluster of **red unattended** dots overnight.

## 8. Close (1 min)

- **Self-improving:** "Every flag your staff label trains it to your home."
- **Reports:** show a generated shift-handoff / clinical / incident report (📄 Reports).
- **The pitch:**
  - "Camera-free, no wearable, installs without trip hazards, runs on your existing
    power and WiFi."
  - "It catches decline early, evidences your care minutes, and proves responsiveness —
    the three things that drive your Star Rating and your funding."
  - "We'd start with a **free 60–90 day pilot on one wing** to prove reliability and
    give you a falls/care-minute outcome. Then ~$30–60 per bed per month, hardware
    bundled — under half a percent of bed revenue."

---

## Honest answers to the questions they'll ask

- **"How reliable is it really?"** — "Demo data is simulated. Through-wall sensing is
  the hard part, especially separating one resident from the neighbour — which is why
  we use a multi-node mesh plus the badge, and why the pilot's first job is to *measure*
  the false-alarm and cross-room rate in *your* building before we promise anything."
- **"Is this surveillance of my staff?"** — "It's framed and governed as care-minute
  evidence and lone-worker safety, consent-based, role-scoped access. The accountability
  analytics exist to protect residents from genuine neglect and to *exonerate* staff in
  disputes — not to police them. It needs consultation and should fit your EBA."
- **"Is it a medical device?"** — "No — wellness / early-warning only. Every flag
  warrants clinical judgement; it augments staff, it doesn't replace them."
- **"What about the nurse-call bell?"** — "Deferred on purpose so we ship faster. It
  plugs in later as just another event source; the engine doesn't change."
- **"What needs integrating later?"** — "Nurse-call, EHR/eMAR, and alert delivery to
  carers' phones. The pilot doesn't need any of them."

---

## Pre-demo checklist

- [ ] App runs clean (`python -m streamlit run sentinel_app.py`), no stale-cache banner.
- [ ] (Optional) `ANTHROPIC_API_KEY` set so 📄 Reports shows real narratives.
- [ ] Know your three "money" screens cold: **baseline-band (UTI early), care minutes,
      responsiveness (unattended fall)**.
- [ ] Lead with resident safety + compliance, not the technology.
