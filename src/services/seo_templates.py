"""
Cémantix Solver — Utilitaires de Gabarit et Rendu HTML SEO (seo_templates)
========================================================================
Fournit les gabarits HTML auto-suffisants, les constantes SEO, les helpers de date
et les composants Schema.org partagés par l'ensemble du sous-système SEO.
"""
import json
import os
from pathlib import Path
import re
from datetime import datetime
from html import escape
from typing import Optional
from urllib.parse import quote

from ..config import BASE_DIR
from .layout_sync import render_header, render_nav_tabs, render_footer

WEB_ROOT = BASE_DIR / "volumes" / "web"
SITE_ORIGIN = "https://cemantix.cyril-randon.fr"
VARIABLES_CSS_FILE = WEB_ROOT / "css" / "variables.css"

ARCHIVES_DIRNAME = "puzzles"
ARCHIVES_PAGE_SIZE = 10
ARCHIVES_MAX_PAGES = 500
SITEMAP_MAX_URLS = 45000
MOT_DU_JOUR_DIRNAME = "mot-du-jour"
METHODE_DIRNAME = "methode"
ARCHIVE_TITLE_PREFIX = "Indice Cémantix du"

_MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}
_WEEKDAYS_FR = {
    0: "lundi", 1: "mardi", 2: "mercredi", 3: "jeudi", 4: "vendredi", 5: "samedi", 6: "dimanche",
}
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_CSS_ROOT_RE = re.compile(r":root\s*\{[^}]*\}", re.DOTALL)
_CSS_LIGHT_RE = re.compile(
    r'(?:@media\s*\(prefers-color-scheme:\s*light\)|\[data-theme=["\']?light["\']?\])'
    r"[^{]*\{[^}]*\}",
    re.DOTALL,
)

NAV_LINKS = [
    ("Tableau de Bord", ""),
    ("Mot du jour", "mot-du-jour/"),
    ("Archives", "puzzles/"),
    ("Méthode & indices", "methode/"),
    ("Jouer Solo", "play/"),
    ("Mode Battle", "battle/"),
    ("Défier le Bot", "defi/"),
    ("Mode Multijoueur", "multi/"),
]


# --------------------------------------------------------------------------- #
# Utilitaires de mise en forme
# --------------------------------------------------------------------------- #
def parse_puzzle_date(value) -> Optional[datetime]:
    """Valide et convertit une date `AAAA-MM-JJ` en `datetime` (None si invalide)."""
    match = _DATE_RE.match(str(value or "").strip())
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def format_date_fr(value) -> str:
    """Formate une date `AAAA-MM-JJ` en français long (« lundi 26 octobre 2026 »)."""
    parsed = parse_puzzle_date(value)
    if not parsed:
        return str(value or "")
    return (
        f"{_WEEKDAYS_FR[parsed.weekday()]} {parsed.day} "
        f"{_MONTHS_FR[parsed.month]} {parsed.year}"
    )


def archive_title(value, puzzle=None) -> str:
    """Titre SEO d'une archive : « Indice Cémantix #1700 du lundi 26 octobre 2026 ».

    Le même libellé sert de base de `<title>`, de `<h1>`, de texte d'ancre dans l'index des
    archives et de `headline` JSON-LD : un seul motif, répété, qui cible la requête
    « indice cemantix #XXX du <date> » sans dupliquer de contenu.
    """
    if puzzle:
        p_clean = str(puzzle).lstrip("#").strip()
        prefix = f"Indice Cémantix #{p_clean} du"
    else:
        prefix = ARCHIVE_TITLE_PREFIX
    return f"{prefix} {format_date_fr(value)}"


def format_clue_words_list(guesses: list, limit: int = 10) -> str:
    """Extrait et formate la liste des premiers mots indices (minuscules, séparés par virgule)."""
    words = []
    for g in (guesses or []):
        if not isinstance(g, dict):
            continue
        w = str(g.get("word") or "").strip().lower()
        if w and w != "••••••••":
            words.append(w)
            if len(words) >= limit:
                break
    return ", ".join(words)


def archive_anchor(value) -> str:
    """Texte d'ancre vers une archive : « Indices et solution du Cémantix du lundi 26 octobre 2026 ».

    L'ancre est volontairement plus large que le titre de la page cible : elle couvre
    le cluster « indice » (les deux premières requêtes de la tendance Google) tout en
    décrivant exactement ce que contient le lien.
    """
    return f"Indices et solution du Cémantix du {format_date_fr(value)}"


def hub_url(dirname: str) -> str:
    """URL absolue d'une page hub (`mot-du-jour`, `methode`, `puzzles`)."""
    return f"{SITE_ORIGIN}/{quote(str(dirname).strip('/'))}/"


def format_duration_fr(seconds) -> str:
    """Formate une durée en secondes de façon lisible (« 42,5 s », « 2 min 05 »)."""
    try:
        total = float(seconds)
    except (TypeError, ValueError):
        return "--"
    if total <= 0:
        return "--"
    if total < 60:
        return f"{total:.1f} s".replace(".", ",")
    minutes, remaining = divmod(int(round(total)), 60)
    return f"{minutes} min {remaining:02d}"


def archive_url(date_str: str) -> str:
    """URL absolue de la page d'archive d'une date `AAAA-MM-JJ`."""
    return f"{SITE_ORIGIN}/puzzles/{quote(str(date_str))}/"


def _join(base: str, href: str) -> str:
    """Concatène un préfixe relatif et un chemin sans produire de double slash."""
    return (base + href) if href else base


def _rel(href: str) -> str:
    """Chemin relatif depuis une page d'archive (profondeur /puzzles/<date>/)."""
    return _join("../../", href)


def _rel_index(href: str) -> str:
    """Chemin relatif depuis l'index des archives (profondeur /puzzles/)."""
    return _join("../", href)


def _load_style_tokens() -> str:
    """Extrait les tokens `:root` (et le bloc thème clair) de `variables.css`."""
    try:
        raw = VARIABLES_CSS_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""
    blocks = _CSS_ROOT_RE.findall(raw) + _CSS_LIGHT_RE.findall(raw)
    return "\n".join(blocks)


def _load_puzzle_css() -> str:
    """Charge et compacte `puzzle.css` pour l'injecter en `<style>` sans requête bloquante."""
    puzzle_css_file = WEB_ROOT / "css" / "puzzle.css"
    try:
        raw = puzzle_css_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    cleaned = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    return re.sub(r"\s+", " ", cleaned).strip()


# --------------------------------------------------------------------------- #
# Squelette HTML commun (auto-suffisant, sans JavaScript)
# --------------------------------------------------------------------------- #
PAGE_CSS = """
        *, *::before, *::after {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
          scrollbar-width: thin;
          scrollbar-color: var(--scrollbar-thumb) transparent;
        }
        ::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        ::-webkit-scrollbar-track {
          background: var(--scrollbar-track);
          border-radius: 9999px;
        }
        ::-webkit-scrollbar-thumb {
          background: var(--scrollbar-thumb);
          border-radius: 9999px;
          transition: background-color 0.2s ease, box-shadow 0.2s ease;
        }
        ::-webkit-scrollbar-thumb:hover {
          background: var(--scrollbar-thumb-hover);
          box-shadow: 0 0 8px var(--accent-glow);
        }
        html {
          scrollbar-gutter: stable;
          overflow-y: scroll;
        }
        html,
        body {
          width: 100%;
          max-width: 100vw;
          overflow-x: hidden;
          -webkit-text-size-adjust: 100%;
          text-size-adjust: 100%;
        }
        body {
          font-family: var(--font-main);
          background: var(--bg-app);
          color: var(--text-main);
          line-height: 1.5;
          min-height: 100vh;
          min-height: 100dvh;
          padding: 0;
          display: flex;
          flex-direction: column;
          transition: background-color 0.3s ease, color 0.3s ease;
        }
        .page {
          max-width: 1200px;
          width: 100%;
          margin: 0 auto;
          padding: 1.5rem 1.5rem 7.5rem 1.5rem;
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          box-sizing: border-box;
        }
        .app-header {
          border-bottom: 1px solid var(--border-color);
          background: var(--bg-card);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          position: sticky;
          top: 0;
          z-index: 100;
          padding-top: env(safe-area-inset-top, 0px);
        }
        .header-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0.85rem 1.5rem;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          min-width: 0;
        }
        .brand-icon {
          width: 48px;
          height: 48px;
          object-fit: contain;
          font-size: 1.8rem;
          filter: drop-shadow(0 0 8px var(--accent));
          flex-shrink: 0;
          display: block;
        }
        .brand-text {
          min-width: 0;
        }
        .brand-text .brand-title {
          display: block;
          font-size: 1.25rem;
          font-weight: 700;
          letter-spacing: -0.02em;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .brand-subtitle {
          font-size: 0.75rem;
          color: var(--text-muted);
          display: block;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .header-actions {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          flex-shrink: 0;
        }
        .btn-icon {
          width: 36px;
          height: 36px;
          border-radius: var(--radius-sm, 6px);
          background: var(--bg-input);
          border: 1px solid var(--border-color);
          color: var(--text-main);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 1.1rem;
          transition: var(--transition, all 0.2s cubic-bezier(0.4, 0, 0.2, 1));
        }
        .btn-icon:hover {
          border-color: var(--accent);
          background: var(--bg-card-hover);
        }
        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.35rem 0.75rem;
          border-radius: 9999px;
          font-size: 0.8rem;
          font-weight: 500;
          border: 1px solid var(--border-color);
          background: var(--bg-input);
        }
        .status-pulse {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: var(--accent);
          box-shadow: 0 0 8px var(--accent);
        }
        .nav-tabs {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.75rem;
          margin-bottom: 0.5rem;
        }
        .nav-tab {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 42px;
          line-height: 1;
          box-sizing: border-box;
          gap: 0.5rem;
          padding: 0 1.4rem;
          border-radius: var(--radius-lg, 16px);
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: var(--transition, all 0.2s cubic-bezier(0.4, 0, 0.2, 1));
          border: 1px solid var(--border-color);
          background: var(--bg-card);
          color: var(--text-muted);
          text-decoration: none;
        }
        .nav-tab:hover:not(.active) {
          color: var(--text-main);
          border-color: rgba(88, 166, 255, 0.4);
          transform: translateY(-1px);
        }
        .nav-tab.active {
          background: var(--accent-btn, #1668dc);
          color: #ffffff;
          border-color: rgba(88, 166, 255, 0.4);
          box-shadow: 0 0 20px var(--accent-glow);
        }
        .tab-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          line-height: 1;
        }
        .tab-badge {
          display: inline-flex;
          align-items: center;
          line-height: 1;
          font-size: 0.65rem;
          font-weight: 700;
          text-transform: uppercase;
          padding: 0.2rem 0.45rem;
          border-radius: 9999px;
          background: rgba(255, 255, 255, 0.25);
          color: #ffffff;
        }
        .breadcrumbs {
          display: inline-flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 0.45rem;
          font-size: 0.82rem;
          color: var(--text-muted);
          margin: -0.5rem 0 0.25rem 0;
          padding: 0.35rem 0.85rem;
          background: var(--bg-card);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-sm, 8px);
          width: fit-content;
        }
        .breadcrumbs a {
          color: var(--text-muted) !important;
          text-decoration: none !important;
          transition: color 0.2s ease;
          font-weight: 500;
        }
        .breadcrumbs a:hover {
          color: var(--accent) !important;
          text-decoration: underline !important;
        }
        .breadcrumbs .crumb-sep {
          opacity: 0.5;
          font-size: 0.75rem;
        }
        .breadcrumbs span:not(.crumb-sep) {
          color: var(--text-main);
          font-weight: 600;
        }
        h1 { font-size: 1.6rem; margin: .25rem 0 .75rem; }
        h2 { font-size: 1.15rem; margin: 2rem 0 .75rem; }
        p { color: var(--text-muted); margin-bottom: .75rem; }
        .card {
          background: var(--bg-card); border: 1px solid var(--border-color);
          border-radius: 12px; padding: 1.25rem; margin-top: 1rem;
        }
        .meta-list { display: flex; flex-wrap: wrap; gap: .5rem; list-style: none; }
        .meta-list li {
          border: 1px solid var(--border-color); border-radius: 999px;
          padding: .3rem .8rem; font-size: .85rem; color: var(--text-muted);
        }
        .meta-list strong { color: var(--text-main); }
        table { width: 100%; border-collapse: collapse; margin-top: .75rem; font-size: .9rem; }
        caption { text-align: left; color: var(--text-muted); font-size: .85rem; padding-bottom: .5rem; }
        th, td { text-align: left; padding: .55rem .6rem; border-bottom: 1px solid var(--border-color); }
        th { color: var(--text-main); font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }
        tbody tr:hover { background: var(--bg-card-hover); }
        td.num { text-align: right; font-variant-numeric: tabular-nums; }
        .tier-ice, .tier-cold { color: var(--tier-ice); }
        .tier-cool { color: var(--tier-cool); }
        .tier-warm { color: var(--tier-warm); }
        .tier-fire { color: var(--tier-fire); }
        .badge {
          display: inline-block; border: 1px solid var(--border-color); border-radius: 999px;
          padding: .2rem .7rem; font-size: .8rem; color: var(--text-muted);
        }
        .badge-win { border-color: var(--success); color: var(--success); }
        .reveal { margin-top: 1rem; border: 1px solid var(--border-color); border-radius: 12px; padding: 1rem 1.25rem; }
        .reveal summary { cursor: pointer; font-weight: 600; color: var(--accent); }
        .reveal-word { font-size: 1.6rem; letter-spacing: .08em; text-transform: uppercase; margin-top: .75rem; }
        .archive-list { list-style: none; display: grid; gap: .5rem; margin-top: 1rem; }
        .archive-list a {
          display: flex; flex-wrap: wrap; justify-content: space-between; gap: .5rem;
          padding: .8rem 1rem; border: 1px solid var(--border-color); border-radius: 10px;
          color: var(--text-main); text-decoration: none;
        }
        .archive-list a:hover { border-color: var(--accent); background: var(--bg-card-hover); }
        .archive-list span { color: var(--text-muted); font-size: .85rem; }
        .pager { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.5rem 0; justify-content: center; align-items: center; }
        .pager a, .pager .current, .pager-nav {
          padding: .45rem .85rem; border: 1px solid var(--border-color); border-radius: 8px;
          color: var(--text-main); text-decoration: none !important; font-size: .85rem;
          background: var(--bg-card); transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; min-height: 38px;
        }
        .pager a:hover { border-color: var(--accent); background: var(--bg-card-hover); }
        .pager .current { border-color: var(--accent); background: var(--accent-btn, #1668dc); color: #ffffff; font-weight: 700; }
        .pager .pager-gap { padding: .45rem .5rem; color: var(--text-muted); font-size: 1rem; border: none; background: transparent; user-select: none; }
        .pager .pager-nav.disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; border-color: var(--border-color); }

        .date-navigation {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
          margin: 1.25rem 0;
          flex-wrap: wrap;
        }
        .btn-nav-date {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.55rem 1.1rem;
          border-radius: var(--radius-md, 10px);
          font-size: 0.88rem;
          font-weight: 600;
          text-decoration: none !important;
          color: var(--text-main) !important;
          background: var(--bg-card);
          border: 1px solid var(--border-color);
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .btn-nav-date:hover {
          border-color: var(--accent);
          background: var(--bg-card-hover);
          color: var(--accent) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .btn-nav-date.btn-all-archives {
          background: var(--bg-input);
        }
        .btn-nav-date.disabled {
          opacity: 0.4;
          cursor: not-allowed;
          pointer-events: none;
        }

        /* Footer Universel */
        .app-footer {
          position: fixed;
          bottom: 0;
          left: 0;
          width: 100%;
          border-top: 1px solid var(--border-color);
          background: var(--bg-card);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          padding: 0.85rem 1.5rem;
          z-index: 100;
          box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.12);
        }
        .footer-container {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 1rem;
        }
        .footer-left p {
          font-size: 0.85rem;
          color: var(--text-main);
        }
        .footer-sub {
          font-size: 0.8rem;
          color: #c9d1d9;
          margin-top: 0.2rem;
          display: block;
        }
        [data-theme="light"] .footer-sub {
          color: #424a53;
        }
        .footer-author-link,
        .footer-sub a {
          color: #58a6ff;
          text-decoration: underline;
          text-underline-offset: 3px;
          font-weight: 600;
        }
        [data-theme="light"] .footer-author-link,
        [data-theme="light"] .footer-sub a {
          color: #0969da;
        }
        .footer-right {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          flex-wrap: wrap;
        }
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.4rem;
          padding: 0.5rem 1rem;
          font-size: 0.875rem;
          font-weight: 600;
          border-radius: var(--radius-sm, 6px);
          border: 1px solid transparent;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          text-decoration: none !important;
        }
        .btn-sm {
          padding: 0.3rem 0.65rem;
          font-size: 0.8rem;
        }
        .btn-ghost {
          background: transparent;
          border-color: var(--border-color);
          color: var(--text-muted) !important;
        }
        .btn-ghost:hover {
          color: var(--text-main) !important;
          background: var(--bg-input);
          border-color: var(--accent);
        }

        a:not(.archive-list a):not(.pager a):not(.nav-tab):not(.brand) {
          color: #58a6ff;
          text-decoration: underline;
          text-underline-offset: 3px;
          font-weight: 600;
          position: relative;
          display: inline;
          transition: color 0.25s ease, text-shadow 0.25s ease;
        }
        [data-theme="light"] a:not(.archive-list a):not(.pager a):not(.nav-tab):not(.brand) {
          color: #0969da;
        }
        a:not(.archive-list a):not(.pager a):not(.nav-tab):not(.brand):hover {
          color: #a5d6ff;
          text-shadow: 0 0 12px var(--accent-glow);
        }
        [data-theme="light"] a:not(.archive-list a):not(.pager a):not(.nav-tab):not(.brand):hover {
          color: #0550ae;
          text-shadow: 0 0 8px rgba(9, 105, 218, 0.25);
        }
        @media (max-width: 768px) {
          .header-container {
            padding: 0.5rem max(0.75rem, env(safe-area-inset-right, 0px)) 0.5rem max(0.75rem, env(safe-area-inset-left, 0px));
            gap: 0.5rem;
            flex-wrap: nowrap;
          }
          .brand {
            gap: 0.45rem;
            flex: 1 1 auto;
            min-width: 0;
          }
          .brand-icon {
            width: clamp(34px, 8vw, 42px);
            height: clamp(34px, 8vw, 42px);
            font-size: clamp(1.3rem, 4.2vw, 1.5rem);
          }
          .brand-text .brand-title {
            font-size: clamp(0.96rem, 3.8vw, 1.08rem);
            line-height: 1.2;
          }
          .brand-subtitle {
            font-size: clamp(0.64rem, 2.5vw, 0.7rem);
            line-height: 1.2;
          }
          .header-actions {
            gap: 0.35rem;
            flex-shrink: 0;
          }
          #daemon-badge {
            padding: 0;
            width: 36px;
            height: 36px;
            min-width: 36px;
            justify-content: center;
            flex-shrink: 0;
          }
          #daemon-status-text {
            display: none;
          }
          .page {
            padding: 0.75rem max(0.75rem, env(safe-area-inset-right, 0px)) 2rem max(0.75rem, env(safe-area-inset-left, 0px));
            gap: 0.9rem;
          }
          .nav-tabs {
            position: relative;
            flex-direction: row;
            flex-wrap: nowrap;
            justify-content: flex-start;
            width: 100%;
            max-width: 100%;
            gap: 0.35rem;
            margin-bottom: 0.25rem;
            padding: 5px 8px;
            background: var(--bg-input);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg, 16px);
            box-sizing: border-box;
            overflow-x: auto;
            overflow-y: hidden;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
          }
          .nav-tabs::-webkit-scrollbar {
            display: none;
          }
          .nav-tab {
            flex: 1 0 auto;
            width: auto;
            height: 40px;
            min-height: 40px;
            line-height: 1;
            box-sizing: border-box;
            justify-content: center;
            align-items: center;
            padding: 0 0.78rem;
            font-size: 0.82rem;
            gap: 0.4rem;
            border-radius: calc(var(--radius-lg, 16px) - 5px);
            border: 1px solid transparent;
            background: transparent;
            white-space: nowrap;
            text-align: center;
          }
          .nav-tab:hover:not(.active) {
            transform: none;
          }
          .nav-tab.active {
            background: var(--accent-btn, #1668dc);
            color: #ffffff;
            border-color: rgba(88, 166, 255, 0.4);
            box-shadow: 0 2px 10px var(--accent-glow);
          }
          .nav-tab .tab-badge {
            display: none;
          }
          .app-footer {
            position: static;
            margin-top: auto;
            padding: 1.25rem 1rem max(1rem, env(safe-area-inset-bottom, 1rem)) 1rem;
            box-shadow: none;
          }
          .footer-container {
            flex-direction: column;
            text-align: center;
            gap: 0.75rem;
            align-items: center;
            justify-content: center;
          }
          .footer-left {
            text-align: center;
          }
          .footer-right {
            flex-direction: row;
            gap: 0.4rem;
            align-items: center;
            justify-content: center;
          }
          .date-navigation {
            flex-direction: column;
            align-items: stretch;
            gap: 0.6rem;
          }
          .btn-nav-date {
            justify-content: center;
            width: 100%;
          }
          .breadcrumbs {
            font-size: 0.75rem;
            padding: 0.25rem 0.55rem;
          }
        }
        @media (max-width: 640px) {
          h1 { font-size: 1.3rem; }
          th, td { padding: .45rem .35rem; font-size: .82rem; }
        }
"""


def render_page(
    *,
    title: str,
    description: str,
    canonical: str,
    json_ld: str,
    body: str,
    breadcrumbs: str,
    resolve,
    robots_meta: str = "index, follow",
    active_tab: str = "archives",
) -> str:
    """Construit un document HTML complet, autonome et indexable par les moteurs."""
    nav = " · ".join(
        f'<a href="{escape(resolve(target), quote=True)}">{escape(label)}</a>'
        for label, target in NAV_LINKS
    )
    home = resolve("")
    header_html = render_header(depth=home)
    nav_tabs = render_nav_tabs(depth=home, active_tab=active_tab)
    footer_html = render_footer(depth=home)
    breadcrumbs_block = (
        f'    <nav class="breadcrumbs" aria-label="Fil d\'Ariane">{breadcrumbs}</nav>\n'
        if breadcrumbs
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="robots" content="{escape(robots_meta)}">
  <link rel="canonical" href="{escape(canonical, quote=True)}">
  <link rel="alternate" hreflang="fr" href="{escape(canonical, quote=True)}">
  <link rel="alternate" hreflang="x-default" href="{escape(canonical, quote=True)}">
  <meta name="theme-color" content="#0d1117">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{escape(canonical, quote=True)}">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:image" content="{SITE_ORIGIN}/og-image.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Cémantix Solver">
  <meta property="og:locale" content="fr_FR">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="{SITE_ORIGIN}/og-image.jpg">
  <link rel="icon" type="image/png" href="{home}icons/favicon.png">
  <link rel="shortcut icon" href="{home}favicon.ico">
  <link rel="apple-touch-icon" href="{home}icons/apple-touch-icon.png">
  <style>{_load_style_tokens()}{PAGE_CSS}{_load_puzzle_css()}</style>
{json_ld}
  <script>
    document.addEventListener("DOMContentLoaded", function() {{
      var toggle = document.getElementById("theme-toggle");
      if (toggle) {{
        toggle.addEventListener("click", function() {{
          var current = document.documentElement.getAttribute("data-theme") || "dark";
          var next = current === "dark" ? "light" : "dark";
          document.documentElement.setAttribute("data-theme", next);
          try {{ localStorage.setItem("cemantix_theme", next); }} catch(e) {{}}
        }});
      }}
      try {{
        var saved = localStorage.getItem("cemantix_theme");
        if (saved) document.documentElement.setAttribute("data-theme", saved);
      }} catch(e) {{}}
    }});
  </script>
</head>
<body>
{header_html}
  <div class="page">
{nav_tabs}
{breadcrumbs_block}    <main>
{body}
    </main>
  </div>
{footer_html}
</body>
</html>
"""


def _json_ld_block(payload: dict) -> str:
    """Sérialise un objet Schema.org en bloc `<script type="application/ld+json">`."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'  <script type="application/ld+json">{body}</script>'


def _archive_href(entry: dict) -> str:
    """Chemin relatif d'une page d'archive depuis une autre page d'archive."""
    return _rel(f"puzzles/{entry.get('date')}/")


def _tier_class(score) -> str:
    """Classe CSS thermique associée à un score en degrés Celsius."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "tier-cold"
    if value < 0:
        return "tier-ice"
    if value < 10:
        return "tier-cold"
    if value < 20:
        return "tier-cool"
    if value < 30:
        return "tier-warm"
    return "tier-fire"


def _clue_rows(guesses: list, limit: int = 10) -> str:
    """Lignes de tableau des mots les plus proches (indices sans spoiler)."""
    rows = []
    for idx, guess in enumerate(guesses[:limit], start=1):
        word = str(guess.get("word") or "").strip()
        if not word or word == "••••••••":
            continue
        score = guess.get("score")
        permille = guess.get("permille")
        score_txt = f"{float(score):+.2f} °C" if isinstance(score, (int, float)) else "--"
        perm_txt = f"{int(permille)} ‰" if isinstance(permille, (int, float)) else "--"
        rows.append(
            f'          <tr><td class="num">{idx}</td>'
            f'<td><strong>{escape(word.capitalize())}</strong></td>'
            f'<td class="num {escape(_tier_class(score))}">{escape(score_txt)}</td>'
            f'<td class="num">{escape(perm_txt)}</td></tr>'
        )
    return "\n".join(rows)


__all__ = [
    "WEB_ROOT",
    "SITE_ORIGIN",
    "VARIABLES_CSS_FILE",
    "ARCHIVES_DIRNAME",
    "ARCHIVES_PAGE_SIZE",
    "ARCHIVES_MAX_PAGES",
    "SITEMAP_MAX_URLS",
    "MOT_DU_JOUR_DIRNAME",
    "METHODE_DIRNAME",
    "ARCHIVE_TITLE_PREFIX",
    "_MONTHS_FR",
    "_WEEKDAYS_FR",
    "_DATE_RE",
    "_CSS_ROOT_RE",
    "_CSS_LIGHT_RE",
    "NAV_LINKS",
    "PAGE_CSS",
    "parse_puzzle_date",
    "format_date_fr",
    "format_clue_words_list",
    "archive_title",
    "archive_anchor",
    "hub_url",
    "format_duration_fr",
    "archive_url",
    "_join",
    "_rel",
    "_rel_index",
    "_load_style_tokens",
    "_load_puzzle_css",
    "render_page",
    "_json_ld_block",
    "_archive_href",
    "_tier_class",
    "_clue_rows",
]
