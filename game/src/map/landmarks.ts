// Real Mildura-district landmarks, placed by *fractional* grid position so they
// stay in their correct relative geography regardless of grid resolution.
// fx: 0 = west, 1 = east.  fy: 0 = north (river side), 1 = south (high terrace).
// Each carries one true "stealth-learning" fact (see docs/mildura-history.md).

export interface Landmark {
  key: string;
  name: string;
  fx: number;
  fy: number;
  year?: number;
  fact: string;
  onWater?: boolean; // forces a riverside/water placement when the map is built
}

export const LANDMARKS: Landmark[] = [
  {
    key: "township",
    name: "Mildura Township",
    fx: 0.5,
    fy: 0.34,
    year: 1887,
    fact: "Surveyed in 1887 on a wide-street American grid modelled on Ontario, California.",
  },
  {
    key: "wharf",
    name: "Mildura Wharf",
    fx: 0.5,
    fy: 0.17,
    year: 1892,
    fact: "Opened 1892; the river was the colony's only economic artery before the 1903 railway.",
    onWater: true,
  },
  {
    key: "kings_billabong",
    name: "Kings Billabong",
    fx: 0.63,
    fy: 0.23,
    fact: "A natural anabranch used as the irrigation system's main storage reservoir.",
    onWater: true,
  },
  {
    key: "psyche_bend",
    name: "Psyche Bend Pump Station",
    fx: 0.22,
    fy: 0.16,
    year: 1890,
    fact: "Its 1,000 hp Tangye steam engine lifted Murray water ~28 m so gravity could do the rest.",
    onWater: true,
  },
  {
    key: "nichols_point",
    name: "Nichols Point",
    fx: 0.71,
    fy: 0.27,
    fact: "Site of a further pumping station feeding the higher land east of the township.",
    onWater: true,
  },
  {
    key: "ninety_foot",
    name: "Ninety Foot",
    fx: 0.56,
    fy: 0.44,
    fact: "A re-lift station serving the highest blocks in the settlement.",
  },
  {
    key: "merbein",
    name: "Merbein",
    fx: 0.12,
    fy: 0.13,
    year: 1913,
    fact: "W.B. Chaffey established his winery and distillery here, ~8 km downriver.",
    onWater: true,
  },
  {
    key: "red_cliffs",
    name: "Red Cliffs",
    fx: 0.5,
    fy: 0.82,
    fact: "Named for the real red river cliffs to the south of Mildura.",
  },
];
