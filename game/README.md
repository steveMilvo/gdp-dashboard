# Mildura: Colony on the Murray

A real-history strategy game set in the Mildura irrigation district (Sunraysia,
Victoria, Australia), rendered in **3D**. This folder is the playable build; the
design lives in [`../docs/build-prompt.md`](../docs/build-prompt.md) and the
sourced history in [`../docs/mildura-history.md`](../docs/mildura-history.md).

## Status: M1 vertical slice (3D)

Implemented so far:

- **Real-layout 3D terrain** — the Murray meandering across the north, Kings
  Billabong, and the land rising ~28 m to the southern terrace, displaced from a
  heightmap and lit with a directional sun + shadows. The relief is literally 3D.
- **3D water surface** for the Murray and Kings Billabong.
- **Landmarks** as 3D markers in their correct relative positions (Township,
  Wharf, Psyche Bend, Kings Billabong, Nichols Point, Ninety Foot, Merbein, Red
  Cliffs), each revealing one true "stealth-learning" fact on hover.
- **Orbit camera** (drag to orbit, wheel zoom, right-drag pan).
- **Year clock + early economy** — river fishing & hunting for food, red gum
  timber, and wool-barge income once the squatter run begins.
- **Free guest mode** — plays with zero sign-up; autosaves to `localStorage`.

Engine: **Three.js / WebGL** (no pixel art). Not yet built (see the build
prompt's milestones): RTS unit control, the pump/channel water system (M3),
date-gated building placement (M4), social groups (M5), crises (M6), the codex &
travelling-fountain device (M7), and cloud accounts/sign-in (M9).

## Run it

```bash
cd game
npm install
npm run dev
```

Open the local URL Vite prints. Controls: **drag** to orbit, **mouse wheel** to
zoom, **right-drag** to pan, **SPACE** to pause.

> Note: `npm install` requires network access to fetch Three.js / Vite.

## The map is a placeholder for real geodata

`src/map/mapData.ts` generates a placeholder that **encodes Mildura's real
layout** so the 3D elevation reads correctly offline. To swap in the **authentic**
terrain (Geoscience Australia ELVIS DEM + OpenStreetMap water vectors), follow
`scripts/build-map.ts` — it documents the pipeline and emits the same data
structure (`source: "real-dem"`), which displaces the same terrain mesh.

## Optional cloud saves (free)

The game is **free to use** and fully playable as a guest. Optional sign-in and
cross-device cloud saves activate only when a Supabase backend is configured —
copy `.env.example` to `.env` and fill in the keys. Cloud auth/sync lands in
milestone M9.
