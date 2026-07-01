// PLACEHOLDER map generator.
//
// This encodes Mildura's *real layout* — the Murray meandering across the north,
// Kings Billabong off the river, and the land rising ~28 m to the southern
// terrace — so the elevation puzzle (you must pump water uphill) is present and
// playable offline. It is a stand-in for the real Geoscience Australia ELVIS DEM
// + OpenStreetMap water vectors. See scripts/build-map.ts for the real pipeline
// that produces the same data structure from authentic geodata.

import { GRID_W, GRID_H, MAP_SEED } from "../config";
import { mulberry32, clamp } from "../util/rng";
import { LANDMARKS } from "./landmarks";

export type TileKind =
  | "river"
  | "billabong"
  | "redgum" // River Red Gum lining the water — the settlers' building timber
  | "floodplain"
  | "mallee"
  | "belah"
  | "terrace";

export interface Tile {
  x: number;
  y: number;
  elevation: number; // 0 (river level) .. 1 (high terrace)
  water: boolean;
  kind: TileKind;
}

export interface GameMap {
  width: number;
  height: number;
  tiles: Tile[];
  index(x: number, y: number): number;
  at(x: number, y: number): Tile;
  // landmark key -> integer tile coords
  landmarkTiles: Record<string, { x: number; y: number }>;
  source: "placeholder" | "real-dem";
}

// Fractional row of the river centre for a given east-west fraction (0..1).
function riverCentreFrac(xf: number): number {
  return 0.13 + 0.05 * Math.sin(xf * Math.PI * 2 * 1.3) + 0.02 * Math.sin(xf * 9.0);
}

export function generateMap(seed: number = MAP_SEED): GameMap {
  const rand = mulberry32(seed);
  const W = GRID_W;
  const H = GRID_H;
  const tiles: Tile[] = new Array(W * H);
  const index = (x: number, y: number) => y * W + x;

  // Light per-tile noise for texture.
  const noise = (x: number, y: number) =>
    0.5 + 0.5 * Math.sin(x * 0.6 + seed) * Math.cos(y * 0.5 - seed) + (rand() - 0.5) * 0.25;

  // Kings Billabong loop centre (from landmark fractions).
  const billa = LANDMARKS.find((l) => l.key === "kings_billabong")!;
  const billaX = billa.fx * (W - 1);
  const billaY = billa.fy * (H - 1);
  const billaR = Math.min(W, H) * 0.07;

  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const xf = x / (W - 1);
      const riverRow = riverCentreFrac(xf) * (H - 1);
      const distToRiver = Math.abs(y - riverRow);
      // Broad, readable channel (the mock-up's hero feature): ~3–5 tiles wide.
      const riverWidth = 3.2 + 1.8 * (0.5 + 0.5 * Math.sin(xf * 20));

      const dBilla = Math.hypot(x - billaX, y - billaY);
      const isBillabongRing = Math.abs(dBilla - billaR) < 1.3;

      let kind: TileKind;
      let water = false;
      let elevation: number;

      if (distToRiver < riverWidth) {
        kind = "river";
        water = true;
        elevation = 0;
      } else if (isBillabongRing) {
        kind = "billabong";
        water = true;
        elevation = 0.02;
      } else {
        // Land: rises from the river (north) to the southern terrace. Dry land
        // never dips below a small positive floor, so only the carved river /
        // billabong beds sit under the water surface.
        const rel = clamp((y - riverRow) / (H - 1), 0, 1);
        elevation = clamp(0.05 + rel * 1.1 + (noise(x, y) - 0.5) * 0.12, 0.04, 1);

        const nearWater = distToRiver < riverWidth + 2.2 || Math.abs(dBilla - billaR) < 2.6;
        if (nearWater) {
          kind = "redgum";
        } else if (elevation < 0.16) {
          kind = "floodplain";
        } else if (noise(x * 1.7, y * 1.3) > 0.74) {
          kind = "belah";
        } else if (elevation > 0.55 && noise(x * 0.4, y * 0.4) > 0.55) {
          kind = "terrace";
        } else {
          kind = "mallee";
        }
      }

      tiles[index(x, y)] = { x, y, elevation, water, kind };
    }
  }

  // Snap landmark fractions to integer tiles; nudge "onWater" ones to the river.
  const landmarkTiles: Record<string, { x: number; y: number }> = {};
  for (const lm of LANDMARKS) {
    let lx = Math.round(lm.fx * (W - 1));
    let ly = Math.round(lm.fy * (H - 1));
    if (lm.onWater) {
      // Walk north to the nearest river tile so pump/wharf sit on the water's edge.
      let best = ly;
      let bestDist = Infinity;
      for (let yy = 0; yy < H; yy++) {
        if (tiles[index(clamp(lx, 0, W - 1), yy)].kind === "river") {
          const d = Math.abs(yy - ly);
          if (d < bestDist) {
            bestDist = d;
            best = yy + 1; // sit just onshore
          }
        }
      }
      ly = clamp(best, 0, H - 1);
    }
    landmarkTiles[lm.key] = { x: clamp(lx, 0, W - 1), y: clamp(ly, 0, H - 1) };
  }

  return {
    width: W,
    height: H,
    tiles,
    index,
    at: (x, y) => tiles[index(x, y)],
    landmarkTiles,
    source: "placeholder",
  };
}

// Colour ramp per tile (returns a 0xRRGGBB int). Land is shaded by elevation to
// reveal relief, so the rise to the terrace reads visually.
export function tileColour(t: Tile): number {
  if (t.kind === "river") return 0x2d6a8e;
  if (t.kind === "billabong") return 0x3f87a6;

  const base: Record<Exclude<TileKind, "river" | "billabong">, [number, number, number]> = {
    redgum: [54, 84, 46],
    floodplain: [142, 130, 84],
    mallee: [108, 130, 78],
    belah: [120, 128, 110],
    terrace: [196, 170, 120],
  };
  const [r, g, b] = base[t.kind as Exclude<TileKind, "river" | "billabong">];
  const shade = 0.62 + 0.38 * t.elevation; // higher ground = brighter
  const rr = Math.round(r * shade);
  const gg = Math.round(g * shade);
  const bb = Math.round(b * shade);
  return (rr << 16) | (gg << 8) | bb;
}
