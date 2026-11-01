"""
Cémantix Solver — Pages d'Archives SEO (seo_archives)
===================================================
Génère les pages individuelles d'archives pour chaque puzzle quotidien résolu
(`/puzzles/AAAA-MM-JJ/`) et l'index paginé de toutes les archives (`/puzzles/`).
"""
from html import escape
from typing import Optional

from .seo_templates import (
    ARCHIVES_PAGE_SIZE,
    SITE_ORIGIN,
    _archive_href,
    _clue_rows,
    _json_ld_block,
    _rel,
    _rel_index,
    archive_anchor,
    archive_title,
    archive_url,
    format_clue_words_list,
    format_date_fr,
    format_duration_fr,
    render_page,
)


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
    puzzle_ref = f" #{puzzle}" if puzzle else ""
    title = f"{archive_title(date_str, puzzle=puzzle)} : 10 indices, synonymes et solution"
    mots_indices = format_clue_words_list(guesses, limit=10)
    clue_paren = f" ({mots_indices})" if mots_indices else ""
    puzzle_prefix = f"Indices Cémantix #{puzzle}" if puzzle else "Indices Cémantix"
    tries_part = f" en {tries} coups" if tries else ""
    description = (
        f"{puzzle_prefix} du {date_fr} : aide sans spoiler avec les 10 mots les plus proches{clue_paren} "
        f"et synonymes pour trouver le mot secret{tries_part}."
    )
    canonical = archive_url(date_str)

    breadcrumbs = (
        f'<a href="{escape(_rel(""), quote=True)}">Accueil</a>'
        f'<span class="crumb-sep">›</span>'
        f'<a href="{escape(_rel("puzzles/"), quote=True)}">Archives</a>'
        f'<span class="crumb-sep">›</span>'
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
        <summary>👁️ Afficher la solution du Cémantix{puzzle_ref} du {escape(date_fr)}</summary>
        <p class="reveal-word">{escape(word.upper())}</p>
        <p>Le solveur a atteint ce mot en {escape(str(tries or '--'))} coups
        ({escape(duration)}) grâce à la régression Ridge sur l'espace vectoriel frWac.</p>
      </details>
"""

    older_link = newer_link = ""
    if older:
        older_link = (
            f'<a href="{escape(_archive_href(older), quote=True)}" class="btn-nav-date" rel="prev">'
            f"⬅️ {escape(format_date_fr(older.get('date')))}</a>"
        )
    if newer:
        newer_link = (
            f'<a href="{escape(_archive_href(newer), quote=True)}" class="btn-nav-date" rel="next">'
            f"{escape(format_date_fr(newer.get('date')))} ➡️</a>"
        )
    date_nav_html = f"""      <nav class="date-navigation" aria-label="Navigation entre les énigmes">
        {older_link or '<span class="btn-nav-date disabled">Premier puzzle</span>'}
        <a href="{escape(_rel('puzzles/'), quote=True)}" class="btn-nav-date btn-all-archives">📚 Toutes les archives</a>
        {newer_link or '<span class="btn-nav-date disabled">Dernier puzzle</span>'}
      </nav>
"""

    body = f"""      <h1>{escape(title)}</h1>
      <p>{win_badge}</p>
      <div class="card">
        <ul class="meta-list">
{chr(10).join('          ' + item for item in meta_items)}
        </ul>
      </div>
{solution_html}{date_nav_html}{clues_html}      <section class="card">
        <h2>ℹ️ À propos de cette archive</h2>
        <p>Cette page est générée automatiquement chaque nuit à minuit (heure de Paris)
        par le solveur Cémantix. Elle conserve la trace des indices explorés par
        l'algorithme pour {escape(puzzle_label)}. Le puzzle en cours se suit sur le
        <a href="{escape(_rel('mot-du-jour/'), quote=True)}">mot du jour Cémantix</a> et la
        <a href="{escape(_rel('methode/'), quote=True)}">méthode des indices</a> explique
        comment lire ces scores. Pour jouer immédiatement, direction le
        <a href="{escape(_rel('play/'), quote=True)}">mode solo illimité</a> ou le
        <a href="{escape(_rel('battle/'), quote=True)}">mode Battle contre l'IA</a>.</p>
      </section>"""

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


def _pager_href(from_page: int, to_page: int) -> str:
    """Calcule le chemin relatif exact entre la page actuelle et la page cible."""
    if from_page == 1:
        return "./" if to_page == 1 else f"page/{to_page}/"
    else:
        return "../../" if to_page == 1 else f"../{to_page}/"


def _build_pager(page: int, total_pages: int) -> str:
    """Génère la navigation paginée complète avec Précédent, Suivant et ellipses."""
    if total_pages <= 1:
        return '<span class="current" aria-current="page">1</span>'

    links = []

    # 1. Bouton Précédent
    if page > 1:
        prev_href = _pager_href(page, page - 1)
        links.append(
            f'<a href="{escape(prev_href, quote=True)}" class="pager-nav pager-prev" rel="prev">‹ Précédent</a>'
        )
    else:
        links.append('<span class="pager-nav pager-prev disabled" aria-disabled="true">‹ Précédent</span>')

    # 2. Fenêtre de numéros de pages avec ellipses
    visible = {1, total_pages}
    for p in range(page - 2, page + 3):
        if 1 <= p <= total_pages:
            visible.add(p)
    if page <= 3:
        for p in range(1, min(5, total_pages + 1)):
            visible.add(p)
    if page >= total_pages - 2:
        for p in range(max(1, total_pages - 3), total_pages + 1):
            visible.add(p)

    sorted_pages = sorted(visible)
    last_p = 0
    for p in sorted_pages:
        if last_p and p > last_p + 1:
            links.append('<span class="pager-gap" aria-hidden="true">…</span>')
        if p == page:
            links.append(f'<span class="current" aria-current="page">{p}</span>')
        else:
            rel = ' rel="start"' if p == 1 else (
                ' rel="prev"' if p == page - 1 else (
                    ' rel="next"' if p == page + 1 else ""
                )
            )
            href = _pager_href(page, p)
            links.append(f'<a href="{escape(href, quote=True)}"{rel}>{p}</a>')
        last_p = p

    # 3. Bouton Suivant
    if page < total_pages:
        next_href = _pager_href(page, page + 1)
        links.append(
            f'<a href="{escape(next_href, quote=True)}" class="pager-nav pager-next" rel="next">Suivant ›</a>'
        )
    else:
        links.append('<span class="pager-nav pager-next disabled" aria-disabled="true">Suivant ›</span>')

    return "\n        ".join(links)


def build_archives_index_page(entries: list, page: int, total_pages: int) -> str:
    """Génère une page d'index des archives (`/puzzles/` ou `/puzzles/page/N/`)."""
    start = (page - 1) * ARCHIVES_PAGE_SIZE
    chunk = entries[start:start + ARCHIVES_PAGE_SIZE]
    newest = entries[0] if entries else None
    newest_fr = format_date_fr(newest.get("date")) if newest else ""

    if page == 1:
        title = "Indice Cémantix du jour : archives des mots du jour, indices et solutions par date"
    else:
        title = f"Indice Cémantix du jour : archives des indices et solutions, page {page}"
    description = (
        f"Le mot du jour Cémantix et ses indices, date par date ({len(entries)} puzzles "
        f"résolus) : thermomètre sémantique, nombre de coups et solution dépliable. "
        f"Dernière archive : {newest_fr}."
    )
    canonical = (
        f"{SITE_ORIGIN}/puzzles/" if page == 1 else f"{SITE_ORIGIN}/puzzles/page/{page}/"
    )
    depth = "../" if page == 1 else "../../../"

    def _resolve(href: str) -> str:
        return f"{depth}{href}"

    if page > 1:
        breadcrumbs = (
            f'<a href="{escape(_resolve(""), quote=True)}">Accueil</a>'
            f'<span class="crumb-sep">›</span>'
            f'<a href="{escape(_resolve("puzzles/"), quote=True)}">Archives</a>'
            f'<span class="crumb-sep">›</span>'
            f"<span>Page {page}</span>"
        )
    else:
        breadcrumbs = ""

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": f"{canonical}#collection",
        "name": title,
        "headline": title,
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
            f'          <li><a href="{escape(_resolve(f"puzzles/{date_str}/"), quote=True)}">'
            f"<span>{escape(archive_anchor(date_str))}</span>"
            f"<span>{escape(suffix)}</span></a></li>"
        )
    listing = "\n".join(items) or (
        '          <li><span>Aucun puzzle résolu pour le moment.</span></li>'
    )

    pager = _build_pager(page, total_pages)

    body = f"""      <h1>Archives Cémantix du jour : le mot du jour, ses indices et sa solution</h1>
      <p>Chaque jour à minuit (heure de Paris), le solveur résout le mot secret de
      Cémantix et publie l'archive datée du puzzle : numéro, nombre de coups, durée de
      calcul, top des mots les plus proches et solution dépliable. Le puzzle en cours se
      suit sur la page <a href="{escape(_resolve('mot-du-jour/'), quote=True)}">mot du jour Cémantix</a> ;
      pour apprendre à lire les scores, la <a href="{escape(_resolve('methode/'), quote=True)}">méthode des indices Cémantix</a>
      explique le thermomètre, les pour mille et les synonymes à tester.</p>
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
        resolve=_resolve,
    )


__all__ = [
    "build_archive_page",
    "build_archives_index_page",
]
