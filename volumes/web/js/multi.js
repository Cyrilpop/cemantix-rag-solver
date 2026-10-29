/**
 * Cémantix Solver — Moteur Client Mode Multijoueur 1v1
 * ======================================================
 * Gère l'ensemble du cycle de vie du duel :
 * - Création de salon, invitation via lien direct ou code court
 * - Saisie manuelle via formulaire
 * - Détection automatique des paramètres d'URL (?r=...&k=...)
 * - Mémorisation locale (LocalStorage) pour reprise multi-appareils
 * - Polling adaptatif non-bloquant (1.5s uniquement lors du tour adverse)
 * - Rendu anti-triche masqué (Même Mot) ou en clair (Mots Choisis)
 * - Modales de confirmation unifiées
 */

import {
  escapeHtml,
  initErrorHandling,
  showToast,
  getTierClass,
  getTierWeatherIcon,
  showConfirmDialog,
} from "./utils.js";
import { initTheme } from "./theme.js";
import { renderGuessesContainer } from "./render.js";

// Clé de stockage local des duels
const STORAGE_KEY = "cemantix_multi_sessions";

// État actif du client
const state = {
  currentRoomId: null,
  currentPlayerKey: null,
  currentRole: null, // "p1" ou "p2"
  sessionData: null,
  selectedMode: "same_word", // "same_word" ou "custom_words"
  selectedDiff: "moyen",
  pollInterval: null,
  isSubmitting: false,
};

// Rythme de la sonde en salle d'attente : réactive au départ, puis plus douce
// tant que rien ne bouge, et totalement suspendue quand l'onglet est masqué.
const WAITING_POLL_MIN_MS = 2000;
const WAITING_POLL_MAX_MS = 10000;

// Au retour d'onglet, on resonde immédiatement : l'adversaire a pu rejoindre
// pendant l'absence, et un salon qui met 10 s à réagir paraitrait cassé.
document.addEventListener("visibilitychange", () => {
  if (document.hidden || !state.currentRoomId) return;
  if (state.pollInterval) {
    clearTimeout(state.pollInterval);
    state.pollInterval = null;
  }
  if (document.getElementById("view-waiting")?.classList.contains("active")) {
    startWaitingPoll();
  }
});

// --------------------------------------------------------------------------
// 1. Initialisation & Routage Automatique par URL
// --------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initErrorHandling();
  initTheme();
  initLobbyEvents();
  initArenaEvents();
  initRoomActions();
  renderRecentGames();

  // Détection des paramètres d'URL (?r=DUEL-XXXXXXXX&k=J2-XXXXXXXX)
  const params = new URLSearchParams(window.location.search);
  const urlRoom = params.get("r") || params.get("room_id");
  const urlKey = params.get("k") || params.get("player_key");

  if (urlRoom) {
    const room = urlRoom.trim().toUpperCase();
    // On efface la clé de l'URL **avant** la requête : si la connexion échoue
    // ou traîne, le secret ne reste pas affiché dans la barre d'adresse.
    if (urlKey) stripKeyFromUrl(room);
    autoJoinFromUrl(room, urlKey ? urlKey.trim().toUpperCase() : null);
  }
});

/**
 * Efface la clé de salon de l'URL une fois qu'elle est en mémoire.
 *
 * Le lien d'invitation doit contenir la clé — c'est ce qui permet au second
 * joueur d'entrer. Mais rien ne justifie qu'elle **reste** dans la barre
 * d'adresse : la page est déjà chargée, la clé est en mémoire et dans
 * `sessionStorage`. Sans ce nettoyage, la clé survivrait dans l'historique du
 * navigateur, dans le champ d'adresse et dans toute capture d'écran, et
 * resterait cliquable des heures plus tard — notamment sur un ordinateur
 * partagé.
 *
 * Le `room_id` seul est conservé : il n'autorise aucune action (toute requête
 * exige une clé valide) et il permet de recharger la page sur le bon salon.
 */
function stripKeyFromUrl(roomId) {
  if (!window.history?.replaceState) return;
  const clean = roomId ? `/multi/?r=${encodeURIComponent(roomId)}` : "/multi/";
  if (window.location.pathname + window.location.search === clean) return;
  window.history.replaceState({}, "", clean);
}

/**
 * Actions des cartes de duel enregistrées localement (reprendre / oublier).
 *
 * La délégation remplace les gestionnaires `onclick="…"` construits par
 * concaténation de chaînes : ces derniers permettaient d'exécuter du code en
 * injectant une apostrophe dans un identifiant de salon. Le copier-coller des
 * mots, lui, est géré globalement par `initDelegatedActions` de utils.js.
 */
function initRoomActions() {
  document.addEventListener("click", (event) => {
    const deleteEl = event.target.closest("[data-delete-room]");
    if (deleteEl) {
      multiDeleteGame(deleteEl.getAttribute("data-delete-room"));
      return;
    }

    const resumeEl = event.target.closest("[data-resume-room]");
    if (resumeEl) {
      multiResumeGame(
        resumeEl.getAttribute("data-resume-room"),
        resumeEl.getAttribute("data-player-key")
      );
    }
  });
}

// --------------------------------------------------------------------------
// 2. Gestion du LocalStorage (Historique des Duels)
// --------------------------------------------------------------------------
function getStoredGames() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveGameToStorage(room_id, player_key, role, meta = {}) {
  const games = getStoredGames();
  games[room_id] = {
    room_id,
    player_key,
    role,
    mode: meta.mode || "same_word",
    opponent_name: meta.opponent_name || "Adversaire",
    difficulty: meta.difficulty || "moyen",
    updated_at: Date.now(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(games));
  renderRecentGames();
}

function removeGameFromStorage(room_id) {
  const games = getStoredGames();
  delete games[room_id];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(games));
  renderRecentGames();
}

function renderRecentGames() {
  const container = document.getElementById("recent-games-container");
  const countBadge = document.getElementById("active-games-count");
  if (!container) return;

  const games = Object.values(getStoredGames()).sort((a, b) => b.updated_at - a.updated_at);

  if (countBadge) {
    if (games.length > 0) {
      countBadge.textContent = games.length;
      countBadge.style.display = "inline-block";
    } else {
      countBadge.style.display = "none";
    }
  }

  if (games.length === 0) {
    container.innerHTML = `<p class="text-muted" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">Aucun duel enregistré sur cet appareil.</p>`;
    return;
  }

  container.innerHTML = games.map((g) => {
    const dateStr = new Date(g.updated_at).toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    const modeLabel = g.mode === "custom_words" ? "✍️ Mots Choisis" : "🎯 Même Mot";
    return `
      <div class="active-game-card">
        <div class="active-game-header">
          <span class="active-game-room">${escapeHtml(g.room_id)}</span>
          <span class="active-game-date">${escapeHtml(dateStr)}</span>
        </div>
        <div style="font-size: 0.88rem; color: var(--text-secondary, #8b949e);">
          <div>Variante : <strong>${modeLabel}</strong></div>
          <div>Adversaire : <strong>${escapeHtml(g.opponent_name || "En attente")}</strong></div>
          <div>Votre rôle : <strong style="color: #79c0ff;">${g.role === "p1" ? "Joueur 1 (Hôte)" : "Joueur 2 (Invité)"}</strong></div>
        </div>
        <div class="active-game-footer">
          <button type="button" class="btn btn-secondary btn-sm" data-delete-room="${escapeHtml(g.room_id)}">Supprimer</button>
          <button type="button" class="btn btn-primary btn-sm" data-resume-room="${escapeHtml(g.room_id)}" data-player-key="${escapeHtml(g.player_key)}">Reprendre</button>
        </div>
      </div>
    `;
  }).join("");
}

function multiResumeGame(roomId, playerKey) {
  connectToRoom(roomId, playerKey);
}

async function multiDeleteGame(roomId) {
  const confirmed = await showConfirmDialog({
    title: "Oublier ce duel ?",
    message: `Voulez-vous retirer le salon ${roomId} de cet appareil ? (La partie restera active sur le serveur).`,
    confirmText: "Retirer",
    cancelText: "Annuler",
    confirmType: "danger",
    icon: "🗑️",
  });
  if (confirmed) {
    removeGameFromStorage(roomId);
    showToast("Salon retiré de l'historique local.");
  }
};

// --------------------------------------------------------------------------
// 3. Navigation entre les Vues Principales
// --------------------------------------------------------------------------
function switchView(viewName) {
  document.querySelectorAll(".multi-view-section").forEach((sec) => sec.classList.remove("active"));
  const target = document.getElementById(`view-${viewName}`);
  if (target) {
    target.classList.add("active");
  }

  // Arrêt du polling si on retourne au lobby
  if (viewName === "lobby") {
    stopPolling();
  }
}

// --------------------------------------------------------------------------
// 4. Événements du Lobby (Créer / Rejoindre)
// --------------------------------------------------------------------------
function initLobbyEvents() {
  // Onglets du lobby
  document.querySelectorAll(".lobby-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".lobby-tab-btn").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      const tab = btn.dataset.lobbyTab;
      document.querySelectorAll(".lobby-panel").forEach((p) => (p.style.display = "none"));
      const panel = document.getElementById(`lobby-panel-${tab}`);
      if (panel) panel.style.display = "block";
    });
  });

  // Sélection du mode de jeu (cartes interactives)
  document.querySelectorAll(".mode-card").forEach((card) => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".mode-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      state.selectedMode = card.dataset.modeSelect;

      const customWordSection = document.getElementById("multi-custom-word-section");
      const diffSection = document.getElementById("multi-diff-section");
      if (state.selectedMode === "custom_words") {
        if (customWordSection) customWordSection.style.display = "flex";
        if (diffSection) diffSection.style.display = "none";
      } else {
        if (customWordSection) customWordSection.style.display = "none";
        if (diffSection) diffSection.style.display = "flex";
      }
    });
  });

  // Sélecteur de difficulté
  document.querySelectorAll("#multi-diff-group .pill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#multi-diff-group .pill-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.selectedDiff = btn.dataset.diff;
    });
  });

  // Bouton "Créer le Salon"
  const btnCreate = document.getElementById("btn-create-game");
  if (btnCreate) {
    btnCreate.addEventListener("click", handleCreateGame);
  }

  // Formulaire "Rejoindre avec un Code"
  const formJoin = document.getElementById("form-join-game");
  if (formJoin) {
    formJoin.addEventListener("submit", handleJoinGame);
  }

  // Boutons de copie salle d'attente
  const btnCopyCode = document.getElementById("btn-copy-room-code");
  if (btnCopyCode) {
    btnCopyCode.addEventListener("click", () => {
      const code = document.getElementById("waiting-room-code")?.textContent;
      if (code) {
        navigator.clipboard.writeText(code);
        showToast(`📋 Code ${code} copié !`);
      }
    });
  }

  const btnCopyUrl = document.getElementById("btn-copy-share-url");
  if (btnCopyUrl) {
    btnCopyUrl.addEventListener("click", () => {
      const urlInput = document.getElementById("waiting-share-url-input");
      if (urlInput?.value) {
        navigator.clipboard.writeText(urlInput.value);
        showToast("🔗 Lien d'invitation direct copié !");
      }
    });
  }

  // Accéder directement à l'arène depuis la salle d'attente
  const btnEnterArena = document.getElementById("btn-waiting-enter-arena");
  if (btnEnterArena) {
    btnEnterArena.addEventListener("click", () => {
      switchView("arena");
      startPolling();
    });
  }

  // Retour lobby depuis salle d'attente
  const btnBackLobby = document.getElementById("btn-waiting-back-lobby");
  if (btnBackLobby) {
    btnBackLobby.addEventListener("click", () => {
      switchView("lobby");
    });
  }

  // Validation mot personnalisé en attente
  const btnSubmitWaitingWord = document.getElementById("btn-submit-waiting-word");
  if (btnSubmitWaitingWord) {
    btnSubmitWaitingWord.addEventListener("click", handleSetupWaitingWord);
  }
}

// --------------------------------------------------------------------------
// 5. Actions d'API : Création & Connexion
// --------------------------------------------------------------------------
async function handleCreateGame() {
  const nameInput = document.getElementById("create-player-name");
  const customWordInput = document.getElementById("create-custom-word");
  const playerName = nameInput ? nameInput.value.trim() : "Joueur 1";
  const customTarget = (state.selectedMode === "custom_words" && customWordInput) ? customWordInput.value.trim() : null;

  try {
    const res = await fetch("/api/multi/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: state.selectedMode,
        difficulty: state.selectedDiff,
        player_name: playerName,
        custom_target: customTarget,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showToast(data.error || "Erreur lors de la création du salon.");
      return;
    }

    state.currentRoomId = data.room_id;
    state.currentPlayerKey = data.player_key;
    state.currentRole = data.role;
    state.sessionData = data.session;

    saveGameToStorage(data.room_id, data.player_key, data.role, {
      mode: state.selectedMode,
      opponent_name: "En attente",
      difficulty: state.selectedDiff,
    });

    // L'URL ne garde que le code de salon : la clé reste en mémoire (voir
    // stripKeyFromUrl) et ne s'installe pas dans l'historique du navigateur.
    stripKeyFromUrl(data.room_id);

    openWaitingRoom(data);
  } catch (err) {
    showToast("Impossible de contacter le serveur.");
  }
}

async function handleJoinGame() {
  const roomInput = document.getElementById("join-room-code");
  const keyInput = document.getElementById("join-player-key");
  const nameInput = document.getElementById("join-player-name");

  const roomCode = roomInput ? roomInput.value.trim().toUpperCase() : "";
  const playerKey = keyInput ? keyInput.value.trim().toUpperCase() : null;
  const playerName = nameInput ? nameInput.value.trim() : "Joueur 2";

  if (!roomCode) {
    showToast("Veuillez saisir un Code Salon valide.");
    return;
  }

  await connectToRoom(roomCode, playerKey, playerName);
}

async function autoJoinFromUrl(roomCode, playerKey) {
  showToast(`Connexion au salon ${roomCode}...`);
  await connectToRoom(roomCode, playerKey || "", "");
}

async function connectToRoom(roomId, playerKey = "", playerName = "") {
  try {
    const res = await fetch("/api/multi/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: roomId || "",
        player_key: playerKey || "",
        player_name: playerName || "",
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showToast(data.error || "Impossible de rejoindre ce salon.");
      if (res.status === 404 && roomId) {
        removeGameFromStorage(roomId);
        if (window.location.search.includes(roomId)) {
          window.history.replaceState({}, "", "/multi/");
        }
      }
      return;
    }

    state.currentRoomId = data.room_id;
    state.currentPlayerKey = data.player_key;
    state.currentRole = data.role;
    state.sessionData = data.session;

    saveGameToStorage(data.room_id, data.player_key, data.role, {
      mode: data.session?.mode || "same_word",
      opponent_name: data.session?.opponent?.name || "Adversaire",
      difficulty: data.session?.difficulty || "moyen",
    });

    // Idem : le code de salon seul reste visible, la clé disparaît de l'URL.
    stripKeyFromUrl(data.room_id);

    // Si on a besoin de choisir un mot en mode Mots Choisis
    if (data.session.state === "waiting_words" && data.session.i_need_to_set_word) {
      openWaitingRoom(data);
      return;
    }

    // Sinon, on entre directement dans l'arène de jeu
    switchView("arena");
    updateArenaUI(data.session);
    startPolling();
  } catch (err) {
    showToast("Erreur de connexion au serveur de jeu.");
  }
}

function openWaitingRoom(data) {
  const roomCodeEl = document.getElementById("waiting-room-code");
  const shareInputEl = document.getElementById("waiting-share-url-input");
  const customWordPrompt = document.getElementById("waiting-custom-word-prompt");

  if (roomCodeEl) roomCodeEl.textContent = data.room_id;
  if (shareInputEl) {
    const origin = window.location.origin;
    shareInputEl.value = `${origin}/multi/?r=${data.room_id}&k=${data.guest_key || ""}`;
  }

  // Si le joueur doit définir un mot secret
  if (customWordPrompt) {
    if (data.session?.waiting_for_words && data.session?.i_need_to_set_word) {
      customWordPrompt.style.display = "block";
    } else {
      customWordPrompt.style.display = "none";
    }
  }

  switchView("waiting");
  startWaitingPoll();
}

async function handleSetupWaitingWord() {
  const input = document.getElementById("waiting-custom-word-input");
  const word = input ? input.value.trim() : "";
  if (!word) {
    showToast("Veuillez saisir un mot.");
    return;
  }

  try {
    const res = await fetch("/api/multi/setup-word", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: state.currentRoomId,
        player_key: state.currentPlayerKey,
        word: word,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showToast(data.error || "Mot invalide.");
      return;
    }

    showToast("Mot validé avec succès !");
    document.getElementById("waiting-custom-word-prompt").style.display = "none";
    state.sessionData = data;
    if (data.state === "in_progress") {
      switchView("arena");
      updateArenaUI(data);
      startPolling();
    }
  } catch (err) {
    showToast("Erreur lors de la validation du mot.");
  }
}

// --------------------------------------------------------------------------
// 6. Arène de Jeu & Interaction Temps Réel
// --------------------------------------------------------------------------
function initArenaEvents() {
  // Formulaire de proposition de mot
  const guessForm = document.getElementById("arena-guess-form");
  if (guessForm) {
    guessForm.addEventListener("submit", handleArenaGuess);
  }

  const arenaInput = document.getElementById("arena-word-input");
  if (arenaInput) {
    arenaInput.addEventListener("input", hideMultiFeedback);
  }

  // Demande d'indice
  const btnHint = document.getElementById("arena-hint-btn");
  if (btnHint) {
    btnHint.addEventListener("click", handleArenaHint);
  }

  // Déclaration de forfait (connecté à la modale unifiée)
  const btnGiveup = document.getElementById("arena-giveup-btn");
  if (btnGiveup) {
    btnGiveup.addEventListener("click", handleArenaGiveup);
  }

  // Bouton partager lien depuis l'arène
  const btnShare = document.getElementById("arena-share-btn");
  if (btnShare) {
    btnShare.addEventListener("click", () => {
      const origin = window.location.origin;
      const guestKey = state.sessionData?.guest_key || "";
      const url = `${origin}/multi/?r=${state.currentRoomId}${guestKey ? `&k=${guestKey}` : ""}`;
      navigator.clipboard.writeText(url);
      showToast("🔗 Lien d'invitation copié !");
    });
  }

  // Quitter vers le lobby
  const btnLeave = document.getElementById("arena-leave-btn");
  if (btnLeave) {
    btnLeave.addEventListener("click", () => {
      switchView("lobby");
    });
  }

  // Relancer depuis l'écran de fin
  const btnNewFromOver = document.getElementById("btn-gameover-new");
  if (btnNewFromOver) {
    btnNewFromOver.addEventListener("click", () => {
      switchView("lobby");
    });
  }

  // Sélecteur d'onglets mobile (duel 1v1)
  const mobileToggleBtns = document.querySelectorAll("#mobile-duel-toggle .mobile-toggle-btn");
  const resultsGrid = document.querySelector(".multi-results-grid");
  mobileToggleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      mobileToggleBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const target = btn.dataset.target;
      if (resultsGrid) {
        resultsGrid.classList.remove("show-player", "show-opponent");
        resultsGrid.classList.add(`show-${target}`);
      }
    });
  });
}

function showMultiFeedback(msg, type = "error") {
  const fb = document.getElementById("arena-feedback");
  if (!fb) return;
  fb.textContent = msg;
  fb.className = `game-feedback is-${type}`;
  fb.style.display = "block";
}

function hideMultiFeedback() {
  const fb = document.getElementById("arena-feedback");
  if (fb) fb.style.display = "none";
}

async function handleArenaGuess(e) {
  if (e) e.preventDefault();
  if (state.isSubmitting) return;

  const input = document.getElementById("arena-word-input");
  const rawWord = input ? input.value.trim() : "";
  if (!rawWord) return;

  if (state.sessionData?.is_finished) {
    showMultiFeedback("Ce duel est terminé. Cliquez sur « Nouveau duel » pour relancer une partie.", "warning");
    return;
  }

  if (!state.sessionData?.is_my_turn) {
    showMultiFeedback("⏳ Ce n'est pas votre tour de jouer ! Attendez le coup adverse.", "warning");
    return;
  }

  // Vérification de doublon côté joueur
  const myGuesses = state.sessionData?.me?.guesses || [];
  if (myGuesses.some((g) => g.word.toLowerCase() === rawWord.toLowerCase())) {
    showMultiFeedback(`Vous avez déjà testé le mot « ${rawWord.toUpperCase()} » dans ce duel.`, "warning");
    if (input) input.select();
    return;
  }

  state.isSubmitting = true;
  const submitBtn = document.getElementById("arena-submit-btn");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch("/api/multi/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: state.currentRoomId,
        player_key: state.currentPlayerKey,
        word: rawWord,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showMultiFeedback(data.error || "Mot invalide ou non reconnu.", "error");
      if (input) input.select();
      return;
    }

    hideMultiFeedback();
    input.value = "";
    state.sessionData = data;
    updateArenaUI(data);

    // Si le tour passe à l'adversaire, enclencher le polling
    if (!data.is_my_turn && !data.is_finished) {
      startPolling();
    }
  } catch (err) {
    showMultiFeedback("Erreur de communication avec le serveur.", "error");
  } finally {
    state.isSubmitting = false;
    if (submitBtn) submitBtn.disabled = false;
    if (input && state.sessionData?.is_my_turn && !state.sessionData?.is_finished) {
      input.focus();
    }
  }
}

async function handleArenaHint() {
  if (!state.sessionData?.is_my_turn) {
    showToast("⏳ Vous ne pouvez demander un indice que pendant votre tour.");
    return;
  }

  const remaining = state.sessionData?.me?.hints_remaining || 0;
  if (remaining <= 0) {
    showToast("⚠️ Vous avez déjà utilisé tous vos indices autorisés.");
    return;
  }

  const confirmed = await showConfirmDialog({
    title: "Consommer un Indice ?",
    message: "Demander un indice consommera 1 tour et passera immédiatement la main à votre adversaire.",
    confirmText: "Obtenir l'indice",
    cancelText: "Annuler",
    confirmType: "primary",
    icon: "💡",
  });

  if (!confirmed) return;

  try {
    const res = await fetch("/api/multi/hint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: state.currentRoomId,
        player_key: state.currentPlayerKey,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showToast(data.error || "Erreur lors de la demande d'indice.");
      return;
    }

    if (data.hint_awarded) {
      showToast(`💡 Indice ${data.hint_awarded.tier_label} obtenu : « ${data.hint_awarded.word.toUpperCase()} » (${data.hint_awarded.score}°C)`);
    }

    state.sessionData = data;
    updateArenaUI(data);
    startPolling();
  } catch (err) {
    showToast("Erreur de communication avec le serveur.");
  }
}

async function handleArenaGiveup() {
  const confirmed = await showConfirmDialog({
    title: "Déclarer Forfait ?",
    message: "Êtes-vous sûr de vouloir abandonner ? Votre adversaire remportera la victoire et les mots secrets seront révélés.",
    confirmText: "Déclarer Forfait",
    cancelText: "Continuer le duel",
    confirmType: "danger",
    icon: "🏳️",
  });

  if (!confirmed) return;

  try {
    const res = await fetch("/api/multi/giveup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: state.currentRoomId,
        player_key: state.currentPlayerKey,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) {
      showToast(data.error || "Erreur lors du forfait.");
      return;
    }

    state.sessionData = data;
    updateArenaUI(data);
    stopPolling();
  } catch (err) {
    showToast("Erreur de communication avec le serveur.");
  }
}

// --------------------------------------------------------------------------
// 7. Polling Adaptatif Intelligent (Smart Polling)
// --------------------------------------------------------------------------
function startPolling() {
  stopPolling();
  
  const pollTick = async () => {
    if (!state.currentRoomId || !state.currentPlayerKey) return;
    if (state.sessionData?.is_finished) {
      stopPolling();
      return;
    }

    try {
      // La cle du joueur voyage dans le corps de la requete, pas dans l'URL :
      // un GET mettrait le secret dans la ligne de requete, donc dans les logs
      // du proxy et dans l'historique. Le POST /api/multi/status est equivalent.
      const res = await fetch("/api/multi/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_id: state.currentRoomId,
          player_key: state.currentPlayerKey,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.valid) {
          const previousTurn = state.sessionData?.is_my_turn;
          state.sessionData = data;
          updateArenaUI(data);

          if (!previousTurn && data.is_my_turn) {
            showToast("🟢 L'adversaire a joué ! C'est à votre tour !");
          }

          if (data.is_finished) {
            stopPolling();
            return;
          }
        }
      }
    } catch {
      // Échec temporaire silencieux
    }

    if (!state.pollInterval) return;

    // Rythme adaptatif : 2.5s si tour adverse, 5s si c'est notre tour
    const delay = state.sessionData?.is_my_turn ? 5000 : 2500;
    state.pollInterval = setTimeout(pollTick, delay);
  };

  const initialDelay = state.sessionData?.is_my_turn ? 4000 : 2000;
  state.pollInterval = setTimeout(pollTick, initialDelay);
}

function stopPolling() {
  if (state.pollInterval) {
    clearTimeout(state.pollInterval);
    state.pollInterval = null;
  }
}

function startWaitingPoll() {
  stopPolling();
  // Sonde adaptative : la salle d'attente peut rester ouverte longtemps (le temps
  // que l'ami rejoigne). Un intervalle fixe de 2 s générait ~1800 requêtes/heure
  // d'onglet ouvert, y compris en arrière-plan. On part sur 2 s pour une détection
  // réactive, on remonte progressivement à 10 s si rien ne bouge, et on met tout en
  // pause dès que l'onglet est masqué — le `visibilitychange` relance une sonde
  // immédiate au retour pour ne pas donner l'impression d'un salon figé.
  let delay = WAITING_POLL_MIN_MS;

  const tick = async () => {
    if (!state.currentRoomId || !state.currentPlayerKey) return;
    if (document.hidden) return;
    try {
      // La cle du joueur voyage dans le corps de la requete, pas dans l'URL :
      // un GET mettrait le secret dans la ligne de requete, donc dans les logs
      // du proxy et dans l'historique. Le POST /api/multi/status est equivalent.
      const res = await fetch("/api/multi/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_id: state.currentRoomId,
          player_key: state.currentPlayerKey,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.valid) return;

      const progressed = data.state !== state.sessionData?.state;
      state.sessionData = data;
      if (progressed) delay = WAITING_POLL_MIN_MS;
      else delay = Math.min(delay * 1.6, WAITING_POLL_MAX_MS);

      // Si l'adversaire a rejoint et que la partie est prête
      if (data.state === "in_progress") {
        showToast("🎮 Votre adversaire a rejoint le duel !");
        stopPolling();
        switchView("arena");
        updateArenaUI(data);
        if (!data.is_my_turn) {
          startPolling();
        }
        return;
      }
    } catch {
      // Silence
    }
    state.pollInterval = setTimeout(tick, delay);
  };

  state.pollInterval = setTimeout(tick, delay);
}

// --------------------------------------------------------------------------
// 8. Rendu & Mise à Jour de l'Interface de Duel
// --------------------------------------------------------------------------
function updateArenaUI(data) {
  if (!data) return;

  // Badges d'en-tête
  const roomBadge = document.getElementById("arena-room-badge");
  const modeBadge = document.getElementById("arena-mode-badge");
  const diffBadge = document.getElementById("arena-diff-badge");
  const hintCount = document.getElementById("arena-hint-count");

  if (roomBadge) roomBadge.textContent = data.room_id;
  if (modeBadge) {
    modeBadge.textContent = data.mode === "custom_words" ? "Mots Choisis" : "Même Mot";
    modeBadge.className = data.mode === "custom_words" ? "mode-card-badge badge-custom-word" : "mode-card-badge badge-same-word";
  }
  if (diffBadge) diffBadge.textContent = data.difficulty;
  if (hintCount) hintCount.textContent = `${data.me?.hints_remaining || 0}/3`;

  // Bandeau de tour
  const turnBanner = document.getElementById("arena-turn-banner");
  const turnBannerText = document.getElementById("turn-banner-text");
  const turnCount = document.getElementById("arena-turn-count");
  const wordInput = document.getElementById("arena-word-input");
  const submitBtn = document.getElementById("arena-submit-btn");

  if (turnCount) turnCount.textContent = `Tour #${data.turn_no || 1}`;

  if (data.is_finished) {
    if (turnBanner) {
      turnBanner.className = "turn-banner";
      turnBanner.style.background = "rgba(137, 87, 229, 0.2)";
      turnBanner.style.borderColor = "#8957e5";
    }
    if (turnBannerText) turnBannerText.textContent = "Partie terminée";
    if (wordInput) {
      wordInput.disabled = true;
      wordInput.placeholder = "Partie terminée.";
    }
    if (submitBtn) submitBtn.disabled = true;
  } else if (data.is_my_turn) {
    if (turnBanner) turnBanner.className = "turn-banner turn-banner-my-turn";
    if (turnBannerText) turnBannerText.textContent = "À vous de jouer !";
    if (wordInput) {
      wordInput.disabled = false;
      wordInput.placeholder = "Entrez un mot français pour attaquer ce tour...";
    }
    if (submitBtn) submitBtn.disabled = false;
  } else {
    if (turnBanner) turnBanner.className = "turn-banner turn-banner-opp-turn";
    if (turnBannerText) turnBannerText.textContent = "En attente du coup adverse...";
    if (wordInput) {
      wordInput.disabled = true;
      wordInput.placeholder = "En attente du tour de votre adversaire...";
    }
    if (submitBtn) submitBtn.disabled = true;
  }

  // HUD Joueur
  const myName = document.getElementById("hud-my-name");
  const myTarget = document.getElementById("hud-my-target");
  const myGauge = document.getElementById("hud-my-gauge");
  const myPct = document.getElementById("hud-my-pct");
  const myMetric = document.getElementById("hud-my-metric");

  if (myName) myName.textContent = data.me?.name || "Vous";
  if (myTarget) myTarget.textContent = data.me?.target ? data.me.target.toUpperCase() : "🔒 Secret";
  if (myGauge) myGauge.style.width = `${data.me?.progress_pct || 0}%`;
  if (myPct) myPct.textContent = `${data.me?.progress_pct || 0}%`;
  if (myMetric) {
    const p = data.me?.best_permille;
    const s = data.me?.best_score;
    myMetric.textContent = p ? `${p} ‰ (${s}°C)` : `${s || 0}°C`;
  }

  // HUD Adversaire
  const oppName = document.getElementById("hud-opp-name");
  const oppTarget = document.getElementById("hud-opp-target");
  const oppGauge = document.getElementById("hud-opp-gauge");
  const oppPct = document.getElementById("hud-opp-pct");
  const oppMetric = document.getElementById("hud-opp-metric");

  if (oppName) oppName.textContent = data.opponent?.name || "Adversaire";
  if (oppTarget) oppTarget.textContent = data.opponent?.target ? data.opponent.target.toUpperCase() : "🔒 Secret";
  if (oppGauge) oppGauge.style.width = `${data.opponent?.progress_pct || 0}%`;
  if (oppPct) oppPct.textContent = `${data.opponent?.progress_pct || 0}%`;
  if (oppMetric) {
    const p = data.opponent?.best_permille;
    const s = data.opponent?.best_score;
    oppMetric.textContent = p ? `${p} ‰ (${s}°C)` : `${s || 0}°C`;
  }

  // Listes de mots sous forme de tuiles standard
  renderGuessesList("my-guesses-list", "my-guesses-count", "mobile-player-count", data.me?.history || [], false, true);
  const isOppMasked = data.mode === "same_word" && !data.is_finished;
  renderGuessesList("opp-guesses-list", "opp-guesses-count", "mobile-opp-count", data.opponent?.history || [], isOppMasked, false);

  const oppMaskIndicator = document.getElementById("opp-mask-indicator");
  if (oppMaskIndicator) {
    oppMaskIndicator.textContent = isOppMasked ? "Mots masqués 🔒" : "Mots en clair 👀";
  }

  // Bannière Game Over
  const gameoverBanner = document.getElementById("arena-gameover-banner");
  if (gameoverBanner) {
    if (data.is_finished) {
      gameoverBanner.style.display = "flex";
      renderGameOverBanner(data);
    } else {
      gameoverBanner.style.display = "none";
    }
  }
}

function renderGuessesList(containerId, countId, mobileCountId, guesses, isMasked, isPlayer) {
  const container = document.getElementById(containerId);
  const countEl = document.getElementById(countId);
  const mobileCountEl = document.getElementById(mobileCountId);
  if (!container) return;

  const countStr = String(guesses ? guesses.length : 0);
  if (countEl && countEl.textContent !== countStr) countEl.textContent = countStr;
  if (mobileCountEl && mobileCountEl.textContent !== countStr) mobileCountEl.textContent = countStr;

  renderGuessesContainer(container, guesses, { isMasked, isPlayer });
}

function renderGameOverBanner(data) {
  const iconEl = document.getElementById("gameover-icon");
  const titleEl = document.getElementById("gameover-title");
  const descEl = document.getElementById("gameover-desc");
  const secretsBox = document.getElementById("gameover-secrets-box");
  const banner = document.getElementById("arena-gameover-banner");

  if (!banner) return;

  if (data.has_won) {
    banner.className = "gameover-banner gameover-win";
    if (iconEl) iconEl.textContent = "🏆";
    if (titleEl) titleEl.textContent = "Victoire Éclatante !";
    if (descEl) descEl.textContent = "Félicitations ! Vous avez démasqué votre mot secret avant votre adversaire !";
  } else if (data.has_lost) {
    banner.className = "gameover-banner gameover-lose";
    if (iconEl) iconEl.textContent = "💀";
    if (titleEl) titleEl.textContent = "Défaite...";
    if (descEl) descEl.textContent = "Votre adversaire a trouvé son mot en premier ou vous avez abandonné.";
  } else {
    banner.className = "gameover-banner";
    if (iconEl) iconEl.textContent = "🤝";
    if (titleEl) titleEl.textContent = "Égalité !";
    if (descEl) descEl.textContent = "Les deux joueurs ont trouvé le mot lors de la même manche !";
  }

  if (secretsBox) {
    if (data.mode === "same_word") {
      secretsBox.innerHTML = `
        <div class="secret-reveal-badge">
          <span>Mot secret commun :</span> <strong style="color: #3fb950; font-size: 1.1rem;">${escapeHtml((data.me?.target || data.opponent?.target || "INCONNU").toUpperCase())}</strong>
        </div>
      `;
    } else {
      secretsBox.innerHTML = `
        <div class="secret-reveal-badge">
          <span>Votre cible :</span> <strong style="color: #79c0ff; font-size: 1.1rem;">${escapeHtml((data.me?.target || "INCONNU").toUpperCase())}</strong>
        </div>
        <div class="secret-reveal-badge">
          <span>Cible adverse :</span> <strong style="color: #a371f7; font-size: 1.1rem;">${escapeHtml((data.opponent?.target || "INCONNU").toUpperCase())}</strong>
        </div>
      `;
    }
  }
}
