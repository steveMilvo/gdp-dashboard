// M4 — date-gated build menu with staged construction.
//   [5] BUILD opens a parchment palette of Mildura's real public works, each
//   gated to its true year (docs/mildura-history.md). Picking one puts a ghost
//   under the pointer (green = buildable, red = not); left-click places it,
//   Esc/right-click cancels. Placed works rise in three stages — survey pegs,
//   timber frame, finished building — over ~9 seconds. Placements ride the
//   save snapshot (sim.placed) and rebuild instantly-complete on load.

import * as THREE from "three";
import type { GameMap } from "../map/mapData";
import { toonGradient } from "../render/world";
import type { Terrain } from "../render/world";
import type { Simulation, PlacedBuildingSave } from "./state";
import type { HudRefs } from "../ui/hud";
import {
  BUILD_CATALOG,
  CATALOG_BY_KEY,
  CARNEGIE_TOWER_OFFSET,
  buildClockTower,
} from "./buildCatalog";
import type { CatalogEntry } from "./buildCatalog";

export interface BuildMenuOpts {
  scene: THREE.Scene;
  terrain: Terrain;
  map: GameMap;
  sim: Simulation;
  hud: HudRefs;
  camera: THREE.Camera;
  dom: HTMLElement; // renderer.domElement — pointer events are picked off it
}

// Construction staging (seconds from placement).
const STAGE_PEGS_END = 3.0;
const STAGE_FRAME_END = 6.2;
const STAGE_DONE = 9.0;

const CLOCK_TOWER_YEAR = 1921; // Memorial Clock Tower dedication

interface PlacedInstance {
  save: PlacedBuildingSave; // shared object also held in sim.placed
  entry: CatalogEntry;
  root: THREE.Group;
  pegs: THREE.Group;
  frame: THREE.Group;
  final: THREE.Group;
  elapsed: number; // seconds since placement (Infinity = restored complete)
  clockTower: boolean; // Carnegie only: 1921 upgrade applied
}

// --- palette chrome (self-contained CSS so index.html stays untouched) ------------
const CSS = `
  .build-palette { right: 14px; bottom: 262px; width: 356px; z-index: 15; }
  .build-palette.hidden { display: none; }
  .bp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; padding: 9px 12px 12px; }
  .bp-entry { display: flex; gap: 8px; align-items: center; padding: 5px 7px;
    border: 1px solid #8a6a1c66; border-radius: 4px; cursor: pointer;
    background: linear-gradient(165deg, #ecdcaeE6, #d3bd85E6); }
  .bp-entry:hover { border-color: #6b5410; background: linear-gradient(165deg, #f4e6bc, #ddc78f); }
  .bp-entry canvas { flex: none; }
  .bp-meta { min-width: 0; }
  .bp-name { font-size: 12px; font-weight: 700; color: #46351c;
    font-variant: small-caps; letter-spacing: 0.4px; line-height: 1.15; }
  .bp-line { font-size: 10.5px; color: #6b5410; }
  .bp-entry.locked { cursor: not-allowed; filter: grayscale(0.9); opacity: 0.55; }
  .bp-entry.locked:hover { border-color: #8a6a1c66; }
  .bp-entry.locked .bp-line.bp-unlock { color: #8a2a1c; font-style: italic; }
  .bp-entry.poor .bp-line.bp-cost { color: #8a2a1c; }
  .bp-entry.deny { animation: bp-deny 0.45s ease; }
  @keyframes bp-deny {
    0%, 100% { box-shadow: none; }
    40% { box-shadow: 0 0 0 3px #c0281c; background: #e8b09a; }
  }
  .bp-hint { font-size: 11px; color: #6b5410; font-style: italic; padding: 0 14px 9px; margin: 0; }
  .actions button[data-action="build"] { grid-column: 1 / -1; }
`;

export function installBuildMenu(opts: BuildMenuOpts): { update(dt: number, t: number): void } {
  const { scene, terrain, map, sim, hud, camera, dom } = opts;

  // ---- CSS + palette DOM ----------------------------------------------------------
  if (!document.getElementById("build-menu-css")) {
    const style = document.createElement("style");
    style.id = "build-menu-css";
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  const ui = document.getElementById("ui")!;
  const palette = document.createElement("div");
  palette.className = "panel parchment build-palette hidden";
  palette.innerHTML = `<h2>Public Works</h2><div class="bp-grid"></div>
    <p class="bp-hint">Left-click to place &middot; Right-click or Esc to cancel</p>`;
  ui.appendChild(palette);

  const grid = palette.querySelector(".bp-grid")!;
  const entryEls = new Map<string, HTMLElement>();
  const unlockEls = new Map<string, HTMLElement>();
  for (const e of BUILD_CATALOG) {
    const d = document.createElement("div");
    d.className = "bp-entry locked";
    d.title = e.blurb;
    d.appendChild(e.icon(38));
    const meta = document.createElement("div");
    meta.className = "bp-meta";
    const costTxt = e.cost.capital > 0 ? `${e.cost.timber} timber &middot; £${e.cost.capital}` : `${e.cost.timber} timber`;
    meta.innerHTML =
      `<div class="bp-name">${e.name}</div>` +
      `<div class="bp-line">${e.year}</div>` +
      `<div class="bp-line bp-cost">${costTxt}</div>` +
      `<div class="bp-line bp-unlock">unlocks ${e.year}</div>`;
    d.appendChild(meta);
    d.addEventListener("click", () => pick(e));
    grid.appendChild(d);
    entryEls.set(e.key, d);
    unlockEls.set(e.key, meta.querySelector(".bp-unlock") as HTMLElement);
  }

  // ---- [5] BUILD button in the existing actions grid (markup matches hud.ts) ------
  const actionsEl = ui.querySelector(".actions");
  const buildBtn = document.createElement("button");
  buildBtn.dataset.action = "build";
  buildBtn.innerHTML = `<span class="key">[5]</span>BUILD`;
  buildBtn.addEventListener("click", () => togglePalette());
  actionsEl?.appendChild(buildBtn);

  let paletteOpen = false;
  function togglePalette(force?: boolean) {
    paletteOpen = force ?? !paletteOpen;
    palette.classList.toggle("hidden", !paletteOpen);
    if (paletteOpen) {
      hud.flashAction("build");
      refreshLocks();
    } else if (pending) {
      cancelPlacement();
    }
  }

  let lastLockYear = -1;
  function refreshLocks() {
    if (sim.year === lastLockYear) return;
    lastLockYear = sim.year;
    for (const e of BUILD_CATALOG) {
      const el = entryEls.get(e.key)!;
      const locked = e.year > sim.year;
      el.classList.toggle("locked", locked);
      unlockEls.get(e.key)!.style.display = locked ? "" : "none";
    }
  }
  function refreshAfford() {
    for (const e of BUILD_CATALOG) {
      const poor = sim.resources.timber < e.cost.timber || sim.resources.capital < e.cost.capital;
      entryEls.get(e.key)!.classList.toggle("poor", poor);
    }
  }

  function affordable(e: CatalogEntry): boolean {
    return sim.resources.timber >= e.cost.timber && sim.resources.capital >= e.cost.capital;
  }
  function denyFlash(e: CatalogEntry) {
    const el = entryEls.get(e.key)!;
    el.classList.remove("deny");
    void el.offsetWidth; // restart the animation
    el.classList.add("deny");
  }

  // ---- ghost placement -------------------------------------------------------------
  const ghostMat = new THREE.MeshBasicMaterial({
    transparent: true,
    opacity: 0.45,
    depthWrite: false,
    color: 0x3fae4a,
  });
  const padMat = new THREE.MeshBasicMaterial({
    transparent: true,
    opacity: 0.28,
    depthWrite: false,
    side: THREE.DoubleSide,
    color: 0x3fae4a,
  });

  let pending: CatalogEntry | null = null;
  let ghost: THREE.Group | null = null;
  let ghostPad: THREE.Mesh | null = null;
  let ghostValid = false;
  let ghostOnGround = false;

  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();

  function pick(e: CatalogEntry) {
    if (e.year > sim.year) return; // history hasn't caught up yet
    if (!affordable(e)) {
      denyFlash(e);
      hud.flashAction("build");
      return;
    }
    cancelPlacement();
    pending = e;
    ghost = e.build();
    ghost.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.material = ghostMat;
        o.castShadow = false;
        o.receiveShadow = false;
      }
    });
    ghostPad = new THREE.Mesh(new THREE.PlaneGeometry(e.footprint.w, e.footprint.d), padMat);
    ghostPad.rotation.x = -Math.PI / 2;
    ghostPad.position.y = 0.06;
    ghost.add(ghostPad);
    ghost.visible = false;
    ghostOnGround = false;
    scene.add(ghost);
  }

  function cancelPlacement() {
    if (ghost) {
      scene.remove(ghost);
      ghost = null;
      ghostPad = null;
    }
    pending = null;
  }

  function snapToTile(x: number, z: number): { x: number; z: number; tx: number; ty: number } {
    const g = terrain.worldToTile(x, z);
    const tx = Math.round(g.x);
    const ty = Math.round(g.y);
    const w = terrain.tileToWorld(tx, ty);
    return { x: w.x, z: w.z, tx, ty };
  }

  function siteValid(e: CatalogEntry, x: number, z: number, tx: number, ty: number): boolean {
    const t = map.at(tx, ty);
    if (t.water || t.kind === "river" || t.kind === "billabong") return false;
    const hw = e.footprint.w / 2;
    const hd = e.footprint.d / 2;
    let lo = Infinity;
    let hi = -Infinity;
    for (const [cx, cz] of [[-hw, -hd], [hw, -hd], [-hw, hd], [hw, hd], [0, 0]]) {
      const h = terrain.heightAt(x + cx, z + cz);
      if (h < terrain.WATER_LEVEL + 0.15) return false; // keep every corner dry
      if (h < lo) lo = h;
      if (h > hi) hi = h;
    }
    if (hi - lo > 1.6) return false; // gentle local slope only
    for (const p of placed) {
      const o = p.entry.footprint;
      if (
        Math.abs(p.root.position.x - x) < hw + o.w / 2 + 0.8 &&
        Math.abs(p.root.position.z - z) < hd + o.d / 2 + 0.8
      ) {
        return false; // overlaps an earlier placement
      }
    }
    return true;
  }

  function moveGhost(clientX: number, clientY: number) {
    if (!pending || !ghost) return;
    ndc.x = (clientX / window.innerWidth) * 2 - 1;
    ndc.y = -(clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObject(terrain.mesh, false)[0];
    if (!hit) {
      ghost.visible = false;
      ghostOnGround = false;
      return;
    }
    const s = snapToTile(hit.point.x, hit.point.z);
    ghost.position.set(s.x, terrain.heightAt(s.x, s.z), s.z);
    ghost.visible = true;
    ghostOnGround = true;
    ghostValid = siteValid(pending, s.x, s.z, s.tx, s.ty);
    const col = ghostValid ? 0x3fae4a : 0xc0392b;
    ghostMat.color.setHex(col);
    padMat.color.setHex(col);
  }

  function tryPlace() {
    if (!pending || !ghost || !ghostOnGround || !ghostValid) return;
    const e = pending;
    if (!affordable(e)) {
      denyFlash(e);
      return;
    }
    sim.resources.timber -= e.cost.timber;
    sim.resources.capital -= e.cost.capital;
    const g = terrain.worldToTile(ghost.position.x, ghost.position.z);
    const save: PlacedBuildingSave = {
      key: e.key,
      tx: Math.round(g.x),
      ty: Math.round(g.y),
      builtYear: sim.year,
    };
    sim.placed.push(save);
    spawn(save, e, 0);
    cancelPlacement();
    refreshAfford();
  }

  // ---- staged construction -----------------------------------------------------------
  const placed: PlacedInstance[] = [];

  function toonMat(color: number): THREE.MeshToonMaterial {
    return new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color });
  }

  function stick(g: THREE.Group, w: number, h: number, d: number, x: number, y: number, z: number, color: number) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), toonMat(color));
    m.position.set(x, y, z);
    m.castShadow = true;
    g.add(m);
  }

  // Stage 1: surveyor's pegs — corner stakes + string line around the footprint.
  function buildPegs(e: CatalogEntry): THREE.Group {
    const g = new THREE.Group();
    const hw = e.footprint.w / 2;
    const hd = e.footprint.d / 2;
    const peg = 0xefe3c2;
    for (const [x, z] of [[-hw, -hd], [hw, -hd], [-hw, hd], [hw, hd]]) {
      stick(g, 0.14, 0.9, 0.14, x, 0.45, z, peg);
    }
    const line = 0xd4af37;
    stick(g, e.footprint.w, 0.05, 0.05, 0, 0.7, -hd, line);
    stick(g, e.footprint.w, 0.05, 0.05, 0, 0.7, hd, line);
    stick(g, 0.05, 0.05, e.footprint.d, -hw, 0.7, 0, line);
    stick(g, 0.05, 0.05, e.footprint.d, hw, 0.7, 0, line);
    return g;
  }

  // Stage 2: timber frame — corner studs, plates and a ridge pole.
  function buildFrame(e: CatalogEntry): THREE.Group {
    const g = new THREE.Group();
    const hw = e.footprint.w / 2 - 0.4;
    const hd = e.footprint.d / 2 - 0.4;
    const h = e.height * 0.75;
    const wood = 0xc9a86f;
    for (const [x, z] of [[-hw, -hd], [hw, -hd], [-hw, hd], [hw, hd]]) {
      stick(g, 0.16, h, 0.16, x, h / 2, z, wood);
    }
    stick(g, hw * 2, 0.14, 0.14, 0, h, -hd, wood);
    stick(g, hw * 2, 0.14, 0.14, 0, h, hd, wood);
    stick(g, 0.14, 0.14, hd * 2, -hw, h, 0, wood);
    stick(g, 0.14, 0.14, hd * 2, hw, h, 0, wood);
    stick(g, 0.14, 0.14, hd * 2, 0, h + e.height * 0.18, 0, wood); // ridge pole
    stick(g, 0.16, h * 0.55, 0.16, 0, h * 0.28, hd, wood); // door stud
    return g;
  }

  function spawn(save: PlacedBuildingSave, e: CatalogEntry, elapsed: number): PlacedInstance {
    const w = terrain.tileToWorld(save.tx, save.ty);
    const root = new THREE.Group();
    root.position.set(w.x, terrain.heightAt(w.x, w.z), w.z);
    const pegs = buildPegs(e);
    const frame = buildFrame(e);
    const final = e.build();
    root.add(pegs, frame, final);
    scene.add(root);
    const inst: PlacedInstance = { save, entry: e, root, pegs, frame, final, elapsed, clockTower: false };
    applyStage(inst);
    maybeClockTower(inst);
    placed.push(inst);
    return inst;
  }

  function applyStage(p: PlacedInstance) {
    const t = p.elapsed;
    p.pegs.visible = t < STAGE_FRAME_END; // pegs stay up while the frame rises
    p.frame.visible = t >= STAGE_PEGS_END && t < STAGE_DONE;
    p.final.visible = t >= STAGE_FRAME_END;
    if (p.final.visible && t < STAGE_DONE) {
      // the finished building rises out of the frame
      const k = (t - STAGE_FRAME_END) / (STAGE_DONE - STAGE_FRAME_END);
      p.final.scale.set(1, 0.08 + 0.92 * k, 1);
    } else {
      p.final.scale.set(1, 1, 1);
    }
  }

  function maybeClockTower(p: PlacedInstance) {
    if (p.clockTower || p.entry.key !== "carnegie") return;
    if (sim.year < CLOCK_TOWER_YEAR || p.elapsed < STAGE_DONE) return;
    p.clockTower = true;
    // take down the 1908 tower, raise the Memorial Clock Tower on the same spot
    const olds: THREE.Object3D[] = [];
    p.final.traverse((o) => {
      if (o.name === "carnegie-tower-1908") olds.push(o);
    });
    for (const o of olds) p.final.remove(o);
    const tower = buildClockTower();
    tower.position.copy(CARNEGIE_TOWER_OFFSET);
    p.final.add(tower);
  }

  // ---- restore from save (instantly complete) ---------------------------------------
  for (const s of sim.placed) {
    const e = CATALOG_BY_KEY[s.key];
    if (!e) continue; // tolerate unknown keys from newer/older saves
    spawn(s, e, Infinity);
  }

  // ---- input -----------------------------------------------------------------------
  // Capture-phase listeners on window run before main.ts's selection/order handlers
  // and OrbitControls; while placing we consume the pointer so nothing else fires.
  let down: { x: number; y: number; button: number } | null = null;

  window.addEventListener(
    "pointerdown",
    (ev) => {
      if (!pending) return;
      if (ev.target !== dom) return; // palette / HUD clicks pass through
      down = { x: ev.clientX, y: ev.clientY, button: ev.button };
      ev.stopPropagation();
    },
    true
  );
  window.addEventListener(
    "pointerup",
    (ev) => {
      if (!pending) return;
      if (ev.target !== dom && !down) return;
      ev.stopPropagation();
      const wasDrag = down && Math.hypot(ev.clientX - down.x, ev.clientY - down.y) > 5;
      const button = down?.button ?? ev.button;
      down = null;
      if (wasDrag) return;
      if (button === 0) tryPlace();
      else if (button === 2) cancelPlacement();
    },
    true
  );
  window.addEventListener(
    "pointermove",
    (ev) => {
      if (!pending) return;
      moveGhost(ev.clientX, ev.clientY);
      if (ev.target === dom) ev.stopPropagation(); // mute landmark tooltips while placing
    },
    true
  );
  window.addEventListener(
    "contextmenu",
    (ev) => {
      if (!pending) return;
      ev.preventDefault();
      ev.stopPropagation();
      cancelPlacement();
    },
    true
  );
  window.addEventListener("keydown", (ev) => {
    if (ev.code === "Digit5") togglePalette();
    else if (ev.code === "Escape") {
      if (pending) cancelPlacement();
      else if (paletteOpen) togglePalette(false);
    }
  });

  refreshLocks();
  refreshAfford();

  // ---- per-frame update ---------------------------------------------------------------
  let affordTick = 0;
  return {
    update(dt: number) {
      for (const p of placed) {
        if (p.elapsed < STAGE_DONE) {
          p.elapsed += dt;
          applyStage(p);
        }
        maybeClockTower(p);
      }
      if (paletteOpen) {
        refreshLocks();
        affordTick += dt;
        if (affordTick > 0.5) {
          affordTick = 0;
          refreshAfford();
        }
      }
    },
  };
}
