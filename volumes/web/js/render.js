/**
 * Cémantix Solver — Rendu partagé des coups (QUAL-08)
 *
 * Mutualise la génération des lignes de coups pour multi.js et battle.js,
 * assurant la cohérence visuelle, la protection anti-XSS et le cache de rendu anti-flicker.
 */

import { escapeHtml, getTierClass, getTierWeatherIcon } from "./utils.js";

/**
 * Génère le fragment HTML d'une liste de coups.
 *
 * @param {Array<Object>} guesses Liste des coups {word, score, permille, order, is_hint, weather}
 * @param {Object} options Options de rendu
 * @param {boolean} [options.isMasked=false] Masquer les mots par des puces (anti-spoiler)
 * @param {boolean} [options.isPlayer=true] Indique si la liste appartient au joueur local
 * @param {string} [options.emptyMessage] Message personnalisé si aucun coup
 * @returns {string} Fragment HTML complet
 */
export function buildGuessesListHtml(guesses, options = {}) {
  const { isMasked = false, isPlayer = true, emptyMessage, orderFormat = "default" } = options;

  if (!guesses || guesses.length === 0) {
    const defaultMsg = isPlayer
      ? "Saisissez votre premier mot pour débuter le duel."
      : "En attente des premiers coups de votre adversaire.";
    return `
      <div class="clues-empty">
        <span>${escapeHtml(emptyMessage || defaultMsg)}</span>
      </div>
    `;
  }

  return guesses.map((g, idx) => {
    const scoreVal = Number(g.score || 0);
    const tierCls = getTierClass(scoreVal);
    const isWinner = g.permille === 1000 || scoreVal >= 100.0;
    const scoreStr = `${scoreVal.toFixed(2)}°C`;
    const permilleStr = g.permille ? `${g.permille} ‰` : "";
    const hintBadge = g.is_hint
      ? `<span class="badge-hint" title="Mot obtenu via un indice (+1 coup)">💡 Indice</span>`
      : "";
    const weatherIcon = g.weather ? g.weather.split(" ")[0] : getTierWeatherIcon(scoreVal, g.permille);

    const wordDisplay = isMasked
      ? `<span class="masked-word-pill">••••••••</span>`
      : `<span class="copyable-word" data-copy="${escapeHtml(g.word)}" style="cursor: pointer;" title="Cliquer pour copier">${escapeHtml(String(g.word || "").toUpperCase())}</span>`;

    let orderPrefix = `#${g.order || idx + 1}`;
    if (orderFormat === "brackets") {
      orderPrefix = `[${g.order || idx + 1}]`;
    } else if (orderFormat === "rank") {
      orderPrefix = `#${idx + 1}`;
    }

    return `
      <div class="guess-row ${isWinner ? "is-winner" : ""}">
        <div class="guess-left">
          <span class="guess-order">${orderPrefix}</span>
          <span class="guess-word">${wordDisplay}</span>
          ${hintBadge}
        </div>
        <div class="guess-right">
          <span class="guess-weather">${weatherIcon}</span>
          <span class="guess-temp ${tierCls}">${scoreVal >= 0 ? "+" : ""}${scoreStr}</span>
          <span class="guess-permille">${permilleStr}</span>
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Injecte la liste des coups dans le conteneur DOM spécifié en évitant les scintillements inutiles.
 *
 * @param {HTMLElement|string} container Element ou ID du conteneur
 * @param {Array<Object>} guesses Liste des coups
 * @param {Object} options Options de rendu
 */
export function renderGuessesContainer(container, guesses, options = {}) {
  const el = typeof container === "string" ? document.getElementById(container) : container;
  if (!el) return;

  const cacheKey = JSON.stringify({
    isMasked: !!options.isMasked,
    orderFormat: options.orderFormat || "default",
    items: (guesses || []).map((g) => [g.word, g.score, g.permille, g.order, g.is_hint]),
  });

  if (el._lastRenderCache === cacheKey) {
    return; // Même état, préservation du DOM existant
  }
  el._lastRenderCache = cacheKey;

  el.innerHTML = buildGuessesListHtml(guesses, options);
}
