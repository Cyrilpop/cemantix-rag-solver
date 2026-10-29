/**
 * Cémantix Solver — Thème (Clair/Sombre) & Mode Anti-Spoiler
 */
import { showToast } from "./utils.js";

export const themeState = {
  theme: localStorage.getItem("cemantix_theme") || "dark",
  globalSpoiler: localStorage.getItem("cemantix_spoiler") !== "false",
  isSpoiled: true,
};

export function activateDeferredStyles() {
  for (const link of document.querySelectorAll("link[data-deferred-css]")) {
    if (link.media === "all") continue;
    const enable = () => {
      if (link.media !== "all") link.media = "all";
    };
    if (link.sheet || document.readyState === "complete") {
      enable();
    } else {
      link.addEventListener("load", enable, { once: true });
      window.addEventListener("load", enable, { once: true });
    }
  }
}

export function initTheme() {
  activateDeferredStyles();

  const html = document.documentElement;
  if (html.getAttribute("data-theme") !== themeState.theme) {
    html.setAttribute("data-theme", themeState.theme);
  }
  updateThemeIcon();

  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle && !themeToggle.dataset.boundTheme) {
    themeToggle.dataset.boundTheme = "1";
    themeToggle.addEventListener("click", toggleTheme);
  }

  initSpoiler();
  initMobileNavScroll();
  initMobileKeyboardAdapt();
}

export function initMobileKeyboardAdapt() {
  const html = document.documentElement;
  if (html.dataset.boundKeyboard) return;
  html.dataset.boundKeyboard = "1";

  const isTextInput = (el) =>
    Boolean(
      el &&
        (el.tagName === "TEXTAREA" ||
          (el.tagName === "INPUT" &&
            !["button", "submit", "checkbox", "radio", "hidden"].includes(el.type)))
    );

  const syncKeyboardState = () => {
    if (window.innerWidth > 768) {
      html.classList.remove("is-keyboard-open");
      return;
    }
    const activeFocused = isTextInput(document.activeElement);
    const vv = window.visualViewport;
    const viewportShrunk = vv
      ? vv.height < 540 || vv.height < window.innerHeight * 0.82
      : window.innerHeight < 540;
    html.classList.toggle("is-keyboard-open", activeFocused && viewportShrunk);
  };

  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncKeyboardState, { passive: true });
  }
  window.addEventListener("resize", syncKeyboardState, { passive: true });
  document.addEventListener("focusin", () => setTimeout(syncKeyboardState, 80));
  document.addEventListener("focusout", () => setTimeout(syncKeyboardState, 80));
}

export function initMobileNavScroll() {
  const navTabs = document.querySelector(".nav-tabs");
  const activeTab = navTabs ? navTabs.querySelector(".nav-tab.active") : null;
  if (!navTabs || !activeTab || activeTab === navTabs.firstElementChild) return;

  requestAnimationFrame(() => {
    if (window.innerWidth > 768) return;
    if (navTabs.scrollWidth > navTabs.clientWidth) {
      const targetLeft =
        activeTab.offsetLeft - (navTabs.clientWidth - activeTab.offsetWidth) / 2;
      navTabs.scrollLeft = Math.max(0, targetLeft);
    }
  });
}

export function updateThemeIcon() {
  const themeToggle = document.getElementById("theme-toggle");
  if (!themeToggle) return;
  const icon = themeToggle.querySelector(".theme-icon");
  if (icon) {
    const nextIcon = themeState.theme === "dark" ? "☀️" : "🌙";
    if (icon.textContent !== nextIcon) {
      icon.textContent = nextIcon;
    }
  }
}

export function toggleTheme() {
  themeState.theme = themeState.theme === "dark" ? "light" : "dark";
  localStorage.setItem("cemantix_theme", themeState.theme);
  document.documentElement.setAttribute("data-theme", themeState.theme);
  updateThemeIcon();
}

export function initSpoiler() {
  updateSpoilerState();
  const spoilerToggle = document.getElementById("global-spoiler-toggle");
  if (spoilerToggle && !spoilerToggle.dataset.boundSpoiler) {
    spoilerToggle.dataset.boundSpoiler = "1";
    spoilerToggle.addEventListener("click", () => toggleGlobalSpoiler());
  }
}

export function updateSpoilerState() {
  const spoilerToggle = document.getElementById("global-spoiler-toggle");
  if (spoilerToggle) {
    const icon = spoilerToggle.querySelector(".spoiler-icon");
    if (icon) {
      const nextIcon = themeState.globalSpoiler ? "🛡️" : "👁️";
      if (icon.textContent !== nextIcon) {
        icon.textContent = nextIcon;
      }
    }
    const nextTitle = themeState.globalSpoiler
      ? "Mode anti-spoiler actif (cliquer pour tout révéler)"
      : "Mode anti-spoiler inactif (cliquer pour masquer)";
    if (spoilerToggle.title !== nextTitle) {
      spoilerToggle.title = nextTitle;
    }
  }
}

export function toggleGlobalSpoiler(onSpoilerChangeCallback) {
  themeState.globalSpoiler = !themeState.globalSpoiler;
  localStorage.setItem("cemantix_spoiler", themeState.globalSpoiler);
  themeState.isSpoiled = themeState.globalSpoiler;
  updateSpoilerState();

  window.dispatchEvent(new CustomEvent("cemantix:spoiler-change", {
    detail: { globalSpoiler: themeState.globalSpoiler }
  }));

  if (typeof onSpoilerChangeCallback === "function") {
    onSpoilerChangeCallback();
  }
  showToast(themeState.globalSpoiler ? "Mode anti-spoiler activé (masqué)" : "Mode anti-spoiler désactivé (tout révélé)");
}
