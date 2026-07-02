// Settler's Almanac (codex): a C-key / button-opened parchment overlay listing
// one true sentence per entry. Rows unlock when the year clock reaches them;
// locked rows read "???". Art upgrade path mirrors portraitEl in hud.ts:
// each entry tries its /buildings/<key>.jpg plate and keeps a canvas-drawn
// placeholder on a miss. All chrome matches the ironwood/parchment panels.
import type { Simulation } from "../game/state";
import { CODEX_ENTRIES } from "../game/codexData";
import type { CodexEntry } from "../game/codexData";

const CODEX_CSS = `
  .codex-btn {
    position: absolute; top: 14px; left: 354px;
    font-family: Georgia, serif; font-size: 11px; letter-spacing: 1px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 8px 12px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 2px solid #191009; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000; box-shadow: 0 4px 12px #0008;
  }
  .codex-btn:hover { outline-color: #c9b26a; color: #ffd; }
  .codex-btn .key { color: #b8912f; margin-right: 5px; }
  .codex-panel {
    left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: 600px; max-width: calc(100vw - 40px); max-height: 76vh;
    display: flex; flex-direction: column; z-index: 30;
  }
  .codex-panel.hidden { display: none; }
  .codex-sub {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 14px; border-bottom: 1px solid #8a6a1c55;
    font-variant: small-caps; letter-spacing: 0.8px; color: #6b5410;
    font-size: 13px; font-weight: 700;
  }
  .codex-sub button {
    font-family: Georgia, serif; font-size: 10.5px; letter-spacing: 0.5px;
    font-variant: small-caps; color: #efe2bd; cursor: pointer; padding: 4px 10px;
    background: linear-gradient(#4a3820, #2a1d0f 60%, #1c130b);
    border: 1px solid #0d0805; outline: 1px solid #6b5636; border-radius: 5px;
    text-shadow: 0 1px 1px #000;
  }
  .codex-sub button:hover { outline-color: #c9b26a; color: #ffd; }
  .codex-list { overflow-y: auto; padding: 6px 14px 12px; }
  .codex-row {
    display: flex; gap: 11px; padding: 8px 4px; align-items: center;
    border-bottom: 1px dashed #8a6a1c44;
  }
  .codex-row:last-child { border-bottom: none; }
  .codex-plate {
    width: 64px; height: 64px; flex: none; border: 2px solid #191009;
    outline: 1px solid #77613a; border-radius: 3px; overflow: hidden;
    background: #241a10;
  }
  .codex-plate img, .codex-plate canvas {
    width: 64px !important; height: 64px !important;
    object-fit: cover; display: block;
  }
  .codex-title {
    font-weight: 700; color: #46351c; font-variant: small-caps;
    letter-spacing: 0.5px; font-size: 14.5px; margin-bottom: 2px;
  }
  .codex-fact { font-size: 12.5px; line-height: 1.38; color: #2b2013; }
  .codex-row.locked .codex-title { color: #8a7a55; }
  .codex-row.locked .codex-fact { color: #8a7a55; font-style: italic; }
`;

// Canvas placeholder plates (no emoji — drawn line art, like the HUD icons).
function drawPlate(unlocked: boolean): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 96;
  const x = c.getContext("2d")!;
  if (!unlocked) {
    const bg = x.createLinearGradient(0, 0, 0, 96);
    bg.addColorStop(0, "#32251a");
    bg.addColorStop(1, "#17100a");
    x.fillStyle = bg;
    x.fillRect(0, 0, 96, 96);
    x.fillStyle = "#6b5636";
    x.font = "bold 44px Georgia";
    x.textAlign = "center";
    x.textBaseline = "middle";
    x.fillText("?", 48, 52);
    return c;
  }
  // sepia plate: sun disc + a simple colonnaded civic facade
  const bg = x.createLinearGradient(0, 0, 0, 96);
  bg.addColorStop(0, "#ecdcae");
  bg.addColorStop(1, "#c9ad74");
  x.fillStyle = bg;
  x.fillRect(0, 0, 96, 96);
  x.fillStyle = "#d9b95c";
  x.beginPath();
  x.arc(70, 24, 11, 0, 7);
  x.fill();
  x.fillStyle = "#5d4226";
  x.beginPath(); // pediment
  x.moveTo(16, 46);
  x.lineTo(48, 30);
  x.lineTo(80, 46);
  x.closePath();
  x.fill();
  x.fillRect(18, 48, 60, 5); // architrave
  for (const px of [22, 38, 54, 70]) x.fillRect(px, 55, 5, 24); // columns
  x.fillRect(14, 80, 68, 6); // steps
  x.strokeStyle = "#8a6a1c";
  x.lineWidth = 3;
  x.strokeRect(4, 4, 88, 88);
  return c;
}

// Plate art cache, portraitEl-style: undefined = untried, null = missed.
const plateArt: Record<string, HTMLImageElement | null | undefined> = {};
function plateEl(entry: CodexEntry, unlocked: boolean): HTMLElement {
  const holder = document.createElement("div");
  holder.className = "codex-plate";
  if (!unlocked) {
    holder.appendChild(drawPlate(false));
    return holder;
  }
  const cached = plateArt[entry.key];
  if (cached) {
    holder.appendChild(cached.cloneNode() as HTMLImageElement);
    return holder;
  }
  holder.appendChild(drawPlate(true));
  if (cached === undefined) {
    if (!entry.img) {
      plateArt[entry.key] = null;
    } else {
      const img = new Image();
      img.onload = () => {
        plateArt[entry.key] = img;
        holder.innerHTML = "";
        holder.appendChild(img.cloneNode() as HTMLImageElement);
      };
      img.onerror = () => {
        plateArt[entry.key] = null; // remember the miss; keep the canvas
      };
      img.src = entry.img;
    }
  }
  return holder;
}

export interface CodexRefs {
  toggle(): void;
  /** Cheap per-frame call: re-renders only while open and the year moved. */
  update(): void;
}

export function installCodex(opts: { sim: Simulation }): CodexRefs {
  const { sim } = opts;
  const root = document.getElementById("ui")!;

  if (!document.getElementById("codex-style")) {
    const style = document.createElement("style");
    style.id = "codex-style";
    style.textContent = CODEX_CSS;
    document.head.appendChild(style);
  }

  const btn = document.createElement("button");
  btn.className = "codex-btn";
  btn.innerHTML = `<span class="key">[C]</span>Almanac`;
  root.appendChild(btn);

  const panel = document.createElement("div");
  panel.className = "panel parchment codex-panel hidden";
  panel.innerHTML = `
    <h1>The Settler's Almanac</h1>
    <div class="codex-sub">
      <span id="codex-count"></span>
      <button id="codex-close">Close [C]</button>
    </div>
    <div class="codex-list" id="codex-list"></div>
  `;
  root.appendChild(panel);

  const countEl = panel.querySelector<HTMLElement>("#codex-count")!;
  const listEl = panel.querySelector<HTMLElement>("#codex-list")!;

  let open = false;
  let renderedYear = -1;

  function render(): void {
    renderedYear = sim.year;
    listEl.innerHTML = "";
    let discovered = 0;
    for (const e of CODEX_ENTRIES) {
      const unlocked = sim.year >= e.unlockYear;
      if (unlocked) discovered++;
      const row = document.createElement("div");
      row.className = unlocked ? "codex-row" : "codex-row locked";
      row.appendChild(plateEl(e, unlocked));
      const txt = document.createElement("div");
      const title = document.createElement("div");
      title.className = "codex-title";
      title.textContent = unlocked
        ? e.year !== undefined
          ? `${e.title} — ${e.circa ? "c. " : ""}${e.year}`
          : e.title
        : "???";
      const fact = document.createElement("div");
      fact.className = "codex-fact";
      fact.textContent = unlocked ? e.fact : "Not yet discovered.";
      txt.append(title, fact);
      row.appendChild(txt);
      listEl.appendChild(row);
    }
    countEl.textContent = `${discovered} of ${CODEX_ENTRIES.length} discovered`;
  }

  const refs: CodexRefs = {
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
  panel.querySelector("#codex-close")!.addEventListener("click", refs.toggle);
  window.addEventListener("keydown", (e) => {
    if (e.code === "KeyC") refs.toggle();
    else if (e.code === "Escape" && open) refs.toggle();
  });

  return refs;
}
