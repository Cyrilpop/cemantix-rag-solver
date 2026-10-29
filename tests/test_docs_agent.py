"""Tests des documents de découverte pour agents IA (llms.txt, ARD).

Lancement :  python -m unittest discover -s tests -v

Ces fichiers sont écrits à la main pour l'essentiel, mais leur section « archive la
plus récente » est régénérée à chaque publication SEO. Les tests verrouillent trois
choses : la valeur injectée suit bien l'historique, la régénération est idempotente,
et les gabarits livrés contiennent bien les marqueurs attendus.
"""
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services.seo import (  # noqa: E402
    WEB_ROOT,
    _AGENT_DOCS_END,
    _AGENT_DOCS_START,
    refresh_agent_docs,
)

GABARITS = ("llms.txt", "agent-skills.md")


def _historique():
    return [
        {"date": "2026-11-09", "win": True, "puzzle": 1713},
        {"date": "2026-11-08", "win": True, "puzzle": 1712},
        {"date": "2026-11-07", "win": False, "puzzle": 1711},
    ]


class TestGabaritsInstruments(unittest.TestCase):
    def test_les_gabarits_portent_les_marqueurs(self):
        for nom in GABARITS:
            source = (WEB_ROOT / nom).read_text(encoding="utf-8")
            self.assertIn(_AGENT_DOCS_START, source, nom)
            self.assertIn(_AGENT_DOCS_END, source, nom)

    def test_aucune_date_ne_sonne_en_dur_hors_bloc_dynamique(self):
        """Dehors du bloc régénéré, une date figée se démoderait silencieusement."""
        import re
        for nom in GABARITS:
            source = (WEB_ROOT / nom).read_text(encoding="utf-8")
            statique = source.split(_AGENT_DOCS_START)[0] + source.split(_AGENT_DOCS_END)[1]
            self.assertFalse(
                re.search(r"puzzles/\d{4}-\d{2}-\d{2}", statique),
                f"{nom} : référence d'archive datée figée hors du bloc dynamique",
            )


class TestRafraichissementDocsAgent(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        for nom in GABARITS:
            shutil.copy(WEB_ROOT / nom, self.racine / nom)

    def tearDown(self):
        shutil.rmtree(self.racine, ignore_errors=True)

    def _bloc(self, nom):
        source = (self.racine / nom).read_text(encoding="utf-8")
        return source.split(_AGENT_DOCS_START)[1].split(_AGENT_DOCS_END)[0]

    def test_la_derniere_date_resolue_est_injectee(self):
        self.assertEqual(refresh_agent_docs(_historique(), web_root=self.racine), 2)
        for nom in GABARITS:
            bloc = self._bloc(nom)
            self.assertIn("2026-11-09", bloc, nom)
            self.assertIn("2026-11-08", bloc, nom)
            # Le puzzle perdu ne doit pas être présenté comme une archive dispo.
            self.assertNotIn("2026-11-07", bloc, nom)
            self.assertIn("2 puzzle(s) résolu(s)", bloc, nom)

    def test_regeneration_idempotente(self):
        refresh_agent_docs(_historique(), web_root=self.racine)
        for nom in GABARITS:
            premier = (self.racine / nom).read_text(encoding="utf-8")
            refresh_agent_docs(_historique(), web_root=self.racine)
            refresh_agent_docs(_historique(), web_root=self.racine)
            second = (self.racine / nom).read_text(encoding="utf-8")
            self.assertEqual(premier, second, nom)
            self.assertEqual(second.count(_AGENT_DOCS_START), 1, nom)

    def test_historique_vide_ninvente_aucune_date(self):
        refresh_agent_docs([], web_root=self.racine)
        for nom in GABARITS:
            bloc = self._bloc(nom)
            self.assertIn("aucune", bloc.lower(), nom)
            self.assertNotIn("/puzzles/20", bloc, nom)

    def test_historique_plus_recent_invalide_l_ancien(self):
        refresh_agent_docs([{"date": "2026-01-05", "win": True, "puzzle": 1}], web_root=self.racine)
        refresh_agent_docs(_historique(), web_root=self.racine)
        for nom in GABARITS:
            bloc = self._bloc(nom)
            self.assertIn("2026-11-09", bloc, nom)
            self.assertNotIn("2026-01-05", bloc, nom)

    def test_fichier_sans_marqueurs_laisse_intact(self):
        orphelin = self.racine / "sans-marqueur.txt"
        orphelin.write_text("# Contenu manuel\n", encoding="utf-8")
        avant = orphelin.read_text(encoding="utf-8")
        refresh_agent_docs(_historique(), web_root=self.racine)
        self.assertEqual(orphelin.read_text(encoding="utf-8"), avant)


if __name__ == "__main__":
    unittest.main(verbosity=2)
