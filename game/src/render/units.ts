// Animated units: settlers (select / order / walk / idle) and grazing sheep.
// Selection is the mock-up's pulsing green double ring.
import * as THREE from "three";
import type { Terrain } from "./world";
import { mulberry32 } from "../util/rng";

const SETTLER_NAMES = ["Tom", "Ada", "Jack", "Mary", "Sam", "Nell"];
const SHIRT_COLOURS = [0x51617a, 0x7a5a41, 0x5d7048, 0x8a4a3a, 0x4a6b70, 0x6b5a7a];

export interface Settler {
  group: THREE.Group;
  name: string;
  target: THREE.Vector3 | null;
  phase: number;
  legL: THREE.Mesh;
  legR: THREE.Mesh;
  armL: THREE.Mesh;
  armR: THREE.Mesh;
  body: THREE.Mesh;
}

function makeRing(r: number): THREE.Mesh {
  const m = new THREE.Mesh(
    new THREE.RingGeometry(r * 0.82, r, 32),
    new THREE.MeshBasicMaterial({
      color: 0x35e04a,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
  );
  m.rotation.x = -Math.PI / 2;
  return m;
}

function makeSettler(i: number, rand: () => number): Settler {
  const g = new THREE.Group();
  const shirt = new THREE.MeshStandardMaterial({ color: SHIRT_COLOURS[i % SHIRT_COLOURS.length], roughness: 0.85 });
  const trouser = new THREE.MeshStandardMaterial({ color: 0x3d3a33, roughness: 0.9 });
  const skin = new THREE.MeshStandardMaterial({ color: 0xd9a679, roughness: 0.7 });
  const hat = new THREE.MeshStandardMaterial({ color: 0x8a713f, roughness: 0.9 });

  const legGeo = new THREE.BoxGeometry(0.16, 0.5, 0.16);
  legGeo.translate(0, -0.25, 0);
  const legL = new THREE.Mesh(legGeo, trouser);
  legL.position.set(0.11, 0.5, 0);
  const legR = new THREE.Mesh(legGeo.clone(), trouser);
  legR.position.set(-0.11, 0.5, 0);

  const body = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.55, 0.26), shirt);
  body.position.y = 0.78;

  const armGeo = new THREE.BoxGeometry(0.11, 0.46, 0.11);
  armGeo.translate(0, -0.2, 0);
  const armL = new THREE.Mesh(armGeo, shirt);
  armL.position.set(0.28, 1.0, 0);
  const armR = new THREE.Mesh(armGeo.clone(), shirt);
  armR.position.set(-0.28, 1.0, 0);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 10, 8), skin);
  head.position.y = 1.22;
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.035, 12), hat);
  brim.position.y = 1.33;
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.16, 0.14, 10), hat);
  crown.position.y = 1.4;

  for (const m of [legL, legR, body, armL, armR, head, brim, crown]) {
    m.castShadow = true;
    g.add(m);
  }
  g.scale.setScalar(1.35);
  g.rotation.y = rand() * Math.PI * 2;
  g.traverse((o) => (o.userData.unitIndex = i));
  return { group: g, name: SETTLER_NAMES[i % SETTLER_NAMES.length], target: null, phase: rand() * 7, legL, legR, armL, armR, body };
}

interface Sheep {
  group: THREE.Group;
  head: THREE.Mesh;
  target: THREE.Vector3 | null;
  grazeUntil: number;
  phase: number;
}

function makeSheep(rand: () => number): Sheep {
  const g = new THREE.Group();
  const woolMat = new THREE.MeshStandardMaterial({ color: 0xe8e0cd, roughness: 1 });
  const darkMat = new THREE.MeshStandardMaterial({ color: 0x4a4038, roughness: 0.9 });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 8), woolMat);
  body.scale.set(1, 0.75, 1.35);
  body.position.y = 0.55;
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.26, 0.34), darkMat);
  head.position.set(0, 0.62, 0.72);
  const legGeo = new THREE.CylinderGeometry(0.05, 0.05, 0.35, 5);
  for (const [sx, sz] of [[0.22, 0.42], [-0.22, 0.42], [0.22, -0.42], [-0.22, -0.42]]) {
    const leg = new THREE.Mesh(legGeo, darkMat);
    leg.position.set(sx, 0.18, sz);
    g.add(leg);
  }
  body.castShadow = true;
  g.add(body, head);
  g.rotation.y = rand() * Math.PI * 2;
  g.scale.setScalar(0.85 + rand() * 0.3);
  return { group: g, head, target: null, grazeUntil: rand() * 4, phase: rand() * 9 };
}

export class UnitManager {
  settlers: Settler[] = [];
  sheep: Sheep[] = [];
  selected: Settler | null = null;
  private ringInner = makeRing(0.85);
  private ringOuter = makeRing(1.2);
  private flourishes: { mesh: THREE.Mesh; born: number }[] = [];
  private scene: THREE.Scene;
  private terrain: Terrain;
  private rand = mulberry32(4242);
  private homeX: number;
  private homeZ: number;

  constructor(scene: THREE.Scene, terrain: Terrain, homeX: number, homeZ: number) {
    this.scene = scene;
    this.terrain = terrain;
    this.homeX = homeX;
    this.homeZ = homeZ;
    for (let i = 0; i < 6; i++) {
      const s = makeSettler(i, this.rand);
      const a = (i / 6) * Math.PI * 2;
      const x = homeX + Math.cos(a) * (4 + this.rand() * 4);
      const z = homeZ + Math.sin(a) * (4 + this.rand() * 4);
      s.group.position.set(x, terrain.heightAt(x, z), z);
      scene.add(s.group);
      this.settlers.push(s);
    }
    for (let i = 0; i < 22; i++) {
      const sh = makeSheep(this.rand);
      const x = homeX - 6 + (this.rand() - 0.5) * 26;
      const z = homeZ + 8 + (this.rand() - 0.5) * 18;
      sh.group.position.set(x, terrain.heightAt(x, z), z);
      scene.add(sh.group);
      this.sheep.push(sh);
    }
    this.ringInner.visible = this.ringOuter.visible = false;
    scene.add(this.ringInner, this.ringOuter);
  }

  pick(raycaster: THREE.Raycaster): Settler | null {
    const hits = raycaster.intersectObjects(this.settlers.map((s) => s.group), true);
    if (!hits.length) return null;
    const idx = hits[0].object.userData.unitIndex as number;
    return this.settlers[idx] ?? null;
  }

  select(s: Settler | null) {
    this.selected = s;
    this.ringInner.visible = this.ringOuter.visible = !!s;
  }

  order(s: Settler, x: number, z: number, now: number) {
    s.target = new THREE.Vector3(x, 0, z);
    const f = makeRing(1.0);
    f.position.set(x, this.terrain.heightAt(x, z) + 0.08, z);
    (f.material as THREE.MeshBasicMaterial).color.setHex(0x7fff8a);
    this.scene.add(f);
    this.flourishes.push({ mesh: f, born: now });
  }

  update(dt: number, t: number) {
    for (const s of this.settlers) {
      const g = s.group;
      if (s.target) {
        const dx = s.target.x - g.position.x;
        const dz = s.target.z - g.position.z;
        const d = Math.hypot(dx, dz);
        if (d < 0.3) {
          s.target = null;
        } else {
          const sp = Math.min(d, 3.2 * dt);
          g.position.x += (dx / d) * sp;
          g.position.z += (dz / d) * sp;
          g.rotation.y = Math.atan2(dx, dz);
          const sw = Math.sin(t * 9 + s.phase) * 0.65;
          s.legL.rotation.x = sw;
          s.legR.rotation.x = -sw;
          s.armL.rotation.x = -sw * 0.8;
          s.armR.rotation.x = sw * 0.8;
        }
      } else {
        // idle: settle limbs, weight-shift and a slow look-around
        s.legL.rotation.x *= 0.8;
        s.legR.rotation.x *= 0.8;
        s.armL.rotation.x = Math.sin(t * 1.7 + s.phase) * 0.06;
        s.armR.rotation.x = -Math.sin(t * 1.7 + s.phase) * 0.06;
        s.group.rotation.y += Math.sin(t * 0.4 + s.phase) * 0.0015;
        s.body.position.y = 0.78 + Math.sin(t * 2 + s.phase) * 0.012;
      }
      g.position.y = this.terrain.heightAt(g.position.x, g.position.z);
    }

    if (this.selected) {
      const p = this.selected.group.position;
      const pulse = 1 + Math.sin(t * 5) * 0.07;
      this.ringInner.position.set(p.x, p.y + 0.06, p.z);
      this.ringOuter.position.set(p.x, p.y + 0.05, p.z);
      this.ringInner.scale.setScalar(pulse);
      this.ringOuter.scale.setScalar(2 - pulse);
    }

    for (const sh of this.sheep) {
      sh.grazeUntil -= dt;
      if (sh.grazeUntil <= 0) {
        if (sh.target) {
          sh.target = null;
          sh.grazeUntil = 2 + this.rand() * 5;
        } else {
          const x = this.homeX - 6 + (this.rand() - 0.5) * 30;
          const z = this.homeZ + 8 + (this.rand() - 0.5) * 22;
          sh.target = new THREE.Vector3(x, 0, z);
          sh.grazeUntil = 4 + this.rand() * 4;
        }
      }
      if (sh.target) {
        const dx = sh.target.x - sh.group.position.x;
        const dz = sh.target.z - sh.group.position.z;
        const d = Math.hypot(dx, dz);
        if (d < 0.4) sh.target = null;
        else {
          sh.group.position.x += (dx / d) * 0.9 * dt;
          sh.group.position.z += (dz / d) * 0.9 * dt;
          sh.group.rotation.y = Math.atan2(dx, dz);
        }
        sh.head.rotation.x = 0;
      } else {
        sh.head.rotation.x = 0.7 + Math.sin(t * 1.2 + sh.phase) * 0.15; // head down, grazing
      }
      sh.group.position.y = this.terrain.heightAt(sh.group.position.x, sh.group.position.z);
    }

    this.flourishes = this.flourishes.filter((f) => {
      const age = t - f.born;
      if (age > 0.7) {
        this.scene.remove(f.mesh);
        return false;
      }
      f.mesh.scale.setScalar(1 + age * 2.4);
      (f.mesh.material as THREE.MeshBasicMaterial).opacity = 0.85 * (1 - age / 0.7);
      return true;
    });
  }
}
