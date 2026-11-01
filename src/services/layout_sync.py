"""
Cémantix Solver — Synchronisation Modulaire du Layout (layout_sync)
===================================================================
Gère la synchronisation automatique des composants d'en-tête (Header)
et de navigation (Menu / Nav-tabs) sur toutes les pages HTML du projet.
Assure l'alignement strict du layout au démarrage du conteneur.
"""
from pathlib import Path
import re
from typing import Dict, Optional

from ..config import BASE_DIR

WEB_ROOT = BASE_DIR / "volumes" / "web"

HEADER_START = "<!-- APP-HEADER:START -->"
HEADER_END = "<!-- APP-HEADER:END -->"
NAV_START = "<!-- NAV-TABS:START -->"
NAV_END = "<!-- NAV-TABS:END -->"

TABS_CONFIG = [
    ("tab-dashboard", "dashboard", "", "📊", "Tableau de Bord", None),
    ("tab-play", "play", "play/", "🎮", "Jouer Solo", None),
    ("tab-battle", "battle", "battle/", "⚔️", "Mode Battle", "Versus IA"),
    ("tab-multi", "multi", "multi/", "👥", "Mode Multijoueur", "1v1 Ami"),
    ("tab-defi", "defi", "defi/", "🤖", "Défier le Bot", "Live"),
    ("tab-archives", "archives", "puzzles/", "📚", "Archives", None),
]


def render_header(depth: str = "") -> str:
    """Génère l'en-tête universel canonique (Header)."""
    logo_src = f"{depth}icons/favicon.png" if depth else "icons/favicon.png"
    return f"""  <header class="app-header">
    <div class="header-container">
      <div class="brand">
        <img src="{logo_src}" alt="Cémantix Solver" class="brand-icon" width="48" height="48">
        <div class="brand-text">
          <span class="brand-title">Cémantix Solver</span>
          <span class="brand-subtitle">Mot du Jour &amp; IA Sémantique</span>
        </div>
      </div>

      <div class="header-actions">
        <div id="daemon-badge" class="status-badge status-sleeping" title="État du démon d'automatisation">
          <span class="status-pulse"></span>
          <span id="daemon-status-text">Veille active (00h00)</span>
        </div>

        <button id="theme-toggle" class="btn-icon" aria-label="Changer de thème" title="Basculer Mode Clair / Sombre">
          <span class="theme-icon">☀️</span>
        </button>

        <button id="global-spoiler-toggle" class="btn-icon" aria-label="Mode anti-spoiler" title="Activer / Désactiver le flou anti-spoiler">
          <span class="spoiler-icon">🛡️</span>
        </button>
      </div>
    </div>
  </header>"""


def render_nav_tabs(depth: str = "", active_tab: str = "dashboard") -> str:
    """Génère la barre d'onglets canonique (Menu) avec état actif et badges."""
    items = []
    for tab_id, tab_key, subpath, icon, label, badge in TABS_CONFIG:
        is_active = (tab_key == active_tab)
        active_cls = " active" if is_active else ""

        # Calcul du href relatif
        if is_active and depth == "../" and tab_key != "dashboard":
            href = "./"
        elif is_active and not depth and tab_key == "dashboard":
            href = "./"
        elif not depth:
            href = "./" if tab_key == "dashboard" else subpath
        else:
            href = f"{depth}{subpath}"

        badge_html = f'\n        <span class="tab-badge">{badge}</span>' if badge else ""
        items.append(
            f'      <a href="{href}" id="{tab_id}" class="nav-tab{active_cls}">\n'
            f'        <span class="tab-icon">{icon}</span>\n'
            f'        <span>{label}</span>{badge_html}\n'
            f'      </a>'
        )

    tabs_inner = "\n".join(items)
    return f"""    <nav class="nav-tabs" aria-label="Navigation des vues">
{tabs_inner}
    </nav>"""


def render_footer(depth: str = "") -> str:
    """Génère le pied de page universel canonique (Footer)."""
    home = depth if depth else "./"
    return f"""  <footer class="app-footer">
    <div class="footer-container">
      <div class="footer-left">
        <p><strong>Cémantix Solver</strong> — Propulsé par RAG vectoriel (frWac Word2Vec + ChromaDB).</p>
        <span class="footer-sub">Conçu par <a href="https://cyril-randon.fr" target="_blank" rel="noopener noreferrer" class="footer-author-link">Cyril RANDON</a>. Projets <a href="https://github.com/Cyrilpop" target="_blank" rel="noopener noreferrer" class="footer-author-link">Github</a></span>
      </div>
      <div class="footer-right">
        <a href="{home}" class="btn btn-ghost btn-sm" title="Tableau de Bord">
          <span>📊</span> Dashboard
        </a>
        <a href="{depth}play/" class="btn btn-ghost btn-sm" title="Jouer Solo">
          <span>🎮</span> Jouer Solo
        </a>
        <a href="{depth}battle/" class="btn btn-ghost btn-sm" title="Mode Battle">
          <span>⚔️</span> Battle
        </a>
      </div>
    </div>
  </footer>"""


def sync_html_file(file_path: Path, depth: str, active_tab: str) -> bool:
    """Met à jour les blocs Header et Menu dans un fichier HTML statique."""
    if not file_path.exists():
        return False

    original = file_path.read_text(encoding="utf-8")
    content = original
    header_html = render_header(depth)
    nav_html = render_nav_tabs(depth, active_tab)

    # 1. Remplacement ou balisage du Header
    if HEADER_START in content and HEADER_END in content:
        pattern = re.compile(rf"{re.escape(HEADER_START)}.*?{re.escape(HEADER_END)}", re.DOTALL)
        content = pattern.sub(f"{HEADER_START}\n{header_html}\n  {HEADER_END}", content, count=1)
    else:
        pattern = re.compile(r"<header\s+class=[\"']app-header[\"'].*?</header>", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(f"{HEADER_START}\n{header_html}\n  {HEADER_END}", content, count=1)

    # 2. Remplacement ou balisage de la Navigation
    if NAV_START in content and NAV_END in content:
        pattern = re.compile(rf"{re.escape(NAV_START)}.*?{re.escape(NAV_END)}", re.DOTALL)
        content = pattern.sub(f"{NAV_START}\n{nav_html}\n    {NAV_END}", content, count=1)
    else:
        pattern = re.compile(r"<nav\s+class=[\"']nav-tabs[\"'].*?</nav>", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(f"{NAV_START}\n{nav_html}\n    {NAV_END}", content, count=1)

    if content != original:
        file_path.write_text(content, encoding="utf-8")
    return True


def sync_all_pages(web_root: Optional[Path] = None) -> Dict[str, bool]:
    """Synchronise toutes les pages statiques fixes de l'application."""
    root = web_root if web_root is not None else WEB_ROOT
    pages = [
        ("index.html", "", "dashboard"),
        ("play/index.html", "../", "play"),
        ("battle/index.html", "../", "battle"),
        ("multi/index.html", "../", "multi"),
        ("defi/index.html", "../", "defi"),
    ]
    results = {}
    for rel_path, depth, active_tab in pages:
        target = root / rel_path
        results[rel_path] = sync_html_file(target, depth, active_tab)
    return results
