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

/**
 * Modale de confirmation personnalisée avec flou d'arrière-plan (glassmorphism).
 * Remplace window.confirm() par une interface moderne et élégante.
 *
 * @param {Object} options
 * @param {string} [options.title="Confirmation"] - Titre de la modale
 * @param {string} [options.message=""] - Message / question explicative
 * @param {string} [options.icon="⚠️"] - Icône ou emoji d'en-tête
 * @param {string} [options.confirmText="Confirmer"] - Texte du bouton d'action
 * @param {string} [options.cancelText="Annuler"] - Texte du bouton d'annulation
 * @param {"danger"|"primary"} [options.confirmType="danger"] - Style du bouton de confirmation
 * @returns {Promise<boolean>} Résout true si confirmé, false si annulé
 */
export function showConfirmDialog({
  title = "Confirmation",
  message = "Êtes-vous sûr de vouloir continuer ?",
  icon = "⚠️",
  confirmText = "Confirmer",
  cancelText = "Annuler",
  confirmType = "danger",
} = {}) {
  return new Promise((resolve) => {
    let backdrop = document.getElementById("global-confirm-modal");
    if (!backdrop) {
      backdrop = document.createElement("div");
      backdrop.id = "global-confirm-modal";
      backdrop.className = "modal-backdrop";
      backdrop.style.display = "none";
      backdrop.setAttribute("role", "dialog");
      backdrop.setAttribute("aria-modal", "true");
      backdrop.setAttribute("aria-labelledby", "confirm-modal-title");
      backdrop.innerHTML = `
        <div class="card confirm-modal-card" role="document">
          <div class="confirm-modal-body">
            <span class="confirm-modal-icon" id="confirm-modal-icon">⚠️</span>
            <h3 class="confirm-modal-title" id="confirm-modal-title">Titre</h3>
            <p class="confirm-modal-message" id="confirm-modal-message">Message</p>
          </div>
          <div class="confirm-modal-footer">
            <button type="button" class="btn btn-secondary" id="confirm-modal-cancel-btn">Annuler</button>
            <button type="button" class="btn" id="confirm-modal-ok-btn">Confirmer</button>
          </div>
        </div>
      `;
      document.body.appendChild(backdrop);
    }

    const card = backdrop.querySelector(".confirm-modal-card");
    const iconEl = backdrop.querySelector("#confirm-modal-icon");
    const titleEl = backdrop.querySelector("#confirm-modal-title");
    const msgEl = backdrop.querySelector("#confirm-modal-message");
    const cancelBtn = backdrop.querySelector("#confirm-modal-cancel-btn");
    const okBtn = backdrop.querySelector("#confirm-modal-ok-btn");

    if (iconEl) iconEl.textContent = icon;
    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    if (cancelBtn) cancelBtn.textContent = cancelText;

    if (okBtn) {
      okBtn.textContent = confirmText;
      okBtn.className = confirmType === "danger" ? "btn btn-danger" : "btn btn-primary";
    }

    if (card) {
      card.classList.toggle("is-accent", confirmType !== "danger");
    }

    let isResolved = false;
    function cleanup(value) {
      if (isResolved) return;
      isResolved = true;
      backdrop.style.display = "none";
      document.removeEventListener("keydown", handleKeyDown);
      backdrop.removeEventListener("click", handleBackdropClick);
      resolve(value);
    }

    function handleKeyDown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        cleanup(false);
      } else if (e.key === "Enter") {
        e.preventDefault();
        cleanup(true);
      }
    }

    function handleBackdropClick(e) {
      if (e.target === backdrop) {
        cleanup(false);
      }
    }

    cancelBtn.onclick = () => cleanup(false);
    okBtn.onclick = () => cleanup(true);
    backdrop.addEventListener("click", handleBackdropClick);
    document.addEventListener("keydown", handleKeyDown);

    backdrop.style.display = "flex";
    setTimeout(() => {
      cancelBtn.focus();
    }, 50);
  });
}

// Rendre également accessible globalement sur window pour commodité
window.showConfirmDialog = showConfirmDialog;
