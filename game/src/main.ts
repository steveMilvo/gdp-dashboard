import Phaser from "phaser";
import BootScene from "./scenes/BootScene";
import MapScene from "./scenes/MapScene";
import UIScene from "./scenes/UIScene";

// Only the first scene auto-starts; BootScene then starts MapScene + UIScene.
new Phaser.Game({
  type: Phaser.AUTO,
  parent: "app",
  backgroundColor: "#1f2933",
  scale: {
    mode: Phaser.Scale.RESIZE,
    autoCenter: Phaser.Scale.CENTER_BOTH,
    width: "100%",
    height: "100%",
  },
  scene: [BootScene, MapScene, UIScene],
});
