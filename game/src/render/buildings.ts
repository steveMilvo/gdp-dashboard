// Squatter-era structures: the homestead (veranda, chimney smoke), the timber
// wharf with wool bales, and banner-flag markers for the other landmarks.
import * as THREE from "three";
import type { Terrain } from "./world";
import { makeGlowTexture } from "./world";
import { LANDMARKS } from "../map/landmarks";
import type { GameMap } from "../map/mapData";

function box(w: number, h: number, d: number, color: number, rough = 0.85): THREE.Mesh {
  const m = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({ color, roughness: rough })
  );
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

function buildHomestead(): THREE.Group {
  const g = new THREE.Group();
  const walls = box(6.4, 2.6, 4.6, 0xd8c8a4);
  walls.position.y = 1.3;
  const roof = new THREE.Mesh(
    new THREE.ConeGeometry(4.8, 2.1, 4),
    new THREE.MeshStandardMaterial({ color: 0x84493a, roughness: 0.7, metalness: 0.15 })
  );
  roof.rotation.y = Math.PI / 4;
  roof.scale.set(1.18, 1, 0.9);
  roof.position.y = 3.6;
  roof.castShadow = true;
  // veranda: shallow awning on posts across the front
  const awn = box(7.4, 0.12, 1.8, 0x9c5a44, 0.7);
  awn.position.set(0, 2.35, 3.1);
  awn.rotation.x = 0.16;
  const postGeo = new THREE.CylinderGeometry(0.08, 0.08, 2.2, 6);
  const postMat = new THREE.MeshStandardMaterial({ color: 0xcfc2a0, roughness: 0.9 });
  for (const px of [-3.2, -1.1, 1.1, 3.2]) {
    const p = new THREE.Mesh(postGeo, postMat);
    p.position.set(px, 1.1, 3.85);
    p.castShadow = true;
    g.add(p);
  }
  const chimney = box(0.55, 1.8, 0.55, 0xa88a70);
  chimney.position.set(2.2, 4.0, -1.1);
  g.add(walls, roof, awn, chimney);
  return g;
}

function buildWharf(): THREE.Group {
  const g = new THREE.Group();
  const deck = box(7.5, 0.35, 3.4, 0x8a6b4a, 0.95);
  deck.position.y = 1.4;
  const pileGeo = new THREE.CylinderGeometry(0.16, 0.18, 2.6, 6);
  const pileMat = new THREE.MeshStandardMaterial({ color: 0x5d4632, roughness: 1 });
  for (const [x, z] of [[-3.2, -1.3], [-3.2, 1.3], [0, -1.3], [0, 1.3], [3.2, -1.3], [3.2, 1.3]]) {
    const p = new THREE.Mesh(pileGeo, pileMat);
    p.position.set(x, 0.2, z);
    g.add(p);
  }
  // wool bales stacked for the barge
  for (let i = 0; i < 5; i++) {
    const b = box(0.9, 0.7, 0.7, 0xe4d7b8, 1);
    b.position.set(-2.4 + (i % 3) * 1.1, 1.95 + Math.floor(i / 3) * 0.75, -0.6);
    b.rotation.y = (i * 0.4) % 0.5;
    g.add(b);
  }
  g.add(deck);
  return g;
}

export function buildSettlement(scene: THREE.Scene, map: GameMap, terrain: Terrain) {
  const townTile = map.landmarkTiles["township"] ?? map.landmarkTiles[Object.keys(map.landmarkTiles)[0]];
  const town = terrain.tileToWorld(townTile.x, townTile.y);
  const homeY = terrain.heightAt(town.x, town.z);

  const homestead = buildHomestead();
  homestead.position.set(town.x, homeY, town.z);
  scene.add(homestead);

  // Chimney smoke
  const smokeTex = makeGlowTexture("205,200,195");
  const smoke: THREE.Sprite[] = [];
  for (let i = 0; i < 9; i++) {
    const s = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: smokeTex, transparent: true, opacity: 0.5, depthWrite: false })
    );
    s.userData.seed = i / 9;
    scene.add(s);
    smoke.push(s);
  }
  const chimneyTop = new THREE.Vector3(town.x + 2.2, homeY + 5.0, town.z - 1.1);

  // Wharf at the wharf landmark (or on the river north of town)
  let wharfPos: THREE.Vector3;
  const wharfTile = map.landmarkTiles["wharf"];
  if (wharfTile) {
    const w = terrain.tileToWorld(wharfTile.x, wharfTile.y);
    wharfPos = new THREE.Vector3(w.x, terrain.WATER_LEVEL, w.z);
  } else {
    wharfPos = new THREE.Vector3(town.x, terrain.WATER_LEVEL, town.z - 20);
  }
  const wharf = buildWharf();
  wharf.position.copy(wharfPos);
  scene.add(wharf);

  // Banner flags on the remaining landmarks (raycast targets for hover facts)
  const flagTargets: THREE.Object3D[] = [];
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x6b5a42, roughness: 0.9 });
  const bannerMat = new THREE.MeshStandardMaterial({
    color: 0xd4af37,
    roughness: 0.55,
    side: THREE.DoubleSide,
  });
  const banners: THREE.Mesh[] = [];
  for (const lm of LANDMARKS) {
    const tile = map.landmarkTiles[lm.key];
    if (!tile) continue;
    const w = terrain.tileToWorld(tile.x, tile.y);
    const y = Math.max(terrain.heightAt(w.x, w.z), terrain.WATER_LEVEL);
    const g = new THREE.Group();
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 5.2, 6), poleMat);
    pole.position.y = 2.6;
    pole.castShadow = true;
    const banner = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 0.95), bannerMat);
    banner.position.set(0.88, 4.55, 0);
    banner.castShadow = true;
    banners.push(banner);
    g.add(pole, banner);
    g.position.set(w.x, y, w.z);
    g.traverse((o) => {
      o.userData.landmark = { name: lm.name, fact: lm.fact, year: lm.year };
    });
    scene.add(g);
    flagTargets.push(g);
  }

  return {
    homePos: new THREE.Vector3(town.x, homeY, town.z),
    flagTargets,
    update(t: number) {
      for (const s of smoke) {
        const ph = (t * 0.14 + (s.userData.seed as number)) % 1;
        s.position.set(
          chimneyTop.x + Math.sin(ph * 9) * 0.4 + ph * 1.6,
          chimneyTop.y + ph * 5.5,
          chimneyTop.z + Math.cos(ph * 7) * 0.3
        );
        s.scale.setScalar(0.7 + ph * 2.6);
        (s.material as THREE.SpriteMaterial).opacity = 0.42 * (1 - ph);
      }
      for (let i = 0; i < banners.length; i++) {
        banners[i].rotation.y = Math.sin(t * 2.2 + i * 1.7) * 0.18;
      }
    },
  };
}
