// M6-lite: the 1893 bank crash and the dried-fruit recovery, applied as a
// modifier AROUND sim.tick (docs/mildura-history.md §§6-7):
//   1893-1895 — banks shut: wool/capital income x0, population growth frozen,
//     and a deterministic ~5% chance per tick that a settler family walks off
//     the blocks (population -1, never below 8).
//   1896+     — dried fruit saves the settlement: the wool-line income
//     (wool + the capital it earns) is doubled.
// Wiring: installCrashEffects({ sim }) once at startup; it wraps sim.tick so
// main.ts's clock keeps calling sim.tick() unchanged. Losses (famine, spending)
// always stand — only the income side is modified. No save-format change:
// everything derives from sim.year, so old saves load untouched.
import { mulberry32 } from "../util/rng";
import type { Simulation } from "./state";

export const CRASH_START = 1893;
export const CRASH_END = 1895; // inclusive; recovery begins 1896
export const POPULATION_FLOOR = 8;

/** Post-tick modifier. Exported for reuse; installCrashEffects wires it. */
export function applyCrashEffects(
  sim: Simulation,
  before: { wool: number; capital: number; population: number }
): void {
  const r = sim.resources;
  const y = sim.year;
  if (y >= CRASH_START && y <= CRASH_END) {
    // Banks shut: no wool or capital income this tick (losses still stand).
    if (r.wool > before.wool) r.wool = before.wool;
    if (r.capital > before.capital) r.capital = before.capital;
    // No new arrivals while the colony teeters.
    if (r.population > before.population) r.population = before.population;
    // Deterministic per-year roll: ~5% chance a settler family leaves.
    const roll = mulberry32(((y * 0x9e3779b1) ^ 0x1893) >>> 0)();
    if (roll < 0.05 && r.population > POPULATION_FLOOR) r.population -= 1;
  } else if (y > CRASH_END) {
    // Dried-fruit recovery: double whatever the wool line earned this tick.
    r.wool += Math.max(0, r.wool - before.wool);
    r.capital += Math.max(0, r.capital - before.capital);
  }
}

export function installCrashEffects(opts: { sim: Simulation }): void {
  const { sim } = opts;
  const baseTick = sim.tick.bind(sim);
  sim.tick = () => {
    const yearBefore = sim.year;
    const before = {
      wool: sim.resources.wool,
      capital: sim.resources.capital,
      population: sim.resources.population,
    };
    baseTick();
    if (sim.year === yearBefore) return; // paused — the tick was a no-op
    applyCrashEffects(sim, before);
  };
}
