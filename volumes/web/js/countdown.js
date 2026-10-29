/**
 * Cémantix Solver — Compte à Rebours Minuit (Europe/Paris)
 */

let countdownInterval = null;

export function initMidnightCountdown() {
  const cdHours = document.getElementById("cd-hours");
  const cdMinutes = document.getElementById("cd-minutes");
  const cdSeconds = document.getElementById("cd-seconds");

  if (!cdHours || !cdMinutes || !cdSeconds) return;

  // Construit une seule fois : `new Intl.DateTimeFormat(...)` est l'objet le plus
  // coûteux de l'API Intl et était réalloué à chaque tick, soit 86 400 fois par jour
  // et par onglet ouvert pour une configuration qui ne change jamais.
  const parisFormatter = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Europe/Paris",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hourCycle: "h23",
  });

  // Dernière valeur affichée, pour ne toucher le DOM qu'en cas de changement réel.
  let lastRendered = "";

  function update() {
    const now = new Date();

    const parts = parisFormatter.formatToParts(now);
    let h = 0, m = 0, s = 0;
    for (const part of parts) {
      if (part.type === "hour") h = parseInt(part.value, 10);
      if (part.type === "minute") m = parseInt(part.value, 10);
      if (part.type === "second") s = parseInt(part.value, 10);
    }

    const currentSeconds = h * 3600 + m * 60 + s;
    const totalDaySeconds = 86400;
    let diffSeconds = totalDaySeconds - currentSeconds;
    // À minuit pile, `currentSeconds` vaut 0 et le reste du jour vaut bien 86 400 s :
    // le ramener à 0 évite l'affichage « 24:00:00 » pendant la première seconde du jour.
    if (diffSeconds >= totalDaySeconds) diffSeconds = 0;

    const hours = Math.floor(diffSeconds / 3600);
    const minutes = Math.floor((diffSeconds % 3600) / 60);
    const seconds = diffSeconds % 60;

    const rendered = `${hours}:${minutes}:${seconds}`;
    if (rendered === lastRendered) return;
    lastRendered = rendered;

    cdHours.textContent = String(hours).padStart(2, "0");
    cdMinutes.textContent = String(minutes).padStart(2, "0");
    cdSeconds.textContent = String(seconds).padStart(2, "0");
  }

  function start() {
    if (countdownInterval) clearInterval(countdownInterval);
    update();
    countdownInterval = setInterval(update, 1000);
  }

  // Un onglet masqué n'affiche rien : on stoppe le tick et on resynchronise à la
  // reprise, au lieu de continuer à calculer une valeur personne ne regarde.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
      }
      return;
    }
    start();
  });

  start();
}
