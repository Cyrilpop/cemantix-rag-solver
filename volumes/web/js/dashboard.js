/**
 * Cémantix Solver — Dashboard, Mot du Jour & Historique
 */
import { escapeHtml, formatDateFr, getTierClass, getTierWeatherIcon, showToast } from "./utils.js";
import { themeState, toggleGlobalSpoiler } from "./theme.js";
import { initMidnightCountdown } from "./countdown.js";
import { initTrajectoryModal, openTrajectoryModal } from "./trajectory.js";

export const dashboardState = {
  data: null,
  secretWord: null,
  searchQuery: "",
  cluesVisible: true,
  isRevealing: false,
  historyPage: 1,
  historyPageSize: 10,
};

export function isTodayEntry(entry) {
  if (!entry) return false;
  if (entry.word_hidden) return true;
  const current = dashboardState.data?.current;
  if (current) {
    if (entry.date && current.date && entry.date === current.date) return true;
    if (entry.puzzle && current.puzzle && String(entry.puzzle) === String(current.puzzle)) return true;
  }
  return false;
}

export function getEffectiveWord(entry) {
  if (!entry) return "";
  if (entry.word) return entry.word;
  if (isTodayEntry(entry) && dashboardState.secretWord) {
    return dashboardState.secretWord;
  }
  return "";
}

export function initDashboard() {
  const secretWordCard = document.getElementById("secret-word-card");
  const hideWordBtn = document.getElementById("hide-word-btn");
  const copyWordBtn = document.getElementById("copy-word-btn");
  const historySearch = document.getElementById("history-search");
  const historyTbody = document.getElementById("history-tbody");
  const manualRefreshBtn = document.getElementById("manual-refresh-btn");

  // Clic direct ou activation clavier sur la carte du mot secret pour révéler
  if (secretWordCard) {
    secretWordCard.addEventListener("click", (e) => {
      if (secretWordCard.classList.contains("is-spoiled") && !e.target.closest("button")) {
        revealSecretWord();
      }
    });
    secretWordCard.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && !e.target.closest("button")) {
        if (secretWordCard.classList.contains("is-spoiled")) {
          e.preventDefault();
          revealSecretWord();
        }
      }
    });
  }

  // Écoute de l'événement global anti-spoiler émis par le bouton du haut
  window.addEventListener("cemantix:spoiler-change", (e) => {
    const isSpoiled = e.detail?.globalSpoiler;
    if (isSpoiled) {
      // Masquer partout
      secretWordCard?.classList.add("is-spoiled");
      secretWordCard?.setAttribute("aria-expanded", "false");
      if (dashboardState.data?.current) {
        renderClues(dashboardState.data.current);
      }
      renderHistoryTable();
    } else {
      // Révéler partout : récupérer et afficher le mot secret s'il n'est pas déjà là
      revealSecretWord();
      if (dashboardState.data?.current) {
        renderClues(dashboardState.data.current);
      }
      renderHistoryTable();
    }
  });

  if (hideWordBtn) {
    hideWordBtn.addEventListener("click", () => {
      // Masque la tuile et active le spoiler global
      if (!themeState.globalSpoiler) {
        toggleGlobalSpoiler();
      } else {
        secretWordCard?.classList.add("is-spoiled");
        secretWordCard?.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (copyWordBtn) {
    copyWordBtn.addEventListener("click", () => {
      if (dashboardState.secretWord) {
        const word = dashboardState.secretWord.toUpperCase();
        navigator.clipboard.writeText(word).then(() => {
          showToast(`📋 Mot secret « ${word} » copié !`);
        }).catch(() => {
          showToast("Erreur lors de la copie.");
        });
      } else {
        fetch("/api/daily/reveal", { method: "POST" })
          .then((res) => res.json())
          .then((json) => {
            if (!json.word) {
              throw new Error(json.message || "Mot indisponible");
            }
            dashboardState.secretWord = json.word;
            const secretWord = document.getElementById("secret-word");
            if (secretWord) secretWord.textContent = json.word.toUpperCase();
            secretWordCard?.classList.remove("is-spoiled");
            secretWordCard?.setAttribute("aria-expanded", "true");
            navigator.clipboard.writeText(json.word.toUpperCase()).then(() => {
              showToast(`📋 Mot secret « ${json.word.toUpperCase()} » copié !`);
            });
          })
          .catch(() => showToast("Erreur lors de la copie."));
      }
    });
  }

  // Commutateur de format des indices du jour (Phrases vs Mots)
  const btnDashboardPhrase = document.getElementById("btn-dashboard-phrase");
  const btnDashboardWord = document.getElementById("btn-dashboard-word");
  if (btnDashboardPhrase && btnDashboardWord) {
    btnDashboardPhrase.addEventListener("click", () => {
      btnDashboardPhrase.classList.add("active");
      btnDashboardPhrase.setAttribute("aria-checked", "true");
      btnDashboardWord.classList.remove("active");
      btnDashboardWord.setAttribute("aria-checked", "false");
      dashboardState.hintsFormat = "phrase";
      document.querySelectorAll("#clues-container .hint-view-phrase").forEach((el) => el.classList.add("active"));
      document.querySelectorAll("#clues-container .hint-view-word").forEach((el) => el.classList.remove("active"));
    });

    btnDashboardWord.addEventListener("click", () => {
      btnDashboardWord.classList.add("active");
      btnDashboardWord.setAttribute("aria-checked", "true");
      btnDashboardPhrase.classList.remove("active");
      btnDashboardPhrase.setAttribute("aria-checked", "false");
      dashboardState.hintsFormat = "word";
      document.querySelectorAll("#clues-container .hint-view-word").forEach((el) => el.classList.add("active"));
      document.querySelectorAll("#clues-container .hint-view-phrase").forEach((el) => el.classList.remove("active"));
    });
  }

  // Démasquage anti-spoiler dans les indices (cartes IA ou mots RAG)
  const cluesContainer = document.getElementById("clues-container");
  if (cluesContainer) {
    cluesContainer.addEventListener("click", (e) => {
      // Cas 1 : Révélation d'une boîte spoiler d'indice IA
      const box = e.target.closest(".dashboard-spoiler-box");
      if (box) {
        if (!box.classList.contains("revealed")) {
          box.classList.add("revealed");
          const btn = box.querySelector(".btn-reveal");
          if (btn) btn.style.display = "none";
        }
        return;
      }

      // Cas 2 : Révélation d'un mot spoiler (repli RAG)
      const spoilerEl = e.target.closest("[data-action='spoiler']");
      if (spoilerEl) {
        if (spoilerEl.dataset.targetWord === "true" && !dashboardState.secretWord) {
          revealSecretWord();
        } else {
          spoilerEl.classList.toggle("is-hidden");
        }
      }
    });
  }

  // Historique - recherche & clics de lignes
  if (historySearch) {
    let searchTimer = null;
    historySearch.addEventListener("input", (e) => {
      dashboardState.searchQuery = e.target.value;
      dashboardState.historyPage = 1;
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(renderHistoryTable, 150);
    });
  }

  // Historique - pagination
  const historyPrev = document.getElementById("history-prev");
  const historyNext = document.getElementById("history-next");
  if (historyPrev) {
    historyPrev.addEventListener("click", () => {
      if (dashboardState.historyPage > 1) {
        dashboardState.historyPage--;
        renderHistoryTable();
      }
    });
  }
  if (historyNext) {
    historyNext.addEventListener("click", () => {
      dashboardState.historyPage++;
      renderHistoryTable();
    });
  }

  if (historyTbody) {
    const handleActivate = (target) => {
      const spoilerEl = target.closest("[data-action='spoiler']");
      if (spoilerEl) {
        const isToday = spoilerEl.dataset.today === "true";
        if (isToday && !dashboardState.secretWord) {
          revealSecretWord();
        } else {
          spoilerEl.classList.toggle("is-hidden");
        }
        return;
      }
      const row = target.closest(".history-row-clickable");
      if (row && row.dataset.puzzle) {
        openTrajectoryModal(row.dataset.puzzle, dashboardState.data, dashboardState.secretWord);
      }
    };

    historyTbody.addEventListener("click", (e) => {
      handleActivate(e.target);
    });

    historyTbody.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleActivate(e.target);
      }
    });
  }

  if (manualRefreshBtn) {
    manualRefreshBtn.addEventListener("click", () => {
      fetchDashboardData(true);
    });
  }

  initMidnightCountdown(() => {
    // Le renouvellement du mot du jour intervient à minuit (00h00 heure de Paris).
    // Une fois le mot résolu par le démon autonome, on actualise automatiquement les données.
    setTimeout(() => fetchDashboardData(true), 3000);
    setTimeout(() => fetchDashboardData(true), 12000);
  });
  initTrajectoryModal();
  fetchDashboardData();

  // Aucun auto-refresh périodique : les données sont stables et ne changent
  // qu'à minuit lors de la parution du mot du jour (géré par initMidnightCountdown).
}

export function revealSecretWord() {
  const secretWord = document.getElementById("secret-word");
  const secretWordCard = document.getElementById("secret-word-card");

  if (dashboardState.secretWord) {
    if (secretWord) secretWord.textContent = dashboardState.secretWord.toUpperCase();
    secretWordCard?.classList.remove("is-spoiled");
    secretWordCard?.setAttribute("aria-expanded", "true");
    if (dashboardState.data?.current) {
      renderClues(dashboardState.data.current);
    }
    renderHistoryTable();
    return;
  }

  if (dashboardState.isRevealing) return;
  dashboardState.isRevealing = true;

  fetch("/api/daily/reveal", { method: "POST" })
    .then((res) => {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then((json) => {
      if (json.word) {
        dashboardState.secretWord = json.word;
        if (secretWord) secretWord.textContent = json.word.toUpperCase();
        secretWordCard?.classList.remove("is-spoiled");
        secretWordCard?.setAttribute("aria-expanded", "true");
        if (dashboardState.data?.current) {
          dashboardState.data.current.word = json.word;
        }
        if (dashboardState.data?.history) {
          const todayItem = dashboardState.data.history.find((h) => isTodayEntry(h));
          if (todayItem) {
            todayItem.word = json.word;
            todayItem.word_hidden = false;
          }
        }
        // Met à jour la liste des indices et le tableau d'historique pour le jour en cours
        if (dashboardState.data?.current) {
          renderClues(dashboardState.data.current);
        }
        renderHistoryTable();
      } else if (json.pending) {
        throw new Error(json.message || "Le mot du jour n'a pas encore été résolu.");
      } else {
        throw new Error("Mot indisponible");
      }
    })
    .catch((err) => {
      console.warn("Échec révélation mot secret :", err);
      if (secretWord) secretWord.textContent = "--------";
      secretWordCard?.classList.add("is-spoiled");
      secretWordCard?.setAttribute("aria-expanded", "false");
      showToast(err.message || "Impossible de révéler le mot secret");
    })
    .finally(() => {
      dashboardState.isRevealing = false;
    });
}

export function fetchDashboardData(isManual = false) {
  const lastUpdated = document.getElementById("last-updated");
  if (isManual && lastUpdated) {
    lastUpdated.textContent = "Actualisation...";
  }

  fetch("/api/daily")
    .then((res) => {
      if (!res.ok) throw new Error("API /api/daily indisponible");
      return res.json();
    })
    .then((json) => {
      // Préserver le mot secret déjà révélé pendant la session lors des actualisations périodiques
      if (dashboardState.secretWord) {
        if (json.current) {
          json.current.word = dashboardState.secretWord;
        }
        if (json.history) {
          const todayItem = json.history.find((h) => isTodayEntry(h));
          if (todayItem) {
            todayItem.word = dashboardState.secretWord;
            todayItem.word_hidden = false;
          }
        }
      }
      dashboardState.data = json;
      renderDashboard(json);
      // Si le mode anti-spoiler est déjà désactivé par l'utilisateur, révéler le mot
      if (!themeState.globalSpoiler && !dashboardState.secretWord) {
        revealSecretWord();
      }
      if (isManual) showToast("Données synchronisées avec succès");
    })
    .catch((err) => {
      console.warn("Échec récupération /api/daily :", err);
      if (isManual) showToast("Impossible d'actualiser les données");
    });
}

export function renderDashboard(data) {
  if (!data) return;
  const current = data.current || {};
  const stats = data.stats || {};
  const daemon = data.daemon || {};

  const puzzleBadge = document.getElementById("puzzle-badge");
  const puzzleDate = document.getElementById("puzzle-date");
  const secretWord = document.getElementById("secret-word");
  const metricTries = document.getElementById("metric-tries");
  const metricTime = document.getElementById("metric-time");
  const metricSource = document.getElementById("metric-source");
  const winBadge = document.getElementById("win-badge");
  const statTotal = document.getElementById("stat-total");
  const statAvgTries = document.getElementById("stat-avg-tries");
  const statAvgTime = document.getElementById("stat-avg-time");
  const statWinRate = document.getElementById("stat-win-rate");
  const lastUpdated = document.getElementById("last-updated");

  const wordToDisplay = dashboardState.secretWord;
  const secretWordCard = document.getElementById("secret-word-card");
  if (puzzleBadge) puzzleBadge.textContent = current.puzzle ? `Puzzle #${current.puzzle}` : "Puzzle du jour";
  if (puzzleDate) puzzleDate.textContent = formatDateFr(current.date);
  if (secretWord) {
    if (wordToDisplay && (!themeState.globalSpoiler || !secretWordCard?.classList.contains("is-spoiled"))) {
      secretWord.textContent = wordToDisplay.toUpperCase();
      secretWordCard?.classList.remove("is-spoiled");
      secretWordCard?.setAttribute("aria-expanded", "true");
    } else {
      if (wordToDisplay) {
        secretWord.textContent = wordToDisplay.toUpperCase();
      } else {
        secretWord.textContent = "--------";
      }
      secretWordCard?.classList.add("is-spoiled");
      secretWordCard?.setAttribute("aria-expanded", "false");
    }
  }
  if (metricTries) metricTries.textContent = current.tries ? `${current.tries} coups` : "--";
  if (metricTime) metricTime.textContent = current.duration_seconds ? `${current.duration_seconds}s` : "--";

  let sourceLabel = "100% RAG Pur";
  if (current.source === "llm") {
    sourceLabel = "Hybride RAG + LLM";
  } else if (current.source === "seed") {
    sourceLabel = "Graine RAG";
  }
  if (metricSource) metricSource.textContent = sourceLabel;

  if (winBadge) {
    if (current.win) {
      winBadge.className = "badge badge-success";
      winBadge.textContent = "🏆 Résolu avec succès";
    } else {
      winBadge.className = "badge";
      winBadge.textContent = "⏳ Non résolu";
    }
  }

  updateDaemonBadge(daemon.status);
  renderClues(current);

  if (statTotal) statTotal.textContent = stats.total_solved || 0;
  if (statAvgTries) statAvgTries.textContent = stats.avg_tries ? `${stats.avg_tries}` : "--";
  if (statAvgTime) statAvgTime.textContent = stats.avg_duration_seconds ? `${stats.avg_duration_seconds}s` : "--";
  if (statWinRate) statWinRate.textContent = `${stats.win_rate ?? 100}%`;

  renderHistoryTable();

  const now = new Date();
  if (lastUpdated) {
    lastUpdated.textContent = `Dernière synchro : ${now.toLocaleTimeString("fr-FR")}`;
  }
}

export function updateDaemonBadge(status) {
  const daemonBadge = document.getElementById("daemon-badge");
  const daemonStatusText = document.getElementById("daemon-status-text");
  if (!daemonBadge || !daemonStatusText) return;

  daemonBadge.className = "status-badge";
  if (status === "sleeping") {
    daemonBadge.classList.add("status-sleeping");
    daemonStatusText.textContent = "Démon en veille (00h00)";
  } else if (status === "solving") {
    daemonBadge.classList.add("status-solving");
    daemonStatusText.textContent = "Résolution en cours...";
  } else if (status === "starting") {
    daemonBadge.classList.add("status-solving");
    daemonStatusText.textContent = "Démon en démarrage";
  } else if (status === "stopped") {
    daemonBadge.classList.add("status-stopped");
    daemonStatusText.textContent = "Démon arrêté";
  } else if (status === "offline") {
    // Battement trop ancien : le démon ne répond plus, ce n'est pas une veille.
    daemonBadge.classList.add("status-stopped");
    daemonStatusText.textContent = "Démon hors ligne";
  } else if (status === "unknown") {
    // Aucun battement reçu : distinguer « inactif » de « jamais vu ».
    daemonBadge.classList.add("status-stopped");
    daemonStatusText.textContent = "Aucun battement reçu";
  } else {
    daemonBadge.classList.add("status-stopped");
    daemonStatusText.textContent = "Démon indisponible";
  }
}

const DASHBOARD_AI_META = {
  1: { tier: "tier-cold", badge: "Indice #1 · Éloigné", weight: "Similarité ~20%" },
  2: { tier: "tier-warm", badge: "Indice #2 · Intermédiaire", weight: "Similarité ~45%" },
  3: { tier: "tier-fire", badge: "Indice #3 · Proche", weight: "Zone brûlante" },
};

export function renderClues(currentOrGuesses, aiHintsParam = null) {
  const cluesContainer = document.getElementById("clues-container");
  if (!cluesContainer) return;

  const formatToolbar = document.getElementById("dashboard-hints-format");

  let guesses = [];
  let aiHints = [];

  if (Array.isArray(currentOrGuesses)) {
    guesses = currentOrGuesses;
    aiHints = aiHintsParam || dashboardState.data?.current?.ai_hints || [];
  } else if (currentOrGuesses && typeof currentOrGuesses === "object") {
    guesses = currentOrGuesses.top_guesses || [];
    aiHints = currentOrGuesses.ai_hints || dashboardState.data?.current?.ai_hints || [];
  }

  const activeFormat = dashboardState.hintsFormat || "phrase";

  // Mode 1 : Indices IA Gemini disponibles
  if (Array.isArray(aiHints) && aiHints.length > 0) {
    if (formatToolbar) formatToolbar.style.display = "";

    // Synchroniser l'état des boutons du commutateur
    const btnPhrase = document.getElementById("btn-dashboard-phrase");
    const btnWord = document.getElementById("btn-dashboard-word");
    if (btnPhrase && btnWord) {
      btnPhrase.classList.toggle("active", activeFormat === "phrase");
      btnPhrase.setAttribute("aria-checked", activeFormat === "phrase" ? "true" : "false");
      btnWord.classList.toggle("active", activeFormat === "word");
      btnWord.setAttribute("aria-checked", activeFormat === "word" ? "true" : "false");
    }

    const sortedAiHints = [...aiHints].sort((a, b) => (a.hint_level || 0) - (b.hint_level || 0));

    const html = sortedAiHints.map((hint) => {
      const level = hint.hint_level || 1;
      const meta = DASHBOARD_AI_META[level] || DASHBOARD_AI_META[1];
      const rawPhrase = String(hint.hint_phrase || "").trim();
      const cleanPhrase = rawPhrase.replace(/^[«"'\s]+|[»"'\s]+$/g, "");
      const formattedPhrase = cleanPhrase ? `« ${escapeHtml(cleanPhrase)} »` : "";
      const rawWord = String(hint.hint_word || "").trim();
      const formattedWord = rawWord ? escapeHtml(rawWord.charAt(0).toUpperCase() + rawWord.slice(1).toLowerCase()) : "";

      const isPhraseActive = activeFormat === "phrase";

      return `
        <div class="dashboard-hint-card ${meta.tier}" data-level="${level}">
          <div class="dashboard-hint-header">
            <span class="dashboard-hint-badge">${meta.badge}</span>
            <span class="dashboard-hint-weight">${meta.weight}</span>
          </div>
          <div class="dashboard-spoiler-box" data-action="reveal-box">
            <div class="hint-view-phrase ${isPhraseActive ? "active" : ""}">
              <span class="spoiler-text">${formattedPhrase}</span>
            </div>
            <div class="hint-view-word ${!isPhraseActive ? "active" : ""}">
              <span class="spoiler-text">${formattedWord}</span>
            </div>
            <button type="button" class="btn-reveal" data-action="reveal-btn" aria-label="Révéler l'indice ${level}">👁️ Révéler l'indice</button>
          </div>
        </div>`;
    }).join("");

    cluesContainer.className = "clues-list has-ai-hints";
    cluesContainer.innerHTML = html;
    return;
  }

  // Mode 2 (Repli gracieux) : Mots candidats du solveur RAG
  if (formatToolbar) formatToolbar.style.display = "none";
  cluesContainer.className = "clues-list";

  if (!guesses || !Array.isArray(guesses) || guesses.length === 0) {
    cluesContainer.innerHTML = `
      <div class="clues-empty">
        <span>Indices d'approche disponibles lors de la prochaine session de résolution.</span>
      </div>`;
    return;
  }

  const resolvedSecret = (dashboardState.secretWord || "").trim().toLowerCase();
  const candidates = guesses.slice(0, 8);

  // Ordonner du plus froid au plus chaud (commence par le plus froid)
  const sortedGuesses = [...candidates].sort((a, b) => {
    const scoreA = typeof a.score === "number" ? a.score : 0;
    const scoreB = typeof b.score === "number" ? b.score : 0;
    return scoreA - scoreB;
  });

  const html = sortedGuesses.map((g, idx) => {
    const score = typeof g.score === "number" ? g.score : 0;
    const permille = g.permille ? `${g.permille} ‰` : "";
    const weather = getTierWeatherIcon(score, g.permille);
    const tierClass = getTierClass(score);

    const rawWord = String(g.word || "").trim();
    const isTargetWord =
      score >= 100 ||
      g.permille === 1000 ||
      rawWord === "••••••••" ||
      (resolvedSecret && rawWord.toLowerCase() === resolvedSecret);

    let wordContent = "";
    if (isTargetWord) {
      const displayWord = (resolvedSecret || (rawWord !== "••••••••" ? rawWord : "MOT SECRET")).toUpperCase();
      wordContent = `
        <span class="word-spoiler is-hidden"
              data-action="spoiler"
              data-target-word="true"
              title="Cliquer pour afficher / masquer le mot secret">
          ${escapeHtml(displayWord)}
        </span>`;
    } else {
      wordContent = `
        <span class="word-spoiler is-hidden"
              data-action="spoiler"
              title="Cliquer pour afficher / masquer l'indice">
          ${escapeHtml(rawWord)}
        </span>`;
    }

    return `
      <div class="clue-item">
        <div class="clue-left">
          <span class="clue-rank">#${idx + 1}</span>
          <span class="clue-word">${wordContent}</span>
        </div>
        <div class="clue-meta">
          <span class="clue-weather">${weather}</span>
          <span class="clue-temp ${tierClass}">${score >= 0 ? "+" : ""}${score.toFixed(2)}°C</span>
          ${permille ? `<span class="clue-permille">${permille}</span>` : ""}
        </div>
      </div>`;
  }).join("");

  cluesContainer.innerHTML = html;
}

export function renderHistoryTable() {
  const historyTbody = document.getElementById("history-tbody");
  if (!historyTbody || !dashboardState.data || !dashboardState.data.history) return;

  const historyPagination = document.getElementById("history-pagination");
  const historyPrev = document.getElementById("history-prev");
  const historyNext = document.getElementById("history-next");
  const historyPageInfo = document.getElementById("history-page-info");

  let items = dashboardState.data.history;
  const q = dashboardState.searchQuery.trim().toLowerCase();

  if (q) {
    items = items.filter((h) => {
      const word = (getEffectiveWord(h) || h.word || "").toLowerCase();
      const date = (h.date || "").toLowerCase();
      const puzzle = String(h.puzzle || "");
      return word.includes(q) || date.includes(q) || puzzle.includes(q);
    });
  }

  if (items.length === 0) {
    historyTbody.innerHTML = `
      <tr>
        <td colspan="8" class="loading-cell">Aucun puzzle correspondant trouvé.</td>
      </tr>`;
    if (historyPagination) historyPagination.style.display = "none";
    historyTbody.dataset.rendered = "";
    return;
  }

  const pageSize = dashboardState.historyPageSize || 10;
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  if (dashboardState.historyPage > totalPages) {
    dashboardState.historyPage = totalPages;
  }
  if (dashboardState.historyPage < 1) {
    dashboardState.historyPage = 1;
  }

  const startIndex = (dashboardState.historyPage - 1) * pageSize;
  const pageItems = items.slice(startIndex, startIndex + pageSize);

  if (historyPagination) {
    historyPagination.style.display = totalPages > 1 ? "flex" : "none";
    if (historyPrev) historyPrev.disabled = dashboardState.historyPage <= 1;
    if (historyNext) historyNext.disabled = dashboardState.historyPage >= totalPages;
    if (historyPageInfo) {
      historyPageInfo.textContent = `Page ${dashboardState.historyPage} sur ${totalPages} (${items.length} puzzles)`;
    }
  }

  const html = pageItems.map((entry) => {
    const isWinner = entry.win !== false;
    const isToday = isTodayEntry(entry);
    const effectiveWord = getEffectiveWord(entry);

    let wordDisplay = "";
    if (effectiveWord) {
      wordDisplay = effectiveWord.toUpperCase();
    } else if (isWinner) {
      wordDisplay = "MOT DU JOUR";
    } else {
      wordDisplay = "NON TROUVÉ";
    }

    const hideWord = themeState.globalSpoiler || (isToday && !dashboardState.secretWord);
    const trajCount = (entry.trajectory && entry.trajectory.length) || entry.tries || 0;

    return `
      <tr class="history-row-clickable" tabindex="0" role="button" data-puzzle="${escapeHtml(entry.puzzle || "")}" title="Cliquez pour inspecter la progression du bot (ou appuyez sur Entrée)">
        <td><strong>${escapeHtml(entry.date || "--")}</strong></td>
        <td><span class="badge badge-accent">#${escapeHtml(entry.puzzle || "--")}</span></td>
        <td>
          <span class="word-spoiler ${hideWord ? "is-hidden" : ""}" 
                data-action="spoiler"
                data-today="${isToday ? "true" : "false"}"
                title="Cliquer pour afficher / masquer">
            ${escapeHtml(wordDisplay)}
          </span>
        </td>
        <td>${escapeHtml(entry.tries || "--")} coups</td>
        <td>${entry.duration_seconds ? `${escapeHtml(entry.duration_seconds)}s` : "--"}</td>
        <td>${entry.source === "llm" ? "Hybride LLM" : "100% RAG"}</td>
        <td>
          <span class="badge ${isWinner ? "badge-success" : ""}">
            ${isWinner ? "✓ Trouvé" : "Échec"}
          </span>
        </td>
        <td>
          <button type="button" class="btn-trajectory" data-puzzle="${escapeHtml(entry.puzzle || "")}" title="Voir les étapes détaillées de résolution">
            <span>🚀</span> Trajectoire (${escapeHtml(trajCount)})
          </button>
        </td>
      </tr>`;
  }).join("");

  const renderKey = `${dashboardState.historyPage}_${totalPages}_${html}`;
  if (historyTbody.dataset.rendered === renderKey) return;
  historyTbody.dataset.rendered = renderKey;
  historyTbody.innerHTML = html;
}
