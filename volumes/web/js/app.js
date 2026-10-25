/**
 * Cémantix Solver — Point d'Entrée Principal JavaScript (Modulaire)
 */
import { initErrorHandling } from "./utils.js";
import { initTheme } from "./theme.js";
import { initDashboard } from "./dashboard.js";
import { initGame } from "./game.js";
import { initBattle } from "./battle.js";

function bootstrap() {
  initErrorHandling();
  initTheme();

  const isDashboardPresent = document.getElementById("view-dashboard") || document.getElementById("secret-word-card");
  const isGamePresent = document.getElementById("view-play") || document.getElementById("game-guess-form");
  const isBattlePresent = document.getElementById("view-battle") || document.getElementById("battle-guess-form");

  // Redirection d'anciennes URLs avec hash (#play -> play/, #battle/#duel -> battle/)
  if (isDashboardPresent && window.location.hash === "#play") {
    window.location.replace("play/");
    return;
  }
  if (isDashboardPresent && (window.location.hash === "#battle" || window.location.hash === "#duel")) {
    window.location.replace("battle/");
    return;
  }

  if (isDashboardPresent) {
    initDashboard();
  }

  if (isGamePresent) {
    initGame();
  }

  if (isBattlePresent) {
    initBattle();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
