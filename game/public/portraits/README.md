# Painted persona portraits (drop-in art slots)

The game automatically uses real painted portrait art from this folder when it
exists, and falls back to the built-in procedural portraits when it doesn't.
No code change needed — just add the files:

| File            | Persona                        | Nameplate shown in-game        |
| --------------- | ------------------------------ | ------------------------------ |
| `latji.jpg`     | Latji Latji Elder              | Pre-Colonial Elder (~1788)     |
| `sturt.jpg`     | Capt. Charles Sturt            | Capt. Charles Sturt (1830)     |
| `squatter.jpg`  | Hugh Jamieson (squatter)       | Hugh Jamieson (1847)           |
| `chaffey.jpg`   | W.B. Chaffey                   | W.B. Chaffey (1887)            |

**Format:** JPEG, portrait orientation (roughly 3:4 — e.g. 512×680 or larger).
Crop each figure from the approved portrait sheet **without** its gold frame
and nameplate — the game draws its own frame and nameplate, so the art should
be just the painting.

Used in two places:
1. The status panel (bottom-left), small.
2. The framed **persona reveal card** that appears beside milestone newspaper
   banners when an era changes.
