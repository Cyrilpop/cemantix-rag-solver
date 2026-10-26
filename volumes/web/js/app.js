/**
 * Cémantix Solver — Point d'Entrée Principal JavaScript (Modulaire)
 *
 * Les modules d'écran sont chargés en `import()` dynamique : un `import` statique
 * fait télécharger ET évaluer le module même si la branche `if` ne s'exécute jamais.
 * Depuis /play/, `dashboard.js` + `trajectory.js` + `countdown.js` représentaient
 * ~27 ko transférés et analysés pour rien sur les ~93 ko du graphe statique.
 */
import { initErrorHandling } from "./utils.js";
import { initTheme } from "./theme.js";

function bootstrap() {
  initErrorHandling();
  initTheme();

  const isDashboardPresent = document.getElementById("view-dashboard") || document.getElementById("secret-word-card");
  const isGamePresent = document.getElementById("view-play") || document.getElementById("game-guess-form");

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
    import("./dashboard.js").then(({ initDashboard }) => initDashboard());
  }

  if (isGamePresent) {
    import("./game.js").then(({ initGame }) => initGame());
  }
  // Pas de branche Battle : /battle/ charge js/battle.js directement, et ce module
  // s'auto-initialise (il appelle lui-même initErrorHandling et initTheme).
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}

