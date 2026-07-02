import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GRID_W, GRID_H } from "./config";
import { generateMap } from "./map/mapData";
import type { Tile } from "./map/mapData";
import { sim, eraForYear } from "./game/state";
import { startGuestSession, loadLocal, saveLocal, isCloudConfigured } from "./auth/session";
import { buildTerrain, buildWater, buildVegetation, paintColour } from "./render/world";
import { buildSettlement } from "./render/buildings";
import { UnitManager } from "./render/units";
import { buildHud } from "./ui/hud";
import { MILESTONES, personaForYear } from "./game/milestones";
import { initNarrator, narrate } from "./game/narrator";
import { installBuildMenu } from "./game/buildMenu";

// --- World scale ------------------------------------------------------------
const MAP_W = 240;
const MAP_D = MAP_W * (GRID_H / GRID_W);
const HEIGHT_SCALE = 38;
const WATER_LEVEL = 0.02 * HEIGHT_SCALE;

// --- Session + restore ------------------------------------------------------
const session = startGuestSession();
const saved = loadLocal();
if (saved) sim.load(saved);

const map = generateMap();

// --- Renderer ---------------------------------------------------------------
const app = document.getElementById("app")!;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xaed4ea);
scene.fog = new THREE.Fog(0xbcd8e8, MAP_W * 1.1, MAP_W * 2.6);

const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.5, 4000);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = 1.32;
controls.minDistance = 14;
controls.maxDistance = MAP_W * 1.3;

// --- Lighting: bright warm midday sun (mock-up look) --------------------------
scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x59653c, 0.7));
scene.add(new THREE.AmbientLight(0xa8bcd0, 0.2));
const sun = new THREE.DirectionalLight(0xfff0d2, 2.5);
sun.position.set(-MAP_W * 0.35, HEIGHT_SCALE * 7, MAP_D * 0.25);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
const s = MAP_W * 0.62;
sun.shadow.camera.left = -s;
sun.shadow.camera.right = s;
sun.shadow.camera.top = s;
sun.shadow.camera.bottom = -s;
sun.shadow.camera.far = MAP_W * 4;
sun.shadow.bias = -0.0004;
scene.add(sun);

// --- Build the world ----------------------------------------------------------
const terrain = buildTerrain(scene, map, MAP_W, MAP_D, HEIGHT_SCALE, WATER_LEVEL);
const water = buildWater(scene, terrain, map);
const veg = buildVegetation(scene, map, terrain);
const settlement = buildSettlement(scene, map, terrain);
const units = new UnitManager(scene, terrain, settlement.homePos.x + 10, settlement.homePos.z + 8);

// Camera opens on the homestead, mock-up-style ¾ view looking over the river.
// Open on the river at the wharf bend — the mock-up's hero shot: high ¾ view
// over the water with forested banks either side.
{
  const wt = map.landmarkTiles["wharf"];
  const w = wt ? terrain.tileToWorld(wt.x, wt.y) : { x: settlement.homePos.x, z: settlement.homePos.z - 40 };
  controls.target.set(w.x, WATER_LEVEL, w.z);
  camera.position.set(w.x + 2, 64, w.z + 30);
}

// Open with a settler selected so the green ring + status card read immediately.
units.select(units.settlers[0]);

// --- HUD ------------------------------------------------------------------------
const cssCol = new THREE.Color();
const hud = buildHud(map, (t: Tile) => `#${paintColour(t, cssCol).getHexString()}`);
hud.setSelected(units.selected);

// [5] BUILD — date-gated build menu with staged construction (M4).
const buildMenu = installBuildMenu({ scene, terrain, map, sim, hud, camera, dom: renderer.domElement });

// --- Personas, milestones & narrator ------------------------------------------
initNarrator();
hud.setPersona(personaForYear(sim.year));
// Milestones already passed (e.g. restored save) never re-fire.
const firedMilestones = new Set(MILESTONES.filter((m) => m.year <= sim.year).map((m) => m.year));

// Dev/testing hook (harmless in production): force personas & banners.
(window as unknown as Record<string, unknown>).__mildura = {
  setPersona: (k: Parameters<typeof hud.setPersona>[0]) => hud.setPersona(k),
  showMilestone: (i: number) => {
    hud.showMilestone(MILESTONES[i]);
    narrate(MILESTONES[i].speech, MILESTONES[i].accent);
  },
};

function checkMilestones() {
  for (const m of MILESTONES) {
    if (m.year > sim.year || firedMilestones.has(m.year)) continue;
    firedMilestones.add(m.year);
    hud.showMilestone(m);
    narrate(m.speech, m.accent);
    if (m.persona) hud.setPersona(m.persona);
  }
}

hud.onMinimapClick = (fx, fy) => {
  const w = terrain.tileToWorld(fx * (GRID_W - 1), fy * (GRID_H - 1));
  const dx = w.x - controls.target.x;
  const dz = w.z - controls.target.z;
  controls.target.set(w.x, terrain.heightAt(w.x, w.z), w.z);
  camera.position.x += dx;
  camera.position.z += dz;
};

function nearestTileOfKind(x: number, z: number, kinds: Tile["kind"][]): { x: number; z: number } | null {
  let best: { x: number; z: number } | null = null;
  let bestD = Infinity;
  for (let ty = 0; ty < GRID_H; ty++) {
    for (let tx = 0; tx < GRID_W; tx++) {
      const t = map.at(tx, ty);
      if (!kinds.includes(t.kind)) continue;
      const w = terrain.tileToWorld(tx, ty);
      const d = (w.x - x) ** 2 + (w.z - z) ** 2;
      if (d < bestD) {
        bestD = d;
        best = w;
      }
    }
  }
  return best;
}

let clockT = 0;
function doAction(action: string) {
  hud.flashAction(action);
  const sel = units.selected ?? units.settlers[0];
  if (!units.selected) {
    units.select(sel);
    hud.setSelected(sel);
  }
  const p = sel.group.position;
  if (action === "survey") {
    controls.target.set(p.x, p.y, p.z);
  } else if (action === "chop") {
    const t = nearestTileOfKind(p.x, p.z, ["redgum"]);
    if (t) units.order(sel, t.x, t.z, clockT);
  } else if (action === "gather") {
    const t = nearestTileOfKind(p.x, p.z, ["floodplain"]);
    if (t) units.order(sel, t.x, t.z, clockT);
  } else if (action === "muster") {
    units.order(sel, settlement.homePos.x + 8, settlement.homePos.z + 6, clockT);
  }
}
hud.onAction = doAction;

// --- Picking: click = select, right-click = order, hover = landmark facts -------
const raycaster = new THREE.Raycaster();
const ndc = new THREE.Vector2();
function setRay(e: PointerEvent | MouseEvent) {
  ndc.x = (e.clientX / window.innerWidth) * 2 - 1;
  ndc.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(ndc, camera);
}

let downAt: { x: number; y: number; button: number } | null = null;
renderer.domElement.addEventListener("contextmenu", (e) => e.preventDefault());
renderer.domElement.addEventListener("pointerdown", (e) => {
  downAt = { x: e.clientX, y: e.clientY, button: e.button };
});
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) {
    downAt = null;
    return;
  }
  setRay(e);
  if (downAt.button === 0) {
    const hit = units.pick(raycaster);
    units.select(hit);
    hud.setSelected(hit);
  } else if (downAt.button === 2 && units.selected) {
    const ground = raycaster.intersectObject(terrain.mesh, false)[0];
    if (ground) units.order(units.selected, ground.point.x, ground.point.z, clockT);
  }
  downAt = null;
});
renderer.domElement.addEventListener("pointermove", (e) => {
  setRay(e);
  const hit = raycaster.intersectObjects(settlement.flagTargets, true)[0];
  if (hit) {
    const d = hit.object.userData.landmark as { name: string; fact: string; year?: number };
    hud.showTooltip(`<b>${d.name}${d.year ? ` (${d.year})` : ""}</b><br>${d.fact}`, e.clientX, e.clientY);
  } else {
    hud.hideTooltip();
  }
});

// --- Keyboard: WASD pan, SPACE pause, 1-4 actions --------------------------------
const keys = new Set<string>();
window.addEventListener("keydown", (e) => {
  keys.add(e.code);
  if (e.code === "Space") sim.paused = !sim.paused;
  const act = ({ Digit1: "survey", Digit2: "chop", Digit3: "gather", Digit4: "muster" } as Record<string, string>)[e.code];
  if (act) doAction(act);
});
window.addEventListener("keyup", (e) => keys.delete(e.code));

const panFwd = new THREE.Vector3();
const panRight = new THREE.Vector3();
function panCamera(dt: number) {
  const speed = 34 * dt;
  camera.getWorldDirection(panFwd);
  panFwd.y = 0;
  panFwd.normalize();
  panRight.crossVectors(panFwd, new THREE.Vector3(0, 1, 0));
  const move = new THREE.Vector3();
  if (keys.has("KeyW") || keys.has("ArrowUp")) move.add(panFwd);
  if (keys.has("KeyS") || keys.has("ArrowDown")) move.sub(panFwd);
  if (keys.has("KeyD") || keys.has("ArrowRight")) move.add(panRight);
  if (keys.has("KeyA") || keys.has("ArrowLeft")) move.sub(panRight);
  if (move.lengthSq() > 0) {
    move.normalize().multiplyScalar(speed);
    controls.target.add(move);
    camera.position.add(move);
  }
}

// --- Simulation clock + autosave ---------------------------------------------
setInterval(() => {
  sim.tick();
  checkMilestones();
  saveLocal(sim.snapshot());
}, 1500);

// --- Loop ----------------------------------------------------------------------
window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const clock = new THREE.Clock();
const dots: { x: number; y: number; kind: "settler" | "sheep" | "home" }[] = [];
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  clockT = clock.elapsedTime;

  panCamera(dt);
  controls.update();
  water.update(clockT);
  veg.update(clockT);
  settlement.update(clockT);
  units.update(dt, clockT);
  buildMenu.update(dt, clockT);

  const r = sim.resources;
  hud.update({
    year: sim.year,
    era: eraForYear(sim.year).name,
    paused: sim.paused,
    food: r.food,
    timber: r.timber,
    wool: r.wool,
    water: r.water,
    capital: r.capital,
    population: r.population,
    sessionLabel: `${session.displayName} · ${isCloudConfigured() ? "cloud saves" : "guest mode (free)"}`,
  });

  dots.length = 0;
  for (const st of units.settlers) {
    const g = terrain.worldToTile(st.group.position.x, st.group.position.z);
    dots.push({ x: g.x, y: g.y, kind: "settler" });
  }
  for (const sh of units.sheep) {
    const g = terrain.worldToTile(sh.group.position.x, sh.group.position.z);
    dots.push({ x: g.x, y: g.y, kind: "sheep" });
  }
  const home = terrain.worldToTile(settlement.homePos.x, settlement.homePos.z);
  dots.push({ x: home.x, y: home.y, kind: "home" });
  hud.drawMinimap(dots, terrain.worldToTile(controls.target.x, controls.target.z));

  renderer.render(scene, camera);
}
animate();
