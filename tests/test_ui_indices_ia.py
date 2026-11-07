"""
Tests Unitaires — Jalon M13 (Affichage des Indices IA avec Double Commutateur Dynamique)
========================================================================================
Valide le rendu et le comportement fonctionnel du composant d'indices sur la page
hub « mot du jour » (/mot-du-jour/) :
1. Présence et états par défaut des commutateurs (IA actif, Phrase active).
2. Ordre strict des indices IA (#1 = le plus éloigné / niveau 1).
3. Masquage anti-spoiler strict par défaut (aucun indice en clair).
4. Repli gracieux sur les indices RAG lorsque la date n'a pas d'indices IA en base.
5. Accessibilité ARIA complète et attributs sémantiques.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

tests_dir = Path(__file__).resolve().parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

import _context  # noqa: F401
from src.services.seo_hubs import build_mot_du_jour_page
from src.services.seo_templates import render_hints_component

SAMPLE_ENTRY = {
    "date": "2026-11-06",
    "puzzle": 1710,
    "word": "boussole",
    "win": True,
    "tries": 12,
    "duration_seconds": 15.4,
    "top_guesses": [
        {"word": "boussole", "score": 100.0, "permille": 1000},
        {"word": "aimant", "score": 45.2, "permille": 950},
        {"word": "aiguille", "score": 41.0, "permille": 880},
        {"word": "nord", "score": 38.5, "permille": 790},
    ],
}

SAMPLE_AI_HINTS = [
    {
        "puzzle_date": "2026-11-06",
        "hint_level": 1,
        "weight": 0.33,
        "hint_word": "navigation",
        "hint_phrase": "Permet d'explorer sans se perdre sur les mers.",
        "model": "gemini-3.8-flash",
        "is_revealed": False,
    },
    {
        "puzzle_date": "2026-11-06",
        "hint_level": 2,
        "weight": 0.66,
        "hint_word": "orientation",
        "hint_phrase": "Indique toujours la même direction cardinale.",
        "model": "gemini-3.8-flash",
        "is_revealed": False,
    },
    {
        "puzzle_date": "2026-11-06",
        "hint_level": 3,
        "weight": 1.00,
        "hint_word": "aimant",
        "hint_phrase": "Son aiguille magnétique réagit au pôle terrestre.",
        "model": "gemini-3.8-flash",
        "is_revealed": False,
    },
]


class TestUiIndicesIa(unittest.TestCase):
    """Vérifications fonctionnelles du composant d'indices IA et du double commutateur."""

    def test_default_switches_states(self):
        """Vérifie les commutateurs et leurs états par défaut (IA actif, Phrase active)."""
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=SAMPLE_AI_HINTS)

        # Commutateur 1 : Source d'indices (IA active par défaut)
        self.assertIn('id="tab-hints-ai"', html)
        self.assertIn('id="tab-hints-rag"', html)
        self.assertIn('class="segment-btn active" id="tab-hints-ai"', html)
        self.assertIn('aria-selected="true" aria-controls="panel-hints-ai"', html)
        self.assertIn('id="tab-hints-rag" role="tab" aria-selected="false"', html)

        # Panneaux associés
        self.assertIn('id="panel-hints-ai" role="tabpanel"', html)
        self.assertIn('class="hints-panel active" id="panel-hints-ai"', html)
        self.assertIn('id="panel-hints-rag" role="tabpanel" aria-labelledby="tab-hints-rag" hidden', html)

        # Commutateur 2 : Format d'indice IA (Phrase active par défaut)
        self.assertIn('id="hints-ai-format"', html)
        self.assertIn('id="btn-format-phrase"', html)
        self.assertIn('id="btn-format-word"', html)
        self.assertIn('class="segment-btn active" id="btn-format-phrase"', html)
        self.assertIn('role="radio" aria-checked="true"', html)
        self.assertIn('id="btn-format-word" role="radio" aria-checked="false"', html)

        # Vues par défaut dans les cartes : vue phrase active, vue mot masquée
        self.assertIn('class="hint-view-phrase active"', html)
        self.assertIn('class="hint-view-word"', html)
        self.assertNotIn('class="hint-view-word active"', html)

    def test_strict_order_of_ai_hints(self):
        """Vérifie l'ordre strict des indices IA (#1 = le plus éloigné / niveau 1)."""
        # On passe les indices dans le désordre pour vérifier le tri systématique
        shuffled_hints = [SAMPLE_AI_HINTS[2], SAMPLE_AI_HINTS[0], SAMPLE_AI_HINTS[1]]
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=shuffled_hints)

        pos_1 = html.find('data-level="1"')
        pos_2 = html.find('data-level="2"')
        pos_3 = html.find('data-level="3"')

        self.assertNotEqual(pos_1, -1, "Carte d'indice #1 absente")
        self.assertNotEqual(pos_2, -1, "Carte d'indice #2 absente")
        self.assertNotEqual(pos_3, -1, "Carte d'indice #3 absente")

        # #1 doit précéder #2 qui doit précéder #3
        self.assertLess(pos_1, pos_2, "L'indice #1 doit apparaître avant l'indice #2")
        self.assertLess(pos_2, pos_3, "L'indice #2 doit apparaître avant l'indice #3")

        # Métadonnées et graduations thermiques
        self.assertIn("Indice #1 · Éloigné", html)
        self.assertIn("Similarité ~20%", html)
        self.assertIn("tier-cold", html)

        self.assertIn("Indice #2 · Intermédiaire", html)
        self.assertIn("Similarité ~45%", html)
        self.assertIn("tier-warm", html)

        self.assertIn("Indice #3 · Proche", html)
        self.assertIn("Zone brûlante", html)
        self.assertIn("tier-fire", html)

        # Contenus associés
        self.assertIn("Permet d&#x27;explorer sans se perdre sur les mers.", html)
        self.assertIn("Navigation", html)
        self.assertIn("Indique toujours la même direction cardinale.", html)
        self.assertIn("Orientation", html)
        self.assertIn("Son aiguille magnétique réagit au pôle terrestre.", html)
        self.assertIn("Aimant", html)

    def test_anti_spoiler_masking_by_default(self):
        """Vérifie la politique anti-spoiler : tous les indices masqués/floutés par défaut."""
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=SAMPLE_AI_HINTS)

        # Toutes les zones d'indices sont des spoiler-box non révélées dans le DOM
        self.assertEqual(html.count('class="ai-hint-content spoiler-box"'), 3)
        self.assertNotIn("spoiler-box revealed", html)

        # Attribut data-spoiler sur tous les textes
        self.assertEqual(html.count('data-spoiler="true"'), 6)  # 3 phrases + 3 mots

        # Présence des boutons de démasquage explicite
        self.assertIn('aria-label="Révéler l\'indice 1"', html)
        self.assertIn('aria-label="Révéler l\'indice 2"', html)
        self.assertIn('aria-label="Révéler l\'indice 3"', html)
        self.assertEqual(html.count("👁️ Révéler l'indice"), 3)

    def test_fallback_to_rag_when_no_ai_hints(self):
        """Vérifie le repli gracieux automatique sur les indices RAG si aucun indice IA."""
        # ai_hints vide
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=[])

        # Aucun commutateur IA présent
        self.assertNotIn('id="tab-hints-ai"', html)
        self.assertNotIn('id="hints-ai-format"', html)
        self.assertNotIn('class="ai-hints-grid"', html)

        # Le tableau des indices du solveur RAG s'affiche directement
        self.assertIn("🌡️ Les 3 indices du mot du jour", html)
        self.assertIn("Aimant", html)
        self.assertIn("Aiguille", html)
        self.assertIn("Nord", html)
        self.assertIn("950 ‰", html)

    def test_database_get_daily_ai_hints_integration(self):
        """Vérifie que build_mot_du_jour_page interroge get_daily_ai_hints si non fourni."""
        with mock.patch("src.services.seo_hubs.get_daily_ai_hints", return_value=SAMPLE_AI_HINTS) as mock_get:
            html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY])
            mock_get.assert_called_once_with("2026-11-06")
            self.assertIn('id="hints-hub"', html)
            self.assertIn('id="tab-hints-ai"', html)

    def test_render_hints_component_empty(self):
        """Vérifie que render_hints_component renvoie une chaîne vide sans données."""
        self.assertEqual(render_hints_component(guesses=[], ai_hints=[]), "")
        self.assertEqual(render_hints_component(guesses=[], ai_hints=None), "")

    def test_aria_accessibility_attributes(self):
        """Vérifie la conformité des attributs ARIA pour l'accessibilité écran/clavier."""
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=SAMPLE_AI_HINTS)

        # Tablist et tabs
        self.assertIn('role="tablist" aria-label="Source des indices"', html)
        self.assertIn('role="tab"', html)
        self.assertIn('role="tabpanel"', html)

        # Radiogroup et radios
        self.assertIn('role="radiogroup" aria-label="Format des indices IA"', html)
        self.assertIn('role="radio"', html)

    def test_rag_clues_order_and_masking(self):
        """Vérifie que les indices RAG commencent par les plus froids et sont masqués par défaut."""
        # SAMPLE_ENTRY a :
        # aimant: score=42.5, permille=950
        # aiguille: score=38.2, permille=910
        # nord: score=25.0, permille=780
        html = build_mot_du_jour_page(SAMPLE_ENTRY, [SAMPLE_ENTRY], ai_hints=None)

        # Vérification masquage anti-spoiler sur les mots du tableau RAG
        self.assertIn('class="word-spoiler is-hidden"', html)
        self.assertIn('data-action="spoiler"', html)

        # Ordre croissant (du plus froid au plus chaud) : Nord (25.0) avant Aiguille (38.2) avant Aimant (42.5)
        pos_nord = html.find("Nord")
        pos_aiguille = html.find("Aiguille")
        pos_aimant = html.find("Aimant")
        self.assertNotEqual(pos_nord, -1)
        self.assertNotEqual(pos_aiguille, -1)
        self.assertNotEqual(pos_aimant, -1)
        self.assertLess(pos_nord, pos_aiguille, "Le mot le plus froid (Nord) doit apparaître avant Aiguille")
        self.assertLess(pos_aiguille, pos_aimant, "Aiguille doit apparaître avant le plus chaud (Aimant)")


    def test_build_web_data_injects_ai_hints(self):
        """Vérifie que build_web_data injecte proprement les indices IA dans current pour le dashboard."""
        from src.services.web import build_web_data
        with mock.patch("src.db.get_daily_ai_hints", return_value=SAMPLE_AI_HINTS):
            data = build_web_data(history=[SAMPLE_ENTRY], heartbeat_path=None)
            self.assertIsNotNone(data["current"])
            self.assertIn("ai_hints", data["current"])
            self.assertEqual(len(data["current"]["ai_hints"]), 3)
            self.assertEqual(data["current"]["ai_hints"][0]["hint_word"], "navigation")
            self.assertEqual(data["current"]["ai_hints"][0]["hint_level"], 1)


if __name__ == "__main__":
    unittest.main()
