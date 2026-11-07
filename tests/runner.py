"""Runner de tests unitaire personnalisé pour Cémantix Solver.

Offre un affichage structuré par module de test avec un alignement strict en colonnes
et un résumé d'exécution clair, lisible et synthétique à la fin de la suite de tests.
"""
import time
import unittest
from typing import Any, Dict, Optional

_ORIGINAL_RUN = unittest.TextTestRunner.run


class CemantixTestResult(unittest.TextTestResult):
    """Collecteur de résultats avec alignement parfait par module."""

    def __init__(self, stream: Any, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        # Désactive les points unittest natifs non groupés
        self.dots = False
        self.current_module: Optional[str] = None
        self.module_start_time: float = time.time()
        self.modules_stats: Dict[str, Dict[str, int]] = {}
        self.current_stats: Optional[Dict[str, int]] = None

    def startTest(self, test: unittest.TestCase) -> None:
        raw_mod = test.__class__.__module__
        mod = raw_mod.split(".")[-1]
        now = time.time()

        if mod != self.current_module:
            self._close_current_module()
            self.current_module = mod
            self.module_start_time = now
            self.current_stats = {"pass": 0, "skip": 0, "fail": 0, "error": 0}
            self.modules_stats[mod] = self.current_stats

        super().startTest(test)

    def _close_current_module(self) -> None:
        if self.current_module and self.current_stats:
            duration = time.time() - (self.module_start_time or time.time())
            s = self.current_stats
            details = []
            if s["pass"]:
                details.append(f"{s['pass']:>2} passé" if s["pass"] == 1 else f"{s['pass']:>2} passés")
            if s["skip"]:
                details.append(f"{s['skip']:>2} ignoré" if s["skip"] == 1 else f"{s['skip']:>2} ignorés")
            if s["fail"]:
                details.append(f"{s['fail']:>2} échec" if s["fail"] == 1 else f"{s['fail']:>2} échecs")
            if s["error"]:
                details.append(f"{s['error']:>2} erreur" if s["error"] == 1 else f"{s['error']:>2} erreurs")

            summary_str = ", ".join(details) if details else " 0 test"
            status_symbol = "✓" if (s["fail"] == 0 and s["error"] == 0) else "❌"
            display_name = self.current_module if self.current_module.startswith("test_") else f"test_{self.current_module}"
            self.stream.writeln(f"  📦 {display_name:<34} {status_symbol}  {summary_str:<26} ({duration:>5.2f}s)")
            self.stream.flush()

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        if self.current_stats:
            self.current_stats["pass"] += 1

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        if self.current_stats:
            self.current_stats["skip"] += 1

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        if self.current_stats:
            self.current_stats["fail"] += 1

    def addError(self, test: unittest.TestCase, err: Any) -> None:
        super().addError(test, err)
        if self.current_stats:
            self.current_stats["error"] += 1

    def stopTestRun(self) -> None:
        self._close_current_module()
        super().stopTestRun()


def cemantix_run(self: unittest.TextTestRunner, test: unittest.TestSuite) -> unittest.TestResult:
    """Méthode run() enrichie pour unittest.TextTestRunner."""
    self.stream.writeln("=" * 76)
    self.stream.writeln("🧪  SUITE DE TESTS CÉMANTIX (Exécution Docker)")
    self.stream.writeln("=" * 76)
    self.stream.flush()

    start_time = time.time()
    result = _ORIGINAL_RUN(self, test)
    total_time = time.time() - start_time

    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)

    nb_mods = len(getattr(result, "modules_stats", {}))
    mod_lbl = f"{nb_mods} module" if nb_mods <= 1 else f"{nb_mods} modules"
    test_lbl = f"{result.testsRun} test exécuté" if result.testsRun <= 1 else f"{result.testsRun} tests exécutés"
    pass_lbl = f"{passed} passé" if passed <= 1 else f"{passed} passés"

    self.stream.writeln("=" * 76)
    self.stream.writeln("📊  RÉSUMÉ D'EXÉCUTION")
    self.stream.writeln("=" * 76)
    self.stream.writeln(f"  Modules testés   : {mod_lbl}")
    self.stream.writeln(f"  Total des tests  : {test_lbl}")
    self.stream.writeln(f"  Tests réussis    : {pass_lbl}")
    if result.skipped:
        skip_cnt = len(result.skipped)
        skip_lbl = f"{skip_cnt} ignoré" if skip_cnt == 1 else f"{skip_cnt} ignorés"
        self.stream.writeln(f"  Tests ignorés    : {skip_lbl} (replis gracieux)")
    if result.failures:
        fail_cnt = len(result.failures)
        fail_lbl = f"{fail_cnt} échec" if fail_cnt == 1 else f"{fail_cnt} échecs"
        self.stream.writeln(f"  Échecs           : {fail_lbl}")
    if result.errors:
        err_cnt = len(result.errors)
        err_lbl = f"{err_cnt} erreur" if err_cnt == 1 else f"{err_cnt} erreurs"
        self.stream.writeln(f"  Erreurs          : {err_lbl}")
    self.stream.writeln(f"  Temps total      : {total_time:.2f}s")
    self.stream.writeln("=" * 76)
    if result.wasSuccessful():
        self.stream.writeln("✅  SUCCÈS GLOBAL : Tous les tests requis sont validés avec succès !")
    else:
        self.stream.writeln("❌  ÉCHEC GLOBAL : Des anomalies ont été détectées ci-dessus.")
    self.stream.writeln("=" * 76)
    self.stream.flush()
    return result


class CemantixTestRunner(unittest.TextTestRunner):
    """Exécuteur direct de tests unittest."""

    resultclass = CemantixTestResult
    run = cemantix_run


def install_runner() -> None:
    """Enregistre le runner Cemantix dans le framework unittest."""
    unittest.TextTestRunner.run = cemantix_run
    unittest.TextTestRunner.resultclass = CemantixTestResult
