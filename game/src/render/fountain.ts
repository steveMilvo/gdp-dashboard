// The travelling fountain — one object, three lives (docs/mildura-history.md §9):
//   A) 1891 — appears in the Rio Vista garden, water playing.
//   B) 1897 — the water stops (Edward Chaffey drowned in it that May; the codex
//      states it plainly, the world only shows a fountain gone still).
//   C) 1936 — the mesh moves to Deakin Avenue as the King George V Memorial
//      Fountain and the water plays again.
// Hover facts ride the existing flagTargets/tooltip pattern via userData.landmark.
import * as THREE from "three";
import type { Terrain } from "./world";
import { toonGradient, makeGlowTexture } from "./world";
import type { GameMap } from "../map/mapData";
import type { Simulation } from "../game/state";

type FountainPhase = "hidden" | "playing" | "still" | "memorial";

interface LandmarkFact {
  name: string;
  fact: string;
  year?: number;
}

const FACTS: Record<Exclude<FountainPhase, "hidden">, LandmarkFact> = {
  playing: {
    name: "The Chaffey Fountain",
    year: 1891,
    fact: "A tiered fountain playing in the Rio Vista garden — brought upriver, it is said, on the paddle steamer PS Gem.",
  },
  still: {
    name: "The Chaffey Fountain",
    year: 1891,
    fact: "The fountain has stood silent since 1897.",
  },
  memorial: {
    name: "King George V Memorial Fountain",
    year: 1936,
    fact: "The old Rio Vista fountain, moved to the Deakin Avenue centre plantation in 1936 in memory of King George V.",
  },
};

function toonMat(color: number): THREE.MeshToonMaterial {
  return new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color });
}

function buildFountainMesh(): THREE.Group {
  const g = new THREE.Group();
  const stone = toonMat(0xcfc6b4);
  const trim = toonMat(0xa89c86);
  const parts: [THREE.BufferGeometry, THREE.MeshToonMaterial, number][] = [
    [new THREE.CylinderGeometry(1.5, 1.62, 0.42, 10), trim, 0.21], // basin wall
    [new THREE.CylinderGeometry(0.24, 0.34, 0.95, 8), stone, 0.85], // pedestal
    [new THREE.CylinderGeometry(0.82, 0.2, 0.26, 10), stone, 1.4], // lower bowl
    [new THREE.CylinderGeometry(0.13, 0.18, 0.5, 8), trim, 1.72], // stem
    [new THREE.CylinderGeometry(0.46, 0.12, 0.2, 10), stone, 2.0], // upper bowl
    [new THREE.ConeGeometry(0.1, 0.32, 8), trim, 2.24], // finial
  ];
  for (const [geo, mat, y] of parts) {
    const m = new THREE.Mesh(geo, mat);
    m.position.y = y;
    m.castShadow = true;
    m.receiveShadow = true;
    g.add(m);
  }
  // still water in the basin (stays even when the jet is off)
  const pool = new THREE.Mesh(
    new THREE.CircleGeometry(1.42, 12),
    new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color: 0x568ca4 })
  );
  pool.rotation.x = -Math.PI / 2;
  pool.position.y = 0.38;
  g.add(pool);
  return g;
}

export function installFountain(opts: {
  scene: THREE.Scene;
  terrain: Terrain;
  map: GameMap;
  sim: Simulation;
  flagTargets: THREE.Object3D[]; // settlement.flagTargets — joins the hover raycast
}): { update(dt: number, t: number): void } {
  const { scene, terrain, map, sim, flagTargets } = opts;

  const town = map.landmarkTiles["township"] ?? { x: 0, y: 0 };
  const tw = terrain.tileToWorld(town.x, town.y);
  // Life A/B: the Rio Vista garden, ~6 world units east of the township.
  const rioVista = new THREE.Vector3(tw.x + 6, 0, tw.z);
  rioVista.y = Math.max(terrain.heightAt(rioVista.x, rioVista.z), terrain.WATER_LEVEL);
  // Life C: the Deakin Avenue centre plantation, ~2 units south of town centre.
  const deakin = new THREE.Vector3(tw.x, 0, tw.z + 2);
  deakin.y = Math.max(terrain.heightAt(deakin.x, deakin.z), terrain.WATER_LEVEL);

  const group = buildFountainMesh();
  group.visible = false;
  scene.add(group);

  // Soft water jet: glow sprites arcing off the finial while the fountain plays.
  const jetTex = makeGlowTexture("198,226,244");
  const jets: THREE.Sprite[] = [];
  for (let i = 0; i < 10; i++) {
    const s = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: jetTex, transparent: true, opacity: 0.6, depthWrite: false })
    );
    s.userData.seed = i / 10;
    s.userData.angle = (i / 10) * Math.PI * 2;
    group.add(s);
    jets.push(s);
  }

  let phase: FountainPhase = "hidden";
  let playing = false;

  function setPhase(next: Exclude<FountainPhase, "hidden">): void {
    phase = next;
    playing = next !== "still";
    group.visible = true;
    group.position.copy(next === "memorial" ? deakin : rioVista);
    const d = FACTS[next];
    group.traverse((o) => {
      o.userData.landmark = { name: d.name, fact: d.fact, year: d.year };
    });
    if (!flagTargets.includes(group)) flagTargets.push(group);
    if (!playing) for (const s of jets) s.visible = false;
  }

  return {
    update(_dt: number, t: number): void {
      const y = sim.year;
      const want: FountainPhase =
        y >= 1936 ? "memorial" : y >= 1897 ? "still" : y >= 1891 ? "playing" : "hidden";
      if (want !== phase && want !== "hidden") setPhase(want);
      if (!group.visible || !playing) return;
      for (const s of jets) {
        const ph = (t * 0.45 + (s.userData.seed as number)) % 1;
        const r = ph * 0.85;
        const a = (s.userData.angle as number) + t * 0.15;
        s.visible = true;
        s.position.set(
          Math.cos(a) * r,
          2.2 + ph * 1.15 - ph * ph * 1.45, // small parabolic arc
          Math.sin(a) * r
        );
        s.scale.setScalar(0.34 + ph * 0.5);
        (s.material as THREE.SpriteMaterial).opacity = 0.55 * (1 - ph * ph);
      }
    },
  };
}
