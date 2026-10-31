"""
Cémantix Solver — Sitemap XML & Écriture Atomique SEO (seo_sitemap)
==================================================================
Génère le fichier `sitemap.xml` conforme au protocole sitemaps.org
et fournit la fonction d'écriture atomique multi-processus/multi-conteneurs.
"""
import os
from pathlib import Path
import secrets
from datetime import datetime
from html import escape
from typing import Optional

from .seo_templates import (
    ARCHIVES_MAX_PAGES,
    ARCHIVES_PAGE_SIZE,
    SITEMAP_MAX_URLS,
    SITE_ORIGIN,
    archive_url,
    parse_puzzle_date,
)


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
        _sitemap_url(f"{SITE_ORIGIN}/mot-du-jour/", newest_date, "0.95"),
        _sitemap_url(f"{SITE_ORIGIN}/puzzles/", newest_date, "0.9"),
        _sitemap_url(f"{SITE_ORIGIN}/methode/", today, "0.9", "monthly"),
        _sitemap_url(f"{SITE_ORIGIN}/play/", today, "0.9", "weekly"),
        _sitemap_url(f"{SITE_ORIGIN}/battle/", today, "0.9", "weekly"),
        _sitemap_url(f"{SITE_ORIGIN}/defi/", today, "0.9", "weekly"),
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


__all__ = [
    "_sitemap_url",
    "build_sitemap",
    "_write_file",
]
