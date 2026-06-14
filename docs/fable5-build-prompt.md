# Build Prompt — "Mildura: Colony on the Murray" (Age of Empires–style strategy game)

> This is a self-contained build brief intended to be handed to **Fable 5** (or
> any capable coding agent) to implement the game. It pairs with the research
> reference in [`mildura-history.md`](./mildura-history.md) — read that document
> first; it is the canonical source of dates, names, and facts. Every in-game
> date, building, and event below must stay faithful to it.

---

## 0. Role & objective

You are building **"Mildura: Colony on the Murray"**, a single-player,
real-history strategy game in the spirit of *Age of Empires* / *Anno* /
*Banished* — part real-time-strategy, part city-builder. The player founds and
grows the Mildura irrigation district (Sunraysia, Victoria, Australia) across
its real historical eras (c. 1840s–1930s), managing land, water, population,
social groups, economy, and conflict.

The game must double as a **quiet learning tool**: history is taught through
mechanics and consequences, never through lectures or quizzes. A player should
absorb *why* Mildura exists (you must pump water uphill from the Murray) simply
by playing.

**Three non-negotiable pillars:**
1. **The map matches the real local map** (see §2 — this is the top priority).
2. **Buildings and events are gated to their real historical dates** (see §5).
3. **History is felt, not told** — stealth learning (see §8).

---

## 1. Recommended technology stack

Default to a **browser-based** build so it runs anywhere and is easy to share:

- **Language:** TypeScript
- **Engine:** Phaser 3 (2D, tile/isometric) — or PixiJS if more control is
  wanted. (Swap to Unity/Godot only if explicitly requested.)
- **Map data prep:** a small Node.js script using GDAL / `geotiff` to convert
  real elevation rasters into a game heightmap (see §2).
- **Build tooling:** Vite. **State:** plain TS modules or a lightweight store.
- **No backend required** for the MVP — everything runs client-side; save games
  to `localStorage`.

Deliver a runnable project (`npm install && npm run dev`) with a README.

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
   resample the DEM down to the game tile grid (e.g. 256×256 or 512×512 tiles),
   normalise heights, then **burn in** the river/billabong polygons as water
   tiles and tag the named landmark coordinates. Emit a single JSON/PNG
   heightmap + a features manifest the game loads at runtime.
5. Commit the processed map data **and** the script, so the map is reproducible
   and verifiably real (not invented).

### 2.3 How terrain drives play

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
- **Wool** — early income via the river-trade economy.
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
| pre-1830 | Latji Latji river camp | starting state; foraging |
| 1847 | Old Mildura Homestead | pastoral HQ (wool) |
| 1853 | Paddle-steamer landing | river trade node |
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

- **Latji Latji (Traditional Owners)** — present from the start; hold knowledge
  of land and water. Diplomacy/knowledge mechanic; their displacement by
  pastoralism and settlement is represented honestly (not erased, not
  trivialised).
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
- **(Optional, light) frontier conflict** between pastoral expansion and the
  Latji Latji — handle with historical honesty and restraint, as displacement and
  dispossession rather than arcade combat.

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
- A full playthrough should run roughly one to a few hours and trace c.
  1847→1930s.

---

## 12. Build order (milestones for the agent)

1. **M1 — Real map:** data pipeline + render the true terrain (Murray, Kings
   Billabong, Psyche Bend, the terrace) with elevation visibly driving water.
2. **M2 — Core loop:** place Homestead → settlers → resources tick → simple UI.
3. **M3 — Water system:** pump + channels + gravity irrigation + salinity; the
   Psyche Bend keystone gate.
4. **M4 — Ages & date-gated build menu** (§3, §5) with soft date gating.
5. **M5 — Social groups & satisfaction** (§6).
6. **M6 — Crises & conflict** (§7), timed to real years.
7. **M7 — Stealth-learning layer:** hover facts, codex, the travelling fountain
   (§8).
8. **M8 — Landmarks art, polish, save/load, README.**

Deliver M1–M3 as a playable vertical slice first; the **real, correct map is the
acceptance gate for M1** — do not proceed until the terrain demonstrably matches
the real district.

---

## 13. Acceptance criteria

- The map is built from **real elevation + river data**, with the named
  landmarks in their **true relative positions**; the processing script and
  source data are committed and reproducible.
- Irrigation only works by **pumping water up and gravity-feeding it down**,
  visibly tied to real elevation.
- Buildings unlock at their **real historical years**; the timeline matches
  `mildura-history.md`.
- At least the six social groups and the listed crisis systems are present and
  affect play.
- A player can learn the real story **without reading any tutorial text** —
  verified by the stealth-learning devices working in-game.
- `npm install && npm run dev` produces a runnable game with a README.

---

*Faithfulness rule: when a fact is uncertain, consult `mildura-history.md`;
items marked ⚠️ there are unverified — prefer the safer framing and never invent
specific dates, names, or figures that contradict the research document.*
