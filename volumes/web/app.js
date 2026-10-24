/**
 * Cémantix Solver — Frontend Client Application
 * Gère l'affichage dynamique, le compte à rebours minuit,
 * l'anti-spoiler, la copie, la recherche et l'actualisation en temps réel.
 */

(() => {
  // --- Neutralisation des erreurs parasites d'extensions navigateur (ex: tabs:outgoing.message.ready) ---
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

  // --- État de l'application ---
  const state = {
    data: null,
    isSpoiled: true,
    cluesVisible: true,
    theme: localStorage.getItem("cemantix_theme") || "dark",
    globalSpoiler: localStorage.getItem("cemantix_spoiler") !== "false",
    searchQuery: "",
  };

  // --- Sélecteurs DOM ---
  const DOM = {
    html: document.documentElement,
    themeToggle: document.getElementById("theme-toggle"),
    globalSpoilerToggle: document.getElementById("global-spoiler-toggle"),
    secretWordCard: document.getElementById("secret-word-card"),
    secretWord: document.getElementById("secret-word"),
    revealWordBtn: document.getElementById("reveal-word-btn"),
    hideWordBtn: document.getElementById("hide-word-btn"),
    copyWordBtn: document.getElementById("copy-word-btn"),
    puzzleBadge: document.getElementById("puzzle-badge"),
    puzzleDate: document.getElementById("puzzle-date"),
    winBadge: document.getElementById("win-badge"),
    metricTries: document.getElementById("metric-tries"),
    metricTime: document.getElementById("metric-time"),
    metricSource: document.getElementById("metric-source"),
    daemonBadge: document.getElementById("daemon-badge"),
    daemonStatusText: document.getElementById("daemon-status-text"),
    cdHours: document.getElementById("cd-hours"),
    cdMinutes: document.getElementById("cd-minutes"),
    cdSeconds: document.getElementById("cd-seconds"),
    cluesWrapper: document.getElementById("clues-wrapper"),
    cluesContainer: document.getElementById("clues-container"),
    cluesToggleBtn: document.getElementById("clues-toggle-btn"),
    cluesBtnText: document.getElementById("clues-btn-text"),
    statTotal: document.getElementById("stat-total"),
    statAvgTries: document.getElementById("stat-avg-tries"),
    statAvgTime: document.getElementById("stat-avg-time"),
    statWinRate: document.getElementById("stat-win-rate"),
    historySearch: document.getElementById("history-search"),
    historyTbody: document.getElementById("history-tbody"),
    lastUpdated: document.getElementById("last-updated"),
    manualRefreshBtn: document.getElementById("manual-refresh-btn"),
    toast: document.getElementById("toast"),

    // --- Onglets & Vues ---
    tabDashboard: document.getElementById("tab-dashboard"),
    tabPlay: document.getElementById("tab-play"),
    viewDashboard: document.getElementById("view-dashboard"),
    viewPlay: document.getElementById("view-play"),

    // --- Mode de Jeu Interactif ---
    modeDailyBtn: document.getElementById("mode-daily-btn"),
    modeUnlimitedBtn: document.getElementById("mode-unlimited-btn"),
    difficultyWrapper: document.getElementById("difficulty-wrapper"),
    difficultyBtns: document.querySelectorAll("#difficulty-group .pill-btn"),
    gameNewBtn: document.getElementById("game-new-btn"),
    gameGiveupBtn: document.getElementById("game-giveup-btn"),
    gameHintBtn: document.getElementById("game-hint-btn"),
    gamePuzzleBadge: document.getElementById("game-puzzle-badge"),

    gameModeBadge: document.getElementById("game-mode-badge"),
    gameStatusText: document.getElementById("game-status-text"),
    gameTriesCount: document.getElementById("game-tries-count"),

    // --- Bannière Victoire ---
    gameWinBanner: document.getElementById("game-win-banner"),
    winTitle: document.getElementById("win-title"),
    winDesc: document.getElementById("win-desc"),
    winSecretWord: document.getElementById("win-secret-word"),
    winTriesCount: document.getElementById("win-tries-count"),
    winNewGameBtn: document.getElementById("win-new-game-btn"),

    // --- Saisie & Spotlight ---
    gameGuessForm: document.getElementById("game-guess-form"),
    gameWordInput: document.getElementById("game-word-input"),
    gameSubmitBtn: document.getElementById("game-submit-btn"),
    gameFeedback: document.getElementById("game-feedback"),
    gameSpotlight: document.getElementById("game-spotlight"),
    spotlightOrder: document.getElementById("spotlight-order"),
    spotlightWord: document.getElementById("spotlight-word"),
    spotlightWeather: document.getElementById("spotlight-weather"),
    spotlightTemp: document.getElementById("spotlight-temp"),
    spotlightGaugeBar: document.getElementById("spotlight-gauge-bar"),
    spotlightPermille: document.getElementById("spotlight-permille"),

    // --- Listes des Essais ---
    gameTopList: document.getElementById("game-top-list"),
    gameChronoList: document.getElementById("game-chrono-list"),

    // --- Modal Trajectoire Bot ---
    trajectoryModal: document.getElementById("trajectory-modal"),
    modalPuzzleBadge: document.getElementById("modal-puzzle-badge"),
    modalDateBadge: document.getElementById("modal-date-badge"),
    modalWinBadge: document.getElementById("modal-win-badge"),
    modalSecretWord: document.getElementById("modal-secret-word"),
    modalCloseBtn: document.getElementById("modal-close-btn"),
    modalBottomCloseBtn: document.getElementById("modal-bottom-close-btn"),
    modalTries: document.getElementById("modal-tries"),
    modalDuration: document.getElementById("modal-duration"),
    modalEngine: document.getElementById("modal-engine"),
    modalBestWord: document.getElementById("modal-best-word"),
    trajectoryFilterBtns: document.querySelectorAll("#trajectory-filter-group .pill-btn"),
    trajectoryList: document.getElementById("trajectory-list"),
    copyTrajectoryBtn: document.getElementById("copy-trajectory-btn"),
    countAll: document.getElementById("count-all"),
    countSeeds: document.getElementById("count-seeds"),
    countRag: document.getElementById("count-rag"),
    countHot: document.getElementById("count-hot"),
  };

  let activeTrajectoryEntry = null;
  let activeTrajectoryFilter = "all";

  // Fonction globale pour copier un mot au clic
  window.copyToClipboard = function(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      showToast(`📋 Mot « ${text} » copié !`);
    }).catch(() => {
      showToast("Erreur lors de la copie.");
    });
  };

  // --- Initialisation du Thème & Spoiler ---
  function initTheme() {
    DOM.html.setAttribute("data-theme", state.theme);
    updateThemeIcon();
  }

  function updateThemeIcon() {
    const icon = DOM.themeToggle.querySelector(".theme-icon");
    if (icon) {
      icon.textContent = state.theme === "dark" ? "☀️" : "🌙";
    }
  }

  function toggleTheme() {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("cemantix_theme", state.theme);
    DOM.html.setAttribute("data-theme", state.theme);
    updateThemeIcon();
  }

  // --- Gestion du Mode Anti-Spoiler ---
  function initSpoiler() {
    state.isSpoiled = state.globalSpoiler;
    updateSpoilerState();
  }

  function updateSpoilerState() {
    if (state.isSpoiled) {
      DOM.secretWordCard.classList.add("is-spoiled");
    } else {
      DOM.secretWordCard.classList.remove("is-spoiled");
    }
    const icon = DOM.globalSpoilerToggle.querySelector(".spoiler-icon");
    if (icon) {
      icon.textContent = state.globalSpoiler ? "🛡️" : "👁️";
    }
  }

  function toggleGlobalSpoiler() {
    state.globalSpoiler = !state.globalSpoiler;
    localStorage.setItem("cemantix_spoiler", state.globalSpoiler);
    state.isSpoiled = state.globalSpoiler;
    updateSpoilerState();
    renderHistoryTable();
    showToast(state.globalSpoiler ? "Mode anti-spoiler activé" : "Mode anti-spoiler désactivé");
  }

  // --- Toast Notifications ---
  let toastTimeout = null;
  function showToast(message) {
    if (!DOM.toast) return;
    DOM.toast.textContent = message;
    DOM.toast.classList.add("show");
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      DOM.toast.classList.remove("show");
    }, 2800);
  }

  // --- Formatage Utilitaires ---
  function formatDateFr(isoDateStr) {
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

  function getTierClass(score) {
    if (score < 0) return "tier-ice";
    if (score < 10) return "tier-cold";
    if (score < 20) return "tier-cool";
    if (score < 30) return "tier-warm";
    return "tier-fire";
  }

  function getTierWeatherIcon(score, permille) {
    if (permille === 1000) return "🥳";
    if (permille && permille >= 990) return "🔥";
    if (permille && permille >= 900) return "🥵";
    if (permille && permille >= 1) return "😎";
    if (score >= 0) return "🥶";
    return "🧊";
  }

  // --- Rendu du Dashboard Principal ---
  function renderDashboard(data) {
    if (!data) return;
    const current = data.current || {};
    const stats = data.stats || {};
    const daemon = data.daemon || {};

    // 1. Mot du jour & Métadonnées
    DOM.puzzleBadge.textContent = current.puzzle ? `Puzzle #${current.puzzle}` : "Puzzle du jour";
    DOM.puzzleDate.textContent = formatDateFr(current.date);
    DOM.secretWord.textContent = (current.word || "--------").toUpperCase();

    DOM.metricTries.textContent = current.tries ? `${current.tries} coups` : "--";
    DOM.metricTime.textContent = current.duration_seconds ? `${current.duration_seconds}s` : "--";

    let sourceLabel = "100% RAG Pur";
    if (current.source === "llm") {
      sourceLabel = "Hybride RAG + LLM";
    } else if (current.source === "seed") {
      sourceLabel = "Graine RAG";
    }
    DOM.metricSource.textContent = sourceLabel;

    // Statut de résolution
    if (current.win) {
      DOM.winBadge.className = "badge badge-success";
      DOM.winBadge.textContent = "🏆 Résolu avec succès";
    } else {
      DOM.winBadge.className = "badge";
      DOM.winBadge.textContent = "⏳ Non résolu";
    }

    // 2. État du démon
    updateDaemonBadge(daemon.status);

    // 3. Podium des indices / top guesses
    renderClues(current.top_guesses);

    // 4. Statistiques globales
    DOM.statTotal.textContent = stats.total_solved || 0;
    DOM.statAvgTries.textContent = stats.avg_tries ? `${stats.avg_tries}` : "--";
    DOM.statAvgTime.textContent = stats.avg_duration_seconds ? `${stats.avg_duration_seconds}s` : "--";
    DOM.statWinRate.textContent = `${stats.win_rate ?? 100}%`;

    // 5. Tableau d'historique
    renderHistoryTable();

    // 6. Horodatage de synchronisation
    const now = new Date();
    DOM.lastUpdated.textContent = `Dernière synchro : ${now.toLocaleTimeString("fr-FR")}`;
  }

  function updateDaemonBadge(status) {
    DOM.daemonBadge.className = "status-badge";
    if (status === "sleeping") {
      DOM.daemonBadge.classList.add("status-sleeping");
      DOM.daemonStatusText.textContent = "Démon en veille (00h00)";
    } else if (status === "solving") {
      DOM.daemonBadge.classList.add("status-solving");
      DOM.daemonStatusText.textContent = "Résolution en cours...";
    } else if (status === "stopped") {
      DOM.daemonBadge.classList.add("status-stopped");
      DOM.daemonStatusText.textContent = "Démon arrêté";
    } else {
      DOM.daemonBadge.classList.add("status-sleeping");
      DOM.daemonStatusText.textContent = "Veille active (00h00)";
    }
  }

  function renderClues(guesses) {
    if (!guesses || !Array.isArray(guesses) || guesses.length === 0) {
      DOM.cluesContainer.innerHTML = `
        <div class="clues-empty">
          <span>Indices d'approche disponibles lors de la prochaine session de résolution.</span>
        </div>`;
      return;
    }

    const html = guesses.slice(0, 8).map((g, idx) => {
      const score = typeof g.score === "number" ? g.score : 0;
      const permille = g.permille ? `${g.permille}‰` : "";
      const weather = getTierWeatherIcon(score, g.permille);
      const tierClass = getTierClass(score);

      return `
        <div class="clue-item">
          <div class="clue-left">
            <span class="clue-rank">#${idx + 1}</span>
            <span class="clue-word">${g.word}</span>
          </div>
          <div class="clue-meta">
            <span class="clue-weather">${weather}</span>
            <span class="clue-temp ${tierClass}">${score >= 0 ? "+" : ""}${score.toFixed(2)}°C</span>
            ${permille ? `<span class="clue-permille">${permille}</span>` : ""}
          </div>
        </div>`;
    }).join("");

    DOM.cluesContainer.innerHTML = html;
  }

  function renderHistoryTable() {
    if (!state.data || !state.data.history) return;

    let items = state.data.history;
    const q = state.searchQuery.trim().toLowerCase();

    if (q) {
      items = items.filter(h => {
        const word = (h.word || "").toLowerCase();
        const date = (h.date || "").toLowerCase();
        const puzzle = String(h.puzzle || "");
        return word.includes(q) || date.includes(q) || puzzle.includes(q);
      });
    }

    if (items.length === 0) {
      DOM.historyTbody.innerHTML = `
        <tr>
          <td colspan="8" class="loading-cell">Aucun puzzle correspondant trouvé.</td>
        </tr>`;
      return;
    }

    const html = items.map(entry => {
      const isWinner = entry.win !== false;
      const wordText = (entry.word || "inconnu").toUpperCase();
      const hideWord = state.globalSpoiler;
      const trajCount = (entry.trajectory && entry.trajectory.length) || entry.tries || 0;

      return `
        <tr class="history-row-clickable" data-puzzle="${entry.puzzle || ""}" title="Cliquez pour inspecter la progression du bot">
          <td><strong>${entry.date || "--"}</strong></td>
          <td><span class="badge badge-accent">#${entry.puzzle || "--"}</span></td>
          <td>
            <span class="word-spoiler ${hideWord ? "is-hidden" : ""}" 
                  data-action="spoiler"
                  title="Cliquer pour afficher / masquer">
              ${wordText}
            </span>
          </td>
          <td>${entry.tries || "--"} coups</td>
          <td>${entry.duration_seconds ? `${entry.duration_seconds}s` : "--"}</td>
          <td>${entry.source === "llm" ? "Hybride LLM" : "100% RAG"}</td>
          <td>
            <span class="badge ${isWinner ? "badge-success" : ""}">
              ${isWinner ? "✓ Trouvé" : "Échec"}
            </span>
          </td>
          <td>
            <button type="button" class="btn-trajectory" data-puzzle="${entry.puzzle || ""}" title="Voir les étapes détaillées de résolution">
              <span>🚀</span> Trajectoire (${trajCount})
            </button>
          </td>
        </tr>`;
    }).join("");

    DOM.historyTbody.innerHTML = html;
  }

  // --- Modal Trajectoire & Progression Bot ---
  function openTrajectoryModal(puzzleId) {
    if (!state.data) return;
    const puzzleStr = String(puzzleId);
    let entry = (state.data.history || []).find(h => String(h.puzzle) === puzzleStr);
    if (!entry && state.data.current && String(state.data.current.puzzle) === puzzleStr) {
      entry = state.data.current;
    }
    if (!entry && state.data.history && state.data.history.length > 0) {
      entry = state.data.history[0];
    }
    if (!entry) return;

    activeTrajectoryEntry = entry;
    activeTrajectoryFilter = "all";

    if (DOM.modalPuzzleBadge) DOM.modalPuzzleBadge.textContent = `Puzzle #${entry.puzzle || "--"}`;
    if (DOM.modalDateBadge) DOM.modalDateBadge.textContent = entry.date || "--";
    if (DOM.modalWinBadge) {
      const isWinner = entry.win !== false;
      DOM.modalWinBadge.className = `badge ${isWinner ? "badge-success" : ""}`;
      DOM.modalWinBadge.textContent = isWinner ? "🏆 Trouvé avec succès" : "⏳ Non résolu";
    }
    if (DOM.modalSecretWord) {
      DOM.modalSecretWord.textContent = (entry.word || "inconnu").toUpperCase();
      DOM.modalSecretWord.classList.add("is-hidden");
    }

    if (DOM.modalTries) DOM.modalTries.textContent = `${entry.tries || "--"} coups`;
    if (DOM.modalDuration) DOM.modalDuration.textContent = entry.duration_seconds ? `${entry.duration_seconds}s` : "--";
    if (DOM.modalEngine) DOM.modalEngine.textContent = entry.source === "llm" ? "Hybride LLM" : "100% RAG Mathématique";

    let traj = entry.trajectory || [];
    // Fallback gracieux si l'historique ancien n'a que top_guesses :
    if (traj.length === 0 && Array.isArray(entry.top_guesses) && entry.top_guesses.length > 0) {
      traj = entry.top_guesses.map((g, idx) => ({
        step: idx + 1,
        word: g.word,
        score: typeof g.score === "number" ? g.score : 0,
        permille: g.permille || null,
        source: "rag",
        weather: getTierWeatherIcon(g.score, g.permille),
        is_record: idx === 0,
      }));
    }
    entry._computedTrajectory = traj;

    const bestWarm = traj.filter(t => t.permille !== 1000).sort((a, b) => (b.permille || 0) - (a.permille || 0))[0];
    if (DOM.modalBestWord) {
      DOM.modalBestWord.textContent = bestWarm ? `${bestWarm.word} (${bestWarm.permille}‰)` : "--";
    }

    // Mise à jour des compteurs de filtres
    if (DOM.countAll) DOM.countAll.textContent = traj.length;
    if (DOM.countSeeds) DOM.countSeeds.textContent = traj.filter(t => t.source === "seed").length;
    if (DOM.countRag) DOM.countRag.textContent = traj.filter(t => t.source === "rag" || t.source === "sniper" || t.source === "llm").length;
    if (DOM.countHot) DOM.countHot.textContent = traj.filter(t => t.permille !== null && t.permille >= 1).length;

    if (DOM.trajectoryFilterBtns) {
      DOM.trajectoryFilterBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.filter === "all");
      });
    }

    renderTrajectoryList();

    if (DOM.trajectoryModal) {
      DOM.trajectoryModal.style.display = "flex";
      document.body.style.overflow = "hidden";
    }
  }

  function closeTrajectoryModal() {
    if (DOM.trajectoryModal) {
      DOM.trajectoryModal.style.display = "none";
      document.body.style.overflow = "";
    }
  }

  function renderTrajectoryList() {
    if (!DOM.trajectoryList) return;
    const traj = (activeTrajectoryEntry && (activeTrajectoryEntry._computedTrajectory || activeTrajectoryEntry.trajectory)) || [];
    if (traj.length === 0) {
      DOM.trajectoryList.innerHTML = `
        <div class="clues-empty">
          <span>Aucune étape détaillée consignée pour ce puzzle.</span>
        </div>`;
      return;
    }
    let filtered = traj;
    if (activeTrajectoryFilter === "seeds") {
      filtered = traj.filter(t => t.source === "seed");
    } else if (activeTrajectoryFilter === "rag") {
      filtered = traj.filter(t => t.source === "rag" || t.source === "sniper" || t.source === "llm");
    } else if (activeTrajectoryFilter === "hot") {
      filtered = traj.filter(t => t.permille !== null && t.permille >= 1);
    }

    if (filtered.length === 0) {
      DOM.trajectoryList.innerHTML = `
        <div class="clues-empty">
          <span>Aucun coup dans cette catégorie de filtrage.</span>
        </div>`;
      return;
    }

    const html = filtered.map(item => {
      const isWin = item.permille === 1000;
      const isRecord = item.is_record && !isWin;
      const score = typeof item.score === "number" ? item.score : 0;
      const permilleText = item.permille !== null ? `${item.permille}‰` : "Hors 1000";
      const permilleClass = item.permille !== null ? getTierClass(score) : "tier-ice";
      const weather = item.weather || getTierWeatherIcon(score, item.permille);
      const gaugePercent = item.permille !== null ? Math.min(100, Math.max(8, (item.permille / 10))) : Math.max(0, Math.min(100, (score + 20)));

      let sourceLabel = "⚡ RAG";
      let sourceClass = "source-rag";
      if (item.source === "seed") {
        sourceLabel = "🌱 Graine";
        sourceClass = "source-seed";
      } else if (item.source === "llm") {
        sourceLabel = "🤖 LLM";
        sourceClass = "source-llm";
      } else if (item.source === "sniper") {
        sourceLabel = "🎯 Sniper";
        sourceClass = "source-sniper";
      }

      return `
        <div class="trajectory-step-card ${isWin ? "is-win" : (isRecord ? "is-record" : "")}">
          <div class="step-left">
            <span class="step-num">#${item.step}</span>
            <span class="step-source-badge ${sourceClass}">${sourceLabel}</span>
            <strong class="step-word" onclick="copyToClipboard('${item.word}')" title="Cliquer pour copier le mot">
              ${item.word}
            </strong>
            ${isRecord ? '<span class="step-record-star" title="Nouveau record thermique du bot !">⭐ Record</span>' : ""}
            ${isWin ? '<span class="badge badge-success" style="font-size: 0.65rem; padding: 1px 6px;">🏆 Cible</span>' : ""}
          </div>
          <div class="step-right">
            <span class="step-weather" title="Indicateur d'ambiance">${weather}</span>
            <span class="step-temp">${score > 0 ? "+" : ""}${score.toFixed(2)}°C</span>
            <span class="step-permille-badge ${permilleClass}">${permilleText}</span>
            <div class="step-mini-gauge" title="Progression : ${permilleText}">
              <div class="step-mini-gauge-bar ${permilleClass}" style="width: ${gaugePercent}%;"></div>
            </div>
          </div>
        </div>`;
    }).join("");

    DOM.trajectoryList.innerHTML = html;
  }

  function copyTrajectorySummary() {
    if (!activeTrajectoryEntry) return;
    const e = activeTrajectoryEntry;
    const traj = e.trajectory || [];
    const bestWarm = traj.filter(t => t.permille !== 1000).sort((a, b) => (b.permille || 0) - (a.permille || 0))[0];

    const lines = [
      `🎯 Cémantix — Trajectoire Bot (Puzzle #${e.puzzle || "--"} du ${e.date || "--"})`,
      `Mot cible : ${(e.word || "").toUpperCase()}`,
      `Statut : ${e.win ? "Trouvé" : "Non trouvé"} en ${e.tries || "--"} coups (${e.duration_seconds || "--"}s) via ${e.source === "llm" ? "Hybride LLM" : "100% RAG Mathématique"}`,
      `Meilleur palier chaud : ${bestWarm ? `${bestWarm.word} (${bestWarm.permille}‰, +${bestWarm.score.toFixed(2)}°C)` : "--"}`,
      `\nChronologie des coups joués :`,
      ...traj.map(t => `  #${t.step.toString().padStart(2, "0")} [${t.source.toUpperCase().padEnd(4, " ")}] ${t.word.padEnd(16, " ")} ${t.score >= 0 ? "+" : ""}${t.score.toFixed(2)}°C ${t.weather} ${t.permille ? `${t.permille}‰` : ""}${t.is_record ? " ⭐" : ""}`),
      `\n🔗 https://cemantix.cyril-randon.fr`
    ];

    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      showToast("📋 Trajectoire complète copiée dans le presse-papier !");
    }).catch(() => {
      showToast("Erreur lors de la copie.");
    });
  }

  // --- Compte à Rebours Minuit (Europe/Paris) ---
  function updateCountdown() {
    const now = new Date();
    const parisTimeStr = now.toLocaleString("en-US", { timeZone: "Europe/Paris" });
    const parisNow = new Date(parisTimeStr);

    const target = new Date(parisNow);
    target.setHours(0, 0, 10, 0);

    if (target <= parisNow) {
      target.setDate(target.getDate() + 1);
    }

    const diffMs = Math.max(0, target - parisNow);
    const totalSecs = Math.floor(diffMs / 1000);

    const h = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;

    DOM.cdHours.textContent = String(h).padStart(2, "0");
    DOM.cdMinutes.textContent = String(m).padStart(2, "0");
    DOM.cdSeconds.textContent = String(s).padStart(2, "0");

    if (totalSecs <= 2) {
      setTimeout(fetchData, 3000);
    }
  }

  // --- Récupération des Données (data.json) ---
  async function fetchData() {
    try {
      const response = await fetch(`data.json?t=${Date.now()}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const json = await response.json();
      state.data = json;
      renderDashboard(json);
    } catch (err) {
      console.warn("Impossible de charger data.json:", err);
      DOM.lastUpdated.textContent = "⚠️ Échec de synchronisation";
    }
  }

  // --- Gestion de la visibilité des indices à taille fixe ---
  function updateCluesVisibility() {
    const wrapper = document.getElementById("clues-wrapper");
    if (wrapper) {
      if (state.cluesVisible) {
        wrapper.classList.remove("is-hidden");
      } else {
        wrapper.classList.add("is-hidden");
      }
    }
    DOM.cluesBtnText.textContent = state.cluesVisible ? "Masquer" : "Afficher";
    const icon = DOM.cluesToggleBtn.querySelector("#clues-btn-icon");
    if (icon) {
      icon.textContent = state.cluesVisible ? "👁️" : "🙈";
    }
  }

  // ==========================================================================
  // Logique du Jeu Interactif (Gameplay)
  // ==========================================================================
  const gameState = {
    gameId: null,
    mode: "daily",
    difficulty: "moyen",
    puzzleId: "--",
    isWon: false,
    isGivenUp: false,
    tries: 0,
    topGuesses: [],
    history: [],
    lastGuess: null,
    secret: null,
    hints: [],
    activeTab: "dashboard",
  };

  const modeSessions = {
    daily: null,
    unlimited: null,
  };

  const GAME_STORAGE_KEY = "cemantix_game_state_v2";
  const TAB_STORAGE_KEY = "cemantix_active_tab_v1";

  function saveGameState() {
    try {
      const mode = gameState.mode || "daily";
      const payload = {
        gameId: gameState.gameId,
        mode: mode,
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
      // Vérifier d'abord le format v2
      let raw = localStorage.getItem(GAME_STORAGE_KEY);
      let isV1 = false;
      if (!raw) {
        // Fallback rétrocompatible format v1
        raw = localStorage.getItem("cemantix_game_state_v1");
        isV1 = true;
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

      // Invalidation si plus de 24 heures
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
    if (DOM.gamePuzzleBadge) DOM.gamePuzzleBadge.textContent = `#${gameState.puzzleId}`;
    if (DOM.gameModeBadge) {
      DOM.gameModeBadge.textContent = gameState.mode === "daily" ? "📅 Défi du Jour" : `♾️ Libre (${gameState.difficulty})`;
    }
    if (DOM.gameTriesCount) DOM.gameTriesCount.textContent = String(gameState.tries || 0);

    if (DOM.modeDailyBtn && DOM.modeUnlimitedBtn) {
      DOM.modeDailyBtn.classList.toggle("active", gameState.mode === "daily");
      DOM.modeUnlimitedBtn.classList.toggle("active", gameState.mode === "unlimited");
    }
    if (DOM.difficultyWrapper) {
      DOM.difficultyWrapper.style.display = gameState.mode === "unlimited" ? "flex" : "none";
    }
    if (DOM.difficultyBtns) {
      DOM.difficultyBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.diff === gameState.difficulty);
      });
    }

    if (gameState.isWon) {
      if (DOM.gameWordInput) DOM.gameWordInput.disabled = true;
      if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;
      if (DOM.gameGiveupBtn) DOM.gameGiveupBtn.disabled = true;
      if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = true;
      if (DOM.winTitle) {
        DOM.winTitle.textContent = "🏆 Victoire triomphale ! Mot secret trouvé !";
        DOM.winTitle.style.color = "var(--success)";
      }
      if (DOM.winDesc) {
        DOM.winDesc.innerHTML = `Bravo ! Vous avez démasqué le mot <strong style="color: var(--success);">${(gameState.secret || '???').toUpperCase()}</strong> en <strong>${gameState.tries}</strong> coups.`;
      }
      if (DOM.gameWinBanner) DOM.gameWinBanner.style.display = "block";
      if (DOM.gameStatusText) DOM.gameStatusText.textContent = `🏆 Victoire en ${gameState.tries} coups !`;
    } else if (gameState.isGivenUp) {
      if (DOM.gameWordInput) DOM.gameWordInput.disabled = true;
      if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;
      if (DOM.gameGiveupBtn) DOM.gameGiveupBtn.disabled = true;
      if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = true;
      if (DOM.winTitle) {
        DOM.winTitle.textContent = "Partie terminée (Abandon)";
        DOM.winTitle.style.color = "var(--text-muted)";
      }
      if (DOM.winDesc) {
        DOM.winDesc.innerHTML = `Le mot secret était <strong style="color: var(--accent);">${(gameState.secret || '???').toUpperCase()}</strong> après <strong>${gameState.tries}</strong> essais.`;
      }
      if (DOM.gameWinBanner) DOM.gameWinBanner.style.display = "block";
      if (DOM.gameStatusText) {
        DOM.gameStatusText.textContent = `Partie abandonnée. Le mot secret était « ${(gameState.secret || '???').toUpperCase()} ».`;
      }
    } else {
      if (DOM.gameWordInput) DOM.gameWordInput.disabled = false;
      if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = false;
      if (DOM.gameGiveupBtn) DOM.gameGiveupBtn.disabled = false;
      if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = false;
      if (DOM.gameWinBanner) DOM.gameWinBanner.style.display = "none";
      if (DOM.gameStatusText) {
        DOM.gameStatusText.textContent = gameState.tries > 0
          ? `Partie en cours (${gameState.tries} coups joués). Continuez à deviner !`
          : "Partie prête ! Saisissez votre premier mot ci-dessous.";
      }
    }

    if (gameState.lastGuess) {
      renderSpotlight(gameState.lastGuess);
    } else if (DOM.gameSpotlight) {
      DOM.gameSpotlight.style.display = "none";
    }

    renderGameLists();
  }

  function switchTab(tabName) {
    gameState.activeTab = tabName;
    try {
      localStorage.setItem(TAB_STORAGE_KEY, tabName);
    } catch (_) {}

    if (DOM.tabDashboard && DOM.tabPlay) {
      if (tabName === "dashboard") {
        DOM.tabDashboard.classList.add("active");
        DOM.tabPlay.classList.remove("active");
        if (DOM.viewDashboard) DOM.viewDashboard.style.display = "flex";
        if (DOM.viewPlay) DOM.viewPlay.style.display = "none";
      } else {
        DOM.tabPlay.classList.add("active");
        DOM.tabDashboard.classList.remove("active");
        if (DOM.viewDashboard) DOM.viewDashboard.style.display = "none";
        if (DOM.viewPlay) DOM.viewPlay.style.display = "flex";

        // Recharger et restaurer immédiatement l'état du mode actif
        loadGameState();
        restoreGameUI();
        if (gameState.gameId) {
          resumeGame(gameState.gameId);
        } else {
          startNewGame(gameState.mode || "daily", gameState.difficulty || "moyen", false);
        }
        setTimeout(() => DOM.gameWordInput?.focus(), 100);
      }
    }
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
      if (!response.ok) {
        return false;
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
      return true;
    } catch (_) {
      return false;
    }
  }

  function setGameMode(mode) {
    if (gameState.mode === mode && gameState.gameId) return;

    // 1. Sauvegarder la session du mode actuel avant de basculer
    saveGameState();

    // 2. Tenter de restaurer la session existante pour le mode cible
    const loaded = loadGameState(mode);
    if (loaded && gameState.gameId && !gameState.isWon && !gameState.isGivenUp) {
      restoreGameUI();
      saveGameState();
      resumeGame(gameState.gameId);
      return;
    }

    // 3. Sinon, démarrer une nouvelle partie pour ce mode
    gameState.mode = mode;
    startNewGame(mode, gameState.difficulty, false);
  }

  function setGameDifficulty(diff) {
    if (gameState.difficulty === diff && gameState.gameId) return;
    gameState.difficulty = diff;
    if (DOM.difficultyBtns) {
      DOM.difficultyBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.diff === diff);
      });
    }
    startNewGame(gameState.mode, diff, true);
  }

  function showGameFeedback(msg, type = "error") {
    if (!DOM.gameFeedback) return;
    DOM.gameFeedback.textContent = msg;
    DOM.gameFeedback.className = `game-feedback is-${type}`;
    DOM.gameFeedback.style.display = "block";
    setTimeout(() => {
      if (DOM.gameFeedback) DOM.gameFeedback.style.display = "none";
    }, 4000);
  }

  async function startNewGame(mode = gameState.mode, difficulty = gameState.difficulty, force = false) {
    if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;
    if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = true;
    if (DOM.gameStatusText) DOM.gameStatusText.textContent = "Initialisation de la partie en cours...";

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

      // Mise à jour complète de l'interface
      restoreGameUI();
      saveGameState();
      showToast(json.mode === "daily" ? "Défi du jour synchronisé !" : `Partie libre (${json.difficulty}) prête !`);
    } catch (err) {
      console.warn("Impossible de contacter l'API du jeu:", err);
      if (DOM.gameStatusText) DOM.gameStatusText.textContent = "⚠️ API du jeu non accessible (vérifiez que le conteneur tourne).";
      if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = false;
      if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = false;
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

    // Vérifier si le mot a déjà été joué
    if (gameState.history.some(g => g.word === word)) {
      showGameFeedback(`Vous avez déjà testé le mot « ${word.toUpperCase()} ».`, "warning");
      if (DOM.gameWordInput) DOM.gameWordInput.value = "";
      return;
    }

    if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;

    try {
      let response = await fetch("/api/game/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId, word }),
      });

      // Auto-healing si la session serveur a expiré ou été redémarrée (404)
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
        if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = false;
        if (DOM.gameWordInput) DOM.gameWordInput.select();
        return;
      }

      // Mise à jour de l'état
      gameState.tries = json.tries;
      gameState.lastGuess = json.last_guess;
      gameState.topGuesses = json.top_guesses || [];
      gameState.history.unshift(json.last_guess);
      if (DOM.gameTriesCount) DOM.gameTriesCount.textContent = String(gameState.tries);

      // Rendu du dernier coup et des listes
      renderSpotlight(json.last_guess);
      renderGameLists();

      if (DOM.gameWordInput) {
        DOM.gameWordInput.value = "";
        DOM.gameWordInput.focus();
      }

      // Gestion de la victoire
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
      if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = false;
    }
  }

  async function requestHint() {
    if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;
    if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = true;

    try {
      let response = await fetch("/api/game/hint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameState.gameId }),
      });

      // Auto-healing si 404
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
        if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = false;
        return;
      }

      // Mise à jour de l'état avec l'indice
      gameState.tries = json.tries;
      gameState.topGuesses = json.top_guesses || [];
      gameState.history.unshift(json.last_guess);
      gameState.lastGuess = json.last_guess;
      if (!gameState.hints) gameState.hints = [];
      gameState.hints.push(json.hint_word);

      if (DOM.gameTriesCount) DOM.gameTriesCount.textContent = String(gameState.tries);
      if (DOM.gameStatusText) {
        DOM.gameStatusText.textContent = `💡 Indice obtenu : « ${json.hint_word.toUpperCase()} » (+1 coup au compteur).`;
      }

      renderSpotlight(json.last_guess);
      renderGameLists();
      saveGameState();
      showToast(`💡 Indice accordé : « ${json.hint_word.toUpperCase()} » (+1 coup)`);
      setTimeout(() => DOM.gameWordInput?.focus(), 100);
    } catch (err) {
      console.warn("Erreur lors de la demande d'indice:", err);
      showGameFeedback("⚠️ Impossible d'obtenir un indice pour le moment.", "danger");
    } finally {
      if (DOM.gameHintBtn && !gameState.isWon && !gameState.isGivenUp) {
        DOM.gameHintBtn.disabled = false;
      }
    }
  }

  async function giveUpGame() {
    if (!gameState.gameId || gameState.isWon || gameState.isGivenUp) return;
    if (!confirm("Voulez-vous vraiment abandonner et révéler le mot secret ?")) return;

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
        if (DOM.gameWordInput) DOM.gameWordInput.disabled = true;
        if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;
        if (DOM.gameGiveupBtn) DOM.gameGiveupBtn.disabled = true;
        if (DOM.gameHintBtn) DOM.gameHintBtn.disabled = true;
        if (DOM.gameStatusText) DOM.gameStatusText.textContent = `Partie abandonnée. Le mot secret était « ${json.secret.toUpperCase()} ».`;

        if (DOM.winTitle) {
          DOM.winTitle.textContent = "Partie terminée (Abandon)";
          DOM.winTitle.style.color = "var(--text-muted)";
        }
        if (DOM.winDesc) {
          DOM.winDesc.innerHTML = `Le mot secret était <strong style="color: var(--accent);">${json.secret.toUpperCase()}</strong> après <strong>${gameState.tries}</strong> essais.`;
        }
        if (DOM.gameWinBanner) DOM.gameWinBanner.style.display = "block";
        saveGameState();
        showToast(`Le mot secret était : ${json.secret.toUpperCase()}`);
      }
    } catch (err) {
      console.warn("Erreur lors de l'abandon:", err);
    }
  }


  function handleGameWin(secretWord, tries) {
    if (DOM.gameWordInput) DOM.gameWordInput.disabled = true;
    if (DOM.gameSubmitBtn) DOM.gameSubmitBtn.disabled = true;
    if (DOM.gameGiveupBtn) DOM.gameGiveupBtn.disabled = true;

    if (DOM.winTitle) {
      DOM.winTitle.textContent = "🏆 Victoire triomphale ! Mot secret trouvé !";
      DOM.winTitle.style.color = "var(--success)";
    }
    if (DOM.winDesc) {
      DOM.winDesc.innerHTML = `Bravo ! Vous avez démasqué le mot <strong style="color: var(--success);">${secretWord.toUpperCase()}</strong> en <strong>${tries}</strong> coups.`;
    }
    if (DOM.gameWinBanner) DOM.gameWinBanner.style.display = "block";
    if (DOM.gameStatusText) DOM.gameStatusText.textContent = `🏆 Victoire en ${tries} coups !`;

    showToast(`🥳 Félicitations ! Mot secret « ${secretWord.toUpperCase()} » trouvé en ${tries} coups !`);
  }

  function renderSpotlight(guess) {
    if (!guess || !DOM.gameSpotlight) return;
    DOM.gameSpotlight.style.display = "block";

    if (DOM.spotlightOrder) DOM.spotlightOrder.textContent = `Essai #${guess.order}`;
    if (DOM.spotlightWord) DOM.spotlightWord.textContent = guess.word.toUpperCase();
    if (DOM.spotlightWeather) DOM.spotlightWeather.textContent = guess.weather;

    const tierClass = getTierClass(guess.score);
    if (DOM.spotlightTemp) {
      DOM.spotlightTemp.className = `spotlight-temp ${tierClass}`;
      DOM.spotlightTemp.textContent = `${guess.score >= 0 ? "+" : ""}${guess.score.toFixed(2)}°C`;
    }

    if (DOM.spotlightGaugeBar) {
      const pct = Math.max(5, Math.min(100, Math.round(((guess.score + 15) / 115) * 100)));
      DOM.spotlightGaugeBar.style.width = `${pct}%`;
      DOM.spotlightGaugeBar.style.backgroundColor = `var(--${tierClass})`;
    }

    if (DOM.spotlightPermille) {
      DOM.spotlightPermille.textContent = guess.permille ? `${guess.permille}‰` : "--‰";
      DOM.spotlightPermille.style.display = guess.permille ? "inline-block" : "none";
    }
  }

  function renderGameLists() {
    // 1. Top 10 des meilleurs mots
    if (DOM.gameTopList) {
      if (gameState.topGuesses.length === 0) {
        DOM.gameTopList.innerHTML = `<div class="clues-empty"><span>Vos meilleures tentatives apparaîtront ici.</span></div>`;
      } else {
        DOM.gameTopList.innerHTML = gameState.topGuesses.map((g, idx) => {
          const tier = getTierClass(g.score);
          const isWinner = g.permille === 1000 || g.score >= 100.0;
          const hintBadge = g.is_hint ? '<span class="badge-hint" title="Mot obtenu via un indice (+1 coup)">💡 Indice</span>' : '';
          return `
            <div class="guess-row ${isWinner ? "is-winner" : ""}">
              <div class="guess-left">
                <span class="guess-order">#${idx + 1}</span>
                <span class="guess-word">${g.word.toUpperCase()}${hintBadge}</span>
              </div>
              <div class="guess-right">
                <span class="guess-weather">${g.weather ? g.weather.split(" ")[0] : ""}</span>
                <span class="guess-temp ${tier}">${g.score >= 0 ? "+" : ""}${g.score.toFixed(2)}°C</span>
                <span class="guess-permille">${g.permille ? `${g.permille}‰` : ""}</span>
              </div>
            </div>`;
        }).join("");
      }
    }

    // 2. Chronologie de tous les coups
    if (DOM.gameChronoList) {
      if (gameState.history.length === 0) {
        DOM.gameChronoList.innerHTML = `<div class="clues-empty"><span>Aucun mot joué pour le moment.</span></div>`;
      } else {
        DOM.gameChronoList.innerHTML = gameState.history.map(g => {
          const tier = getTierClass(g.score);
          const isWinner = g.permille === 1000 || g.score >= 100.0;
          const hintBadge = g.is_hint ? '<span class="badge-hint" title="Mot obtenu via un indice (+1 coup)">💡 Indice</span>' : '';
          return `
            <div class="guess-row ${isWinner ? "is-winner" : ""}">
              <div class="guess-left">
                <span class="guess-order">[${g.order}]</span>
                <span class="guess-word">${g.word.toUpperCase()}${hintBadge}</span>
              </div>
              <div class="guess-right">
                <span class="guess-weather">${g.weather ? g.weather.split(" ")[0] : ""}</span>
                <span class="guess-temp ${tier}">${g.score >= 0 ? "+" : ""}${g.score.toFixed(2)}°C</span>
                <span class="guess-permille">${g.permille ? `${g.permille}‰` : ""}</span>
              </div>
            </div>`;
        }).join("");
      }
    }

  }

  // --- Événements & Interactions ---
  function initEvents() {
    DOM.themeToggle.addEventListener("click", toggleTheme);
    DOM.globalSpoilerToggle.addEventListener("click", toggleGlobalSpoiler);

    DOM.revealWordBtn.addEventListener("click", () => {
      state.isSpoiled = false;
      updateSpoilerState();
    });

    DOM.hideWordBtn.addEventListener("click", () => {
      state.isSpoiled = true;
      updateSpoilerState();
    });

    DOM.copyWordBtn.addEventListener("click", async () => {
      const word = DOM.secretWord.textContent.trim();
      if (!word || word.startsWith("-")) return;
      try {
        await navigator.clipboard.writeText(word);
        showToast(`Mot « ${word} » copié dans le presse-papier !`);
      } catch {
        showToast("Erreur lors de la copie.");
      }
    });

    DOM.cluesToggleBtn.addEventListener("click", () => {
      state.cluesVisible = !state.cluesVisible;
      updateCluesVisibility();
    });

    const revealCluesBtn = document.getElementById("reveal-clues-btn");
    if (revealCluesBtn) {
      revealCluesBtn.addEventListener("click", () => {
        state.cluesVisible = true;
        updateCluesVisibility();
      });
    }

    DOM.historySearch.addEventListener("input", (e) => {
      state.searchQuery = e.target.value;
      renderHistoryTable();
    });

    // --- Événements du Tableau d'Historique & Modal Trajectoire ---
    if (DOM.historyTbody) {
      DOM.historyTbody.addEventListener("click", (e) => {
        const spoiler = e.target.closest('[data-action="spoiler"]');
        if (spoiler) {
          spoiler.classList.toggle("is-hidden");
          return;
        }
        const row = e.target.closest("tr[data-puzzle]");
        if (row && row.dataset.puzzle) {
          openTrajectoryModal(row.dataset.puzzle);
        }
      });
    }

    if (DOM.modalCloseBtn) {
      DOM.modalCloseBtn.addEventListener("click", closeTrajectoryModal);
    }
    if (DOM.modalBottomCloseBtn) {
      DOM.modalBottomCloseBtn.addEventListener("click", closeTrajectoryModal);
    }
    if (DOM.trajectoryModal) {
      DOM.trajectoryModal.addEventListener("click", (e) => {
        if (e.target === DOM.trajectoryModal) closeTrajectoryModal();
      });
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && DOM.trajectoryModal && DOM.trajectoryModal.style.display === "flex") {
        closeTrajectoryModal();
      }
    });

    if (DOM.trajectoryFilterBtns) {
      DOM.trajectoryFilterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          DOM.trajectoryFilterBtns.forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          activeTrajectoryFilter = btn.dataset.filter || "all";
          renderTrajectoryList();
        });
      });
    }

    if (DOM.copyTrajectoryBtn) {
      DOM.copyTrajectoryBtn.addEventListener("click", copyTrajectorySummary);
    }

    DOM.manualRefreshBtn.addEventListener("click", async () => {
      DOM.manualRefreshBtn.disabled = true;
      await fetchData();
      showToast("Données actualisées !");
      setTimeout(() => {
        DOM.manualRefreshBtn.disabled = false;
      }, 1000);
    });

    // --- Événements du Mode de Jeu Interactif ---
    if (DOM.tabDashboard) {
      DOM.tabDashboard.addEventListener("click", () => switchTab("dashboard"));
    }
    if (DOM.tabPlay) {
      DOM.tabPlay.addEventListener("click", () => switchTab("play"));
    }

    if (DOM.modeDailyBtn) {
      DOM.modeDailyBtn.addEventListener("click", () => setGameMode("daily"));
    }
    if (DOM.modeUnlimitedBtn) {
      DOM.modeUnlimitedBtn.addEventListener("click", () => setGameMode("unlimited"));
    }

    if (DOM.difficultyBtns) {
      DOM.difficultyBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          if (btn.dataset.diff) setGameDifficulty(btn.dataset.diff);
        });
      });
    }

    if (DOM.gameNewBtn) {
      DOM.gameNewBtn.addEventListener("click", () => startNewGame(gameState.mode, gameState.difficulty, true));
    }
    if (DOM.winNewGameBtn) {
      DOM.winNewGameBtn.addEventListener("click", () => startNewGame(gameState.mode, gameState.difficulty, true));
    }
    if (DOM.gameGiveupBtn) {
      DOM.gameGiveupBtn.addEventListener("click", () => giveUpGame());
    }
    if (DOM.gameHintBtn) {
      DOM.gameHintBtn.addEventListener("click", () => requestHint());
    }

    if (DOM.gameGuessForm) {
      DOM.gameGuessForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const word = DOM.gameWordInput ? DOM.gameWordInput.value : "";
        submitGuess(word);
      });
    }
  }

  // --- Démarrage de l'Application ---
  function init() {
    initTheme();
    initSpoiler();
    initEvents();

    fetchData();
    updateCountdown();
    setInterval(updateCountdown, 1000);
    setInterval(fetchData, 30000);

    // Restauration de l'état du jeu et de l'onglet actif
    const hasSavedGame = loadGameState();
    let savedTab = "dashboard";
    try {
      savedTab = localStorage.getItem(TAB_STORAGE_KEY) || "dashboard";
    } catch (_) {}

    if (savedTab === "play") {
      switchTab("play");
    } else {
      restoreGameUI();
      if (gameState.gameId) {
        resumeGame(gameState.gameId);
      }
    }
  }

  document.addEventListener("DOMContentLoaded", init);

})();
