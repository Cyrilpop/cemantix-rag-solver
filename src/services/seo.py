"""
Cémantix Solver — Générateur de Pages SEO (Archives & Sitemap)
==============================================================
Transforme l'historique des résolutions en **contenu indexable par les moteurs
de recherche**, sans dépendre de l'exécution JavaScript côté navigateur.

Trois livrables produits à chaque export (`--export-web`, démon de minuit) :
- `volumes/web/puzzles/index.html`           : index paginé de toutes les archives ;
- `volumes/web/puzzles/AAAA-MM-JJ/index.html`: page dédiée par puzzle (longue traîne
  « cemantix du 26 octobre 2026 »), solution placée derrière un `<details>` ;
- `volumes/web/sitemap.xml`                  : `lastmod` réel + URLs des archives.

Les pages sont auto-suffisantes : les tokens de style sont extraits de
`css/variables.css` puis injectés dans une balise `<style>` unique, ce qui garantit
un rendu correct même sans JavaScript et sans requête CSS supplémentaire.
"""
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from ..config import BASE_DIR, log

WEB_ROOT = BASE_DIR / "volumes" / "web"
SITE_ORIGIN = "https://cemantix.cyril-randon.fr"
VARIABLES_CSS_FILE = WEB_ROOT / "css" / "variables.css"

ARCHIVES_DIRNAME = "puzzles"
ARCHIVES_PAGE_SIZE = 60
ARCHIVES_MAX_PAGES = 500
SITEMAP_MAX_URLS = 45000

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
          border-top: 1px solid var(--border-color); font-size: .85rem; color: var(--text-dim);
        }
        .site-footer a { color: var(--accent); text-decoration: none; }
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
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
  <link rel="canonical" href="{escape(canonical, quote=True)}">
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
  <style>{_load_style_tokens()}{PAGE_CSS}</style>
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
    title = f"Cémantix du {date_fr} : indices, solution et trajectoire du solveur IA"
    description = (
        f"Indices du Cémantix du {date_fr} ({puzzle_label}) : les {min(len(guesses), 10)} mots "
        f"les plus proches avec leur score sémantique, résolu en {tries or '--'} coups "
        f"par le solveur {source_label}."
    )
    canonical = archive_url(date_str)

    breadcrumbs = (
        f'<a href="{escape(_rel(""), quote=True)}">Accueil</a> › '
        f'<a href="{escape(_rel("puzzles/"), quote=True)}">Archives</a> › '
        f"<span>{escape(date_str)}</span>"
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
                "author": {"@type": "Person", "name": "Cyril Randon", "url": "https://cyril-randon.fr"},
                "publisher": {"@type": "Person", "name": "Cyril Randon", "url": "https://cyril-randon.fr"},
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical}#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE_ORIGIN}/"},
                    {"@type": "ListItem", "position": 2, "name": "Archives", "item": f"{SITE_ORIGIN}/puzzles/"},
                    {"@type": "ListItem", "position": 3, "name": date_str},
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


    body = f"""      <h1>Cémantix du {escape(date_fr)}</h1>
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

    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        body=body,
        breadcrumbs=breadcrumbs,
        resolve=_rel,
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
        title = "Archives des puzzles Cémantix : tous les mots du jour résolus par l'IA"
    else:
        title = f"Archives des puzzles Cémantix — page {page}"
    description = (
        f"Archive complète des puzzles Cémantix résolus ({len(entries)} jours indexés). "
        f"Dernier puzzle disponible : {newest_fr}. Indices, scores et solution par date."
    )
    canonical = (
        f"{SITE_ORIGIN}/puzzles/" if page == 1 else f"{SITE_ORIGIN}/puzzles/page/{page}/"
    )
    breadcrumbs = f'<a href="{escape(_rel_index(""), quote=True)}">Accueil</a> › <span>Archives</span>'

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": f"{canonical}#collection",
        "name": "Archives des puzzles Cémantix",
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
            f"<span>{escape(format_date_fr(date_str))}</span>"
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

    body = f"""      <h1>Archives des puzzles Cémantix</h1>
      <p>Chaque jour à minuit (heure de Paris), le solveur résout le mot secret de
      Cémantix et publie ici la page correspondante : numéro de puzzle, nombre de coups,
      durée de calcul, top des mots les plus proches et solution dépliable.</p>
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
    """Écrit un fichier texte en UTF-8 (crée les répertoires parents)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


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

    # Remplacement de l'intérieur vers l'extérieur pour conserver les index valides.
    targets = []
    for match in _DATA_SEO_RE.finditer(block):
        key = match.group(1)
        if key not in replacements:
            continue
        absolute = block_start + match.end()
        try:
            tag_close = source.index(">", absolute) + 1
            content_end = source.index("</", tag_close)
        except ValueError:
            continue
        targets.append((tag_close, content_end, replacements[key]))

    for tag_close, content_end, payload in sorted(targets, reverse=True):
        source = source[:tag_close] + payload + source[content_end:]

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

    index_file.write_text(source, encoding="utf-8", newline="\n")
    return True


def publish_seo_pages(history: list, generated_at: datetime, web_root: Path = None) -> dict:
    """Génère les pages d'archives, l'index paginé et le sitemap dans le webroot.

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

    written = {"archives": 0, "index_pages": 0, "sitemap": False}
    if not entries:
        log("ℹ️  SEO : aucun puzzle résolu, génération du sitemap seul.")
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

    _write_file(root / "sitemap.xml", build_sitemap(entries, generated_at))
    written["sitemap"] = True

    written["prerender"] = prerender_dashboard(entries[0] if entries else None, web_root=root)
    log(
        f"🔎  SEO publié : {written['archives']} archive(s), "
        f"{written['index_pages']} page(s) d'index, sitemap.xml régénéré"
        + (", accueil pré-rendu" if written["prerender"] else "")
    )
    return written

