// M6 — the full crisis suite. Real crises on their real dates, felt as
// gameplay. Every event and date below is drawn from docs/mildura-history.md:
//   §2  1870s-80s — drought and the rabbit plague break the Mildura station;
//       the lease reverts to the Victorian Government by 1884.
//   §6  1893 — the Murray drops to record lows; the harvest is stranded; the
//       planned railway is shelved. (The banking side of 1893 is owned by
//       game/crash.ts — this module handles only the river.)
//   §6  10 December 1895 — Chaffey Brothers Ltd goes into liquidation, owing
//       ~£22,000 in wages. (Narrative beat only: crash.ts owns the economics.)
//   §6  1896 — the Royal Commission at Langtree Hall finds the brothers
//       undercapitalised with serious planning errors, but no breach of
//       contract. A reputational/political blow: a one-off capital fine.
//   §7  Salinity, "the long-term curse", intensifying through the 1920s-30s;
//       the State Rivers & Water Supply Commission's gravitational drainage
//       outfall of 1924 counters it (a relief beat, tone "news").
//
// Design rules honoured here:
//   - Every effect is deterministic from sim.year alone — no rng, no save-
//     format change; old saves load untouched and effects resume correctly.
//   - Each banner fires once per playthrough: the fired set is seeded from
//     sim.year on install, the same pattern main.ts uses for milestones.
//   - hud.showMilestone queues safely, so a crisis banner landing in the same
//     year as a milestone (1893) simply queues behind it.
//   - Bounded effects with recovery: every debuff has an end year (or a
//     small permanent residual in salinity's case — the doc calls it the
//     long-term curse) and every clamp floors at zero.
//   - Visual touch: during the 1893 record low the water plane target drops
//     ~0.4 units; getWaterLevelOffset() exposes a smoothed offset for the
//     render loop (wired in main.ts: water.mesh.position.y = WATER_LEVEL +
//     crises.getWaterLevelOffset()). The doc names no specific flood year,
//     so no flood event is invented — the offset only ever goes down.

import type { Simulation } from "./state";
import type { Accent } from "./narrator";

export interface CrisisEvent {
  year: number;
  title: string;
  body: string;
  speech: string; // narrator line (period phrasing)
  tone: "news" | "alarm";
  /** One-off effect applied the tick the banner fires (e.g. the 1896 fine). */
  onFire?: (sim: Simulation) => void;
}

// --- The suite (chronological) ----------------------------------------------

/** 1896 Royal Commission: a one-off reputational fine on the colony's books. */
export const ROYAL_COMMISSION_FINE = 60; // £

export const CRISES: CrisisEvent[] = [
  {
    year: 1870,
    tone: "alarm",
    title: "DROUGHT ON THE RUN — AND THE RABBITS COME",
    body:
      "Dry years settle over the Mildura run and the rabbit plague strips the " +
      "saltbush bare. Through the 1870s and '80s the station is broken; by " +
      "1884 the lease has reverted to the Victorian Government.",
    speech:
      "The seventies. The rain has failed on the Mildura run, and now the " +
      "rabbits are in — thousands upon thousands, eating the saltbush to the " +
      "roots. This drought will break the station before it lifts.",
  },
  {
    year: 1893,
    tone: "alarm",
    title: "THE MURRAY FALLS TO RECORD LOWS",
    body:
      "The great river shrinks between its banks. The harvest is stranded on " +
      "the wharf with no water to float it out, and the planned railway is " +
      "shelved. The pumps at Psyche Bend suck at a dwindling river.",
    speech:
      "Eighteen ninety-three, and the river itself has turned on us. The " +
      "Murray is down to a record low — the harvest is stranded on the bank, " +
      "and the railway they promised is shelved. Pray for rain upstream.",
  },
  {
    year: 1895,
    tone: "alarm",
    title: "CHAFFEY BROTHERS LTD IN LIQUIDATION",
    body:
      "10 December 1895: the company that built the colony goes into " +
      "liquidation, owing some £22,000 in wages, with 438,000 acres of unsold " +
      "land on its books. The banks foreclose on many settlers.",
    speech:
      "December, eighteen ninety-five. Chaffey Brothers Limited is wound up — " +
      "twenty-two thousand pounds owing in wages, and near half a million " +
      "acres unsold. The men who dreamt the colony could not pay for it.",
  },
  {
    year: 1896,
    tone: "alarm",
    title: "ROYAL COMMISSION SITS AT LANGTREE HALL",
    body:
      "The Commission finds the Chaffeys entered the scheme undercapitalised " +
      "and made serious planning errors — no breach of contract, but damning " +
      "on financial management. The colony's credit takes the bruise.",
    speech:
      "Eighteen ninety-six. The Royal Commission has sat at Langtree Hall and " +
      "handed down its finding: undercapitalised from the first, and grave " +
      "errors of planning. No law broken — but the colony's good name pays.",
    onFire: (sim) => {
      sim.resources.capital = Math.max(0, sim.resources.capital - ROYAL_COMMISSION_FINE);
    },
  },
  {
    year: 1920,
    tone: "alarm",
    title: "SALT RISES UNDER THE VINES",
    body:
      "Salinity — the long-term curse of irrigation — creeps up through the " +
      "root zone. White crusts spread on the low ground and yields sicken " +
      "through the twenties.",
    speech:
      "Nineteen twenty. There's a white crust coming up on the low blocks — " +
      "salt, rising with every watering. The old curse of irrigation country, " +
      "and it will not be ignored.",
  },
  {
    year: 1924,
    tone: "news",
    title: "THE DRAINAGE OUTFALL IS DUG",
    body:
      "The State Rivers and Water Supply Commission builds a gravitational " +
      "drainage outfall to carry the salt away — works that will be " +
      "intensified through the 1930s. The vines breathe again.",
    speech:
      "Nineteen twenty-four. The State Rivers Commission has dug the drainage " +
      "outfall at last — the salt water runs away by gravity now. The blocks " +
      "will carry the scar, but the vines will live.",
  },
];

// --- Effect windows (deterministic from sim.year) -----------------------------

/** 1870s-80s drought & rabbit plague: the station bleeds until the lease
 *  reverts to the Victorian Government (doc: "by 1884"). */
const DROUGHT_START = 1870;
const DROUGHT_END = 1884; // inclusive

/** The 1893 record low. One recovery season follows before the river runs
 *  full again (the doc names only 1893 itself as the record year). */
export const LOW_RIVER_YEAR = 1893;
const LOW_RIVER_RECOVERY_END = 1894; // inclusive

/** Salinity creep: sharp through the early twenties, cut to a small permanent
 *  residual once the 1924 drainage outfall is built (the long-term curse). */
const SALINITY_START = 1920;
const OUTFALL_YEAR = 1924;

/** Water-plane offset target for the render loop: the 1893 record low drops
 *  the river ~0.4 world units. The doc names no flood year, so no raise. */
export function waterLevelTargetFor(year: number): number {
  return year >= LOW_RIVER_YEAR && year <= LOW_RIVER_RECOVERY_END ? -0.4 : 0;
}

// --- Install -------------------------------------------------------------------

export interface CrisesDeps {
  sim: Simulation;
  hud: { showMilestone(m: { year: number; title: string; body: string; tone?: "news" | "alarm" }): void };
  /** Optional waterworks handle: during the 1893 low river its contribution
   *  for the tick is subtracted back out (the pumps suck at a dry river). */
  waterworks?: { getWaterTick(): number; getFoodTick(): number };
  narrate?: (text: string, accent?: Accent) => void;
}

export interface Crises {
  /** Call once per sim tick, AFTER sim.tick() and waterworks.applyTick(). */
  applyTick(): void;
  /** Call once per frame: eases the water-plane offset toward its target. */
  update(dt: number, t: number): void;
  /** Smoothed offset for the water plane (0 outside crisis years). */
  getWaterLevelOffset(): number;
}

export function installCrises(deps: CrisesDeps): Crises {
  const { sim, hud, waterworks, narrate } = deps;

  // Crises already in the past (restored save) never re-fire — the same
  // seeding pattern main.ts uses for milestones.
  const fired = new Set<number>(CRISES.filter((c) => c.year <= sim.year).map((c) => c.year));

  let waterOffset = 0; // smoothed render value

  function fireBanners(): void {
    for (const c of CRISES) {
      if (c.year > sim.year || fired.has(c.year)) continue;
      fired.add(c.year);
      hud.showMilestone({ year: c.year, title: c.title, body: c.body, tone: c.tone });
      narrate?.(c.speech, "AU");
      c.onFire?.(sim);
    }
  }

  function applyEffects(): void {
    const y = sim.year;
    const r = sim.resources;

    // 1870-1884: drought starves the flocks, rabbits strip the feed.
    if (y >= DROUGHT_START && y <= DROUGHT_END) {
      r.wool = Math.max(0, r.wool - 2);
      r.food = Math.max(0, r.food - 2);
    }

    // 1893 (+ one recovery season): the pumps and the fishermen both fail.
    if (y >= LOW_RIVER_YEAR && y <= LOW_RIVER_RECOVERY_END) {
      if (waterworks) {
        // Suspend the irrigation contribution: take back exactly what
        // waterworks.applyTick() just added this tick.
        r.water = Math.max(0, r.water - waterworks.getWaterTick());
        r.food = Math.max(0, r.food - waterworks.getFoodTick());
      }
      // Fishing food halved: the base tick feeds ~0.3 food/head from river
      // protein after 1847 — claw back half of it while the river is down.
      r.food = Math.max(0, r.food - Math.ceil(r.population * 0.15));
    }

    // Salinity: a hard creep through the early twenties, then a small
    // permanent residual once the 1924 outfall drains the worst of it.
    if (y >= SALINITY_START && y < OUTFALL_YEAR) {
      r.food = Math.max(0, r.food - 3);
    } else if (y >= OUTFALL_YEAR) {
      r.food = Math.max(0, r.food - 1);
    }
  }

  return {
    applyTick() {
      if (sim.paused) return;
      fireBanners();
      applyEffects();
    },
    update(dt: number, _t: number) {
      const target = waterLevelTargetFor(sim.year);
      // Ease over ~2s so the river visibly falls and refills.
      waterOffset += (target - waterOffset) * Math.min(1, dt * 0.8);
      if (Math.abs(waterOffset - target) < 0.001) waterOffset = target;
    },
    getWaterLevelOffset: () => waterOffset,
  };
}
