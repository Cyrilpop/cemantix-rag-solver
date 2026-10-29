"""Tests du contrôle d'intégrité des fichiers téléchargés (SEC-11).

Lancement :  python -m unittest discover -s tests -v
"""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.engine import vocab  # noqa: E402


class TestVerificationW2V(unittest.TestCase):
    """Le seuil de taille est rabaissé pour que les tests restent rapides."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cemantix_w2v_"))
        self.path = self.dir / "modele.bin"
        self._orig = vocab.MIN_W2V_BYTES
        vocab.MIN_W2V_BYTES = 64
        os.environ.pop("W2V_SHA256", None)

    def tearDown(self):
        vocab.MIN_W2V_BYTES = self._orig
        os.environ.pop("W2V_SHA256", None)

    def _write(self, content: bytes) -> Path:
        self.path.write_bytes(content)
        return self.path

    def test_en_tete_valide_accepte(self):
        self._write(b"12345 500\n" + b"x" * 200)
        self.assertIsNone(vocab.verify_w2v_file(self.path))

    def test_fichier_absent_refuse(self):
        with self.assertRaises(ValueError) as ref:
            vocab.verify_w2v_file(self.dir / "inexistant.bin")
        self.assertIn("absent", str(ref.exception))

    def test_fichier_tronque_refuse(self):
        self._write(b"12345 500\n")  # trop court devant MIN_W2V_BYTES
        with self.assertRaises(ValueError) as ref:
            vocab.verify_w2v_file(self.path)
        self.assertIn("taille suspecte", str(ref.exception))

    def test_page_html_refuse(self):
        """Le proxy d'entreprise renvoie 200 OK avec du HTML : rien ne doit passer."""
        self._write(b"<!DOCTYPE html>\n<html><body>Site bloque</body></html>" + b" " * 200)
        with self.assertRaises(ValueError) as ref:
            vocab.verify_w2v_file(self.path)
        self.assertIn("HTML", str(ref.exception))

    def test_en_tete_invalide_refuse(self):
        self._write(b"ceci n'est pas un en-tete\n" + b"x" * 200)
        with self.assertRaises(ValueError) as ref:
            vocab.verify_w2v_file(self.path)
        self.assertIn("en-tête word2vec invalide", str(ref.exception))

    def test_en_tete_incoherent_refuse(self):
        self._write(b"7 3\n" + b"x" * 200)  # 7 mots / 3 dimensions : improbable
        with self.assertRaises(ValueError) as ref:
            vocab.verify_w2v_file(self.path)
        self.assertIn("incohérent", str(ref.exception))

    def test_empreinte_correcte_acceptee(self):
        content = b"12345 500\n" + b"y" * 200
        self._write(content)
        empreinte = hashlib.sha256(content).hexdigest()
        with mock.patch.dict(os.environ, {"W2V_SHA256": empreinte}, clear=False):
            self.assertIsNone(vocab.verify_w2v_file(self.path))

    def test_empreinte_erronee_refusee(self):
        self._write(b"12345 500\n" + b"z" * 200)
        with mock.patch.dict(os.environ, {"W2V_SHA256": "0" * 64}, clear=False):
            with self.assertRaises(ValueError) as ref:
                vocab.verify_w2v_file(self.path)
        self.assertIn("SHA-256 inattendue", str(ref.exception))

    def test_empreinte_non_configuree_non_bloquante(self):
        """Le SHA-256 reste optionnel : un déploiement existant ne casse pas."""
        self._write(b"12345 500\n" + b"w" * 200)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("W2V_SHA256", None)
            self.assertIsNone(vocab.verify_w2v_file(self.path))


class TestDetectionHtml(unittest.TestCase):
    def test_variants_html(self):
        for le in (b"<!DOCTYPE html>", b"<HTML>", b"  <html lang=fr>", b"<html\n"):
            self.assertTrue(vocab._looks_like_html(le), le)

    def test_binaire_non_signale_comme_html(self):
        self.assertFalse(vocab._looks_like_html(b"12345 500\n\x00\x01\x02"))
        self.assertFalse(vocab._looks_like_html(b"maison 0.1 0.2"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
