/**
 * Cémantix Solver — Dashboard, Mot du Jour & Historique
 */
import { formatDateFr, getTierClass, getTierWeatherIcon, showToast } from "./utils.js";
import { themeState } from "./theme.js";
import { initMidnightCountdown } from "./countdown.js";
import { initTrajectoryModal, openTrajectoryModal } from "./trajectory.js";

export const dashboardState = {
  data: null,
  searchQuery: "",
  cluesVisible: true,
};

export function initDashboard() {
  const secretWordCard = document.getElementById("secret-word-card");
  const revealWordBtn = document.getElementById("reveal-word-btn");
  const hideWordBtn = document.getElementById("hide-word-btn");
  const copyWordBtn = document.getElementById("copy-word-btn");
  const cluesToggleBtn = document.getElementById("clues-toggle-btn");
  const revealCluesBtn = document.getElementById("reveal-clues-btn");
  const historySearch = document.getElementById("history-search");
  const historyTbody = document.getElementById("history-tbody");
  const manualRefreshBtn = document.getElementById("manual-refresh-btn");

  if (revealWordBtn) {
    revealWordBtn.addEventListener("click", () => {
      themeState.isSpoiled = false;
      secretWordCard?.classList.remove("is-spoiled");
    });
  }

  if (hideWordBtn) {
    hideWordBtn.addEventListener("click", () => {
      themeState.isSpoiled = true;
      secretWordCard?.classList.add("is-spoiled");
    });
  }

  if (copyWordBtn) {
    copyWordBtn.addEventListener("click", () => {
      const secretWord = document.getElementById("secret-word");
      const word = secretWord?.textContent?.trim();
      if (word && word !== "--------") {
        navigator.clipboard.writeText(word).then(() => {
          showToast(`📋 Mot secret « ${word} » copié !`);
        }).catch(() => {
          showToast("Erreur lors de la copie.");
        });
      }
    });
  }

  // Toggle Clues
  if (cluesToggleBtn) {
    cluesToggleBtn.addEventListener("click", toggleClues);
  }
  if (revealCluesBtn) {
    revealCluesBtn.addEventListener("click", () => {
      dashboardState.cluesVisible = true;
      updateCluesVisibility();
    });
  }

  // Historique - recherche & clics de lignes
  if (historySearch) {
    historySearch.addEventListener("input", (e) => {
      dashboardState.searchQuery = e.target.value;
      renderHistoryTable();
    });
  }

  if (historyTbody) {
    historyTbody.addEventListener("click", (e) => {
      const spoilerEl = e.target.closest("[data-action='spoiler']");
      if (spoilerEl) {
        spoilerEl.classList.toggle("is-hidden");
        return;
      }
      const row = e.target.closest(".history-row-clickable");
      if (row && row.dataset.puzzle) {
        openTrajectoryModal(row.dataset.puzzle, dashboardState.data);
      }
    });
  }

  if (manualRefreshBtn) {
    manualRefreshBtn.addEventListener("click", () => {
      fetchDashboardData(true);
    });
  }

  initMidnightCountdown();
  initTrajectoryModal();
  fetchDashboardData();

  // Polling automatique toutes les 30 secondes
  setInterval(() => {
    fetchDashboardData(false);
  }, 30000);
}

export function fetchDashboardData(isManual = false) {
  const lastUpdated = document.getElementById("last-updated");
  if (isManual && lastUpdated) {
    lastUpdated.textContent = "Actualisation...";
  }

  fetch(`data.json?t=${Date.now()}`)
    .then((res) => {
      if (!res.ok) throw new Error("Fichier data.json indisponible");
      return res.json();
    })
    .then((json) => {
      dashboardState.data = json;
      renderDashboard(json);
      if (isManual) showToast("Données synchronisées avec succès");
    })
    .catch((err) => {
      console.warn("Échec récupération data.json :", err);
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

  if (puzzleBadge) puzzleBadge.textContent = current.puzzle ? `Puzzle #${current.puzzle}` : "Puzzle du jour";
  if (puzzleDate) puzzleDate.textContent = formatDateFr(current.date);
  if (secretWord) secretWord.textContent = (current.word || "--------").toUpperCase();
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
  renderClues(current.top_guesses);

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
  } else if (status === "stopped") {
    daemonBadge.classList.add("status-stopped");
    daemonStatusText.textContent = "Démon arrêté";
  } else {
    daemonBadge.classList.add("status-sleeping");
    daemonStatusText.textContent = "Veille active (00h00)";
  }
}

export function renderClues(guesses) {
  const cluesContainer = document.getElementById("clues-container");
  if (!cluesContainer) return;

  if (!guesses || !Array.isArray(guesses) || guesses.length === 0) {
    cluesContainer.innerHTML = `
      <div class="clues-empty">
        <span>Indices d'approche disponibles lors de la prochaine session de résolution.</span>
      </div>`;
    return;
  }

  const html = guesses.slice(0, 8).map((g, idx) => {
    const score = typeof g.score === "number" ? g.score : 0;
    const permille = g.permille ? `${g.permille} ‰` : "";
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

  cluesContainer.innerHTML = html;
}

function toggleClues() {
  dashboardState.cluesVisible = !dashboardState.cluesVisible;
  updateCluesVisibility();
}

function updateCluesVisibility() {
  const cluesWrapper = document.getElementById("clues-wrapper");
  const cluesBtnText = document.getElementById("clues-btn-text");
  const cluesBtnIcon = document.getElementById("clues-btn-icon");

  if (!cluesWrapper) return;
  if (dashboardState.cluesVisible) {
    cluesWrapper.classList.remove("is-hidden");
    if (cluesBtnText) cluesBtnText.textContent = "Masquer";
    if (cluesBtnIcon) cluesBtnIcon.textContent = "👁️";
  } else {
    cluesWrapper.classList.add("is-hidden");
    if (cluesBtnText) cluesBtnText.textContent = "Afficher";
    if (cluesBtnIcon) cluesBtnIcon.textContent = "🙈";
  }
}

export function renderHistoryTable() {
  const historyTbody = document.getElementById("history-tbody");
  if (!historyTbody || !dashboardState.data || !dashboardState.data.history) return;

  let items = dashboardState.data.history;
  const q = dashboardState.searchQuery.trim().toLowerCase();

  if (q) {
    items = items.filter((h) => {
      const word = (h.word || "").toLowerCase();
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
    return;
  }

  const html = items.map((entry) => {
    const isWinner = entry.win !== false;
    const wordText = (entry.word || "inconnu").toUpperCase();
    const hideWord = themeState.globalSpoiler;
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

  historyTbody.innerHTML = html;
}
