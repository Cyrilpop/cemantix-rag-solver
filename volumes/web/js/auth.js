/**
 * Cémantix Solver — Module Frontend d'Authentification Joueur (M14)
 * =================================================================
 * Gère l'attribution de profil invité, la synchronisation du badge Header,
 * la bannière d'accueil non intrusive première visite et la modale de profil.
 */

const STORAGE_SESSION_KEY = "cemantix_player_session";
const STORAGE_DISMISSED_KEY = "cemantix_welcome_dismissed";
const API_BASE = "/api/player";

let currentSession = null;
let initAuthPromise = null;

export function getStoredSession() {
  try {
    const raw = localStorage.getItem(STORAGE_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function saveStoredSession(session) {
  try {
    localStorage.setItem(STORAGE_SESSION_KEY, JSON.stringify(session));
    currentSession = session;
  } catch (e) {
    // Mode navigation privée stricte
  }
}

export function clearStoredSession() {
  try {
    localStorage.removeItem(STORAGE_SESSION_KEY);
    currentSession = null;
  } catch (e) {
    // Mode navigation privée
  }
}

/**
 * Met à jour le texte du badge Header universel.
 */
function updateHeaderBadge(username) {
  const badgeNameEl = document.getElementById("player-badge-name");
  const badgeBtn = document.getElementById("player-badge");
  const welcomeNameEl = document.getElementById("player-welcome-name");

  if (badgeNameEl) {
    badgeNameEl.textContent = "Mon compte";
  }
  if (badgeBtn) {
    badgeBtn.title = username ? `Mon compte (${username})` : "Mon compte";
    badgeBtn.setAttribute("aria-label", "Mon compte");
  }
  if (welcomeNameEl && username) {
    welcomeNameEl.textContent = username;
  }
}

/**
 * Affiche la bannière d'accueil première visite discrète.
 */
function showWelcomeToast(username) {
  if (localStorage.getItem(STORAGE_DISMISSED_KEY) === "true") {
    return;
  }

  // Évite les doublons
  if (document.getElementById("player-welcome-toast")) {
    return;
  }

  const toast = document.createElement("div");
  toast.id = "player-welcome-toast";
  toast.className = "player-welcome-toast";
  toast.setAttribute("role", "status");

  toast.innerHTML = `
    <div class="player-welcome-content">
      <p class="player-welcome-msg">
        👋 <strong>Bienvenue !</strong> Ton identité de jeu est <strong>${escapeHtml(username)}</strong>.
      </p>
      <div class="player-welcome-actions">
        <button type="button" id="btn-welcome-rename" class="btn btn-sm btn-primary">✏️ Personnaliser mon pseudo</button>
        <button type="button" id="btn-welcome-ok" class="btn btn-sm btn-secondary">C'est parti !</button>
        <button type="button" id="btn-welcome-close" class="btn-icon btn-sm" aria-label="Fermer" title="Ne plus afficher">✕</button>
      </div>
    </div>
  `;

  document.body.appendChild(toast);

  const dismiss = () => {
    localStorage.setItem(STORAGE_DISMISSED_KEY, "true");
    toast.remove();
  };

  const btnOk = toast.querySelector("#btn-welcome-ok");
  const btnClose = toast.querySelector("#btn-welcome-close");
  const btnRename = toast.querySelector("#btn-welcome-rename");

  if (btnOk) btnOk.addEventListener("click", dismiss);
  if (btnClose) btnClose.addEventListener("click", dismiss);
  if (btnRename) {
    btnRename.addEventListener("click", () => {
      dismiss();
      openPlayerModal("profile");
    });
  }
}

/**
 * Construit et injecte la modale native <dialog> dans le DOM si absente.
 */
function ensurePlayerModal() {
  let modal = document.getElementById("player-modal");
  if (modal) return modal;

  modal = document.createElement("dialog");
  modal.id = "player-modal";
  modal.className = "modal player-modal";

  modal.innerHTML = `
    <div class="player-modal-card">
      <div class="player-modal-header">
        <h3>👤 Mon compte</h3>
        <button type="button" id="modal-close-cross" class="btn-icon btn-sm" aria-label="Fermer la modale">✕</button>
      </div>

      <nav class="player-nav-tabs" aria-label="Onglets profil">
        <button type="button" class="player-tab-btn active" data-tab="profile">Mon Profil</button>
        <button type="button" class="player-tab-btn" data-tab="claim">🔒 Protéger</button>
        <button type="button" class="player-tab-btn" data-tab="login">📱 Connexion</button>
      </nav>

      <!-- Onglet 1 : Profil & Renommage -->
      <div id="tab-profile" class="player-tab-pane active">
        <div class="player-profile-summary">
          <div class="player-profile-info">
            <span class="player-field-note">Pseudo actuel :</span>
            <span id="player-modal-current-name" class="player-profile-name">Profil invité</span>
          </div>
          <span id="player-modal-status-badge" class="player-badge-status status-guest">Invité</span>
        </div>

        <div id="player-rename-container" class="player-field-group">
          <label for="input-player-rename">Personnaliser mon pseudo (8 à 24 car.) :</label>
          <input type="text" id="input-player-rename" class="player-input" minlength="8" maxlength="24" placeholder="Ex: PanthereAgile" autocomplete="off">
          <span class="player-field-note">⚠️ Attention : la personnalisation est définitive (possible une seule fois).</span>
          <button type="button" id="btn-player-rename" class="btn btn-primary btn-sm" style="margin-top: 0.5rem;">Enregistrer mon pseudo</button>
        </div>

        <div id="player-rename-locked" class="player-msg is-success" style="display: none;">
          ✓ Pseudo personnalisé et verrouillé.
        </div>

        <div id="player-rename-msg" class="player-msg"></div>

        <div class="player-actions-row" style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem;">
          <button type="button" id="btn-player-claim-shortcut" class="btn btn-secondary btn-sm">🔒 Protéger par mot de passe</button>
          <button type="button" id="btn-player-login-shortcut" class="btn btn-secondary btn-sm">📱 Changer d'appareil / Se connecter</button>
        </div>

        <div class="player-danger-zone">
          <button type="button" id="btn-player-delete-account" class="btn btn-ghost btn-sm" style="color: var(--danger);">🗑️ Réinitialiser mon profil</button>
        </div>
      </div>

      <!-- Onglet 2 : Protection par Mot de Passe & 4 Mots -->
      <div id="tab-claim" class="player-tab-pane">
        <div id="claim-form-container">
          <p class="player-field-note" style="line-height: 1.4;">
            Définissez un mot de passe pour retrouver vos parties et statistiques sur un autre appareil. 
            <strong>Aucun email n'est collecté :</strong> une phrase secrète de 4 mots vous sera remise pour récupérer l'accès en cas d'oubli.
          </p>
          <div class="player-field-group" style="margin-top: 0.5rem;">
            <label for="input-claim-pwd">Mot de passe (8 caractères min.) :</label>
            <input type="password" id="input-claim-pwd" class="player-input" minlength="8" placeholder="••••••••">
          </div>
          <div class="player-field-group">
            <label for="input-claim-pwd2">Confirmer le mot de passe :</label>
            <input type="password" id="input-claim-pwd2" class="player-input" minlength="8" placeholder="••••••••">
          </div>
          <button type="button" id="btn-player-claim-submit" class="btn btn-primary btn-sm" style="margin-top: 0.5rem;">
            🔒 Activer la protection
          </button>
        </div>

        <!-- Encart de phrase secrète une fois claim réussi -->
        <div id="claim-success-container" style="display: none; flex-direction: column; gap: 0.85rem;">
          <div class="player-msg is-success" style="display: block;">
            ✓ Compte protégé avec succès !
          </div>
          <div class="recovery-box">
            <span class="player-field-note">🔑 Votre phrase secrète de secours (4 mots) :</span>
            <div id="claim-recovery-phrase" class="recovery-phrase">mot1 mot2 mot3 mot4</div>
            <button type="button" id="btn-copy-recovery-phrase" class="btn btn-secondary btn-sm">📋 Copier la phrase</button>
          </div>
          <p class="player-field-note" style="color: var(--warning); line-height: 1.4;">
            ⚠️ <strong>Important :</strong> Conservez précieusement ces 4 mots ! En l'absence d'adresse email, ils constituent votre unique moyen de réinitialiser votre mot de passe.
          </p>
        </div>

        <div id="player-claim-msg" class="player-msg"></div>
      </div>

      <!-- Onglet 3 : Connexion Multi-Appareils & Récupération -->
      <div id="tab-login" class="player-tab-pane">
        <p class="player-field-note" style="line-height: 1.4; margin-bottom: 0.75rem;">
          Vous changez d'appareil ou souhaitez retrouver votre progression ? Connectez-vous ici avec votre pseudo et votre mot de passe :
        </p>
        <div class="pill-group" style="width: 100%; margin-bottom: 0.5rem;">
          <button type="button" class="pill-btn active" id="btn-subtab-login" style="flex: 1;">Se connecter</button>
          <button type="button" class="pill-btn" id="btn-subtab-reset" style="flex: 1;">Mot de passe oublié (4 mots)</button>
        </div>

        <!-- Formulaire Connexion -->
        <div id="subpane-login" style="display: flex; flex-direction: column; gap: 0.75rem;">
          <div class="player-field-group">
            <label for="input-login-user">Pseudo :</label>
            <input type="text" id="input-login-user" class="player-input" placeholder="Votre pseudo">
          </div>
          <div class="player-field-group">
            <label for="input-login-pwd">Mot de passe :</label>
            <input type="password" id="input-login-pwd" class="player-input" placeholder="••••••••">
          </div>
          <button type="button" id="btn-player-login-submit" class="btn btn-primary btn-sm">Se connecter</button>
        </div>

        <!-- Formulaire Réinitialisation 4 mots -->
        <div id="subpane-reset" style="display: none; flex-direction: column; gap: 0.75rem;">
          <p class="player-field-note">Restaurez l'accès grâce à vos 4 mots de secours :</p>
          <div class="player-field-group">
            <label for="input-reset-user">Pseudo :</label>
            <input type="text" id="input-reset-user" class="player-input" placeholder="Votre pseudo">
          </div>
          <div class="player-field-group">
            <label for="input-reset-phrase">Phrase de secours (4 mots) :</label>
            <input type="text" id="input-reset-phrase" class="player-input" placeholder="ex: navire falaise citron vortex">
          </div>
          <div class="player-field-group">
            <label for="input-reset-pwd">Nouveau mot de passe :</label>
            <input type="password" id="input-reset-pwd" class="player-input" minlength="8" placeholder="••••••••">
          </div>
          <button type="button" id="btn-player-reset-submit" class="btn btn-primary btn-sm">Réinitialiser et se connecter</button>
        </div>

        <div id="player-login-msg" class="player-msg"></div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  attachModalEvents(modal);
  return modal;
}

/**
 * Associe les écouteurs d'événements de la modale.
 */
function attachModalEvents(modal) {
  // Fermeture
  const closeCross = modal.querySelector("#modal-close-cross");
  if (closeCross) {
    closeCross.addEventListener("click", () => modal.close());
  }
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.close();
  });

  // Navigation par onglets
  const tabBtns = modal.querySelectorAll(".player-tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const targetId = `tab-${btn.dataset.tab}`;
      modal.querySelectorAll(".player-tab-pane").forEach((pane) => {
        pane.classList.remove("active");
      });
      const targetPane = modal.querySelector(`#${targetId}`);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Bascule sous-onglets login / reset
  const subBtnLogin = modal.querySelector("#btn-subtab-login");
  const subBtnReset = modal.querySelector("#btn-subtab-reset");
  const subPaneLogin = modal.querySelector("#subpane-login");
  const subPaneReset = modal.querySelector("#subpane-reset");

  if (subBtnLogin && subBtnReset) {
    subBtnLogin.addEventListener("click", () => {
      subBtnLogin.classList.add("active");
      subBtnReset.classList.remove("active");
      subPaneLogin.style.display = "flex";
      subPaneReset.style.display = "none";
    });
    subBtnReset.addEventListener("click", () => {
      subBtnReset.classList.add("active");
      subBtnLogin.classList.remove("active");
      subPaneLogin.style.display = "none";
      subPaneReset.style.display = "flex";
    });
  }

  // Raccourci vers la protection depuis le profil
  const btnClaimShortcut = modal.querySelector("#btn-player-claim-shortcut");
  if (btnClaimShortcut) {
    btnClaimShortcut.addEventListener("click", () => {
      const claimTabBtn = modal.querySelector('.player-tab-btn[data-tab="claim"]');
      if (claimTabBtn) claimTabBtn.click();
    });
  }

  // Raccourci vers la connexion sur un autre appareil
  const btnLoginShortcut = modal.querySelector("#btn-player-login-shortcut");
  if (btnLoginShortcut) {
    btnLoginShortcut.addEventListener("click", () => {
      const loginTabBtn = modal.querySelector('.player-tab-btn[data-tab="login"]');
      if (loginTabBtn) loginTabBtn.click();
    });
  }

  // Action Renommage
  const btnRename = modal.querySelector("#btn-player-rename");
  if (btnRename) {
    btnRename.addEventListener("click", handleRenameAction);
  }

  // Action Protection
  const btnClaim = modal.querySelector("#btn-player-claim-submit");
  if (btnClaim) {
    btnClaim.addEventListener("click", handleClaimAction);
  }

  // Action Copie Phrase de Secours
  const btnCopyPhrase = modal.querySelector("#btn-copy-recovery-phrase");
  if (btnCopyPhrase) {
    btnCopyPhrase.addEventListener("click", () => {
      const phraseEl = modal.querySelector("#claim-recovery-phrase");
      if (phraseEl) {
        navigator.clipboard.writeText(phraseEl.textContent.trim()).then(() => {
          btnCopyPhrase.textContent = "✓ Copié !";
          setTimeout(() => {
            btnCopyPhrase.textContent = "📋 Copier la phrase";
          }, 2000);
        });
      }
    });
  }

  // Action Connexion
  const btnLogin = modal.querySelector("#btn-player-login-submit");
  if (btnLogin) {
    btnLogin.addEventListener("click", handleLoginAction);
  }

  // Action Réinitialisation
  const btnReset = modal.querySelector("#btn-player-reset-submit");
  if (btnReset) {
    btnReset.addEventListener("click", handleResetAction);
  }

  // Action Suppression / Droit à l'effacement
  const btnDelete = modal.querySelector("#btn-player-delete-account");
  if (btnDelete) {
    btnDelete.addEventListener("click", handleDeleteAccountAction);
  }
}

/**
 * Met à jour le contenu de la modale avec la session courante.
 */
function refreshModalView() {
  const modal = document.getElementById("player-modal");
  if (!modal) return;

  const currentNameEl = modal.querySelector("#player-modal-current-name");
  const statusBadgeEl = modal.querySelector("#player-modal-status-badge");
  const renameContainer = modal.querySelector("#player-rename-container");
  const renameLocked = modal.querySelector("#player-rename-locked");
  const renameMsg = modal.querySelector("#player-rename-msg");
  const btnClaimShortcut = modal.querySelector("#btn-player-claim-shortcut");

  if (!currentSession) {
    if (currentNameEl) currentNameEl.textContent = "Chargement du compte…";
    return;
  }

  if (currentNameEl) currentNameEl.textContent = currentSession.username;
  if (renameMsg) {
    renameMsg.style.display = "none";
    renameMsg.textContent = "";
  }

  if (statusBadgeEl) {
    if (currentSession.is_claimed) {
      statusBadgeEl.className = "player-badge-status status-claimed";
      statusBadgeEl.textContent = "Protégé 🔒";
      if (btnClaimShortcut) btnClaimShortcut.style.display = "none";
    } else {
      statusBadgeEl.className = "player-badge-status status-guest";
      statusBadgeEl.textContent = "Invité";
      if (btnClaimShortcut) btnClaimShortcut.style.display = "inline-flex";
    }
  }

  if (currentSession.can_change_username) {
    if (renameContainer) renameContainer.style.display = "flex";
    if (renameLocked) renameLocked.style.display = "none";
  } else {
    if (renameContainer) renameContainer.style.display = "none";
    if (renameLocked) renameLocked.style.display = "block";
  }
}

/**
 * Ouvre la modale de profil joueur.
 */
export async function openPlayerModal(tab = "profile") {
  const modal = ensurePlayerModal();
  if (!currentSession && initAuthPromise) {
    try {
      await initAuthPromise;
    } catch (e) {
      // Ignorer l'erreur réseau éventuelle
    }
  }
  refreshModalView();
  const tabBtn = modal.querySelector(`.player-tab-btn[data-tab="${tab}"]`);
  if (tabBtn) tabBtn.click();
  modal.showModal();
}

/**
 * Gestionnaire d'action : Renommage unique.
 */
async function handleRenameAction() {
  const modal = document.getElementById("player-modal");
  const input = modal.querySelector("#input-player-rename");
  const msgEl = modal.querySelector("#player-rename-msg");
  const btn = modal.querySelector("#btn-player-rename");

  const newName = (input?.value || "").trim();
  if (newName.length < 8 || newName.length > 24) {
    showMsg(msgEl, "Le pseudo doit comporter entre 8 et 24 caractères.", "error");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Enregistrement…";

  try {
    const res = await fetch(`${API_BASE}/rename`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentSession.auth_token}`,
      },
      body: JSON.stringify({ new_username: newName }),
    });
    const data = await res.json();
    if (!res.ok) {
      showMsg(msgEl, data.error || "Erreur lors du renommage.", "error");
      return;
    }

    currentSession.username = data.username;
    currentSession.can_change_username = false;
    saveStoredSession(currentSession);
    updateHeaderBadge(data.username);
    refreshModalView();
    showMsg(msgEl, "Pseudo personnalisé avec succès !", "success");
  } catch (err) {
    showMsg(msgEl, "Erreur réseau. Veuillez réessayer.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Enregistrer mon pseudo";
  }
}

/**
 * Gestionnaire d'action : Sécurisation par mot de passe.
 */
async function handleClaimAction() {
  const modal = document.getElementById("player-modal");
  const pwd1 = modal.querySelector("#input-claim-pwd")?.value || "";
  const pwd2 = modal.querySelector("#input-claim-pwd2")?.value || "";
  const msgEl = modal.querySelector("#player-claim-msg");
  const btn = modal.querySelector("#btn-player-claim-submit");

  if (pwd1.length < 8) {
    showMsg(msgEl, "Le mot de passe doit comporter au moins 8 caractères.", "error");
    return;
  }
  if (pwd1 !== pwd2) {
    showMsg(msgEl, "Les mots de passe ne correspondent pas.", "error");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Sécurisation en cours…";

  try {
    const res = await fetch(`${API_BASE}/claim`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentSession.auth_token}`,
      },
      body: JSON.stringify({ password: pwd1 }),
    });
    const data = await res.json();
    if (!res.ok) {
      showMsg(msgEl, data.error || "Erreur lors de la protection du compte.", "error");
      return;
    }

    currentSession.is_claimed = true;
    saveStoredSession(currentSession);
    refreshModalView();

    // Affichage de la phrase de secours
    const formContainer = modal.querySelector("#claim-form-container");
    const successContainer = modal.querySelector("#claim-success-container");
    const phraseDisplay = modal.querySelector("#claim-recovery-phrase");

    if (formContainer) formContainer.style.display = "none";
    if (phraseDisplay) phraseDisplay.textContent = data.recovery_phrase;
    if (successContainer) successContainer.style.display = "flex";
  } catch (err) {
    showMsg(msgEl, "Erreur réseau. Veuillez réessayer.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "🔒 Activer la protection";
  }
}

/**
 * Gestionnaire d'action : Connexion pseudo + mot de passe.
 */
async function handleLoginAction() {
  const modal = document.getElementById("player-modal");
  const user = (modal.querySelector("#input-login-user")?.value || "").trim();
  const pwd = modal.querySelector("#input-login-pwd")?.value || "";
  const msgEl = modal.querySelector("#player-login-msg");
  const btn = modal.querySelector("#btn-player-login-submit");

  if (!user || !pwd) {
    showMsg(msgEl, "Pseudo et mot de passe requis.", "error");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Connexion…";

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pwd }),
    });
    const data = await res.json();
    if (!res.ok) {
      showMsg(msgEl, data.error || "Identifiants incorrects.", "error");
      return;
    }

    saveStoredSession(data);
    updateHeaderBadge(data.username);
    refreshModalView();
    showMsg(msgEl, `Reconnexion réussie ! Bienvenue ${data.username}.`, "success");
    setTimeout(() => {
      modal.close();
    }, 1500);
  } catch (err) {
    showMsg(msgEl, "Erreur réseau.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Se connecter";
  }
}

/**
 * Gestionnaire d'action : Réinitialisation via phrase de secours de 4 mots.
 */
async function handleResetAction() {
  const modal = document.getElementById("player-modal");
  const user = (modal.querySelector("#input-reset-user")?.value || "").trim();
  const phrase = (modal.querySelector("#input-reset-phrase")?.value || "").trim();
  const pwd = modal.querySelector("#input-reset-pwd")?.value || "";
  const msgEl = modal.querySelector("#player-login-msg");
  const btn = modal.querySelector("#btn-player-reset-submit");

  if (!user || !phrase || !pwd) {
    showMsg(msgEl, "Tous les champs sont requis.", "error");
    return;
  }
  if (pwd.length < 8) {
    showMsg(msgEl, "Le nouveau mot de passe doit comporter au moins 8 caractères.", "error");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Vérification…";

  try {
    const res = await fetch(`${API_BASE}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, recovery_phrase: phrase, new_password: pwd }),
    });
    const data = await res.json();
    if (!res.ok) {
      showMsg(msgEl, data.error || "Phrase de secours invalide.", "error");
      return;
    }

    // Mise à jour de la session avec le nouveau token
    if (currentSession && currentSession.username.toLowerCase() === user.toLowerCase()) {
      currentSession.auth_token = data.auth_token;
      saveStoredSession(currentSession);
    }
    showMsg(msgEl, "Mot de passe réinitialisé avec succès ! Vous pouvez maintenant vous connecter.", "success");
    modal.querySelector("#btn-subtab-login")?.click();
  } catch (err) {
    showMsg(msgEl, "Erreur réseau.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Réinitialiser et se connecter";
  }
}

/**
 * Gestionnaire d'action : Droit à l'effacement RGPD.
 */
async function handleDeleteAccountAction() {
  if (!confirm("Voulez-vous vraiment effacer votre identité joueur et réinitialiser vos données de jeu ? Cette action est irréversible.")) {
    return;
  }

  if (currentSession && currentSession.auth_token) {
    try {
      await fetch(`${API_BASE}/delete-account`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${currentSession.auth_token}`,
        },
      });
    } catch (e) {
      // Poursuite locale
    }
  }

  clearStoredSession();
  window.location.reload();
}

function showMsg(el, text, type) {
  if (!el) return;
  el.textContent = text;
  el.className = `player-msg is-${type}`;
  el.style.display = "block";
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[m]));
}

/**
 * Initialisation automatique au chargement de la page.
 */
export async function initAuth() {
  // Attache le clic sur les badges Header une seule fois
  const badgeBtn = document.getElementById("player-badge");
  if (badgeBtn && !badgeBtn.dataset.authBound) {
    badgeBtn.dataset.authBound = "true";
    badgeBtn.addEventListener("click", () => openPlayerModal("profile"));
  }

  const welcomeBadge = document.getElementById("player-welcome-badge");
  if (welcomeBadge && !welcomeBadge.dataset.authBound) {
    welcomeBadge.dataset.authBound = "true";
    welcomeBadge.addEventListener("click", () => openPlayerModal("profile"));
  }

  // Pré-chargement immédiat depuis le localStorage
  let session = getStoredSession();
  const isFirstVisit = !session;

  if (session && session.username) {
    currentSession = session;
    updateHeaderBadge(session.username);
    refreshModalView();
  } else {
    updateHeaderBadge(null);
  }

  // Lancement de la synchronisation asynchrone avec le backend
  initAuthPromise = (async () => {
    try {
      const payload = session ? {
        player_id: session.player_id,
        auth_token: session.auth_token,
        username: session.username,
      } : {};

      const res = await fetch(`${API_BASE}/guest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        saveStoredSession(data);
        updateHeaderBadge(data.username);
        refreshModalView();

        if (isFirstVisit) {
          showWelcomeToast(data.username);
        }
      } else if (session) {
        // En cas de token expiré ou corrompu, recrée un profil propre
        clearStoredSession();
        const retryRes = await fetch(`${API_BASE}/guest`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (retryRes.ok) {
          const retryData = await retryRes.json();
          saveStoredSession(retryData);
          updateHeaderBadge(retryData.username);
          refreshModalView();
          if (isFirstVisit) {
            showWelcomeToast(retryData.username);
          }
        }
      }
    } catch (e) {
      // Mode déconnecté ou erreur réseau : s'il n'y a pas de session, génère un profil local
      if (!currentSession) {
        const localFallback = {
          player_id: "local-" + Math.random().toString(36).substring(2, 10),
          auth_token: "offline",
          username: "Castor" + Math.floor(100 + Math.random() * 900),
          can_change_username: true,
          is_claimed: false,
        };
        saveStoredSession(localFallback);
        updateHeaderBadge(localFallback.username);
        refreshModalView();
      }
    }
  })();

  return initAuthPromise;
}

// Auto-démarrage si le DOM est déjà prêt
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initAuth());
  } else {
    initAuth();
  }
}

