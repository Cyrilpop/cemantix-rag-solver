"""
Cémantix Solver — Générateur de Pages SEO (Archives & Sitemap)
==============================================================
Transforme l'historique des résolutions en **contenu indexable par les moteurs
de recherche**, sans dépendre de l'exécution JavaScript côté navigateur.

Trois livrables produits à chaque export (`--export-web`, démon de minuit) :
- `volumes/web/puzzles/index.html`           : index paginé de toutes les archives ;
- `volumes/web/puzzles/AAAA-MM-JJ/index.html`: page dédiée par puzzle, titrée
  « Solution Cémantix du lundi 26 octobre 2026 » (longue traîne « solution cemantix du
  <date> »), solution placée derrière un `<details>` ;
- `volumes/web/sitemap.xml`                  : `lastmod` réel + URLs des archives.

Les pages sont auto-suffisantes : les tokens de style sont extraits de
`css/variables.css` puis injectés dans une balise `<style>` unique, ce qui garantit
un rendu correct même sans JavaScript et sans requête CSS supplémentaire.
"""
import json
import os
import re
import secrets
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

from ..config import BASE_DIR, log

WEB_ROOT = BASE_DIR / "volumes" / "web"
SITE_ORIGIN = "https://cemantix.cyril-randon.fr"
VARIABLES_CSS_FILE = WEB_ROOT / "css" / "variables.css"

ARCHIVES_DIRNAME = "puzzles"
ARCHIVES_PAGE_SIZE = 60
ARCHIVES_MAX_PAGES = 500
SITEMAP_MAX_URLS = 45000
# Mot-clé visé par les pages d'archive : « Solution Cémantix du lundi 26 octobre 2026 ».
# La date y figure en français long (jour de semaine compris) : c'est la forme tapée
# par un chercheur, alors que l'URL et le <lastmod> du sitemap restent au format ISO
# `AAAA-MM-JJ` exigé par le protocole sitemaps.org.
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
    ("Archives", "puzzles/"),
    ("Jouer Solo", "play/"),
    ("Mode Battle", "battle/"),
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
    # resolve("") renvoie le préfixe racine ("../../") : il doit rester tel quel.
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



# --------------------------------------------------------------------------- #
# Page d'archive quotidienne
# --------------------------------------------------------------------------- #
def build_archive_page(entry: dict, older: Optional[dict], newer: Optional[dict]) -> str:
    """Génère la page HTML indexable d'un puzzle résolu (`/puzzles/AAAA-MM-JJ/`)."""
    date_str = str(entry.get("date"))
    date_fr = format_date_fr(date_str)
    puzzle = entry.get("puzzle")
    word = str(entry.get("word") or "").strip()
    win = entry.get("win") is True
    tries = entry.get("tries")
    duration = format_duration_fr(entry.get("duration_seconds"))
    guesses = [g for g in (entry.get("top_guesses") or []) if str(g.get("word", "")) != "••••••••"]
    source_label = "Hybride RAG + LLM" if entry.get("source") == "llm" else "100 % RAG pur"

    puzzle_label = f"Puzzle #{puzzle}" if puzzle else "Puzzle du jour"
    title = archive_title(date_str)
    description = (
        f"{title} : le mot secret et les {min(len(guesses), 10)} mots les plus proches, "
        f"trouvés en {tries or '--'} coups par le solveur {source_label} ({puzzle_label})."
    )
    canonical = archive_url(date_str)

    breadcrumbs = (
        f'<a href="{escape(_rel(""), quote=True)}">Accueil</a> › '
        f'<a href="{escape(_rel("puzzles/"), quote=True)}">Archives</a> › '
        f"<span>{escape(date_fr)}</span>"
    )

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": f"{canonical}#article",
                "headline": title,
                "description": description,
                "inLanguage": "fr-FR",
                "datePublished": f"{date_str}T00:00:01+01:00",
                "dateModified": entry.get("timestamp") or f"{date_str}T00:00:01+01:00",
                "image": f"{SITE_ORIGIN}/og-image.jpg",
                "author": {
                    "@type": "Person",
                    "name": "Cyril Randon",
                    "url": "https://cyril-randon.fr",
                    "sameAs": [
                        "https://github.com/Cyrilpop/cemantix-rag-solver",
                        "https://www.linkedin.com/in/cyril-randon"
                    ]
                },
                "publisher": {
                    "@type": "Person",
                    "name": "Cyril Randon",
                    "url": "https://cyril-randon.fr",
                    "sameAs": [
                        "https://github.com/Cyrilpop/cemantix-rag-solver",
                        "https://www.linkedin.com/in/cyril-randon"
                    ]
                },
                "isPartOf": {"@type": "WebSite", "@id": f"{SITE_ORIGIN}/#website"},
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical}#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE_ORIGIN}/"},
                    {"@type": "ListItem", "position": 2, "name": "Archives", "item": f"{SITE_ORIGIN}/puzzles/"},
                    {"@type": "ListItem", "position": 3, "name": date_fr},
                ],
            },
        ],
    })

    meta_items = [
        f"<li>{escape(puzzle_label)}</li>",
        f"<li>Publié le <strong>{escape(date_fr)}</strong></li>",
        f"<li>Résolu en <strong>{escape(str(tries or '--'))} coups</strong></li>",
        f"<li>Durée de calcul&nbsp;: <strong>{escape(duration)}</strong></li>",
        f"<li>Méthode&nbsp;: <strong>{escape(source_label)}</strong></li>",
    ]
    win_badge = (
        '<span class="badge badge-win">✓ Trouvé</span>'
        if win
        else '<span class="badge">⏳ Non résolu</span>'
    )


    clues_html = ""
    if guesses:
        clues_html = f"""      <section class="card">
        <h2>🌡️ Les {min(len(guesses), 10)} mots les plus proches du mot secret</h2>
        <p>Le thermomètre sémantique officiel de Cémantix : plus le score en pour mille
        (‰) approche 1000, plus le mot est proche du mot secret. Le mot cible vaut
        exactement 1000 ‰.</p>
        <table>
          <caption>Indices de proximité sémantique mesurés par le solveur RAG</caption>
          <thead>
            <tr><th scope="col">#</th><th scope="col">Mot</th><th scope="col">Score</th><th scope="col">Similarité</th></tr>
          </thead>
          <tbody>
{_clue_rows(guesses)}
          </tbody>
        </table>
      </section>
"""

    solution_html = ""
    if word:
        solution_html = f"""      <details class="reveal">
        <summary>👁️ Afficher la solution du Cémantix du {escape(date_fr)}</summary>
        <p class="reveal-word">{escape(word.upper())}</p>
        <p>Le solveur a atteint ce mot en {escape(str(tries or '--'))} coups
        ({escape(duration)}) grâce à la régression Ridge sur l'espace vectoriel frWac.</p>
      </details>
"""

    older_link = newer_link = ""
    if older:
        older_link = (
            f'<a href="{escape(_archive_href(older), quote=True)}" rel="prev">'
            f"← {escape(format_date_fr(older.get('date')))}</a>"
        )
    if newer:
        newer_link = (
            f'<a href="{escape(_archive_href(newer), quote=True)}" rel="next">'
            f"{escape(format_date_fr(newer.get('date')))} →</a>"
        )
    pagination = ""
    if older_link or newer_link:
        pagination = f"""      <nav class="pager" aria-label="Navigation entre les archives">
        {older_link}
        <a href="{escape(_rel('puzzles/'), quote=True)}">Toutes les archives</a>
        {newer_link}
      </nav>
"""


    body = f"""      <h1>{escape(title)}</h1>
      <p>{win_badge}</p>
      <div class="card">
        <ul class="meta-list">
{chr(10).join('          ' + item for item in meta_items)}
        </ul>
      </div>
{clues_html}{solution_html}      <section class="card">
        <h2>ℹ️ À propos de cette archive</h2>
        <p>Cette page est générée automatiquement chaque nuit à minuit (heure de Paris)
        par le solveur Cémantix. Elle conserve la trace des indices explorés par
        l'algorithme pour {escape(puzzle_label)}. Pour jouer immédiatement, direction le
        <a href="{escape(_rel('play/'), quote=True)}">mode solo illimité</a> ou le
        <a href="{escape(_rel('battle/'), quote=True)}">mode Battle contre l'IA</a>.</p>
      </section>
{pagination}"""

    # Protection anti "thin content" (SEO-01b) : si aucun indice / trajectoire n'est disponible, noindex
    robots_meta = "index, follow"
    if not guesses and not win:
        robots_meta = "noindex, follow"

    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        body=body,
        breadcrumbs=breadcrumbs,
        resolve=_rel,
        robots_meta=robots_meta,
    )


# --------------------------------------------------------------------------- #
# Index paginé des archives
# --------------------------------------------------------------------------- #
def build_archives_index_page(entries: list, page: int, total_pages: int) -> str:
    """Génère une page d'index des archives (`/puzzles/` ou `/puzzles/page/N/`)."""
    start = (page - 1) * ARCHIVES_PAGE_SIZE
    chunk = entries[start:start + ARCHIVES_PAGE_SIZE]
    newest = entries[0] if entries else None
    newest_fr = format_date_fr(newest.get("date")) if newest else ""

    if page == 1:
        title = "Solution Cémantix : archives de tous les puzzles résolus par l'IA"
    else:
        title = f"Solution Cémantix — archives des puzzles, page {page}"
    description = (
        f"Toutes les solutions Cémantix par date ({len(entries)} puzzles résolus) : "
        f"indices thermiques, coups et mot secret dépliable. "
        f"Dernière archive : {newest_fr}."
    )
    canonical = (
        f"{SITE_ORIGIN}/puzzles/" if page == 1 else f"{SITE_ORIGIN}/puzzles/page/{page}/"
    )
    breadcrumbs = f'<a href="{escape(_rel_index(""), quote=True)}">Accueil</a> › <span>Archives</span>'

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": f"{canonical}#collection",
        "name": "Solution Cémantix — archives des puzzles résolus",
        "description": description,
        "inLanguage": "fr-FR",
        "isPartOf": {"@type": "WebSite", "name": "Cémantix Solver", "url": f"{SITE_ORIGIN}/"},
        "url": canonical,
    })

    items = []
    for entry in chunk:
        date_str = str(entry.get("date"))
        tries = entry.get("tries")
        suffix = f"{tries} coups" if tries else "non résolu"
        items.append(
            f'          <li><a href="{escape(_rel_index(f"puzzles/{date_str}/"), quote=True)}">'
            f"<span>{escape(archive_title(date_str))}</span>"
            f"<span>{escape(suffix)}</span></a></li>"
        )
    listing = "\n".join(items) or (
        '          <li><span>Aucun puzzle résolu pour le moment.</span></li>'
    )

    links = []
    for candidate in range(1, total_pages + 1):
        if candidate == page:
            links.append(f'<span class="current" aria-current="page">{candidate}</span>')
        elif candidate == 1 or candidate == total_pages or abs(candidate - page) <= 2:
            href = "../" if candidate == 1 else f"../page/{candidate}/"
            rel = ' rel="start"' if candidate == 1 else (
                ' rel="prev"' if candidate == page - 1 else (
                    ' rel="next"' if candidate == page + 1 else ""
                )
            )
            links.append(f'<a href="{escape(href, quote=True)}"{rel}>{candidate}</a>')
    pager = "\n        ".join(links)

    body = f"""      <h1>Solution Cémantix : archives des puzzles résolus</h1>
      <p>Chaque jour à minuit (heure de Paris), le solveur résout le mot secret de
      Cémantix et publie une page « {escape(ARCHIVE_TITLE_PREFIX)} … » datée : numéro de
      puzzle, nombre de coups, durée de calcul, top des mots les plus proches et solution
      dépliable.</p>
      <div class="card">
        <h2>{len(entries)} puzzles indexés — page {page} sur {total_pages}</h2>
        <ul class="archive-list">
{listing}
        </ul>
      </div>
      <nav class="pager" aria-label="Pagination des archives">
        {pager}
      </nav>
"""

    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        body=body,
        breadcrumbs=breadcrumbs,
        resolve=_rel_index,
    )


# --------------------------------------------------------------------------- #
# Sitemap & publication
# --------------------------------------------------------------------------- #
def _sitemap_url(loc: str, lastmod: Optional[str], priority: str, changefreq: str = "daily") -> str:
    """Bloc `<url>` d'un sitemap, `lastmod` omis si inconnu."""
    mod = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    return (
        "  <url>\n"
        f"    <loc>{escape(loc, quote=True)}</loc>\n"
        f"{mod}"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>"
    )


def build_sitemap(entries: list, generated_at: datetime) -> str:
    """Construit `sitemap.xml` avec le `lastmod` réel de chaque page."""
    today = generated_at.strftime("%Y-%m-%d")
    newest = entries[0] if entries else None
    newest_date = str(newest.get("date")) if newest else today

    urls = [
        _sitemap_url(f"{SITE_ORIGIN}/", newest_date, "1.0"),
        _sitemap_url(f"{SITE_ORIGIN}/puzzles/", newest_date, "0.9"),
        _sitemap_url(f"{SITE_ORIGIN}/play/", today, "0.9", "weekly"),
        _sitemap_url(f"{SITE_ORIGIN}/battle/", today, "0.9", "weekly"),
        _sitemap_url(f"{SITE_ORIGIN}/multi/", today, "0.9", "weekly"),
    ]

    total_pages = max(1, -(-len(entries) // ARCHIVES_PAGE_SIZE))
    for page in range(2, min(total_pages, ARCHIVES_MAX_PAGES) + 1):
        urls.append(_sitemap_url(f"{SITE_ORIGIN}/puzzles/page/{page}/", newest_date, "0.6"))

    for entry in entries[:SITEMAP_MAX_URLS]:
        date_str = str(entry.get("date"))
        if not parse_puzzle_date(date_str):
            continue
        urls.append(_sitemap_url(archive_url(date_str), date_str, "0.8", "monthly"))

    body = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _write_file(path: Path, content: str) -> None:
    """Écrit un fichier texte en UTF-8 de façon atomique (compatible multi-conteneurs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        try:
            os.chmod(tmp_path, 0o644)
        except OSError:
            pass
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------- #
# Pré-rendu du tableau de bord (contenu indexable sans JavaScript)
# --------------------------------------------------------------------------- #
_PRERENDER_START = "<!-- SEO-PRERENDER:DEBUT"
_PRERENDER_END = "<!-- SEO-PRERENDER:FIN -->"
_PRERENDER_ANCHOR_ID = 'id="resume-du-jour-title"'
_DATA_SEO_RE = re.compile(r'data-seo="([^"]+)"')


def _daily_summary(entry: dict) -> str:
    """Paragraphe de résumé du jour, sans révéler le mot secret."""
    date_fr = format_date_fr(entry.get("date"))
    puzzle = entry.get("puzzle")
    tries = entry.get("tries")
    duration = format_duration_fr(entry.get("duration_seconds"))
    guesses = [g for g in (entry.get("top_guesses") or []) if str(g.get("word", "")) != "••••••••"]
    source_label = "hybride RAG + LLM" if entry.get("source") == "llm" else "100 % RAG pur"
    puzzle_label = f"le puzzle #{puzzle}" if puzzle else "le puzzle du jour"

    clue_names = ", ".join(
        str(g.get("word", "")).capitalize() for g in guesses[:5] if g.get("word")
    )
    clue_part = (
        f" Les mots les plus proches observés étaient {clue_names}." if clue_names else ""
    )
    status = "résolu" if entry.get("win") is True else "non résolu"
    return (
        f"<strong>Cémantix du {escape(date_fr)}</strong> : {puzzle_label} a été "
        f"{status} en <strong>{escape(str(tries or '--'))} coups</strong> "
        f"({escape(duration)}) par le solveur {escape(source_label)}."
        f"{clue_part} La solution reste masquée tant que vous ne la demandez pas ; "
        f"elle est consultable sur la "
        f"<a href=\"puzzles/{escape(str(entry.get('date')), quote=True)}/\">"
        f"page d'archive du jour</a>."
    )


def prerender_dashboard(entry: Optional[dict], web_root: Path = None) -> bool:
    """Injecte le résumé du jour dans `index.html` (contenu lisible sans JS).

    Le remplacement est délimité par les commentaires `SEO-PRERENDER` et ciblé par
    l'attribut `data-seo`, ce qui rend l'opération idempotente : relancer la
    génération ne duplique jamais le contenu.
    """
    root = web_root if web_root is not None else WEB_ROOT
    index_file = root / "index.html"
    try:
        source = index_file.read_text(encoding="utf-8")
    except OSError as exc:
        log(f"⚠️  Pré-rendu SEO ignoré ({exc})")
        return False

    if _PRERENDER_START not in source or _PRERENDER_END not in source:
        log("⚠️  Pré-rendu SEO ignoré : balises SEO-PRERENDER absentes de index.html")
        return False

    if entry:
        date_fr = format_date_fr(entry.get("date"))
        replacements = {
            "resume-title": f"Cémantix du {date_fr} : résumé de la résolution",
            "resume-subtitle": "Indices, thermomètre et performance du solveur IA du jour",
            "resume-body": _daily_summary(entry),
            "resume-link": (
                "Consultez l'<a href=\"puzzles/\">archive complète des puzzles</a> "
                "pour retrouver les indices jour par jour."
            ),
        }
    else:
        replacements = {
            "resume-title": "Cémantix du jour : résumé de la résolution",
            "resume-subtitle": "Indices, thermomètre et performance du solveur IA",
            "resume-body": (
                "Le résumé du puzzle du jour sera publié automatiquement après la "
                "résolution de minuit."
            ),
            "resume-link": (
                "Consultez l'<a href=\"puzzles/\">archive complète des puzzles</a> "
                "pour retrouver les indices jour par jour."
            ),
        }

    # Le bloc utile va du titre du résumé au marqueur de fermeture : les éléments
    # ciblés par data-seo sont cherchés uniquement dans cette zone.
    start = source.index(_PRERENDER_START)
    end = source.index(_PRERENDER_END, start)
    anchor = source.rfind(_PRERENDER_ANCHOR_ID, 0, start)
    block_start = source.rfind("<", 0, anchor) if anchor != -1 else start
    block = source[block_start:end]

    # Remplacement ciblé par balise/attribut data-seo avec regex robuste.
    # L'élément complet <tag data-seo="key"...>...</tag> est remplacé proprement
    # afin de ne pas être perturbé par les balises internes (ex: <a>, <strong>).
    def _replace_seo_tag(text: str, key: str, new_content: str) -> str:
        # Correspondance d'une balise ayant data-seo="key" et de son contenu complet
        pattern = re.compile(
            rf'(<([a-zA-Z0-9]+)\b[^>]*\bdata-seo="{re.escape(key)}"[^>]*>).*?(</\2>)',
            flags=re.DOTALL,
        )
        return pattern.sub(rf"\g<1>{new_content}\g<3>", text, count=1)

    for key, val in replacements.items():
        source = _replace_seo_tag(source, key, val)

    # Badges "Puzzle #N" et date du jour, lus tels quels par les crawlers.
    if entry:
        puzzle = entry.get("puzzle")
        if puzzle:
            source = re.sub(
                r'(<span id="puzzle-badge"[^>]*>).*?(</span>)',
                rf"\g<1>Puzzle #{puzzle}\g<2>",
                source,
                count=1,
                flags=re.DOTALL,
            )
        source = re.sub(
            r'(<span id="puzzle-date"[^>]*>).*?(</span>)',
            rf"\g<1>{escape(format_date_fr(entry.get('date')))}\g<2>",
            source,
            count=1,
            flags=re.DOTALL,
        )

    try:
        _write_file(index_file, source)
    except OSError as exc:
        log(f"⚠️  Pré-rendu SEO non réécrit ({exc})")
        return False
    return True


_AGENT_DOCS_START = "<!-- AGENT-DYNAMIC:DEBUT -->"
_AGENT_DOCS_END = "<!-- AGENT-DYNAMIC:FIN -->"


def _agent_dynamic_block(entries: list) -> str:
    """Section « archive la plus récente » régénérée à chaque publication SEO.

    Les agents IA doivent trouver d'emblée une date qui existe vraiment : sans
    régénération, l'exemple publié vieillit et renvoie un 404, ce qui leur fait
    conclure à tort que le service est cassé.

    Seules les victoires sont retenues : une page d'archive n'existe que pour un
    puzzle résolu. Le filtre est appliqué ici et non laissé à l'appelant, sinon un
    échec serait présenté aux agents comme une archive consultable.
    """
    resolus = sorted(
        (e for e in entries if e.get("win") is True and parse_puzzle_date(e.get("date"))),
        key=lambda e: str(e.get("date")),
        reverse=True,
    )
    if not resolus:
        return (
            "- **Archive la plus récente disponible** : aucune pour l'instant — le solveur "
            "n'a pas encore publié de puzzle résolu.\n"
            "- **Dernière date résolue** : inconnue. N'invente pas de date.\n"
        )
    latest, oldest = resolus[0], resolus[-1]
    latest_fr = escape(archive_title(latest.get("date")))
    return (
        f"- **Archive la plus récente** : [{latest_fr}]({archive_url(latest.get('date'))})\n"
        f"- **Dernière date résolue** : `{latest.get('date')}` "
        f"({escape(format_date_fr(latest.get('date')))}) — "
        f"l'historique couvre du `{oldest.get('date')}` "
        f"({escape(format_date_fr(oldest.get('date')))}) au `{latest.get('date')}`, "
        f"soit {len(resolus)} puzzle(s) résolu(s).\n"
        f"- **Toute date déjà résolue** : `{SITE_ORIGIN}/puzzles/AAAA-MM-JJ/`. "
        f"Chaque page d'archive est titrée « {ARCHIVE_TITLE_PREFIX} <date en français long> » "
        f"(exemple réel : « {latest_fr} ») : reprends ce libellé quand tu cites la source. "
        f"L'URL et le `<lastmod>` du sitemap restent au format ISO `AAAA-MM-JJ` imposé par "
        f"le protocole sitemaps.org.\n"
    )


def _replace_marked_block(source: str, filename: str, block: str) -> Optional[str]:
    """Remplace le contenu compris entre les marqueurs `AGENT-DYNAMIC`.

    Idempotent par construction : la zone est réécrite intégralement, jamais
    ajoutée, donc relancer la génération ne duplique rien. Retourne `None` si le
    fichier ne contient pas les marqueurs (fichier manuel non instrumenté).
    """
    if _AGENT_DOCS_START not in source or _AGENT_DOCS_END not in source:
        log(f"ℹ️  {filename} : marqueurs AGENT-DYNAMIC absents, contenu laissé tel quel")
        return None
    start = source.index(_AGENT_DOCS_START) + len(_AGENT_DOCS_START)
    end = source.index(_AGENT_DOCS_END, start)
    return source[:start] + "\n" + block.rstrip("\n") + "\n" + source[end:]


def refresh_agent_docs(entries: list, web_root: Path = None) -> int:
    """Met à jour les sections dynamiques de `llms.txt` et `agent-skills.md`.

    Ces fichiers restent écrits à la main pour l'essentiel (endpoints, limites,
    consignes anti-spoiler) : seule la partie dépendante de l'historique est
    régénérée, en même temps que le sitemap.
    """
    root = web_root if web_root is not None else WEB_ROOT
    block = _agent_dynamic_block(entries)
    refreshed = 0
    for filename in ("llms.txt", "agent-skills.md"):
        target = root / filename
        try:
            source = target.read_text(encoding="utf-8")
        except OSError as exc:
            log(f"⚠️  {filename} ignoré ({exc})")
            continue
        updated = _replace_marked_block(source, filename, block)
        if updated is None:
            continue
        try:
            _write_file(target, updated)
        except OSError as exc:
            log(f"⚠️  {filename} non réécrit ({exc})")
            continue
        refreshed += 1
    return refreshed


def build_ard_manifest(origin: str = SITE_ORIGIN) -> str:
    """Construit le manifeste ARD conforme à Lighthouse (`ai-catalog.json` & `ard.json`)."""
    base = origin.rstrip("/")
    domain = urlparse(base).hostname or "cemantix.cyril-randon.fr"
    payload = {
        "specVersion": "1.0",
        "host": {
            "displayName": "Cémantix Solver",
            "identifier": f"did:web:{domain}",
            "documentationUrl": f"{base}/llms.txt",
        },
        "entries": [
            {
                "identifier": f"urn:air:{domain}:agent:cemantix-solver",
                "displayName": "Cémantix Solver — carte d'agent",
                "type": "application/agent-card+json",
                "url": f"{base}/.well-known/agent-card.json",
                "description": (
                    "Carte d'agent du solveur sémantique Cémantix : compétences exposées, "
                    "modes d'entrée et de sortie, endpoints publics. Le mot secret est "
                    "masqué par conception (protection anti-spoiler) ; la solution d'une "
                    "date donnée se consulte sur la page d'archive correspondante."
                ),
                "representativeQueries": [
                    "Quels sont les indices sémantiques du Cémantix du jour ?",
                    "Combien de coups ont été nécessaires pour trouver le Cémantix du jour ?",
                    "Similarité sémantique et solveur Cémantix",
                ],
            },
            {
                "identifier": f"urn:air:{domain}:skills:cemantix-indices",
                "displayName": "Compétences Cémantix Solver (mode d'emploi agent)",
                "type": 'text/markdown; profile="urn:air:agent-skills"',
                "url": f"{base}/agent-skills.md",
                "description": (
                    "Protocole d'usage pour un agent autonome : les trois requêtes "
                    "autorisées (indices du jour, archive datée, état du service), la "
                    "conduite à tenir en cas de 404 et l'interdiction de révéler ou de "
                    "reconstituer le mot secret."
                ),
                "representativeQueries": [
                    "Comment interroger le solveur Cémantix ?",
                    "Solution et indices du Cémantix du 26 octobre 2026",
                    "Quelle est la solution du Cémantix du lundi 26 octobre 2026 ?",
                ],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_agent_card(origin: str = SITE_ORIGIN) -> str:
    """Construit la carte d'agent A2A `.well-known/agent-card.json`."""
    base = origin.rstrip("/")
    payload = {
        "name": "Cémantix Solver",
        "description": (
            "Résolution sémantique du jeu Cémantix : indices thermiques quotidiens, "
            "archives par date et solveur vectoriel Word2Vec. Les réponses publiques "
            "sont sans spoiler : le mot secret n'est jamais exposé avant sa révélation "
            "par le visiteur."
        ),
        "url": f"{base}/api/daily",
        "provider": {
            "organization": "Cyril RANDON",
            "url": "https://cyril-randon.fr",
        },
        "version": "1.0.0",
        "documentation": f"{base}/llms.txt",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "authentication": {
            "schemes": ["none"],
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "daily-indices",
                "name": "Indices sémantiques du jour",
                "description": (
                    "Renvoie les données agrégées du puzzle du jour : date, numéro, "
                    "nombre de coups, durée et dix mots les plus proches avec leur "
                    "score. Le mot secret est masqué."
                ),
                "tags": ["cemantix", "semantique", "indices"],
                "examples": [
                    "Quels sont les indices sémantiques du Cémantix du jour ?",
                    "Combien de coups ont été nécessaires pour trouver le Cémantix du jour ?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
            {
                "id": "dated-archive",
                "name": "Archive d'une date précise",
                "description": (
                    "Interroge la page statique /puzzles/AAAA-MM-JJ/ d'un puzzle résolu. "
                    "Chaque page est titrée « Solution Cémantix du lundi 26 octobre 2026 » "
                    "(date en français long), l'URL restant en ISO AAAA-MM-JJ. "
                    "Un statut 404 signifie que la date n'a pas encore été résolue."
                ),
                "tags": ["cemantix", "archive", "date", "solution"],
                "examples": [
                    "Quelle est la solution du Cémantix du 26 octobre 2026 ?",
                    "Donne les indices du Cémantix du 26 octobre 2026",
                    "Quand le puzzle du 23 octobre 2026 a-t-il été résolu ?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/html"],
            },
            {
                "id": "service-health",
                "name": "État du service",
                "description": (
                    "Vérifie la disponibilité du service et le nombre de sessions de "
                    "jeu actives, sans aucune donnée de puzzle."
                ),
                "tags": ["sante", "disponibilite"],
                "examples": ["Le solveur Cémantix est-il disponible ?"],
                "inputModes": [],
                "outputModes": ["application/json"],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def publish_ard_manifests(web_root: Path = None) -> int:
    """Génère atomiquement `.well-known/{ai-catalog,ard,agent-card}.json`.

    Recrée systématiquement les manifestes ARD et A2A au démarrage des conteneurs
    et lors de chaque publication SEO afin d'éliminer tout fichier absent, tronqué
    ou resté sur un schéma obsolète.
    """
    root = web_root if web_root is not None else WEB_ROOT
    well_known = root / ".well-known"
    ard_content = build_ard_manifest(SITE_ORIGIN)
    card_content = build_agent_card(SITE_ORIGIN)

    targets = (
        (well_known / "ai-catalog.json", ard_content),
        (well_known / "ard.json", ard_content),
        (well_known / "agent-card.json", card_content),
    )
    written_count = 0
    for path, payload in targets:
        try:
            _write_file(path, payload)
            written_count += 1
        except OSError as exc:
            log(f"⚠️  [ARD] Impossible d'écrire {path.name} ({exc})")
    return written_count


def publish_seo_pages(history: list, generated_at: datetime, web_root: Path = None) -> dict:
    """Génère les pages d'archives, l'index paginé, le sitemap et les manifestes ARD.

    Seuls les puzzles gagnés sont publiés : une page sans solution n'apporte aucune
    réponse au chercheur et ferait doublon avec le tableau de bord.
    """
    root = web_root if web_root is not None else WEB_ROOT
    archives_root = root / ARCHIVES_DIRNAME

    entries = sorted(
        (
            e for e in history
            if e.get("win") is True and parse_puzzle_date(e.get("date"))
        ),
        key=lambda e: str(e.get("date")),
        reverse=True,
    )

    written = {"archives": 0, "index_pages": 0, "sitemap": False, "ard_manifests": 0}

    # Génération prioritaire et atomique de sitemap.xml et des manifestes ARD (.well-known/)
    _write_file(root / "sitemap.xml", build_sitemap(entries, generated_at))
    written["sitemap"] = True
    written["ard_manifests"] = publish_ard_manifests(web_root=root)

    if not entries:
        log("ℹ️  SEO : aucun puzzle résolu, génération du sitemap et des manifestes ARD.")
    else:
        for idx, entry in enumerate(entries):
            newer = entries[idx - 1] if idx > 0 else None
            older = entries[idx + 1] if idx + 1 < len(entries) else None
            html = build_archive_page(entry, older, newer)
            _write_file(archives_root / str(entry.get("date")) / "index.html", html)
            written["archives"] += 1

        total_pages = min(
            max(1, -(-len(entries) // ARCHIVES_PAGE_SIZE)), ARCHIVES_MAX_PAGES
        )
        for page in range(1, total_pages + 1):
            html = build_archives_index_page(entries, page, total_pages)
            target = archives_root / "index.html" if page == 1 else archives_root / "page" / str(page) / "index.html"
            _write_file(target, html)
            written["index_pages"] += 1

    written["prerender"] = prerender_dashboard(entries[0] if entries else None, web_root=root)
    written["agent_docs"] = refresh_agent_docs(entries, web_root=root)
    log(
        f"🔎  SEO publié : {written['archives']} archive(s), "
        f"{written['index_pages']} page(s) d'index, sitemap.xml régénéré, "
        f"{written['ard_manifests']} manifeste(s) ARD"
        + (", accueil pré-rendu" if written["prerender"] else "")
        + (f", {written['agent_docs']} doc(s) agent rafraîchie(s)" if written["agent_docs"] else "")
    )
    return written


def ensure_seo_published(web_root: Path = None) -> Optional[dict]:
    """Garantit la présence et la conformité de `sitemap.xml`, `.well-known/` et `/puzzles/` au démarrage.

    Invoqué automatiquement au lancement des conteneurs (`cemantix_web` et
    `cemantix_worker`) afin de recréer immédiatement `volumes/web/sitemap.xml`,
    `volumes/web/.well-known/{ai-catalog,ard,agent-card}.json`, `/puzzles/` et le
    pré-rendu SEO après un `git pull`, un déploiement vierge ou un redémarrage.
    """
    from .daemon import PARIS_TZ, load_history
    try:
        try:
            history = load_history()
        except Exception as db_exc:
            log(f"⚠️  [SEO] Historique indisponible au démarrage ({db_exc}), repli sur historique vide.")
            history = []
        return publish_seo_pages(
            history=history,
            generated_at=datetime.now(PARIS_TZ),
            web_root=web_root,
        )
    except Exception as exc:
        log(f"⚠️  [SEO] Génération automatique SEO/ARD au démarrage en échec : {exc}")
        return None

