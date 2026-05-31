# Sentinel — Hardware & first real-data runbook

How to go from the simulated prototype to **real Channel State Information (CSI)** on a
bench, then toward a room mesh. Scoped honestly: Tier 1 is a *physics proof*, not a
deployable product. See `PLAN.md` for the full deployment architecture.

> **Mental model.** The little **ESP32 boards are the sensing nodes** (they read the
> signal). Your **WiFi router is the signal source** the nodes sense against, and the
> data uplink to the dashboard. ESP32 ≠ router — different device class. "ESP32 mesh"
> means the *nodes talk directly to each other* (for localisation); only one node needs
> to reach the router to push results out.

---

## Tier 1 — Minimum viable CSI test (~US$25–35)

Espressif's official **ESP-CSI** approach uses **two ESP32 boards**: one transmits, one
receives and reads the CSI. Smallest real experiment.

| # | Item | Why | Link |
|---|---|---|---|
| 2× | ESP32-S3-DevKitC-1-N8 | Reference board, best-supported for ESP-CSI (one TX, one RX) | https://www.digikey.com/en/products/detail/espressif-systems/ESP32-S3-DEVKITC-1-N8/15199021 |
| alt | Seeed XIAO ESP32-S3 | Tiny/cheaper (~$7–8), same chip | https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/ |
| 2× | USB-C cables + 5V USB wall plugs | Power + flashing | (likely on hand) |

Your **ASUS router** is the ambient signal source — nothing to buy there.

**Software (all free):**
- ESP-CSI (Espressif firmware + examples): https://github.com/espressif/esp-csi
- CSIKit (Python: parse + visualise CSI): https://github.com/Gi-z/CSIKit
- Walkthrough: https://www.hackster.io/limengdu0117/esp-csi-diy-wifi-human-presence-detection-f80508

---

## Tier 2 — Room mesh + localisation (~US$60–90)

Once Tier 1 shows motion, add nodes to test multi-node geofencing (cross-room
attribution) and the identity **tag**.

| # | Item | Why | Link |
|---|---|---|---|
| 4× | ESP32-S3-DevKitC-1 | Corner mesh for triangulation | https://www.digikey.com/en/products/detail/espressif-systems/ESP32-S3-DEVKITC-1-N8/15199021 |
| 2× | BLE beacon tags (coin-cell) | Resident/staff identity anchor, read by ESP32 BLE | https://www.amazon.com/s?k=ble+ibeacon+coin+cell+tag |
| opt | Qorvo DWM3000 UWB module | 10–30 cm location vs ~1–3 m for BLE | https://www.digikey.com/en/products/detail/qorvo/DWM3000/13688419 |
| — | Enclosures + wall mounts | Tidy mounting (or 3D-print) | any |

---

## Tier 3 — Higher-resolution radar experiment (optional, ~US$15)

| # | Item | Why | Link |
|---|---|---|---|
| 2× | Seeed XIAO ESP32-C5 | 5 GHz CSI → finer micro-movement (breathing); *experimental* | https://wiki.seeedstudio.com/getting_started_xiao_esp32c5/ |

---

## Runbook — from boards to replacing the simulator

1. **Flash ESP-CSI** onto both Tier-1 boards (one as TX, one as RX) following the
   ESP-CSI repo README. Confirm the RX board streams CSI frames over serial/UDP.
2. **Read it with CSIKit** — capture a baseline of the empty room, then walk through and
   watch the CSI amplitude change. This is your "the physics is real" moment.
3. **Log a labelled dataset** — empty / sitting / walking / (later) lying still — so you
   have ground truth to validate detection against.
4. **Build a real ingest** to replace `sentinel/simulator.py`:
   - Keep the *same output shape* the rest of the engine expects (per-resident history
     rows + a realtime dict). The engine (`baseline.py`, `signals.py`, `presence.py`,
     `analytics.py`) and the whole dashboard stay unchanged — only the data source swaps.
   - Start by mapping CSI → presence/motion (reliable). Treat breathing/HR as a later,
     harder milestone.
5. **Validate honestly** — measure detection rate and false alarms against your labelled
   data before claiming anything.

---

## Honest caveats (read before buying)

- **Buy from DigiKey / Mouser / Seeed**, not cheap clones — CSI behaviour is firmware /
  chip-revision sensitive; clones cause hard-to-debug failures.
- **Motion is easy; vitals are hard.** Expect convincing presence/motion quickly;
  breathing/heart rate need real signal processing and may not come from a 2-board rig.
- **One rig ≠ the product.** A single TX/RX pair cannot do cross-room attribution — that
  is the entire reason the design needs the multi-node mesh + tag (Tier 2+). Tier 1 is a
  physics proof, not a deployable monitor.
- **Prices/stock shift** and links are live product pages — confirm at checkout. Exact
  board variant suffixes (N8 / N16 / N8R8) differ in flash/PSRAM; any ESP32-S3 DevKitC-1
  works for CSI.
- **Existing ASUS router as signal source:** fine, no changes needed. Stock ASUS firmware
  does **not** expose CSI itself — only specific Nexmon-supported Broadcom routers (e.g.
  RT-AC86U) can, and that's a separate research path, not required here since the ESP32s
  do the sensing.

---

## What this does NOT replace

This is the sensing front-end only. A real deployment still needs everything in
`PLAN.md` Phase 1+: a database (real residents, consent), tuned clinical thresholds,
alert delivery to carers, auth/audit, and per-building calibration. The bench rig proves
the input; the rest of the repo is the (already-built) intelligence and UI waiting for it.
