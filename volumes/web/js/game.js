/**
 * Cémantix Solver — Moteur de Jeu Interactif (Défi du Jour & Mode Illimité)
 */
import { escapeHtml, getTierClass, showToast, showConfirmDialog } from "./utils.js";

const GAME_STORAGE_KEY = "cemantix_game_state_v2";

export const gameState = {
  gameId: null,
  mode: "daily",
  difficulty: "moyen",
  puzzleId: "----",
  isWon: false,
  isGivenUp: false,
  tries: 0,
  topGuesses: [],
  history: [],
  lastGuess: null,
  secret: null,
  hints: [],
};

const modeSessions = {
  daily: null,
  unlimited: null,
};

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
    gameNewBtn.addEventListener("click", () => startNewGame(gameState.mode, gameState.difficulty, true));
  }
  if (winNewGameBtn) {
    winNewGameBtn.addEventListener("click", () => startNewGame(gameState.mode, gameState.difficulty, true));
  }
  if (gameGiveupBtn) {
    gameGiveupBtn.addEventListener("click", giveUpGame);
  }
  if (gameHintBtn) {
    gameHintBtn.addEventListener("click", requestHint);
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
    startNewGame(gameState.mode || "daily", gameState.difficulty || "moyen", false);
  }

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
      isWon: gameState.isWon,
      isGivenUp: gameState.isGivenUp,
      tries: gameState.tries,
      topGuesses: gameState.topGuesses,
      history: gameState.history,
      lastGuess: gameState.lastGuess,
      secret: gameState.secret,
      hints: gameState.hints || [],
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
      raw = localStorage.getItem("cemantix_game_state_v1");
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

  if (gamePuzzleBadge) gamePuzzleBadge.textContent = `#${gameState.puzzleId}`;
  if (gameModeBadge) {
    gameModeBadge.textContent = gameState.mode === "daily" ? "📅 Défi du Jour" : `♾️ Libre (${gameState.difficulty})`;
  }
  if (gameTriesCount) gameTriesCount.textContent = String(gameState.tries || 0);

  if (modeDailyBtn && modeUnlimitedBtn) {
    modeDailyBtn.classList.toggle("active", gameState.mode === "daily");
    modeUnlimitedBtn.classList.toggle("active", gameState.mode === "unlimited");
  }
  if (difficultyWrapper) {
    difficultyWrapper.style.display = gameState.mode === "unlimited" ? "flex" : "none";
  }
  if (difficultyBtns) {
    difficultyBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.diff === gameState.difficulty);
    });
  }

  if (gameState.isWon) {
    if (gameWordInput) gameWordInput.disabled = true;
    if (gameSubmitBtn) gameSubmitBtn.disabled = true;
    if (gameGiveupBtn) gameGiveupBtn.disabled = true;
    if (gameHintBtn) gameHintBtn.disabled = true;
    if (winTitle) {
      winTitle.textContent = "🏆 Victoire triomphale ! Mot secret trouvé !";
      winTitle.style.color = "var(--success)";
    }
    if (winDesc) {
      winDesc.innerHTML = `Bravo ! Vous avez démasqué le mot <strong style="color: var(--success);">${escapeHtml((gameState.secret || "???").toUpperCase())}</strong> en <strong>${gameState.tries}</strong> coups.`;
    }
    if (gameWinBanner) gameWinBanner.style.display = "block";
    if (gameStatusText) gameStatusText.textContent = `🏆 Victoire en ${gameState.tries} coups !`;
  } else if (gameState.isGivenUp) {
    if (gameWordInput) gameWordInput.disabled = true;
    if (gameSubmitBtn) gameSubmitBtn.disabled = true;
    if (gameGiveupBtn) gameGiveupBtn.disabled = true;
    if (gameHintBtn) gameHintBtn.disabled = true;
    if (winTitle) {
      winTitle.textContent = "Partie terminée (Abandon)";
      winTitle.style.color = "var(--text-muted)";
    }
    if (winDesc) {
      winDesc.innerHTML = `Le mot secret était <strong style="color: var(--accent);">${escapeHtml((gameState.secret || "???").toUpperCase())}</strong> après <strong>${gameState.tries}</strong> essais.`;
    }
    if (gameWinBanner) gameWinBanner.style.display = "block";
    if (gameStatusText) {
      gameStatusText.textContent = `Partie abandonnée. Le mot secret était « ${(gameState.secret || "???").toUpperCase()} ».`;
    }
  } else {
    if (gameWordInput) gameWordInput.disabled = false;
    if (gameSubmitBtn) gameSubmitBtn.disabled = false;
    if (gameGiveupBtn) gameGiveupBtn.disabled = false;
    if (gameHintBtn) gameHintBtn.disabled = false;
    if (gameWinBanner) gameWinBanner.style.display = "none";
    if (gameStatusText) {
      gameStatusText.textContent = gameState.tries > 0
        ? `Partie en cours (${gameState.tries} coups joués). Continuez à deviner !`
        : "Partie prête ! Saisissez votre premier mot ci-dessous.";
    }
  }

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
    const response = await fetch("/api/game/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        game_id: gameId,
        mode: gameState.mode || "daily",
        difficulty: gameState.difficulty || "moyen",
      }),
    });
    if (!response.ok) return false;
    const json = await response.json();
    gameState.gameId = json.game_id;
    gameState.mode = json.mode;
    gameState.difficulty = json.difficulty;
    gameState.puzzleId = json.puzzle_id;
    gameState.isWon = json.is_won || false;
    gameState.isGivenUp = json.is_given_up || false;
    gameState.tries = json.tries || 0;
    gameState.topGuesses = json.top_guesses || [];
    gameState.history = json.history || [];
    gameState.lastGuess = json.last_guess || null;
    gameState.secret = json.secret || null;
    gameState.hints = json.hints || [];
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
  if (loaded && gameState.gameId && !gameState.isWon && !gameState.isGivenUp) {
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
    const response = await fetch("/api/game/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, difficulty, force }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const json = await response.json();
    gameState.gameId = json.game_id;
    gameState.mode = json.mode;
    gameState.difficulty = json.difficulty;
    gameState.puzzleId = json.puzzle_id;
    gameState.isWon = json.is_won || false;
    gameState.isGivenUp = json.is_given_up || false;
    gameState.tries = json.tries || 0;
    gameState.topGuesses = json.top_guesses || [];
    gameState.history = json.history || [];
    gameState.lastGuess = json.last_guess || null;
    gameState.secret = json.secret || null;
    gameState.hints = json.hints || [];

    restoreGameUI();
    saveGameState();
    showToast(json.mode === "daily" ? "Défi du jour synchronisé !" : `Partie libre (${json.difficulty}) prête !`);
  } catch (err) {
    console.warn("Impossible de contacter l'API du jeu:", err);
    if (gameStatusText) gameStatusText.textContent = "⚠️ API du jeu non accessible (vérifiez que le conteneur tourne).";
    if (gameSubmitBtn) gameSubmitBtn.disabled = false;
    if (gameHintBtn) gameHintBtn.disabled = false;
  }
}

async function submitGuess(rawWord) {
  const word = (rawWord || "").trim().toLowerCase();
  if (!word) return;

  if (!gameState.gameId) {
    await startNewGame();
    return;
  }

  if (gameState.isWon || gameState.isGivenUp) {
    showGameFeedback("Cette partie est terminée. Cliquez sur « Nouvelle Partie » pour rejouer.", "warning");
    return;
  }

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
    let response = await fetch("/api/game/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameState.gameId, word }),
    });

    if (response.status === 404) {
      console.warn("Session introuvable (404), auto-healing en cours...");
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "moyen");
      response = await fetch("/api/game/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId, word }),
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
    }

    saveGameState();
  } catch (err) {
    console.warn("Erreur lors de la soumission du mot:", err);
    showGameFeedback("Erreur réseau lors de la communication avec l'API.", "error");
  } finally {
    if (gameSubmitBtn) gameSubmitBtn.disabled = false;
  }
}

async function requestHint() {
  if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;
  const gameHintBtn = document.getElementById("game-hint-btn");
  const gameTriesCount = document.getElementById("game-tries-count");
  const gameStatusText = document.getElementById("game-status-text");
  const gameWordInput = document.getElementById("game-word-input");

  if (gameHintBtn) gameHintBtn.disabled = true;

  try {
    let response = await fetch("/api/game/hint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameState.gameId }),
    });

    if (response.status === 404) {
      console.warn("Session introuvable (404), auto-healing en cours...");
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "moyen");
      response = await fetch("/api/game/hint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId }),
      });
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const json = await response.json();
    if (json.error) {
      showGameFeedback(json.error, "warning");
      if (gameHintBtn) gameHintBtn.disabled = false;
      return;
    }

    gameState.tries = json.tries;
    gameState.topGuesses = json.top_guesses || [];
    gameState.history.unshift(json.last_guess);
    gameState.lastGuess = json.last_guess;
    if (!gameState.hints) gameState.hints = [];
    gameState.hints.push(json.hint_word);

    if (gameTriesCount) gameTriesCount.textContent = String(gameState.tries);
    if (gameStatusText) {
      gameStatusText.textContent = `💡 Indice obtenu : « ${json.hint_word.toUpperCase()} » (+1 coup au compteur).`;
    }

    renderSpotlight(json.last_guess);
    renderGameLists();
    saveGameState();
    showToast(`💡 Indice accordé : « ${json.hint_word.toUpperCase()} » (+1 coup)`);
    setTimeout(() => gameWordInput?.focus(), 100);
  } catch (err) {
    console.warn("Erreur lors de la demande d'indice:", err);
    showGameFeedback("⚠️ Impossible d'obtenir un indice pour le moment.", "danger");
  } finally {
    if (gameHintBtn && !gameState.isWon && !gameState.isGivenUp) {
      gameHintBtn.disabled = false;
    }
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
    let response = await fetch("/api/game/giveup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameState.gameId }),
    });

    if (response.status === 404) {
      await startNewGame(gameState.mode || "daily", gameState.difficulty || "moyen");
      response = await fetch("/api/game/giveup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId }),
      });
    }

    const json = await response.json();
    if (json.secret) {
      gameState.isGivenUp = true;
      gameState.secret = json.secret;
      if (gameWordInput) gameWordInput.disabled = true;
      if (gameSubmitBtn) gameSubmitBtn.disabled = true;
      if (gameGiveupBtn) gameGiveupBtn.disabled = true;
      if (gameHintBtn) gameHintBtn.disabled = true;
      if (gameStatusText) gameStatusText.textContent = `Partie abandonnée. Le mot secret était « ${json.secret.toUpperCase()} ».`;

      if (winTitle) {
        winTitle.textContent = "Partie terminée (Abandon)";
        winTitle.style.color = "var(--text-muted)";
      }
      if (winDesc) {
        winDesc.innerHTML = `Le mot secret était <strong style="color: var(--accent);">${escapeHtml(json.secret.toUpperCase())}</strong> après <strong>${gameState.tries}</strong> essais.`;
      }
      if (gameWinBanner) gameWinBanner.style.display = "block";
      saveGameState();
      showToast(`Le mot secret était : ${json.secret.toUpperCase()}`);
    }
  } catch (err) {
    console.warn("Erreur lors de l'abandon:", err);
  }
}

function handleGameWin(secretWord, tries) {
  const gameWordInput = document.getElementById("game-word-input");
  const gameSubmitBtn = document.getElementById("game-submit-btn");
  const gameGiveupBtn = document.getElementById("game-giveup-btn");
  const winTitle = document.getElementById("win-title");
  const winDesc = document.getElementById("win-desc");
  const gameWinBanner = document.getElementById("game-win-banner");
  const gameStatusText = document.getElementById("game-status-text");

  if (gameWordInput) gameWordInput.disabled = true;
  if (gameSubmitBtn) gameSubmitBtn.disabled = true;
  if (gameGiveupBtn) gameGiveupBtn.disabled = true;

  if (winTitle) {
    winTitle.textContent = "🏆 Victoire triomphale ! Mot secret trouvé !";
    winTitle.style.color = "var(--success)";
  }
  if (winDesc) {
    winDesc.innerHTML = `Bravo ! Vous avez démasqué le mot <strong style="color: var(--success);">${escapeHtml(secretWord.toUpperCase())}</strong> en <strong>${tries}</strong> coups.`;
  }
  if (gameWinBanner) gameWinBanner.style.display = "block";
  if (gameStatusText) gameStatusText.textContent = `🏆 Victoire en ${tries} coups !`;

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

function renderGameLists() {
  const gameTopList = document.getElementById("game-top-list");
  const gameChronoList = document.getElementById("game-chrono-list");

  // 1. Top 10 des meilleurs mots
  if (gameTopList) {
    if (gameState.topGuesses.length === 0) {
      gameTopList.innerHTML = `<div class="clues-empty"><span>Vos meilleures tentatives apparaîtront ici.</span></div>`;
    } else {
      gameTopList.innerHTML = gameState.topGuesses.map((g, idx) => {
        const tier = getTierClass(g.score);
        const isWinner = g.permille === 1000 || g.score >= 100.0;
        const hintBadge = g.is_hint ? '<span class="badge-hint" title="Mot obtenu via un indice (+1 coup)">💡 Indice</span>' : "";
        return `
          <div class="guess-row ${isWinner ? "is-winner" : ""}">
            <div class="guess-left">
              <span class="guess-order">#${idx + 1}</span>
              <span class="guess-word">${escapeHtml(g.word.toUpperCase())}${hintBadge}</span>
            </div>
            <div class="guess-right">
              <span class="guess-weather">${g.weather ? g.weather.split(" ")[0] : ""}</span>
              <span class="guess-temp ${tier}">${g.score >= 0 ? "+" : ""}${g.score.toFixed(2)}°C</span>
              <span class="guess-permille">${g.permille ? `${g.permille} ‰` : ""}</span>
            </div>
          </div>`;
      }).join("");
    }
  }

  // 2. Chronologie de tous les coups
  if (gameChronoList) {
    if (gameState.history.length === 0) {
      gameChronoList.innerHTML = `<div class="clues-empty"><span>Aucun mot joué pour le moment.</span></div>`;
    } else {
      gameChronoList.innerHTML = gameState.history.map((g) => {
        const tier = getTierClass(g.score);
        const isWinner = g.permille === 1000 || g.score >= 100.0;
        const hintBadge = g.is_hint ? '<span class="badge-hint" title="Mot obtenu via un indice (+1 coup)">💡 Indice</span>' : "";
        return `
          <div class="guess-row ${isWinner ? "is-winner" : ""}">
            <div class="guess-left">
              <span class="guess-order">[${g.order}]</span>
              <span class="guess-word">${escapeHtml(g.word.toUpperCase())}${hintBadge}</span>
            </div>
            <div class="guess-right">
              <span class="guess-weather">${g.weather ? g.weather.split(" ")[0] : ""}</span>
              <span class="guess-temp ${tier}">${g.score >= 0 ? "+" : ""}${g.score.toFixed(2)}°C</span>
              <span class="guess-permille">${g.permille ? `${g.permille} ‰` : ""}</span>
            </div>
          </div>`;
      }).join("");
    }
  }
}
