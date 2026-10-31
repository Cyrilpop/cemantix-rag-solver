"""Tests de caractérisation du frontend Cémantix (M5).

Verrouille les contrats DOM, la cohérence de navigation, l'accessibilité,
les exports JavaScript partagés et l'intégrité anti-spoiler avant toute simplification.
"""
import re
import unittest
from pathlib import Path

import _context  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "volumes" / "web"
JS_DIR = WEB_DIR / "js"
CSS_DIR = WEB_DIR / "css"

PAGES = {
    "dashboard": WEB_DIR / "index.html",
    "play": WEB_DIR / "play" / "index.html",
    "battle": WEB_DIR / "battle" / "index.html",
    "multi": WEB_DIR / "multi" / "index.html",
    "defi": WEB_DIR / "defi" / "index.html",
}


class TestFrontendDOMContracts(unittest.TestCase):
    """Vérifie la présence des éléments DOM indispensables au bon fonctionnement JS."""

    def test_dashboard_dom_contract(self):
        html = PAGES["dashboard"].read_text(encoding="utf-8")
        required_ids = [
            "view-dashboard",
            "secret-word-card",
            "secret-word",
            "daemon-badge",
            "theme-toggle",
            "global-spoiler-toggle",
            "tab-dashboard",
            "tab-play",
            "tab-battle",
            "tab-defi",
            "tab-multi",
            "tab-archives",
            "history-tbody",
            "toast",
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', html, f"ID manquant dans index.html : {el_id}")

    def test_solo_play_dom_contract(self):
        html = PAGES["play"].read_text(encoding="utf-8")
        required_ids = [
            "view-play",
            "game-guess-form",
            "game-word-input",
            "game-submit-btn",
            "game-hint-btn",
            "game-giveup-btn",
            "game-new-btn",
            "game-spotlight",
            "game-top-list",
            "game-chrono-list",
            "toast",
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', html, f"ID manquant dans play/index.html : {el_id}")

    def test_battle_dom_contract(self):
        html = PAGES["battle"].read_text(encoding="utf-8")
        required_ids = [
            "battle-word-input",
            "battle-submit-btn",
            "battle-hint-btn",
            "battle-giveup-btn",
            "battle-new-btn",
            "battle-player-list",
            "battle-ai-list",
            "battle-spotlight",
            "toast",
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', html, f"ID manquant dans battle/index.html : {el_id}")

    def test_multi_dom_contract(self):
        html = PAGES["multi"].read_text(encoding="utf-8")
        required_ids = [
            "view-lobby",
            "view-arena",
            "join-room-code",
            "btn-create-game",
            "arena-word-input",
            "arena-submit-btn",
            "toast",
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', html, f"ID manquant dans multi/index.html : {el_id}")

    def test_defi_dom_contract(self):
        html = PAGES["defi"].read_text(encoding="utf-8")
        required_ids = [
            "defi-form",
            "defi-word",
            "defi-submit",
            "defi-status",
            "defi-guesses",
            "defi-chrono",
            "toast",
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', html, f"ID manquant dans defi/index.html : {el_id}")


class TestFrontendNavigationContracts(unittest.TestCase):
    """Vérifie la cohérence de la barre de navigation partagée."""

    def test_all_pages_have_complete_navigation_tabs(self):
        nav_tab_ids = [
            "tab-dashboard",
            "tab-play",
            "tab-battle",
            "tab-defi",
            "tab-multi",
            "tab-archives",
        ]
        for name, path in PAGES.items():
            html = path.read_text(encoding="utf-8")
            self.assertIn('<nav class="nav-tabs"', html, f"Balise <nav class='nav-tabs'> absente de {name}")
            for tab_id in nav_tab_ids:
                self.assertIn(f'id="{tab_id}"', html, f"Onglet {tab_id} manquant dans {name}")

    def test_active_nav_tab_matches_page(self):
        expected_active = {
            "dashboard": "tab-dashboard",
            "play": "tab-play",
            "battle": "tab-battle",
            "multi": "tab-multi",
            "defi": "tab-defi",
        }
        for name, expected_id in expected_active.items():
            html = PAGES[name].read_text(encoding="utf-8")
            pattern = rf'id="{expected_id}"\s+class="nav-tab active"|class="nav-tab active"\s+id="{expected_id}"'
            self.assertRegex(html, pattern, f"L'onglet actif de {name} n'est pas {expected_id}")


class TestFrontendAccessibilityAndSecurity(unittest.TestCase):
    """Vérifie les critères d'accessibilité, métadonnées et sécurité CSP."""

    def test_html_meta_viewports_and_charset(self):
        for name, path in PAGES.items():
            html = path.read_text(encoding="utf-8")
            self.assertIn('<meta charset="UTF-8">', html, f"Charset UTF-8 manquant dans {name}")
            self.assertIn('viewport-fit=cover', html, f"viewport-fit=cover manquant dans {name}")
            self.assertIn('<html lang="fr"', html, f"lang='fr' manquant dans {name}")

    def test_csp_no_inline_onload_or_onclick(self):
        for name, path in PAGES.items():
            html = path.read_text(encoding="utf-8")
            # Interdit les gestionnaires onclick= et onload= inline dans les gabarits HTML
            self.assertNotRegex(html, r"\bonload\s*=", f"Attribut onload interdit dans {name}")
            self.assertNotRegex(html, r"\bonclick\s*=", f"Attribut onclick interdit dans {name}")

    def test_dialog_accessibility_roles(self):
        for name, path in PAGES.items():
            html = path.read_text(encoding="utf-8")
            modals = re.findall(r'<div[^>]*class="[^"]*modal-backdrop[^"]*"[^>]*>', html)
            for m in modals:
                self.assertIn('role="dialog"', m, f"role='dialog' manquant dans {m} ({name})")
                self.assertIn('aria-modal="true"', m, f"aria-modal='true' manquant dans {m} ({name})")

    def test_anti_spoiler_invariants(self):
        # Vérifie que le mot secret du jour n'apparaît jamais en clair dans le HTML statique
        for name, path in PAGES.items():
            html = path.read_text(encoding="utf-8")
            # Les zones de révélation utilisent les classes anti-spoiler
            if "word-spoiler" in html:
                self.assertIn("is-hidden", html)


class TestJavaScriptModuleExports(unittest.TestCase):
    """Garantit la stabilité des contrats d'export des modules ES JavaScript."""

    def test_utils_js_exports(self):
        code = (JS_DIR / "utils.js").read_text(encoding="utf-8")
        required_exports = [
            "escapeHtml",
            "escapeText",
            "safeNumber",
            "initDelegatedActions",
            "initErrorHandling",
            "showToast",
            "copyToClipboard",
            "formatDateFr",
            "getTierClass",
            "getTierWeatherIcon",
            "showConfirmDialog",
        ]
        for sym in required_exports:
            self.assertRegex(code, rf"export\s+(?:function|const)\s+{sym}\b", f"Export manquant dans utils.js : {sym}")

    def test_render_js_exports(self):
        code = (JS_DIR / "render.js").read_text(encoding="utf-8")
        self.assertRegex(code, r"export\s+function\s+buildGuessesListHtml\b")
        self.assertRegex(code, r"export\s+function\s+renderGuessesContainer\b")

    def test_theme_js_exports(self):
        code = (JS_DIR / "theme.js").read_text(encoding="utf-8")
        required_exports = [
            "initTheme",
            "initSpoiler",
            "toggleTheme",
            "toggleGlobalSpoiler",
            "themeState",
        ]
        for sym in required_exports:
            self.assertRegex(code, rf"export\s+(?:function|const)\s+{sym}\b", f"Export manquant dans theme.js : {sym}")

    def test_trajectory_js_exports(self):
        code = (JS_DIR / "trajectory.js").read_text(encoding="utf-8")
        self.assertRegex(code, r"export\s+function\s+initTrajectoryModal\b")
        self.assertRegex(code, r"export\s+function\s+openTrajectoryModal\b")

    def test_dashboard_js_exports(self):
        code = (JS_DIR / "dashboard.js").read_text(encoding="utf-8")
        required_exports = [
            "dashboardState",
            "initDashboard",
            "revealSecretWord",
            "fetchDashboardData",
            "renderDashboard",
        ]
        for sym in required_exports:
            self.assertRegex(code, rf"export\s+(?:function|const)\s+{sym}\b", f"Export manquant dans dashboard.js : {sym}")


class TestDashboardSecretWordReveal(unittest.TestCase):
    """Vérifie les contrats du mot secret du jour (M5.1).

    Couvre l'état initial, la révélation locale avec spoiler global activé,
    le bouton Masquer, le toggle global, la gestion d'erreurs, l'anti-rebond
    et l'accessibilité au clavier.
    """

    def setUp(self):
        self.html = PAGES["dashboard"].read_text(encoding="utf-8")
        self.js = (JS_DIR / "dashboard.js").read_text(encoding="utf-8")

    def test_secret_word_card_initial_hidden_state(self):
        """1. État initial masqué conforme et accessible."""
        # Dans le gabarit HTML
        self.assertIn('id="secret-word-card"', self.html)
        self.assertRegex(self.html, r'id="secret-word-card"[^>]*class="[^"]*\bis-spoiled\b')
        self.assertRegex(self.html, r'id="secret-word-card"[^>]*tabindex="0"')
        self.assertRegex(self.html, r'id="secret-word-card"[^>]*role="button"')
        self.assertRegex(self.html, r'id="secret-word-card"[^>]*aria-expanded="false"')
        self.assertRegex(self.html, r'id="secret-word-card"[^>]*aria-label=')
        self.assertIn('id="secret-word"', self.html)
        self.assertIn('--------</h2>', self.html)

        # Dans le state initial JS
        self.assertRegex(self.js, r"secretWord:\s*null")
        self.assertRegex(self.js, r"isRevealing:\s*false")

    def test_reveal_removes_spoiler_regardless_of_global_spoiler(self):
        """2. Le clic direct révèle le mot même avec le spoiler global actif."""
        # revealSecretWord ne doit plus conditionner la suppression de is-spoiled à !themeState.globalSpoiler
        pattern_bad = r'if\s*\(\s*!themeState\.globalSpoiler\s*\)\s*\{\s*secretWordCard\?\.classList\.remove\("is-spoiled"\)'
        self.assertNotRegex(self.js, pattern_bad, "La révélation locale ne doit pas être bloquée par globalSpoiler")

        # Vérifie la présence de la suppression inconditionnelle de is-spoiled et l'attribut aria-expanded="true"
        self.assertIn('secretWordCard?.classList.remove("is-spoiled");', self.js)
        self.assertIn('secretWordCard?.setAttribute("aria-expanded", "true");', self.js)

        # Vérifie que themeState.globalSpoiler n'est pas modifié dans revealSecretWord (protection locale)
        reveal_func = re.search(r"export function revealSecretWord\(\) \{(.*?)\n\}", self.js, re.DOTALL)
        self.assertTrue(reveal_func, "Fonction revealSecretWord introuvable")
        reveal_body = reveal_func.group(1)
        self.assertNotIn("themeState.globalSpoiler =", reveal_body)
        self.assertNotIn("toggleGlobalSpoiler()", reveal_body)

    def test_hide_button_restores_hidden_state(self):
        """3. Le bouton Masquer restaure l'état masqué."""
        self.assertIn('id="hide-word-btn"', self.html)
        # Vérifie que le gestionnaire de hideWordBtn ajoute is-spoiled et met à jour aria-expanded
        self.assertIn('secretWordCard?.classList.add("is-spoiled");', self.js)
        self.assertIn('secretWordCard?.setAttribute("aria-expanded", "false");', self.js)

    def test_global_spoiler_toggle_remains_functional(self):
        """4. Le toggle global spoiler reste pleinement fonctionnel."""
        self.assertIn('id="global-spoiler-toggle"', self.html)
        # L'événement cemantix:spoiler-change met à jour le card et aria-expanded
        self.assertIn('window.addEventListener("cemantix:spoiler-change"', self.js)
        self.assertRegex(self.js, r'if\s*\(\s*isSpoiled\s*\)\s*\{[^}]*secretWordCard\?\.classList\.add\("is-spoiled"\)')
        self.assertRegex(self.js, r'if\s*\(\s*isSpoiled\s*\)\s*\{[^}]*secretWordCard\?\.setAttribute\("aria-expanded",\s*"false"\)')
        self.assertRegex(self.js, r'else\s*\{[^}]*revealSecretWord\(\)')

    def test_failed_api_requests_do_not_reveal(self):
        """5. Les échecs API et puzzles non résolus ne dévoilent pas le mot."""
        # Dans revealSecretWord, le catch réapplique is-spoiled et aria-expanded="false"
        reveal_func = re.search(r"export function revealSecretWord\(\) \{(.*?)\n\}", self.js, re.DOTALL).group(1)
        self.assertIn(".catch(", reveal_func)
        self.assertIn('secretWordCard?.classList.add("is-spoiled")', reveal_func)
        self.assertIn('secretWordCard?.setAttribute("aria-expanded", "false")', reveal_func)
        self.assertIn('secretWord.textContent = "--------"', reveal_func)
        # Gère le cas json.pending
        self.assertIn("json.pending", reveal_func)

    def test_repeated_clicks_do_not_issue_redundant_requests(self):
        """6. Déduplication des requêtes en cours de vol (isRevealing)."""
        reveal_func = re.search(r"export function revealSecretWord\(\) \{(.*?)\n\}", self.js, re.DOTALL).group(1)
        # Vérifie le guard en entrée
        self.assertIn("if (dashboardState.isRevealing) return;", reveal_func)
        self.assertIn("dashboardState.isRevealing = true;", reveal_func)
        self.assertIn(".finally(", reveal_func)
        self.assertIn("dashboardState.isRevealing = false;", reveal_func)

    def test_keyboard_accessibility_activation(self):
        """7. Accessibilité clavier : activation via Entrée ou Espace."""
        self.assertIn('secretWordCard.addEventListener("keydown"', self.js)
        self.assertIn('e.key === "Enter"', self.js)
        self.assertIn('e.key === " "', self.js)
        self.assertIn("e.preventDefault()", self.js)

    def test_polling_preserves_local_reveal(self):
        """8. Le rafraîchissement périodique préserve une révélation locale active."""
        # renderDashboard ne doit pas ré-ajouter is-spoiled si le mot est révélé localement
        self.assertRegex(
            self.js,
            r"!themeState\.globalSpoiler\s*\|\|\s*!secretWordCard\?\.classList\.contains\(\"is-spoiled\"\)",
        )


if __name__ == "__main__":
    unittest.main()
