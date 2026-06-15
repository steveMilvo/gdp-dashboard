import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GRID_W, GRID_H } from "./config";
import { generateMap, tileColour } from "./map/mapData";
import { LANDMARKS } from "./map/landmarks";
import { sim, eraForYear } from "./game/state";
import { startGuestSession, loadLocal, saveLocal, isCloudConfigured } from "./auth/session";

// --- World scale ------------------------------------------------------------
const MAP_W = 240; // world units east–west
const MAP_D = MAP_W * (GRID_H / GRID_W); // north–south, keeps real aspect
const HEIGHT_SCALE = 38; // vertical exaggeration so the ~28 m lift reads in 3D
const WATER_LEVEL = 0.14 * HEIGHT_SCALE;

// tile (x,y) -> world position helper (matches the displaced PlaneGeometry)
function tileToWorld(x: number, y: number) {
  return {
    x: -MAP_W / 2 + (x / (GRID_W - 1)) * MAP_W,
    z: -MAP_D / 2 + (y / (GRID_H - 1)) * MAP_D,
  };
}

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
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9ec9e6);
scene.fog = new THREE.Fog(0x9ec9e6, MAP_W * 0.9, MAP_W * 2.4);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.5, 4000);
camera.position.set(0, HEIGHT_SCALE * 4.5, MAP_D * 0.75);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = 1.35; // keep camera above the ground
controls.minDistance = 30;
controls.maxDistance = MAP_W * 1.6;
controls.target.set(0, 0, 0);

// --- Lighting ---------------------------------------------------------------
scene.add(new THREE.AmbientLight(0x88aacc, 0.7));
const sun = new THREE.DirectionalLight(0xfff2d6, 2.1);
sun.position.set(-MAP_W * 0.5, HEIGHT_SCALE * 8, -MAP_D * 0.3);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
const s = MAP_W * 0.7;
sun.shadow.camera.left = -s;
sun.shadow.camera.right = s;
sun.shadow.camera.top = s;
sun.shadow.camera.bottom = -s;
sun.shadow.camera.far = MAP_W * 4;
scene.add(sun);

// --- Terrain (displaced from the real-layout heightmap) ---------------------
const geo = new THREE.PlaneGeometry(MAP_W, MAP_D, GRID_W - 1, GRID_H - 1);
geo.rotateX(-Math.PI / 2); // lie flat in XZ; Y is up
const pos = geo.attributes.position;
const colors = new Float32Array(GRID_W * GRID_H * 3);
const col = new THREE.Color();
for (let iy = 0; iy < GRID_H; iy++) {
  for (let ix = 0; ix < GRID_W; ix++) {
    const idx = iy * GRID_W + ix;
    const t = map.at(ix, iy);
    pos.setY(idx, t.elevation * HEIGHT_SCALE);
    col.setHex(tileColour(t));
    colors[idx * 3] = col.r;
    colors[idx * 3 + 1] = col.g;
    colors[idx * 3 + 2] = col.b;
  }
}
geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
geo.computeVertexNormals();
const terrain = new THREE.Mesh(
  geo,
  new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0.0 })
);
terrain.receiveShadow = true;
terrain.castShadow = true;
scene.add(terrain);

// --- Water (the Murray + Kings Billabong sit below this surface) -------------
const water = new THREE.Mesh(
  new THREE.PlaneGeometry(MAP_W, MAP_D),
  new THREE.MeshStandardMaterial({
    color: 0x2d6a8e,
    transparent: true,
    opacity: 0.8,
    roughness: 0.15,
    metalness: 0.2,
  })
);
water.rotation.x = -Math.PI / 2;
water.position.y = WATER_LEVEL;
scene.add(water);

// --- Landmarks (3D markers + raycast hover facts) ---------------------------
const markers: THREE.Object3D[] = [];
const markerGeo = new THREE.ConeGeometry(2.6, 8, 6);
const markerMat = new THREE.MeshStandardMaterial({ color: 0xffd24a, roughness: 0.4 });
for (const lm of LANDMARKS) {
  const p = map.landmarkTiles[lm.key];
  const w = tileToWorld(p.x, p.y);
  const h = map.at(p.x, p.y).elevation * HEIGHT_SCALE;
  const cone = new THREE.Mesh(markerGeo, markerMat);
  cone.position.set(w.x, Math.max(h, WATER_LEVEL) + 6, w.z);
  cone.castShadow = true;
  cone.userData = { name: lm.name, fact: lm.fact, year: lm.year };
  scene.add(cone);
  markers.push(cone);
}

// --- HUD + tooltip ----------------------------------------------------------
const hud = document.getElementById("hud")!;
const footer = document.getElementById("footer")!;
const tooltip = document.getElementById("tooltip")!;
footer.textContent =
  `${session.displayName} · ${isCloudConfigured() ? "cloud saves on" : "guest mode (free) · local saves"}` +
  " · drag to orbit · wheel to zoom · right-drag to pan · SPACE to pause";

function updateHud() {
  const r = sim.resources;
  const era = eraForYear(sim.year);
  hud.innerHTML =
    `<b>Mildura — ${sim.year}</b> &nbsp; Era: ${era.name}${sim.paused ? " &nbsp;[PAUSED]" : ""}<br>` +
    `Pop ${r.population} · Food ${r.food} · Timber ${r.timber} · ` +
    `Wool ${r.wool} · Water ${r.water} · £${r.capital}`;
}

// --- Raycast hover for landmark facts ---------------------------------------
const raycaster = new THREE.Raycaster();
const ndc = new THREE.Vector2();
renderer.domElement.addEventListener("pointermove", (e) => {
  ndc.x = (e.clientX / window.innerWidth) * 2 - 1;
  ndc.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(ndc, camera);
  const hit = raycaster.intersectObjects(markers, false)[0];
  if (hit) {
    const d = hit.object.userData as { name: string; fact: string; year?: number };
    tooltip.style.display = "block";
    tooltip.style.left = `${e.clientX}px`;
    tooltip.style.top = `${e.clientY}px`;
    tooltip.innerHTML = `<b>${d.name}${d.year ? ` (${d.year})` : ""}</b><br>${d.fact}`;
  } else {
    tooltip.style.display = "none";
  }
});

// --- Simulation clock + autosave -------------------------------------------
window.addEventListener("keydown", (e) => {
  if (e.code === "Space") sim.paused = !sim.paused;
});
setInterval(() => {
  sim.tick();
  saveLocal(sim.snapshot());
}, 1500);

// --- Resize + render loop ---------------------------------------------------
window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  updateHud();
  renderer.render(scene, camera);
}
animate();
