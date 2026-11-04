"""Tests du module d'injection Google Tag Manager (src/services/gtm.py).

Garanties vérifiées :
1. Le gabarit déposé dans les fichiers ne contient QUE le placeholder Go template
   ``{{ env `GOOGLE_TAG_MANAGER_ID` }}`` — jamais l'ID réel (secret .env, jamais
   versionné).
2. L'injection est idempotente et se place avant ``</head>``.
3. La substitution à la livraison remplace le placeholder par l'ID réel.
4. Les pages statiques versionnées portent le bloc ; la console /panier-9x/ en
   est exclue ; le gabarit SEO généré l'intègre quand l'environnement fournit
   un ID (et s'en passe sinon).
"""
import os
import re
import unittest
from pathlib import Path
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services import gtm
from src.services.gtm import (
    GTM_END,
    GTM_ENV_VAR,
    GTM_PLACEHOLDER,
    GTM_START,
    STATIC_PAGES,
    harden_gtm_for_delivery,
    gtm_id_from_env,
    inject_gtm_block,
    render_gtm_snippet,
    resolve_gtm_for_delivery,
    sync_static_pages,
)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "volumes" / "web"

# ID factice de test : uniquement en mémoire, jamais écrit sur disque.
ID_TEST = "GTM-TEST1234"


class TestGtmSnippet(unittest.TestCase):
    def test_snippet_ne_contient_que_le_placeholder(self):
        self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", gtm.GTM_SNIPPET)
        self.assertNotIn("GTM-", gtm.GTM_SNIPPET.replace(GTM_PLACEHOLDER, ""))
        self.assertIn("window.dataLayer = window.dataLayer || [];", gtm.GTM_SNIPPET)
        self.assertIn("function gtag()", gtm.GTM_SNIPPET)
        self.assertIn("gtag('js', new Date());", gtm.GTM_SNIPPET)
        self.assertIn(GTM_START, gtm.GTM_SNIPPET)
        self.assertIn(GTM_END, gtm.GTM_SNIPPET)

    def test_render_gtm_snippet_avec_id_reel(self):
        bloc = render_gtm_snippet(ID_TEST)
        self.assertIn(f"gtm.js?id={ID_TEST}", bloc)
        self.assertNotIn(GTM_PLACEHOLDER, bloc)

    def test_render_gtm_snippet_sans_id_est_vide(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(gtm_id_from_env(), "")
            self.assertEqual(render_gtm_snippet(), "")

    def test_gtm_id_from_env_normalise(self):
        with mock.patch.dict(os.environ, {GTM_ENV_VAR: "  GTM-ABC123  "}):
            self.assertEqual(gtm_id_from_env(), "GTM-ABC123")


class TestInjectGtmBlock(unittest.TestCase):
    BASE_HTML = (
        "<!DOCTYPE html>\n<html lang=\"fr\">\n<head>\n  <meta charset=\"UTF-8\">\n"
        "  <title>Page</title>\n</head>\n<body>\n  <main>Contenu</main>\n</body>\n</html>\n"
    )

    def test_injection_avant_head_et_idempotente(self):
        une_fois = inject_gtm_block(self.BASE_HTML)
        self.assertIn(GTM_START, une_fois)
        self.assertLess(une_fois.index(GTM_START), une_fois.index("</head>"))
        deux_fois = inject_gtm_block(une_fois)
        self.assertEqual(une_fois, deux_fois, "L'injection doit être idempotente")
        self.assertEqual(deux_fois.count(GTM_START), 1)

    def test_injection_remplace_un_bloc_existant(self):
        obsolete = self.BASE_HTML.replace(
            "</head>",
            "  <!-- GTM:START -->\n  <script>ancien()</script>\n  <!-- GTM:END -->\n</head>",
        )
        injecte = inject_gtm_block(obsolete)
        self.assertEqual(injecte.count(GTM_START), 1)
        self.assertNotIn("ancien()", injecte)
        self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", injecte)

    def test_injection_sans_head_leve_une_erreur(self):
        with self.assertRaises(ValueError):
            inject_gtm_block("<html><body>sans head</body></html>")



class TestDeliveryResolution(unittest.TestCase):
    def test_substitution_placeholder(self):
        page = inject_gtm_block("<html><head><title>t</title></head><body></body></html>")
        livree = resolve_gtm_for_delivery(page, ID_TEST)
        self.assertIn(f"gtm.js?id={ID_TEST}", livree)
        self.assertNotIn(GTM_PLACEHOLDER, livree)

    def test_pas_did_ne_change_rien(self):
        # « pas d'ID » doit se lire des deux façons : ID explicitement vide, et
        # None = « relire l'environnement » dans un environnement qui n'en fournit
        # pas. Sans patch, ce test dépendrait de l'absence réelle de
        # GOOGLE_TAG_MANAGER_ID dans le shell : il passait en CI par construction
        # et échouait sur tout poste où le .env est exporté.
        page = inject_gtm_block("<html><head><title>t</title></head><body></body></html>")
        self.assertEqual(resolve_gtm_for_delivery(page, ""), page)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_gtm_for_delivery(page, None), page)

    def test_none_relit_lenvironnement(self):
        # Symétrie du cas précédent : None ne veut pas dire « aucun ID » mais
        # « le lire dans l'environnement ». Un shell qui exporte le .env doit donc
        # bien donner lieu à la substitution.
        page = inject_gtm_block("<html><head><title>t</title></head><body></body></html>")
        with mock.patch.dict(os.environ, {GTM_ENV_VAR: ID_TEST}):
            livree = resolve_gtm_for_delivery(page, None)
        self.assertIn(f"gtm.js?id={ID_TEST}", livree)
        self.assertNotIn(GTM_PLACEHOLDER, livree)

    def test_page_sans_bloc_nest_pas_touchee(self):
        page = "<html><head><title>t</title></head><body></body></html>"
        self.assertEqual(resolve_gtm_for_delivery(page, ID_TEST), page)

    def test_harden_repare_un_jeton_altere(self):
        # Le jeton placeholder a été corrompu dans le fichier servi (proxy, éditeur).
        page = (
            "<html><head><!-- GTM:START -->"
            '<script async src="https://www.googletagmanager.com/gtm.js?id="></script>'
            "<!-- GTM:END --></head><body></body></html>"
        )
        durcie = harden_gtm_for_delivery(page, ID_TEST)
        self.assertIn(f"gtm.js?id={ID_TEST}", durcie)

    def test_harden_rejette_un_contenu_injecte_dans_le_jeton(self):
        # Un caractère altérant l'attribut src ne peut pas s'échapper du bloc :
        # tout ce qui suit `id=` jusqu'au délimiteur est remplacé par l'ID propre.
        page = (
            "<html><head><!-- GTM:START -->"
            '<script async src="https://www.googletagmanager.com/gtm.js?id=x onerror=alert(1)">'
            "</script><!-- GTM:END --></head><body></body></html>"
        )
        durcie = harden_gtm_for_delivery(page, ID_TEST)
        self.assertIn(f"gtm.js?id={ID_TEST}\">", durcie)
        self.assertNotIn("onerror", durcie)


class TestStaticPages(unittest.TestCase):
    def test_sync_static_pages_injecte_partout(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            racine = Path(tmpdir)
            for rel in STATIC_PAGES:
                cible = racine / rel
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_text(
                    "<html><head><title>x</title></head><body></body></html>",
                    encoding="utf-8",
                )
            results = sync_static_pages(web_root=racine)
            self.assertTrue(all(results.values()), results)
            for rel in STATIC_PAGES:
                html = (racine / rel).read_text(encoding="utf-8")
                self.assertIn(GTM_START, html)
                self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", html)

    def test_pages_statiques_versionnees_portent_le_placeholder(self):
        for rel in STATIC_PAGES:
            html = (WEB_DIR / rel).read_text(encoding="utf-8")
            self.assertIn(GTM_START, html, f"Bloc GTM manquant dans {rel}")
            self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", html, f"Placeholder GTM manquant dans {rel}")

    def test_console_admin_exclue_du_suivi(self):
        html = (WEB_DIR / "panier-9x" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("googletagmanager", html)
        self.assertNotIn(GTM_START, html)
        self.assertNotIn("panier-9x", STATIC_PAGES)

    def test_aucun_id_reel_gtm_versionne(self):
        # Seules les pages statiques versionnées sont auditées : les pages
        # générées sur disque (archives, hubs) portent l'ID résolu par le
        # conteneur au moment de la publication et sont régénérées en continu.
        gtm_real_re = re.compile(r"googletagmanager\.com/gtm\.js\?id=GTM-[A-Z0-9]+")
        for rel in STATIC_PAGES:
            html_file = WEB_DIR / rel
            self.assertIsNone(
                gtm_real_re.search(html_file.read_text(encoding="utf-8")),
                f"FUITE : ID GTM réel commité dans {html_file}",
            )


class TestGtmDansGabaritGenere(unittest.TestCase):
    def _render(self, **kwargs):
        from src.services.seo_templates import render_page

        params = dict(
            title="Test GTM",
            description="Description de test pour le gabarit SEO généré.",
            canonical="https://cemantix.cyril-randon.fr/puzzles/",
            json_ld="",
            body="<p>Contenu</p>",
            breadcrumbs="",
            resolve=lambda p: f"../{p}",
        )
        params.update(kwargs)
        return render_page(**params)

    def test_render_page_porte_toujours_le_placeholder(self):
        # Le gabarit écrit sur disque est indépendant de l'environnement : il
        # porte le jeton, jamais l'ID (la substitution a lieu à la livraison).
        html = self._render()
        self.assertIn(GTM_START, html)
        self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", html)
        self.assertLess(html.index(GTM_START), html.index("</head>"))

    def test_render_page_ne_fuit_jamais_l_id_environne(self):
        with mock.patch.dict(os.environ, {GTM_ENV_VAR: ID_TEST}):
            html = self._render()
        self.assertNotIn(ID_TEST, html)
        self.assertIn(f"gtm.js?id={GTM_PLACEHOLDER}", html)

    def test_render_page_est_identique_avec_ou_sans_environnement(self):
        avec = self._render()
        with mock.patch.dict(os.environ, {GTM_ENV_VAR: ID_TEST}):
            sans = self._render()
        self.assertEqual(avec, sans, "Le rendu doit être déterministe hors environnement")


if __name__ == "__main__":
    unittest.main(verbosity=2)