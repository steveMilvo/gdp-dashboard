// Era gates — the age-up structure. History HOLDS at each gate year until the
// colony has earned the next chapter: the year clock freezes (the economy and
// your settlers keep working) while the objectives panel shows the live
// requirements. Meeting them releases the clock and the milestone fires.
// The clock also pauses while a newspaper banner is up so narration finishes.

import type { Simulation } from "./state";
import type { HudRefs } from "../ui/hud";

interface Requirement {
  label: string; // short imperative, e.g. "Stockpile timber"
  target: number;
  value(sim: Simulation): number;
}

interface Gate {
  beforeYear: number; // the clock holds at beforeYear - 1 until met
  title: string; // objectives panel heading while held
  hint: string; // one line of guidance
  reqs: Requirement[];
  done?: boolean;
}

function placedCount(sim: Simulation, keys?: string[]): number {
  if (!keys) return sim.placed.length;
  return sim.placed.filter((p) => keys.includes(p.key)).length;
}

// Requirements use only mechanics the player actually has at that point in
// history: chop/gather trips, wool passively accruing from the run, the
// build palette once its dates unlock, irrigation water after 1889.
const GATES: Gate[] = [
  {
    beforeYear: 1830,
    title: "River Country",
    hint: "Learn the river's living: fish, hunt and cut before the strangers come.",
    reqs: [
      { label: "Gather food stores", target: 60, value: (s) => s.resources.food },
      { label: "Cut red gum timber", target: 30, value: (s) => s.resources.timber },
    ],
  },
  {
    beforeYear: 1847,
    title: "Sturt's Passage",
    hint: "The maps are drawn; prove the country can carry people.",
    reqs: [
      { label: "Grow the camp", target: 14, value: (s) => s.resources.population },
      { label: "Food stores", target: 80, value: (s) => s.resources.food },
    ],
  },
  {
    beforeYear: 1887,
    title: "The Squatter Run",
    hint: "Wool pays for everything. Build the shed and fill the bale room.",
    reqs: [
      { label: "Raise the Woolshed", target: 1, value: (s) => placedCount(s, ["woolshed"]) },
      { label: "Bale up wool", target: 120, value: (s) => s.resources.wool },
      { label: "Bank capital £", target: 260, value: (s) => s.resources.capital },
    ],
  },
  {
    beforeYear: 1889,
    title: "The Indenture",
    hint: "The Chaffeys have signed. Give the colony a headquarters and the timber to build a dream.",
    reqs: [
      { label: "Build Chaffey HQ", target: 1, value: (s) => placedCount(s, ["chaffey_hq"]) },
      { label: "Timber stockpile", target: 40, value: (s) => s.resources.timber },
    ],
  },
  {
    beforeYear: 1893,
    title: "Water Uphill",
    hint: "The pumps are lifting the river. Grow the garden before the banks shake.",
    reqs: [
      { label: "Irrigation water", target: 20, value: (s) => s.resources.water },
      { label: "Public works standing", target: 2, value: (s) => placedCount(s) },
      { label: "Population", target: 18, value: (s) => s.resources.population },
    ],
  },
  // 1893-1895: the Crash arrives regardless — history's hammer, not a reward.
  {
    beforeYear: 1895,
    title: "The Crash",
    hint: "Hold the colony together. Keep them fed until the dried fruit pays.",
    reqs: [
      { label: "Population held", target: 12, value: (s) => s.resources.population },
      { label: "Food stores", target: 60, value: (s) => s.resources.food },
    ],
  },
  {
    beforeYear: 1921,
    title: "The Fruit Republic",
    hint: "Raisins by the ton. Build the town the blockies deserve.",
    reqs: [
      { label: "Public works standing", target: 4, value: (s) => placedCount(s) },
      { label: "Population", target: 26, value: (s) => s.resources.population },
    ],
  },
  {
    beforeYear: 1934,
    title: "Red Cliffs & After",
    hint: "The diggers are on their blocks. One last push makes Mildura a city.",
    reqs: [
      { label: "Public works standing", target: 6, value: (s) => placedCount(s) },
      { label: "Bank capital £", target: 400, value: (s) => s.resources.capital },
    ],
  },
];

export function installEras(opts: { sim: Simulation; hud: HudRefs }) {
  const { sim, hud } = opts;

  // Gates already satisfied by a restored save never re-hold.
  for (const g of GATES) if (sim.year >= g.beforeYear) g.done = true;

  let holding: Gate | null = null;
  let playerSpeed = sim.speed || 1; // remember QA/user overrides while we hold
  let victoryShown = sim.year >= 1934;

  function reqLine(r: Requirement): string {
    const v = Math.min(r.value(sim), r.target);
    const done = v >= r.target;
    return `<div class="obj-req${done ? " done" : ""}">${done ? "&#10003;" : "&#8226;"} ${r.label} <b>${v}/${r.target}</b></div>`;
  }

  function renderObjectives(g: Gate) {
    hud.setObjectives(
      `<div class="obj-gate"><b>${g.title}, ${sim.year}</b> — history waits.</div>` +
        `<div class="obj-hint">${g.hint}</div>` +
        g.reqs.map(reqLine).join("")
    );
  }

  /** Call once per sim-clock interval, BEFORE sim.tick(). */
  function applyClock() {
    // Narration/banners always get room to breathe.
    if (hud.toastActive()) {
      if (sim.speed !== 0) playerSpeed = sim.speed;
      sim.speed = 0;
      return;
    }

    const gate = GATES.find((g) => !g.done);
    if (!gate) {
      sim.speed = sim.speed === 0 ? playerSpeed : sim.speed;
      if (!victoryShown && sim.year >= 1934) {
        victoryShown = true;
        hud.showMilestone({
          year: 1934,
          title: "A CITY ON THE MURRAY",
          body:
            "From river country to proclaimed city in a lifetime — pumps, vines, " +
            "clubs and clock towers. The colony is yours, and it endures.",
          build: "Sandbox unlocked — the years are yours",
        });
      }
      hud.setObjectives(null);
      return;
    }

    const atGate = sim.year >= gate.beforeYear - 1;
    const met = gate.reqs.every((r) => r.value(sim) >= r.target);

    if (atGate && !met) {
      // Hold the year; the economy still ticks (speed 0 advances everything
      // in sim.tick except the year itself) and settlers keep working.
      if (sim.speed !== 0) playerSpeed = sim.speed;
      sim.speed = 0;
      holding = gate;
      renderObjectives(gate);
      return;
    }

    if (met && (atGate || holding === gate)) {
      gate.done = true;
      holding = null;
      sim.speed = playerSpeed || 1;
      hud.setObjectives(null);
      hud.flashAction("survey");
      return;
    }

    // Approaching the gate: show what's coming so the player can prepare —
    // and make sure the clock is running again after any banner/hold froze it.
    if (sim.speed === 0) sim.speed = playerSpeed || 1;
    holding = null;
    renderObjectives(gate);
  }

  return { applyClock, GATES };
}
