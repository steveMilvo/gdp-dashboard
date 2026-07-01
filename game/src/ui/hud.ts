// Mock-up UI: four corner panels — parchment mission panel (top-left), ornate
// minimap + objectives (top-right), status panel with portrait/bars/counters
// (bottom-left), inventory slot-grid with hotkey actions (bottom-right).
// All icons are canvas-drawn (no emoji → renders identically everywhere).
import { GRID_W, GRID_H } from "../config";
import type { GameMap, Tile } from "../map/mapData";
import type { Settler } from "../render/units";

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

function drawPortrait(): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d")!;
  // parchment sky
  const bg = x.createLinearGradient(0, 0, 0, 64);
  bg.addColorStop(0, "#c7ddec");
  bg.addColorStop(1, "#e0d3a8");
  x.fillStyle = bg;
  x.fillRect(0, 0, 64, 64);
  // shoulders
  x.fillStyle = "#51617a";
  x.beginPath();
  x.moveTo(8, 64);
  x.bezierCurveTo(12, 44, 52, 44, 56, 64);
  x.fill();
  // head
  x.fillStyle = "#d9a679";
  x.beginPath();
  x.arc(32, 30, 12, 0, 7);
  x.fill();
  // hat
  x.fillStyle = "#8a713f";
  x.beginPath();
  x.ellipse(32, 21, 17, 5, 0, 0, 7);
  x.fill();
  x.fillRect(23, 10, 18, 11);
  x.strokeStyle = "#5d4a26";
  x.strokeRect(23, 10, 18, 11);
  // face
  x.fillStyle = "#4a3524";
  x.fillRect(27, 28, 2.6, 2.6);
  x.fillRect(35, 28, 2.6, 2.6);
  x.strokeStyle = "#a56a45";
  x.beginPath();
  x.arc(32, 35, 4, 0.35, Math.PI - 0.35);
  x.stroke();
  return c;
}

export interface HudRefs {
  setSelected(s: Settler | null): void;
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
        <p><b>CONTROLS:</b> Click to Select a Settler,<br>
        Right-Click to Move &middot; Drag to Look,<br>
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
      <h2 class="bar-title">Settler Status</h2>
      <div class="status-row">
        <div class="portrait" id="hud-portrait"></div>
        <div class="bars">
          <div class="bar-line"><span class="heart"></span><div class="bar"><div id="bar-health" class="fill green" style="width:88%"></div></div></div>
          <div class="bar-line"><span class="bolt"></span><div class="bar"><div id="bar-energy" class="fill yellow" style="width:64%"></div></div></div>
          <div id="hud-selname" class="sel-name">No settler selected</div>
        </div>
      </div>
      <div class="counters" id="hud-counters"></div>
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

  document.getElementById("hud-portrait")!.appendChild(drawPortrait());

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
  const selName = document.getElementById("hud-selname")!;

  const refs: HudRefs = {
    onMinimapClick: null,
    onAction: null,
    setSelected(s) {
      selName.textContent = s ? `${s.name} — Settler` : "No settler selected";
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
      const bales = Math.floor(v.wool / 25);
      objectives.innerHTML =
        `-Survey the river frontage (flags visited).<br>` +
        `-Stock the run (${Math.min(22 + Math.floor(v.population / 3), 40)}/40 sheep).<br>` +
        `-Load wool for the barge (${Math.min(bales, 10)}/10 bales).`;
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
