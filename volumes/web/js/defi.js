/**
 * Cémantix Solver — Mode « Défier le Bot » (DEFI-15/16)
 * ======================================================
 * Le joueur propose un mot ; l'API web l'empile, le worker le résout, et cette
 * page affiche les coups **en direct** via SSE, avec repli polling si le flux
 * tombe. Rendu identique à la trajectoire du mot du jour (mêmes classes CSS,
 * même modal). Toute valeur affichée passe par escapeHtml() — règle du projet.
 */
import { escapeHtml, getTierClass, getTierWeatherIcon } from "./utils.js";
import { initTrajectoryModal, openTrajectoryModal } from "./trajectory.js";

const API = "/api/challenge";
const POLL_MS = 2000;
const MAX_RECONNECTS = 3;

let currentId = null;
let steps = [];
let stream = null;
let pollTimer = null;
let chronoTimer = null;
let startedAt = 0;
let reconnects = 0;
let lastDone = null;

function el(id) {
  return document.getElementById(id);
}

function setStatus(msg) {
  const box = el("defi-status");
  if (box) box.textContent = msg;
}

function startChrono() {
  startedAt = Date.now();
  stopChrono();
  chronoTimer = setInterval(() => {
    const badge = el("defi-chrono");
    if (badge) badge.textContent = `⏱️ ${((Date.now() - startedAt) / 1000).toFixed(0)} s`;
  }, 1000);
}

function stopChrono() {
  if (chronoTimer) clearInterval(chronoTimer);
  chronoTimer = null;
}

/** Ligne de coup — même gabarit que la timeline de la modal trajectoire. */
function stepRowHtml(item) {
  const score = typeof item.score === "number" ? item.score : 0;
  const isWin = item.permille === 1000;
  const isRecord = item.is_record && !isWin;
  const hasP = item.permille !== null && item.permille !== undefined;
  const permilleText = hasP ? `${item.permille} ‰` : "Hors 1000";
  const permilleClass = hasP ? getTierClass(score) : "tier-ice";
  const weather = item.weather || getTierWeatherIcon(score, item.permille);

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
    <div class="trajectory-step-card ${isWin ? "is-win" : ""} ${isRecord ? "is-record" : ""}">
      <div class="step-left">
        <span class="step-num">#${escapeHtml(String(item.step || ""))}</span>
        <span class="step-source-badge ${sourceClass}">${sourceLabel}</span>
        <strong class="step-word">${escapeHtml(String(item.word || ""))}</strong>
        ${isRecord ? '<span class="step-record-star" title="Nouveau record thermique du bot !">⭐ Record</span>' : ""}
        ${isWin ? '<span class="badge badge-success" style="font-size: 0.65rem; padding: 1px 6px;">🏆 Cible</span>' : ""}
      </div>
      <div class="step-right">
        <span class="step-weather" title="Indicateur d'ambiance">${escapeHtml(weather)}</span>
        <span class="step-temp ${getTierClass(score)}">${score >= 0 ? "+" : ""}${score.toFixed(2)}°C</span>
        <span class="step-permille ${permilleClass}">${escapeHtml(permilleText)}</span>
      </div>
    </div>`;
}

function renderSteps() {
  const box = el("defi-guesses");
  if (!box) return;
  if (!steps.length) {
    box.innerHTML = '<div class="clues-empty"><span>Le bot cherche… premier coup imminent.</span></div>';
    return;
  }
  box.innerHTML = steps.map(stepRowHtml).join("");
  box.scrollTop = box.scrollHeight;
}

function mergeSteps(incoming) {
  if (!Array.isArray(incoming)) return;
  incoming.forEach((s) => {
    if (s && !steps.some((e) => e.step === s.step)) steps.push(s);
  });
  steps.sort((a, b) => (a.step || 0) - (b.step || 0));
  renderSteps();
}

function showResult(done) {
  stopChrono();
  closeStream();
  lastDone = done;
  const card = el("defi-result");
  const title = el("defi-result-title");
  const line = el("defi-result-line");
  if (!card || !title || !line) return;
  if (done.status === "solved") {
    title.textContent = "🏆 Le bot a trouvé votre mot !";
    line.textContent = `« ${done.word || ""} » retrouvé en ${done.tries_count} coups (${(done.duration_seconds || 0).toFixed(1)} s).`;
  } else if (done.status === "lost") {
    title.textContent = "😅 Le bot a perdu — beau jeu !";
    line.textContent = `Pas trouvé en ${done.tries_count} coups (${(done.duration_seconds || 0).toFixed(1)} s). Votre mot lui a résisté.`;
  } else {
    title.textContent = "⚠️ Défi interrompu";
    line.textContent = done.error || "Le bot n'a pas pu mener ce défi au bout.";
  }
  card.style.display = "";
  const submit = el("defi-submit");
  if (submit) submit.disabled = false;
  setStatus("Défi terminé — lancez-en un autre (dans la limite de 10 par heure).");
}

function openFullTrajectory() {
  if (!lastDone) return;
  const entry = {
    puzzle: "Défi",
    date: new Date().toLocaleDateString("fr-FR"),
    word: lastDone.word || null,
    win: lastDone.status === "solved",
    tries: lastDone.tries_count,
    duration_seconds: lastDone.duration_seconds,
    source: "rag",
    trajectory: steps,
  };
  openTrajectoryModal("Défi", { current: entry }, lastDone.word || null);
}

function closeStream() {
  if (stream) {
    stream.close();
    stream = null;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function openStream(id) {
  if (typeof EventSource === "undefined") {
    startPolling(id);
    return;
  }
  stream = new EventSource(`${API}/${id}/stream`);
  stream.onmessage = (evt) => {
    let payload;
    try {
      payload = JSON.parse(evt.data);
    } catch (_e) {
      return;
    }
    if (payload.event === "step" && payload.step) {
      mergeSteps([payload.step]);
      setStatus(`Le bot joue… ${steps.length} coup(s).`);
    } else if (payload.event === "done") {
      showResult(payload);
    } else if (payload.event === "gone" || payload.event === "timeout") {
      closeStream();
      startPolling(id);
    }
  };
  stream.onerror = () => {
    // Repli polling (DEFI-15) : l'EventSource est fermé, on relit l'état borné.
    closeStream();
    if (reconnects < MAX_RECONNECTS) {
      reconnects += 1;
      setStatus("Suivi direct interrompu — bascule en rafraîchissement simple.");
      startPolling(id);
    } else {
      setStatus("Suivi indisponible. Rechargez la page pour reprendre le suivi.");
    }
  };
}

function startPolling(id) {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    fetch(`${API}/${id}`, { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (["solved", "lost", "error"].includes(data.status)) {
          showResult({
            status: data.status,
            tries_count: data.tries_count,
            duration_seconds: data.duration_seconds,
            word: data.word,
            error: data.error,
          });
        } else {
          setStatus(`Le bot cherche… ${data.tries_count || 0} coup(s) joué(s).`);
        }
      })
      .catch(() => {});
  }, POLL_MS);
}

async function submitChallenge(word) {
  const submit = el("defi-submit");
  if (submit) submit.disabled = true;
  closeStream();
  steps = [];
  reconnects = 0;
  lastDone = null;
  renderSteps();
  el("defi-result").style.display = "none";

  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 201 && data.id) {
      currentId = data.id;
      const quota = data.quota_restant === "unlimited" ? "illimité" : `${data.quota_restant} restant(s)`;
      setStatus(`Défi accepté dans la file (quota : ${quota}). Le worker démarre…`);
      startChrono();
      openStream(data.id);
    } else if (res.status === 429) {
      const mins = Math.ceil((data.retry_after || 60) / 60);
      setStatus(`Trop de défis : 10 autorisés par heure. Réessayez dans ~${mins} min.`);
      if (submit) submit.disabled = false;
    } else {
      setStatus(data.error || "Mot non reconnu — un seul mot français, 3 à 24 lettres.");
      if (submit) submit.disabled = false;
    }
  } catch (_err) {
    setStatus("Connexion impossible au serveur. Réessayez dans un instant.");
    if (submit) submit.disabled = false;
  }
}

export function initDefi() {
  initTrajectoryModal();
  const form = el("defi-form");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = el("defi-word");
    const word = (input.value || "").trim().toLowerCase();
    if (word) submitChallenge(word);
  });

  const retry = el("defi-retry");
  if (retry) {
    retry.addEventListener("click", () => {
      el("defi-result").style.display = "none";
      const input = el("defi-word");
      if (input) {
        input.value = "";
        input.focus();
      }
    });
  }

  const full = el("defi-full-trajectory");
  if (full) full.addEventListener("click", openFullTrajectory);
}

if (document.getElementById("defi-form")) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDefi);
  } else {
    initDefi();
  }
}

