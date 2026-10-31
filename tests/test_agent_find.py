"""Tests de l'outil agent_find.py (M5).

Vérifie la découverte de symboles Python, JS, HTML et la protection de contexte.
"""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _context  # noqa: F401
import tools.agent_find as agent_find

ROOT = Path(__file__).resolve().parent.parent


class TestAgentFind(unittest.TestCase):
    def test_find_python_symbols(self):
        matches = agent_find.find_python_symbols("estimate_secret", ROOT / "src")
        self.assertTrue(len(matches) > 0)
        file_paths = [m[0] for m in matches]
        self.assertTrue(any("ranking.py" in p for p in file_paths))

    def test_find_js_symbols(self):
        matches = agent_find.find_js_symbols("escapeHtml", ROOT / "volumes" / "web" / "js")
        self.assertTrue(len(matches) > 0)
        file_paths = [m[0] for m in matches]
        self.assertTrue(any("utils.js" in p for p in file_paths))

    def test_find_html_symbols(self):
        matches = agent_find.find_html_symbols("secret-word", ROOT / "volumes" / "web")
        self.assertTrue(len(matches) > 0)
        file_paths = [m[0] for m in matches]
        self.assertTrue(any("index.html" in p for p in file_paths))

    def test_file_summary_html_detects_critical_css(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            agent_find.file_summary("volumes/web/index.html")
        out = buf.getvalue()
        self.assertIn("CSS critique généré", out)
        self.assertIn("tokens", out)
        self.assertIn("Repères structurels", out)

    def test_safe_read_html_masks_critical_css(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            agent_find.safe_read_html("volumes/web/index.html", 40, 60)
        out = buf.getvalue()
        self.assertIn("critical-css", out)
        self.assertNotIn(":root{--font-main:", out)
        self.assertIn("masqué", out)


if __name__ == "__main__":
    unittest.main()
