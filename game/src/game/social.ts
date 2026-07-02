// M5 — Social groups & satisfaction (docs/build-prompt.md §6).
//
// The six groups of the brief, each with an era-driven presence (0..1), a
// satisfaction meter (0..100) moved by simple legible factors (food surplus,
// water access post-1889, capital through the Crash, salinity for the
// blockies), and a one-line "voice" that changes with the satisfaction band.
// All dates and wording are grounded in docs/mildura-history.md — nothing here
// invents a fact the docs do not carry.
//
// Effects: the presence-weighted aggregate satisfaction becomes a modest
// 0.8x–1.2x modifier on food income and population growth. It is applied by
// wrapping sim.tick exactly the additive way game/crash.ts does (snapshot →
// baseTick → adjust the income delta), so the two wraps compose in either
// order. The modifier is exported as getSocialModifier() so other systems
// (e.g. labour trip yields) can multiply by it without importing the panel.
//
// UI: a compact [G] PEOPLE parchment panel (button + KeyG, mirroring the
// [C] Almanac pattern in ui/codex.ts) with canvas-drawn silhouettes, presence
// dots, a green/yellow/red satisfaction bar, and the voice line.

import { mulberry32, clamp } from "../util/rng";
import type { Simulation } from "./state";
import { CRASH_START, CRASH_END } from "./crash";

// --- model -------------------------------------------------------------------

export type GroupKey = "latji" | "squatters" | "blockies" | "labourers" | "gentry" | "temperance";

export interface SocialGroup {
  key: GroupKey;
  name: string;
  sub: string; // one-line role description (from the brief)
  presence: number; // 0..1 — era-driven
  satisfaction: number; // 0..100 — smoothed toward a computed target
  voice: string; // current one-line voice
}

export interface SocialRefs {
  groups: SocialGroup[];
  /** Presence-weighted aggregate satisfaction, 0..100. */
  aggregate(): number;
  /** Yield/growth modifier, clamped 0.8..1.2. Same value as getSocialModifier(). */
  modifier(): number;
  toggle(): void;
  /** Cheap per-frame call: re-renders only while open and the year moved. */
  update(): void;
}

export interface SocialOptions {
  sim: Simulation;
  /** Optional waterworks hooks — salinity pressure on the blockies. */
  getSalinityCount?: () => number;
  getIrrigatedCount?: () => number;
}

// Module-level so any system can read the current modifier without a handle
// on the installed panel (labour yields, orchestrator wiring, QA).
let currentModifier = 1.0;
export function getSocialModifier(): number {
  return currentModifier;
}

// --- era presence (docs/mildura-history.md §§1-7) ------------------------------

function ramp(y: number, y0: number, y1: number, a: number, b: number): number {
  if (y <= y0) return a;
  if (y >= y1) return b;
  return a + ((b - a) * (y - y0)) / (y1 - y0);
}

function presenceFor(key: GroupKey, y: number): number {
  switch (key) {
    case "latji":
      // Present from the start and through every era; the river people do not
      // leave the river. Pastoral and colony expansion presses their numbers
      // on country down, never to zero (docs §§1-2).
      return ramp(y, 1847, 1890, 1.0, 0.55);
    case "squatters":
      // 1847 Jamieson licence; ~10,000 sheep by 1854; drought and rabbits
      // break the station in the 1870s-80s; run reverts to the government by
      // 1884 and the old order fades after the 1887 Indenture (docs §2).
      if (y < 1847) return 0;
      if (y < 1878) return ramp(y, 1847, 1854, 0.3, 1.0);
      if (y < 1887) return ramp(y, 1878, 1887, 1.0, 0.5);
      return ramp(y, 1887, 1900, 0.5, 0.1);
    case "blockies":
      // Irrigation smallholders arrive with the 1887 Indenture (docs §3).
      if (y < 1887) return 0;
      return ramp(y, 1887, 1895, 0.25, 1.0);
    case "labourers":
      // Navvies dig the channels from 1887; the workforce steadies as the
      // colony becomes a fruit town (docs §§3, 6-7).
      if (y < 1887) return 0;
      return ramp(y, 1887, 1891, 0.3, 0.9);
    case "gentry": {
      // The Chaffeys and the town notables; Rio Vista complete c. 1891;
      // George Chaffey leaves for California in 1897, W.B. stays (docs §§5-6).
      if (y < 1887) return 0;
      const g = ramp(y, 1887, 1891, 0.2, 0.7);
      return y >= 1897 ? Math.min(g, 0.5) : g;
    }
    case "temperance":
      // The dry colony is founded with the settlement itself; the 1915 wine
      // licence and 1919 full licence end the dry era (docs §5).
      if (y < 1887) return 0;
      if (y < 1915) return ramp(y, 1887, 1889, 0.4, 0.8);
      return ramp(y, 1915, 1930, 0.8, 0.4);
  }
}

// --- satisfaction targets -------------------------------------------------------

interface Signals {
  year: number;
  foodSurplus: number; // -1..1.5 — (food - population) normalised
  water01: number; // 0..1 — irrigation water reserve (meaningful post-1889)
  capital01: number; // 0..1 — capital buffer vs a £300 comfort line
  salinity: number; // salted-tile count from waterworks (0 when absent)
  crash: boolean; // 1893-1895 banking crisis window
}

function targetFor(key: GroupKey, s: Signals): number {
  const y = s.year;
  switch (key) {
    case "latji": {
      // River country provides before the runs; from 1847 the meter carries
      // displacement pressure — sheep on the old food grounds, then the colony
      // carving the land (docs §§1-3). Factual, restrained; floor at 20.
      let t = y < 1847 ? 74 + s.foodSurplus * 10 : y < 1887 ? 46 + s.foodSurplus * 8 : 38 + s.foodSurplus * 8;
      return clamp(t, 20, 88);
    }
    case "squatters": {
      if (y < 1887) {
        // Wool-barge prosperity, then drought and rabbits from the late 1870s.
        let t = 62 + s.foodSurplus * 8 + s.capital01 * 12;
        if (y >= 1878) t -= 18;
        return clamp(t, 15, 90);
      }
      return 28; // the Indenture carves up the run; the old order resents it
    }
    case "blockies": {
      // Demand reliable water: nothing grows on the terrace until the pumps
      // lift the river (1889+); salinity is their slow antagonist; the banks
      // foreclose through the Crash; the 1895 Irrigation Trust hands the
      // growers their own water (docs §§4, 6-7).
      let t = 40 + (y >= 1889 ? s.water01 * 32 : -6);
      t -= Math.min(25, s.salinity * 2);
      if (s.crash) t -= 15;
      if (y >= 1896) t += 10;
      return clamp(t, 8, 92);
    }
    case "labourers": {
      // Jobs and wages: capital pays the pay-sheet; the 1895 liquidation left
      // ~£22,000 in wages unpaid; the Working Man's Club (1894) is the one
      // reliable comfort (docs §§5-6).
      let t = 45 + s.capital01 * 25 + s.foodSurplus * 5;
      if (s.crash) t -= 28;
      if (y >= 1894) t += 8;
      return clamp(t, 8, 90);
    }
    case "gentry": {
      // Capital and standing; the Crash and the 1896 Royal Commission at
      // Langtree Hall are their reckoning; dried fruit restores the books.
      let t = 50 + s.capital01 * 30;
      if (s.crash) t -= 25;
      if (y === 1896 || y === 1897) t -= 10;
      if (y >= 1898) t += 5;
      return clamp(t, 10, 92);
    }
    case "temperance": {
      // A cross-cutting tension, not a bloc that wins: the members'-club
      // loophole (1894-95) frays the ban, the 1915 wine licence and 1919 full
      // licence end the dry era (docs §5).
      let t = 58 + s.foodSurplus * 4;
      if (y >= 1894) t -= 8;
      if (y >= 1915) t -= 10;
      if (y >= 1919) t -= 14;
      return clamp(t, 15, 85);
    }
  }
}

// --- voices (one line, band + era) -----------------------------------------------

function voiceFor(key: GroupKey, sat: number, y: number): string {
  const band = sat >= 60 ? 2 : sat >= 38 ? 1 : 0;
  switch (key) {
    case "latji":
      if (y < 1847) return "The river gives as it always has — fish, mussels, waterfowl on the floodplain.";
      if (band === 2) return "We remain on the river, as we have for tens of thousands of years.";
      if (band === 1)
        return y < 1887
          ? "Sheep graze the old food grounds now; some of us shepherd for station wages."
          : "The blocks spread over the old food grounds; still we fish the river as we always have.";
      return "The runs and the blocks press upon our country; still we stay by the river.";
    case "squatters":
      if (y >= 1887) return "The Indenture carves the run into fruit blocks. The old wool order is done.";
      if (band === 2) return "Ten thousand sheep on the run, and wool away by barge at high water.";
      if (band === 1) return "Drought bites and the rabbits strip the paddocks bare.";
      return "The station is breaking; the lease will revert to the Crown.";
    case "blockies":
      if (y < 1889) return "Nothing grows on the high terrace until the pumps lift the river.";
      if (band === 2) return "The vines take hold — the water comes when it is promised.";
      if (band === 1)
        return y >= 1896
          ? "The Trust is ours now; the channels must still be kept true."
          : "The channels run short; we petition the company over water reliability.";
      return "Salt rises under the vines and the bank holds the deed.";
    case "labourers":
      if (band === 2)
        return y >= 1894 ? "Steady wages, and the Working Man's Club at the end of the day." : "Steady work on the channels, and the pay-sheet is met.";
      if (band === 1) return "Work is patchy; we wait on the company's pay-sheet.";
      return y >= 1895
        ? "Chaffey Brothers owe twenty-two thousand pounds in wages, and the banks are shut."
        : "The pay-sheet is short and the camps grow restless.";
    case "gentry":
      if (band === 2) return "Capital flows, and Rio Vista's gardens are the equal of any in the colony.";
      if (band === 1) return "The books are strained; the Mildura Club keeps its own counsel.";
      return y >= 1896 ? "The Royal Commission at Langtree Hall reads our failures into the record." : "The banks are calling in their loans.";
    case "temperance":
      if (y >= 1919) return "Wine licence, then full licence — the dry era is over.";
      if (band === 2) return "The colony stays dry: coffee palaces, not public houses.";
      if (band === 1) return "The members' clubs pour what the law never quite forbade.";
      return "The loopholes widen; the dry colony is dry in name.";
  }
}

// --- canvas icons (simple silhouettes, no emoji) -----------------------------------

function drawIcon(key: GroupKey): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 80;
  const x = c.getContext("2d")!;
  const bg = x.createLinearGradient(0, 0, 0, 80);
  bg.addColorStop(0, "#ecdcae");
  bg.addColorStop(1, "#c9ad74");
  x.fillStyle = bg;
  x.fillRect(0, 0, 80, 80);
  x.strokeStyle = "#8a6a1c";
  x.lineWidth = 3;
  x.strokeRect(3, 3, 74, 74);
  x.fillStyle = "#5d4226";
  x.strokeStyle = "#5d4226";
  switch (key) {
    case "latji": {
      // river current lines and a fish silhouette
      x.lineWidth = 3.5;
      for (const yy of [22, 32]) {
        x.beginPath();
        for (let i = 0; i <= 8; i++) x.lineTo(12 + i * 7, yy + (i % 2 ? -3 : 3));
        x.stroke();
      }
      x.beginPath(); // Murray cod body
      x.ellipse(38, 54, 17, 8, 0, 0, Math.PI * 2);
      x.fill();
      x.beginPath(); // tail
      x.moveTo(54, 54);
      x.lineTo(66, 46);
      x.lineTo(66, 62);
      x.closePath();
      x.fill();
      break;
    }
    case "squatters": {
      // wool bale with cross straps
      x.fillRect(16, 26, 48, 34);
      x.strokeStyle = "#ecdcae";
      x.lineWidth = 3;
      x.beginPath();
      x.moveTo(16, 43);
      x.lineTo(64, 43);
      x.moveTo(32, 26);
      x.lineTo(32, 60);
      x.moveTo(48, 26);
      x.lineTo(48, 60);
      x.stroke();
      break;
    }
    case "blockies": {
      // vine post with a grape cluster
      x.fillRect(37, 18, 6, 46);
      x.fillRect(20, 24, 40, 5);
      for (const [gx, gy] of [
        [30, 38],
        [38, 38],
        [46, 38],
        [34, 46],
        [42, 46],
        [38, 54],
      ]) {
        x.beginPath();
        x.arc(gx, gy, 5.5, 0, Math.PI * 2);
        x.fill();
      }
      break;
    }
    case "labourers": {
      // swagman hat: crown + wide brim
      x.beginPath();
      x.ellipse(40, 48, 26, 8, 0, 0, Math.PI * 2);
      x.fill();
      x.beginPath();
      x.ellipse(40, 38, 13, 12, 0, Math.PI, 0);
      x.fill();
      x.fillRect(27, 38, 26, 8);
      break;
    }
    case "gentry": {
      // top hat
      x.fillRect(24, 20, 32, 30);
      x.beginPath();
      x.ellipse(40, 52, 24, 7, 0, 0, Math.PI * 2);
      x.fill();
      x.fillStyle = "#c9ad74";
      x.fillRect(24, 40, 32, 4);
      break;
    }
    case "temperance": {
      // coffee cup and saucer (the coffee-palace colony)
      x.beginPath();
      x.moveTo(22, 30);
      x.lineTo(52, 30);
      x.lineTo(48, 52);
      x.lineTo(26, 52);
      x.closePath();
      x.fill();
      x.lineWidth = 4;
      x.beginPath();
      x.arc(54, 38, 8, -Math.PI / 2, Math.PI / 2);
      x.stroke();
      x.beginPath();
      x.ellipse(38, 58, 22, 5, 0, 0, Math.PI * 2);
      x.fill();
      break;
    }
  }
  return c;
}

// --- UI chrome (parchment/ironwood, mirrors ui/codex.ts) ----------------------------

const SOCIAL_CSS = `
  .social-btn {
    position: absolute; top: 14px; left: 466px;
    font-family: Georgia, serif; font-size: 11px; letter-spacing: 1px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 8px 12px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 2px solid #191009; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000; box-shadow: 0 4px 12px #0008;
  }
  .social-btn:hover { outline-color: #c9b26a; color: #ffd; }
  .social-btn .key { color: #b8912f; margin-right: 5px; }
  .social-panel {
    left: 354px; top: 58px; width: 428px; max-width: calc(100vw - 380px);
    max-height: 74vh; display: flex; flex-direction: column; z-index: 25;
  }
  .social-panel.hidden { display: none; }
  .social-sub {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 14px; border-bottom: 1px solid #8a6a1c55;
    font-variant: small-caps; letter-spacing: 0.8px; color: #6b5410;
    font-size: 12.5px; font-weight: 700;
  }
  .social-sub button {
    font-family: Georgia, serif; font-size: 10.5px; letter-spacing: 0.5px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 4px 10px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 1px solid #0d0805; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000;
  }
  .social-sub button:hover { outline-color: #c9b26a; color: #ffd; }
  .social-list { overflow-y: auto; padding: 4px 14px 12px; }
  .social-row {
    display: flex; gap: 10px; padding: 8px 2px; align-items: center;
    border-bottom: 1px dashed #8a6a1c44;
  }
  .social-row:last-child { border-bottom: none; }
  .social-row.absent { opacity: 0.45; }
  .social-icon {
    width: 44px; height: 44px; flex: none; border: 2px solid #191009;
    outline: 1px solid #77613a; border-radius: 3px; overflow: hidden;
  }
  .social-icon canvas { width: 44px !important; height: 44px !important; display: block; }
  .social-name {
    font-weight: 700; color: #46351c; font-variant: small-caps;
    letter-spacing: 0.5px; font-size: 13.5px;
  }
  .social-dots { display: inline-block; margin-left: 7px; letter-spacing: 2px; }
  .social-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    margin-right: 3px; background: #b8912f; box-shadow: 0 0 0 1px #5d422655 inset; }
  .social-dot.off { background: #bfa76d55; }
  .social-barwrap { height: 8px; margin: 4px 0 3px; border-radius: 4px;
    background: #00000022; border: 1px solid #5d422655; overflow: hidden; }
  .social-bar { height: 100%; border-radius: 3px; transition: width 0.4s; }
  .social-bar.green { background: linear-gradient(#7dbb5e, #4e8a36); }
  .social-bar.yellow { background: linear-gradient(#d9b95c, #b8912f); }
  .social-bar.red { background: linear-gradient(#c96a4e, #96402a); }
  .social-voice { font-size: 11.8px; line-height: 1.32; color: #2b2013; font-style: italic; }
  .social-row.absent .social-voice { font-style: normal; color: #6b5410; }
`;

// --- install ------------------------------------------------------------------------

const GROUP_DEFS: { key: GroupKey; name: string; sub: string }[] = [
  { key: "latji", name: "Latji Latji", sub: "the river people — knowledge of land and water" },
  { key: "squatters", name: "Squatters & Pastoralists", sub: "the old wool order" },
  { key: "blockies", name: "Block Settlers & Growers", sub: "the irrigation smallholders" },
  { key: "labourers", name: "Working Men & Labourers", sub: "the navvies and workers" },
  { key: "gentry", name: "The Elite & Gentry", sub: "capital and civic notables" },
  { key: "temperance", name: "Temperance & Drinkers", sub: "the dry colony's cross-cutting tension" },
];

export function installSocial(opts: SocialOptions): SocialRefs {
  const { sim } = opts;
  const root = document.getElementById("ui")!;

  const groups: SocialGroup[] = GROUP_DEFS.map((d) => ({
    ...d,
    presence: presenceFor(d.key, sim.year),
    satisfaction: 60,
    voice: "",
  }));

  function signals(): Signals {
    const r = sim.resources;
    return {
      year: sim.year,
      foodSurplus: clamp((r.food - r.population) / Math.max(12, r.population), -1, 1.5),
      water01: clamp(r.water / 100, 0, 1),
      capital01: clamp(r.capital / 300, 0, 1),
      salinity: opts.getSalinityCount ? opts.getSalinityCount() : 0,
      crash: sim.year >= CRASH_START && sim.year <= CRASH_END,
    };
  }

  function aggregate(): number {
    let sum = 0;
    let w = 0;
    for (const g of groups) {
      if (g.presence <= 0.01) continue;
      sum += g.satisfaction * g.presence;
      w += g.presence;
    }
    return w > 0 ? sum / w : 60;
  }

  /** Recompute presences, ease satisfaction toward targets, refresh voices. */
  function recompute(step: number): void {
    const s = signals();
    for (const g of groups) {
      g.presence = presenceFor(g.key, s.year);
      const target = targetFor(g.key, s);
      g.satisfaction = clamp(g.satisfaction + (target - g.satisfaction) * step, 0, 100);
      g.voice = voiceFor(g.key, g.satisfaction, s.year);
    }
    currentModifier = clamp(0.8 + (0.4 * aggregate()) / 100, 0.8, 1.2);
  }
  recompute(1); // settle immediately on install (also covers restored saves)

  // --- sim effects: wrap sim.tick the additive crash.ts way (order-independent) ---
  const baseTick = sim.tick.bind(sim);
  sim.tick = () => {
    const yearBefore = sim.year;
    const r = sim.resources;
    const before = { food: r.food, population: r.population };
    baseTick();
    if (sim.year === yearBefore) return; // paused — the tick was a no-op
    recompute(0.25);
    const mod = currentModifier;
    // Food income scales with the colony's temper (losses always stand).
    const gained = r.food - before.food;
    if (gained > 0) r.food = before.food + Math.round(gained * mod);
    // Population: discontent deters arrivals; contentment attracts them.
    const roll = mulberry32(((sim.year * 0x85ebca6b) ^ 0x50c1a1) >>> 0)();
    const grew = r.population > before.population;
    const inCrash = sim.year >= CRASH_START && sim.year <= CRASH_END;
    if (grew && mod < 0.9 && roll < 0.5) {
      r.population = before.population; // family thinks better of coming
    } else if (!grew && mod > 1.1 && !inCrash && r.food > r.population * 2 && roll < 0.3) {
      r.population += 1; // word of a contented colony travels
    }
  };

  // --- UI ---------------------------------------------------------------------
  if (!document.getElementById("social-style")) {
    const style = document.createElement("style");
    style.id = "social-style";
    style.textContent = SOCIAL_CSS;
    document.head.appendChild(style);
  }

  const btn = document.createElement("button");
  btn.className = "social-btn";
  btn.innerHTML = `<span class="key">[G]</span>People`;
  root.appendChild(btn);

  const panel = document.createElement("div");
  panel.className = "panel parchment social-panel hidden";
  panel.innerHTML = `
    <h1>The People of the Colony</h1>
    <div class="social-sub">
      <span id="social-mood"></span>
      <button id="social-close">Close [G]</button>
    </div>
    <div class="social-list" id="social-list"></div>
  `;
  root.appendChild(panel);

  const moodEl = panel.querySelector<HTMLElement>("#social-mood")!;
  const listEl = panel.querySelector<HTMLElement>("#social-list")!;
  const icons = new Map<GroupKey, HTMLCanvasElement>();

  let open = false;
  let renderedYear = -1;

  function barClass(sat: number): string {
    return sat >= 60 ? "green" : sat >= 38 ? "yellow" : "red";
  }

  function render(): void {
    renderedYear = sim.year;
    listEl.innerHTML = "";
    for (const g of groups) {
      const absent = g.presence <= 0.01;
      const row = document.createElement("div");
      row.className = absent ? "social-row absent" : "social-row";

      const icon = document.createElement("div");
      icon.className = "social-icon";
      let cnv = icons.get(g.key);
      if (!cnv) {
        cnv = drawIcon(g.key);
        icons.set(g.key, cnv);
      }
      icon.appendChild(cnv);
      row.appendChild(icon);

      const txt = document.createElement("div");
      txt.style.flex = "1";
      const name = document.createElement("div");
      name.className = "social-name";
      name.textContent = g.name;
      const dots = document.createElement("span");
      dots.className = "social-dots";
      const filled = Math.round(g.presence * 5);
      for (let i = 0; i < 5; i++) {
        const d = document.createElement("span");
        d.className = i < filled ? "social-dot" : "social-dot off";
        dots.appendChild(d);
      }
      name.appendChild(dots);
      txt.appendChild(name);

      if (!absent) {
        const wrap = document.createElement("div");
        wrap.className = "social-barwrap";
        const bar = document.createElement("div");
        bar.className = `social-bar ${barClass(g.satisfaction)}`;
        bar.style.width = `${Math.round(g.satisfaction)}%`;
        wrap.appendChild(bar);
        txt.appendChild(wrap);
      }
      const voice = document.createElement("div");
      voice.className = "social-voice";
      voice.textContent = absent ? g.sub : `"${g.voice}"`;
      txt.appendChild(voice);

      row.appendChild(txt);
      listEl.appendChild(row);
    }
    const agg = Math.round(aggregate());
    const temper = agg >= 60 ? "content" : agg >= 38 ? "uneasy" : "restless";
    moodEl.textContent = `Colony temper: ${temper} (${agg}) — yields x${currentModifier.toFixed(2)}`;
  }

  const refs: SocialRefs = {
    groups,
    aggregate,
    modifier: () => currentModifier,
    toggle() {
      open = !open;
      panel.classList.toggle("hidden", !open);
      if (open) render();
    },
    update() {
      if (open && sim.year !== renderedYear) render();
    },
  };

  btn.addEventListener("click", refs.toggle);
  panel.querySelector("#social-close")!.addEventListener("click", refs.toggle);
  window.addEventListener("keydown", (e) => {
    if (e.code === "KeyG") refs.toggle();
    else if (e.code === "Escape" && open) refs.toggle();
  });

  return refs;
}
