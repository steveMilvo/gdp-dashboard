# :earth_americas: GDP dashboard template

A simple Streamlit app showing the GDP of different countries in the world.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gdp-dashboard-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

---

## 🛰️ Aged Care Sentinel (prototype)

This repo also hosts a Phase 0 prototype of **Aged Care Sentinel** — a camera-free,
per-resident early-warning dashboard built on simulated ambient-sensing data. It
demonstrates a live wing board (floor map, mesh-node health, live vitals waveform),
per-resident baseline/drift detection with a "things to watch for" list, tiered alerts,
role-typed LLM reports, onboarding, and a self-improving feedback loop.

```
$ pip install -r requirements.txt
$ streamlit run sentinel_app.py
```

Reports use a deterministic template unless `ANTHROPIC_API_KEY` is set (then Claude
writes them). See [`PLAN.md`](PLAN.md) for the full architecture and hardware design.
