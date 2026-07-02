// M3 — The Water System (docs/mildura-history.md §4, timeline 1889–1892).
//
// The keystone mechanic: water is PUMPED up from the Murray at Psyche Bend
// (the Tangye steam pumps, "water runs uphill", 1889) and then gravity-fed
// along channels to the fruit blocks. Nothing here may run uphill from the
// channel head — gravity is the law. From 15 years after irrigation begins,
// the lowest-lying irrigated ground starts to salt up (the long-term curse;
// the drainage outfall answer only arrives in 1924).
import * as THREE from "three";
import { GRID_W, GRID_H } from "../config";
import type { GameMap, Tile } from "../map/mapData";
import type { Terrain } from "../render/world";
import { toonGradient, makeGlowTexture } from "../render/world";
import { mulberry32 } from "../util/rng";
import type { Simulation } from "./state";

export interface WaterworksOptions {
  scene: THREE.Scene;
  terrain: Terrain;
  map: GameMap;
  sim: Simulation;
}

export interface Waterworks {
  /** Per-frame: builds the works once sim.year >= 1889, animates water/steam. */
  update(dt: number, t: number): void;
  /** Per sim tick (call right after sim.tick()): pump water + irrigated food. */
  applyTick(): void;
  /** +water per tick while the pump runs (0 before 1889). */
  getWaterTick(): number;
  /** +food per tick from irrigated blocks, capped ~12; salted tiles yield 0. */
  getFoodTick(): number;
  /** Irrigated tiles lost to salt — for a future HUD "salinity" line. */
  getSalinityCount(): number;
  /** Irrigated tile count (includes salted). */
  getIrrigatedCount(): number;
}

// History (docs/mildura-history.md): pumping/irrigation begins 1889; salinity
// creeps in over the following decades. We start the mottle 15 years on.
const PUMP_YEAR = 1889;
const SALT_LAG_YEARS = 15;
const FOOD_CAP = 12;
const IRRIGATION_RADIUS = 2.5; // tiles from a channel
const MAX_CHANNEL_TILES = 60;

function toonMat(opts: THREE.MeshToonMaterialParameters = {}): THREE.MeshToonMaterial {
  return new THREE.MeshToonMaterial({ gradientMap: toonGradient(), ...opts });
}

// --- Channel routing --------------------------------------------------------
// Deterministic: walk from the pump's channel head toward the township, then
// branch along roughly-constant elevation. Every channel tile must satisfy
// elevation <= head elevation (+epsilon) — water never runs uphill from the head.
export interface ChannelTile {
  x: number;
  y: number;
  dx: number; // flow direction (unit grid step) for strip orientation
  dy: number;
}

// Exported for headless verification / the __mildura dev hook.
export function routeChannels(map: GameMap): { tiles: ChannelTile[]; headElev: number } {
  const rand = mulberry32(0x1889);
  const pump = map.landmarkTiles["psyche_bend"];
  const town = map.landmarkTiles["township"];
  const tiles: ChannelTile[] = [];
  if (!pump || !town) return { tiles, headElev: 0 };

  const inChannel = new Set<number>();
  const key = (x: number, y: number) => y * GRID_W + x;
  const land = (x: number, y: number): Tile | null => {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return null;
    const t = map.at(x, y);
    return t.water ? null : t;
  };

  // Head: step off the water first (the bank lies south of the river), then
  // two tiles inland toward the township — the discharge pipe lifts the water
  // this far, gravity takes over from here.
  let hx = pump.x;
  let hy = pump.y;
  let guard = 0;
  while (!land(hx, hy) && guard++ < GRID_H) hy = Math.min(GRID_H - 1, hy + 1);
  for (let s = 0; s < 2; s++) {
    const nx = hx + Math.sign(town.x - hx);
    const ny = hy + Math.sign(town.y - hy);
    if (land(nx, ny)) {
      hx = nx;
      hy = ny;
    }
  }
  const head = land(hx, hy) ?? map.at(pump.x, pump.y);
  const headElev = head.elevation + 1e-4;

  const push = (x: number, y: number, dx: number, dy: number) => {
    inChannel.add(key(x, y));
    tiles.push({ x, y, dx, dy });
  };
  push(head.x, head.y, Math.sign(town.x - head.x) || 1, Math.sign(town.y - head.y));

  const STEPS: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]];

  // Mainline: greedy toward the township, never above the head.
  let cx = head.x;
  let cy = head.y;
  const mainline: ChannelTile[] = [tiles[0]];
  for (let s = 0; s < 30 && tiles.length < MAX_CHANNEL_TILES; s++) {
    let best: { x: number; y: number; dx: number; dy: number } | null = null;
    let bestD = Infinity;
    for (const [dx, dy] of STEPS) {
      const nx = cx + dx;
      const ny = cy + dy;
      const t = land(nx, ny);
      if (!t || inChannel.has(key(nx, ny)) || t.elevation > headElev) continue;
      const d = (nx - town.x) ** 2 + (ny - town.y) ** 2 + rand() * 0.5; // tie jitter
      if (d < bestD) {
        bestD = d;
        best = { x: nx, y: ny, dx, dy };
      }
    }
    if (!best) break; // gravity says no further
    push(best.x, best.y, best.dx, best.dy);
    mainline.push(tiles[tiles.length - 1]);
    cx = best.x;
    cy = best.y;
    if ((cx - town.x) ** 2 + (cy - town.y) ** 2 <= 4) break;
  }

  // Branches: every ~6th mainline tile, run laterals both ways along
  // roughly-constant elevation (contour furrows feeding the blocks).
  for (let i = 5; i < mainline.length && tiles.length < MAX_CHANNEL_TILES; i += 6) {
    const m = mainline[i];
    const perp: [number, number][] = m.dx !== 0 ? [[0, 1], [0, -1]] : [[1, 0], [-1, 0]];
    const startElev = map.at(m.x, m.y).elevation;
    for (const [pdx, pdy] of perp) {
      let bx = m.x;
      let by = m.y;
      const len = 4 + Math.floor(rand() * 4);
      for (let s = 0; s < len && tiles.length < MAX_CHANNEL_TILES; s++) {
        // Prefer straight ahead; slip sideways only to hold the contour.
        const cands: [number, number][] = [[pdx, pdy], [m.dx, m.dy], [-m.dx, -m.dy]];
        let pick: { x: number; y: number; dx: number; dy: number } | null = null;
        let pickErr = Infinity;
        for (let c = 0; c < cands.length; c++) {
          const [dx, dy] = cands[c];
          if (dx === 0 && dy === 0) continue;
          const nx = bx + dx;
          const ny = by + dy;
          const t = land(nx, ny);
          if (!t || inChannel.has(key(nx, ny)) || t.elevation > headElev) continue;
          const err = Math.abs(t.elevation - startElev) + c * 0.02; // straight bias
          if (err < pickErr) {
            pickErr = err;
            pick = { x: nx, y: ny, dx, dy };
          }
        }
        if (!pick) break;
        push(pick.x, pick.y, pick.dx, pick.dy);
        bx = pick.x;
        by = pick.y;
      }
    }
  }

  return { tiles, headElev };
}

// --- Pump station -----------------------------------------------------------
// Brick engine house + tall chimney + big intake pipe angled into the river,
// ~8 world units tall — the Psyche Bend silhouette.
function buildPumpStation(
  scene: THREE.Scene,
  terrain: Terrain,
  map: GameMap
): { group: THREE.Group; chimneyTop: THREE.Vector3 } {
  const pump = map.landmarkTiles["psyche_bend"];
  // The landmark tile may sit in the channel; anchor the engine house on the
  // south bank and run the intake pipe back north into the river.
  let by = pump.y;
  while (by < GRID_H - 1 && map.at(pump.x, by).water) by++;
  const w = terrain.tileToWorld(pump.x, by + 1 < GRID_H ? by + 1 : by);
  const baseY = Math.max(terrain.heightAt(w.x, w.z), terrain.WATER_LEVEL + 0.15);
  const g = new THREE.Group();
  g.position.set(w.x, baseY, w.z);

  const brick = toonMat({ color: 0x99432f });
  const brickDark = toonMat({ color: 0x7c3626 });
  const iron = toonMat({ color: 0x4c5157 });
  const roofMat = toonMat({ color: 0x6a6f75 });

  const house = new THREE.Mesh(new THREE.BoxGeometry(5.2, 3.6, 3.6), brick);
  house.position.y = 1.8;
  house.castShadow = house.receiveShadow = true;
  g.add(house);

  // Gable roof: squashed 4-sided cone, mock-up style.
  const roof = new THREE.Mesh(new THREE.ConeGeometry(3.4, 1.7, 4), roofMat);
  roof.rotation.y = Math.PI / 4;
  roof.scale.set(1.25, 1, 0.85);
  roof.position.y = 4.45;
  roof.castShadow = true;
  g.add(roof);

  // Arched-door hint: dark inset panel facing the river (north = -z).
  const door = new THREE.Mesh(new THREE.BoxGeometry(1.2, 2.0, 0.15), brickDark);
  door.position.set(0, 1.0, -1.85);
  g.add(door);

  // Chimney: the stack that carries the whole silhouette to ~8 units.
  const stack = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.62, 7.6, 8), brickDark);
  stack.position.set(1.7, 3.8, 1.0);
  stack.castShadow = true;
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.58, 0.5, 0.5, 8), brick);
  cap.position.set(1.7, 7.7, 1.0);
  g.add(stack, cap);

  // Big intake pipe angled down into the river. The river lies north (-z in
  // world space): run the pipe from the engine house down under the surface.
  const start = new THREE.Vector3(w.x - 1.2, baseY + 1.1, w.z - 1.6);
  const riverT = terrain.tileToWorld(pump.x, Math.max(0, by - 3)); // 3 tiles out into the channel
  const end = new THREE.Vector3(riverT.x - 1.2, terrain.WATER_LEVEL - 0.5, riverT.z);
  const dir = end.clone().sub(start);
  const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.44, dir.length(), 8), iron);
  pipe.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  pipe.position.copy(start).add(dir.multiplyScalar(0.5)).sub(g.position);
  pipe.castShadow = true;
  g.add(pipe);
  // Flanged elbow where the pipe leaves the engine house.
  const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.56, 0.56, 0.34, 8), iron);
  flange.quaternion.copy(pipe.quaternion);
  flange.position.copy(start).sub(g.position);
  flange.castShadow = true;
  g.add(flange);

  scene.add(g);
  return { group: g, chimneyTop: new THREE.Vector3(w.x + 1.7, baseY + 8.0, w.z + 1.0) };
}

// --- Install -----------------------------------------------------------------
export function installWaterworks(opts: WaterworksOptions): Waterworks {
  const { scene, terrain, map, sim } = opts;
  const tileW = terrain.MAP_W / (GRID_W - 1);
  const tileD = terrain.MAP_D / (GRID_H - 1);

  let built = false;
  let salted = false;
  let saltedCount = 0;
  let irrigated: Tile[] = [];
  let steam: THREE.Sprite[] = [];
  let chimneyTop = new THREE.Vector3();
  let flowTex: THREE.CanvasTexture | null = null;

  function tintVertex(colors: THREE.BufferAttribute, t: Tile, target: THREE.Color, k: number) {
    const i = t.y * GRID_W + t.x;
    const c = new THREE.Color(colors.getX(i), colors.getY(i), colors.getZ(i)).lerp(target, k);
    colors.setXYZ(i, c.r, c.g, c.b);
  }

  function build() {
    built = true;

    // 1) Pump station + steam puffs.
    const ps = buildPumpStation(scene, terrain, map);
    chimneyTop = ps.chimneyTop;
    const steamTex = makeGlowTexture("236,238,240");
    for (let i = 0; i < 8; i++) {
      const s = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: steamTex, transparent: true, opacity: 0.5, depthWrite: false })
      );
      s.userData.seed = i / 8;
      scene.add(s);
      steam.push(s);
    }

    // 2) Channels.
    const { tiles: channel, headElev } = routeChannels(map);

    // Dark cut strip (the excavated channel bed).
    const cutGeo = new THREE.BoxGeometry(tileW * 1.12, 0.42, tileD * 0.62);
    const cutMat = toonMat({ color: 0x3a2d20 });
    const cut = new THREE.InstancedMesh(cutGeo, cutMat, Math.max(1, channel.length));
    // Bright running water on top: canvas streak texture, UV-scrolled in update().
    const c = document.createElement("canvas");
    c.width = 64;
    c.height = 16;
    {
      const x = c.getContext("2d")!;
      x.fillStyle = "#5fb4dd";
      x.fillRect(0, 0, 64, 16);
      x.fillStyle = "rgba(255,255,255,0.75)";
      for (const [sx, sy, sw] of [[4, 3, 20], [30, 9, 22], [48, 5, 14], [14, 12, 16]] as const) {
        x.beginPath();
        x.ellipse(sx + sw / 2, sy, sw / 2, 1.4, 0, 0, 7);
        x.fill();
      }
    }
    flowTex = new THREE.CanvasTexture(c);
    flowTex.wrapS = flowTex.wrapT = THREE.RepeatWrapping;
    const flowGeo = new THREE.PlaneGeometry(tileW * 1.12, tileD * 0.4);
    flowGeo.rotateX(-Math.PI / 2);
    const flowMat = new THREE.MeshBasicMaterial({ map: flowTex, transparent: true, opacity: 0.92, depthWrite: false });
    const flow = new THREE.InstancedMesh(flowGeo, flowMat, Math.max(1, channel.length));

    const dummy = new THREE.Object3D();
    for (let i = 0; i < channel.length; i++) {
      const ct = channel[i];
      const w = terrain.tileToWorld(ct.x, ct.y);
      const y = terrain.heightAt(w.x, w.z);
      const ang = Math.atan2(-ct.dy * tileD, ct.dx * tileW); // strip long axis = flow dir
      dummy.position.set(w.x, y + 0.05, w.z);
      dummy.rotation.set(0, ang, 0);
      dummy.scale.setScalar(1);
      dummy.updateMatrix();
      cut.setMatrixAt(i, dummy.matrix);
      dummy.position.y = y + 0.32;
      dummy.updateMatrix();
      flow.setMatrixAt(i, dummy.matrix);
    }
    cut.instanceMatrix.needsUpdate = true;
    flow.instanceMatrix.needsUpdate = true;
    cut.receiveShadow = true;
    scene.add(cut, flow);

    // 3) Irrigation: tiles near a channel, never above the head — gravity feed.
    const near = new Set<number>();
    const R = Math.ceil(IRRIGATION_RADIUS);
    for (const ct of channel) {
      for (let dy = -R; dy <= R; dy++) {
        for (let dx = -R; dx <= R; dx++) {
          if (dx * dx + dy * dy > IRRIGATION_RADIUS * IRRIGATION_RADIUS) continue;
          const nx = ct.x + dx;
          const ny = ct.y + dy;
          if (nx < 0 || ny < 0 || nx >= GRID_W || ny >= GRID_H) continue;
          const t = map.at(nx, ny);
          if (t.water || t.elevation > headElev) continue;
          near.add(ny * GRID_W + nx);
        }
      }
    }
    irrigated = [...near].sort((a, b) => a - b).map((i) => map.at(i % GRID_W, Math.floor(i / GRID_W)));

    // Tint the terrain toward lush irrigated green.
    const colors = terrain.mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
    const lush = new THREE.Color(0x4da635);
    for (const t of irrigated) tintVertex(colors, t, lush, 0.45);
    colors.needsUpdate = true;

    // 4) Vine rows on irrigated floodplain/mallee blocks (not in the channel cut).
    const rand = mulberry32(0x1890);
    const channelKeys = new Set(channel.map((ct) => ct.y * GRID_W + ct.x));
    const vineTiles = irrigated.filter(
      (t) => (t.kind === "floodplain" || t.kind === "mallee") && !channelKeys.has(t.y * GRID_W + t.x)
    );
    const rowGeo = new THREE.BoxGeometry(tileW * 0.72, 0.5, 0.26);
    rowGeo.translate(0, 0.28, 0);
    const rowMat = toonMat({ color: 0x3c7d2c });
    const rows = new THREE.InstancedMesh(rowGeo, rowMat, Math.max(1, vineTiles.length * 2));
    const tint = new THREE.Color();
    let ri = 0;
    for (const t of vineTiles) {
      const w = terrain.tileToWorld(t.x, t.y);
      for (let k = 0; k < 2; k++) {
        const zOff = (k - 0.5) * tileD * 0.5;
        const x = w.x + (rand() - 0.5) * 0.4;
        const z = w.z + zOff;
        dummy.position.set(x, terrain.heightAt(x, z), z);
        dummy.rotation.set(0, (rand() - 0.5) * 0.14, 0);
        dummy.scale.setScalar(0.85 + rand() * 0.35);
        dummy.updateMatrix();
        rows.setMatrixAt(ri, dummy.matrix);
        tint.setHSL(0.29 + rand() * 0.05, 0.5, 0.3 + rand() * 0.14);
        rows.setColorAt(ri, tint);
        ri++;
      }
    }
    rows.count = ri;
    rows.instanceMatrix.needsUpdate = true;
    if (rows.instanceColor) rows.instanceColor.needsUpdate = true;
    rows.castShadow = true;
    scene.add(rows);
  }

  // Salt mottle: the lowest ~10% of irrigated ground, 15 years after the pumps.
  function applySalinity() {
    salted = true;
    const n = Math.floor(irrigated.length * 0.1);
    const lowest = [...irrigated].sort((a, b) => a.elevation - b.elevation).slice(0, n);
    saltedCount = lowest.length;
    const colors = terrain.mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
    const salt = new THREE.Color(0xdcdcd2);
    for (const t of lowest) tintVertex(colors, t, salt, 0.7);
    colors.needsUpdate = true;
  }

  function getWaterTick(): number {
    return built ? 2 : 0;
  }
  function getFoodTick(): number {
    if (!built) return 0;
    const productive = irrigated.length - saltedCount;
    return Math.min(FOOD_CAP, Math.floor(productive / 10));
  }

  return {
    update(_dt: number, t: number) {
      if (!built && sim.year >= PUMP_YEAR) build(); // also covers loaded saves past 1889
      if (built && !salted && sim.year >= PUMP_YEAR + SALT_LAG_YEARS) applySalinity();
      if (!built) return;
      if (flowTex) flowTex.offset.x = -((t * 0.5) % 1); // channel water visibly running
      for (const s of steam) {
        const ph = (t * 0.22 + (s.userData.seed as number)) % 1;
        s.position.set(
          chimneyTop.x + Math.sin(ph * 8) * 0.35 + ph * 1.2,
          chimneyTop.y + ph * 4.6,
          chimneyTop.z + Math.cos(ph * 6) * 0.3
        );
        s.scale.setScalar(0.6 + ph * 2.4);
        (s.material as THREE.SpriteMaterial).opacity = 0.5 * (1 - ph);
      }
    },
    applyTick() {
      if (!built || sim.paused) return;
      const r = sim.resources;
      r.water = Math.min(100, r.water + getWaterTick());
      r.food += getFoodTick();
    },
    getWaterTick,
    getFoodTick,
    getSalinityCount: () => saltedCount,
    getIrrigatedCount: () => irrigated.length,
  };
}
