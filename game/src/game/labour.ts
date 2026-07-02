// M2 — the working gather economy. Settlers ordered onto red gum or floodplain
// tiles fell timber / gather food in a walk → work → carry-home loop, and from
// the squatter run (1847) the passive economy steps back so this player-directed
// labour is what keeps the colony fed and built (docs/mildura-history.md §1847).
//
// Task state lives in a side-table keyed by Settler — units.ts is untouched.
import * as THREE from "three";
import type { Terrain } from "../render/world";
import { toonGradient, makeGlowTexture } from "../render/world";
import type { GameMap } from "../map/mapData";
import type { Settler, UnitManager } from "../render/units";
import type { Simulation } from "./state";
import type { HudRefs } from "../ui/hud";
import { mulberry32 } from "../util/rng";

export type TaskKind = "chop" | "gather";
type TaskPhase = "moving" | "working" | "carrying";

interface Task {
  kind: TaskKind;
  phase: TaskPhase;
  workX: number; // world-space work spot (tree / tucker patch)
  workZ: number;
  workT: number; // seconds spent in the current working phase
  strikesDone: number; // chip bursts already spawned this working phase
  heading: number; // face-the-work yaw, fixed at arrival
}

// Side-table: task state per settler, without touching units.ts internals.
const tasks = new WeakMap<Settler, Task>();
// Carry props (log / sack) created lazily per settler, parented to the group.
const props = new WeakMap<Settler, { log: THREE.Mesh; sack: THREE.Mesh }>();

const SWING_PERIOD = 4; // seconds per chop/gather cycle
const SWINGS_PER_TRIP = 3; // cycles before the settler carries the haul home
const TIMBER_PER_TRIP = 8;
const FOOD_PER_TRIP = 6;

/** Selected-settler status line, e.g. "chopping red gum" → "Tom — chopping red gum". */
export function getTaskLabel(s: Settler): string {
  const task = tasks.get(s);
  if (!task) return s.target ? "walking" : "Settler";
  if (task.kind === "chop") {
    if (task.phase === "moving") return "heading to the red gums";
    if (task.phase === "working") return "chopping red gum";
    return "hauling timber home";
  }
  if (task.phase === "moving") return "heading to the floodplain";
  if (task.phase === "working") return "gathering food";
  return "carrying food home";
}

export interface LabourOpts {
  scene: THREE.Scene;
  terrain: Terrain;
  map: GameMap;
  sim: Simulation;
  hud: HudRefs;
  units: UnitManager;
  homePos: THREE.Vector3;
}

export interface Labour {
  /** Start (or restart) a chop/gather loop at a world position. */
  assign(s: Settler, kind: TaskKind, x: number, z: number, now: number): void;
  /** Right-click routing: chop on redgum, gather on floodplain, else plain move. */
  orderAt(s: Settler, x: number, z: number, now: number): void;
  /** Drop any task (plain move / muster keeps working settlers honest). */
  clearTask(s: Settler): void;
  update(dt: number, t: number): void;
}

export function installLabour(opts: LabourOpts): Labour {
  const { scene, terrain, map, sim, hud, units, homePos } = opts;
  const rand = mulberry32(1887); // chip scatter only; world content stays elsewhere

  // Post-1847 the passive economy steps back (see state.ts tick()).
  sim.labourRebalance = true;

  // Deposits land at the veranda front of the homestead.
  const depotX = homePos.x + 1.5;
  const depotZ = homePos.z + 5;

  // --- Wood-chip burst pool (soft brown sprites, mock-up glow style) -----------
  const chipTex = makeGlowTexture("146,94,47");
  interface Chip {
    sprite: THREE.Sprite;
    vel: THREE.Vector3;
    life: number; // remaining seconds; <= 0 means free
  }
  const chips: Chip[] = [];
  for (let i = 0; i < 36; i++) {
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: chipTex, transparent: true, opacity: 0, depthWrite: false })
    );
    sprite.visible = false;
    scene.add(sprite);
    chips.push({ sprite, vel: new THREE.Vector3(), life: 0 });
  }
  function burstChips(x: number, y: number, z: number) {
    let spawned = 0;
    for (const c of chips) {
      if (c.life > 0) continue;
      c.life = 0.55 + rand() * 0.25;
      c.sprite.visible = true;
      c.sprite.position.set(x, y, z);
      c.sprite.scale.setScalar(0.28 + rand() * 0.22);
      (c.sprite.material as THREE.SpriteMaterial).opacity = 0.9;
      const a = rand() * Math.PI * 2;
      c.vel.set(Math.cos(a) * (1 + rand() * 2), 2.5 + rand() * 2, Math.sin(a) * (1 + rand() * 2));
      if (++spawned >= 6) break;
    }
  }

  // --- Carry props: red gum log / cream tucker sack ----------------------------
  const logMat = new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color: 0x6b452c });
  const sackMat = new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color: 0xe6d8b4 });
  function propsFor(s: Settler) {
    let p = props.get(s);
    if (!p) {
      const log = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 1.05), logMat);
      log.position.set(0, 1.08, 0.34);
      log.rotation.z = 0.12;
      log.castShadow = true;
      const sack = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.36, 0.34), sackMat);
      sack.position.set(0, 1.12, 0.32);
      sack.rotation.x = 0.1;
      sack.castShadow = true;
      log.visible = sack.visible = false;
      s.group.add(log, sack);
      p = { log, sack };
      props.set(s, p);
    }
    return p;
  }
  function showProp(s: Settler, kind: TaskKind | null) {
    const p = propsFor(s);
    p.log.visible = kind === "chop";
    p.sack.visible = kind === "gather";
  }

  function assign(s: Settler, kind: TaskKind, x: number, z: number, now: number) {
    tasks.set(s, { kind, phase: "moving", workX: x, workZ: z, workT: 0, strikesDone: 0, heading: 0 });
    showProp(s, null);
    s.body.rotation.x = 0;
    units.order(s, x, z, now);
  }

  function clearTask(s: Settler) {
    if (!tasks.has(s)) return;
    tasks.delete(s);
    showProp(s, null);
    s.body.rotation.x = 0;
  }

  function orderAt(s: Settler, x: number, z: number, now: number) {
    const g = terrain.worldToTile(x, z);
    const kind = map.at(Math.round(g.x), Math.round(g.y)).kind;
    if (kind === "redgum") assign(s, "chop", x, z, now);
    else if (kind === "floodplain") assign(s, "gather", x, z, now);
    else {
      clearTask(s);
      units.order(s, x, z, now);
    }
  }

  // Keep the status line live as the selected settler moves through the loop.
  let lastLabel = "";

  function update(dt: number, t: number) {
    for (const s of units.settlers) {
      const task = tasks.get(s);
      if (!task) continue;

      if (task.phase === "moving") {
        // units.update walks the settler; arrival clears target.
        if (!s.target) {
          task.phase = "working";
          task.workT = 0;
          task.strikesDone = 0;
          task.heading = s.group.rotation.y;
        }
      } else if (task.phase === "working") {
        task.workT += dt;
        s.group.rotation.y = task.heading; // hold facing against the idle drift
        const u = (task.workT % SWING_PERIOD) / SWING_PERIOD;
        if (task.kind === "chop") {
          // Raise the axe arm slowly, strike fast, recover — with a body lean.
          let arm: number;
          if (u < 0.6) arm = -(u / 0.6) * 2.1; // wind up
          else if (u < 0.72) arm = -2.1 + ((u - 0.6) / 0.12) * 3.0; // strike
          else arm = 0.9 - ((u - 0.72) / 0.28) * 0.9; // recover
          s.armR.rotation.x = arm;
          s.armL.rotation.x = Math.sin(u * Math.PI * 2) * 0.15;
          s.body.rotation.x = 0.1 + Math.max(0, arm) * 0.18;
        } else {
          // Gathering: both arms sweep low over the tucker grounds, back bent.
          const sw = Math.sin(t * 2.4 + s.phase);
          s.armR.rotation.x = 0.9 + sw * 0.5;
          s.armL.rotation.x = 0.9 - sw * 0.5;
          s.body.rotation.x = 0.28;
        }
        // One chip burst per completed strike (chop only).
        const cycle = Math.floor(task.workT / SWING_PERIOD);
        const inStrike = u >= 0.68;
        if (task.kind === "chop" && inStrike && task.strikesDone <= cycle) {
          task.strikesDone = cycle + 1;
          const fx = s.group.position.x + Math.sin(task.heading) * 0.9;
          const fz = s.group.position.z + Math.cos(task.heading) * 0.9;
          burstChips(fx, s.group.position.y + 1.1, fz);
        }
        if (task.workT >= SWING_PERIOD * SWINGS_PER_TRIP) {
          task.phase = "carrying";
          s.body.rotation.x = 0;
          showProp(s, task.kind);
          // Head home without the green order flourish (auto-move, not a command).
          s.target = new THREE.Vector3(depotX, 0, depotZ);
        }
      } else {
        // carrying → deposit at the homestead, then walk straight back out.
        if (!s.target) {
          if (task.kind === "chop") sim.resources.timber += TIMBER_PER_TRIP;
          else sim.resources.food += FOOD_PER_TRIP;
          showProp(s, null);
          task.phase = "moving";
          s.target = new THREE.Vector3(task.workX, 0, task.workZ);
        }
      }
    }

    // Refresh "Tom — chopping red gum" whenever the selected settler's task shifts.
    if (units.selected) {
      const label = getTaskLabel(units.selected);
      if (label !== lastLabel) {
        lastLabel = label;
        hud.setSelected(units.selected);
      }
    }

    // Chip physics: a short arc with gravity, fading out.
    for (const c of chips) {
      if (c.life <= 0) continue;
      c.life -= dt;
      if (c.life <= 0) {
        c.sprite.visible = false;
        continue;
      }
      c.vel.y -= 9.5 * dt;
      c.sprite.position.addScaledVector(c.vel, dt);
      (c.sprite.material as THREE.SpriteMaterial).opacity = Math.min(0.9, c.life * 2.2);
    }
  }

  return { assign, orderAt, clearTask, update };
}
