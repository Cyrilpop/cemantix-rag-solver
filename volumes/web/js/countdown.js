/**
 * Cémantix Solver — Compte à Rebours Minuit (Europe/Paris)
 */

let countdownInterval = null;

export function initMidnightCountdown() {
  const cdHours = document.getElementById("cd-hours");
  const cdMinutes = document.getElementById("cd-minutes");
  const cdSeconds = document.getElementById("cd-seconds");

  if (!cdHours || !cdMinutes || !cdSeconds) return;

  function update() {
    const now = new Date();
    // Heure de Paris (gère l'heure d'été/hiver)
    const parisFormatter = new Intl.DateTimeFormat("fr-FR", {
      timeZone: "Europe/Paris",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hourCycle: "h23",
    });

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
    if (diffSeconds < 0) diffSeconds += totalDaySeconds;

    const hours = Math.floor(diffSeconds / 3600);
    const minutes = Math.floor((diffSeconds % 3600) / 60);
    const seconds = diffSeconds % 60;

    cdHours.textContent = String(hours).padStart(2, "0");
    cdMinutes.textContent = String(minutes).padStart(2, "0");
    cdSeconds.textContent = String(seconds).padStart(2, "0");
  }

  update();
  if (countdownInterval) clearInterval(countdownInterval);
  countdownInterval = setInterval(update, 1000);
}
