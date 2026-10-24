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
          <td colspan="7" class="loading-cell">Aucun puzzle correspondant trouvé.</td>
        </tr>`;
      return;
    }

    const html = items.map(entry => {
      const isWinner = entry.win !== false;
      const wordText = (entry.word || "inconnu").toUpperCase();
      const hideWord = state.globalSpoiler;

      return `
        <tr>
          <td><strong>${entry.date || "--"}</strong></td>
          <td><span class="badge badge-accent">#${entry.puzzle || "--"}</span></td>
          <td>
            <span class="word-spoiler ${hideWord ? "is-hidden" : ""}" 
                  onclick="this.classList.toggle('is-hidden')"
                  title="Cliquez pour afficher / masquer">
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
        </tr>`;
    }).join("");

    DOM.historyTbody.innerHTML = html;
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

    DOM.manualRefreshBtn.addEventListener("click", async () => {
      DOM.manualRefreshBtn.disabled = true;
      await fetchData();
      showToast("Données actualisées !");
      setTimeout(() => {
        DOM.manualRefreshBtn.disabled = false;
      }, 1000);
    });
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
  }

  document.addEventListener("DOMContentLoaded", init);
})();
