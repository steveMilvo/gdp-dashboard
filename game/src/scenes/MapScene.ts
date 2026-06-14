import Phaser from "phaser";
import { TILE, MAP_PX_W, MAP_PX_H } from "../config";
import { generateMap, tileColour, GameMap } from "../map/mapData";
import { LANDMARKS } from "../map/landmarks";
import { sim } from "../game/state";
import { saveLocal } from "../auth/session";

// Renders the real-layout map, shows landmark "one-true-fact" tooltips, and runs
// the year clock. Pan = drag, zoom = mouse wheel.
export default class MapScene extends Phaser.Scene {
  private map!: GameMap;
  private tooltip!: Phaser.GameObjects.Text;
  private dragging = false;
  private lastX = 0;
  private lastY = 0;

  constructor() {
    super("MapScene");
  }

  create(): void {
    this.map = generateMap();
    this.drawTerrain();
    this.drawLandmarks();

    const cam = this.cameras.main;
    cam.setBounds(0, 0, MAP_PX_W, MAP_PX_H);
    cam.centerOn(MAP_PX_W * 0.5, MAP_PX_H * 0.35);
    cam.setZoom(1);

    this.setupCameraControls();

    this.tooltip = this.add
      .text(12, this.scale.height - 30, "Hover a marker to uncover its story.", {
        fontFamily: "system-ui, sans-serif",
        fontSize: "14px",
        color: "#f5e9c8",
        backgroundColor: "#00000088",
        padding: { x: 8, y: 4 },
      })
      .setScrollFactor(0)
      .setDepth(2000);

    // Year clock + autosave.
    this.time.addEvent({
      delay: 1500,
      loop: true,
      callback: () => {
        sim.tick();
        saveLocal(sim.snapshot());
      },
    });

    this.input.keyboard?.on("keydown-SPACE", () => (sim.paused = !sim.paused));
  }

  private drawTerrain(): void {
    const g = this.add.graphics();
    for (const t of this.map.tiles) {
      g.fillStyle(tileColour(t), 1);
      g.fillRect(t.x * TILE, t.y * TILE, TILE, TILE);
    }
    g.setDepth(0);
  }

  private drawLandmarks(): void {
    for (const lm of LANDMARKS) {
      const pos = this.map.landmarkTiles[lm.key];
      const px = pos.x * TILE + TILE / 2;
      const py = pos.y * TILE + TILE / 2;

      const marker = this.add
        .circle(px, py, 5, 0xffd24a)
        .setStrokeStyle(1.5, 0x3a2c00)
        .setDepth(10)
        .setInteractive({ useHandCursor: true });

      const label = this.add
        .text(px + 8, py - 6, lm.name, {
          fontFamily: "system-ui, sans-serif",
          fontSize: "11px",
          color: "#fff8e6",
          stroke: "#000000",
          strokeThickness: 3,
        })
        .setDepth(10);
      label.setVisible(false);

      marker.on("pointerover", () => {
        label.setVisible(true);
        const year = lm.year ? ` (${lm.year})` : "";
        this.tooltip.setText(`${lm.name}${year} — ${lm.fact}`);
      });
      marker.on("pointerout", () => label.setVisible(false));
    }
  }

  private setupCameraControls(): void {
    const cam = this.cameras.main;

    this.input.on("pointerdown", (p: Phaser.Input.Pointer) => {
      this.dragging = true;
      this.lastX = p.x;
      this.lastY = p.y;
    });
    this.input.on("pointerup", () => (this.dragging = false));
    this.input.on("pointermove", (p: Phaser.Input.Pointer) => {
      if (!this.dragging) return;
      cam.scrollX -= (p.x - this.lastX) / cam.zoom;
      cam.scrollY -= (p.y - this.lastY) / cam.zoom;
      this.lastX = p.x;
      this.lastY = p.y;
    });
    this.input.on(
      "wheel",
      (_p: Phaser.Input.Pointer, _o: unknown, _dx: number, dy: number) => {
        cam.setZoom(Phaser.Math.Clamp(cam.zoom - dy * 0.001, 0.5, 4));
      }
    );
  }
}
