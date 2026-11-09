"""Harnais local : lance la chaine SEO sans les dependances lourdes (pas de reseau pip).

Usage :  py local/run_seo_tests.py

`src/__init__.py` importe le moteur, donc `numpy` / `requests` / `urllib3`. Le poste de
developpement n'a pas d'acces reseau pour installer `requirements.txt`, et la chaine SEO
(`src/services/seo.py`) n'utilise que la bibliotheque standard : ce harnais enregistre un
paquet `src.services` vide puis charge `seo.py` a son emplacement reel, ce qui rend les
`from src.services.seo import ...` des tests fonctionnels sans executer `src/__init__.py`.

La suite complete (moteur, API, base) reste couverte par le job `tests` de la CI.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load(name: str, relative_path: str):
    """Charge un module du depot sous son nom canonique, sans executer `src/__init__.py`."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    parent, _, leaf = name.rpartition(".")
    if parent:
        setattr(sys.modules[parent], leaf, module)
    spec.loader.exec_module(module)
    return module


def _install_seo_module() -> None:
    """Rend `src.services.seo` importable sans executer `src/__init__.py`.

    `src/__init__.py` importe le moteur (numpy, requests, urllib3) : on construit donc les
    paquets `src` et `src.services` a la main, puis on charge `config` et `seo`, qui n'ont
    que des dependances de la bibliotheque standard.

    La chaine SEO a ete decoupee en modules au jalon M4 : `seo.py` ne contient plus le
    code, il re-exporte depuis ses modules freres, qui dependent eux-memes de `gtm` et
    `layout_sync` (`seo_templates`, `seo_sitemap`, `seo_archives`, `seo_hubs`,
    `seo_agents`, `seo_google`, `seo_indexnow`). Un paquet factice n'explorant pas le
    disque, chaque module doit etre enregistre a la main, dans l'ordre des dependances —
    sinon `seo.py` echoue des l'import sur « No module named 'src.services.seo_templates' ».
    `requests` n'est requis par aucun d'eux : les modules de notification l'importent sous
    `try/except ImportError`, et `src.db` n'est jamais importe au niveau module.
    """
    for name in ("src", "src.services"):
        package = ModuleType(name)
        package.__path__ = []  # paquet factice : aucune exploration du disque
        sys.modules[name] = package
    sys.modules["src"].__path__ = [str(ROOT / "src")]
    _load("src.config", "src/config.py")
    for module in ("gtm", "layout_sync", "seo_templates", "seo_sitemap", "seo_archives",
                   "seo_hubs", "seo_agents", "seo_google", "seo_indexnow"):
        _load(f"src.services.{module}", f"src/services/{module}.py")
    _load("src.services.seo", "src/services/seo.py")


_install_seo_module()

NAMES = sys.argv[1:] or ["test_seo_archives", "test_seo_hubs", "test_docs_agent",
                         "test_agent_delivery"]
loaded = []
for name in NAMES:
    try:
        __import__(name)
        loaded.append(name)
    except Exception as exc:  # pragma: no cover - harnais uniquement
        import traceback

        print("SKIP", name, type(exc).__name__, exc)
        traceback.print_exc()

suite = unittest.defaultTestLoader.loadTestsFromNames(loaded)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("tests=", result.testsRun, "failures=", len(result.failures), "errors=", len(result.errors))
sys.exit(0 if result.wasSuccessful() else 1)
