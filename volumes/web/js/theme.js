/**
 * Cémantix Solver — Thème (Clair/Sombre) & Mode Anti-Spoiler
 */
import { showToast } from "./utils.js";

export const themeState = {
  theme: localStorage.getItem("cemantix_theme") || "dark",
  globalSpoiler: localStorage.getItem("cemantix_spoiler") !== "false",
  isSpoiled: true,
};

export function initTheme() {
  const html = document.documentElement;
  html.setAttribute("data-theme", themeState.theme);
  updateThemeIcon();

  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", toggleTheme);
  }

  initSpoiler();
}

export function updateThemeIcon() {
  const themeToggle = document.getElementById("theme-toggle");
  if (!themeToggle) return;
  const icon = themeToggle.querySelector(".theme-icon");
  if (icon) {
    icon.textContent = themeState.theme === "dark" ? "☀️" : "🌙";
  }
}

export function toggleTheme() {
  themeState.theme = themeState.theme === "dark" ? "light" : "dark";
  localStorage.setItem("cemantix_theme", themeState.theme);
  document.documentElement.setAttribute("data-theme", themeState.theme);
  updateThemeIcon();
}

export function initSpoiler() {
  themeState.isSpoiled = themeState.globalSpoiler;
  updateSpoilerState();

  const spoilerToggle = document.getElementById("global-spoiler-toggle");
  if (spoilerToggle) {
    spoilerToggle.addEventListener("click", toggleGlobalSpoiler);
  }
}

export function updateSpoilerState() {
  const secretWordCard = document.getElementById("secret-word-card");
  if (secretWordCard) {
    if (themeState.isSpoiled) {
      secretWordCard.classList.add("is-spoiled");
    } else {
      secretWordCard.classList.remove("is-spoiled");
    }
  }

  const spoilerToggle = document.getElementById("global-spoiler-toggle");
  if (spoilerToggle) {
    const icon = spoilerToggle.querySelector(".spoiler-icon");
    if (icon) {
      icon.textContent = themeState.globalSpoiler ? "🛡️" : "👁️";
    }
  }
}

export function toggleGlobalSpoiler(onSpoilerChangeCallback) {
  themeState.globalSpoiler = !themeState.globalSpoiler;
  localStorage.setItem("cemantix_spoiler", themeState.globalSpoiler);
  themeState.isSpoiled = themeState.globalSpoiler;
  updateSpoilerState();
  if (typeof onSpoilerChangeCallback === "function") {
    onSpoilerChangeCallback();
  }
  showToast(themeState.globalSpoiler ? "Mode anti-spoiler activé" : "Mode anti-spoiler désactivé");
}
