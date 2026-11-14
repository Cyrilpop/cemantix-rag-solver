/**
 * Cémantix Solver — Gestion du Header & Routage Profil/Compte (Jalon M16)
 * =====================================================================
 * Gère l'aiguillage intelligent du badge « Mon compte » dans le header :
 * - Joueur connecté/revendiqué (is_claimed = true) : redirection fluide vers /account/
 * - Joueur invité / non connecté : ouverture de la modale d'inscription rapide
 */
import { openPlayerModal } from "./auth.js";

const SESSION_KEY = "cemantix_player_session";

export function getStoredPlayerSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function navigateToAccountOrModal(defaultTab = "login") {
  const session = getStoredPlayerSession();
  const currentPath = window.location.pathname;

  // Si le joueur est revendiqué avec mot de passe
  if (session && session.is_claimed) {
    if (currentPath.includes("/account")) {
      // Déjà sur la page compte : bascule sur l'onglet si fonction présente
      const tabBtn = document.querySelector(`.account-nav-btn[data-tab="${defaultTab}"]`);
      if (tabBtn) tabBtn.click();
      return;
    }
    window.location.href = "/account/";
    return;
  }

  // Joueur invité ou sans mot de passe : modale rapide d'onboarding
  openPlayerModal(defaultTab);
}

export function updateHeaderAccountBadge() {
  const session = getStoredPlayerSession();
  const badgeNameEl = document.getElementById("player-badge-name");
  const badgeBtn = document.getElementById("player-badge");
  const isClaimed = Boolean(session && session.is_claimed);

  if (badgeNameEl) {
    badgeNameEl.textContent = isClaimed ? "Mon compte" : "Connexion / Inscription";
  }
  if (badgeBtn) {
    badgeBtn.title = isClaimed ? "Mon compte" : "Connexion ou inscription";
    badgeBtn.setAttribute("aria-label", isClaimed ? "Mon compte" : "Connexion / Inscription");
  }
}

export function bindHeaderNavigation() {
  updateHeaderAccountBadge();
  const badgeBtn = document.getElementById("player-badge");
  if (badgeBtn && !badgeBtn.dataset.headerBound) {
    badgeBtn.dataset.headerBound = "true";
    badgeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      navigateToAccountOrModal("login");
    });
  }

  const welcomeBadge = document.getElementById("player-welcome-badge");
  if (welcomeBadge && !welcomeBadge.dataset.headerBound) {
    welcomeBadge.dataset.headerBound = "true";
    welcomeBadge.addEventListener("click", (e) => {
      e.preventDefault();
      navigateToAccountOrModal("login");
    });
  }
}
