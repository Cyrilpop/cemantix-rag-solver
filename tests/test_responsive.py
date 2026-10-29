"""Tests de non-régression desktop et des invariants responsive mobile (RESP-01 à RESP-12).

Lancement (dans Docker) :
  docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests -v
"""
import re
import unittest
from pathlib import Path

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "volumes" / "web"
CSS_DIR = WEB_DIR / "css"
DIST_DIR = CSS_DIR / "dist"
JS_DIR = WEB_DIR / "js"

BUNDLES: dict[str, tuple[str, ...]] = {
    "dashboard": ("variables.css", "base.css", "layout.css", "dashboard.css", "modal.css"),
    "play": ("variables.css", "base.css", "layout.css", "game.css", "modal.css"),
    "battle": ("variables.css", "base.css", "layout.css", "game.css", "modal.css", "battle.css"),
    "multi": ("variables.css", "base.css", "layout.css", "game.css", "modal.css", "multi.css"),
    "modal": ("modal.css",),
    "puzzle": ("puzzle.css",),
}

CRITICAL_PAGES: dict[str, tuple[Path, tuple[str, ...]]] = {
    "dashboard": (WEB_DIR / "index.html", ("variables.css", "base.css", "layout.css", "dashboard.css")),
    "play": (WEB_DIR / "play" / "index.html", ("variables.css", "base.css", "layout.css", "game.css")),
    "battle": (WEB_DIR / "battle" / "index.html", ("variables.css", "base.css", "layout.css", "game.css", "battle.css")),
    "multi": (WEB_DIR / "multi" / "index.html", ("variables.css", "base.css", "layout.css", "game.css", "multi.css")),
}


def _strip_comments(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"[ \t]*\n[ \t]*", "\n", css)
    css = re.sub(r"\n{2,}", "\n", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    css = css.replace("}", "}\n")
    return css.strip()


def _extract_media_blocks(css: str) -> list[tuple[str, str]]:
    """Extrait les blocs @media (condition, contenu interne) avec équilibrage d'accolades."""
    cleaned = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    blocks: list[tuple[str, str]] = []
    idx = 0
    while True:
        match = re.search(r"@media\s*([^{]+)\{", cleaned[idx:])
        if not match:
            break
        cond = match.group(1).strip()
        brace_open = idx + match.end() - 1
        depth = 0
        pos = brace_open
        while pos < len(cleaned):
            if cleaned[pos] == "{":
                depth += 1
            elif cleaned[pos] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((cond, cleaned[brace_open + 1 : pos]))
                    idx = pos + 1
                    break
            pos += 1
        else:
            break
    return blocks


def _strip_media_blocks(css: str) -> str:
    """Retourne uniquement les règles hors blocs @media (socle Desktop)."""
    cleaned = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[str] = []
    idx = 0
    while True:
        match = re.search(r"@media\s*[^{]+\{", cleaned[idx:])
        if not match:
            out.append(cleaned[idx:])
            break
        out.append(cleaned[idx : idx + match.start()])
        pos = idx + match.end() - 1
        depth = 0
        while pos < len(cleaned):
            if cleaned[pos] == "{":
                depth += 1
            elif cleaned[pos] == "}":
                depth -= 1
                if depth == 0:
                    idx = pos + 1
                    break
            pos += 1
        else:
            break
    return "".join(out)


class TestBundlesEtFinsDeLigne(unittest.TestCase):
    """Garantit la fraîcheur des bundles CSS minifiés et l'encodage LF Unix."""

    def test_bundles_dist_synchronises_avec_sources(self):
        for bundle_name, sources in BUNDLES.items():
            parts = [
                f"/* {src} */\n{_strip_comments((CSS_DIR / src).read_text(encoding='utf-8'))}"
                for src in sources
            ]
            header = (
                f"/* Bundle {bundle_name} — généré par tools/build_css_bundles.py. "
                f"Ne pas éditer : modifier css/*.css puis relancer le script. */\n"
            )
            expected = header + "\n".join(parts) + "\n"
            actual = (DIST_DIR / f"{bundle_name}.css").read_text(encoding="utf-8")
            self.assertEqual(
                actual,
                expected,
                f"Le bundle compilé css/dist/{bundle_name}.css n'est pas synchronisé avec ses sources.",
            )

    def test_aucun_retour_chariot_crlf_dans_les_assets_web(self):
        tracked_html = [
            WEB_DIR / "index.html",
            WEB_DIR / "play" / "index.html",
            WEB_DIR / "battle" / "index.html",
            WEB_DIR / "multi" / "index.html",
        ]
        # puzzles/index.html est généré dynamiquement au runtime (non suivi sous Git en CI)
        puzzles_html = WEB_DIR / "puzzles" / "index.html"
        if puzzles_html.is_file():
            tracked_html.append(puzzles_html)

        targets = (
            list(CSS_DIR.glob("*.css"))
            + list(DIST_DIR.glob("*.css"))
            + list(JS_DIR.glob("*.js"))
            + tracked_html
        )
        for path in targets:
            raw_bytes = path.read_bytes()
            self.assertNotIn(b"\r\n", raw_bytes, f"Fin de ligne CRLF détectée dans {path.relative_to(ROOT)}")


class TestSanctuarisationDesktop(unittest.TestCase):
    """Vérifie que l'affichage Desktop (> 768px) demeure strictement intact."""

    def test_socle_desktop_intact_hors_media_queries(self):
        layout_desktop = _strip_media_blocks((CSS_DIR / "layout.css").read_text(encoding="utf-8"))
        self.assertIn("max-width: 1200px", layout_desktop)
        self.assertRegex(layout_desktop, r"\.nav-tabs\s*\{[^}]*justify-content:\s*center")
        self.assertRegex(layout_desktop, r"\.grid-2col\s*\{[^}]*grid-template-columns:\s*1fr\s+1fr")

        dash_desktop = _strip_media_blocks((CSS_DIR / "dashboard.css").read_text(encoding="utf-8"))
        self.assertRegex(dash_desktop, r"\.hero-body-grid\s*\{[^}]*grid-template-columns:\s*1\.35fr\s+1fr")
        self.assertRegex(dash_desktop, r"\.stats-row\s*\{[^}]*grid-template-columns:\s*repeat\(4,\s*1fr\)")

        game_desktop = _strip_media_blocks((CSS_DIR / "game.css").read_text(encoding="utf-8"))
        self.assertRegex(game_desktop, r"\.guess-form-row\s*\{[^}]*display:\s*flex")
        self.assertNotIn("flex-direction: column", re.search(r"\.guess-form-row\s*\{[^}]*\}", game_desktop).group(0))

        multi_desktop = _strip_media_blocks((CSS_DIR / "multi.css").read_text(encoding="utf-8"))
        self.assertRegex(multi_desktop, r"\.multi-results-grid\s*\{[^}]*grid-template-columns:\s*1fr\s+1fr")

        battle_desktop = _strip_media_blocks((CSS_DIR / "battle.css").read_text(encoding="utf-8"))
        self.assertRegex(battle_desktop, r"\.battle-hud-grid\s*\{[^}]*grid-template-columns:\s*1fr\s+auto\s+1fr")

    def test_helpers_js_mobiles_gardes_par_largeur_768(self):
        theme_js = (JS_DIR / "theme.js").read_text(encoding="utf-8")
        self.assertIn("window.innerWidth > 768", theme_js)
        self.assertGreaterEqual(theme_js.count("window.innerWidth > 768"), 2)


class TestInvariantsResponsiveMobile(unittest.TestCase):
    """Vérifie les 12 constats de la feuille de route 2026-10-responsive-mobile."""

    def _mobile_css(self, filename: str) -> str:
        blocks = _extract_media_blocks((CSS_DIR / filename).read_text(encoding="utf-8"))
        return "\n".join(body for cond, body in blocks if "max-width" in cond)

    def test_resp_01_et_12_verrouillage_horizontal_et_header_mobile(self):
        base_mob = self._mobile_css("base.css")
        self.assertIn("overflow-x: clip", base_mob)
        self.assertRegex(base_mob, r"\.btn-icon\s*\{[^}]*min-width:\s*44px")
        self.assertRegex(base_mob, r"\.btn-icon\s*\{[^}]*min-height:\s*44px")

        layout_mob = self._mobile_css("layout.css")
        self.assertIn("clamp(", layout_mob)
        self.assertRegex(layout_mob, r"#daemon-status-text\s*\{[^}]*display:\s*none")

    def test_resp_02_navigation_principale_sans_rognage_gauche(self):
        layout_mob = self._mobile_css("layout.css")
        self.assertRegex(layout_mob, r"\.nav-tabs\s*\{[^}]*justify-content:\s*flex-start")
        self.assertRegex(layout_mob, r"\.nav-tabs\s*\{[^}]*flex-wrap:\s*nowrap")
        self.assertRegex(layout_mob, r"\.nav-tabs\s*\{[^}]*overflow-x:\s*auto")
        # Ne jamais masquer .tab-badge globalement (protège #arena-diff-badge sur /multi/)
        self.assertIn(".nav-tab .tab-badge", layout_mob)

        multi_js = (JS_DIR / "multi.js").read_text(encoding="utf-8")
        self.assertIn("initTheme", multi_js)

    def test_resp_03_et_04_zone_saisie_empilee_et_clavier_virtuel(self):
        game_mob = self._mobile_css("game.css")
        self.assertRegex(game_mob, r"\.guess-form-row\s*\{[^}]*flex-direction:\s*column")
        self.assertRegex(game_mob, r"\.game-input\s*\{[^}]*font-size:\s*16px")
        self.assertRegex(game_mob, r"\.guess-side-actions\s*\{[^}]*grid-template-columns:\s*1fr\s+1fr")
        self.assertRegex(game_mob, r"\.game-guesses-list\s*\{[^}]*height:\s*auto")
        self.assertIn("38dvh", game_mob)
        self.assertIn("html.is-keyboard-open", game_mob)

    def test_resp_05_et_06_dashboard_metriques_et_thermometre(self):
        dash_css = (CSS_DIR / "dashboard.css").read_text(encoding="utf-8")
        dash_mob = self._mobile_css("dashboard.css")
        self.assertRegex(dash_mob, r"\.metrics-grid\s*\{[^}]*repeat\(2,\s*minmax\(0,\s*1fr\)\)")
        self.assertRegex(dash_mob, r"\.metric-card:last-child\s*\{[^}]*grid-column:\s*1\s*/\s*-1")
        self.assertRegex(dash_mob, r"\.temp-tier\s*\{[^}]*flex-direction:\s*column")

        # Vérifie que les règles de base précèdent bien leurs surcharges @media dans dashboard.css
        self.assertGreater(dash_css.rfind("@media (max-width: 768px)"), dash_css.find(".faq-answer {"))
        self.assertGreater(dash_css.rfind("@media (max-width: 640px)"), dash_css.find(".btn-trajectory {"))
        self.assertGreater(dash_css.rfind("@media (max-width: 480px)"), dash_css.find(".stat-label {"))

        index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        self.assertEqual(index_html.count('class="tier-emoji"'), 5)

    def test_resp_07_08_09_multijoueur_lobby_cartes_et_safe_area(self):
        multi_mob = self._mobile_css("multi.css")
        self.assertRegex(multi_mob, r"\.lobby-nav\s*\{[^}]*justify-content:\s*flex-start")
        self.assertRegex(multi_mob, r"\.lobby-tab-btn\s*\{[^}]*min-width:\s*max-content")
        self.assertRegex(multi_mob, r"\.mode-cards-grid\s*\{[^}]*grid-template-columns:\s*1fr")
        self.assertRegex(multi_mob, r"\.multi-list-card\s+\.game-guesses-list\s*\{[^}]*height:\s*auto")
        self.assertIn("safe-area-inset-bottom", multi_mob)

        multi_html = (WEB_DIR / "multi" / "index.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(multi_html.count('class="hide-mobile-inline"'), 4)
        self.assertIn("waiting-actions", multi_html)
        self.assertIn("arena-topbar-actions", multi_html)

    def test_resp_10_battle_scoreboard_et_actions(self):
        battle_mob = self._mobile_css("battle.css")
        self.assertRegex(battle_mob, r"\.battle-actions\s*\{[^}]*display:\s*flex")
        self.assertRegex(
            battle_mob,
            r"\.battle-scoreboard\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto\s+minmax\(0,\s*1fr\)",
        )
        self.assertRegex(battle_mob, r"\.target-revealed\s*\{[^}]*overflow-wrap:\s*anywhere")

    def test_resp_11_modales_cibles_44px_et_dvh(self):
        modal_mob = self._mobile_css("modal.css")
        self.assertRegex(modal_mob, r"\.modal-close-btn\s*\{[^}]*min-width:\s*44px")
        self.assertRegex(modal_mob, r"\.modal-badges\s*\{[^}]*flex-wrap:\s*wrap")
        self.assertRegex(modal_mob, r"#trajectory-filter-group\s*\{[^}]*repeat\(2,\s*minmax\(0,\s*1fr\)\)")
        self.assertIn("92dvh", modal_mob)
        self.assertIn("safe-area-inset-bottom", modal_mob)


class TestPerformanceMobilePageSpeed(unittest.TestCase):
    """Verrouille l'absence de CSS bloquant le rendu et de reflow forcé JS sur mobile."""

    def test_aucune_feuille_css_bloquante_et_conformite_csp(self):
        for bundle_name, (html_path, sources) in CRITICAL_PAGES.items():
            html = html_path.read_text(encoding="utf-8")
            # Aucun gestionnaire inline onload= (interdit par la CSP script-src 'self')
            self.assertNotRegex(html, r"\bonload\s*=", f"Attribut onload interdit par CSP dans {html_path}")

            # Toutes les balises <link rel="stylesheet"> hors <noscript> doivent être différées (media="print")
            hors_noscript = re.sub(r"<noscript>.*?</noscript>", "", html, flags=re.DOTALL | re.IGNORECASE)
            for link_tag in re.findall(r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', hors_noscript, flags=re.IGNORECASE):
                self.assertIn('media="print"', link_tag, f"Feuille CSS bloquante détectée dans {html_path}: {link_tag}")
                self.assertIn("data-deferred-css", link_tag)

            # Le bloc <style id="critical-css"> doit être synchronisé avec les sources minifiées
            expected_compact = "".join(
                _strip_comments((CSS_DIR / src).read_text(encoding="utf-8")).replace("\n", "")
                for src in sources
            )
            match = re.search(
                rf'<style id="critical-css" data-bundle="{re.escape(bundle_name)}">(.*?)</style>',
                html,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, f"Bloc <style id='critical-css'> manquant dans {html_path}")
            self.assertEqual(
                match.group(1),
                expected_compact,
                f"CSS critique inline désynchronisé dans {html_path.relative_to(ROOT)}",
            )

    def test_pages_archives_seo_sans_requete_css_bloquante(self):
        from src.services import seo

        rendered = seo.render_page(
            title="Test",
            description="Description test",
            canonical="https://cemantix.cyril-randon.fr/puzzles/",
            json_ld="",
            body="<p>Contenu</p>",
            breadcrumbs="",
            resolve=lambda p: f"../{p}",
        )
        self.assertNotIn('rel="stylesheet"', rendered)
        self.assertIn(".puzzle-link", rendered)

    def test_aucun_reflow_synchrone_dans_init_mobile_nav_scroll(self):
        theme_js = (JS_DIR / "theme.js").read_text(encoding="utf-8")
        # initTheme ne doit pas réécrire data-theme inconditionnellement
        self.assertIn('html.getAttribute("data-theme") !== themeState.theme', theme_js)
        # Dans initMobileNavScroll, la lecture de window.innerWidth doit être différée dans requestAnimationFrame
        fn_match = re.search(
            r"export function initMobileNavScroll\(\)\s*\{(.*?)\n\}",
            theme_js,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(fn_match)
        fn_body = fn_match.group(1)
        before_raf = fn_body.split("requestAnimationFrame")[0]
        self.assertNotIn("innerWidth", before_raf)
        self.assertNotIn("offsetWidth", before_raf)
        self.assertNotIn("scrollWidth", before_raf)


if __name__ == "__main__":
    unittest.main()
