/**
 * Cémantix Solver — Moteur Client Mode Battle (Joueur vs Bot IA)
 * ==============================================================
 * Gère le tour par tour, les 3 indices graduels, la double jauge de progression,
 * la synchronisation avec l'API /api/battle/* et la réactivité mobile.
 */
import { getTierClass, showToast, initErrorHandling, showConfirmDialog } from "./utils.js?v=20261025b";
import { initTheme } from "./theme.js";

const BATTLE_STORAGE_KEY = "cemantix_battle_state_v1";

export const battleState = {
  battleId: null,
  difficulty: "moyen",
  turnNo: 0,
  isFinished: false,
  winner: null,
  stats: {
    player: 0,
    ai: 0,
    draws: 0,
    match: 1,
    difficulty: "moyen",
  },
  hintsUsed: [],
  hintsRemaining: 3,
  player: {
    last_guess: null,
    top_guesses: [],
    history: [],
    best_score: 0.0,
    best_permille: null,
    progress_pct: 0.0,
    secret: null,
  },
  ai: {
    target: "------",
    last_guess: null,
    top_guesses: [],
    history: [],
    best_score: 0.0,
    best_permille: null,
    progress_pct: 0.0,
    secret: null,
  },
};

let modalSelectedDiff = "moyen";

export function initBattle() {
  initErrorHandling();
  initTheme();

  const diffBtns = document.querySelectorAll("#battle-diff-group .pill-btn");
  const newBtn = document.getElementById("battle-new-btn");
  const replayBtn = document.getElementById("battle-replay-btn");
  const giveupBtn = document.getElementById("battle-giveup-btn");
  const hintBtn = document.getElementById("battle-hint-btn");
  const guessForm = document.getElementById("battle-guess-form");
  const wordInput = document.getElementById("battle-word-input");

  // Sélecteur de difficulté (barre de jeu) -> ouvre la modale avec ce niveau pré-sélectionné
  diffBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const diff = btn.dataset.diff;
      if (diff) {
        openBattleNewModal(diff);
      }
    });
  });

  if (newBtn) {
    newBtn.addEventListener("click", () => openBattleNewModal(battleState.difficulty));
  }
  if (replayBtn) {
    replayBtn.addEventListener("click", () => openBattleNewModal(battleState.difficulty));
  }
  if (giveupBtn) {
    giveupBtn.addEventListener("click", giveUpBattle);
  }
  if (hintBtn) {
    hintBtn.addEventListener("click", requestBattleHint);
  }

  if (guessForm) {
    guessForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = wordInput ? wordInput.value : "";
      submitBattleGuess(val);
    });
  }

  // Configuration de la modale de lancement
  setupBattleNewModal();

  // Toggle mobile
  setupMobileDuelToggle();

  // Restauration de l'état local ou ouverture de la modale de démarrage
  const hasSaved = loadBattleState();
  if (hasSaved && battleState.battleId) {
    resumeBattle(battleState.battleId);
  } else {
    // Premier lancement : afficher directement la modale avec effet blur au premier plan
    openBattleNewModal(battleState.difficulty || "moyen");
  }

  setTimeout(() => wordInput?.focus(), 150);
}

function setupBattleNewModal() {
  const modal = document.getElementById("battle-new-modal");
  const modalClose = document.getElementById("battle-modal-close");
  const modalCancel = document.getElementById("battle-modal-cancel");
  const modalForm = document.getElementById("battle-modal-form");
  const modalDiffCards = document.querySelectorAll("#modal-diff-group .modal-diff-card");

  modalDiffCards.forEach((card) => {
    card.addEventListener("click", () => {
      modalDiffCards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      modalSelectedDiff = card.dataset.diff || "moyen";
    });
  });

  if (modalClose) {
    modalClose.addEventListener("click", () => closeBattleNewModal());
  }
  if (modalCancel) {
    modalCancel.addEventListener("click", () => closeBattleNewModal());
  }

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeBattleNewModal();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const modalEl = document.getElementById("battle-new-modal");
      if (modalEl && modalEl.style.display !== "none") {
        closeBattleNewModal();
      }
    }
  });

  if (modalForm) {
    modalForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const activeCard = document.querySelector("#modal-diff-group .modal-diff-card.active");
      const diff = activeCard ? activeCard.dataset.diff : (modalSelectedDiff || "moyen");
      const aiInput = document.getElementById("modal-ai-word-input");
      const aiWord = aiInput ? aiInput.value.trim().toLowerCase() : "";

      await startNewBattle(diff, Boolean(battleState.battleId), aiWord, true);
    });
  }
}

export function openBattleNewModal(preferredDiff = null) {
  const modal = document.getElementById("battle-new-modal");
  if (!modal) return;

  const targetDiff = preferredDiff || battleState.difficulty || "moyen";
  modalSelectedDiff = targetDiff;

  const modalDiffCards = document.querySelectorAll("#modal-diff-group .modal-diff-card");
  modalDiffCards.forEach((c) => {
    c.classList.toggle("active", c.dataset.diff === targetDiff);
  });

  const modalError = document.getElementById("modal-battle-error");
  if (modalError) {
    modalError.style.display = "none";
    modalError.textContent = "";
  }

  const aiInput = document.getElementById("modal-ai-word-input");
  if (aiInput) {
    aiInput.value = "";
  }

  modal.style.display = "flex";

  setTimeout(() => {
    if (aiInput) aiInput.focus();
  }, 120);
}

export function closeBattleNewModal(force = false) {
  const modal = document.getElementById("battle-new-modal");
  if (!modal) return;
  modal.style.display = "none";

  // Si l'utilisateur ferme sans valider et qu'aucune partie n'est initialisée
  if (!force && !battleState.battleId) {
    startNewBattle(modalSelectedDiff || "moyen", false, "", false);
  } else {
    const wordInput = document.getElementById("battle-word-input");
    if (wordInput && !battleState.isFinished) wordInput.focus();
  }
}

function saveBattleState() {
  try {
    const payload = {
      ...battleState,
      savedAt: Date.now(),
    };
    localStorage.setItem(BATTLE_STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn("Erreur sauvegarde battleState:", e);
  }
}

function loadBattleState() {
  try {
    const raw = localStorage.getItem(BATTLE_STORAGE_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    if (!data || !data.battleId) return false;
    // Expire après 12 heures
    if (data.savedAt && (Date.now() - data.savedAt > 12 * 3600 * 1000)) {
      return false;
    }
    Object.assign(battleState, data);
    return true;
  } catch (_) {
    return false;
  }
}

async function startNewBattle(difficulty = "moyen", keepStats = true, aiWord = "", isFromModal = false) {
  const newBtn = document.getElementById("battle-new-btn");
  const modalSubmitBtn = document.getElementById("battle-modal-submit");
  const modalError = document.getElementById("modal-battle-error");
  const wordInput = document.getElementById("battle-word-input");

  if (newBtn) newBtn.disabled = true;
  if (modalSubmitBtn) {
    modalSubmitBtn.disabled = true;
    modalSubmitBtn.innerHTML = `<span>⏳</span> Lancement...`;
  }
  if (modalError) {
    modalError.style.display = "none";
    modalError.textContent = "";
  }

  try {
    const payload = {
      difficulty,
      battle_id: keepStats ? battleState.battleId : null,
      ai_word: aiWord || null,
    };
    const response = await fetch("/api/battle/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const json = await response.json();
    if (!response.ok || !json.valid) {
      const errorMsg = json.error || "Erreur lors de l'initialisation du duel.";
      if (isFromModal && modalError) {
        modalError.innerHTML = `<span>⚠️</span> <span>${errorMsg}</span>`;
        modalError.style.display = "flex";
        const aiInput = document.getElementById("modal-ai-word-input");
        if (aiInput) aiInput.select();
      } else {
        showToast(errorMsg, "error");
      }
      return false;
    }

    syncStateFromAPI(json);
    renderBattleUI();
    saveBattleState();

    // Fermeture de la modale après succès
    closeBattleNewModal(true);

    if (wordInput) {
      wordInput.value = "";
      wordInput.disabled = false;
      wordInput.focus();
    }
    const aiTargetMsg = aiWord ? `Cible de l'IA : « ${json.ai.target.toUpperCase()} »` : "Cible IA tirée au sort 🎲";
    showToast(`⚔️ Manche #${battleState.stats.match} lancée (${battleState.difficulty.toUpperCase()}) — ${aiTargetMsg} !`, "info");
    return true;
  } catch (err) {
    console.warn("Erreur startNewBattle:", err);
    if (isFromModal && modalError) {
      modalError.innerHTML = `<span>⚠️</span> <span>Erreur réseau de communication avec le serveur.</span>`;
      modalError.style.display = "flex";
    } else {
      showToast("Erreur réseau de communication avec le serveur.", "error");
    }
    return false;
  } finally {
    if (newBtn) newBtn.disabled = false;
    if (modalSubmitBtn) {
      modalSubmitBtn.disabled = false;
      modalSubmitBtn.innerHTML = `<span>⚔️</span> Démarrer le Duel`;
    }
  }
}

async function resumeBattle(battleId) {
  try {
    const response = await fetch("/api/battle/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        battle_id: battleId,
        difficulty: battleState.difficulty || "moyen",
      }),
    });
    if (!response.ok) {
      startNewBattle(battleState.difficulty || "moyen", false);
      return;
    }
    const json = await response.json();
    syncStateFromAPI(json);
    renderBattleUI();
    saveBattleState();
  } catch (err) {
    console.warn("Erreur resumeBattle:", err);
    renderBattleUI();
  }
}

function setBattleDifficulty(diff) {
  openBattleNewModal(diff);
}

async function submitBattleGuess(rawWord) {
  const word = (rawWord || "").trim().toLowerCase();
  if (!word) return;

  if (battleState.isFinished) {
    showBattleFeedback("Cette manche est terminée. Cliquez sur « Manche Suivante » pour continuer.", "warning");
    return;
  }

  // Vérification de doublon côté joueur
  if (battleState.player.history.some((g) => g.word.toLowerCase() === word)) {
    showBattleFeedback(`Vous avez déjà testé le mot « ${word.toUpperCase()} » dans cette manche.`, "warning");
    const input = document.getElementById("battle-word-input");
    if (input) input.value = "";
    return;
  }

  const submitBtn = document.getElementById("battle-submit-btn");
  const wordInput = document.getElementById("battle-word-input");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const response = await fetch("/api/battle/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        battle_id: battleState.battleId,
        word,
      }),
    });

    const json = await response.json();
    if (!response.ok || !json.valid) {
      showBattleFeedback(json.error || "Mot invalide ou non reconnu.", "error");
      if (wordInput) wordInput.select();
      return;
    }

    hideBattleFeedback();
    syncStateFromAPI(json);
    renderBattleUI();
    saveBattleState();

    if (wordInput) {
      wordInput.value = "";
      wordInput.focus();
    }

    if (battleState.isFinished) {
      handleMatchConclusion();
    }
  } catch (err) {
    console.warn("Erreur submitBattleGuess:", err);
    showBattleFeedback("Erreur de communication avec le serveur.", "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function requestBattleHint() {
  if (battleState.isFinished) return;
  if (battleState.hintsRemaining <= 0) {
    showBattleFeedback("Vous avez utilisé vos 3 indices autorisés pour cette manche.", "warning");
    return;
  }

  const hintBtn = document.getElementById("battle-hint-btn");
  const wordInput = document.getElementById("battle-word-input");
  if (hintBtn) hintBtn.disabled = true;

  try {
    const response = await fetch("/api/battle/hint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ battle_id: battleState.battleId }),
    });

    const json = await response.json();
    if (!response.ok || !json.valid) {
      showBattleFeedback(json.error || "Aucun indice disponible.", "warning");
      return;
    }

    hideBattleFeedback();
    syncStateFromAPI(json);
    renderBattleUI();
    saveBattleState();

    if (json.hint_awarded) {
      const h = json.hint_awarded;
      const rk = h.permille ? `${h.permille} ‰` : `${h.score}°C`;
      showToast(`💡 Indice #${h.tier} (${h.tier_label}) : « ${h.word.toUpperCase()} » (${rk})`, "info");
    }

    if (wordInput) wordInput.focus();

    if (battleState.isFinished) {
      handleMatchConclusion();
    }
  } catch (err) {
    console.warn("Erreur requestBattleHint:", err);
    showBattleFeedback("Erreur réseau lors de la demande d'indice.", "error");
  } finally {
    if (hintBtn) hintBtn.disabled = false;
  }
}

async function giveUpBattle() {
  if (battleState.isFinished) return;

  const confirmed = await showConfirmDialog({
    title: "Déclarer Forfait ?",
    message: "Voulez-vous vraiment abandonner cette manche ? Le point sera immédiatement accordé au bot IA et les mots secrets seront révélés.",
    icon: "🏳️",
    confirmText: "Déclarer Forfait",
    confirmType: "danger",
    cancelText: "Continuer le duel",
  });

  if (!confirmed) return;

  const giveupBtn = document.getElementById("battle-giveup-btn");
  if (giveupBtn) giveupBtn.disabled = true;

  try {
    const response = await fetch("/api/battle/giveup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ battle_id: battleState.battleId }),
    });

    const json = await response.json();
    if (json && json.valid) {
      syncStateFromAPI(json);
      renderBattleUI();
      saveBattleState();
      handleMatchConclusion();
    }
  } catch (err) {
    console.warn("Erreur giveUpBattle:", err);
    showToast("Erreur lors de l'abandon de la manche.", "error");
  } finally {
    if (giveupBtn) giveupBtn.disabled = false;
  }
}

function syncStateFromAPI(json) {
  battleState.battleId = json.battle_id;
  battleState.difficulty = json.difficulty || battleState.difficulty;
  battleState.turnNo = json.turn_no || 0;
  battleState.isFinished = Boolean(json.is_finished);
  battleState.winner = json.winner || null;
  battleState.stats = json.stats || battleState.stats;
  battleState.hintsUsed = json.hints_used || [];
  battleState.hintsRemaining = typeof json.hints_remaining === "number" ? json.hints_remaining : 3;

  if (json.player) {
    battleState.player = {
      ...battleState.player,
      ...json.player,
    };
  }
  if (json.ai) {
    battleState.ai = {
      ...battleState.ai,
      ...json.ai,
    };
  }
}

function renderBattleUI() {
  // 1. Boutons de difficulté
  const diffBtns = document.querySelectorAll("#battle-diff-group .pill-btn");
  diffBtns.forEach((b) => b.classList.toggle("active", b.dataset.diff === battleState.difficulty));

  // 2. Scoreboard & Badges
  const scorePlayerVal = document.getElementById("score-player-val");
  const scoreAiVal = document.getElementById("score-ai-val");
  const matchBadge = document.getElementById("battle-match-badge");
  const turnBadge = document.getElementById("battle-turn-badge");

  if (scorePlayerVal) scorePlayerVal.textContent = String(battleState.stats.player || 0);
  if (scoreAiVal) scoreAiVal.textContent = String(battleState.stats.ai || 0);
  if (matchBadge) matchBadge.textContent = `Manche #${battleState.stats.match || 1}`;
  if (turnBadge) turnBadge.textContent = `Tour #${battleState.turnNo + 1}`;

  // 3. Bouton Indice
  const hintCount = document.getElementById("battle-hint-count");
  const hintBtn = document.getElementById("battle-hint-btn");
  if (hintCount) hintCount.textContent = `${battleState.hintsRemaining}/3`;
  if (hintBtn) {
    hintBtn.disabled = battleState.isFinished || battleState.hintsRemaining <= 0;
  }

  // 4. HUD Confrontation & Doubles Jauges
  const playerPct = document.getElementById("player-progress-pct");
  const playerMetric = document.getElementById("player-best-metric");
  const playerBar = document.getElementById("player-gauge-bar");

  const aiTarget = document.getElementById("ai-target-label");
  const aiPct = document.getElementById("ai-progress-pct");
  const aiMetric = document.getElementById("ai-best-metric");
  const aiBar = document.getElementById("ai-gauge-bar");

  const pPctVal = battleState.player.progress_pct || 0;
  const aPctVal = battleState.ai.progress_pct || 0;

  if (playerPct) playerPct.textContent = `${pPctVal}%`;
  if (playerMetric) {
    const p = battleState.player.best_permille;
    const s = battleState.player.best_score;
    playerMetric.textContent = p ? `${p} ‰` : (s ? `${s}°C` : "--");
  }
  if (playerBar) playerBar.style.width = `${pPctVal}%`;

  if (aiTarget) aiTarget.textContent = (battleState.ai.target || "------").toUpperCase();
  if (aiPct) aiPct.textContent = `${aPctVal}%`;
  if (aiMetric) {
    const p = battleState.ai.best_permille;
    const s = battleState.ai.best_score;
    aiMetric.textContent = p ? `${p} ‰` : (s ? `${s}°C` : "--");
  }
  if (aiBar) aiBar.style.width = `${aPctVal}%`;

  // 5. Spotlight du dernier tour
  renderBattleSpotlight();

  // 6. Listes des coups (Vos mots & Mots du Bot)
  renderGuessesList("battle-player-list", battleState.player.top_guesses, true);
  renderGuessesList("battle-ai-list", battleState.ai.top_guesses, false);

  // Compteurs mobiles
  const mobPlayerCount = document.getElementById("mobile-player-count");
  const mobAiCount = document.getElementById("mobile-ai-count");
  if (mobPlayerCount) mobPlayerCount.textContent = String(battleState.player.history.length || 0);
  if (mobAiCount) mobAiCount.textContent = String(battleState.ai.history.length || 0);

  // 7. Bannière de fin de manche
  renderBanner();
}

function renderBattleSpotlight() {
  const spotlight = document.getElementById("battle-spotlight");
  if (!spotlight) return;

  const lastP = battleState.player.last_guess;
  const lastA = battleState.ai.last_guess;

  if (!lastP && !lastA) {
    spotlight.style.display = "none";
    return;
  }

  spotlight.style.display = "block";
  const turnNum = document.getElementById("spotlight-turn-num");
  const statusTag = document.getElementById("spotlight-status-tag");
  if (turnNum) turnNum.textContent = String(battleState.turnNo);
  if (statusTag) {
    if (battleState.isFinished) {
      statusTag.textContent = "Manche terminée";
      statusTag.className = "badge badge-success";
    } else {
      statusTag.textContent = "Tour complété";
      statusTag.className = "badge badge-accent";
    }
  }

  // Joueur
  const pWord = document.getElementById("spotlight-player-word");
  const pWeather = document.getElementById("spotlight-player-weather");
  const pTemp = document.getElementById("spotlight-player-temp");
  const pPermille = document.getElementById("spotlight-player-permille");

  if (lastP) {
    if (pWord) pWord.textContent = lastP.word.toUpperCase();
    if (pWeather) pWeather.textContent = lastP.weather;
    if (pTemp) pTemp.textContent = `${lastP.score.toFixed(2)}°C`;
    if (pPermille) pPermille.textContent = lastP.permille ? `${lastP.permille} ‰` : "-- ‰";
  } else {
    if (pWord) pWord.textContent = "-------";
    if (pWeather) pWeather.textContent = "🧊 Glacé";
    if (pTemp) pTemp.textContent = "0.00°C";
    if (pPermille) pPermille.textContent = "-- ‰";
  }

  // Bot IA
  const aWord = document.getElementById("spotlight-ai-word");
  const aWeather = document.getElementById("spotlight-ai-weather");
  const aTemp = document.getElementById("spotlight-ai-temp");
  const aPermille = document.getElementById("spotlight-ai-permille");

  if (lastA) {
    if (aWord) aWord.textContent = lastA.word.toUpperCase();
    if (aWeather) aWeather.textContent = lastA.weather;
    if (aTemp) aTemp.textContent = `${lastA.score.toFixed(2)}°C`;
    if (aPermille) aPermille.textContent = lastA.permille ? `${lastA.permille} ‰` : "-- ‰";
  } else {
    if (aWord) aWord.textContent = "-------";
    if (aWeather) aWeather.textContent = "🧊 Glacé";
    if (aTemp) aTemp.textContent = "0.00°C";
    if (aPermille) aPermille.textContent = "-- ‰";
  }
}

function renderGuessesList(containerId, guesses, isPlayer) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!guesses || guesses.length === 0) {
    container.innerHTML = `
      <div class="clues-empty">
        <span>${isPlayer ? "Saisissez votre premier mot pour débuter le duel." : "Le bot répliquera dès votre premier essai."}</span>
      </div>
    `;
    return;
  }

  const html = guesses.map((g, idx) => {
    const tierCls = getTierClass(g.score, g.permille);
    const scoreStr = `${Number(g.score).toFixed(2)}°C`;
    const permilleStr = g.permille ? `${g.permille} ‰` : "-- ‰";
    const hintBadge = g.is_hint
      ? `<span class="badge-hint" title="Indice sémantique">💡 Indice</span>`
      : "";

    return `
      <div class="guess-row ${tierCls}" style="animation-delay: ${idx * 0.02}s">
        <div class="guess-left">
          <span class="guess-order">#${g.order}</span>
          <span class="guess-word">${g.word.toUpperCase()}</span>
          ${hintBadge}
        </div>
        <div class="guess-right">
          <span class="guess-weather">${g.weather || ""}</span>
          <span class="guess-temp">${scoreStr}</span>
          <span class="guess-permille">${permilleStr}</span>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = html;
}

function renderBanner() {
  const banner = document.getElementById("battle-banner");
  const wordInput = document.getElementById("battle-word-input");
  const submitBtn = document.getElementById("battle-submit-btn");
  const giveupBtn = document.getElementById("battle-giveup-btn");

  if (!banner) return;

  if (!battleState.isFinished) {
    banner.style.display = "none";
    if (wordInput) wordInput.disabled = false;
    if (submitBtn) submitBtn.disabled = false;
    if (giveupBtn) giveupBtn.disabled = false;
    return;
  }

  if (wordInput) wordInput.disabled = true;
  if (submitBtn) submitBtn.disabled = true;
  if (giveupBtn) giveupBtn.disabled = true;

  const iconEl = document.getElementById("battle-banner-icon");
  const titleEl = document.getElementById("battle-banner-title");
  const descEl = document.getElementById("battle-banner-desc");
  const pWordEl = document.getElementById("banner-player-word");
  const aWordEl = document.getElementById("banner-ai-word");

  banner.className = "battle-banner card";

  if (battleState.winner === "player") {
    if (iconEl) iconEl.textContent = "🏆";
    if (titleEl) {
      titleEl.textContent = "VICTOIRE ! Vous avez battu l'IA !";
      titleEl.style.color = "var(--success)";
    }
    if (descEl) {
      descEl.textContent = `Félicitations ! Vous avez démasqué votre mot secret en ${battleState.turnNo} tour(s) avant le bot adverse.`;
    }
  } else if (battleState.winner === "ai") {
    banner.classList.add("banner-ai-win");
    if (iconEl) iconEl.textContent = "🤖";
    if (titleEl) {
      titleEl.textContent = "L'IA RAG remporte la manche !";
      titleEl.style.color = "#f0883e";
    }
    if (descEl) {
      descEl.textContent = `Le bot adverse a atteint sa cible au tour #${battleState.turnNo}. Relevez le défi pour la revanche !`;
    }
  } else if (battleState.winner === "draw") {
    banner.classList.add("banner-draw");
    if (iconEl) iconEl.textContent = "🤝";
    if (titleEl) {
      titleEl.textContent = "Égalité parfaite !";
      titleEl.style.color = "#a371f7";
    }
    if (descEl) {
      descEl.textContent = `Incroyable ! Vous et le bot IA avez découvert vos cibles au même tour (${battleState.turnNo}) !`;
    }
  } else {
    // Abandon / giveup
    banner.classList.add("banner-ai-win");
    if (iconEl) iconEl.textContent = "🏳️";
    if (titleEl) {
      titleEl.textContent = "Manche abandonnée (Forfait)";
      titleEl.style.color = "var(--text-muted)";
    }
    if (descEl) {
      descEl.textContent = "Vous avez déclaré forfait pour cette manche. Le point est attribué au bot IA.";
    }
  }

  if (pWordEl) pWordEl.textContent = (battleState.player.secret || "???").toUpperCase();
  if (aWordEl) aWordEl.textContent = (battleState.ai.secret || battleState.ai.target || "???").toUpperCase();

  banner.style.display = "block";
}

function handleMatchConclusion() {
  if (battleState.winner === "player") {
    showToast("🎉 Victoire éclatante ! Vous avez battu l'IA !", "success");
  } else if (battleState.winner === "ai") {
    showToast("🤖 L'IA a trouvé son mot en premier !", "warning");
  } else if (battleState.winner === "draw") {
    showToast("🤝 Match nul synchronisé !", "info");
  }
}

function showBattleFeedback(msg, type = "error") {
  const fb = document.getElementById("battle-feedback");
  if (!fb) return;
  fb.textContent = msg;
  fb.className = `game-feedback feedback-${type}`;
  fb.style.display = "block";
}

function hideBattleFeedback() {
  const fb = document.getElementById("battle-feedback");
  if (fb) fb.style.display = "none";
}

function setupMobileDuelToggle() {
  const toggle = document.getElementById("mobile-duel-toggle");
  const grid = document.querySelector(".battle-results-grid");
  if (!toggle || !grid) return;

  grid.classList.add("show-player");

  const btns = toggle.querySelectorAll(".mobile-toggle-btn");
  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      btns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const target = btn.dataset.target;
      if (target === "ai") {
        grid.classList.remove("show-player");
        grid.classList.add("show-ai");
      } else {
        grid.classList.remove("show-ai");
        grid.classList.add("show-player");
      }
    });
  });
}

// Auto-bootstrap
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("view-battle") || document.getElementById("battle-guess-form")) {
      initBattle();
    }
  });
} else {
  if (document.getElementById("view-battle") || document.getElementById("battle-guess-form")) {
    initBattle();
  }
}
