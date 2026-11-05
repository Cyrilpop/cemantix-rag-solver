/**
 * Cémantix Solver — Mode « Défier le Bot » (DEFI-15/16)
 * ======================================================
 * Le joueur propose un mot ; l'API web l'empile, le worker le résout, et cette
 * page affiche les coups **en direct** via SSE (avec repli polling).
 * Pour donner vie à la réflexion de l'IA, chaque coup est révélé en temps réel
 * avec une pause aléatoire entre 0.3 et 0.5 seconde (300ms à 500ms).
 * Rendu identique à la trajectoire du mot du jour (mêmes classes CSS, même modal).
 * Toute valeur affichée passe par escapeHtml() — règle du projet.
 */
import { escapeHtml } from "./utils.js";
import { initTrajectoryModal, openTrajectoryModal, buildTrajectoryStepHtml } from "./trajectory.js";

const API = "/api/challenge";
const POLL_MS = 2000;
const MAX_RECONNECTS = 3;

let currentId = null;
let currentSessionId = 0;
let displayedSteps = [];
let pendingQueue = [];
let pendingDone = null;
let isProcessingQueue = false;

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

/** Message d'attente : position dans la file, recherche, ou solveur absent. */
function waitingMessage(payload) {
  if (payload.solveur === "hors-ligne") {
    return "⚠️ Le solveur ne répond pas : ton défi est bien enregistré, mais aucun bot ne le traite pour l'instant. Réessaie plus tard.";
  }
  if (payload.status === "queued") {
    const attente = Number(payload.attente_secondes || 0);
    if (attente > 60) {
      return `⚠️ Ton défi attend depuis ${Math.round(attente / 60)} minute(s) sans que le bot le prenne : le solveur ne consomme pas la file (redéploiement du worker nécessaire).`;
    }
    const pos = payload.position;
    return (pos === null || pos === undefined)
      ? "Défi reçu — en file d'attente devant le bot."
      : `Défi reçu — position ${Number(pos) + 1} dans la file.`;
  }
  return `Le bot cherche… ${payload.tries_count || 0} coup(s) joué(s).`;
}

function resetStepsView(emptyText = "En attente d'un défi.") {
  const box = el("defi-guesses");
  if (box) {
    box.innerHTML = `<div class="clues-empty"><span>${escapeHtml(emptyText)}</span></div>`;
  }
}

function appendStepToView(step) {
  const box = el("defi-guesses");
  if (!box) return;
  const stepHtml = buildTrajectoryStepHtml(step, { showGauge: false });
  if (displayedSteps.length === 1) {
    box.innerHTML = stepHtml;
  } else {
    box.insertAdjacentHTML("beforeend", stepHtml);
  }
  box.scrollTop = box.scrollHeight;
}

async function processQueue() {
  if (isProcessingQueue) return;
  isProcessingQueue = true;
  const session = currentSessionId;

  while (pendingQueue.length > 0) {
    if (session !== currentSessionId) {
      isProcessingQueue = false;
      return;
    }

    // Pause aléatoire entre 0.3 et 0.5 seconde (300ms à 500ms) pour simuler la réflexion du bot
    const pauseMs = Math.floor(Math.random() * 200) + 300;
    await new Promise((resolve) => setTimeout(resolve, pauseMs));

    if (session !== currentSessionId) {
      isProcessingQueue = false;
      return;
    }

    const nextStep = pendingQueue.shift();
    displayedSteps.push(nextStep);
    appendStepToView(nextStep);
    setStatus(`Le bot joue… ${displayedSteps.length} coup(s).`);
  }

  isProcessingQueue = false;

  // Si le résultat terminal est arrivé pendant l'animation des coups
  if (session === currentSessionId && pendingDone) {
    // Laisser un court instant pour voir le coup gagnant avant d'afficher la carte de dénouement
    await new Promise((resolve) => setTimeout(resolve, 350));
    if (session === currentSessionId && pendingDone) {
      const donePayload = pendingDone;
      pendingDone = null;
      showResult(donePayload);
    }
  }
}

function enqueueSteps(incoming) {
  if (!Array.isArray(incoming)) return;
  let added = false;
  for (const s of incoming) {
    if (!s) continue;
    const stepNum = s.step;
    const alreadyDisplayed = displayedSteps.some((e) => e.step === stepNum);
    const alreadyQueued = pendingQueue.some((e) => e.step === stepNum);
    if (!alreadyDisplayed && !alreadyQueued) {
      pendingQueue.push(s);
      added = true;
    }
  }
  if (added) {
    pendingQueue.sort((a, b) => (a.step || 0) - (b.step || 0));
    processQueue();
  }
}

function handleDone(donePayload) {
  pendingDone = donePayload;
  // Si aucune animation n'est en cours et que la file est vide, dénouement immédiat
  if (!isProcessingQueue && pendingQueue.length === 0) {
    const payload = pendingDone;
    pendingDone = null;
    showResult(payload);
  }
}

function showResult(done) {
  stopChrono();
  closeStream();
  lastDone = done;
  const elapsedSec = startedAt > 0 ? (Date.now() - startedAt) / 1000 : (done.duration_seconds || 0);
  const displayDuration = Math.max(elapsedSec, Number(done.duration_seconds || 0)).toFixed(1);

  const card = el("defi-result");
  const title = el("defi-result-title");
  const line = el("defi-result-line");
  if (!card || !title || !line) return;
  if (done.status === "solved") {
    title.textContent = "🏆 Le bot a trouvé votre mot !";
    line.textContent = `« ${done.word || ""} » retrouvé en ${done.tries_count} coups (${displayDuration} s).`;
  } else if (done.status === "lost") {
    title.textContent = "😅 Le bot a perdu — beau jeu !";
    line.textContent = `Pas trouvé en ${done.tries_count} coups (${displayDuration} s). Votre mot lui a résisté.`;
  } else {
    title.textContent = "⚠️ Défi interrompu";
    line.textContent = done.error || "Le bot n'a pas pu mener ce défi au bout.";
  }
  card.style.display = "";
  const submit = el("defi-submit");
  if (submit) submit.disabled = false;
  setStatus("Défi terminé — lancez-en un autre (dans la limite de 10 par heure).");
  // WOF-05/06 : le défi vient d'être archivé par le worker — rafraîchit palmarès et bandeau.
  setTimeout(loadKpis, 1500);
  loadKpis();
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
    trajectory: displayedSteps,
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
  const source = new EventSource(`${API}/${id}/stream`);
  stream = source;
  source.onmessage = (evt) => {
    let payload;
    try {
      payload = JSON.parse(evt.data);
    } catch (_e) {
      return;
    }
    if (payload.event === "step" && payload.step) {
      enqueueSteps([payload.step]);
    } else if (payload.event === "done") {
      stream = null;
      source.close();
      handleDone(payload);
    } else if (payload.event === "status" || payload.event === "ping") {
      // Battement du serveur : le flux est vivant
      if (!displayedSteps.length && !pendingQueue.length) {
        setStatus(waitingMessage(payload));
      }
    } else if (payload.event === "gone" || payload.event === "timeout") {
      stream = null;
      source.close();
      startPolling(id);
    }
  };
  source.onerror = () => {
    // Un flux coupé n'est pas une fin de défi : reconnexion puis repli polling
    if (stream !== source) return;
    stream = null;
    source.close();
    if (reconnects < MAX_RECONNECTS) {
      reconnects += 1;
      setStatus("Suivi direct interrompu — reconnexion…");
      setTimeout(() => {
        if (currentId === id && !pollTimer) openStream(id);
      }, 1000 * reconnects);
    } else {
      setStatus("Suivi direct indisponible — rafraîchissement simple.");
      startPolling(id);
    }
  };
}

function startPolling(id) {
  if (pollTimer) return;
  const session = currentSessionId;
  const read = () => {
    if (session !== currentSessionId) return;
    fetch(`${API}/${id}?detail=1`, { headers: { Accept: "application/json" } })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data || session !== currentSessionId) return;
        if (Array.isArray(data.trajectory) && data.trajectory.length) {
          enqueueSteps(data.trajectory);
        }
        if (["solved", "lost", "error"].includes(data.status)) {
          if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
          }
          handleDone({
            status: data.status,
            tries_count: data.tries_count,
            duration_seconds: data.duration_seconds,
            word: data.word,
            error: data.error,
          });
        } else if (!displayedSteps.length && !pendingQueue.length) {
          setStatus(waitingMessage(data));
        }
      })
      .catch(() => {});
  };
  read();
  pollTimer = setInterval(read, POLL_MS);
}

async function submitChallenge(word) {
  const submit = el("defi-submit");
  if (submit) submit.disabled = true;
  closeStream();
  stopChrono();
  currentSessionId += 1;
  displayedSteps = [];
  pendingQueue = [];
  pendingDone = null;
  isProcessingQueue = false;
  reconnects = 0;
  lastDone = null;
  resetStepsView("En attente des premiers coups du bot.");
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
      loadKpis();
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
      currentSessionId += 1;
      displayedSteps = [];
      pendingQueue = [];
      pendingDone = null;
      isProcessingQueue = false;
      closeStream();
      stopChrono();
      resetStepsView("En attente d'un défi.");
      el("defi-result").style.display = "none";
      const input = el("defi-word");
      if (input) {
        input.value = "";
        input.focus();
      }
      setStatus("Le bot attend votre mot. Un seul mot français du dictionnaire Cémantix, 3 à 24 lettres.");
    });
  }

  const full = el("defi-full-trajectory");
  if (full) full.addEventListener("click", openFullTrajectory);

  const wall = el("defi-wall-of-fame");
  if (wall) wall.addEventListener("click", onWallClick);

  const filterGroup = el("defi-list-filters");
  if (filterGroup) {
    filterGroup.addEventListener("click", (evt) => {
      const btn = evt.target.closest("button.pill-btn");
      if (!btn || btn.classList.contains("active")) return;
      filterGroup.querySelectorAll(".pill-btn").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      activeChallengeFilter = btn.dataset.filter || "all";
      renderChallengesList();
    });
  }

  loadKpis();
}

// --------------------------------------------------------------------------- //
// M9 — Wall of Fame, KPIs communautaires, bandeau visiteur, replay (WOF-03..06)
// --------------------------------------------------------------------------- //
const FETCH_JSON = { headers: { Accept: "application/json" } };
let challengesList = [];
let activeChallengeFilter = "all";

function animateCount(node, target, decimals = 0) {
  if (!node) return;
  const suffix = node.dataset.suffix || "";
  const fmt = (v) => `${v.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !Number.isFinite(target)) {
    node.textContent = fmt(Number.isFinite(target) ? target : 0);
    return;
  }
  const start = performance.now();
  const duration = 600;
  const tick = (now) => {
    const t = Math.min(1, (now - start) / duration);
    node.textContent = fmt(target * t);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function renderKpis(glob) {
  if (!glob) return;
  animateCount(el("kpi-bot-win-rate"), Number(glob.bot_win_rate_pct || 0), 1);
  animateCount(el("kpi-total"), Number(glob.total_challenges || 0));
  animateCount(el("kpi-avg-tries"), Number(glob.avg_tries || 0), 1);
  animateCount(el("kpi-wall-count"), Number(glob.wall_of_fame_count || 0));
}

function renderPlayerBanner(player) {
  const banner = el("defi-player-banner");
  if (!banner || !player) return;
  const remaining = player.quota_remaining === "unlimited"
    ? "défis illimités"
    : `${player.quota_remaining} défi${player.quota_remaining > 1 ? "s" : ""} restant${player.quota_remaining > 1 ? "s" : ""} cette heure-ci`;
  const name = player.display_name || "Visiteur";
  if (player.total_played > 0) {
    banner.textContent = `Bienvenue ${name} — ${player.player_wins} victoire${player.player_wins > 1 ? "s" : ""} / ` +
      `${player.total_played} défi${player.total_played > 1 ? "s" : ""} lancé${player.total_played > 1 ? "s" : ""} ` +
      `(${Math.round(player.player_win_rate_pct)} %) • ${remaining}`;
  } else {
    banner.textContent = `Bienvenue ${name} — aucun défi lancé pour l'instant • ${remaining}`;
  }
  banner.hidden = false;
}

function renderChallengesList() {
  const box = el("defi-wall-of-fame");
  if (!box) return;

  const items = challengesList.filter((it) => {
    if (activeChallengeFilter === "lost") return it.outcome === "lost";
    if (activeChallengeFilter === "won") return it.outcome === "won" || it.outcome === "solved";
    return true;
  });

  if (!items.length) {
    const emptyMsg = activeChallengeFilter === "lost"
      ? "Aucun mot invaincu pour l'instant — soyez le premier !"
      : (activeChallengeFilter === "won" ? "Aucune victoire bot enregistrée." : "Aucun défi pour l'instant.");
    box.innerHTML = `<li class="clues-empty"><span>${escapeHtml(emptyMsg)}</span></li>`;
    return;
  }

  box.innerHTML = items.map((it) => {
    const isBotWon = it.outcome === "won" || it.outcome === "solved";
    const date = it.date ? new Date(it.date).toLocaleDateString("fr-FR") : "";
    const badgeHtml = isBotWon
      ? `<span class="badge" style="font-size:0.72rem;font-weight:700;color:var(--success,#3fb950);background:rgba(63,185,80,0.12);border:1px solid rgba(63,185,80,0.35);padding:2px 8px;border-radius:999px;">🤖 Bot a trouvé (${escapeHtml(String(it.tries_count))} coups)</span>`
      : `<span class="badge" style="font-size:0.72rem;font-weight:700;color:var(--tier-warm,#f59e0b);background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.45);padding:2px 8px;border-radius:999px;">🏆 Mot invaincu (${escapeHtml(String(it.tries_count))} coups)</span>`;

    return `<li class="guess-row" style="display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;justify-content:space-between;padding:.5rem .75rem;">
      <div style="min-width:0;flex:1 1 auto;display:flex;flex-direction:column;gap:3px;">
        <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;">
          <strong style="font-size:0.95rem;letter-spacing:0.02em;">${escapeHtml(it.secret_word)}</strong>
          ${badgeHtml}
        </div>
        <div class="card-subtitle" style="font-size:0.74rem;">
          ${escapeHtml(it.player)} · ${escapeHtml(date)}${it.duration_seconds ? ` · ${escapeHtml(String(it.duration_seconds))} s` : ""}
        </div>
      </div>
      <button type="button" class="btn btn-secondary btn-sm" data-challenge-id="${escapeHtml(it.challenge_id)}" style="flex-shrink:0;">👁️ Revoir</button>
    </li>`;
  }).join("");
}

/** Charge (ou recharge) KPIs, liste des défis et bandeau. Silencieux en cas d'échec. */
async function loadKpis() {
  try {
    const res = await fetch(`${API}/kpis`, FETCH_JSON);
    if (!res.ok) return;
    const data = await res.json();
    renderKpis(data.global);
    challengesList = Array.isArray(data.recent_challenges) && data.recent_challenges.length
      ? data.recent_challenges
      : (data.wall_of_fame || []);
    renderChallengesList();
    renderPlayerBanner(data.player);
  } catch (_err) {
    const box = el("defi-wall-of-fame");
    if (box && box.querySelector(".clues-empty")) {
      box.innerHTML = `<li class="clues-empty"><span>Palmarès momentanément indisponible.</span></li>`;
    }
  }
}

async function onWallClick(evt) {
  const btn = evt.target.closest("button[data-challenge-id]");
  if (!btn) return;
  btn.disabled = true;
  try {
    const res = await fetch(`${API}/${encodeURIComponent(btn.dataset.challengeId)}/guesses`, FETCH_JSON);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const entry = {
      puzzle: "Défi",
      date: "Wall of Fame",
      word: data.secret_word || null,
      win: data.outcome === "won",
      tries: data.tries_count,
      source: "rag",
      trajectory: data.steps || [],
    };
    openTrajectoryModal("Défi", { current: entry }, data.secret_word || null);
  } catch (_err) {
    setStatus("Impossible de charger le chemin de ce défi pour le moment.");
  } finally {
    btn.disabled = false;
  }
}

if (document.getElementById("defi-form")) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDefi);
  } else {
    initDefi();
  }
}
