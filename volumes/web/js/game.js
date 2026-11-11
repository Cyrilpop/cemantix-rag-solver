/**
 * Cémantix Solver — Moteur de Jeu Interactif (Défi du Jour & Mode Illimité)
 * Jalon M15 : Mot du jour autonome, classement des gagnants, anti-spoiler & indices IA
 */
import { escapeHtml, getTierClass, getTierWeatherIcon, showToast, showConfirmDialog } from "./utils.js";
import { getStoredSession, getPlayerUsername } from "./auth.js";

const GAME_STORAGE_KEY = "cemantix_game_state_v3";

export const gameState = {
  gameId: null,
  mode: "daily",
  difficulty: "normal",
  puzzleId: "----",
  puzzleDate: null,
  isWon: false,
  isGivenUp: false,
  tries: 0,
  topGuesses: [],
  allGuesses: [],
  history: [],
  lastGuess: null,
  secret: null,
  hints: [],
  hintsRevealed: [],
  leaderboard: [],
};

export function getParisTodayDate() {
  try {
    const formatter = new Intl.DateTimeFormat("fr-CA", {
      timeZone: "Europe/Paris",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    return formatter.format(new Date()); // Format standard YYYY-MM-DD
  } catch (_) {
    return new Date().toISOString().slice(0, 10);
  }
}

export function formatFrenchDate(dateStr) {
  if (!dateStr) return "";
  try {
    const parts = String(dateStr).split("-");
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(year, month, day);
      return d.toLocaleDateString("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    }
  } catch (_) {}
  return String(dateStr);
}

const modeSessions = {
  daily: null,
  unlimited: null,
};

function getLocalPlayerId() {
  const session = getStoredSession();
  return session?.player_id || session?.playerId || session?.id || null;
}

export function initGame() {
  const modeDailyBtn = document.getElementById("mode-daily-btn");
  const modeUnlimitedBtn = document.getElementById("mode-unlimited-btn");
  const difficultyBtns = document.querySelectorAll("#difficulty-group .pill-btn");
  const gameNewBtn = document.getElementById("game-new-btn");
  const winNewGameBtn = document.getElementById("win-new-game-btn");
  const gameGiveupBtn = document.getElementById("game-giveup-btn");
  const gameHintBtn = document.getElementById("game-hint-btn");
  const gameGuessForm = document.getElementById("game-guess-form");
  const gameWordInput = document.getElementById("game-word-input");
  const refreshLeaderboardBtn = document.getElementById("refresh-leaderboard-btn");

  // Modales M15
  const hintModal = document.getElementById("hint-choice-modal");
  const hintModalClose = document.getElementById("hint-modal-close");
  const hintChoiceWordBtn = document.getElementById("hint-choice-word-btn");
  const hintChoicePhraseBtn = document.getElementById("hint-choice-phrase-btn");

  const trajectoryModal = document.getElementById("trajectory-modal");
  const trajectoryModalClose = document.getElementById("trajectory-modal-close");

  if (modeDailyBtn) {
    modeDailyBtn.addEventListener("click", () => setGameMode("daily"));
  }
  if (modeUnlimitedBtn) {
    modeUnlimitedBtn.addEventListener("click", () => setGameMode("unlimited"));
  }

  difficultyBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.diff) setGameDifficulty(btn.dataset.diff);
    });
  });

  if (gameNewBtn) {
    gameNewBtn.addEventListener("click", () => {
      if (gameState.mode === "daily") {
        if (gameState.isWon || gameState.isGivenUp) {
          showConfirmDialog({
            title: "Défi du Jour terminé",
            message: "Vous avez déjà complété le mot du jour pour aujourd'hui ! Le prochain mot sera disponible demain à 00h00. Souhaitez-vous vous entraîner en mode illimité ?",
            icon: "📅",
            confirmText: "Passer en mode illimité",
            cancelText: "Rester sur le défi du jour",
          }).then((confirmed) => {
            if (confirmed) {
              setGameMode("unlimited");
            }
          });
        } else {
          showConfirmDialog({
            title: "Défi du Jour en cours",
            message: "Le mot du jour est unique et partagé par tous les joueurs. Vos essais sont conservés pour le classement et ne peuvent pas être réinitialisés. Pour jouer de nouvelles parties, passez en mode illimité.",
            icon: "ℹ️",
            confirmText: "Passer en mode illimité",
            cancelText: "Continuer le défi du jour",
          }).then((confirmed) => {
            if (confirmed) {
              setGameMode("unlimited");
            }
          });
        }
        return;
      }
      startNewGame(gameState.mode, gameState.difficulty, true);
    });
  }
  if (winNewGameBtn) {
    winNewGameBtn.addEventListener("click", () => {
      if (gameState.mode === "daily") {
        setGameMode("unlimited");
      } else {
        startNewGame(gameState.mode, gameState.difficulty, true);
      }
    });
  }
  if (gameGiveupBtn) {
    gameGiveupBtn.addEventListener("click", giveUpGame);
  }
  if (gameHintBtn) {
    gameHintBtn.addEventListener("click", openHintModalOrRequest);
  }

  if (refreshLeaderboardBtn) {
    refreshLeaderboardBtn.addEventListener("click", () => {
      fetchLeaderboard();
      showToast("Classement actualisé.");
    });
  }

  // Écouteurs Modale Choix d'Indice
  if (hintModalClose && hintModal) {
    hintModalClose.addEventListener("click", () => {
      hintModal.style.display = "none";
    });
    hintModal.addEventListener("click", (e) => {
      if (e.target === hintModal) hintModal.style.display = "none";
    });
  }

  if (hintChoiceWordBtn) {
    hintChoiceWordBtn.addEventListener("click", () => {
      if (hintModal) hintModal.style.display = "none";
      executeHintRequest("word");
    });
  }
  if (hintChoicePhraseBtn) {
    hintChoicePhraseBtn.addEventListener("click", () => {
      if (hintModal) hintModal.style.display = "none";
      executeHintRequest("phrase");
    });
  }

  // Écouteurs Modale Trajectoire
  if (trajectoryModalClose && trajectoryModal) {
    trajectoryModalClose.addEventListener("click", () => {
      trajectoryModal.style.display = "none";
    });
    trajectoryModal.addEventListener("click", (e) => {
      if (e.target === trajectoryModal) trajectoryModal.style.display = "none";
    });
  }

  if (gameGuessForm) {
    gameGuessForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const word = gameWordInput ? gameWordInput.value : "";
      submitGuess(word);
    });
  }

  // Restauration de l'état
  const hasSavedGame = loadGameState();
  restoreGameUI();
  if (hasSavedGame && gameState.gameId) {
    resumeGame(gameState.gameId);
  } else {
    startNewGame(gameState.mode || "daily", gameState.difficulty || "normal", false);
  }

  fetchLeaderboard();
  setTimeout(() => gameWordInput?.focus(), 100);
}

function saveGameState() {
  try {
    const mode = gameState.mode || "daily";
    const payload = {
      gameId: gameState.gameId,
      mode: gameState.mode,
      difficulty: gameState.difficulty,
      puzzleId: gameState.puzzleId,
      puzzleDate: gameState.puzzleDate,
      isWon: gameState.isWon,
      isGivenUp: gameState.isGivenUp,
      tries: gameState.tries,
      topGuesses: gameState.topGuesses,
      allGuesses: gameState.allGuesses,
      history: gameState.history,
      lastGuess: gameState.lastGuess,
      secret: gameState.secret,
      hints: gameState.hints || [],
      hintsRevealed: gameState.hintsRevealed || [],
      savedAt: Date.now(),
    };
    modeSessions[mode] = payload;
    localStorage.setItem(GAME_STORAGE_KEY, JSON.stringify({
      currentMode: mode,
      sessions: modeSessions,
    }));
  } catch (e) {
    console.warn("Erreur sauvegarde locale:", e);
  }
}

function loadGameState(targetMode) {
  try {
    let raw = localStorage.getItem(GAME_STORAGE_KEY);
    if (!raw) {
      raw = localStorage.getItem("cemantix_game_state_v2");
    }
    if (!raw) return false;

    const data = JSON.parse(raw);
    if (!data) return false;

    let sessionToLoad = null;
    if (data.sessions) {
      modeSessions.daily = data.sessions.daily || null;
      modeSessions.unlimited = data.sessions.unlimited || null;
      const mode = targetMode || data.currentMode || gameState.mode || "daily";
      sessionToLoad = modeSessions[mode];
    } else if (data.gameId) {
      sessionToLoad = data;
      modeSessions[data.mode || "daily"] = { ...data };
    }

    if (!sessionToLoad || !sessionToLoad.gameId) return false;

    // Pour le mode Défi du Jour : si la date sauvegardée n'est pas celle d'aujourd'hui (fuseau Paris),
    // la session locale est obsolète et ne doit pas restaurer l'écran de victoire de la veille.
    const requestedMode = targetMode || data.currentMode || gameState.mode || "daily";
    if (requestedMode === "daily") {
      const todayParis = getParisTodayDate();
      if (sessionToLoad.puzzleDate && sessionToLoad.puzzleDate !== todayParis) {
        modeSessions.daily = null;
        return false;
      }
    }

    if (sessionToLoad.savedAt && (Date.now() - sessionToLoad.savedAt > 24 * 3600 * 1000)) {
      return false;
    }

    Object.assign(gameState, sessionToLoad);
    return true;
  } catch (_) {
    return false;
  }
}

function restoreGameUI() {
  const gamePuzzleBadge = document.getElementById("game-puzzle-badge");
  const gameModeBadge = document.getElementById("game-mode-badge");
  const gameTriesCount = document.getElementById("game-tries-count");
  const modeDailyBtn = document.getElementById("mode-daily-btn");
  const modeUnlimitedBtn = document.getElementById("mode-unlimited-btn");
  const difficultyWrapper = document.getElementById("difficulty-wrapper");
  const difficultyBtns = document.querySelectorAll("#difficulty-group .pill-btn");
  const gameWordInput = document.getElementById("game-word-input");
  const gameSubmitBtn = document.getElementById("game-submit-btn");
  const gameGiveupBtn = document.getElementById("game-giveup-btn");
  const gameHintBtn = document.getElementById("game-hint-btn");
  const winTitle = document.getElementById("win-title");
  const winDesc = document.getElementById("win-desc");
  const gameWinBanner = document.getElementById("game-win-banner");
  const gameStatusText = document.getElementById("game-status-text");
  const gameSpotlight = document.getElementById("game-spotlight");

  if (gamePuzzleBadge) {
    if (gameState.mode === "daily") {
      const pNum = (gameState.puzzleId && String(gameState.puzzleId) !== "9999" && String(gameState.puzzleId) !== "----") ? gameState.puzzleId : "1";
      const dtFormatted = formatFrenchDate(gameState.puzzleDate) || formatFrenchDate(new Date().toISOString().slice(0, 10));
      gamePuzzleBadge.textContent = `Défi #${pNum}${dtFormatted ? " du " + dtFormatted : ""}`;
    } else {
      gamePuzzleBadge.textContent = `#${gameState.puzzleId || "1"}`;
    }
  }
  if (gameModeBadge) {
    if (gameState.mode === "daily") {
      const diffLabel = gameState.difficulty ? (gameState.difficulty.charAt(0).toUpperCase() + gameState.difficulty.slice(1)) : "Moyen";
      gameModeBadge.textContent = `🎯 ${diffLabel}`;
    } else {
      const diffLabel = gameState.difficulty ? (gameState.difficulty.charAt(0).toUpperCase() + gameState.difficulty.slice(1)) : "Normal";
      gameModeBadge.textContent = `♾️ Libre (${diffLabel})`;
    }
  }
  if (gameTriesCount) gameTriesCount.textContent = String(gameState.tries || 0);

  if (modeDailyBtn && modeUnlimitedBtn) {
    modeDailyBtn.classList.toggle("active", gameState.mode === "daily");
    modeUnlimitedBtn.classList.toggle("active", gameState.mode === "unlimited");
  }
  if (difficultyWrapper) {
    difficultyWrapper.style.display = gameState.mode === "unlimited" ? "flex" : "none";
  }
  const gameActionsWrapper = document.getElementById("game-actions-wrapper");
  if (gameActionsWrapper) {
    gameActionsWrapper.style.display = gameState.mode === "unlimited" ? "block" : "none";
  }
  if (difficultyBtns) {
    difficultyBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.diff === gameState.difficulty);
    });
  }

  const winNewGameBtn = document.getElementById("win-new-game-btn");
  const isDaily = (gameState.mode === "daily");
  if (winNewGameBtn) {
    if (isDaily) {
      winNewGameBtn.innerHTML = "<span>♾️</span> S'entraîner en Mode Illimité";
      winNewGameBtn.title = "Défi du jour terminé. Jouez à volonté de nouvelles énigmes en mode illimité !";
    } else {
      winNewGameBtn.innerHTML = "<span>🔄</span> Nouvelle partie libre";
      winNewGameBtn.title = "Lancer un nouveau mot secret aléatoire.";
    }
  }

  const winIcon = document.getElementById("win-icon") || document.querySelector(".win-trophy");

  if (gameState.isWon) {
    if (gameWordInput) gameWordInput.disabled = true;
    if (gameSubmitBtn) gameSubmitBtn.disabled = true;
    if (gameGiveupBtn) gameGiveupBtn.disabled = true;
    if (winTitle) {
      winTitle.textContent = isDaily ? "🏆 Félicitations ! Mot du jour trouvé !" : "🏆 Victoire triomphale ! Mot secret trouvé !";
      winTitle.style.color = "var(--success)";
    }
    const storedUser = getPlayerUsername() || getStoredSession()?.username;
    const greeting = storedUser ? `Bravo <strong>${escapeHtml(storedUser)}</strong> ! ` : "Bravo ! ";
    const dailyNote = isDaily
      ? `<br><span class="daily-completed-note" style="display:block; margin-top:0.6rem; font-size:0.88rem; color:var(--text-muted); line-height:1.4;">📅 <strong>Défi du Jour terminé !</strong> Le mot est unique chaque jour (prochain défi disponible demain à minuit). Vous pouvez continuer à jouer à volonté en mode illimité ci-dessous.</span>`
      : "";
    if (winDesc) {
      winDesc.innerHTML = `${greeting}Vous avez démasqué le mot <strong style="color: var(--success);">${escapeHtml((gameState.secret || "???").toUpperCase())}</strong> en <strong>${gameState.tries}</strong> coups.${dailyNote}`;
    }
    if (winIcon) winIcon.textContent = "🏆";
    if (gameWinBanner) {
      gameWinBanner.classList.remove("is-defeat");
      gameWinBanner.style.display = "block";
    }
    if (gameStatusText) gameStatusText.textContent = `🏆 Victoire en ${gameState.tries} coups !`;
  } else if (gameState.isGivenUp) {
    if (gameWordInput) gameWordInput.disabled = true;
    if (gameSubmitBtn) gameSubmitBtn.disabled = true;
    if (gameGiveupBtn) gameGiveupBtn.disabled = true;
    if (winTitle) {
      winTitle.textContent = isDaily ? "Défi du jour terminé (Abandon)" : "Partie terminée (Abandon)";
      winTitle.style.color = "var(--danger, #ef4444)";
    }
    const dailyNote = isDaily
      ? `<br><span class="daily-completed-note" style="display:block; margin-top:0.6rem; font-size:0.88rem; color:var(--text-muted); line-height:1.4;">📅 <strong>Défi du Jour terminé (Abandon)</strong>. Rendez-vous demain à minuit pour le prochain mot secret, ou continuez à vous entraîner en mode illimité ci-dessous.</span>`
      : "";
    if (winDesc) {
      winDesc.innerHTML = `Le mot secret était <strong style="color: var(--accent);">${escapeHtml((gameState.secret || "???").toUpperCase())}</strong> après <strong>${gameState.tries}</strong> essais.${dailyNote}`;
    }
    if (winIcon) winIcon.textContent = "🏳️";
    if (gameWinBanner) {
      gameWinBanner.classList.add("is-defeat");
      gameWinBanner.style.display = "block";
    }
    if (gameStatusText) {
      gameStatusText.textContent = `Partie abandonnée. Le mot secret était « ${(gameState.secret || "???").toUpperCase()} ».`;
    }
  } else {
    if (gameWordInput) gameWordInput.disabled = false;
    if (gameSubmitBtn) gameSubmitBtn.disabled = false;
    if (gameGiveupBtn) gameGiveupBtn.disabled = false;
    if (gameWinBanner) {
      gameWinBanner.classList.remove("is-defeat");
      gameWinBanner.style.display = "none";
    }
    if (gameStatusText) {
      gameStatusText.textContent = gameState.tries > 0
        ? `Partie en cours (${gameState.tries} coups joués). Continuez à deviner !`
        : "Partie prête ! Saisissez votre premier mot ci-dessous.";
    }
  }
  updateHintButtonState();

  if (gameState.lastGuess) {
    renderSpotlight(gameState.lastGuess);
  } else if (gameSpotlight) {
    gameSpotlight.style.display = "none";
  }

  renderGameLists();
}

async function resumeGame(gameId) {
  if (!gameId) return false;
  try {
    const playerId = getLocalPlayerId();
    const response = await fetch("/api/game/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        game_id: gameId,
        mode: gameState.mode || "daily",
        difficulty: gameState.difficulty || "normal",
        player_id: playerId,
      }),
    });
    if (!response.ok) return false;
    const json = await response.json();
    gameState.gameId = json.game_id;
    gameState.mode = json.mode;
    gameState.difficulty = json.difficulty;
    gameState.puzzleId = json.puzzle_id;
    gameState.puzzleDate = json.puzzle_date || null;
    gameState.isWon = json.is_won || false;
    gameState.isGivenUp = json.is_given_up || false;
    gameState.tries = json.tries || 0;
    gameState.topGuesses = json.top_guesses || [];
    gameState.allGuesses = json.all_guesses || json.history || [];
    gameState.history = json.history || [];
    gameState.lastGuess = json.last_guess || null;
    gameState.secret = json.secret || null;
    gameState.hints = json.hints || [];
    gameState.hintsRevealed = json.hints_revealed || [];
    restoreGameUI();
    saveGameState();
    return true;
  } catch (_) {
    return false;
  }
}

function setGameMode(mode) {
  if (gameState.mode === mode && gameState.gameId) return;

  saveGameState();

  const loaded = loadGameState(mode);
  if (loaded && gameState.gameId) {
    restoreGameUI();
    saveGameState();
    resumeGame(gameState.gameId);
    return;
  }

  gameState.mode = mode;
  startNewGame(mode, gameState.difficulty, false);
}

function setGameDifficulty(diff) {
  if (gameState.difficulty === diff && gameState.gameId) return;
  gameState.difficulty = diff;
  const difficultyBtns = document.querySelectorAll("#difficulty-group .pill-btn");
  difficultyBtns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.diff === diff);
  });
  startNewGame(gameState.mode, diff, true);
}

function showGameFeedback(msg, type = "error") {
  const gameFeedback = document.getElementById("game-feedback");
  if (!gameFeedback) return;
  gameFeedback.textContent = msg;
  gameFeedback.className = `game-feedback is-${type}`;
  gameFeedback.style.display = "block";
  setTimeout(() => {
    if (gameFeedback) gameFeedback.style.display = "none";
  }, 4000);
}

async function startNewGame(mode = gameState.mode, difficulty = gameState.difficulty, force = false) {
  const gameSubmitBtn = document.getElementById("game-submit-btn");
  const gameHintBtn = document.getElementById("game-hint-btn");
  const gameStatusText = document.getElementById("game-status-text");

  if (gameSubmitBtn) gameSubmitBtn.disabled = true;
  if (gameHintBtn) gameHintBtn.disabled = true;
  if (gameStatusText) gameStatusText.textContent = "Initialisation de la partie en cours...";

  try {
    const playerId = getLocalPlayerId();
    const response = await fetch("/api/game/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, difficulty, force, player_id: playerId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const json = await response.json();
    gameState.gameId = json.game_id;
    gameState.mode = json.mode;
    gameState.difficulty = json.difficulty;
    gameState.puzzleId = json.puzzle_id;
    gameState.puzzleDate = json.puzzle_date || null;
    gameState.isWon = json.is_won || false;
    gameState.isGivenUp = json.is_given_up || false;
    gameState.tries = json.tries || 0;
    gameState.topGuesses = json.top_guesses || [];
    gameState.allGuesses = json.all_guesses || json.history || [];
    gameState.history = json.history || [];
    gameState.lastGuess = json.last_guess || null;
    gameState.secret = json.secret || null;
    gameState.hints = json.hints || [];
    gameState.hintsRevealed = json.hints_revealed || [];

    restoreGameUI();
    saveGameState();
    fetchLeaderboard();
    showToast(json.mode === "daily" ? `Défi du jour synchronisé (${json.difficulty}) !` : `Partie libre (${json.difficulty}) prête !`);
  } catch (err) {
    console.warn("Impossible de contacter l'API du jeu:", err);
    if (gameStatusText) gameStatusText.textContent = "⚠️ API du jeu non accessible (vérifiez que le conteneur tourne).";
  } finally {
    if (gameSubmitBtn && !gameState.isWon && !gameState.isGivenUp) gameSubmitBtn.disabled = false;
    updateHintButtonState();
  }
}

async function submitGuess(rawWord) {
  if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;

  const word = rawWord.trim().toLowerCase();
  if (!word) {
    showGameFeedback("Veuillez saisir un mot avant de valider.", "warning");
    return;
  }

  // Vérification locale anti-doublon
  if (gameState.history.some((g) => g.word === word)) {
    showGameFeedback(`Vous avez déjà testé le mot « ${word.toUpperCase()} ».`, "warning");
    const gameWordInput = document.getElementById("game-word-input");
    if (gameWordInput) gameWordInput.value = "";
    return;
  }

  const gameSubmitBtn = document.getElementById("game-submit-btn");
  const gameWordInput = document.getElementById("game-word-input");
  const gameTriesCount = document.getElementById("game-tries-count");

  if (gameSubmitBtn) gameSubmitBtn.disabled = true;

  try {
    const playerId = getLocalPlayerId();
    let response = await fetch("/api/game/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameState.gameId, word, player_id: playerId }),
    });

    if (response.status === 404) {
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "normal");
      response = await fetch("/api/game/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId, word, player_id: playerId }),
      });
    }

    const json = await response.json();

    if (!response.ok || !json.valid) {
      showGameFeedback(json.error || "Mot invalide ou non reconnu.", "error");
      if (gameSubmitBtn) gameSubmitBtn.disabled = false;
      if (gameWordInput) gameWordInput.select();
      return;
    }

    gameState.tries = json.tries;
    gameState.lastGuess = json.last_guess;
    gameState.topGuesses = json.top_guesses || [];
    gameState.history.unshift(json.last_guess);

    // Mettre à jour la liste complète des mots
    const existingIdx = gameState.allGuesses.findIndex((g) => g.word === json.last_guess.word);
    if (existingIdx >= 0) {
      gameState.allGuesses[existingIdx] = json.last_guess;
    } else {
      gameState.allGuesses.push(json.last_guess);
    }
    gameState.allGuesses.sort((a, b) => (b.score || 0) - (a.score || 0));

    if (gameTriesCount) gameTriesCount.textContent = String(gameState.tries);

    renderSpotlight(json.last_guess);
    renderGameLists();

    if (gameWordInput) {
      gameWordInput.value = "";
      gameWordInput.focus();
    }

    if (json.is_win) {
      gameState.isWon = true;
      gameState.secret = json.secret;
      handleGameWin(json.secret, json.tries);
      fetchLeaderboard();
    }

    saveGameState();
  } catch (err) {
    console.warn("Erreur lors de la soumission du mot:", err);
    showGameFeedback("Erreur réseau lors de la communication avec l'API.", "error");
  } finally {
    if (gameSubmitBtn && !gameState.isWon && !gameState.isGivenUp) gameSubmitBtn.disabled = false;
  }
}

function openHintModalOrRequest() {
  if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;

  const revealedCount = (gameState.hintsRevealed || []).length;
  if (revealedCount >= 3) {
    showToast("⚠️ Quota maximum de 3 indices déjà atteint pour cette partie.", "warning");
    return;
  }

  if (gameState.mode === "daily") {
    const hintModal = document.getElementById("hint-choice-modal");
    const hintModalLevel = document.getElementById("hint-modal-level");
    if (hintModal) {
      if (hintModalLevel) hintModalLevel.textContent = `#${revealedCount + 1}`;
      hintModal.style.display = "flex";
      return;
    }
  }

  // Repli mode illimité
  executeHintRequest("word");
}

async function executeHintRequest(hintType = "word") {
  if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;

  const gameHintBtn = document.getElementById("game-hint-btn");
  const gameTriesCount = document.getElementById("game-tries-count");
  const gameStatusText = document.getElementById("game-status-text");
  const gameWordInput = document.getElementById("game-word-input");

  if (gameHintBtn) gameHintBtn.disabled = true;

  try {
    const playerId = getLocalPlayerId();
    const nextLevel = (gameState.hintsRevealed || []).length + 1;
    let response = await fetch("/api/game/hint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        game_id: gameState.gameId,
        type: hintType,
        level: nextLevel,
        player_id: playerId,
      }),
    });

    if (response.status === 404) {
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "normal");
      response = await fetch("/api/game/hint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_id: gameState.gameId,
          type: hintType,
          level: nextLevel,
          player_id: playerId,
        }),
      });
    }

    const json = await response.json();
    if (!response.ok || json.error) {
      showGameFeedback(json.error || "Impossible d'obtenir un indice.", "warning");
      return;
    }

    gameState.tries = json.tries || gameState.tries + 1;
    if (gameTriesCount) gameTriesCount.textContent = String(gameState.tries);

    if (json.hint_type === "phrase") {
      // Indice au format Phrase
      if (!gameState.hintsRevealed) gameState.hintsRevealed = [];
      gameState.hintsRevealed.push({
        level: json.hint_level || nextLevel,
        type: "phrase",
        content: json.content,
      });

      if (gameStatusText) {
        gameStatusText.textContent = `💬 Indice phrase #${json.hint_level || nextLevel} débloqué (+1 coup).`;
      }
      showToast(`💬 Indice #${json.hint_level || nextLevel} accordé : énigme débloquée (+1 coup)`);
    } else {
      // Indice au format Mot
      const word = json.word || json.hint_word;
      if (word) {
        if (!gameState.hints) gameState.hints = [];
        gameState.hints.push(word);

        if (!gameState.hintsRevealed) gameState.hintsRevealed = [];
        gameState.hintsRevealed.push({
          level: json.hint_level || nextLevel,
          type: "word",
          content: word,
          score: json.score,
          permille: json.permille,
        });

        if (json.last_guess) {
          gameState.lastGuess = json.last_guess;
          gameState.topGuesses = json.top_guesses || [];
          gameState.history.unshift(json.last_guess);

          const existingIdx = gameState.allGuesses.findIndex((g) => g.word === json.last_guess.word);
          if (existingIdx >= 0) {
            gameState.allGuesses[existingIdx] = json.last_guess;
          } else {
            gameState.allGuesses.push(json.last_guess);
          }
          gameState.allGuesses.sort((a, b) => (b.score || 0) - (a.score || 0));
          renderSpotlight(json.last_guess);
        }

        if (gameStatusText) {
          gameStatusText.textContent = `💡 Indice mot : « ${word.toUpperCase()} » (+1 coup au compteur).`;
        }
        showToast(`💡 Indice #${json.hint_level || nextLevel} accordé : « ${word.toUpperCase()} » (+1 coup)`);
      }
    }

    renderGameLists();
    saveGameState();
    setTimeout(() => gameWordInput?.focus(), 100);
  } catch (err) {
    console.warn("Erreur lors de la demande d'indice:", err);
    showGameFeedback("⚠️ Impossible d'obtenir un indice pour le moment.", "danger");
  } finally {
    updateHintButtonState();
  }
}

function updateHintButtonState() {
  const gameHintBtn = document.getElementById("game-hint-btn");
  const hintBadge = document.getElementById("game-hint-badge");
  if (!gameHintBtn) return;

  const revealed = gameState.hintsRevealed || [];
  const remaining = Math.max(0, 3 - revealed.length);

  if (hintBadge) {
    hintBadge.textContent = `${remaining}/3`;
    if (remaining === 0) {
      hintBadge.classList.add("is-exhausted");
      hintBadge.classList.remove("badge-accent");
    } else {
      hintBadge.classList.remove("is-exhausted");
      hintBadge.classList.add("badge-accent");
    }
  }

  if (gameState.isWon || gameState.isGivenUp) {
    gameHintBtn.disabled = true;
    gameHintBtn.style.opacity = "0.5";
    gameHintBtn.style.cursor = "not-allowed";
  } else if (remaining === 0) {
    gameHintBtn.disabled = true;
    gameHintBtn.style.opacity = "0.5";
    gameHintBtn.style.cursor = "not-allowed";
    gameHintBtn.title = "Vous avez utilisé tous vos indices pour cette partie (0/3 restant).";
  } else {
    gameHintBtn.disabled = false;
    gameHintBtn.style.opacity = "1";
    gameHintBtn.style.cursor = "pointer";
    gameHintBtn.title = `Demander un indice sémantique (+1 coup au compteur, ${remaining}/3 disponible${remaining > 1 ? "s" : ""})`;
  }
}

async function giveUpGame() {
  if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;

  const confirmed = await showConfirmDialog({
    title: "Abandonner la partie ?",
    message: "Voulez-vous vraiment abandonner et révéler le mot secret ? Cette partie sera comptabilisée comme un échec.",
    icon: "🏳️",
    confirmText: "Révéler le mot secret",
    confirmType: "danger",
    cancelText: "Continuer à chercher",
  });
  if (!confirmed) return;

  const gameWordInput = document.getElementById("game-word-input");
  const gameSubmitBtn = document.getElementById("game-submit-btn");
  const gameGiveupBtn = document.getElementById("game-giveup-btn");
  const gameHintBtn = document.getElementById("game-hint-btn");
  const gameStatusText = document.getElementById("game-status-text");
  const winTitle = document.getElementById("win-title");
  const winDesc = document.getElementById("win-desc");
  const gameWinBanner = document.getElementById("game-win-banner");

  try {
    const playerId = getLocalPlayerId();
    let response = await fetch("/api/game/giveup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameState.gameId, player_id: playerId }),
    });

    if (response.status === 404) {
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "normal");
      response = await fetch("/api/game/giveup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId, player_id: playerId }),
      });
    }

    const json = await response.json();
    if (json.secret) {
      gameState.isGivenUp = true;
      gameState.secret = json.secret;
      restoreGameUI();
      saveGameState();
      fetchLeaderboard();
      showToast(`Le mot secret était : ${json.secret.toUpperCase()}`);
    }
  } catch (err) {
    console.warn("Erreur lors de l'abandon:", err);
  }
}

function handleGameWin(secretWord, tries) {
  gameState.isWon = true;
  gameState.secret = secretWord;
  restoreGameUI();
  showToast(`🥳 Félicitations ! Mot secret « ${secretWord.toUpperCase()} » trouvé en ${tries} coups !`);
}

function renderSpotlight(guess) {
  const gameSpotlight = document.getElementById("game-spotlight");
  const spotlightOrder = document.getElementById("spotlight-order");
  const spotlightWord = document.getElementById("spotlight-word");
  const spotlightWeather = document.getElementById("spotlight-weather");
  const spotlightTemp = document.getElementById("spotlight-temp");
  const spotlightGauge = document.getElementById("spotlight-gauge");
  const spotlightGaugeBar = document.getElementById("spotlight-gauge-bar");
  const spotlightPermille = document.getElementById("spotlight-permille");

  if (!guess || !gameSpotlight) return;
  gameSpotlight.style.display = "block";

  if (spotlightOrder) spotlightOrder.textContent = `Essai #${guess.order}`;
  if (spotlightWord) spotlightWord.textContent = guess.word.toUpperCase();
  if (spotlightWeather) spotlightWeather.textContent = guess.weather;

  const tierClass = getTierClass(guess.score);
  if (spotlightTemp) {
    spotlightTemp.className = `spotlight-temp ${tierClass}`;
    spotlightTemp.textContent = `${guess.score >= 0 ? "+" : ""}${guess.score.toFixed(2)}°C`;
  }

  const isWarm = (typeof guess.score === "number" && guess.score >= 20) ||
                 (guess.permille !== null && guess.permille >= 1);

  const gaugeContainer = spotlightGauge || spotlightGaugeBar?.parentElement;
  if (gaugeContainer) {
    gaugeContainer.style.display = isWarm ? "block" : "none";
  }

  if (spotlightGaugeBar) {
    if (isWarm) {
      let pct = 10;
      if (guess.permille !== null && guess.permille >= 1) {
        pct = Math.max(10, Math.min(100, Math.round((guess.permille / 1000) * 100)));
      } else {
        pct = Math.max(10, Math.min(100, Math.round(((guess.score - 20) / 80) * 90 + 10)));
      }
      spotlightGaugeBar.style.width = `${pct}%`;
    } else {
      spotlightGaugeBar.style.width = "0%";
    }
  }

  if (spotlightPermille) {
    spotlightPermille.textContent = guess.permille ? `${guess.permille} ‰` : "-- ‰";
    spotlightPermille.style.display = guess.permille ? "inline-block" : "none";
  }
}

async function fetchLeaderboard() {
  const leaderboardList = document.getElementById("game-leaderboard-list");
  if (!leaderboardList) return;

  try {
    const response = await fetch("/api/game/leaderboard");
    if (!response.ok) return;
    const json = await response.json();
    gameState.leaderboard = json.leaderboard || [];
    renderLeaderboard();
  } catch (e) {
    console.warn("Erreur chargement classement:", e);
  }
}

function renderLeaderboard() {
  const container = document.getElementById("game-leaderboard-list");
  if (!container) return;

  const list = gameState.leaderboard || [];
  if (list.length === 0) {
    container.innerHTML = `
      <div class="clues-empty">
        <span>Aucun joueur n'a encore participé aujourd'hui. Soyez le premier !</span>
      </div>
    `;
    return;
  }

  const isGameFinished = gameState.isWon || gameState.isGivenUp;
  const currentUsername = (getPlayerUsername() || "").toLowerCase();

  const html = list.map((item) => {
    const isMe = currentUsername && item.username.toLowerCase() === currentUsername;
    const isWon = (item.status === "won");
    const timeStr = item.duration_seconds
      ? `${Math.floor(item.duration_seconds / 60)}m${Math.round(item.duration_seconds % 60).toString().padStart(2, "0")}s`
      : "--";

    let replayBtn = "";
    if (isGameFinished) {
      replayBtn = `
        <button type="button" class="btn btn-ghost btn-sm btn-replay-action" data-game-id="${item.game_id}" data-username="${escapeHtml(item.username)}" title="Voir la trajectoire de ce joueur">
          <span>🎯</span> Replay
        </button>
      `;
    } else {
      replayBtn = `
        <button type="button" class="btn btn-ghost btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;" title="🔒 Protection anti-spoiler : terminez votre partie pour débloquer les trajectoires">
          <span>🔒</span> Masqué
        </button>
      `;
    }

    const rankColor = isWon ? "var(--accent)" : "var(--text-muted)";
    const statusBadge = isWon
      ? `<span class="badge badge-success" style="font-size: 0.65rem; padding: 1px 6px; background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3);">Trouvé</span>`
      : `<span class="badge badge-danger" style="font-size: 0.65rem; padding: 1px 6px; background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);">Abandon</span>`;

    return `
      <div class="guess-row ${isMe ? "is-winner" : ""}" style="display: flex; align-items: center; justify-content: space-between; padding: 0.55rem 0.75rem;">
        <div class="guess-left" style="display: flex; align-items: center; gap: 0.65rem;">
          <span class="guess-order" style="font-weight: 700; color: ${rankColor};">#${item.rank}</span>
          <span class="guess-player-name" style="font-size: 0.88rem; font-weight: 600; text-transform: none; ${isMe ? "color: var(--accent); font-weight: 800;" : ""}">${escapeHtml(item.username)}</span>
          ${statusBadge}
        </div>
        <div class="guess-right" style="display: flex; align-items: center; gap: 0.75rem;">
          <span style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; ${!isWon ? "color: var(--text-muted);" : ""}">${item.tries_count} coups</span>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${timeStr}</span>
          ${replayBtn}
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = html;

  // Brancher les boutons de replay actifs
  container.querySelectorAll(".btn-replay-action").forEach((btn) => {
    btn.addEventListener("click", () => {
      const gId = btn.dataset.gameId;
      const uName = btn.dataset.username;
      openTrajectoryModal(gId, uName);
    });
  });
}

async function openTrajectoryModal(targetGameId, username) {
  const modal = document.getElementById("trajectory-modal");
  const modalName = document.getElementById("trajectory-player-name");
  const modalList = document.getElementById("trajectory-list");

  if (!modal || !modalList) return;
  if (modalName) modalName.textContent = username || "Joueur";
  modalList.innerHTML = '<div class="clues-empty"><span>Chargement de la trajectoire en cours...</span></div>';
  modal.style.display = "flex";

  try {
    const playerId = getLocalPlayerId();
    const gameId = gameState.gameId || "";
    const pDate = gameState.puzzleDate || "";
    const url = `/api/game/trajectory/${targetGameId}?player_id=${encodeURIComponent(playerId || "")}&game_id=${encodeURIComponent(gameId)}&date=${encodeURIComponent(pDate)}`;
    const res = await fetch(url);
    const json = await res.json();

    if (!res.ok || json.error) {
      modalList.innerHTML = `<div class="clues-empty"><span style="color: var(--danger);">${escapeHtml(json.error || "Trajectoire verrouillée.")}</span></div>`;
      return;
    }

    const guesses = json.trajectory || [];
    if (guesses.length === 0) {
      modalList.innerHTML = '<div class="clues-empty"><span>Aucun coup enregistré pour cette session.</span></div>';
      return;
    }

    modalList.innerHTML = guesses.map((g) => {
      const scoreVal = Number(g.score || 0);
      const tierCls = getTierClass(scoreVal);
      const isWinner = g.permille === 1000 || scoreVal >= 100.0;
      const scoreStr = `${scoreVal >= 0 ? "+" : ""}${scoreVal.toFixed(2)}°C`;
      const permilleStr = g.permille ? `${g.permille} ‰` : "";
      const weatherIcon = g.weather ? g.weather.split(" ")[0] : getTierWeatherIcon(scoreVal, g.permille);

      return `
        <div class="guess-row ${isWinner ? "is-winner" : ""}" style="padding: 0.45rem 0.65rem;">
          <div class="guess-left">
            <span class="guess-order">#${g.order}</span>
            <span class="guess-word">${escapeHtml(g.word.toUpperCase())}</span>
            ${g.is_hint ? '<span class="badge-hint">💡 Indice</span>' : ""}
          </div>
          <div class="guess-right">
            <span class="guess-weather">${weatherIcon}</span>
            <span class="guess-temp ${tierCls}">${scoreStr}</span>
            <span class="guess-permille">${permilleStr}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    modalList.innerHTML = '<div class="clues-empty"><span style="color: var(--danger);">Erreur réseau lors de la récupération.</span></div>';
  }
}

function renderGameLists() {
  // 1. Rendu des indices débloqués (M15)
  const hintsCard = document.getElementById("game-hints-card");
  const hintsList = document.getElementById("game-hints-list");
  const hintsBadge = document.getElementById("hints-count-badge");
  const revealed = gameState.hintsRevealed || [];

  if (hintsCard && hintsList) {
    if (revealed.length > 0) {
      hintsCard.style.display = "block";
      if (hintsBadge) hintsBadge.textContent = String(revealed.length);
      hintsList.innerHTML = revealed.map((h) => {
        const isWord = h.type === "word";
        const icon = isWord ? "🔤 Mot" : "💬 Phrase";
        const contentHtml = isWord
          ? `<strong style="font-family: var(--font-mono); font-size: 1rem; color: var(--accent);">${escapeHtml(h.content.toUpperCase())}</strong> <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">(${h.score !== undefined ? (h.score >= 0 ? "+" : "") + Number(h.score).toFixed(2) + "°C" : ""}${h.permille ? " · " + h.permille + "‰" : ""})</span>`
          : `<em>« ${escapeHtml(h.content)} »</em>`;

        return `
          <div class="hint-unlocked-row" style="display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.6rem 0.85rem; background: var(--bg-input); border: 1px solid var(--border-color); border-radius: var(--radius-sm); margin-bottom: 0.4rem;">
            <span class="badge badge-accent" style="flex-shrink: 0;">Indice #${h.level} (${icon})</span>
            <div style="flex: 1; font-size: 0.9rem; line-height: 1.4;">
              ${contentHtml}
            </div>
          </div>
        `;
      }).join("");
    } else {
      hintsCard.style.display = "none";
    }
  }

  // 2. Tuile « Tous vos mots » (triés du plus chaud au plus froid avec jauge de température)
  const allListContainer = document.getElementById("game-top-list");
  const allWordsCount = document.getElementById("all-words-count");
  const guesses = [...(gameState.allGuesses || gameState.topGuesses || [])];
  guesses.sort((a, b) => (b.score || 0) - (a.score || 0));

  if (allWordsCount) allWordsCount.textContent = String(guesses.length);

  if (allListContainer) {
    if (guesses.length === 0) {
      allListContainer.innerHTML = `
        <div class="clues-empty">
          <span>Vos tentatives apparaîtront ici, triées par proximité sémantique.</span>
        </div>
      `;
    } else {
      allListContainer.innerHTML = guesses.map((g, idx) => {
        const scoreVal = Number(g.score || 0);
        const tierCls = getTierClass(scoreVal);
        const isWinner = g.permille === 1000 || scoreVal >= 100.0;
        const scoreStr = `${scoreVal >= 0 ? "+" : ""}${scoreVal.toFixed(2)}°C`;
        const permilleStr = g.permille ? `${g.permille} ‰` : "";
        const weatherIcon = g.weather ? g.weather.split(" ")[0] : getTierWeatherIcon(scoreVal, g.permille);

        // Calcul de la jauge individuelle relative
        let pct = 0;
        if (scoreVal >= 20 || (g.permille && g.permille >= 1)) {
          if (g.permille && g.permille >= 1) {
            pct = Math.max(10, Math.min(100, Math.round((g.permille / 1000) * 100)));
          } else {
            pct = Math.max(10, Math.min(100, Math.round(((scoreVal - 20) / 80) * 90 + 10)));
          }
        }

        const gaugeHtml = pct > 0 ? `
          <div style="width: 50px; height: 6px; background: rgba(255,255,255,0.06); border-radius: 99px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); flex-shrink: 0;" title="${scoreStr} (${pct}%)">
            <div style="width: ${pct}%; height: 100%; border-radius: 99px; background: var(--gradient-game);"></div>
          </div>
        ` : '';

        return `
          <div class="guess-row ${isWinner ? "is-winner" : ""}" style="padding: 0.5rem 0.75rem;">
            <div class="guess-left" style="gap: 0.5rem;">
              <span class="guess-order" style="min-width: 28px;">#${idx + 1}</span>
              <span class="guess-word" style="cursor: pointer;" title="Essai d'origine #${g.order || idx + 1}">${escapeHtml(g.word.toUpperCase())}</span>
              ${g.is_hint ? '<span class="badge-hint">💡</span>' : ""}
            </div>
            <div class="guess-right" style="gap: 0.6rem;">
              ${gaugeHtml}
              <span class="guess-weather">${weatherIcon}</span>
              <span class="guess-temp ${tierCls}" style="min-width: 58px; text-align: right;">${scoreStr}</span>
              <span class="guess-permille" style="min-width: 38px;">${permilleStr}</span>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // 3. Rendu du classement
  renderLeaderboard();
}
