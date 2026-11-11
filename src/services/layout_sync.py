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
FOOTER_START = "<!-- APP-FOOTER:START -->"
FOOTER_END = "<!-- APP-FOOTER:END -->"

TABS_CONFIG = [
    ("tab-dashboard", "dashboard", "", "🎯", "Mot du Jour", None),
    ("tab-play", "play", "play/", "🎮", "Jouer Solo", None),
    ("tab-battle", "battle", "battle/", "⚔️", "Mode Battle", "Versus IA"),
    ("tab-multi", "multi", "multi/", "👥", "Mode Multijoueur", "1v1 Ami"),
    ("tab-defi", "defi", "defi/", "🤖", "Défier le Bot", "Live"),
    ("tab-archives", "archives", "puzzles/", "📚", "Archives", None),
]


def render_header(depth: str = "") -> str:
    """Génère l'en-tête universel canonique (Header)."""
    return """  <header class="app-header">
    <div class="header-container">
      <div class="brand">
        <a href="/" class="brand-link" style="display:flex;align-items:center;gap:0.75rem;text-decoration:none;color:inherit;">
          <img src="/icons/favicon.png" alt="Cémantix Solver" class="brand-icon" width="48" height="48">
          <div class="brand-text">
            <span class="brand-title">Cémantix Solver</span>
            <span class="brand-subtitle">Mot du Jour &amp; IA Sémantique</span>
          </div>
        </a>
      </div>

      <div class="header-actions">
        <div id="player-welcome-badge" class="player-welcome-badge" title="Bienvenue sur Cémantix Solver">
          <span class="welcome-wave">👋</span>
          <span class="welcome-text">Bienvenue <strong id="player-welcome-name">Joueur</strong></span>
        </div>

        <button id="player-badge" class="player-badge" aria-label="Mon compte" title="Mon compte">
          <span class="player-icon">👤</span>
          <span id="player-badge-name" class="player-name">Mon compte</span>
          <span class="player-caret">▾</span>
        </button>

        <button id="theme-toggle" class="btn-icon" aria-label="Changer de thème" title="Basculer Mode Clair / Sombre">
          <span class="theme-icon">☼</span>
        </button>

        <button id="global-spoiler-toggle" class="btn-icon" aria-label="Mode anti-spoiler" title="Activer / Désactiver le flou anti-spoiler">
          <span class="spoiler-icon">🔒</span>
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

        # Calcul du href absolu depuis la racine (anti crawl-trap SEO)
        href = f"/{subpath}"

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
    """Génère le pied de page universel canonique (Footer) avec liens racine absolus."""
    return """  <footer class="app-footer">
    <div class="footer-container">
      <div class="footer-left">
        <p><strong>Cémantix Solver</strong> — Propulsé par RAG vectoriel (frWac Word2Vec + ChromaDB).</p>
        <span class="footer-sub">Conçu par <a href="https://cyril-randon.fr" target="_blank" rel="noopener noreferrer" class="footer-author-link">Cyril RANDON</a>. Projets <a href="https://github.com/Cyrilpop" target="_blank" rel="noopener noreferrer" class="footer-author-link">Github</a> · <a href="/#confidentialite" class="footer-author-link">Politique de confidentialité</a> · <a href="/#conditions-utilisation" class="footer-author-link">Conditions d'utilisation</a></span>
      </div>
      <div class="footer-right">
        <span id="app-version" class="footer-time">v--</span>
        <a href="/" class="btn btn-ghost btn-sm" title="Mot du Jour">
          <span>🎯</span> Mot du Jour
        </a>
        <a href="/play/" class="btn btn-ghost btn-sm" title="Jouer Solo">
          <span>🎮</span> Jouer Solo
        </a>
        <a href="/battle/" class="btn btn-ghost btn-sm" title="Mode Battle">
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

    # 3. Remplacement ou balisage du Footer universel
    footer_html = render_footer(depth)
    if FOOTER_START in content and FOOTER_END in content:
        pattern = re.compile(rf"{re.escape(FOOTER_START)}.*?{re.escape(FOOTER_END)}", re.DOTALL)
        content = pattern.sub(f"{FOOTER_START}\n{footer_html}\n  {FOOTER_END}", content, count=1)
    else:
        pattern = re.compile(r"<footer\s+class=[\"']app-footer[\"'].*?</footer>", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(f"{FOOTER_START}\n{footer_html}\n  {FOOTER_END}", content, count=1)

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
        ("puzzles/index.html", "../", "archives"),
    ]
    results = {}
    for rel_path, depth, active_tab in pages:
        target = root / rel_path
        results[rel_path] = sync_html_file(target, depth, active_tab)

    # Injection du bloc Google Tag Manager placeholder (l'ID réel est substitué
    # à la livraison HTTP ; voir src/services/gtm.py). La console /panier-9x/
    # est volontairement exclue du suivi.
    from .gtm import sync_static_pages as sync_gtm_pages
    for rel_path, ok in sync_gtm_pages(web_root=root).items():
        results[f"gtm:{rel_path}"] = ok
    return results
