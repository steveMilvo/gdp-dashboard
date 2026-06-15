# Vision — "Australia: A Nation Built" (curriculum-aligned history game)

> **Status: forward-looking concept.** This is the planned *next* project, to be
> built **only once the Mildura game (the proof-of-concept) works**. Mildura
> proves the core loop — real map, date-gated building, history-as-mechanics,
> stealth learning — at town scale. This scales the same engine to the whole
> national story.
>
> Pairs with [`build-prompt.md`](./build-prompt.md) and
> [`mildura-history.md`](./mildura-history.md); reuse that architecture.

---

## 1. Concept

A strategy/builder game that takes the player across **Australian history from
deep time to the modern day**, structured around **key dates** and aligned to the
**Australian Curriculum** (HASS / History). Like Mildura, it teaches through
mechanics and consequences, not lectures — but here the **learning is explicitly
rewarded**: engaging with a real historical "learning point" grants in-game
**boosts** (resources, governance upgrades, technology upgrades).

The technology tree is a celebration of **real Australian inventions**.

---

## 2. Eras (discovery → settlement → federation → modern)

The opening era draws on the deep-time cultural and archaeological record
(see the research doc).

| Era | Rough span | Theme |
|-----|-----------|-------|
| **Deep Time / First Nations** | 65,000+ yrs ago → 1606 | Aboriginal & Torres Strait Islander cultures, Country, trade routes, fire management, the oldest continuous cultures on Earth |
| **Encounter & Exploration** | 1606–1787 | Macassan trade; Dutch landfalls (Janszoon 1606, Hartog 1616), Cook's 1770 east-coast charting |
| **Colonisation & Settlement** | 1788–1850 | First Fleet (1788); convict era; pastoral expansion |
| **Gold & Growth** | 1851–1900 | Gold rushes; Eureka (1854); immigration; self-government; railways/telegraph |
| **Federation** | 1901 | The colonies become a nation (1 Jan 1901); Constitution; early nationhood |
| **World Wars & Between** | 1914–1945 | Gallipoli/WWI; the Depression; WWII; national identity |
| **Postwar & Modern** | 1945–2000 | Mass migration; Snowy Scheme; decimal currency (1966); postwar growth |
| **Contemporary** | 2000–today | Modern economy, science & culture |

---

## 3. Learning points → reward boosts (core hook)

The signature mechanic. Throughout play, the game surfaces **learning points**
(real events, figures, civics, inventions). Engaging with one — a short
interactive moment, a choice with real historical context, or discovering a site
— grants a **reward**:

- **Resource boosts** — population, food, money, materials.
- **Governance upgrades** — unlock civic systems tied to real milestones
  (e.g. self-government → Federation → universal suffrage), each improving
  stability/diplomacy options.
- **Technology upgrades** — unlock the Australian-invention tech tree (§4).

Design rules (carry over the Mildura "stealth learning" ethos):
- Rewards make the learning **worth seeking**, but the game stays playable
  without grinding facts — curiosity is incentivised, not mandatory.
- Keep it **never a pop-quiz**; learning points are woven into events, building,
  and exploration.
- An opt-in **codex/almanac** records everything learned (a collectible history).

---

## 4. Technology tree — real Australian inventions

The tech tree celebrates genuine Australian innovation. Each node = a real
invention granting a gameplay upgrade and a one-line true fact.
**⚠️ Verify every date/attribution against a primary source before building.**

| Invention | Person / body | ~Date | Possible in-game effect |
|-----------|---------------|-------|-------------------------|
| Mechanical ice-making / refrigeration | James Harrison | 1850s | preserve food; boost export economy |
| Electric drill | Arthur James Arnot | 1889 | construction speed |
| Penicillin (development & mass production) | Howard Florey (Nobel 1945) | 1940s | health / population |
| Hills Hoist | Lance Hill | 1945 | civic happiness / suburban era |
| Victa rotary mower | Mervyn Victor Richardson | 1952 | suburban growth |
| Black box flight recorder | David Warren | 1950s | safety / aviation |
| Medical ultrasound (grey-scale imaging) | Kossoff & team, Commonwealth Acoustic Labs | 1960s–70s | health |
| Cochlear implant ("bionic ear") | Graeme Clark | 1978 | health / prestige |
| Polymer banknotes | RBA + CSIRO | 1988 | economy / anti-counterfeiting |
| Gardasil (HPV vaccine) | Ian Frazer & Jian Zhou | 1990s–2006 | health |
| **WiFi (wireless LAN)** | CSIRO, John O'Sullivan & team | 1990s | communications / late-game economy |
| Spray-on skin (ReCell) | Fiona Wood | 1990s | health / disaster response |
| Google Maps (origin: Where 2 Technologies) | Lars & Jens Rasmussen (Sydney) | 2000s | information / logistics |

(Plenty more to draw on: the stump-jump plough, the winged keel, the dual-flush
toilet, the notepad/wine cask, the bionic eye, Relenza, the ute, etc.)

---

## 5. Map

- A map of **Australia** (real coastline + topography), built from the same
  real-geodata pipeline used for Mildura (Geoscience Australia DEM + OSM), at
  continental scale.
- Settlement, resources, and expansion track the real historical geography
  (coastal cities first, inland later; the Goldfields, the Snowy, etc.).
- ⚠️ At national scale, consider whether play is continent-wide or a series of
  regional scenarios (e.g. Sydney Cove 1788, the Goldfields, Federation) — a
  decision to make in the build brief.

---

## 6. Australian Curriculum alignment

- Target the **HASS / History** strand. Map eras and learning points to real
  curriculum content (e.g. Year 4 First Contacts; Year 5 colonial Australia;
  Year 6 Federation & democracy; Year 9 making of the modern world; Year 10
  modern Australia).
- ⚠️ **Confirm specific content descriptors and codes against the official ACARA
  Australian Curriculum (v9)** before claiming alignment — do not invent codes.
- Provide a **teacher mode / curriculum map** linking in-game learning points to
  curriculum outcomes, so it's usable in classrooms.

---

## 7. Reuse from Mildura

- Same engine/stack (TypeScript + Three.js/WebGL 3D, free-tier backend for free
  accounts).
- Same pillars: **real map**, **date-gated unlocks**, **stealth learning**.
- Same free-to-use accounts & cloud-save system.
- The Mildura title can live on as a **detailed regional scenario** within (or
  alongside) the national game.

---

## 8. Open decisions (for the eventual build brief)

- Year-level focus / single game vs. age-banded modes.
- Continent-wide sandbox vs. curated scenario campaign.
- How explicit the "reward for learning" is (visible XP vs. invisible boosts).
- Platform priority (web first, given free/easy access for schools).

---

*Accuracy note: this is a concept draft. Every date, attribution, and curriculum
reference above must be verified against primary/authoritative sources (ACARA,
museums, the inventors' institutions) before it goes into a build — same
discipline as `mildura-history.md`.*
