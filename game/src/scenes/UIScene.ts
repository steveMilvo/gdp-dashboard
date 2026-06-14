import Phaser from "phaser";
import { sim, eraForYear } from "../game/state";
import type { Session } from "../auth/session";
import { isCloudConfigured } from "../auth/session";

// Lightweight HUD overlay: year, era, resources, session, and controls hint.
export default class UIScene extends Phaser.Scene {
  private bar!: Phaser.GameObjects.Text;
  private footer!: Phaser.GameObjects.Text;

  constructor() {
    super("UIScene");
  }

  create(): void {
    this.add.rectangle(0, 0, this.scale.width, 56, 0x10181f, 0.85).setOrigin(0, 0);

    this.bar = this.add.text(12, 8, "", {
      fontFamily: "system-ui, sans-serif",
      fontSize: "15px",
      color: "#f5e9c8",
      lineSpacing: 2,
    });

    const session = this.registry.get("session") as Session | undefined;
    const cloud = isCloudConfigured() ? "cloud saves on" : "guest mode (free) · local saves";
    this.footer = this.add
      .text(
        12,
        this.scale.height - 54,
        `${session?.displayName ?? "Guest"} · ${cloud}\nDrag to pan · wheel to zoom · SPACE to pause`,
        {
          fontFamily: "system-ui, sans-serif",
          fontSize: "12px",
          color: "#9fb3c8",
        }
      )
      .setOrigin(0, 0);

    this.scale.on("resize", () => {
      this.footer.setY(this.scale.height - 54);
    });
  }

  update(): void {
    const r = sim.resources;
    const era = eraForYear(sim.year);
    const status = sim.paused ? "  [PAUSED]" : "";
    this.bar.setText(
      `Mildura — ${sim.year}   ·   Era: ${era.name}${status}\n` +
        `Pop ${r.population}  ·  Food ${r.food}  ·  Timber ${r.timber}  ·  ` +
        `Wool ${r.wool}  ·  Water ${r.water}  ·  £${r.capital}`
    );
  }
}
