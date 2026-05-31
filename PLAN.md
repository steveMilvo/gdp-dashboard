# Aged Care Sentinel — Plan & Architecture

A privacy-preserving, camera-free monitoring platform for aged-care facilities.
It turns ambient RF sensing (WiFi CSI, e.g. RuView on ESP32 nodes) plus a cheap
locator tag into **per-resident early-warning intelligence**: not just "a fall
happened" alarms, but "this resident is sliding toward a UTI — act now" foresight.

> **Status:** Phase 0 — software prototype on simulated data (no hardware required).
> The prototype proves the engine, the live board, the role-based reports, and the
> self-improving loop. Hardware integration is a later phase.

---

## 1. Thesis

Every product in this space is a smarter **alarm** — reactive, event-based. The
whitespace is a **sentinel**: predicting the slow slide (UTI → delirium → fall,
infection, dehydration, mobility decline, withdrawal) *days before* the crisis, by
watching each resident drift from **their own baseline**, and narrating it in plain
language to the right person.

This is buildable now because three things converged: cheap continuous ambient
vitals/gait sensing (RuView/ESP32), LLMs that turn signals into meaning, and
on-device processing for privacy/offline operation.

**Moat is not the sensing** (RuView commoditised that). It is: the longitudinal
per-resident model, the clinical signal library, distribution, and trust.

---

## 2. System at a glance

```
[Room nodes + locator tag] -> [edge/ingest] -> SENTINEL ENGINE
                                                ├─ per-resident baseline (digital twin)
                                                ├─ real-time engine  -> ALERTS (tiered + escalation)
                                                ├─ sentinel engine    -> FLAGS / watchlist
                                                └─ clinical signal library
                                                       │
                     ┌──────────────────────────────────┼──────────────────────────────┐
               LIVE BOARD                 REPORT GENERATOR (LLM)                  FEEDBACK LOOP
            (carers/nurses)        ├─ carer / shift-handoff                 (outcome labels ->
                                   ├─ doctor / clinical                       self-improvement)
                                   ├─ management / operational
                                   └─ incident (auto-drafted)
```

One engine feeds every screen and report.

---

## 3. User roles (drives access + report scope)

| Role | Primary surface |
|---|---|
| Carer (on-shift) | Live board, alerts, per-resident watchlist, shift handoff |
| Nurse / clinical lead | Triage queue, amber flags, clinical reports, escalation |
| Management | Operational dashboards, incident/compliance reports |
| Doctor / GP (external) | Per-resident clinical summary reports |
| Admin | Onboarding, node binding, consent, user management |
| Family (later) | Soft wellbeing summaries (opt-in) |

Same data, filtered and narrated per role.

---

## 4. Data model

`Facility -> Wing -> Room -> Node` and `Resident -> ResidentProfile -> Baseline`,
with the event chain:

```
Reading/Signal -> Event -> Flag -> Alert -> Incident
                                 ↘ Outcome/Feedback (closes the loop)
Report (generated, typed, role-scoped)   User (role, scope)   Consent
```

History attaches to `resident_id`, not the room — so it follows residents through
room moves (common in facilities).

---

## 5. Functional modules

- **Onboarding** — intake (care level, mobility, continence, dementia, fall history,
  meds), **consent capture**, node→room→resident binding (NFC tap), and **baseline
  seeding** from profile + cohort priors so it is useful on day one.
- **Live monitoring board** — wing view, rooms colour-coded 🟢🟡🟠🔴, ranked
  "needs attention this shift" triage list, click-through to resident detail.
- **Alert / alarm system** — tiered with escalation:
  - 🔴 RED (life-safety: fall, no vitals, wander) → page now, ack required, escalates.
  - 🟠 AMBER (clinical: UTI pattern, mobility decline) → nurse queue.
  - 🟡 INFO (trend for care plan).
  Tuned so RED is rare and trusted (alarm fatigue is the #1 product-killer).
- **Per-resident watchlist** — living "things to watch for", generated from the
  resident's own data and refined as outcomes confirm.
- **Report generator (LLM narrator, role-typed)** — carer/shift-handoff, doctor/
  clinical, management/operational.
- **Incident reports** — auto-drafted on a RED event, structured + compliance-ready,
  carer-verified.
- **Two-tier help model** — both ways a resident gets help, no button/wearable:
  - *Active call* — a **deliberate help gesture** (e.g. both arms raised and waved for
    ~3–5s) is an easy, reliable CSI signature → immediate **RED "assistance requested"**
    page. Covers conscious residents who can't reach a button (on the floor, bathroom,
    garden). For able residents; a confirm-back loop is recommended in production to
    suppress false calls. Not a substitute for passive sensing in advanced dementia.
  - *Passive call* — sensed distress (fall, prolonged no-motion, vitals) catches the
    resident who **can't** ask. Together they cover both populations.
- **Staff badges, co-presence & care minutes** — staff carry a cheap BLE badge (read by
  the same room nodes), so the system resolves "who is the second person" (staff vs
  unknown), suppresses false falls, **auto-logs every staff–resident interaction**, and
  tallies **AN-ACC care minutes** per resident (the headline AU compliance feature).
  Policy: log all co-presence; alert only on an *unidentified* person *after hours*.
  Staff tracking is consent-based and framed as care-minute evidence + lone-worker
  safety, not surveillance; access is role-scoped.

---

## 6. Intelligence layer

- **Baseline / digital twin** — per-resident normal (gait, sleep, night trips,
  resting HR, daily rhythm).
- **Drift / anomaly detection** — two clocks: real-time (acute) + longitudinal
  (multi-day drift vs baseline, via z-scores).
- **Clinical signal library** — pattern → condition mappings (UTI, dehydration,
  decline, withdrawal). Core IP.
- **LLM narrator** — turns signals into plain-language, role-specific reports
  (Claude API, prompt caching).

---

## 7. Self-improving loop (safe by design)

Every flag/alert gets an **outcome label** in the UI ("confirmed UTI" / "false alarm"
/ "no action"). That label is the training signal, applied at three levels:

1. **Per-resident adaptation (automatic, safe)** — baseline keeps re-learning;
   per-individual false alarms get suppressed.
2. **Population / cohort learning (reviewed)** — outcomes across residents refine
   cohort priors and the signal library for *this* facility.
3. **Signal-library refinement (human-in-the-loop, auditable)** — proposed detection
   changes are surfaced for clinical review, never silently applied.

**Guardrail:** life-safety (RED) thresholds never auto-tune without clinical sign-off.
Self-improvement runs freely on trend/early-warning logic (statistically forgiving)
and is gated on anything where a miss is dangerous. All model changes are versioned
and auditable — essential for a regulated setting.

---

## 8. Hardware / deployment (decided during design)

- **Node** = a small ESP32-S3 board (~$5–8 at volume) that reads WiFi CSI (and has
  BLE on-chip to read the locator tag). Sensing requires the radio on continuously.
- **Cross-room attribution** — through-wall sensing means a single node hears the
  neighbour. Solve with a **multi-node mesh + spatial geofencing** to the room
  polygon, plus a cheap **locator tag** (BLE/UWB, coin-cell, years of battery) on the
  resident's walker/bed to nail "which body is the resident". Tag converts a hard
  signal-separation problem into easy nearest-location assignment.
- **Power** — continuous sensing needs continuous power (battery alone ≈ 1 day), so
  nodes are mains-powered, **never** off a switched light circuit. Use the always-live
  **bedside / bed-head socket** as the single power point; feed high-corner nodes via
  thin **low-voltage wiring along the wall–ceiling junction in raceway** (no floor
  cables, no trip hazard — critical for a fall-prevention product). Small battery
  backup keeps RED alerts alive through outages.
- **Install** — non-technical staff: plug in, mount high in corners, NFC-tap to
  commission. Self-surveying mesh + geofence; per-room calibration; **measure
  cross-room leakage empirically in the pilot** before promising anything.
- **Honest framing** — wellness / early-warning, **not** a medical or emergency
  device. Consent per resident. Camera-free is the privacy trump card.

---

## 9. Tech stack

- **Prototype (this repo):** Streamlit + simulated node feed + Claude API narrator
  (graceful template fallback if no API key). Proves engine, board, reports, loop —
  no hardware.
- **Production:** multi-role, real-time, multi-tenant → web stack (React/Next +
  API + Postgres + websockets for the live board + role-based auth + edge ingest
  service for nodes). The prototype de-risks and demos; production is a rebuild.

---

## 10. Phased build

| Phase | Deliverable |
|---|---|
| **0** | Simulated-data prototype: live board + per-resident baseline/drift + LLM shift report + a "caught a UTI 3 days early" scenario |
| **1** | Onboarding + data model + real-time board + tiered alerts/escalation |
| **2** | Report generator (carer/doctor/management) + auto incident reports |
| **3** | Feedback capture + self-improving loop + per-resident watchlist |
| **4** | Hardware integration (real nodes + tag), per-building calibration & cross-room validation |

Compliance, consent, audit, and role-based access are threaded through every phase.

> **MVP data boundary (scope decision):** the prototype runs entirely on **mesh-native
> data** — sensed resident movement + staff-badge movement/attendance. No nurse-call
> ("bell") or EHR integration is required to ship. Responsiveness/accountability is
> derived from *sensed* attention events (out-of-bed, fall, restlessness, wandering)
> vs staff badge attendance. A nurse-call bell feed is deferred to a later phase and
> simply becomes one more event source flowing into the same pipeline.

---

## 11. Running the Phase 0 prototype

```
pip install -r requirements.txt
streamlit run sentinel_app.py
```

Optional — wire the LLM narrator to real Claude API output:

```
export ANTHROPIC_API_KEY=sk-...
# optional model override (defaults to a cost-effective report model):
export SENTINEL_MODEL=claude-sonnet-4-6
```

Without an API key the narrator falls back to a built-in deterministic template so
the demo always runs.

---

## 12. Research basis & sensing roadmap

The core thesis — RF/WiFi as a spatial sensing modality for the home — is grounded in
published work, not speculation. These references both validate the approach and define
the later-phase sensing upgrades.

**Validating the approach (today):**
- **DensePose-from-WiFi (Carnegie Mellon, arXiv 2301.00250)** — full human body-pose
  reconstruction through walls from commodity WiFi. Upstream of our fall/gait sensing.
- **Sub-meter RF positioning (e.g. ZaiNar)** — confirms the localization/geofencing we
  rely on for cross-room attribution is a funded, proven field.
- **Commodity WiFi sensing already shipping** (e.g. carrier "WiFi motion" features) —
  the hardware and base capability already exist in homes.

**Roadmap upgrades (later phases, not MVP):**
- **Pose-based fall classification (from DensePose-from-WiFi)** — move from
  "impact + no motion" to posture-aware detection (on-floor vs in-bed vs slumped),
  plus richer gait/mobility-decline signals. *Phase 4 sensing upgrade.*
- **Tag-free identity (WhoFi, arXiv 2507.12869)** — re-identify individuals from their
  WiFi biometric signature, potentially removing the locator tag. Treat as a research
  track behind the tag, **gated on hard guardrails**: it is lab-grade (degrades with
  layout change, crowds, signature drift over time), needs an enrollment step, and is an
  **ethical escalation** — covert through-wall biometric ID is exactly the capability
  that makes WiFi-sensing legally contentious, and is especially sensitive for staff.
  The explicit, consent-clear **tag remains the default identity anchor**; tag-free ID is
  opt-in only, and never at the cost of the camera-free / consent-first positioning.

**Out of scope (macro context only):** military electromagnetic-warfare and satellite
RF-geolocation platforms (Anduril, HawkEye 360, Spire) show RF sensing is a large,
well-capitalised wave, but have no aged-care application — useful as investor context,
not a scope driver.
