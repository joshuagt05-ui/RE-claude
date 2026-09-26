# Maps

Every chapter and every Dispatch opens with a map. The in-world idea is **Eli's atlas**. The maps show the true situation on the chapter's date, so the reader often knows more than the characters do. A red river on the map while Ray waters the cattle is the kind of dramatic irony we want.

| Map | File |
|---|---|
| Reference: The Watershed | `out/ref-watershed.svg` |
| Chapter 1: Homecoming | `out/ch01.svg` |
| Dispatch I: Departures | `out/dispatch01.svg` |

## How it works
- `specs/<id>.json` describes one map: its extent, places, story rivers (red or clean), outbreak zones, routes, flights, roads, mountains and handwritten notes.
- `render.py` turns every spec into `out/<id>.svg`. It uses the Python standard library only:
  ```
  python3 maps/render.py            # all maps
  python3 maps/render.py ch02       # one map
  ```
- Base geography is Natural Earth (public domain), taken from the `sane-topojson` and `us-atlas` packages and vendored in `data/` with their licenses. Fictional places are defined in the specs.

## Map vocabulary
| Mark | Meaning |
|---|---|
| ★ in a dashed ring | Where the family is |
| Red river | Contaminated water |
| Blue river | Clean water, as far as anyone knows |
| Red hatching | Outbreak. Dashed outline means rumored. |
| Dashed black line | Where they went. Dotted means where they're going. |
| Dotted arc | Flight. Red means a carrier was aboard. |
| ⊗ | Destroyed |

## Adding a chapter map
Copy the closest spec. Set `kicker` (the part), `title`, `subtitle` (day, date and place) and `extent` ([west, south, east, north]). Then update what's red. Use `"base": "world"` with `"projection": {"type": "natural_earth"}` and `"fit": "contain"` for global maps.
