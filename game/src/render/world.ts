// World rendering, styled to the approved mock-up (docs/build-prompt.md §1.8):
// cel/toon shading with stepped gradients, flat-faceted foliage, real branching
// gum trees with clumped canopies, dense ground cover, light flowing water with
// streaks and rock foam.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { GRID_W, GRID_H } from "../config";
import type { GameMap, Tile } from "../map/mapData";
import { mulberry32 } from "../util/rng";

export interface Terrain {
  mesh: THREE.Mesh;
  heightAt(x: number, z: number): number;
  tileToWorld(tx: number, ty: number): { x: number; z: number };
  worldToTile(x: number, z: number): { x: number; y: number };
  MAP_W: number;
  MAP_D: number;
  HEIGHT_SCALE: number;
  WATER_LEVEL: number;
}

const BED_DROP = 0.06;

function hash2(x: number, y: number): number {
  return mulberry32((x * 73856093) ^ (y * 19349663) ^ 0x5bd1)();
}

// --- Toon shading ---------------------------------------------------------------
let _gradient: THREE.DataTexture | null = null;
export function toonGradient(): THREE.DataTexture {
  if (_gradient) return _gradient;
  const data = new Uint8Array([70, 118, 178, 255]);
  _gradient = new THREE.DataTexture(data, data.length, 1, THREE.RedFormat);
  _gradient.minFilter = _gradient.magFilter = THREE.NearestFilter;
  _gradient.needsUpdate = true;
  return _gradient;
}
function toonMat(opts: THREE.MeshToonMaterialParameters = {}): THREE.MeshToonMaterial {
  return new THREE.MeshToonMaterial({ gradientMap: toonGradient(), ...opts });
}

// Painterly base colours per tile kind.
export function paintColour(t: Tile, out: THREE.Color): THREE.Color {
  switch (t.kind) {
    case "river":
      out.setHex(0x4d84a8);
      break;
    case "billabong":
      out.setHex(0x568cA4);
      break;
    case "redgum":
      out.setHex(0x4a7a2e);
      break;
    case "floodplain":
      out.setHex(0x83a04a);
      break;
    case "mallee":
      out.setHex(0x64843c);
      break;
    case "belah":
      out.setHex(0x557234);
      break;
    default:
      out.setHex(0xac8d55);
  }
  const patch = hash2(t.x >> 2, t.y >> 2) - 0.5;
  const jit = hash2(t.x, t.y) - 0.5;
  const hsl = { h: 0, s: 0, l: 0 };
  out.getHSL(hsl);
  out.setHSL(
    hsl.h + jit * 0.014 + patch * 0.012,
    Math.min(1, Math.max(0, hsl.s + patch * 0.1)),
    Math.min(1, Math.max(0, hsl.l + patch * 0.07 + jit * 0.04))
  );
  if (!t.water) out.offsetHSL(0, 0, t.elevation * 0.04);
  return out;
}

export function buildTerrain(
  scene: THREE.Scene,
  map: GameMap,
  MAP_W: number,
  MAP_D: number,
  HEIGHT_SCALE: number,
  WATER_LEVEL: number
): Terrain {
  const geo = new THREE.PlaneGeometry(MAP_W, MAP_D, GRID_W - 1, GRID_H - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  const colors = new Float32Array(GRID_W * GRID_H * 3);
  const heights = new Float32Array(GRID_W * GRID_H);
  const col = new THREE.Color();
  for (let iy = 0; iy < GRID_H; iy++) {
    for (let ix = 0; ix < GRID_W; ix++) {
      const idx = iy * GRID_W + ix;
      const t = map.at(ix, iy);
      const elev = (t.water ? t.elevation - BED_DROP : t.elevation) * HEIGHT_SCALE;
      heights[idx] = elev;
      pos.setY(idx, elev);
      paintColour(t, col);
      colors[idx * 3] = col.r;
      colors[idx * 3 + 1] = col.g;
      colors[idx * 3 + 2] = col.b;
    }
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, toonMat({ vertexColors: true }));
  mesh.receiveShadow = true;
  scene.add(mesh);

  const tileToWorld = (tx: number, ty: number) => ({
    x: -MAP_W / 2 + (tx / (GRID_W - 1)) * MAP_W,
    z: -MAP_D / 2 + (ty / (GRID_H - 1)) * MAP_D,
  });
  const worldToTile = (x: number, z: number) => ({
    x: Math.min(GRID_W - 1, Math.max(0, ((x + MAP_W / 2) / MAP_W) * (GRID_W - 1))),
    y: Math.min(GRID_H - 1, Math.max(0, ((z + MAP_D / 2) / MAP_D) * (GRID_H - 1))),
  });
  const heightAt = (x: number, z: number) => {
    const g = worldToTile(x, z);
    const x0 = Math.floor(g.x), y0 = Math.floor(g.y);
    const x1 = Math.min(GRID_W - 1, x0 + 1), y1 = Math.min(GRID_H - 1, y0 + 1);
    const fx = g.x - x0, fy = g.y - y0;
    const h00 = heights[y0 * GRID_W + x0], h10 = heights[y0 * GRID_W + x1];
    const h01 = heights[y1 * GRID_W + x0], h11 = heights[y1 * GRID_W + x1];
    return (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy;
  };

  return { mesh, heightAt, tileToWorld, worldToTile, MAP_W, MAP_D, HEIGHT_SCALE, WATER_LEVEL };
}

// --- Animated water with painterly flow streaks ---------------------------------
export function buildWater(scene: THREE.Scene, terrain: Terrain, map: GameMap) {
  const SEG_X = 120, SEG_Y = 96;
  const geo = new THREE.PlaneGeometry(terrain.MAP_W, terrain.MAP_D, SEG_X, SEG_Y);
  geo.rotateX(-Math.PI / 2);
  const mesh = new THREE.Mesh(
    geo,
    toonMat({ color: 0x74b0d4, transparent: true, opacity: 0.92 })
  );
  mesh.position.y = terrain.WATER_LEVEL;
  scene.add(mesh);

  const pos = geo.attributes.position as THREE.BufferAttribute;
  const baseX = new Float32Array(pos.count);
  const baseZ = new Float32Array(pos.count);
  for (let i = 0; i < pos.count; i++) {
    baseX[i] = pos.getX(i);
    baseZ[i] = pos.getZ(i);
  }

  // Flow streaks: soft white dashes drifting downstream along river tiles.
  const streakTexC = document.createElement("canvas");
  streakTexC.width = 64;
  streakTexC.height = 16;
  {
    const x = streakTexC.getContext("2d")!;
    const g = x.createLinearGradient(0, 0, 64, 0);
    g.addColorStop(0, "rgba(255,255,255,0)");
    g.addColorStop(0.35, "rgba(255,255,255,0.8)");
    g.addColorStop(0.7, "rgba(255,255,255,0.55)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g;
    x.beginPath();
    x.ellipse(32, 8, 30, 5, 0, 0, 7);
    x.fill();
  }
  const streakTex = new THREE.CanvasTexture(streakTexC);
  const streakMat = new THREE.MeshBasicMaterial({
    map: streakTex,
    transparent: true,
    depthWrite: false,
    opacity: 0.55,
  });
  const streakGeo = new THREE.PlaneGeometry(5.5, 1.0);
  streakGeo.rotateX(-Math.PI / 2);

  const riverCols: { x: number; z: number }[] = [];
  for (let tx = 0; tx < GRID_W; tx += 2) {
    for (let ty = 0; ty < GRID_H; ty++) {
      if (map.at(tx, ty).kind === "river") {
        const w = terrain.tileToWorld(tx, ty);
        riverCols.push({ x: w.x, z: w.z });
        break;
      }
    }
  }
  const streaks: { m: THREE.Mesh; ox: number; oz: number; ph: number }[] = [];
  for (let i = 0; i < riverCols.length; i++) {
    if (hash2(i, 7) > 0.55) continue;
    const rc = riverCols[i];
    const m = new THREE.Mesh(streakGeo, streakMat);
    m.position.set(rc.x, terrain.WATER_LEVEL + 0.09, rc.z + (hash2(i, 3) - 0.5) * 2.5);
    scene.add(m);
    streaks.push({ m, ox: rc.x, oz: m.position.z, ph: hash2(i, 11) * 8 });
  }

  return {
    mesh,
    update(t: number) {
      for (let i = 0; i < pos.count; i++) {
        const x = baseX[i], z = baseZ[i];
        pos.setY(
          i,
          0.09 * Math.sin(x * 0.55 + t * 1.9) +
            0.06 * Math.sin(z * 0.8 - t * 1.3) +
            0.04 * Math.sin((x + z) * 1.7 + t * 3.1)
        );
      }
      pos.needsUpdate = true;
      geo.computeVertexNormals();
      for (const s of streaks) {
        const ph = (t * 0.55 + s.ph) % 3;
        s.m.position.x = s.ox + ph * 4 - 6;
        (s.m.material as THREE.MeshBasicMaterial).opacity = 0.5 * Math.sin((ph / 3) * Math.PI);
      }
    },
  };
}

// --- Soft round sprite texture (foam / smoke) ------------------------------------
export function makeGlowTexture(rgb: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 2, 32, 32, 30);
  g.addColorStop(0, `rgba(${rgb},0.95)`);
  g.addColorStop(0.55, `rgba(${rgb},0.45)`);
  g.addColorStop(1, `rgba(${rgb},0)`);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

// --- Branching gum-tree archetypes ------------------------------------------------
interface Archetype {
  geo: THREE.BufferGeometry;
  anchors: THREE.Vector3[]; // foliage clump positions (branch tips), local space
}

function buildArchetype(seed: number): Archetype {
  const rand = mulberry32(seed);
  const parts: THREE.BufferGeometry[] = [];
  const anchors: THREE.Vector3[] = [];
  const up = new THREE.Vector3(0, 1, 0);

  function segment(start: THREE.Vector3, dir: THREE.Vector3, len: number, r0: number, r1: number) {
    const g = new THREE.CylinderGeometry(r1, r0, len, 5, 1);
    g.translate(0, len / 2, 0);
    const q = new THREE.Quaternion().setFromUnitVectors(up, dir.clone().normalize());
    g.applyQuaternion(q);
    g.translate(start.x, start.y, start.z);
    parts.push(g);
    return start.clone().add(dir.clone().normalize().multiplyScalar(len));
  }

  // Trunk: thick, short, slightly leaning — classic river red gum.
  const lean = new THREE.Vector3((rand() - 0.5) * 0.35, 1, (rand() - 0.5) * 0.35);
  const trunkTop = segment(new THREE.Vector3(0, 0, 0), lean, 2.1 + rand() * 0.9, 0.62, 0.42);

  // 3–4 main limbs forking outward and up, each with 1–2 twigs.
  const limbs = 3 + Math.floor(rand() * 2);
  for (let i = 0; i < limbs; i++) {
    const az = (i / limbs) * Math.PI * 2 + rand() * 0.8;
    const tilt = 0.55 + rand() * 0.5; // radians off vertical
    const dir = new THREE.Vector3(Math.sin(tilt) * Math.cos(az), Math.cos(tilt), Math.sin(tilt) * Math.sin(az));
    const end = segment(trunkTop, dir, 2.2 + rand() * 1.4, 0.3, 0.16);
    anchors.push(end.clone());
    const twigs = 1 + Math.floor(rand() * 2);
    for (let k = 0; k < twigs; k++) {
      const tAz = az + (rand() - 0.5) * 1.6;
      const tTilt = tilt * (0.5 + rand() * 0.6);
      const tDir = new THREE.Vector3(Math.sin(tTilt) * Math.cos(tAz), Math.cos(tTilt), Math.sin(tTilt) * Math.sin(tAz));
      const tEnd = segment(end, tDir, 1.3 + rand() * 1.0, 0.13, 0.06);
      anchors.push(tEnd.clone());
    }
  }
  const geo = mergeGeometries(parts)!;
  return { geo, anchors };
}

// Faceted foliage clump (flat-shaded = painterly).
function clumpGeometry(): THREE.BufferGeometry {
  const g = new THREE.IcosahedronGeometry(1.15, 1).toNonIndexed();
  g.scale(1, 0.62, 1);
  g.computeVertexNormals();
  return g;
}

interface Placement {
  p: THREE.Vector3;
  s: number;
  ry: number;
  tint: THREE.Color;
}

function fillInstanced(
  geo: THREE.BufferGeometry,
  mat: THREE.Material,
  items: Placement[],
  shadows = true
): THREE.InstancedMesh {
  const m = new THREE.InstancedMesh(geo, mat, items.length);
  const dummy = new THREE.Object3D();
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    dummy.position.copy(it.p);
    dummy.scale.setScalar(it.s);
    dummy.rotation.set(0, it.ry, 0);
    dummy.updateMatrix();
    m.setMatrixAt(i, dummy.matrix);
    m.setColorAt(i, it.tint);
  }
  m.castShadow = shadows;
  m.instanceMatrix.needsUpdate = true;
  if (m.instanceColor) m.instanceColor.needsUpdate = true;
  return m;
}

export function buildVegetation(scene: THREE.Scene, map: GameMap, terrain: Terrain) {
  const archetypes = [buildArchetype(11), buildArchetype(29), buildArchetype(47)];
  const branchPlacements: Placement[][] = [[], [], []];
  const canopies: Placement[] = [];
  const shrubs: Placement[] = [];
  const grass: Placement[] = [];
  const rocks: Placement[] = [];
  const riverRocks: THREE.Vector3[] = [];
  const logs: Placement[] = [];
  const c = new THREE.Color();

  const jitterPos = (tx: number, ty: number, salt: number, spread = 2.4) => {
    const w = terrain.tileToWorld(tx, ty);
    const r1 = hash2(tx * 3 + salt, ty * 7 + salt) - 0.5;
    const r2 = hash2(tx * 5 + salt, ty * 11 + salt) - 0.5;
    const x = w.x + r1 * spread;
    const z = w.z + r2 * spread;
    return new THREE.Vector3(x, terrain.heightAt(x, z), z);
  };

  const rotY = new THREE.Matrix4();
  const anchorWorld = new THREE.Vector3();

  for (let ty = 0; ty < GRID_H; ty++) {
    for (let tx = 0; tx < GRID_W; tx++) {
      const t = map.at(tx, ty);
      const h = hash2(tx, ty);
      const grassy = t.kind === "redgum" || t.kind === "floodplain" || t.kind === "mallee" || t.kind === "belah";

      if (t.kind === "redgum") {
        const n = h > 0.4 ? 2 : 1;
        for (let k = 0; k < n; k++) {
          const p = jitterPos(tx, ty, k * 13);
          if (p.y < terrain.WATER_LEVEL + 0.1) continue;
          const s = 0.8 + hash2(tx + k, ty - k) * 0.9;
          const ry = hash2(tx - k, ty + k) * Math.PI * 2;
          const ai = Math.floor(hash2(tx * 7 + k, ty * 5) * 3) % 3;
          // pink-brown gum bark
          c.setHSL(0.045 + h * 0.02, 0.28, 0.46 + (h - 0.5) * 0.12);
          branchPlacements[ai].push({ p, s, ry, tint: c.clone() });
          // foliage clumps at every branch tip
          rotY.makeRotationY(ry);
          const anchors = archetypes[ai].anchors;
          for (let b = 0; b < anchors.length; b++) {
            anchorWorld.copy(anchors[b]).applyMatrix4(rotY).multiplyScalar(s).add(p);
            anchorWorld.y -= 0.15 * s; // weeping droop
            c.setHSL(
              0.27 + hash2(tx * 2 + b, ty * 3 + k) * 0.05,
              0.52 + h * 0.12,
              0.17 + hash2(tx + b * 5, ty) * 0.12
            );
            canopies.push({
              p: anchorWorld.clone(),
              s: s * (0.8 + hash2(tx * 7 + b, ty + k) * 0.7),
              ry: b * 1.3,
              tint: c.clone(),
            });
          }
        }
      } else if (t.kind === "mallee" && h < 0.3) {
        const p = jitterPos(tx, ty, 3);
        c.setHSL(0.23 + h * 0.06, 0.46, 0.21 + h * 0.09);
        shrubs.push({ p, s: 0.6 + h * 0.9, ry: h * 6, tint: c.clone() });
      } else if (t.kind === "belah" && h < 0.45) {
        const p = jitterPos(tx, ty, 5);
        c.setHSL(0.28, 0.32, 0.18 + h * 0.07);
        shrubs.push({ p, s: 1.0 + h * 1.1, ry: h * 6, tint: c.clone() });
      } else if (t.kind === "floodplain" && h > 0.93) {
        const p = jitterPos(tx, ty, 7);
        logs.push({ p, s: 0.8 + h, ry: h * 6, tint: new THREE.Color(0x6b4a33) });
      }

      // Ground cover: small tufts, tinted close to the ground so they read as
      // texture, densest under the gums and along the banks.
      if (grassy) {
        const tufts = t.kind === "redgum" ? 3 : 1;
        for (let g = 0; g < tufts; g++) {
          const p = jitterPos(tx, ty, 40 + g * 9, 2.9);
          if (p.y < terrain.WATER_LEVEL + 0.05) continue;
          c.setHSL(0.245 + hash2(tx + g, ty) * 0.04, 0.48, 0.2 + hash2(tx, ty + g) * 0.09);
          grass.push({ p, s: 0.38 + hash2(tx * (g + 1), ty) * 0.42, ry: hash2(tx, ty * (g + 1)) * 6, tint: c.clone() });
        }
      }

      // Boulders: clustered in the channel (foam) and scattered on banks.
      if (t.kind === "river" && hash2(tx * 31, ty * 17) > 0.94) {
        const w = terrain.tileToWorld(tx, ty);
        const cluster = 1 + Math.floor(hash2(tx, ty * 3) * 3);
        for (let r = 0; r < cluster; r++) {
          const p = new THREE.Vector3(
            w.x + (hash2(tx + r, ty) - 0.5) * 3,
            terrain.WATER_LEVEL - 0.02,
            w.z + (hash2(tx, ty + r) - 0.5) * 3
          );
          c.setHSL(0.08, 0.05, 0.58 + (hash2(tx * r + 1, ty) - 0.5) * 0.16);
          rocks.push({ p, s: 0.7 + hash2(tx + r * 3, ty) * 1.1, ry: h * 6 + r, tint: c.clone() });
          if (r === 0) riverRocks.push(p.clone());
        }
      } else if ((t.kind === "redgum" || t.kind === "floodplain") && hash2(tx * 13, ty * 29) > 0.975) {
        const p = jitterPos(tx, ty, 21);
        c.setHSL(0.08, 0.06, 0.55 + (h - 0.5) * 0.16);
        rocks.push({ p, s: 0.5 + h * 0.9, ry: h * 6, tint: c.clone() });
      }
    }
  }

  const barkMat = toonMat();
  const leafMat = toonMat();
  const clump = clumpGeometry();
  const shrubGeo = new THREE.IcosahedronGeometry(1.0, 1).toNonIndexed();
  shrubGeo.scale(1, 0.7, 1);
  shrubGeo.translate(0, 0.55, 0);
  shrubGeo.computeVertexNormals();
  // Grass: crossed quads, anchored at the base.
  const gA = new THREE.PlaneGeometry(1.1, 0.75);
  const gB = gA.clone();
  gB.rotateY(Math.PI / 2);
  const grassGeo = mergeGeometries([gA, gB])!;
  grassGeo.translate(0, 0.3, 0);
  const grassMat = toonMat({ side: THREE.DoubleSide });
  const rockGeo = new THREE.DodecahedronGeometry(0.7, 0).toNonIndexed();
  rockGeo.computeVertexNormals();
  const logGeo = new THREE.CylinderGeometry(0.22, 0.28, 2.4, 6);
  logGeo.rotateZ(Math.PI / 2);
  logGeo.translate(0, 0.24, 0);

  for (let a = 0; a < 3; a++) {
    scene.add(fillInstanced(archetypes[a].geo, barkMat, branchPlacements[a]));
  }
  scene.add(fillInstanced(clump, leafMat, canopies));
  scene.add(fillInstanced(shrubGeo, leafMat, shrubs));
  scene.add(fillInstanced(grassGeo, grassMat, grass, false));
  scene.add(fillInstanced(rockGeo, toonMat(), rocks));
  scene.add(fillInstanced(logGeo, barkMat, logs));

  // Foam where the river breaks around boulders.
  const foamTex = makeGlowTexture("255,255,255");
  const foams: THREE.Sprite[] = [];
  for (const p of riverRocks) {
    for (let i = 0; i < 3; i++) {
      const s = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: foamTex, transparent: true, opacity: 0.7, depthWrite: false })
      );
      s.position.set(p.x + (i - 1) * 0.9, terrain.WATER_LEVEL + 0.12, p.z + 0.8 + i * 0.5);
      s.scale.setScalar(1.4);
      s.userData.phase = i * 2.1 + p.x;
      scene.add(s);
      foams.push(s);
    }
  }

  return {
    counts: { trees: branchPlacements.reduce((n, a) => n + a.length, 0), canopies: canopies.length, grass: grass.length },
    update(t: number) {
      for (const f of foams) {
        const ph = (t * 1.6 + (f.userData.phase as number)) % 2;
        (f.material as THREE.SpriteMaterial).opacity = 0.25 + 0.45 * Math.abs(Math.sin(ph * Math.PI));
        f.scale.setScalar(1.1 + 0.5 * Math.abs(Math.sin(ph * Math.PI)));
      }
    },
  };
}
