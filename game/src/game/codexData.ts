// Codex ("Settler's Almanac") entries — the stealth-learning layer. Every
// sentence is TRUE and drawn from docs/mildura-history.md; nothing invented,
// dates are sacred. Landmark entries reuse the hover facts from map/landmarks.
import { LANDMARKS } from "../map/landmarks";

export interface CodexEntry {
  key: string; // also the art filename stem where an image exists
  title: string;
  unlockYear: number; // sim.year >= unlockYear reveals the row
  year?: number; // historic date printed beside the title
  circa?: boolean; // prints "c. <year>"
  fact: string; // ONE true sentence
  img?: string; // art upgrade path, e.g. "buildings/<key>.jpg" (optional)
}

// Landmarks without an explicit year unlock with the era that puts them on
// the colony's map (irrigation survey 1889, soldier settlement 1921, &c.).
const LANDMARK_UNLOCKS: Record<string, number> = {
  township: 1887,
  wharf: 1892,
  kings_billabong: 1889,
  psyche_bend: 1890,
  nichols_point: 1889,
  ninety_foot: 1889,
  merbein: 1913,
  red_cliffs: 1921,
};

const LANDMARK_IMGS: Record<string, string> = {
  psyche_bend: "buildings/psyche_pumphouse.jpg",
  wharf: "buildings/paddle_steamer.jpg",
};

// Civic buildings, machines and river trade — see docs/mildura-history.md §§4-8
// and game/public/ASSET-MANIFEST.md for the matching art slots.
const BUILDINGS: CodexEntry[] = [
  {
    key: "paddle_steamer",
    title: "The Paddle Steamers",
    unlockYear: 1853,
    year: 1853,
    fact:
      "The Murray paddle-steamer trade opened in 1853, and at its peak some " +
      "150 vessels worked the river system — wool bales were the dominant cargo.",
    img: "buildings/paddle_steamer.jpg",
  },
  {
    key: "psyche_pumps",
    title: "The Psyche Bend Pumps",
    unlockYear: 1889,
    year: 1889,
    fact:
      "George Chaffey designed the pumps in 1889 around a 1,000-horsepower " +
      "Tangye triple-expansion steam engine, lifting Murray water about 28 m " +
      "in stages so gravity could feed 300 miles of channels.",
    img: "buildings/psyche_pumps.jpg",
  },
  {
    key: "grand_coffee_palace",
    title: "The Grand Coffee Palace",
    unlockYear: 1889,
    year: 1889,
    fact:
      "Tendered in 1889 for a dry settlement where pubs were barred, it poured " +
      "coffee until a wine licence arrived in 1915 — it is the Grand Hotel today.",
    img: "buildings/grand_coffee_palace.jpg",
  },
  {
    key: "langtree_hall",
    title: "Langtree Hall",
    unlockYear: 1889,
    year: 1889,
    fact:
      "Mildura's first public hall, built in 1889; the 1896 Royal Commission " +
      "into the Chaffey collapse sat here.",
    img: "buildings/langtree_hall.jpg",
  },
  {
    key: "rio_vista",
    title: "Rio Vista",
    unlockYear: 1891,
    year: 1891,
    circa: true,
    fact:
      "W.B. Chaffey's Queen Anne villa above the river, designed by architect " +
      "E.C. Sharland and completed about 1891 — 'Rio Vista' is Spanish for " +
      "'River View'.",
    img: "buildings/rio_vista.jpg",
  },
  {
    key: "travelling_fountain",
    title: "The Chaffey Fountain",
    unlockYear: 1891,
    year: 1891,
    fact:
      "It first played in the Rio Vista garden; Edward Chaffey, W.B.'s " +
      "youngest son, drowned in it in May 1897, and the stilled fountain was " +
      "moved to Deakin Avenue in 1936 as the King George V Memorial Fountain.",
    img: "buildings/travelling_fountain.jpg",
  },
  {
    key: "workingmans_club",
    title: "The Working Man's Club",
    unlockYear: 1894,
    year: 1894,
    fact:
      "Established 1894 on Deakin Avenue; its bar, rebuilt in 1970 at 91 " +
      "metres with 32 beer taps, was Guinness-recorded as the world's longest.",
    img: "buildings/workingmans_club.jpg",
  },
  {
    key: "mildura_club",
    title: "The Mildura Club",
    unlockYear: 1894,
    year: 1894,
    fact:
      "Founded 1894 as a gentlemen's club on the British model, with W.B. " +
      "Chaffey a leading figure; its purpose-built clubhouse opened in 1920.",
    img: "buildings/mildura_club.jpg",
  },
  {
    key: "settlers_club",
    title: "The Settlers Club",
    unlockYear: 1895,
    year: 1895,
    fact:
      "Licensed in 1895, the club served its first drinks on two boards " +
      "supported by a row of barrels.",
    img: "buildings/settlers_club.jpg",
  },
  {
    key: "carnegie_building",
    title: "The Carnegie Library",
    unlockYear: 1908,
    year: 1908,
    fact:
      "Opened 1908 with a £2,000 Andrew Carnegie grant — one of only four " +
      "Carnegie libraries in Australia; its tower was replaced by the " +
      "four-faced Memorial Clock Tower, dedicated 1921.",
    img: "buildings/carnegie_building.jpg",
  },
  {
    key: "big_lizzie",
    title: "Big Lizzie",
    unlockYear: 1920,
    year: 1920,
    circa: true,
    fact:
      "Frank Bottrill's giant oil-engined traction engine, built about " +
      "1915-17 on his patent 'Dreadnought' wheels, cleared the mallee for the " +
      "Red Cliffs soldier-settlement blocks.",
    img: "buildings/big_lizzie.jpg",
  },
  {
    key: "sacred_heart",
    title: "Sacred Heart Church",
    unlockYear: 1921,
    year: 1921,
    fact:
      "The Lombardic Romanesque church held its first Mass on 18 December " +
      "1921, and was renamed a Peace Memorial with the 1969 extensions.",
    img: "buildings/sacred_heart.jpg",
  },
];

export const CODEX_ENTRIES: CodexEntry[] = [
  ...LANDMARKS.map(
    (lm): CodexEntry => ({
      key: lm.key,
      title: lm.name,
      unlockYear: lm.year ?? LANDMARK_UNLOCKS[lm.key] ?? 1887,
      year: lm.year,
      fact: lm.fact,
      img: LANDMARK_IMGS[lm.key],
    })
  ),
  ...BUILDINGS,
].sort((a, b) => a.unlockYear - b.unlockYear || a.title.localeCompare(b.title));
