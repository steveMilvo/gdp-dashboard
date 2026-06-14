import Phaser from "phaser";
import { startGuestSession, loadLocal } from "../auth/session";
import { sim } from "../game/state";

// Establishes a free guest session, restores any local autosave, then launches
// the map and the HUD overlay.
export default class BootScene extends Phaser.Scene {
  constructor() {
    super("BootScene");
  }

  create(): void {
    const session = startGuestSession();
    this.registry.set("session", session);

    const saved = loadLocal();
    if (saved) sim.load(saved);

    this.scene.start("MapScene");
    this.scene.launch("UIScene");
  }
}
