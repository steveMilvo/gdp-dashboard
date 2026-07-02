// Historical milestones — each fires once when the year clock reaches it,
// shows a period newspaper-clipping banner, promotes the special build it
// unlocks, switches the era persona, and is read by the narrator.
// Dates per docs/mildura-history.md.

export type PersonaKey = "latji" | "sturt" | "squatter" | "chaffey";

export interface Milestone {
  year: number;
  title: string; // headline on the clipping
  body: string; // printed text
  speech: string; // what the narrator says (period phrasing)
  build?: string; // "SPECIAL BUILD UNLOCKED" chip
  persona?: PersonaKey; // switches the status-panel persona
  tone?: "news" | "alarm";
}

export const MILESTONES: Milestone[] = [
  {
    year: 1830,
    title: "A Whaleboat on the Wide River",
    body:
      "Capt. Charles Sturt rows down the great river and names it the Murray. " +
      "On these banks the Latji Latji have fished and firestick-farmed for " +
      "countless generations.",
    speech:
      "Eighteen thirty. Captain Charles Sturt has come down the wide brown " +
      "river in a whaleboat, and given it the name Murray. Mind — the Latji " +
      "Latji people have known this bend, and fished it, since time out of mind.",
    build: "Explorer's Camp",
    persona: "sturt",
  },
  {
    year: 1847,
    title: "The Squatters Take Up 'Mildura'",
    body:
      "The Jamieson brothers claim the Mildura run — sheep on the saltbush, " +
      "wool down the river by barge.",
    speech:
      "Eighteen forty-seven. The Jamieson brothers have taken up the Mildura " +
      "run. It's sheep country now — saltbush and sweat — and the wool goes " +
      "down the river by barge.",
    build: "Homestead & Woolshed",
    persona: "squatter",
  },
  {
    year: 1887,
    title: "THE INDENTURE IS SIGNED!",
    body:
      "George & W.B. Chaffey sign with the Colony of Victoria: 250,000 acres " +
      "to make a garden of the desert. The township grid is surveyed at once.",
    speech:
      "Eighteen eighty-seven, and what a year! The Chaffey brothers, fresh " +
      "from California, have signed the Indenture — a quarter of a million " +
      "acres to turn red dust into a garden. They're pegging out the township " +
      "this very week.",
    build: "Chaffey HQ & Township Grid",
    persona: "chaffey",
  },
  {
    year: 1889,
    title: "WATER RUNS UPHILL AT PSYCHE BEND",
    body:
      "The great triple-expansion pumps lift the Murray to the high terrace. " +
      "Irrigation begins — every fruit block drinks from the river.",
    speech:
      "Eighteen eighty-nine. By steam and iron, the water runs uphill! The " +
      "pumps at Psyche Bend are lifting the Murray onto the terrace, and the " +
      "channels are running full. Plant your vines, ladies and gentlemen.",
    build: "Psyche Bend Pump Station",
  },
  {
    year: 1891,
    title: "Rio Vista Rises on the Riverbank",
    body:
      "W.B. Chaffey builds his grand Queen-Anne villa overlooking the river — " +
      "'Rio Vista', the river view.",
    speech:
      "Eighteen ninety-one. Mister W.B. Chaffey is building himself a fine " +
      "house above the river — Rio Vista, he calls it. All fretwork and fancy " +
      "brick. A palace at the end of the earth.",
    build: "Rio Vista",
  },
  {
    year: 1893,
    title: "THE BANKS HAVE FAILED",
    body:
      "The land boom bursts and the colony's banks close their doors. Money " +
      "is scarce, the river is low — hold fast.",
    speech:
      "Eighteen ninety-three. Hard news. The banks have shut their doors, the " +
      "boom has burst, and the river's running low into the bargain. Batten " +
      "down. Those who hold their nerve will see the other side.",
    tone: "alarm",
  },
  {
    year: 1895,
    title: "The Fruit Republic",
    body:
      "Dried fruit saves the settlement: raisins, sultanas and currants go to " +
      "market by rail and river. The blockies endure.",
    speech:
      "Eighteen ninety-five. And here's the salvation of the place: dried " +
      "fruit. Raisins and sultanas, off to market by the ton. The colony " +
      "lives — the Fruit Republic is born.",
    build: "Drying Racks & Packing Shed",
  },
];

export function personaForYear(year: number): PersonaKey {
  if (year >= 1887) return "chaffey";
  if (year >= 1847) return "squatter";
  if (year >= 1830) return "sturt";
  return "latji";
}
