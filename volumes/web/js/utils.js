/**
 * Cémantix Solver — Utilitaires & Formatage
 */

// Neutralisation des erreurs parasites d'extensions navigateur
export function initErrorHandling() {
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event?.reason;
    const msg = (reason && (reason.message || String(reason))) || "";
    if (msg.includes("tabs:outgoing.message.ready") || msg.includes("No Listener")) {
      event.preventDefault();
    }
  });

  window.addEventListener("error", (event) => {
    const msg = event?.message || "";
    if (msg.includes("tabs:outgoing.message.ready") || msg.includes("No Listener")) {
      event.preventDefault();
    }
  });
}

// Toast Notifications
let toastTimeout = null;
export function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.classList.remove("show");
  }, 2800);
}

// Fonction globale pour copier un mot au clic
export function copyToClipboard(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`📋 Mot « ${text} » copié !`);
  }).catch(() => {
    showToast("Erreur lors de la copie.");
  });
}

// Rendre accessible globalement pour les onclick inline du HTML/table
window.copyToClipboard = copyToClipboard;

// Formatage Date en Français
export function formatDateFr(isoDateStr) {
  if (!isoDateStr) return "--";
  try {
    const parts = isoDateStr.split("-");
    if (parts.length === 3) {
      const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
      return d.toLocaleDateString("fr-FR", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      });
    }
    const d = new Date(isoDateStr);
    return d.toLocaleDateString("fr-FR", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return isoDateStr;
  }
}

// Classification Thermique & Icônes Météo
export function getTierClass(score) {
  if (score < 0) return "tier-ice";
  if (score < 10) return "tier-cold";
  if (score < 20) return "tier-cool";
  if (score < 30) return "tier-warm";
  return "tier-fire";
}

export function getTierWeatherIcon(score, permille) {
  if (permille === 1000) return "🥳";
  if (permille && permille >= 990) return "🔥";
  if (permille && permille >= 900) return "🥵";
  if (permille && permille >= 1) return "😎";
  if (score >= 0) return "🥶";
  return "🧊";
}
