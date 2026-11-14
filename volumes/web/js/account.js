/**
 * Cémantix Solver — Logique Client de l'Espace « Mon compte » (Jalon M16)
 * ======================================================================
 * Gère la navigation par onglets verticaux, la consultation du profil,
 * la modification de mot de passe, l'affichage unique des mots de récupération
 * et le tableau de bord des statistiques de jeu personnelles.
 */
import { initAuth, openPlayerModal } from "./auth.js";
import { showToast, showConfirmDialog } from "./utils.js";

const SESSION_KEY = "cemantix_player_session";

function getStoredToken() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    return session ? session.auth_token : null;
  } catch {
    return null;
  }
}

function getStoredSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function apiFetch(endpoint, options = {}) {
  const token = getStoredToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(endpoint, {
    ...options,
    headers,
  });

  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// --- Navigation par Onglets Verticaux -----------------------------------------

function initTabs() {
  const navBtns = document.querySelectorAll(".account-nav-btn[data-tab]");
  const panes = document.querySelectorAll(".account-tab-pane");

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      if (!targetTab) return;

      navBtns.forEach((b) => b.classList.remove("active"));
      panes.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(`tab-${targetTab}`);
      if (targetPane) {
        targetPane.classList.add("active");
      }

      // Chargement à la demande
      if (targetTab === "profile") loadProfile();
      else if (targetTab === "security") loadRecoveryStatus();
      else if (targetTab === "stats") loadStats();
    });
  });

  // Déconnexion
  const logoutBtn = document.getElementById("btn-account-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }
}

// --- Chargement du Profil ---------------------------------------------------

async function loadProfile() {
  const nameEl = document.getElementById("acc-profile-name");
  const statusEl = document.getElementById("acc-profile-status");
  const createdEl = document.getElementById("acc-profile-created");
  const lastLoginEl = document.getElementById("acc-profile-last-login");
  const pwdUpdatedEl = document.getElementById("acc-profile-pwd-updated");

  const { ok, data } = await apiFetch("/api/account/profile");
  if (!ok) {
    if (nameEl) nameEl.textContent = "Session expirée ou profil invité";
    return;
  }

  if (nameEl) nameEl.textContent = data.username || "Joueur";
  if (statusEl) {
    if (data.isClaimed) {
      statusEl.className = "player-badge-status status-claimed";
      statusEl.textContent = "Compte protégé 🔒";
    } else {
      statusEl.className = "player-badge-status status-guest";
      statusEl.textContent = "Profil invité ⚠️";
    }
  }

  const formatDate = (isoStr) => {
    if (!isoStr) return "Non renseigné";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  if (createdEl) createdEl.textContent = formatDate(data.createdAt);
  if (lastLoginEl) lastLoginEl.textContent = formatDate(data.lastLoginAt);
  if (pwdUpdatedEl) pwdUpdatedEl.textContent = formatDate(data.passwordUpdatedAt);
}

// --- Sécurité & Changement de Mot de Passe ----------------------------------

function initSecurityForm() {
  const form = document.getElementById("account-pwd-form");
  const feedbackEl = document.getElementById("pwd-form-feedback");
  const submitBtn = document.getElementById("btn-submit-password");

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!feedbackEl || !submitBtn) return;

    feedbackEl.className = "account-feedback";
    feedbackEl.style.display = "none";

    const currentPwd = (document.getElementById("input-current-password")?.value || "").trim();
    const newPwd = (document.getElementById("input-new-password")?.value || "").trim();
    const confirmPwd = (document.getElementById("input-confirm-password")?.value || "").trim();

    if (!currentPwd || !newPwd) {
      feedbackEl.className = "account-feedback is-error";
      feedbackEl.textContent = "Veuillez renseigner le mot de passe actuel et le nouveau mot de passe.";
      return;
    }

    if (newPwd.length < 8) {
      feedbackEl.className = "account-feedback is-error";
      feedbackEl.textContent = "Le nouveau mot de passe doit comporter au moins 8 caractères.";
      return;
    }

    if (newPwd !== confirmPwd) {
      feedbackEl.className = "account-feedback is-error";
      feedbackEl.textContent = "La confirmation ne correspond pas au nouveau mot de passe.";
      return;
    }

    submitBtn.classList.add("is-loading");
    submitBtn.disabled = true;

    try {
      const { ok, data } = await apiFetch("/api/account/password", {
        method: "POST",
        body: JSON.stringify({
          currentPassword: currentPwd,
          newPassword: newPwd,
        }),
      });

      if (!ok) {
        feedbackEl.className = "account-feedback is-error";
        feedbackEl.textContent = data.error || "Erreur lors de la modification du mot de passe.";
      } else {
        feedbackEl.className = "account-feedback is-success";
        feedbackEl.textContent = "✓ Votre mot de passe a été mis à jour avec succès.";
        form.reset();
        showToast("✓ Mot de passe mis à jour");
        loadProfile();
      }
    } catch {
      feedbackEl.className = "account-feedback is-error";
      feedbackEl.textContent = "Erreur réseau. Veuillez réessayer.";
    } finally {
      submitBtn.classList.remove("is-loading");
      submitBtn.disabled = false;
    }
  });
}

// --- Mots de Récupération ----------------------------------------------------

async function loadRecoveryStatus() {
  const statusEl = document.getElementById("recovery-status-text");
  const dateEl = document.getElementById("recovery-status-date");
  const regenBtn = document.getElementById("btn-regenerate-recovery");

  const { ok, data } = await apiFetch("/api/account/recovery");
  if (!ok) {
    if (statusEl) statusEl.textContent = "Statut indisponible";
    return;
  }

  if (statusEl) {
    if (data.configured) {
      statusEl.innerHTML = `<span style="color:var(--success);">✓ Phrase de secours active (${data.count} mots)</span>`;
      if (regenBtn) regenBtn.textContent = "🎲 Remplacer ma phrase de secours";
    } else {
      statusEl.innerHTML = `<span style="color:var(--warning);">⚠️ Aucune phrase de secours configurée</span>`;
      if (regenBtn) regenBtn.textContent = "🎲 Configurer ma phrase de secours";
    }
  }

  if (dateEl) {
    if (data.configured) {
      dateEl.textContent = "Pour votre sécurité, vos 4 mots sont protégés cryptographiquement et ne peuvent pas être ré-affichés.";
    } else {
      dateEl.textContent = "Générez vos mots pour pouvoir restaurer votre compte en cas d'oubli.";
    }
  }
}

function initRecoveryActions() {
  const regenBtn = document.getElementById("btn-regenerate-recovery");
  const revealBox = document.getElementById("recovery-reveal-box");
  const wordsGrid = document.getElementById("recovery-words-grid");
  const copyBtn = document.getElementById("btn-copy-recovery-words");
  const dismissBtn = document.getElementById("btn-dismiss-recovery-words");

  let lastGeneratedWords = [];

  if (regenBtn) {
    regenBtn.addEventListener("click", async () => {
      const confirmed = await showConfirmDialog({
        title: "Remplacer la phrase de secours ?",
        message: "Attention : générer une nouvelle phrase de secours invalidera définitivement la précédente. Êtes-vous sûr de vouloir continuer ?",
        icon: "🔑",
        confirmText: "Générer une nouvelle phrase",
        cancelText: "Annuler",
        confirmType: "danger",
      });
      if (!confirmed) {
        return;
      }

      regenBtn.disabled = true;
      regenBtn.classList.add("is-loading");

      try {
        const { ok, data } = await apiFetch("/api/account/recovery", {
          method: "POST",
          body: JSON.stringify({ count: 4 }),
        });

        if (!ok) {
          alert(data.error || "Erreur lors de la génération des mots.");
          return;
        }

        lastGeneratedWords = data.recoveryWords || [];
        if (wordsGrid) {
          wordsGrid.innerHTML = lastGeneratedWords
            .map((w, idx) => `<div class="recovery-word-chip"><span style="font-size:0.75rem;opacity:0.6;display:block;">#${idx + 1}</span>${w}</div>`)
            .join("");
        }

        if (revealBox) {
          revealBox.style.display = "flex";
          revealBox.scrollIntoView({ behavior: "smooth" });
        }

        loadRecoveryStatus();
        showToast("✓ Nouvelle phrase de secours générée");
      } catch {
        alert("Erreur de connexion au serveur.");
      } finally {
        regenBtn.disabled = false;
        regenBtn.classList.remove("is-loading");
      }
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      if (!lastGeneratedWords.length) return;
      const text = lastGeneratedWords.join(" - ");
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.textContent = "✓ Copié !";
        setTimeout(() => {
          copyBtn.textContent = "📋 Copier les mots";
        }, 2500);
      } catch {
        prompt("Copiez vos mots :", text);
      }
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener("click", () => {
      if (revealBox) {
        revealBox.style.display = "none";
      }
      lastGeneratedWords = [];
    });
  }
}

// --- Statistiques de Jeu Personnelles ----------------------------------------

async function loadStats() {
  const gamesEl = document.getElementById("stat-total-games");
  const winsEl = document.getElementById("stat-victories");
  const winRateEl = document.getElementById("stat-win-rate");
  const avgGuessesEl = document.getElementById("stat-avg-guesses");
  const bestScoreEl = document.getElementById("stat-best-score");
  const avgTimeEl = document.getElementById("stat-avg-time");
  const hintsEl = document.getElementById("stat-hints-used");

  const { ok, data } = await apiFetch("/api/account/stats");
  if (!ok) return;

  if (gamesEl) gamesEl.textContent = data.totalGames ?? 0;
  if (winsEl) winsEl.textContent = data.victories ?? 0;
  if (winRateEl) winRateEl.textContent = `${data.winRate ?? 0}%`;
  if (avgGuessesEl) avgGuessesEl.textContent = data.avgGuesses ? `${data.avgGuesses}` : "-";
  if (bestScoreEl) bestScoreEl.textContent = data.bestScore ? `${data.bestScore}°C` : "-";
  if (avgTimeEl) {
    const sec = data.avgTimeSeconds || 0;
    if (sec > 60) {
      const min = Math.floor(sec / 60);
      const rem = Math.round(sec % 60);
      avgTimeEl.textContent = `${min}m ${rem}s`;
    } else {
      avgTimeEl.textContent = sec ? `${Math.round(sec)}s` : "-";
    }
  }
  if (hintsEl) hintsEl.textContent = data.hintsUsed ?? 0;
}

// --- Déconnexion -------------------------------------------------------------

async function handleLogout() {
  const confirmed = await showConfirmDialog({
    title: "Se déconnecter ?",
    message: "Voulez-vous vraiment vous déconnecter de votre compte ?",
    icon: "🚪",
    confirmText: "Se déconnecter",
    cancelText: "Rester connecté",
    confirmType: "danger",
  });
  if (!confirmed) {
    return;
  }

  try {
    await apiFetch("/api/account/logout", { method: "POST" });
  } catch {
    // Ignore network errors on logout
  }

  localStorage.removeItem(SESSION_KEY);
  showToast("Déconnexion réussie");
  window.location.href = "/";
}

// --- Initialisation au Chargement --------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  await initAuth();

  const session = getStoredSession();
  const unauthPrompt = document.getElementById("account-unauth-prompt");
  const mainLayout = document.getElementById("account-main-layout");

  if (!session || !session.auth_token) {
    if (unauthPrompt) unauthPrompt.style.display = "flex";
    if (mainLayout) mainLayout.style.display = "none";

    const loginShortcutBtn = document.getElementById("btn-account-login-prompt");
    if (loginShortcutBtn) {
      loginShortcutBtn.addEventListener("click", () => openPlayerModal("login"));
    }
    return;
  }

  if (unauthPrompt) unauthPrompt.style.display = "none";
  if (mainLayout) mainLayout.style.display = "grid";

  initTabs();
  initSecurityForm();
  initRecoveryActions();

  // Charge par défaut le profil
  loadProfile();
});
