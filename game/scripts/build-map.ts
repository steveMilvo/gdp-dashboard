/**
 * build-map.ts — REAL map data pipeline (run offline on a machine with network).
 *
 * The game currently ships with a placeholder map (src/map/mapData.ts) that
 * encodes Mildura's real layout. This script documents and (when run with the
 * right data/tools) produces the *authentic* heightmap from open geodata, in the
 * same shape the game loads.
 *
 * It is intentionally NOT part of the Vite build (tsconfig includes only src/),
 * because it needs network access and GDAL — neither available in every sandbox.
 *
 * STEPS
 * 1. Elevation (the critical layer):
 *    Download a DEM for the bounding box from Geoscience Australia ELVIS
 *    (https://elevation.fsdf.org.au) — 5 m DEM where available, else 1-second
 *    SRTM — or Vicmap Elevation.
 *      Bounding box (approx): lat -34.30..-34.02, lon 141.95..142.45
 *      Centre: Mildura ~ -34.1855, 142.1625
 * 2. Water & roads:
 *    Pull the Murray River, Kings Billabong, lakes and roads from OpenStreetMap
 *    via the Overpass API for the same box.
 * 3. Historic grid (optional polish):
 *    Overlay the 1887 township survey from PROV / Trove so streets like Deakin
 *    Avenue land in their true positions.
 * 4. Process (GDAL / geotiff):
 *    - reproject to a local metric CRS and clip to the box
 *    - resample the DEM to the game tile grid (GRID_W x GRID_H)
 *    - normalise elevations to 0..1 (0 = river level)
 *    - burn in river/billabong polygons as water tiles
 *    - tag the named landmark coordinates (see src/map/landmarks.ts)
 * 5. Emit:
 *    - public/map/heightmap.json  (the GameMap structure)
 *    - commit BOTH the processed output and the source attribution so the map
 *      is reproducible and verifiably real.
 *
 * Then point generateMap() at the loaded JSON (source: "real-dem") instead of
 * the procedural placeholder.
 */

async function main(): Promise<void> {
  console.log("build-map: this is the documented real-DEM pipeline stub.");
  console.log("Run on a networked machine with GDAL installed; see the header for steps.");
  console.log("Output target: public/map/heightmap.json");
}

main();
