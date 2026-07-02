// M2 — classic RTS multi-unit control. Owns the multi-selection set, the
// drag box-select overlay, per-selected-settler pulsing rings, and group
// order fan-out (right-click + the [1]-[4] action buttons all route here).
//
// Camera conflict resolution, the classic way: LEFT-drag on the canvas is
// box-select, camera orbit moves to MIDDLE-drag (RIGHT-drag pan unchanged).
//
// Back-compat: units.selected always points at the FIRST selected settler
// (assigned directly, without units.select(), so the old single-unit ring
// pair in UnitManager stays hidden — this module renders a ring per unit).
import * as THREE from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GRID_W, GRID_H } from "../config";
import type { Terrain } from "../render/world";
import type { GameMap, Tile } from "../map/mapData";
import { makeRing } from "../render/units";
import type { Settler, UnitManager } from "../render/units";
import type { Labour } from "./labour";
import type { HudRefs } from "../ui/hud";

const DRAG_THRESHOLD = 6; // px before a left-press becomes a box-select
const CSS = `
  #select-box {
    position: fixed; display: none; pointer-events: none; z-index: 40;
    border: 1.5px solid #e3c34e; background: rgba(227, 195, 78, 0.16);
    box-shadow: inset 0 0 10px rgba(227, 195, 78, 0.28);
  }
`;

export interface SelectionOpts {
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  dom: HTMLElement; // renderer.domElement
  scene: THREE.Scene;
  terrain: Terrain;
  map: GameMap;
  units: UnitManager;
  labour: Labour;
  hud: HudRefs;
  homePos: THREE.Vector3; // settlement.homePos — muster rallies near here
}

export interface SelectionManager {
  /** Number of settlers currently selected. */
  count(): number;
  /** Selected settlers, first = primary (mirrors units.selected). */
  list(): Settler[];
  /** Single-select (or deselect with null) — plain left-click path. */
  selectOnly(s: Settler | null): void;
  /** Select all six settlers (double-click a settler). */
  selectAll(): void;
  /** Right-click fan-out: labour.orderAt for every selected settler. */
  orderAll(x: number, z: number, now: number): void;
  /** [1]-[4] hotbar actions applied across the whole selection. */
  doAction(action: string, now: number): void;
  update(dt: number, t: number): void;
}

export function installSelection(opts: SelectionOpts): SelectionManager {
  const { camera, controls, dom, scene, terrain, map, units, labour, hud, homePos } = opts;

  // --- camera remap: free LEFT for box-select, orbit on MIDDLE ------------------
  controls.mouseButtons = { LEFT: null, MIDDLE: THREE.MOUSE.ROTATE, RIGHT: THREE.MOUSE.PAN };

  // Hide UnitManager's built-in single-selection ring pair for good; from here
  // on units.selected is kept in sync by direct assignment only.
  units.select(null);

  // --- selection state -----------------------------------------------------------
  let sel: Settler[] = [];

  // Ring pool: one pulsing green pair per settler, reusing units.ts's makeRing.
  const rings = units.settlers.map(() => {
    const inner = makeRing(0.85);
    const outer = makeRing(1.2);
    inner.visible = outer.visible = false;
    scene.add(inner, outer);
    return { inner, outer };
  });

  function apply(next: Settler[]) {
    sel = next;
    units.selected = sel[0] ?? null; // back-compat: hud/labour read this
    hud.setSelected(sel[0] ?? null, sel.length);
    for (let i = 0; i < rings.length; i++) {
      rings[i].inner.visible = rings[i].outer.visible = i < sel.length;
    }
  }

  // Deterministic fan-out ring so group orders do not stack on one point.
  function offsetFor(i: number, n: number): { x: number; z: number } {
    if (n <= 1) return { x: 0, z: 0 };
    const r = 1.5 + 0.22 * n;
    const a = (i / n) * Math.PI * 2;
    return { x: Math.cos(a) * r, z: Math.sin(a) * r };
  }

  function nearestTileOfKind(x: number, z: number, kinds: Tile["kind"][]): { x: number; z: number } | null {
    let best: { x: number; z: number } | null = null;
    let bestD = Infinity;
    for (let ty = 0; ty < GRID_H; ty++) {
      for (let tx = 0; tx < GRID_W; tx++) {
        const t = map.at(tx, ty);
        if (!kinds.includes(t.kind)) continue;
        const w = terrain.tileToWorld(tx, ty);
        const d = (w.x - x) ** 2 + (w.z - z) ** 2;
        if (d < bestD) {
          bestD = d;
          best = w;
        }
      }
    }
    return best;
  }

  function orderAll(x: number, z: number, now: number) {
    sel.forEach((s, i) => {
      const o = offsetFor(i, sel.length);
      labour.orderAt(s, x + o.x, z + o.z, now);
    });
  }

  function doAction(action: string, now: number) {
    hud.flashAction(action);
    if (sel.length === 0) apply([units.settlers[0]]);
    if (action === "survey") {
      const p = sel[0].group.position;
      controls.target.set(p.x, p.y, p.z);
      return;
    }
    sel.forEach((s, i) => {
      const o = offsetFor(i, sel.length);
      const p = s.group.position;
      if (action === "chop") {
        const t = nearestTileOfKind(p.x, p.z, ["redgum"]);
        if (t) labour.assign(s, "chop", t.x + o.x, t.z + o.z, now);
      } else if (action === "gather") {
        const t = nearestTileOfKind(p.x, p.z, ["floodplain"]);
        if (t) labour.assign(s, "gather", t.x + o.x, t.z + o.z, now);
      } else if (action === "muster") {
        labour.clearTask(s);
        units.order(s, homePos.x + 8 + o.x, homePos.z + 6 + o.z, now);
      }
    });
  }

  // --- box-select overlay ----------------------------------------------------------
  if (!document.getElementById("selection-css")) {
    const style = document.createElement("style");
    style.id = "selection-css";
    style.textContent = CSS;
    document.head.appendChild(style);
  }
  const boxEl = document.createElement("div");
  boxEl.id = "select-box";
  document.body.appendChild(boxEl);

  let boxStart: { x: number; y: number } | null = null;
  let boxActive = false;

  function boxRect(ex: number, ey: number) {
    return {
      x0: Math.min(boxStart!.x, ex),
      y0: Math.min(boxStart!.y, ey),
      x1: Math.max(boxStart!.x, ex),
      y1: Math.max(boxStart!.y, ey),
    };
  }

  function drawBox(ex: number, ey: number) {
    const r = boxRect(ex, ey);
    boxEl.style.display = "block";
    boxEl.style.left = `${r.x0}px`;
    boxEl.style.top = `${r.y0}px`;
    boxEl.style.width = `${r.x1 - r.x0}px`;
    boxEl.style.height = `${r.y1 - r.y0}px`;
  }

  const proj = new THREE.Vector3();
  function finishBox(ex: number, ey: number) {
    const r = boxRect(ex, ey);
    const picked: Settler[] = [];
    for (const s of units.settlers) {
      proj.copy(s.group.position);
      proj.y += 1; // torso height reads better than the feet
      proj.project(camera);
      if (proj.z < -1 || proj.z > 1) continue; // behind the camera / clipped
      const sx = ((proj.x + 1) / 2) * window.innerWidth;
      const sy = ((1 - proj.y) / 2) * window.innerHeight;
      if (sx >= r.x0 && sx <= r.x1 && sy >= r.y0 && sy <= r.y1) picked.push(s);
    }
    apply(picked); // empty box = classic deselect
  }

  // buildMenu's capture-phase stopPropagation while placing keeps these quiet.
  dom.addEventListener("pointerdown", (e) => {
    if (e.button === 0) boxStart = { x: e.clientX, y: e.clientY };
  });
  window.addEventListener("pointermove", (e) => {
    if (!boxStart) return;
    if (!boxActive && Math.hypot(e.clientX - boxStart.x, e.clientY - boxStart.y) > DRAG_THRESHOLD) {
      boxActive = true;
    }
    if (boxActive) drawBox(e.clientX, e.clientY);
  });
  window.addEventListener("pointerup", (e) => {
    if (boxActive) finishBox(e.clientX, e.clientY);
    boxStart = null;
    boxActive = false;
    boxEl.style.display = "none";
  });

  // Double-click a settler: select the whole party.
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  dom.addEventListener("dblclick", (e) => {
    ndc.x = (e.clientX / window.innerWidth) * 2 - 1;
    ndc.y = -(e.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(ndc, camera);
    if (units.pick(raycaster)) apply([...units.settlers]);
  });

  // Esc deselects — but only as a fallback when neither the build palette nor
  // the codex overlay is open (both bind Escape themselves; checked via the DOM
  // so this stays decoupled from their internals).
  window.addEventListener("keydown", (e) => {
    if (e.code !== "Escape" || sel.length === 0) return;
    const overlayOpen = !!document.querySelector(
      ".build-palette:not(.hidden), .codex-panel:not(.hidden)"
    );
    if (!overlayOpen) apply([]);
  });

  return {
    count: () => sel.length,
    list: () => sel.slice(),
    selectOnly(s) {
      apply(s ? [s] : []);
    },
    selectAll() {
      apply([...units.settlers]);
    },
    orderAll,
    doAction,
    update(_dt: number, t: number) {
      const pulse = 1 + Math.sin(t * 5) * 0.07;
      for (let i = 0; i < sel.length; i++) {
        const p = sel[i].group.position;
        rings[i].inner.position.set(p.x, p.y + 0.06, p.z);
        rings[i].outer.position.set(p.x, p.y + 0.05, p.z);
        rings[i].inner.scale.setScalar(pulse);
        rings[i].outer.scale.setScalar(2 - pulse);
      }
      // labour.update refreshes the status line with the primary settler's task
      // label; when a group is selected, re-assert the "N settlers selected"
      // composite (hud.setSelected is a no-op when the text is unchanged).
      if (sel.length > 1) hud.setSelected(sel[0], sel.length);
    },
  };
}
