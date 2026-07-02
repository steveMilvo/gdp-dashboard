// Minimal simulation for the M1 slice: a year clock, eras, and an illustrative
// early-economy resource model (fish + game for food, then livestock & wool).
// Buildings/water systems arrive in later milestones (see docs/build-prompt.md).

export interface Resources {
  food: number;
  water: number;
  timber: number;
  wool: number;
  capital: number; // £
  population: number;
}

export interface Era {
  name: string;
  startYear: number;
}

// Aligned to docs/mildura-history.md.
export const ERAS: Era[] = [
  { name: "River Country", startYear: 1820 },
  { name: "Sturt's Passage", startYear: 1830 },
  { name: "The Squatter Run", startYear: 1847 },
  { name: "The Indenture", startYear: 1887 },
  { name: "Water Uphill", startYear: 1889 },
  { name: "The Colony", startYear: 1893 },
  { name: "Crash", startYear: 1893 },
  { name: "The Fruit Republic", startYear: 1895 },
];

export function eraForYear(year: number): Era {
  let current = ERAS[0];
  for (const e of ERAS) if (year >= e.startYear) current = e;
  return current;
}

// M4 build menu: a building placed on the map (tile coords + the year it went up).
export interface PlacedBuildingSave {
  key: string; // catalog key (game/buildCatalog.ts)
  tx: number;
  ty: number;
  builtYear: number;
}

export interface SaveState {
  year: number;
  resources: Resources;
  placed?: PlacedBuildingSave[]; // M4 — optional so older saves still load
}

export class Simulation {
  year = 1829; // opens on Latji Latji river country, the year before Sturt

  paused = false;
  speed = 1; // years advanced per tick
  // Set by the M2 labour module (game/labour.ts): once player-directed
  // chop/gather loops exist, the post-1847 passive economy steps back so
  // worked trips are what feed and build the colony. Not persisted.
  labourRebalance = false;
  resources: Resources = {
    food: 40,
    water: 0,
    timber: 20,
    wool: 0,
    capital: 200,
    population: 12,
  };

  /** Advance one simulation step (called on a timer). */
  tick(): void {
    if (this.paused) return;
    this.year += this.speed;
    const r = this.resources;
    const era = eraForYear(this.year);

    // Early protein: river fishing + hunting kangaroo/emu. Before the squatter
    // economy, river country comfortably feeds its people (fish traps, mussels,
    // firestick-managed game) — the camp must not starve pre-1847.
    let food = 4 + Math.round(r.population * (this.year < 1847 ? 0.85 : 0.3));
    // Livestock & the wool-barge economy arrive with the squatter run.
    if (this.year >= 1847) {
      food += 6;
      r.wool += 3;
      r.capital += 2; // wool sent up/down river by barge
    }
    // Red gum timber harvested along the river. With the labour module active,
    // felling becomes player-directed from the squatter run: passive timber
    // stops and passive food is trimmed ~30% (pre-1847 river country untouched —
    // the Latji Latji camp stays self-sufficient).
    const rebalanced = this.labourRebalance && this.year >= 1847;
    if (!rebalanced) r.timber += 1;
    else food = Math.round(food * 0.7);

    r.food += food - r.population; // population eats
    r.food = Math.max(0, r.food);

    // Population grows on a food surplus, shrinks on famine.
    if (r.food > r.population * 2) r.population += 1;
    else if (r.food <= 0) r.population = Math.max(1, r.population - 1);

    // Irrigation (water as a resource) is unlocked from the Water Uphill era;
    // wired to the pump/channel system in a later milestone.
    if (era.name === "Water Uphill" || this.year >= 1890) r.water = Math.min(100, r.water + 1);
  }

  // M4: placed buildings ride the save; the build menu owns the meshes.
  placed: PlacedBuildingSave[] = [];

  load(s: SaveState): void {
    this.year = s.year;
    this.resources = { ...s.resources };
    this.placed = (s.placed ?? []).map((p) => ({ ...p })); // tolerate pre-M4 saves
  }

  snapshot(): SaveState {
    return { year: this.year, resources: { ...this.resources }, placed: this.placed.map((p) => ({ ...p })) };
  }
}

export const sim = new Simulation();
