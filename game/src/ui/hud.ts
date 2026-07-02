// Mock-up UI: four corner panels — parchment mission panel (top-left), ornate
// minimap + objectives (top-right), status panel with portrait/bars/counters
// (bottom-left), inventory slot-grid with hotkey actions (bottom-right).
// All icons are canvas-drawn (no emoji → renders identically everywhere).
import { GRID_W, GRID_H } from "../config";
import type { GameMap, Tile } from "../map/mapData";
import type { Settler } from "../render/units";
import { getTaskLabel } from "../game/labour";

type IconKind = "timber" | "water" | "food" | "wool" | "pop" | "pound";

function drawIcon(kind: IconKind, size = 22): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const x = c.getContext("2d")!;
  const s = size / 24;
  x.scale(s, s);
  x.lineWidth = 1.4;
  switch (kind) {
    case "timber": {
      x.fillStyle = "#8a5a33";
      x.strokeStyle = "#4a2f18";
      for (const [px, py] of [[3, 14], [11, 14], [7, 7]]) {
        x.beginPath();
        (x as any).roundRect(px, py, 10, 7, 3);
        x.fill();
        x.stroke();
        x.fillStyle = "#a06b3d";
      }
      x.fillStyle = "#d9b184";
      x.beginPath();
      x.arc(8, 17.5, 2.2, 0, 7);
      x.fill();
      break;
    }
    case "water": {
      x.fillStyle = "#4d90c9";
      x.strokeStyle = "#1d4a70";
      x.beginPath();
      x.moveTo(12, 3);
      x.bezierCurveTo(18, 11, 19, 15, 12, 20);
      x.bezierCurveTo(5, 15, 6, 11, 12, 3);
      x.fill();
      x.stroke();
      x.fillStyle = "#bfe0f5";
      x.beginPath();
      x.arc(10, 13, 2, 0, 7);
      x.fill();
      break;
    }
    case "food": {
      x.fillStyle = "#b3702e";
      x.strokeStyle = "#5d3814";
      x.beginPath();
      x.ellipse(10, 12, 7, 5, -0.6, 0, 7);
      x.fill();
      x.stroke();
      x.strokeStyle = "#e8d5a8";
      x.lineWidth = 2.4;
      x.beginPath();
      x.moveTo(15, 8);
      x.lineTo(20, 4);
      x.stroke();
      x.fillStyle = "#e8d5a8";
      x.beginPath();
      x.arc(20.5, 3.5, 2, 0, 7);
      x.fill();
      break;
    }
    case "wool": {
      x.fillStyle = "#efe6d2";
      x.strokeStyle = "#8f8468";
      for (const [px, py, r] of [[8, 13, 5], [13, 10, 5.4], [17, 14, 4.4], [12, 15, 5]]) {
        x.beginPath();
        x.arc(px, py, r, 0, 7);
        x.fill();
      }
      x.stroke();
      break;
    }
    case "pop": {
      x.fillStyle = "#d9c9a2";
      x.strokeStyle = "#5a4a2e";
      x.beginPath();
      x.arc(12, 8, 4, 0, 7);
      x.fill();
      x.stroke();
      x.beginPath();
      x.moveTo(5, 21);
      x.bezierCurveTo(6, 13, 18, 13, 19, 21);
      x.fill();
      x.stroke();
      break;
    }
    case "pound": {
      x.fillStyle = "#e3c34e";
      x.strokeStyle = "#6b5410";
      x.beginPath();
      x.arc(12, 12, 9, 0, 7);
      x.fill();
      x.stroke();
      x.fillStyle = "#5d4a10";
      x.font = "bold 13px Georgia";
      x.textAlign = "center";
      x.textBaseline = "middle";
      x.fillText("£", 12, 13);
      break;
    }
  }
  return c;
}

// --- Era personas: detailed painted portraits (96px, shown at 64) -------------
import type { PersonaKey } from "../game/milestones";

interface PersonaSpec {
  name: string;
  role: string;
  plate: string; // gold-frame nameplate text, mock-up style
}
export const PERSONAS: Record<PersonaKey, PersonaSpec> = {
  latji: {
    name: "Latji Latji Elder",
    role: "First People of the River",
    plate: "Pre-Colonial Elder (~1788)",
  },
  sturt: { name: "Capt. Charles Sturt", role: "Explorer, 1830", plate: "Capt. Charles Sturt (1830)" },
  squatter: { name: "Hugh Jamieson", role: "Squatter, Mildura Run", plate: "Hugh Jamieson (1847)" },
  chaffey: { name: 'W.B. Chaffey — "The Boss"', role: "Irrigationist", plate: "W.B. Chaffey (1887)" },
};

function portraitBase(
  sky0: string,
  sky1: string
): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = c.height = 96;
  c.style.width = c.style.height = "64px";
  const x = c.getContext("2d")!;
  const bg = x.createLinearGradient(0, 0, 0, 96);
  bg.addColorStop(0, sky0);
  bg.addColorStop(1, sky1);
  x.fillStyle = bg;
  x.fillRect(0, 0, 96, 96);
  return [c, x];
}

function face(
  x: CanvasRenderingContext2D,
  skin: string,
  shade: string,
  eye = "#2b1d12"
): void {
  // neck + head
  x.fillStyle = shade;
  x.fillRect(41, 52, 14, 12);
  x.fillStyle = skin;
  x.beginPath();
  x.ellipse(48, 42, 17, 20, 0, 0, 7);
  x.fill();
  // side shading
  x.fillStyle = shade;
  x.globalAlpha = 0.35;
  x.beginPath();
  x.ellipse(55, 44, 9, 17, 0.15, -1.2, 1.4);
  x.fill();
  x.globalAlpha = 1;
  // eyes
  x.fillStyle = "#f2ede2";
  x.beginPath();
  x.ellipse(41.5, 40, 3.4, 2.4, 0, 0, 7);
  x.ellipse(54.5, 40, 3.4, 2.4, 0, 0, 7);
  x.fill();
  x.fillStyle = eye;
  x.beginPath();
  x.arc(42, 40.4, 1.6, 0, 7);
  x.arc(55, 40.4, 1.6, 0, 7);
  x.fill();
  // nose + mouth
  x.strokeStyle = shade;
  x.lineWidth = 1.6;
  x.beginPath();
  x.moveTo(48, 42);
  x.lineTo(46.5, 48);
  x.lineTo(49, 48.6);
  x.stroke();
  x.beginPath();
  x.moveTo(43.5, 54);
  x.quadraticCurveTo(48, 56.2, 52.5, 54);
  x.stroke();
}

function brows(x: CanvasRenderingContext2D, color: string, w = 2.4): void {
  x.strokeStyle = color;
  x.lineWidth = w;
  x.beginPath();
  x.moveTo(37.5, 36);
  x.quadraticCurveTo(41.5, 34.2, 45, 36);
  x.moveTo(51, 36);
  x.quadraticCurveTo(54.5, 34.2, 58.5, 36);
  x.stroke();
}

function drawLatji(): HTMLCanvasElement {
  const [c, x] = portraitBase("#f4c684", "#b86f3e"); // river dawn
  // possum-skin cloak over the shoulders
  x.fillStyle = "#7a5a3c";
  x.beginPath();
  x.moveTo(10, 96);
  x.bezierCurveTo(16, 66, 80, 66, 86, 96);
  x.fill();
  x.strokeStyle = "#5d4429";
  x.lineWidth = 2;
  for (let i = 0; i < 4; i++) {
    x.beginPath();
    x.moveTo(24 + i * 13, 96);
    x.quadraticCurveTo(28 + i * 13, 80, 34 + i * 12, 72);
    x.stroke();
  }
  face(x, "#5d4028", "#402a18");
  // grey-flecked curly hair + full beard
  x.fillStyle = "#3d332b";
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI - Math.PI;
    x.beginPath();
    x.arc(48 + Math.cos(a) * 16, 30 + Math.sin(a) * 12, 4.6, 0, 7);
    x.fill();
  }
  x.fillStyle = "#6e655c";
  for (let i = 0; i < 9; i++) {
    x.beginPath();
    x.arc(34 + i * 3.4, 24 - (i % 3) * 3, 2.2, 0, 7);
    x.fill();
  }
  // beard
  x.fillStyle = "#57504a";
  x.beginPath();
  x.moveTo(33, 46);
  x.quadraticCurveTo(35, 66, 48, 68);
  x.quadraticCurveTo(61, 66, 63, 46);
  x.quadraticCurveTo(56, 55, 48, 55);
  x.quadraticCurveTo(40, 55, 33, 46);
  x.fill();
  brows(x, "#57504a", 2.8);
  // red-ochre headband
  x.fillStyle = "#a3402a";
  x.fillRect(31, 27, 34, 5);
  x.fillStyle = "#c2542f";
  x.fillRect(31, 27, 34, 2);
  return c;
}

function drawSturt(): HTMLCanvasElement {
  const [c, x] = portraitBase("#9cc4e0", "#4d84a8"); // river blue
  // navy coat with epaulettes and brass buttons
  x.fillStyle = "#24344d";
  x.beginPath();
  x.moveTo(10, 96);
  x.bezierCurveTo(16, 64, 80, 64, 86, 96);
  x.fill();
  x.fillStyle = "#c9a227";
  x.fillRect(14, 70, 14, 5);
  x.fillRect(68, 70, 14, 5);
  // white cravat
  x.fillStyle = "#efe9da";
  x.beginPath();
  x.moveTo(42, 66);
  x.lineTo(54, 66);
  x.lineTo(50, 82);
  x.lineTo(46, 82);
  x.fill();
  x.fillStyle = "#d8b23a";
  for (const py of [78, 86]) {
    x.beginPath();
    x.arc(36, py, 1.8, 0, 7);
    x.arc(60, py, 1.8, 0, 7);
    x.fill();
  }
  face(x, "#e0b088", "#a97a52");
  // brown side-whiskers
  x.fillStyle = "#5d4530";
  x.beginPath();
  x.ellipse(33.5, 46, 3.4, 8, 0.15, 0, 7);
  x.ellipse(62.5, 46, 3.4, 8, -0.15, 0, 7);
  x.fill();
  brows(x, "#5d4530");
  // black peaked cap with gold band
  x.fillStyle = "#1c2026";
  x.beginPath();
  x.ellipse(48, 26, 19, 9, 0, Math.PI, 0);
  x.fill();
  x.fillRect(29, 22, 38, 7);
  x.fillStyle = "#c9a227";
  x.fillRect(29, 27, 38, 2.6);
  x.fillStyle = "#0f1216";
  x.beginPath();
  x.ellipse(48, 30.5, 15, 3.4, 0, 0, Math.PI);
  x.fill();
  return c;
}

function drawSquatter(): HTMLCanvasElement {
  const [c, x] = portraitBase("#e8d590", "#b3924e"); // paddock gold
  // olive work shirt + red neckerchief
  x.fillStyle = "#667048";
  x.beginPath();
  x.moveTo(10, 96);
  x.bezierCurveTo(16, 64, 80, 64, 86, 96);
  x.fill();
  x.strokeStyle = "#4d5636";
  x.lineWidth = 1.6;
  x.beginPath();
  x.moveTo(48, 70);
  x.lineTo(48, 96);
  x.stroke();
  x.fillStyle = "#9c3a2a";
  x.beginPath();
  x.moveTo(40, 64);
  x.lineTo(56, 64);
  x.lineTo(48, 76);
  x.fill();
  face(x, "#d9a679", "#a5754a");
  // big brown beard + moustache
  x.fillStyle = "#5d4226";
  x.beginPath();
  x.moveTo(32, 44);
  x.quadraticCurveTo(34, 68, 48, 70);
  x.quadraticCurveTo(62, 68, 64, 44);
  x.quadraticCurveTo(56, 53, 48, 53);
  x.quadraticCurveTo(40, 53, 32, 44);
  x.fill();
  x.beginPath();
  x.ellipse(48, 52, 8.5, 3, 0, 0, 7);
  x.fill();
  brows(x, "#5d4226", 3);
  // wide slouch hat
  x.fillStyle = "#8a713f";
  x.beginPath();
  x.ellipse(48, 27, 25, 7.5, 0, 0, 7);
  x.fill();
  x.fillStyle = "#9c8149";
  x.beginPath();
  x.ellipse(48, 19, 13, 9, 0, Math.PI, 0);
  x.fill();
  x.fillRect(35, 17, 26, 9);
  x.fillStyle = "#6b5630";
  x.fillRect(35, 23, 26, 3);
  return c;
}

function drawChaffey(): HTMLCanvasElement {
  const [c, x] = portraitBase("#bfe0d2", "#6f9c6a"); // vine green
  // charcoal suit, white wing collar, gold watch chain
  x.fillStyle = "#3a3a42";
  x.beginPath();
  x.moveTo(10, 96);
  x.bezierCurveTo(16, 64, 80, 64, 86, 96);
  x.fill();
  x.fillStyle = "#efe9da";
  x.beginPath();
  x.moveTo(43, 64);
  x.lineTo(53, 64);
  x.lineTo(51, 76);
  x.lineTo(45, 76);
  x.fill();
  x.fillStyle = "#23252c";
  x.beginPath();
  x.moveTo(44, 70);
  x.lineTo(52, 70);
  x.lineTo(49, 84);
  x.lineTo(47, 84);
  x.fill();
  x.strokeStyle = "#d8b23a";
  x.lineWidth = 1.6;
  x.beginPath();
  x.moveTo(30, 84);
  x.quadraticCurveTo(48, 92, 66, 84);
  x.stroke();
  face(x, "#e0b088", "#a97a52");
  // neat dark hair under a black bowler + handlebar moustache
  x.fillStyle = "#2b2320";
  x.beginPath();
  x.ellipse(48, 27, 21, 6.5, 0, 0, 7);
  x.fill();
  x.beginPath();
  x.ellipse(48, 18, 12.5, 9.5, 0, Math.PI, 0);
  x.fill();
  x.fillRect(35.5, 16, 25, 10);
  x.fillStyle = "#17130f";
  x.fillRect(35.5, 24, 25, 2.4);
  x.fillStyle = "#4a3524";
  x.beginPath();
  x.ellipse(41, 51.5, 6, 2.6, 0.28, 0, 7);
  x.ellipse(55, 51.5, 6, 2.6, -0.28, 0, 7);
  x.fill();
  brows(x, "#4a3524");
  return c;
}

const PORTRAIT_PAINTERS: Record<PersonaKey, () => HTMLCanvasElement> = {
  latji: drawLatji,
  sturt: drawSturt,
  squatter: drawSquatter,
  chaffey: drawChaffey,
};

// Portrait element with an asset upgrade path: if real painted art exists at
// /portraits/<key>.jpg (game/public/portraits/), it replaces the procedural
// canvas automatically. Drop the files in — no code change needed.
const portraitArt: Partial<Record<PersonaKey, HTMLImageElement | null>> = {};
function portraitEl(key: PersonaKey): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "portrait-art";
  const cached = portraitArt[key];
  if (cached) {
    holder.appendChild(cached.cloneNode() as HTMLImageElement);
    return holder;
  }
  holder.appendChild(PORTRAIT_PAINTERS[key]());
  if (cached === undefined) {
    const img = new Image();
    img.onload = () => {
      portraitArt[key] = img;
      holder.innerHTML = "";
      holder.appendChild(img.cloneNode() as HTMLImageElement);
    };
    img.onerror = () => {
      portraitArt[key] = null; // remember the miss; keep the canvas
    };
    img.src = `portraits/${key}.jpg`;
  }
  return holder;
}

export interface MilestoneToast {
  year: number;
  title: string;
  body: string;
  build?: string;
  tone?: "news" | "alarm";
  persona?: PersonaKey; // reveals the era's framed portrait card beside the clipping
}

export interface HudRefs {
  /** count > 1 shows the group line ("4 settlers selected") instead of s. */
  setSelected(s: Settler | null, count?: number): void;
  setPersona(key: PersonaKey): void;
  showMilestone(m: MilestoneToast): void;
  /** Era gates override the objectives panel; null restores the flavour lines. */
  setObjectives(html: string | null): void;
  /** True while a newspaper banner is showing or queued (clock pauses on it). */
  toastActive(): boolean;
  update(vals: {
    year: number;
    era: string;
    paused: boolean;
    food: number;
    timber: number;
    wool: number;
    water: number;
    capital: number;
    population: number;
    sessionLabel: string;
  }): void;
  drawMinimap(
    unitDots: { x: number; y: number; kind: "settler" | "sheep" | "home" }[],
    camTile: { x: number; y: number }
  ): void;
  onMinimapClick: ((fx: number, fy: number) => void) | null;
  onAction: ((action: string) => void) | null;
  showTooltip(html: string, px: number, py: number): void;
  hideTooltip(): void;
  flashAction(action: string): void;
}

export function buildHud(map: GameMap, minimapColour: (t: Tile) => string): HudRefs {
  const root = document.getElementById("ui")!;
  root.innerHTML = `
    <div class="panel parchment top-left">
      <h1>Mildura — Colony on the Murray</h1>
      <div class="body">
        <p><b>CONTROLS:</b> Click / Drag: Select Settlers,<br>
        Right-Click to Move &middot; Middle-Drag: Look,<br>
        W,A,S,D to Pan &middot; Wheel to Zoom</p>
        <p><b>GAME STATUS:</b> <span id="hud-era">—</span><br>
        <b>YEAR:</b> <span id="hud-year">—</span> <span id="hud-paused"></span><br>
        <b>ANIMATION:</b> Enabled</p>
      </div>
    </div>

    <div class="top-right">
      <div class="panel dark minimap-frame"><canvas id="minimap" width="220" height="180"></canvas></div>
      <div class="panel parchment objectives">
        <h2>Objectives:</h2>
        <div class="body" id="hud-objectives"></div>
      </div>
    </div>

    <div class="panel dark bottom-left">
      <h2 class="bar-title" id="hud-persona-name">Settler Status</h2>
      <div class="status-row">
        <div class="portrait" id="hud-portrait"></div>
        <div class="bars">
          <div id="hud-persona-role" class="persona-role"></div>
          <div class="bar-line"><span class="heart"></span><div class="bar"><div id="bar-health" class="fill green" style="width:88%"></div></div></div>
          <div class="bar-line"><span class="bolt"></span><div class="bar"><div id="bar-energy" class="fill yellow" style="width:64%"></div></div></div>
          <div id="hud-selname" class="sel-name">No settler selected</div>
        </div>
      </div>
      <div class="counters" id="hud-counters"></div>
    </div>

    <div id="milestone-wrap" class="hidden">
      <div id="persona-card">
        <div class="pc-img" id="pc-img"></div>
        <div class="pc-plate" id="pc-plate"></div>
      </div>
      <div id="milestone" class="panel parchment milestone">
        <div class="masthead">The Mildura Cultivator — Extra</div>
        <h1 id="milestone-title"></h1>
        <img id="milestone-art" class="hidden" alt="" />
        <div class="body">
          <p id="milestone-body"></p>
          <div id="milestone-build" class="build-chip hidden"></div>
        </div>
      </div>
    </div>

    <div class="panel dark bottom-right">
      <h2 class="bar-title">Stores</h2>
      <div class="slots" id="hud-slots"></div>
      <div class="actions">
        <button data-action="survey"><span class="key">[1]</span>SURVEY</button>
        <button data-action="chop"><span class="key">[2]</span>CHOP</button>
        <button data-action="gather"><span class="key">[3]</span>GATHER</button>
        <button data-action="muster"><span class="key">[4]</span>MUSTER</button>
      </div>
    </div>

    <div id="tooltip"></div>
  `;

  // portrait is set via setPersona() once the sim year is known

  // resource counters (status panel): timber, water, food — like the mock-up row
  const counters = document.getElementById("hud-counters")!;
  const counterVals: Record<string, HTMLElement> = {};
  for (const kind of ["timber", "water", "food"] as IconKind[]) {
    const d = document.createElement("div");
    d.className = "counter";
    d.appendChild(drawIcon(kind));
    const v = document.createElement("b");
    v.textContent = "0";
    d.appendChild(v);
    counterVals[kind] = v;
    counters.appendChild(d);
  }

  // inventory slots: timber, wool, food, water, £, pop + 2 empty
  const slotDefs: (IconKind | null)[] = ["timber", "wool", "food", "water", "pound", "pop", null, null];
  const slotsEl = document.getElementById("hud-slots")!;
  const slotVals: Partial<Record<IconKind, HTMLElement>> = {};
  for (const def of slotDefs) {
    const s = document.createElement("div");
    s.className = "slot";
    if (def) {
      s.appendChild(drawIcon(def, 26));
      const b = document.createElement("span");
      b.className = "badge";
      b.textContent = "0";
      s.appendChild(b);
      slotVals[def] = b;
    }
    slotsEl.appendChild(s);
  }

  // Minimap base layer, prerendered from tiles.
  const mm = document.getElementById("minimap") as HTMLCanvasElement;
  const mctx = mm.getContext("2d")!;
  const base = document.createElement("canvas");
  base.width = GRID_W;
  base.height = GRID_H;
  const bctx = base.getContext("2d")!;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      bctx.fillStyle = minimapColour(map.at(x, y));
      bctx.fillRect(x, y, 1, 1);
    }
  }

  const tooltip = document.getElementById("tooltip")!;
  const objectives = document.getElementById("hud-objectives")!;
  let objectivesOverride: string | null = null;
  const selName = document.getElementById("hud-selname")!;

  // Milestone toast queue: one clipping (plus persona card) at a time, ~9s each.
  const wrapEl = document.getElementById("milestone-wrap")!;
  const milestoneEl = document.getElementById("milestone")!;
  const cardEl = document.getElementById("persona-card")!;
  const queue: MilestoneToast[] = [];
  let showing = false;
  function pump() {
    if (showing) return;
    const m = queue.shift();
    if (!m) return;
    showing = true;
    document.getElementById("milestone-title")!.textContent = m.title;
    document.getElementById("milestone-body")!.textContent = m.body;
    const chip = document.getElementById("milestone-build")!;
    if (m.build) {
      chip.textContent = `★ Special build unlocked: ${m.build}`;
      chip.classList.remove("hidden");
    } else {
      chip.classList.add("hidden");
    }
    if (m.persona) {
      const holder = document.getElementById("pc-img")!;
      holder.innerHTML = "";
      holder.appendChild(portraitEl(m.persona));
      document.getElementById("pc-plate")!.textContent = PERSONAS[m.persona].plate;
      cardEl.classList.remove("hidden");
    } else {
      cardEl.classList.add("hidden");
    }
    // Painted vignette slot: shows /milestones/<year>.jpg when the art exists.
    const art = document.getElementById("milestone-art") as HTMLImageElement;
    art.classList.add("hidden");
    art.onload = () => art.classList.remove("hidden");
    art.onerror = () => art.classList.add("hidden");
    art.src = `milestones/${m.year}.jpg`;
    milestoneEl.classList.toggle("alarm", m.tone === "alarm");
    wrapEl.classList.remove("hidden");
    wrapEl.classList.add("show");
    const obj = root.querySelector(".objectives");
    obj?.classList.add("glow");
    setTimeout(() => {
      wrapEl.classList.remove("show");
      obj?.classList.remove("glow");
      setTimeout(() => {
        wrapEl.classList.add("hidden");
        showing = false;
        pump();
      }, 450);
    }, 9000);
  }

  const refs: HudRefs = {
    onMinimapClick: null,
    onAction: null,
    setSelected(s, count = 1) {
      const txt =
        count > 1
          ? `${count} settlers selected`
          : s
            ? `${s.name} — ${getTaskLabel(s)}`
            : "No settler selected";
      if (selName.textContent !== txt) selName.textContent = txt; // repeat-call cheap
    },
    setPersona(key) {
      const spec = PERSONAS[key];
      const holder = document.getElementById("hud-portrait")!;
      holder.innerHTML = "";
      holder.appendChild(portraitEl(key));
      document.getElementById("hud-persona-name")!.textContent = spec.name;
      document.getElementById("hud-persona-role")!.textContent = spec.role;
    },
    showMilestone(m) {
      queue.push(m);
      pump();
    },
    update(v) {
      document.getElementById("hud-era")!.textContent = v.era;
      document.getElementById("hud-year")!.textContent = String(v.year);
      document.getElementById("hud-paused")!.textContent = v.paused ? "· PAUSED" : "";
      counterVals["timber"].textContent = String(v.timber);
      counterVals["water"].textContent = String(v.water);
      counterVals["food"].textContent = String(v.food);
      slotVals["timber"]!.textContent = String(v.timber);
      slotVals["wool"]!.textContent = String(v.wool);
      slotVals["food"]!.textContent = String(v.food);
      slotVals["water"]!.textContent = String(v.water);
      slotVals["pound"]!.textContent = String(v.capital);
      slotVals["pop"]!.textContent = String(v.population);
      // Era gates (game/eras.ts) own this panel when a gate is approaching/held;
      // otherwise fall back to the flavour objectives.
      if (objectivesOverride !== null) {
        if (objectives.innerHTML !== objectivesOverride) objectives.innerHTML = objectivesOverride;
      } else {
        const bales = Math.floor(v.wool / 25);
        objectives.innerHTML =
          `-Survey the river frontage (flags visited).<br>` +
          `-Stock the run (${Math.min(22 + Math.floor(v.population / 3), 40)}/40 sheep).<br>` +
          `-Load wool for the barge (${Math.min(bales, 10)}/10 bales).`;
      }
    },
    setObjectives(html) {
      objectivesOverride = html;
    },
    toastActive() {
      return showing || queue.length > 0;
    },
    drawMinimap(unitDots, camTile) {
      mctx.imageSmoothingEnabled = false;
      mctx.drawImage(base, 0, 0, mm.width, mm.height);
      const sx = mm.width / GRID_W;
      const sy = mm.height / GRID_H;
      for (const d of unitDots) {
        mctx.fillStyle = d.kind === "home" ? "#e04a35" : d.kind === "sheep" ? "#efe6d2" : "#ffffff";
        const r = d.kind === "home" ? 3 : 1.6;
        mctx.fillRect(d.x * sx - r, d.y * sy - r, r * 2, r * 2);
      }
      mctx.strokeStyle = "#f5e9c8";
      mctx.lineWidth = 1.2;
      mctx.strokeRect(camTile.x * sx - 9, camTile.y * sy - 7, 18, 14);
    },
    showTooltip(html, px, py) {
      tooltip.style.display = "block";
      tooltip.innerHTML = html;
      tooltip.style.left = `${Math.min(px, window.innerWidth - 340)}px`;
      tooltip.style.top = `${py}px`;
    },
    hideTooltip() {
      tooltip.style.display = "none";
    },
    flashAction(action) {
      const b = root.querySelector(`button[data-action="${action}"]`) as HTMLElement | null;
      if (!b) return;
      b.classList.add("flash");
      setTimeout(() => b.classList.remove("flash"), 250);
    },
  };

  mm.addEventListener("click", (e) => {
    const r = mm.getBoundingClientRect();
    refs.onMinimapClick?.((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
  });
  root.querySelectorAll("button[data-action]").forEach((b) =>
    b.addEventListener("click", () => refs.onAction?.((b as HTMLElement).dataset.action!))
  );

  return refs;
}
