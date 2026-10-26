/**
 * Cémantix Solver — Modal de Trajectoire et Débriefing IA
 */
import { escapeHtml, getTierClass, getTierWeatherIcon, showToast } from "./utils.js";

let activeTrajectoryEntry = null;
let activeTrajectoryFilter = "all";

export function initTrajectoryModal() {
  const modal = document.getElementById("trajectory-modal");
  const closeBtn = document.getElementById("modal-close-btn");
  const bottomCloseBtn = document.getElementById("modal-bottom-close-btn");
  const copyBtn = document.getElementById("copy-trajectory-btn");
  const secretWordEl = document.getElementById("modal-secret-word");
  const filterBtns = document.querySelectorAll("#trajectory-filter-group .pill-btn");

  if (closeBtn) closeBtn.addEventListener("click", closeTrajectoryModal);
  if (bottomCloseBtn) bottomCloseBtn.addEventListener("click", closeTrajectoryModal);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeTrajectoryModal();
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && modal.style.display === "flex") {
      closeTrajectoryModal();
    }
  });

  if (copyBtn) {
    copyBtn.addEventListener("click", copyTrajectorySummary);
  }

  if (secretWordEl) {
    secretWordEl.addEventListener("click", () => {
      secretWordEl.classList.toggle("is-hidden");
    });
  }

  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeTrajectoryFilter = btn.dataset.filter || "all";
      renderTrajectoryList();
    });
  });
}

export function openTrajectoryModal(puzzleId, data) {
  if (!data) return;
  const puzzleStr = String(puzzleId);
  let entry = (data.history || []).find((h) => String(h.puzzle) === puzzleStr);
  if (!entry && data.current && String(data.current.puzzle) === puzzleStr) {
    entry = data.current;
  }
  if (!entry && data.history && data.history.length > 0) {
    entry = data.history[0];
  }
  if (!entry) return;

  activeTrajectoryEntry = entry;
  activeTrajectoryFilter = "all";

  const modalPuzzleBadge = document.getElementById("modal-puzzle-badge");
  const modalDateBadge = document.getElementById("modal-date-badge");
  const modalWinBadge = document.getElementById("modal-win-badge");
  const modalSecretWord = document.getElementById("modal-secret-word");
  const modalTries = document.getElementById("modal-tries");
  const modalDuration = document.getElementById("modal-duration");
  const modalEngine = document.getElementById("modal-engine");
  const modalBestWord = document.getElementById("modal-best-word");
  const countAll = document.getElementById("count-all");
  const countSeeds = document.getElementById("count-seeds");
  const countRag = document.getElementById("count-rag");
  const countHot = document.getElementById("count-hot");
  const filterBtns = document.querySelectorAll("#trajectory-filter-group .pill-btn");
  const modal = document.getElementById("trajectory-modal");

  if (modalPuzzleBadge) modalPuzzleBadge.textContent = `Puzzle #${entry.puzzle || "--"}`;
  if (modalDateBadge) modalDateBadge.textContent = entry.date || "--";
  if (modalWinBadge) {
    const isWinner = entry.win !== false;
    modalWinBadge.className = `badge ${isWinner ? "badge-success" : ""}`;
    modalWinBadge.textContent = isWinner ? "🏆 Trouvé avec succès" : "⏳ Non résolu";
  }
  if (modalSecretWord) {
    modalSecretWord.textContent = (entry.word || "inconnu").toUpperCase();
    modalSecretWord.classList.add("is-hidden");
  }

  if (modalTries) modalTries.textContent = `${entry.tries || "--"} coups`;
  if (modalDuration) modalDuration.textContent = entry.duration_seconds ? `${entry.duration_seconds}s` : "--";
  if (modalEngine) modalEngine.textContent = entry.source === "llm" ? "Hybride LLM" : "100% RAG Mathématique";

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

  const bestWarm = traj.filter((t) => t.permille !== 1000).sort((a, b) => (b.permille || 0) - (a.permille || 0))[0];
  if (modalBestWord) {
    modalBestWord.textContent = bestWarm ? `${bestWarm.word} (${bestWarm.permille} ‰)` : "--";
  }

  if (countAll) countAll.textContent = traj.length;
  if (countSeeds) countSeeds.textContent = traj.filter((t) => t.source === "seed").length;
  if (countRag) countRag.textContent = traj.filter((t) => t.source === "rag" || t.source === "sniper" || t.source === "llm").length;
  if (countHot) countHot.textContent = traj.filter((t) => t.permille !== null && t.permille >= 1).length;

  filterBtns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === "all");
  });

  renderTrajectoryList();

  if (modal) {
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
  }
}

export function closeTrajectoryModal() {
  const modal = document.getElementById("trajectory-modal");
  if (modal) {
    modal.style.display = "none";
    document.body.style.overflow = "";
  }
}

function renderTrajectoryList() {
  const listEl = document.getElementById("trajectory-list");
  if (!listEl) return;
  const traj = (activeTrajectoryEntry && (activeTrajectoryEntry._computedTrajectory || activeTrajectoryEntry.trajectory)) || [];
  if (traj.length === 0) {
    listEl.innerHTML = `
      <div class="clues-empty">
        <span>Aucune étape détaillée consignée pour ce puzzle.</span>
      </div>`;
    return;
  }
  let filtered = traj;
  if (activeTrajectoryFilter === "seeds") {
    filtered = traj.filter((t) => t.source === "seed");
  } else if (activeTrajectoryFilter === "rag") {
    filtered = traj.filter((t) => t.source === "rag" || t.source === "sniper" || t.source === "llm");
  } else if (activeTrajectoryFilter === "hot") {
    filtered = traj.filter((t) => t.permille !== null && t.permille >= 1);
  }

  if (filtered.length === 0) {
    listEl.innerHTML = `
      <div class="clues-empty">
        <span>Aucun coup dans cette catégorie de filtrage.</span>
      </div>`;
    return;
  }

  const html = filtered.map((item) => {
    const isWin = item.permille === 1000;
    const isRecord = item.is_record && !isWin;
    const score = typeof item.score === "number" ? item.score : 0;
    const permilleText = item.permille !== null ? `${item.permille} ‰` : "Hors 1000";
    const permilleClass = item.permille !== null ? getTierClass(score) : "tier-ice";
    const weather = item.weather || getTierWeatherIcon(score, item.permille);
    const gaugePercent = item.permille !== null ? Math.min(100, Math.max(8, item.permille / 10)) : Math.max(0, Math.min(100, score + 20));

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
          <strong class="step-word copyable-word" data-copy="${escapeHtml(item.word)}" title="Cliquer pour copier le mot">
            ${escapeHtml(item.word)}
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

  listEl.innerHTML = html;
}

function copyTrajectorySummary() {
  if (!activeTrajectoryEntry) return;
  const e = activeTrajectoryEntry;
  const traj = e.trajectory || [];
  const bestWarm = traj.filter((t) => t.permille !== 1000).sort((a, b) => (b.permille || 0) - (a.permille || 0))[0];

  const lines = [
    `🎯 Cémantix — Trajectoire Bot (Puzzle #${e.puzzle || "--"} du ${e.date || "--"})`,
    `Mot cible : ${(e.word || "").toUpperCase()}`,
    `Statut : ${e.win ? "Trouvé" : "Non trouvé"} en ${e.tries || "--"} coups (${e.duration_seconds || "--"}s) via ${e.source === "llm" ? "Hybride LLM" : "100% RAG Mathématique"}`,
    `Meilleur palier chaud : ${bestWarm ? `${bestWarm.word} (${bestWarm.permille} ‰, +${bestWarm.score.toFixed(2)}°C)` : "--"}`,
    `\nChronologie des coups joués :`,
    ...traj.map((t) => `  #${t.step.toString().padStart(2, "0")} [${t.source.toUpperCase().padEnd(4, " ")}] ${t.word.padEnd(16, " ")} ${t.score >= 0 ? "+" : ""}${t.score.toFixed(2)}°C ${t.weather} ${t.permille ? `${t.permille} ‰` : ""}${t.is_record ? " ⭐" : ""}`),
    `\n🔗 https://cemantix.cyril-randon.fr`,
  ];

  navigator.clipboard.writeText(lines.join("\n")).then(() => {
    showToast("📋 Trajectoire complète copiée dans le presse-papier !");
  }).catch(() => {
    showToast("Erreur lors de la copie.");
  });
}
