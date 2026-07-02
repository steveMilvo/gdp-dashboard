# Mildura: Colony on the Murray

A real-history strategy game set in the Mildura irrigation district (Sunraysia,
Victoria, Australia), rendered in **3D**. This folder is the playable build; the
design lives in [`../docs/build-prompt.md`](../docs/build-prompt.md) and the
sourced history in [`../docs/mildura-history.md`](../docs/mildura-history.md).

## Status: playable slice through M7

Implemented:

- **Real-layout cel-shaded 3D world** — the Murray, Kings Billabong, the
  terrace rise, dense painted red-gum forest, animated water with flow
  streaks, rock foam, painterly canvas textures throughout.
- **Working economy (M2)** — settlers chop red gum and gather food with full
  work animations (axe swings, wood chips, carry trips to the homestead);
  right-click is context-sensitive (red gum = chop, floodplain = gather).
- **The water system (M3)** — the Psyche Bend pump rises in 1889, gravity-fed
  channels cut toward the township, irrigated blocks green up with vine rows,
  and salinity bleaches the lowest blocks from 1904.
- **Date-gated construction (M4)** — [5] BUILD opens the Public Works palette:
  ten real buildings (Woolshed 1847 → Sacred Heart 1921) with costs, ghost
  placement, staged peg/frame/complete construction, and the Carnegie
  building upgrading with the Memorial Clock Tower in 1921. Placements save.
- **Era personas & milestones** — the status-panel guide evolves (Latji Latji
  Elder → Sturt → Jamieson → Chaffey); nine narrated newspaper milestones
  with per-era accents (GB/US/AU) and gold-framed portrait reveal cards.
- **Stealth learning (M7)** — the [C] Settler's Almanac (20 sourced entries,
  drop-in art slots), the travelling fountain living its three real lives
  (Rio Vista 1891 → still after 1897 → Deakin Avenue 1936), and the 1893-95
  Crash freezing the economy until the dried-fruit recovery.
- **Free guest mode** — zero sign-up, autosaves to localStorage.

Engine: **Three.js / WebGL, cel-shaded** (no pixel art). Still to come per the
build prompt: box-select & multi-unit control, the full crisis suite, social
groups, accounts/cloud saves (M9), and deployment (M10).


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
