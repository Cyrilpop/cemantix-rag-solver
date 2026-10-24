/**
 * Cémantix Solver — Point d'Entrée Principal JavaScript (Modulaire)
 */
import { initErrorHandling } from "./utils.js";
import { initTheme } from "./theme.js";
import { initDashboard } from "./dashboard.js";
import { initGame } from "./game.js";

function bootstrap() {
  initErrorHandling();
  initTheme();

  const isDashboardPresent = document.getElementById("view-dashboard") || document.getElementById("secret-word-card");
  const isGamePresent = document.getElementById("view-play") || document.getElementById("game-guess-form");

  // Redirection d'anciennes URLs #play vers play/ si pages distinctes
  if (isDashboardPresent && !isGamePresent && window.location.hash === "#play") {
    window.location.replace("play/");
    return;
  }

  if (isDashboardPresent) {
    initDashboard();
  }

  if (isGamePresent) {
    initGame();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
