// Global tuning constants for the M1 map slice.

export const GRID_W = 110; // tiles across (east-west)
export const GRID_H = 90; // tiles down (north-south); north (y=0) is the river side
export const TILE = 9; // pixel size of a tile
export const MAP_SEED = 1887; // deterministic placeholder map (year of the Indenture)

export const MAP_PX_W = GRID_W * TILE;
export const MAP_PX_H = GRID_H * TILE;

// Real river-to-terrace lift that defines the whole settlement, in metres.
export const RIVER_LIFT_M = 28;
