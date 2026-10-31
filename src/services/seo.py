"""
Cémantix Solver — Orchestration & Publication SEO (seo)
======================================================
Transforme l'historique des résolutions en contenu indexable par les moteurs
de recherche, sans dépendre de l'exécution JavaScript côté navigateur.

Ce module orchestre la publication SEO et ré-exporte l'ensemble des composants
du sous-système SEO pour une rétrocompatibilité descendante totale :
- `seo_templates` : Gabarits HTML, helpers de formatage et tokens de style.
- `seo_archives`  : Pages individuelles d'archives et index paginé.
- `seo_hubs`      : Pages hub « mot du jour » et « méthode & indices ».
- `seo_sitemap`   : Génération du sitemap XML et écriture atomique.
- `seo_agents`    : Manifestes ARD/A2A et documentation agentique dynamique.
"""
from datetime import datetime
from html import escape
import os
from pathlib import Path
import re
from typing import Optional

from ..config import log

# --------------------------------------------------------------------------- #
# Ré-exports pour rétrocompatibilité totale
# --------------------------------------------------------------------------- #
from .seo_templates import (
    ARCHIVE_TITLE_PREFIX,
    ARCHIVES_DIRNAME,
    ARCHIVES_MAX_PAGES,
    ARCHIVES_PAGE_SIZE,
    METHODE_DIRNAME,
    MOT_DU_JOUR_DIRNAME,
    NAV_LINKS,
    PAGE_CSS,
    SITEMAP_MAX_URLS,
    SITE_ORIGIN,
    VARIABLES_CSS_FILE,
    WEB_ROOT,
    _CSS_LIGHT_RE,
    _CSS_ROOT_RE,
    _DATE_RE,
    _MONTHS_FR,
    _WEEKDAYS_FR,
    _archive_href,
    _clue_rows,
    _join,
    _json_ld_block,
    _load_puzzle_css,
    _load_style_tokens,
    _rel,
    _rel_index,
    _tier_class,
    archive_anchor,
    archive_title,
    archive_url,
    format_date_fr,
    format_duration_fr,
    hub_url,
    parse_puzzle_date,
    render_page,
)
from .seo_archives import (
    build_archive_page,
    build_archives_index_page,
)
from .seo_hubs import (
    _HUB_FAQ,
    _METHODE_ETAPES,
    _METHODE_FAQ,
    _METHODE_SECTIONS_A,
    _faq_items_html,
    _faq_json_ld,
    _hub_breadcrumb_json_ld,
    _hub_breadcrumbs,
    _render_hub_page,
    build_methode_page,
    build_mot_du_jour_page,
)
from .seo_sitemap import (
    _sitemap_url,
    _write_file,
    build_sitemap,
)
from .seo_agents import (
    _AGENT_DOCS_END,
    _AGENT_DOCS_START,
    _agent_dynamic_block,
    _replace_marked_block,
    build_agent_card,
    build_ard_manifest,
    publish_ard_manifests,
    refresh_agent_docs,
)


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
        f"{clue_part} La solution reste masquée tant que vous ne la demandez pas ; elle est "
        f"consultable sur la <a href=\"mot-du-jour/\">page du mot du jour Cémantix</a> et sur la "
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
            "resume-title": f"Cémantix du {date_fr} : indices et résumé du mot du jour",
            "resume-subtitle": "Indices, thermomètre et performance du solveur IA du jour",
            "resume-body": _daily_summary(entry),
            "resume-link": (
                "Le <a href=\"mot-du-jour/\">mot du jour Cémantix</a> reprend ces indices "
                "avec la solution dépliable, la <a href=\"methode/\">méthode des indices</a> "
                "explique le thermomètre et les synonymes à tester, et l'"
                "<a href=\"puzzles/\">archive complète des puzzles</a> les retrouve jour "
                "par jour."
            ),
        }
    else:
        replacements = {
            "resume-title": "Cémantix du jour : indices et résumé de la résolution",
            "resume-subtitle": "Indices, thermomètre et performance du solveur IA",
            "resume-body": (
                "Le résumé du puzzle du jour sera publié automatiquement après la "
                "résolution de minuit."
            ),
            "resume-link": (
                "Suivez le <a href=\"mot-du-jour/\">mot du jour Cémantix</a> dès sa "
                "publication, consultez la <a href=\"methode/\">méthode des indices</a> et "
                "l'<a href=\"puzzles/\">archive complète des puzzles</a>."
            ),
        }

    start = source.index(_PRERENDER_START)
    end = source.index(_PRERENDER_END, start)
    anchor = source.rfind(_PRERENDER_ANCHOR_ID, 0, start)
    block_start = source.rfind("<", 0, anchor) if anchor != -1 else start
    block = source[block_start:end]

    def _replace_seo_tag(text: str, key: str, new_content: str) -> str:
        pattern = re.compile(
            rf'(<([a-zA-Z0-9]+)\b[^>]*\bdata-seo="{re.escape(key)}"[^>]*>).*?(</\2>)',
            flags=re.DOTALL,
        )
        return pattern.sub(rf"\g<1>{new_content}\g<3>", text, count=1)

    for key, val in replacements.items():
        source = _replace_seo_tag(source, key, val)

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


# --------------------------------------------------------------------------- #
# Publication & Point d'entrée
# --------------------------------------------------------------------------- #
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

    written = {"archives": 0, "index_pages": 0, "hub_pages": 0, "sitemap": False, "ard_manifests": 0}

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

    hub = build_mot_du_jour_page(entries[0] if entries else None, entries)
    _write_file(root / MOT_DU_JOUR_DIRNAME / "index.html", hub)
    written["hub_pages"] += 1
    _write_file(root / METHODE_DIRNAME / "index.html", build_methode_page())
    written["hub_pages"] += 1

    written["prerender"] = prerender_dashboard(entries[0] if entries else None, web_root=root)
    written["agent_docs"] = refresh_agent_docs(entries, web_root=root)
    log(
        f"🔎  SEO publié : {written['archives']} archive(s), "
        f"{written['index_pages']} page(s) d'index, {written['hub_pages']} page(s) hub, "
        f"sitemap.xml régénéré, "
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


__all__ = [
    # Constantes
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
    # Templates & formatters
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
    # Archives
    "build_archive_page",
    "build_archives_index_page",
    # Hubs
    "_HUB_FAQ",
    "_METHODE_SECTIONS_A",
    "_METHODE_ETAPES",
    "_METHODE_FAQ",
    "_faq_items_html",
    "_faq_json_ld",
    "_hub_breadcrumbs",
    "_hub_breadcrumb_json_ld",
    "_render_hub_page",
    "build_mot_du_jour_page",
    "build_methode_page",
    # Sitemap
    "_sitemap_url",
    "_write_file",
    "build_sitemap",
    # Agents
    "_AGENT_DOCS_START",
    "_AGENT_DOCS_END",
    "_agent_dynamic_block",
    "_replace_marked_block",
    "refresh_agent_docs",
    "build_ard_manifest",
    "build_agent_card",
    "publish_ard_manifests",
    # Prerender & Orchestration
    "_PRERENDER_START",
    "_PRERENDER_END",
    "_PRERENDER_ANCHOR_ID",
    "_DATA_SEO_RE",
    "_daily_summary",
    "prerender_dashboard",
    "publish_seo_pages",
    "ensure_seo_published",
]
