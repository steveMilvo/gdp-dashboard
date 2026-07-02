// M4 build catalog — the date-gated public works of Mildura. Every unlock year
// is verified against docs/mildura-history.md (dates are sacred):
//   1847 Jamieson run & homestead/woolshed · 1887 the Indenture (Chaffey HQ) ·
//   1889 Grand Coffee Palace tenders & Langtree Hall · 1891 Rio Vista completed ·
//   1892 wharf opens · 1894 Working Man's Club · 1908 Carnegie Free Library
//   (its tower replaced by the 1921 Memorial Clock Tower) · 1920 the Mildura
//   Club's purpose-built clubhouse opens · 1921 Sacred Heart first Mass.
// Each entry supplies a distinct cel-shaded silhouette from a box/cone/cylinder
// kit plus a canvas-drawn facade icon (no emoji).

import * as THREE from "three";
import { toonGradient } from "../render/world";

export interface BuildCost {
  timber: number;
  capital: number; // £
}

export interface CatalogEntry {
  key: string;
  name: string;
  year: number; // unlock year, per docs/mildura-history.md
  cost: BuildCost;
  blurb: string; // one-line period note for the palette tooltip
  footprint: { w: number; d: number }; // world units on the ground
  height: number; // rough eave/ridge height, used for the timber-frame stage
  build(): THREE.Group; // completed cel-shaded mesh
  icon(size?: number): HTMLCanvasElement; // ink silhouette for the palette
}

// --- cel-shaded kit ---------------------------------------------------------------
function mat(color: number): THREE.MeshToonMaterial {
  return new THREE.MeshToonMaterial({ gradientMap: toonGradient(), color });
}

function addBox(
  g: THREE.Group,
  w: number,
  h: number,
  d: number,
  color: number,
  x: number,
  y: number,
  z: number,
  ry = 0
): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color));
  m.position.set(x, y, z);
  m.rotation.y = ry;
  m.castShadow = true;
  m.receiveShadow = true;
  g.add(m);
  return m;
}

// Hip/pyramid roof: 4-sided cone, mock-up style (see buildHomestead).
function addHip(
  g: THREE.Group,
  w: number,
  h: number,
  d: number,
  color: number,
  x: number,
  y: number,
  z: number
): THREE.Mesh {
  // Bake the 45° turn into the geometry so the w/d scale stays axis-aligned
  // (mesh rotation would apply after scale and swing corners off-footprint).
  const geo = new THREE.ConeGeometry(0.72, h, 4);
  geo.rotateY(Math.PI / 4);
  const m = new THREE.Mesh(geo, mat(color));
  m.scale.set(w, 1, d);
  m.position.set(x, y, z);
  m.castShadow = true;
  g.add(m);
  return m;
}

// Gable roof: triangular prism, ridge along Z.
function gableGeo(w: number, h: number, d: number): THREE.BufferGeometry {
  const s = new THREE.Shape();
  s.moveTo(-w / 2, 0);
  s.lineTo(w / 2, 0);
  s.lineTo(0, h);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: d, bevelEnabled: false });
  geo.translate(0, 0, -d / 2);
  geo.computeVertexNormals();
  return geo;
}

function addGable(
  g: THREE.Group,
  w: number,
  h: number,
  d: number,
  color: number,
  x: number,
  y: number,
  z: number,
  ry = 0
): THREE.Mesh {
  const m = new THREE.Mesh(gableGeo(w, h, d), mat(color));
  m.position.set(x, y, z);
  m.rotation.y = ry;
  m.castShadow = true;
  g.add(m);
  return m;
}

function addCyl(
  g: THREE.Group,
  r0: number,
  r1: number,
  h: number,
  color: number,
  x: number,
  y: number,
  z: number,
  seg = 8
): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r0, h, seg), mat(color));
  m.position.set(x, y, z);
  m.castShadow = true;
  g.add(m);
  return m;
}

// Veranda: shallow awning slab on a row of slim posts along +Z.
function addVeranda(g: THREE.Group, w: number, d: number, yTop: number, z: number, color = 0x9c5a44): void {
  const awn = addBox(g, w, 0.12, d, color, 0, yTop, z + d / 2);
  awn.rotation.x = 0.14;
  const n = Math.max(3, Math.round(w / 2.2));
  for (let i = 0; i < n; i++) {
    const px = -w / 2 + 0.4 + (i / (n - 1)) * (w - 0.8);
    addCyl(g, 0.07, 0.07, yTop - 0.15, 0xefe3c2, px, (yTop - 0.15) / 2, z + d - 0.25, 6);
  }
}

// --- palette colours (parchment-friendly, flat cel tones) --------------------------
const TIMBER_WALL = 0xb8a37e;
const CREAM = 0xe3d7b4;
const BRICK = 0x9c4a38;
const CLUB_BRICK = 0xa9705a;
const STONE = 0xd9c9a2;
const IRON_GREY = 0x8d9499;
const ROOF_RED = 0x84493a;
const SLATE = 0x5a5f66;
const WHITE_TRIM = 0xefe9da;
const DARK_TIMBER = 0x6b4a33;

// --- mesh builders ------------------------------------------------------------------
function buildWoolshed(): THREE.Group {
  const g = new THREE.Group();
  addBox(g, 9, 2.2, 4.6, TIMBER_WALL, 0, 1.1, 0);
  addGable(g, 5.0, 1.4, 9.4, IRON_GREY, 0, 2.2, 0, Math.PI / 2);
  // skillion sorting wing + loading ramp
  addBox(g, 3.4, 1.6, 2.2, 0xa8926c, -2.4, 0.8, 3.2);
  const skil = addBox(g, 3.6, 0.1, 2.5, IRON_GREY, -2.4, 1.75, 3.2);
  skil.rotation.x = 0.18;
  const ramp = addBox(g, 1.6, 0.16, 2.4, DARK_TIMBER, 3.4, 0.5, 2.9);
  ramp.rotation.x = -0.32;
  // wool bales by the door
  addBox(g, 0.9, 0.7, 0.7, 0xe4d7b8, 4.0, 0.35, 1.4, 0.3);
  addBox(g, 0.9, 0.7, 0.7, 0xe4d7b8, 3.2, 0.35, 1.8, -0.2);
  return g;
}

function buildWharfWorks(): THREE.Group {
  const g = new THREE.Group();
  // decked river frontage on red gum piles, goods shed + hand crane (1892 kit)
  addBox(g, 8, 0.35, 4, 0x8a6b4a, 0, 1.1, 0);
  for (const [x, z] of [[-3.5, -1.5], [-3.5, 1.5], [0, -1.5], [0, 1.5], [3.5, -1.5], [3.5, 1.5]]) {
    addCyl(g, 0.18, 0.16, 2.4, 0x5d4632, x, 0.1, z, 6);
  }
  addBox(g, 3.4, 1.9, 2.4, TIMBER_WALL, -2.0, 2.2, -0.5);
  addGable(g, 2.6, 0.9, 3.6, IRON_GREY, -2.0, 3.15, -0.5, Math.PI / 2);
  // crane: mast + jib + hook
  addCyl(g, 0.14, 0.12, 3.2, DARK_TIMBER, 2.6, 2.85, 0.6, 6);
  const jib = addBox(g, 2.6, 0.14, 0.14, DARK_TIMBER, 3.6, 4.1, 0.6);
  jib.rotation.z = 0.35;
  addBox(g, 0.08, 1.1, 0.08, 0x3a3a42, 4.7, 3.7, 0.6);
  addBox(g, 0.9, 0.7, 0.7, 0xe4d7b8, 1.4, 1.63, -1.0, 0.4);
  return g;
}

function buildChaffeyHq(): THREE.Group {
  const g = new THREE.Group();
  // two-storey survey office with veranda and company flag
  addBox(g, 6, 4.6, 4.6, CREAM, 0, 2.3, 0);
  addHip(g, 4.6, 1.9, 3.6, ROOF_RED, 0, 5.5, 0);
  addVeranda(g, 6.4, 1.5, 2.4, 2.3);
  addBox(g, 6.4, 0.12, 1.5, ROOF_RED, 0, 4.45, 3.0); // upper balcony floor
  addBox(g, 0.5, 1.6, 0.5, 0xa88a70, 2.1, 6.4, -1.2); // chimney
  addCyl(g, 0.06, 0.05, 3.4, WHITE_TRIM, -2.5, 7.4, -1.6, 6); // flagpole
  addBox(g, 1.1, 0.6, 0.05, 0xd4af37, -1.9, 8.7, -1.6); // company standard
  return g;
}

function buildCoffeePalace(): THREE.Group {
  const g = new THREE.Group();
  // grand two-storey temperance palace: parapet front + corner tower
  addBox(g, 8, 5.4, 5.4, CREAM, 0, 2.7, 0);
  addHip(g, 6.6, 1.6, 4.2, SLATE, 0, 6.1, -0.4);
  addBox(g, 8.2, 1.1, 0.4, WHITE_TRIM, 0, 5.9, 2.6); // parapet
  addBox(g, 2.2, 7.2, 2.2, CREAM, 3.4, 3.6, 2.0); // corner tower
  addHip(g, 2.4, 1.8, 2.4, SLATE, 3.4, 8.1, 2.0);
  addVeranda(g, 8.2, 1.4, 3.1, 2.7, SLATE); // street awning
  addBox(g, 1.4, 2.0, 0.15, DARK_TIMBER, -1.2, 1.0, 2.75); // double doors
  return g;
}

function buildRioVista(): THREE.Group {
  const g = new THREE.Group();
  // W.B. Chaffey's Queen Anne villa: red brick, crossing gables, double veranda
  addBox(g, 7, 5.2, 5.6, BRICK, 0, 2.6, 0);
  addGable(g, 5.8, 2.2, 7.4, SLATE, 0, 5.2, 0, Math.PI / 2);
  addBox(g, 3.2, 5.6, 3.4, BRICK, -2.2, 2.8, 1.6); // gabled wing
  addGable(g, 3.6, 1.9, 3.6, SLATE, -2.2, 5.6, 1.6);
  addVeranda(g, 7.2, 1.4, 2.2, 2.8, WHITE_TRIM); // ground veranda
  addBox(g, 7.2, 0.12, 1.4, WHITE_TRIM, 0, 4.3, 3.5); // first-floor veranda
  addBox(g, 0.55, 2.2, 0.55, 0x7a3b2c, 2.4, 6.6, -1.6); // chimneys
  addBox(g, 0.55, 2.0, 0.55, 0x7a3b2c, -0.6, 6.9, -1.0);
  return g;
}

function buildWorkingMansClub(): THREE.Group {
  const g = new THREE.Group();
  // long single-storey club (the famous long bar lives inside)
  addBox(g, 9.5, 2.8, 5, CREAM, 0, 1.4, 0);
  addGable(g, 5.4, 1.3, 9.9, ROOF_RED, 0, 2.8, 0, Math.PI / 2);
  addVeranda(g, 9.9, 1.6, 2.6, 2.5, ROOF_RED); // full-length street awning
  addBox(g, 3.2, 0.7, 0.14, 0xd4af37, 0, 3.3, 2.6); // signboard
  addBox(g, 0.5, 1.5, 0.5, 0xa88a70, -3.6, 4.0, -1.4); // kitchen chimney
  return g;
}

function buildMilduraClub(): THREE.Group {
  const g = new THREE.Group();
  // symmetric two-storey brick clubhouse (opened 1920, cnr Deakin & Ninth)
  addBox(g, 7, 5.0, 5, CLUB_BRICK, 0, 2.5, 0);
  addHip(g, 6.0, 1.8, 4.2, SLATE, 0, 5.9, 0);
  // central portico: two columns + flat entablature
  addBox(g, 2.4, 0.5, 1.5, WHITE_TRIM, 0, 3.0, 3.0);
  addCyl(g, 0.14, 0.14, 2.7, WHITE_TRIM, -0.85, 1.35, 3.5, 8);
  addCyl(g, 0.14, 0.14, 2.7, WHITE_TRIM, 0.85, 1.35, 3.5, 8);
  addBox(g, 1.3, 2.1, 0.15, DARK_TIMBER, 0, 1.05, 2.55); // door
  addBox(g, 0.5, 1.7, 0.5, 0x84564a, 2.4, 6.2, -1.4);
  addBox(g, 0.5, 1.7, 0.5, 0x84564a, -2.4, 6.2, -1.4);
  return g;
}

// Anchor where the Carnegie tower (and its 1921 Memorial Clock Tower
// replacement) stands, in the building's local space.
export const CARNEGIE_TOWER_OFFSET = new THREE.Vector3(0, 0, -1.2);

function buildCarnegie(): THREE.Group {
  const g = new THREE.Group();
  // Carnegie Free Library (1908): classical stone hall, columned portico
  addBox(g, 6, 3.4, 5, STONE, 0, 1.7, 0);
  addGable(g, 5.2, 1.3, 6.4, ROOF_RED, 0, 3.4, 0, Math.PI / 2);
  // portico with pediment
  for (const px of [-1.8, -0.6, 0.6, 1.8]) {
    addCyl(g, 0.17, 0.15, 2.6, WHITE_TRIM, px, 1.5, 3.1, 8);
  }
  addBox(g, 4.6, 0.4, 1.6, STONE, 0, 3.0, 3.0);
  addGable(g, 4.6, 1.0, 1.6, ROOF_RED, 0, 3.2, 3.0);
  addBox(g, 4.8, 0.35, 5.6, 0xc4b28a, 0, 0.2, 0.6); // steps/plinth
  // the original 1908 tower — removed for the Memorial Clock Tower in 1921
  const tower = addBox(g, 1.5, 2.6, 1.5, STONE, CARNEGIE_TOWER_OFFSET.x, 4.3, CARNEGIE_TOWER_OFFSET.z);
  tower.name = "carnegie-tower-1908";
  const cap = addHip(g, 1.7, 1.0, 1.7, ROOF_RED, CARNEGIE_TOWER_OFFSET.x, 6.1, CARNEGIE_TOWER_OFFSET.z);
  cap.name = "carnegie-tower-1908";
  return g;
}

// Canvas-drawn clock face (ticks + hands frozen at a dignified ten past ten).
function clockFaceTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d")!;
  x.fillStyle = "#f0e6cb";
  x.beginPath();
  x.arc(32, 32, 30, 0, 7);
  x.fill();
  x.strokeStyle = "#2b2013";
  x.lineWidth = 3;
  x.stroke();
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    x.beginPath();
    x.moveTo(32 + Math.cos(a) * 24, 32 + Math.sin(a) * 24);
    x.lineTo(32 + Math.cos(a) * 27, 32 + Math.sin(a) * 27);
    x.stroke();
  }
  x.lineWidth = 3.5;
  x.beginPath();
  x.moveTo(32, 32);
  x.lineTo(32 + 13, 32 - 9); // ten past
  x.moveTo(32, 32);
  x.lineTo(32 - 10, 32 - 12); // ten to eleven-ish hour hand
  x.stroke();
  return new THREE.CanvasTexture(c);
}

/** The 1921 WWI Memorial Clock Tower — replaces the Carnegie building's
 *  original tower on the same spot (docs/mildura-history.md §Carnegie). */
export function buildClockTower(): THREE.Group {
  const g = new THREE.Group();
  addBox(g, 1.7, 6.4, 1.7, STONE, 0, 3.2, 0);
  addBox(g, 2.1, 0.5, 2.1, 0xc4b28a, 0, 0.25, 0); // memorial plinth
  addBox(g, 2.0, 0.35, 2.0, WHITE_TRIM, 0, 6.55, 0); // cornice
  addHip(g, 1.6, 1.2, 1.6, 0x6d7a4a, 0, 7.35, 0); // weathered copper cap
  const face = clockFaceTexture();
  const faceMat = new THREE.MeshBasicMaterial({ map: face });
  const faceGeo = new THREE.PlaneGeometry(1.15, 1.15);
  for (let i = 0; i < 4; i++) {
    const f = new THREE.Mesh(faceGeo, faceMat);
    const a = (i / 4) * Math.PI * 2;
    f.position.set(Math.sin(a) * 0.87, 5.7, Math.cos(a) * 0.87);
    f.rotation.y = a;
    g.add(f);
  }
  return g;
}

function buildSacredHeart(): THREE.Group {
  const g = new THREE.Group();
  // Sacred Heart (Peace Memorial) Church — first Mass 18 December 1921
  addBox(g, 4.6, 3.6, 8, 0xc9b28a, 0, 1.8, -0.6);
  addGable(g, 5.0, 2.6, 8.4, ROOF_RED, 0, 3.6, -0.6);
  addBox(g, 2.0, 6.6, 2.0, 0xc9b28a, -2.6, 3.3, 2.6); // bell tower
  addHip(g, 1.9, 2.4, 1.9, ROOF_RED, -2.6, 7.7, 2.6); // spire
  addBox(g, 0.1, 1.0, 0.1, 0xd4af37, -2.6, 9.4, 2.6); // cross
  addBox(g, 0.55, 0.1, 0.1, 0xd4af37, -2.6, 9.5, 2.6);
  addBox(g, 1.3, 2.3, 0.15, DARK_TIMBER, 0.4, 1.15, 3.35); // west door
  addGable(g, 1.6, 0.6, 0.3, 0xc9b28a, 0.4, 2.35, 3.35); // door hood
  return g;
}

function buildLangtreeHall(): THREE.Group {
  const g = new THREE.Group();
  // Mildura's first public hall (1889) — plain gable with a proud parapet front
  addBox(g, 6.6, 3.0, 4.6, TIMBER_WALL, 0, 1.5, 0);
  addGable(g, 5.0, 1.5, 6.8, IRON_GREY, 0, 3.0, 0, Math.PI / 2);
  addBox(g, 5.2, 1.4, 0.35, CREAM, 0, 3.4, 2.3); // parapet facade
  addBox(g, 1.9, 0.6, 0.4, CREAM, 0, 4.35, 2.3); // parapet crown
  addBox(g, 1.4, 2.2, 0.15, DARK_TIMBER, 0, 1.1, 2.35); // hall doors
  addBox(g, 0.5, 1.4, 0.5, 0xa88a70, 2.3, 4.0, -1.3);
  return g;
}

// --- ink silhouette icons (canvas only — headless fonts lack emoji) ----------------
type Painter = (x: CanvasRenderingContext2D) => void;

const INK = "#3a2a14";

// Painters draw in a 24x24 space, ground line at y=21.
const ICON_PAINTERS: Record<string, Painter> = {
  woolshed(x) {
    x.fillRect(3, 13, 18, 8);
    x.beginPath();
    x.moveTo(2, 13);
    x.lineTo(12, 8);
    x.lineTo(22, 13);
    x.closePath();
    x.fill();
    x.clearRect(10.5, 16, 3, 5); // sliding door
  },
  wharf(x) {
    x.fillRect(2, 15, 20, 2); // deck
    x.fillRect(4, 17, 1.6, 4);
    x.fillRect(11, 17, 1.6, 4);
    x.fillRect(18, 17, 1.6, 4); // piles
    x.fillRect(6, 9, 5, 6); // goods shed
    x.beginPath();
    x.moveTo(5, 9);
    x.lineTo(8.5, 6);
    x.lineTo(12, 9);
    x.closePath();
    x.fill();
    x.fillRect(16, 6, 1.4, 9); // crane mast
    x.save();
    x.translate(16.7, 7);
    x.rotate(-0.5);
    x.fillRect(0, 0, 6, 1.2); // jib
    x.restore();
    x.fillRect(20.6, 8.4, 0.9, 3.4); // hook line
  },
  chaffey_hq(x) {
    x.fillRect(5, 8, 13, 13);
    x.beginPath();
    x.moveTo(4, 8);
    x.lineTo(11.5, 3.5);
    x.lineTo(19, 8);
    x.closePath();
    x.fill();
    x.fillRect(3, 13.6, 17, 1.2); // veranda line
    x.fillRect(20, 2, 1, 10); // flagpole
    x.beginPath();
    x.moveTo(21, 2);
    x.lineTo(21, 5);
    x.lineTo(24, 3.5);
    x.closePath();
    x.fill();
    x.clearRect(10.5, 16.5, 3, 4.5);
  },
  coffee_palace(x) {
    x.fillRect(3, 9, 15, 12);
    for (let i = 0; i < 5; i++) x.fillRect(3 + i * 3.2, 7.4, 2, 1.8); // parapet teeth
    x.fillRect(17, 4, 5, 17); // corner tower
    x.beginPath();
    x.moveTo(16.4, 4);
    x.lineTo(19.5, 1);
    x.lineTo(22.6, 4);
    x.closePath();
    x.fill();
    x.fillRect(2, 14.4, 16, 1.2); // awning
    x.clearRect(6, 16.8, 2.6, 4.2);
  },
  rio_vista(x) {
    x.fillRect(4, 11, 16, 10);
    x.beginPath();
    x.moveTo(3, 11);
    x.lineTo(9, 5);
    x.lineTo(15, 11);
    x.closePath();
    x.fill(); // main gable
    x.beginPath();
    x.moveTo(12, 11);
    x.lineTo(17, 6.5);
    x.lineTo(22, 11);
    x.closePath();
    x.fill(); // wing gable
    x.fillRect(18.6, 2.4, 1.8, 5); // chimney
    x.fillRect(3, 15.2, 18, 1); // double veranda rails
    x.fillRect(3, 18.2, 18, 1);
  },
  workingmans_club(x) {
    x.fillRect(2, 12, 20, 9);
    x.beginPath();
    x.moveTo(1, 12);
    x.lineTo(12, 7.5);
    x.lineTo(23, 12);
    x.closePath();
    x.fill();
    x.fillRect(1, 15, 22, 1.2); // long awning
    x.fillRect(4, 16.2, 1, 4.8);
    x.fillRect(11.5, 16.2, 1, 4.8);
    x.fillRect(19, 16.2, 1, 4.8); // posts
    x.clearRect(6.6, 17, 2.4, 4);
  },
  mildura_club(x) {
    x.fillRect(4, 9, 16, 12);
    x.beginPath();
    x.moveTo(3, 9);
    x.lineTo(7, 5);
    x.lineTo(17, 5);
    x.lineTo(21, 9);
    x.closePath();
    x.fill(); // hipped roof
    x.fillRect(9, 12.5, 6, 1.2); // portico beam
    x.fillRect(9.6, 13.7, 1.1, 7.3);
    x.fillRect(13.3, 13.7, 1.1, 7.3); // columns
    x.clearRect(11.1, 15.5, 1.8, 5.5);
  },
  carnegie(x) {
    x.fillRect(4, 12, 16, 9);
    x.beginPath();
    x.moveTo(3, 12);
    x.lineTo(12, 7);
    x.lineTo(21, 12);
    x.closePath();
    x.fill(); // pediment
    x.fillRect(9.4, 2.4, 5.2, 5); // tower (clock from 1921)
    x.beginPath();
    x.arc(12, 4.9, 1.5, 0, 7);
    x.fill();
    x.clearRect(6.4, 14, 1.4, 7);
    x.clearRect(9.4, 14, 1.4, 7);
    x.clearRect(13.2, 14, 1.4, 7);
    x.clearRect(16.2, 14, 1.4, 7); // column gaps
  },
  sacred_heart(x) {
    x.fillRect(8, 11, 14, 10);
    x.beginPath();
    x.moveTo(7, 11);
    x.lineTo(15, 4.5);
    x.lineTo(23, 11);
    x.closePath();
    x.fill(); // steep nave gable
    x.fillRect(2.4, 7, 4.6, 14); // tower
    x.beginPath();
    x.moveTo(1.8, 7);
    x.lineTo(4.7, 2.6);
    x.lineTo(7.6, 7);
    x.closePath();
    x.fill(); // spire
    x.fillRect(4.2, 0.2, 1, 2.6);
    x.fillRect(3.4, 0.9, 2.6, 1); // cross
    x.clearRect(13.6, 15.5, 2.8, 5.5);
  },
  langtree_hall(x) {
    x.fillRect(4, 10, 16, 11);
    x.fillRect(8, 7, 8, 3); // parapet crown
    x.beginPath();
    x.moveTo(3, 10);
    x.lineTo(12, 6);
    x.lineTo(21, 10);
    x.closePath();
    x.fill();
    x.clearRect(10.4, 14.5, 3.2, 6.5);
    x.clearRect(6, 12.5, 2, 3);
    x.clearRect(16, 12.5, 2, 3); // windows
  },
};

function makeIcon(key: string): (size?: number) => HTMLCanvasElement {
  return (size = 40) => {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const x = c.getContext("2d")!;
    x.scale(size / 24, size / 24);
    x.fillStyle = INK;
    ICON_PAINTERS[key](x);
    return c;
  };
}

function entry(
  key: string,
  name: string,
  year: number,
  timber: number,
  capital: number,
  blurb: string,
  footprint: { w: number; d: number },
  height: number,
  build: () => THREE.Group
): CatalogEntry {
  return { key, name, year, cost: { timber, capital }, blurb, footprint, height, build, icon: makeIcon(key) };
}

// Order: chronological — the palette reads like the town growing up.
export const BUILD_CATALOG: CatalogEntry[] = [
  entry("woolshed", "Woolshed", 1847, 20, 0,
    "The Jamiesons' Yerre Yerre run turns to sheep — wool by barge.", { w: 10, d: 7 }, 3.6, buildWoolshed),
  entry("chaffey_hq", "Chaffey HQ", 1887, 25, 30,
    "The Indenture is signed; the township grid is surveyed at once.", { w: 8, d: 7 }, 5.5, buildChaffeyHq),
  entry("coffee_palace", "Grand Coffee Palace", 1889, 30, 60,
    "Tenders let 1889 — the temperance colony's grandest address.", { w: 9.5, d: 7 }, 6.5, buildCoffeePalace),
  entry("langtree_hall", "Langtree Hall", 1889, 15, 15,
    "Mildura's first public hall; hosts the 1896 Royal Commission.", { w: 8, d: 6.5 }, 4.5, buildLangtreeHall),
  entry("rio_vista", "Rio Vista", 1891, 40, 80,
    "W.B. Chaffey's Queen Anne villa — 'the river view'.", { w: 9, d: 8 }, 6.4, buildRioVista),
  entry("wharf", "River Wharf", 1892, 30, 20,
    "Opened 1892; extended 1899 with three berthing levels.", { w: 9.5, d: 6 }, 4.2, buildWharfWorks),
  entry("workingmans_club", "Working Man's Club", 1894, 25, 40,
    "Est. 1894 on Deakin Avenue — later home of the world's longest bar.", { w: 10.5, d: 7 }, 4.1, buildWorkingMansClub),
  entry("carnegie", "Carnegie Library", 1908, 20, 40,
    "£2,000 Carnegie grant; its tower gives way to the Memorial Clock Tower in 1921.", { w: 8, d: 8 }, 4.7, buildCarnegie),
  entry("mildura_club", "Mildura Club", 1920, 25, 50,
    "The 1894 club's purpose-built clubhouse opens on Deakin Avenue, 1920.", { w: 8.5, d: 7 }, 6.0, buildMilduraClub),
  entry("sacred_heart", "Sacred Heart Church", 1921, 30, 50,
    "The Peace Memorial church — first Mass 18 December 1921.", { w: 8, d: 10 }, 6.2, buildSacredHeart),
];

export const CATALOG_BY_KEY: Record<string, CatalogEntry> = Object.fromEntries(
  BUILD_CATALOG.map((e) => [e.key, e])
);
