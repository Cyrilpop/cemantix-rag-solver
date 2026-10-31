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

WEB_ROOT = BASE_DIR / "volumes" / "web"
SITE_ORIGIN = "https://cemantix.cyril-randon.fr"
VARIABLES_CSS_FILE = WEB_ROOT / "css" / "variables.css"

ARCHIVES_DIRNAME = "puzzles"
ARCHIVES_PAGE_SIZE = 60
ARCHIVES_MAX_PAGES = 500
SITEMAP_MAX_URLS = 45000
MOT_DU_JOUR_DIRNAME = "mot-du-jour"
METHODE_DIRNAME = "methode"
ARCHIVE_TITLE_PREFIX = "Solution Cémantix du"

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


def archive_title(value) -> str:
    """Titre SEO d'une archive : « Solution Cémantix du lundi 26 octobre 2026 ».

    Le même libellé sert de `<title>`, de `<h1>`, de texte d'ancre dans l'index des
    archives et de `headline` JSON-LD : un seul motif, répété, qui cible la requête
    « solution cemantix du <date> » sans dupliquer de contenu.
    """
    return f"{ARCHIVE_TITLE_PREFIX} {format_date_fr(value)}"


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
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          font-family: var(--font-main);
          background: var(--bg-app);
          color: var(--text-main);
          line-height: 1.6;
          min-height: 100vh;
          padding: 0 1rem 3rem;
        }
        .page { max-width: 960px; margin: 0 auto; }
        .site-header {
          display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem 1rem;
          padding: 1.5rem 0 1rem; border-bottom: 1px solid var(--border-color);
        }
        .site-title { font-size: 1.25rem; font-weight: 700; }
        .site-title a { color: var(--text-main); text-decoration: none; }
        .site-subtitle { color: var(--text-muted); font-size: .85rem; }
        .breadcrumbs { margin: 1.25rem 0 .5rem; font-size: .85rem; color: var(--text-muted); }
        .breadcrumbs a { color: var(--accent); text-decoration: none; }
        .breadcrumbs a:hover { text-decoration: underline; }
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
        .pager { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.5rem 0; }
        .pager a, .pager .current {
          padding: .4rem .8rem; border: 1px solid var(--border-color); border-radius: 8px;
          color: var(--text-main); text-decoration: none; font-size: .85rem;
        }
        .pager a:hover { border-color: var(--accent); }
        .pager .current { border-color: var(--accent); color: var(--accent); }
        .site-footer {
          margin-top: 2.5rem; padding-top: 1.25rem;
          border-top: 1px solid var(--border-color); font-size: .85rem; color: #c9d1d9;
        }
        [data-theme="light"] .site-footer { color: #424a53; }

        a:not(.archive-list a):not(.pager a):not(.site-title a) {
          color: #58a6ff;
          text-decoration: underline;
          text-underline-offset: 3px;
          font-weight: 600;
          position: relative;
          display: inline;
          transition: color 0.25s ease, text-shadow 0.25s ease;
        }
        [data-theme="light"] a:not(.archive-list a):not(.pager a):not(.site-title a) {
          color: #0969da;
        }
        a:not(.archive-list a):not(.pager a):not(.site-title a):hover {
          color: #a5d6ff;
          text-shadow: 0 0 12px var(--accent-glow);
        }
        [data-theme="light"] a:not(.archive-list a):not(.pager a):not(.site-title a):hover {
          color: #0550ae;
          text-shadow: 0 0 8px rgba(9, 105, 218, 0.25);
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
) -> str:
    """Construit un document HTML complet, autonome et indexable par les moteurs."""
    nav = " · ".join(
        f'<a href="{escape(resolve(target), quote=True)}">{escape(label)}</a>'
        for label, target in NAV_LINKS
    )
    home = resolve("")
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
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎯</text></svg>">
  <style>{_load_style_tokens()}{PAGE_CSS}{_load_puzzle_css()}</style>
{json_ld}
</head>
<body>
  <div class="page">
    <header class="site-header">
      <span class="site-title"><a href="{escape(home, quote=True)}">🎯 Cémantix Solver</a></span>
      <span class="site-subtitle">Archives quotidiennes &amp; analyse sémantique</span>
    </header>
    <nav class="breadcrumbs" aria-label="Fil d'Ariane">{breadcrumbs}</nav>
    <main>
{body}
    </main>
    <nav class="pager" aria-label="Navigation du site">{nav}</nav>
    <footer class="site-footer">
      <p>Cémantix Solver — solveur sémantique RAG (frWac Word2Vec + ChromaDB), conçu par
      <a href="https://cyril-randon.fr" rel="noopener noreferrer">Cyril RANDON</a>.
      Jeu original : <a href="https://cemantix.certitudes.org" rel="noopener noreferrer">cemantix.certitudes.org</a>.</p>
    </footer>
  </div>
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
