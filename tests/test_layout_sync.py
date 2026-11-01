"""Tests du module de synchronisation modulaire du layout (Header & Nav-tabs)."""
import tempfile
import unittest
from pathlib import Path

import _context  # noqa: F401

from src.services.layout_sync import (
    HEADER_END,
    HEADER_START,
    NAV_END,
    NAV_START,
    render_header,
    render_nav_tabs,
    sync_html_file,
)


class TestLayoutSync(unittest.TestCase):
    def test_render_header_desktop_and_depth(self):
        h = render_header("")
        self.assertIn('<img src="icons/favicon.png"', h)
        self.assertIn('class="brand-icon"', h)
        self.assertIn('Cémantix Solver', h)
        self.assertIn('id="theme-toggle"', h)
        self.assertIn('id="daemon-badge"', h)
        self.assertIn('id="global-spoiler-toggle"', h)

        h_sub = render_header("../")
        self.assertIn('<img src="../icons/favicon.png"', h_sub)

    def test_render_nav_tabs_active_states(self):
        tabs_play = render_nav_tabs("../", "play")
        self.assertIn('id="tab-play" class="nav-tab active"', tabs_play)
        self.assertIn('href="./"', tabs_play)  # active page points to ./
        self.assertIn('id="tab-dashboard" class="nav-tab"', tabs_play)
        self.assertIn('href="../"', tabs_play)
        self.assertIn('id="tab-battle" class="nav-tab"', tabs_play)
        self.assertIn('href="../battle/"', tabs_play)
        self.assertIn('<span class="tab-badge">Versus IA</span>', tabs_play)

        tabs_dash = render_nav_tabs("", "dashboard")
        self.assertIn('id="tab-dashboard" class="nav-tab active"', tabs_dash)
        self.assertIn('href="./"', tabs_dash)
        self.assertIn('id="tab-play" class="nav-tab"', tabs_dash)
        self.assertIn('href="play/"', tabs_dash)

    def test_sync_html_file_injects_and_wraps_markers(self):
        initial_html = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
  <header class="app-header">Old Header</header>
  <main class="main-content">
    <nav class="nav-tabs">Old Tabs</nav>
    <div>Page Content</div>
  </main>
</body>
</html>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / "test.html"
            tmp_file.write_text(initial_html, encoding="utf-8")

            # Première synchro : doit injecter les délimiteurs
            ok = sync_html_file(tmp_file, "../", "play")
            self.assertTrue(ok)

            synced = tmp_file.read_text(encoding="utf-8")
            self.assertIn(HEADER_START, synced)
            self.assertIn(HEADER_END, synced)
            self.assertIn(NAV_START, synced)
            self.assertIn(NAV_END, synced)
            self.assertIn('id="tab-play" class="nav-tab active"', synced)
            self.assertIn("<div>Page Content</div>", synced)  # contenu préservé !

            # Deuxième synchro : idempotente
            ok2 = sync_html_file(tmp_file, "../", "play")
            self.assertTrue(ok2)
            self.assertEqual(synced, tmp_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

