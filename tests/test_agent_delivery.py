"""Tests du contrat de livraison des ressources lues par les agents IA (`SEO-22` à `SEO-25`).

Lancement :  python -m unittest discover -s tests -v

Un audit agentique (Google Lighthouse « Navigation agentique », validateur
`ard-schema`, auditeurs llms.txt tiers) ne lit jamais le dépôt : il lit ce que le
serveur répond. Trois familles de pannes lui sont donc fatales, et aucune n'est
visible depuis les tests qui vérifient le contenu des fichiers :

1. `robots.txt` interdit la lecture du manifeste -> le robot ne peut pas le
   valider et l'annonce comme « schéma non valide » ;
2. le proxy replie une URL inconnue sur `/index.html` (soft 404) -> le robot
   reçoit du HTML : « Unexpected token '<', "<!DOCTYPE " » pour un JSON,
   « aucun en-tête H1, aucun lien » pour un llms.txt ;
3. une ressource annoncée n'existe nulle part dans le webroot.

Ce module verrouille les trois, sans dépendance tierce : il ne lit que des
fichiers, et réutilise les gardes de `tools/check_seo.py` pour ne pas dupliquer
la règle.
"""
import unittest
from pathlib import Path

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

try:
    import tools.check_seo as check_seo
except ModuleNotFoundError:  # pragma: no cover — conteneur sans le dossier tools
    check_seo = None

RACINE = Path(__file__).resolve().parent.parent
README = RACINE / "README.md"
NGINX_LOCAL = RACINE / "local" / "nginx" / "cemantix.local.conf"
DOCS_AGENTS = ("llms.txt", "llms.md", "agent-skills.md")


@unittest.skipIf(check_seo is None, "tools/check_seo.py non importable dans ce conteneur")
class TestRobotsLaisseLireLesAgents(unittest.TestCase):
    """`SEO-22` : un manifeste de découverte doit rester crawlable."""

    def test_aucune_ressource_agent_n_est_interdite(self):
        robots = check_seo.ROBOTS_TXT.read_text(encoding="utf-8")
        for ressource in check_seo.RESSOURCES_AGENTS:
            self.assertIsNone(
                check_seo._robots_interdit(robots, ressource),
                f"robots.txt interdit la lecture de {ressource}",
            )

    def test_le_garde_detecte_un_disallow_well_known(self):
        """Le contrôle ne doit pas s'endormir si le Disallow revient (SEO-22)."""
        robots = (check_seo.ROBOTS_TXT.read_text(encoding="utf-8")
                  + "\nDisallow: /.well-known/\n")
        self.assertEqual(
            check_seo._robots_interdit(robots, "/.well-known/ai-catalog.json"),
            "/.well-known/",
        )

    def test_le_garde_ne_bloque_rien_sans_motif_concernant(self):
        robots = "User-agent: *\nDisallow: /api/\nDisallow: /*?reveal=\n"
        for ressource in check_seo.RESSOURCES_AGENTS:
            self.assertIsNone(check_seo._robots_interdit(robots, ressource), ressource)


@unittest.skipIf(check_seo is None, "tools/check_seo.py non importable dans ce conteneur")
class TestRessourcesAnnounceesLivrables(unittest.TestCase):
    """`SEO-24` : chaque URL annoncée aux agents doit correspondre à une ressource."""

    def test_aucun_lien_dans_la_documentation_des_agents(self):
        self.assertEqual(check_seo.check_decouvrabilite_agents(), [])

    def test_une_url_inconnue_du_webroot_est_un_lien_mort(self):
        self.assertFalse(check_seo._fichier_livrable("/page-qui-n-existe-pas/"))
        self.assertFalse(check_seo._fichier_livrable("/llms-absent.txt"))

    def test_pages_generees_et_api_ne_sont_pas_tenues_en_defaut(self):
        """Elles n'existent pas dans le dépôt : un dépôt cloné ne doit pas échouer."""
        for chemin in ("/", "/sitemap.xml", "/mot-du-jour/", "/methode/",
                       "/puzzles/2026-01-01/", "/api/daily"):
            self.assertTrue(check_seo._fichier_livrable(chemin), chemin)

    def test_les_hubs_sont_declares_partout(self):
        """`SEO-25` : `/mot-du-jour/` et `/methode/` doivent être découvrables
        depuis chacun des documents d'agents, pas seulement depuis `llms.txt`."""
        for nom in DOCS_AGENTS:
            texte = (check_seo.WEB_ROOT / nom).read_text(encoding="utf-8")
            self.assertIn("/mot-du-jour/", texte, nom)
            self.assertIn("/methode/", texte, nom)


class TestContratDeLivraisonProxy(unittest.TestCase):
    """`SEO-23` : le proxy ne doit jamais répondre la page d'accueil à un robot."""

    def test_reference_caddy_ne_replie_plus_sur_index_html(self):
        readme = README.read_text(encoding="utf-8")
        self.assertNotIn(
            "try_files {path} {path}/index.html {path}/ /index.html", readme,
            "repli soft 404 : un manifeste manquant serait livré en HTML",
        )
        self.assertIn("try_files {path} {path}/index.html {path}/ =404", readme)

    def test_reference_caddy_declare_le_bloc_des_ressources_agents(self):
        readme = README.read_text(encoding="utf-8")
        for attente in (
            "@agents_json path /.well-known/ai-catalog.json",
            '@agents_txt path /llms.txt',
            'handle @agents_json {',
            'header Content-Type "application/json; charset=utf-8"',
            'header Content-Type "text/plain; charset=utf-8"',
            'header Content-Type "text/markdown; charset=utf-8"',
        ):
            self.assertIn(attente, readme)

    def test_nginx_local_applique_le_meme_contrat(self):
        """Le miroir de test doit rester fidèle à la référence de production."""
        nginx = NGINX_LOCAL.read_text(encoding="utf-8")
        self.assertIn("try_files $uri $uri/index.html $uri/ =404", nginx)
        self.assertIn("location = /llms.txt {", nginx)
        self.assertIn("default_type application/json;", nginx)
        self.assertIn("default_type text/markdown;", nginx)


if __name__ == "__main__":
    unittest.main(verbosity=2)
