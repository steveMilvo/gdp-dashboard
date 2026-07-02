# Asset manifest — where every painted image goes

Drop JPEGs into these folders on this branch and the game picks them up
automatically (live slots) or holds them for the milestone that wires them in
(codex/cards). No code changes needed. No text/frames in the images unless
noted — the game draws its own chrome.

## portraits/ — persona art (LIVE: status panel + milestone reveal cards)
3:4 portrait, ≥512×680.

| File | Subject |
| --- | --- |
| `latji.jpg` | Latji Latji Elder |
| `sturt.jpg` | Capt. Charles Sturt |
| `squatter.jpg` | Hugh Jamieson |
| `chaffey.jpg` | W.B. Chaffey |

## milestones/ — newspaper-banner vignettes (LIVE: shown inside the clipping)
Landscape 5:3, ~1000×600. Filename = milestone year.

| File | Subject |
| --- | --- |
| `1830.jpg` | Sturt's whaleboat on the river |
| `1847.jpg` | The squatter run (homestead, sheep, stockmen) |
| `1887.jpg` | Surveying the township grid |
| `1889.jpg` | Psyche Bend pumps lift the river (exterior with pipes works well) |
| `1891.jpg` | Rio Vista rises |
| `1893.jpg` | The Crash (crowd at the shuttered bank) |
| `1895.jpg` | The Fruit Republic (drying racks) |
| `1921.jpg` | Red Cliffs soldier settlement / irrigation opening ceremony |
| `1934.jpg` | Mildura proclaimed a city (1930s-40s street scene works well) |

## buildings/ — historic buildings, monuments, equipment (codex/build cards; slots land with the construction-menu milestone)
Square 1:1 preferred, ~600×600+. See ART-PROMPTS.md here for full prompts.

| File | Subject |
| --- | --- |
| `grand_coffee_palace.jpg` | Grand Coffee Palace (1889) |
| `mildura_club.jpg` | The Mildura Club (1920 clubhouse) |
| `settlers_club.jpg` | Settlers Club cottage (1895) |
| `workingmans_club.jpg` | Working Man's Club |
| `langtree_hall.jpg` | Langtree Hall (1889) |
| `carnegie_library.jpg` | Carnegie Free Library (1908, no clock tower) |
| `clock_tower.jpg` | Memorial Clock Tower (1921) |
| `sacred_heart.jpg` | Sacred Heart Church (1921 massing) |
| `chaffey_statue.jpg` | W.B. Chaffey statue |
| `cenotaph.jpg` | Cenotaph |
| `travelling_fountain.jpg` | The Chaffey fountain (Rio Vista garden) |
| `paddle_steamer.jpg` | Paddle steamer at the wharf |
| `psyche_pumps.jpg` | Psyche Bend engine room (interior — green Tangye, red flywheel) |
| `psyche_pumphouse.jpg` | Psyche Bend pump house (exterior, pipes discharging) |
| `channels_digging.jpg` | Blockie digging an irrigation channel |
| `chaffey_bros.jpg` | George & W.B. Chaffey over the colony map |
| `street_1948.jpg` | Langtree Avenue street scene, late 1940s |
| `big_lizzie.jpg` | Big Lizzie — Bottrill's mallee-clearing traction engine (Red Cliffs) |
| `rio_vista.jpg` | Rio Vista villa (portrait codex plate; landscape version → milestones/1891.jpg) |
| `langtree_hall_interior.jpg` | Langtree Hall interior (stage & pioneer curios; also suits an 1896 Royal Commission scene) |

Notes:
- The 1887 milestone banner can alternatively use `chaffey_bros.jpg` cropped
  to 5:3 if preferred over the surveying scene.
- Where art was generated with in-image text (signs, plaques), that's fine for
  codex plates but avoid it for milestone vignettes and portraits.
