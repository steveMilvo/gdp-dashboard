// Procedurally *painted* canvas textures — brush-dab style so surfaces read as
// hand-painted game art (the mock-up look) rather than flat-shaded primitives.
// All deterministic (seeded) so every load paints the same world.
import * as THREE from "three";
import { mulberry32 } from "../util/rng";

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return [c, c.getContext("2d")!];
}

function wrap(c: HTMLCanvasElement): THREE.CanvasTexture {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// River red gum bark: pink-grey base, vertical ribbon strokes, pale shed patches.
export function barkTexture(): THREE.CanvasTexture {
  const [c, x] = canvas(128, 256);
  const rand = mulberry32(101);
  const g = x.createLinearGradient(0, 0, 128, 0);
  g.addColorStop(0, "#b09384");
  g.addColorStop(0.5, "#c9b3a2");
  g.addColorStop(1, "#a3887a");
  x.fillStyle = g;
  x.fillRect(0, 0, 128, 256);
  for (let i = 0; i < 110; i++) {
    const px = rand() * 128;
    const wl = 3 + rand() * 8;
    const len = 40 + rand() * 200;
    const py = rand() * 256 - 40;
    x.fillStyle = `rgba(${(90 + rand() * 110) | 0},${(70 + rand() * 80) | 0},${(60 + rand() * 70) | 0},${
      0.12 + rand() * 0.2
    })`;
    x.beginPath();
    x.ellipse(px, py + len / 2, wl / 2, len / 2, (rand() - 0.5) * 0.12, 0, 7);
    x.fill();
  }
  for (let i = 0; i < 26; i++) {
    x.fillStyle = `rgba(230,216,201,${0.14 + rand() * 0.22})`;
    x.beginPath();
    x.ellipse(rand() * 128, rand() * 256, 4 + rand() * 9, 16 + rand() * 42, (rand() - 0.5) * 0.2, 0, 7);
    x.fill();
  }
  // dark scars
  for (let i = 0; i < 10; i++) {
    x.fillStyle = `rgba(60,42,32,${0.2 + rand() * 0.25})`;
    x.beginPath();
    x.ellipse(rand() * 128, rand() * 256, 1.5 + rand() * 3, 8 + rand() * 22, (rand() - 0.5) * 0.3, 0, 7);
    x.fill();
  }
  return wrap(c);
}

// Eucalypt canopy: layered leaf dabs, deep shadow blotches, sunlit highlights.
export function leafTexture(): THREE.CanvasTexture {
  const [c, x] = canvas(256, 256);
  const rand = mulberry32(202);
  x.fillStyle = "#679a40";
  x.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 42; i++) {
    x.fillStyle = `rgba(30,62,20,${0.1 + rand() * 0.14})`;
    x.beginPath();
    x.ellipse(rand() * 256, rand() * 256, 20 + rand() * 42, 14 + rand() * 30, rand() * 3, 0, 7);
    x.fill();
  }
  for (let i = 0; i < 950; i++) {
    x.fillStyle = `hsla(${70 + rand() * 45},44%,${34 + rand() * 28}%,${0.45 + rand() * 0.5})`;
    x.beginPath();
    x.ellipse(rand() * 256, rand() * 256, 2.5 + rand() * 5, 1 + rand() * 2, rand() * Math.PI, 0, 7);
    x.fill();
  }
  for (let i = 0; i < 260; i++) {
    x.fillStyle = `hsla(${72 + rand() * 34},52%,${56 + rand() * 18}%,${0.35 + rand() * 0.4})`;
    x.beginPath();
    x.ellipse(rand() * 256, rand() * 256, 2 + rand() * 4, 1 + rand() * 1.6, rand() * Math.PI, 0, 7);
    x.fill();
  }
  return wrap(c);
}

// Ground mottle: near-white multiplier with soft dark/light dabs, so the
// terrain's vertex colours stay in charge but stop looking airbrushed.
export function groundTexture(): THREE.CanvasTexture {
  const [c, x] = canvas(256, 256);
  const rand = mulberry32(303);
  x.fillStyle = "#f4f2ea";
  x.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 520; i++) {
    x.fillStyle = `rgba(30,55,20,${0.04 + rand() * 0.08})`;
    x.beginPath();
    x.ellipse(rand() * 256, rand() * 256, 3 + rand() * 9, 2 + rand() * 5, rand() * 3, 0, 7);
    x.fill();
  }
  for (let i = 0; i < 320; i++) {
    x.fillStyle = `rgba(255,252,225,${0.05 + rand() * 0.09})`;
    x.beginPath();
    x.ellipse(rand() * 256, rand() * 256, 2.5 + rand() * 7, 1.5 + rand() * 4, rand() * 3, 0, 7);
    x.fill();
  }
  // faint brush strokes
  for (let i = 0; i < 90; i++) {
    x.strokeStyle = `rgba(60,80,35,${0.03 + rand() * 0.05})`;
    x.lineWidth = 1 + rand() * 2;
    x.beginPath();
    const px = rand() * 256, py = rand() * 256, a = rand() * Math.PI;
    x.moveTo(px, py);
    x.lineTo(px + Math.cos(a) * (8 + rand() * 18), py + Math.sin(a) * (4 + rand() * 8));
    x.stroke();
  }
  return wrap(c);
}

// Water: streaky current lines, mostly white so the material colour tints it.
export function waterTexture(): THREE.CanvasTexture {
  const [c, x] = canvas(256, 128);
  const rand = mulberry32(404);
  x.fillStyle = "#f2f6f8";
  x.fillRect(0, 0, 256, 128);
  for (let i = 0; i < 130; i++) {
    const py = rand() * 128;
    const len = 20 + rand() * 90;
    const px = rand() * 256;
    x.strokeStyle =
      rand() > 0.45
        ? `rgba(255,255,255,${0.10 + rand() * 0.2})`
        : `rgba(120,160,190,${0.08 + rand() * 0.14})`;
    x.lineWidth = 1 + rand() * 2.4;
    x.beginPath();
    x.moveTo(px, py);
    x.bezierCurveTo(px + len * 0.3, py - 2 - rand() * 3, px + len * 0.7, py + 2 + rand() * 3, px + len, py);
    x.stroke();
  }
  return wrap(c);
}
