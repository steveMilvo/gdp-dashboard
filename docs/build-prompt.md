# Build Prompt — "Mildura: Colony on the Murray" (a real, fully-playable 3D RTS)

> This is a self-contained build brief intended to be handed to **Fable 5** (or
> any capable coding agent) to implement the game. It pairs with the research
> reference in [`mildura-history.md`](./mildura-history.md) — read that document
> first; it is the canonical source of dates, names, and facts. Every in-game
> date, building, and event below must stay faithful to it.

---

## 0. Role & objective

Build me a **fully playable, Age of Empires–style real-time strategy game in the
browser**, set in the Mildura irrigation district (Sunraysia, Victoria,
Australia) across its real historical eras (c. 1840s–1930s). It is part RTS, part
city-builder — the player founds and grows the colony, managing land, water,
population, social groups, economy, and conflict.

**Render it in a full 3D world** (Three.js or equivalent WebGL — **no pixel
art**). It must **look like a real game**: proper lighting and shadows, readable
unit/building silhouettes, terrain with texture variety, and smooth camera pan
and zoom — **not blobby placeholder geometry**.

The game must also double as a **quiet learning tool**: history is taught through
mechanics and consequences, never through lectures or quizzes. A player should
absorb *why* Mildura exists (you must pump water uphill from the Murray) simply
by playing.

**Non-negotiable pillars:**
1. **A real 3D game, not a prototype look** — Three.js/WebGL, real lighting,
   shadows, textures and camera (see §1, §1.6).
2. **The map matches the real local topography** (see §2 — top priority; the real
   elevation becomes the literal 3D terrain).
3. **A classic RTS core loop and controls** — select/box-select/right-click,
   minimap, resource bar (see §1.6).
4. **Buildings and events gated to real historical dates** (§5); **history felt,
   not told** — stealth learning (§8).
5. **Check in at key decisions, then deploy live to Vercel** and verify the
   deployed build runs (see §1.7).

---

## 1. Technology stack

A **browser-based, full-3D** build:

- **Language:** TypeScript.
- **3D engine:** **Three.js** (or equivalent WebGL). **No pixel art, no 2D
  tilemap** — real 3D meshes, materials, lighting and shadows.
- **Rendering quality:** physically-plausible lighting with directional sun +
  shadows, ambient/sky light, fog for depth; PBR or well-lit standard materials;
  texture variety on terrain (water, red gum, mallee/belah scrub, the terrace);
  distinct, readable silhouettes for every unit and building; smooth orbit/pan
  camera with zoom and edge/keyboard scroll. Keep performance smooth (instancing
  for repeated meshes, LOD where needed).
- **Map data prep:** a small Node.js script using GDAL / `geotiff` to convert the
  real elevation raster into a 3D terrain heightmap (see §2).
- **Build tooling:** Vite. **State:** plain TS modules or a lightweight store.
- **Backend / accounts:** a **free-tier managed backend** for sign-in and cloud
  saves — **Supabase** (Postgres + Auth + Row-Level Security) or Firebase. Game
  logic runs **client-side**; the backend only handles auth and save data. Guest
  play falls back to `localStorage` and syncs on sign-in (see §1.5).
- **Hosting:** **deploy to Vercel** (see §1.7).

Deliver a runnable project (`npm install && npm run dev`) with a README. Keep all
backend keys in environment variables (`.env`, never committed); the app must run
in a **guest mode without any backend configured** so it's always playable.

---

## 1.5 Accounts, sign-in & cloud saves (free to use)

The game must support **user accounts and sign-in**, and be **free to use** — no
paywalls, no subscriptions, no charge for any feature. Accounts exist only to
save progress, sync across devices, and (optionally) compare scores.

### Requirements

- **Free, optional sign-in.** Anyone can play immediately as a **guest** (local
  saves). Signing in is opt-in and unlocks **cloud saves** synced across devices.
- **Sign-in methods:** email + password (with verification + password reset) and
  at least one **OAuth provider** (Google recommended; add others as easy wins).
  "Magic link" email sign-in is a good low-friction option.
- **Per-user save slots:** each account stores multiple named save games (full
  game state as JSON), with created/updated timestamps; last-played autosave.
- **Guest → account migration:** when a guest signs in, offer to upload their
  local save(s) to the cloud so nothing is lost.
- **Account management:** sign out, delete account + all data (honour the
  request fully), and export save data.

### Data model (minimal)

- `users` — provided by the auth provider (id, email, display name, created_at).
- `saves` — `id`, `user_id` (FK), `name`, `state` (JSONB game state), `era/year`,
  `created_at`, `updated_at`.
- *(optional)* `scores` / `leaderboard` — `user_id`, `metric`, `value`, `era`.

### Security & privacy

- **Row-Level Security:** a user can read/write **only their own** saves
  (enforce server-side, e.g. Supabase RLS policies — never trust the client).
- Collect the **minimum** personal data (email + optional display name). Publish a
  short privacy note. Provide real account + data deletion.
- All secrets in env vars; never commit keys. HTTPS only.

### Acceptance for this slice

- A new visitor can play with **zero sign-up**.
- A user can create an account, sign in (email + Google), and their saves
  **persist across devices and browser sessions**.
- A guest's local save can be **migrated** into their account on first sign-in.
- A user can **delete their account and data**, and it is actually removed.

---

## 1.6 Core RTS loop, controls & "real game" visuals

This must play like a classic RTS, themed to Mildura's real history.

### The core loop (AoE-style, mapped to Mildura)
- **Start** with a **town centre** (the **Chaffey HQ / homestead**) and a few
  **villagers (settlers)** on the generated 3D map.
- **Villagers gather resources** and **construct buildings**. Mildura's resources
  replace AoE's wood/food/gold (see §4): **Food** (river fishing, hunting, then
  sheep & cattle), **Timber** (red gum), **£ / Capital** (wool→barge trade, later
  dried fruit & wine), and the keystone **Water** (pumped uphill, then gravity-
  fed — see §2/§3). 
- **Train more villagers (settlers) and workers**, and **advance through Ages**
  (the real eras, §3) that unlock stronger buildings, units and tech.
- **An antagonist applies pressure on the same map.** Mildura was not won by armies,
  so the primary "enemy" is **environmental & economic** — drought, the record-low
  1893 river, creeping salinity, and the 1890s financial crash (see §7). You
  "win" by surviving the Crash with the colony intact and reaching prosperity;
  you "lose" if the colony depopulates, goes bankrupt, or salinity ruins the land.
  - *Optional "Rival Colony" mode* for players who want the classic
    destroy-the-base loop: a competing AI irrigation colony (e.g. a Renmark-style
    rival) races you for river frontage and water; win by out-developing or
    out-lasting it. Keep it historically plausible (economic/expansion rivalry,
    not arcade warfare).

### Controls (classic RTS)
- **Left-click** to select a unit/building; **drag** to **box-select** groups.
- **Right-click** to **move, gather, build, or repair** (context-sensitive on the
  target); double-click selects all of a type on screen.
- **Minimap** (showing terrain, your base, resources, the antagonist/rival) and a
  **resource bar** (Food, Timber, £, Water, Population) always on screen.
- Smooth **camera pan and zoom** (mouse-edge scroll, WASD/arrows, wheel zoom,
  optional rotate). Building-placement preview snaps to valid terrain.

### "Make it look like a real game"
- Proper **lighting and shadows**; terrain with **texture variety** (river,
  red-gum riverline, mallee/belah scrub, the cultivated terrace, channels);
  **readable silhouettes** for each unit and building; smooth camera. **No blobby
  placeholder geometry** — use real modelled meshes (low-poly is fine if it's
  clean and readable). Selection/health rings, gather/build animations, and water
  that visibly flows through the channels.

---

## 1.7 Check-in workflow & deployment

**Check in with me at key decision points instead of deciding silently.**

- **Before building the world**, present **3 visual-style directions, labelled
  A / B / C**, each with a **one-line tradeoff**, and **wait for my pick.**
- Do the same for **any major gameplay scoping decision** — including **what you'd
  cut** if the full loop won't fit in one shot. Propose A/B/C options, wait.
- Don't silently make large architectural or art-direction choices.

**Deployment:**
- **Deploy live to Vercel** once it's playable, then **verify the deployed version
  actually runs** (load it, start a game, confirm no console/runtime errors) —
  don't just report success.
- Keep secrets in Vercel env vars; the deployed build must still work in **guest
  mode** if no backend is configured.

---

## 2. THE MAP — must match the real local topography (top priority)

The whole game rests on real terrain. Mildura's farmland sits **~28 m above the
Murray River**, so water must be lifted and then gravity-fed downhill. Elevation
*is* the core puzzle — get the real contours right and the gameplay emerges for
free.

### 2.1 Real-world extent

Build the map from the real district around Mildura. Suggested bounding box
(adjust to taste, but keep it the real place):

- Centre: Mildura township, approx **-34.1855° lat, 142.1625° lon**
- Bounding box approx **lat -34.30 to -34.02, lon 141.95 to 142.45**
- Must include these **real features**, correctly placed relative to each other:
  - The **Murray River** with its real meanders/horseshoe bends (northern edge)
  - **Kings Billabong** (the natural anabranch used as the system's reservoir)
  - **Psyche Bend** (downstream/west — site of the lowest pump lift)
  - **Nichols Point**, **Ninety Foot** (further pump-station sites)
  - **Red Cliffs** (south, the real red river cliffs), **Merbein** (~8 km
    downriver, NW), **Irymple**, **Cardross**
  - The **1887 American-grid township** on the terrace above the river

### 2.2 Data pipeline (use real open data — do not hand-draw the terrain)

1. **Elevation (the critical layer):** download a DEM for the bounding box from
   **Geoscience Australia ELVIS** (elevation.fsdf.org.au) — 5 m DEM where
   available, else 1-second SRTM — or **Vicmap Elevation**.
2. **Water & vectors:** pull the Murray River, Kings Billabong, lakes and roads
   from **OpenStreetMap** (Overpass API).
3. **Historic grid (optional polish):** overlay the 1887 parish/township survey
   grid from **Public Record Office Victoria (PROV)** / **Trove** so streets
   like Deakin Avenue land in their true positions.
4. **Processing script:** reproject to a local metric CRS, clip to the box,
   resample the DEM to a heightmap grid (e.g. 256×256 or 512×512), normalise
   heights, then tag the river/billabong polygons and the named landmark
   coordinates. Emit a single JSON/PNG **heightmap** + a features manifest.
5. **Build the 3D terrain from the heightmap** — displace a terrain mesh by the
   real elevations so the ~28 m river-to-terrace rise is literally visible in 3D;
   render the river/billabong as flowing water surfaces below the banks. The real
   contours become the playable 3D landscape.
6. Commit the processed map data **and** the script, so the map is reproducible
   and verifiably real (not invented).

### 2.3 Vegetation / biome layer (real regional ecology)

Paint a vegetation layer over the terrain that matches the real Mallee–Murray
country — it supplies resources and authentic art:

- **River Red Gum (*Eucalyptus camaldulensis*)** — large trees lining the Murray
  in dense stands along the river corridor. The settlers' main **building timber**
  (see §5) and a habitat band along all water tiles.
- **Mallee** (multi-stemmed dwarf eucalypts) — the dominant cover on the inland
  flats; cleared for farmland.
- **Belah / belar (*Casuarina pauper*)** — stands of hard inland timber in the
  dry scrub.

Tie vegetation to tile type: red gum follows the river/billabong; mallee and
belah fill the terrace and inland flats. Clearing scrub yields land for farming;
red gum yields construction timber.

### 2.4 How terrain drives play

- Tiles carry **elevation** and **water-distance**. Crops need irrigation;
  irrigation only reaches tiles **below** the height a pump can lift to and
  within channel range.
- Riverbank/floodplain tiles are cheap but **flood** and can't be farmed; the
  high terrace is farmable **only once water is pumped up to it**.
- A player who reads the contours prospers; one who ignores them builds pumps
  and channels that can't reach their blocks.

---

## 3. Eras / Ages (advancement spine)

Each Age changes available buildings, units, and the economy. Advancing requires
a real-history trigger.

| Age | Advance trigger | Theme |
|-----|-----------------|-------|
| I. River Country (pre-1830) | start | Latji Latji land; river foraging/fishing |
| II. The Squatter Run (1847+) | build Homestead | sheep pastoralism; wool→river trade |
| III. The Indenture (1887) | sign the Chaffey agreement | survey grid; attract settlers; big capital |
| IV. Water Uphill (1889–92) | build **Psyche Bend Pump** | irrigation unlocks; desert→farmland |
| V. The Colony (1890s) | build civic buildings/Rio Vista | population boom; temperance society |
| VI. Crash (1893–96) | scripted crisis | depression, drought, insolvency — survival |
| VII. The Fruit Republic (1895+) | form Irrigation Trust | grower self-rule; dried fruit & wine; railway |

---

## 4. Resources

- **Water** — the master resource. Must be **pumped** (the 28 m lift) and
  distributed by **gravity channels**. **Salinity** is a slow creeping debuff on
  over-irrigated land, countered by drainage works (unlock 1924).
- **Timber (Red Gum)** — harvested from the riverside red gum stands; the early
  building material (slab huts) before milled/imported materials arrive.
- **Bush food (Kangaroo & Emu)** — an **early Food source**: settlers hunt
  kangaroo and emu to survive until livestock is introduced, after which **Sheep
  & Cattle** become the food/wool base.
- **River fishing** — the other **early protein source**: fishing the Murray
  (Murray cod, golden perch/callop, yabbies & crayfish) yields food from water
  tiles. Available from the start (the Latji Latji rely on it) and a steady,
  low-tech food supply throughout the early eras.
- **Wool** — the settlement's **primary early income**, sent up- and downriver by
  barge (see river-trade economy, §6/§7 era flavour).
- **Capital (£)** — Chaffey investment and bank credit; can collapse in the Crash.
- **Settlers / Labour** — population; navvies to dig channels.
- **Coal / Steam** — fuel for the Tangye pumping engine.
- **Dried Fruit & Wine** — late-game export economy (raisins, sultanas,
  currants, brandy).
- **Food** — sustains population.

---

## 5. Buildings & structures — gated to real dates

Buildings appear in the build menu at their **real historical year** (soft
gating: allow building slightly early at a steep cost premium, but the real date
is the natural/cheap unlock — so the optimal path quietly traces real history).
All dates/facts below come from `mildura-history.md`.

| Year | Structure | Game role |
|------|-----------|-----------|
| pre-1830 | Latji Latji river camp | starting state; foraging, hunting (kangaroo/emu) & river fishing |
| 1840s | **Red gum slab hut** | first dwelling — built from riverside red gum timber |
| 1847 | Old Mildura Homestead | pastoral HQ (sheep/cattle → wool) |
| 1853 | Paddle-steamer landing & wool barges | river trade node; wool exported up/downriver |
| 1887 | Township survey grid; Deakin Avenue | unlocks settlement plots; prestige axis |
| 1888 | *Mildura Cultivator* (newspaper); first vines | civic info; vineyard |
| 1889 | Langtree Hall; Grand Coffee Palace; Rio Vista (begun) | first hall; hospitality; founder's mansion |
| 1890–92 | **Psyche Bend Pump Station** (Tangye 1,000 hp) | **keystone — unlocks irrigation** |
| 1891 | Rio Vista completed | prestige building + its garden fountain |
| 1892 | Mildura Wharf; winery cellars | river export; wine |
| 1894 | Working Man's Club; Mildura Club | morale / social buildings |
| 1895 | Settlers Club; **First Mildura Irrigation Trust** | social; civic governance unlock |
| 1896 | Royal Commission (at Langtree Hall) | crisis event building |
| 1903 | **Railway to Melbourne** | replaces slow river logistics |
| 1908 | Carnegie Free Library | knowledge/culture (rare wonder-tier) |
| 1913–14 | Merbein winery/distillery | late export economy |
| 1914 | Desailly Rotunda | morale/gathering |
| 1920 | Mildura Club clubhouse; first Mayor | civic milestone |
| 1921 | Memorial Clock Tower (replaces Carnegie tower) | memorial + civic timekeeping |
| 1923 | New Post Office; Cenotaph | communications; memorial |
| 1924 | Drainage outfall | counters salinity debuff |
| 1927 | Lock 11 / Mildura Weir | raises/stabilises river level |
| 1929 | W.B. Chaffey bronze statue (Montford) | founder monument (reflective late marker) |
| 1934 | Base Hospital (Art Deco) | health; unlocks at "city" status |
| 1936 | King George V Fountain | the relocated Rio Vista fountain (see §8) |

**Keystone rule:** nothing grows on the high terrace until **Psyche Bend** is
built. The Tangye-pump flavour ("Tangyes of Birmingham refused to build the
engine, then stamped it with a disclaimer") appears as a one-line hover fact.

---

## 6. Population & social groups (factions within your town)

Model population as distinct **social groups** with their own needs, loyalties,
and frictions. Keeping them balanced is a core management loop.

- **Latji Latji (river people)** — present from the start; hold knowledge of the
  land and water (a diplomacy/knowledge mechanic).
- **Squatters / Pastoralists** — the old wool order (Jamiesons, McEdward);
  resent the irrigation colony carving up the run.
- **Block Settlers / Growers** — the irrigation smallholders; the backbone of
  the colony; demand reliable water and fair treatment (they revolt → push for
  the Irrigation Trust in 1895).
- **Working Men / Labourers** — the navvies and workers; want jobs, wages, and a
  place to drink (Working Man's Club). Unpaid wages in the 1895 collapse = unrest.
- **The Elite / Gentry** — the Chaffeys and town notables (Mildura Club); supply
  capital and civic buildings; favour temperance.
- **Temperance vs. Drinkers** — a cross-cutting social tension (the dry colony,
  the coffee palaces, the members'-club loophole, the 1915–19 licence fights).

Each group has a **satisfaction** meter feeding overall stability. Neglect breeds
strikes, departures, or political pressure.

---

## 7. Conflict systems

This is not primarily a military game; most conflict is **social, economic, and
environmental**. Model these tension/crisis systems:

- **Environmental:** the **1893 record-low river** and drought; recurring
  drought; the **1880s rabbit plague**; floods on the floodplain; **creeping
  salinity** (the slow long-term antagonist).
- **Economic:** the **1890s depression** and **1893 banking crisis**; the
  **Chaffey Brothers liquidation (Dec 1895)** with ~£22,000 unpaid wages; bank
  foreclosures on settlers.
- **Political / social:** the **1896 Royal Commission** (a public reckoning event
  at Langtree Hall); settler revolt leading to grower self-governance (Irrigation
  Trust); temperance vs. liquor-licence politics.
- **Inter-group friction:** squatters vs. colonists; labour vs. capital
  (wages/strikes); settlers vs. the Chaffey company over water reliability.

Each crisis is **scripted to its real year** but its severity depends on the
player's preparedness (water reserves, capital buffer, group satisfaction).

---

## 8. "Stealth learning" — history felt, not told

- **Mechanics encode the lesson.** The player learns "Mildura exists because of
  pumped irrigation on high ground" by *failing to farm* until they build the
  pump. No popup says it.
- **Salinity** teaches the real long-term cost of irrigation purely as a debuff.
- **Real timing.** Crises fire on their true years, so the player feels history's
  rhythm as difficulty.
- **Opt-in depth.** Hovering any building reveals **one true sentence** (e.g. the
  Tangye disclaimer; the Carnegie £2,000 grant; the Cenotaph names). A codex /
  almanac fills in as you build — history as reward, never homework.
- **The travelling fountain (signature device).** The same fountain **asset
  physically moves across the map over 40 years**: it sits in the **Rio Vista
  garden** (1891) → goes **idle after Edward Chaffey drowns in it (May 1897)** →
  is **relocated to Deakin Avenue as the King George V Memorial Fountain (1936)**.
  An observant player discovers a whole human story just by noticing the object
  move — with zero text.

---

## 9. Landmarks / wonders (real, signature buildings)

Give these distinctive art and a hover fact: **Psyche Bend Pump Station**
(the power plant / keystone), **Rio Vista** (founder's mansion), **Carnegie
Library**, **Working Man's Club** (the world's-longest-bar morale building),
**Mildura Club** & **Settlers Club**, **Grand Coffee Palace**, **Langtree Hall**
(the inquiry building), the **Wharf**, **Memorial Clock Tower**, **Cenotaph**,
and the **W.B. Chaffey statue**.

---

## 10. Key characters

- **George Chaffey** — the Engineer (water/tech bonuses; leaves for California in
  1897).
- **William B. Chaffey** — the Statesman ("The Boss"; stays, becomes first Mayor
  in 1920; long-game civic bonuses).
- **Alfred Deakin** — the Patron (off-map government; grants the 1887 Indenture).
- **The Jamiesons / McEdward** — the squatters who held the land first.
- **The Banks & the Royal Commission** — antagonist economic forces of the Crash.

---

## 11. Win / lose & session shape

- **No single victory.** Offer goals: survive the Crash with the colony intact;
  reach a target population/prosperity; transition to grower self-governance;
  build the full landmark set. Provide a **sandbox/free-build** mode too.
- **Lose states:** colony depopulates (mass settler exodus), bankruptcy with no
  recovery, or terminal salinity ruining the farmland.
- **Optional Rival Colony mode** adds a classic RTS win/lose condition:
  out-develop or outlast a competing AI colony racing you for river frontage and
  water (§1.6).
- A full playthrough should run roughly one to a few hours and trace c.
  1847→1930s.

---

## 12. Build order (milestones for the agent)

0. **M0 — Visual-style check-in (do this first):** generate the real 3D terrain
   from the DEM, then present **3 visual-style directions (A/B/C)** with one-line
   tradeoffs and **wait for my pick** before building out the world (§1.7).
1. **M1 — Real 3D map:** data pipeline + render the true terrain as a **3D
   heightmap** (Murray, Kings Billabong, Psyche Bend, the terrace) with elevation
   visibly driving water.
2. **M2 — Core RTS loop:** town-centre/homestead → settlers gather & build →
   **resource bar + minimap** → **select / box-select / right-click** controls →
   camera pan/zoom (§1.6).
3. **M3 — Water system:** pump + channels + gravity irrigation + salinity; the
   Psyche Bend keystone gate. **Deploy this vertical slice to Vercel and verify
   it runs** (§1.7).
4. **M4 — Ages & date-gated build menu** (§3, §5) with soft date gating.
5. **M5 — Social groups & satisfaction** (§6).
6. **M6 — Crises & conflict** (§7), timed to real years; optional Rival Colony AI
   (§1.6).
7. **M7 — Stealth-learning layer:** hover facts, codex, the travelling fountain
   (§8).
8. **M8 — "Real game" visual polish:** lighting, shadows, terrain textures,
   readable unit/building silhouettes, animations; landmarks art; local
   save/load; README.
9. **M9 — Accounts & cloud saves (§1.5):** guest mode first, then optional
   sign-in (email + Google), per-user cloud save slots, guest→account migration,
   and account/data deletion. Local save/load (M8) must work independently so the
   game is always playable without an account.
10. **M10 — Final deploy:** redeploy to Vercel and **verify the live build runs
    end-to-end** (loads, starts a game, no runtime errors), still playable in
    guest mode.

Deliver M1–M3 as a playable vertical slice first; the **real, correct 3D map is
the acceptance gate for M1**. **Check in (A/B/C) at M0 and at any major scoping
decision** — including **what you'd cut** if the full loop won't fit in one shot.

---

## 13. Acceptance criteria

- Renders as a **real 3D game** (Three.js/WebGL): lighting, shadows, terrain
  texture variety, readable unit/building silhouettes and smooth camera pan/zoom
  — **no pixel art, no placeholder blobs**.
- Plays as a **classic RTS**: left-click select, drag box-select, right-click
  move/gather/build, a **minimap** and a **resource bar**.
- The agent **checked in with 3 A/B/C visual-style options before building the
  world**, and at major scoping decisions (§1.7).
- **Deployed to Vercel** and the **live build verified to run** (loads, starts a
  game, no runtime errors) — still playable in guest mode.
- The map is built from **real elevation + river data**, rendered as **3D
  terrain**, with the named landmarks in their **true relative positions**; the
  processing script and source data are committed and reproducible.
- Irrigation only works by **pumping water up and gravity-feeding it down**,
  visibly tied to real elevation.
- Buildings unlock at their **real historical years**; the timeline matches
  `mildura-history.md`.
- At least the six social groups and the listed crisis systems are present and
  affect play.
- A player can learn the real story **without reading any tutorial text** —
  verified by the stealth-learning devices working in-game.
- The game is **free to use** with **optional sign-in**: it is fully playable as
  a guest, and signed-in users get cloud saves that persist across devices, with
  guest→account save migration and real account/data deletion (§1.5).
- `npm install && npm run dev` produces a runnable game with a README.

---

*Faithfulness rule: when a fact is uncertain, consult `mildura-history.md`;
items marked ⚠️ there are unverified — prefer the safer framing and never invent
specific dates, names, or figures that contradict the research document.*
