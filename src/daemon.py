"""
Cémantix Solver — Démon Planificateur Quotidien
================================================
Exécute en tâche de fond permanente le solveur Cémantix.
Se met en veille et se réveille chaque jour à 00h00 (heure de Paris / Europe/Paris)
pour résoudre le mot secret du jour dès sa parution sur cemantix.certitudes.org.

Fonctionnalités :
- Horloge calée sur le fuseau officiel de Cémantix (Europe/Paris).
- Veille économe en ressources avec interception propre des signaux SIGTERM/SIGINT (docker stop).
- Rattrapage immédiat au démarrage si le mot du jour n'a pas encore été résolu.
- Sauvegarde de l'historique dans cemantix_data/daily_history.json.
- Logs clairs et horodatés sur stdout (visibles via docker logs -f).
"""
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import DATA_DIR, log
from .solvers import Solver

PARIS_TZ = ZoneInfo("Europe/Paris")
DAILY_HISTORY_FILE = DATA_DIR / "daily_history.json"


def load_history(filepath: Path = DAILY_HISTORY_FILE) -> list:
    """Charge l'historique des résolutions quotidiennes."""
    if not filepath.exists():
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"⚠️  Erreur lors de la lecture de {filepath} : {e}")
        return []


def save_history(history: list, filepath: Path = DAILY_HISTORY_FILE) -> None:
    """Sauvegarde l'historique des résolutions dans un fichier JSON indenté."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠️  Erreur lors de la sauvegarde de {filepath} : {e}")


def has_solved_today(history: list, today_str: str) -> tuple[bool, dict | None]:
    """Vérifie si le puzzle de la date donnée a déjà été résolu avec succès."""
    for entry in history:
        if entry.get("date") == today_str and entry.get("win") is True:
            return True, entry
    return False, None


def get_next_run(target_hour: int = 0, target_minute: int = 0, buffer_seconds: int = 10) -> tuple[float, datetime]:
    """Calcule le temps restant en secondes et le datetime cible pour la prochaine exécution.
    
    Un léger buffer de sécurité (10s par défaut) permet de s'assurer que l'API
    du site a bien basculé sur le nouveau puzzle à 00h00.
    """
    now = datetime.now(PARIS_TZ)
    target = now.replace(hour=target_hour, minute=target_minute, second=buffer_seconds, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    seconds = max(0.0, (target - now).total_seconds())
    return seconds, target


def format_duration(seconds: float) -> str:
    """Formate une durée en secondes sous forme lisible (Xh Ym Zs)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hrs > 0:
        parts.append(f"{hrs}h")
    if mins > 0 or hrs > 0:
        parts.append(f"{mins:02d}m")
    parts.append(f"{secs:02d}s")
    return " ".join(parts)


def run_daily_solver(args) -> dict:
    """Exécute une session de résolution du mot du jour et consigne le résultat."""
    now = datetime.now(PARIS_TZ)
    today_str = now.strftime("%Y-%m-%d")
    log(f"\n{'═' * 60}")
    log(f"🎯  [DÉMON CÉMANTIX] Début de résolution pour le {today_str} ({now.strftime('%H:%M:%S')})")
    log(f"{'═' * 60}")

    solver = Solver(args)
    puzzle_id = getattr(solver.game, "puzzle", None)
    result = solver.run()

    entry = {
        "date": today_str,
        "puzzle": puzzle_id,
        "word": result.get("word"),
        "tries": result.get("tries"),
        "attempts": result.get("attempts"),
        "source": result.get("source"),
        "win": result.get("win", False),
        "duration_seconds": round(result.get("time", 0.0), 2),
        "timestamp": now.isoformat(),
    }

    history = load_history()
    # Remplacer une éventuelle entrée précédente non victorieuse pour le même puzzle
    history = [h for h in history if not (h.get("date") == today_str and h.get("win") is False)]
    history.append(entry)
    save_history(history)

    log(f"📝  Résultat enregistré dans {DAILY_HISTORY_FILE}")
    return entry


def run_daemon_loop(args) -> None:
    """Boucle principale du démon 24h/24."""
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        log(f"\n🛑  Signal {sig_name} reçu, arrêt propre du démon Cémantix...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log("=" * 60)
    log("⏰  DÉMON CÉMANTIX SOLVER — VEILLE QUOTIDIENNE (00h00)")
    log("=" * 60)
    now = datetime.now(PARIS_TZ)
    log(f"📅  Heure locale (Europe/Paris) : {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log(f"💾  Fichier historique          : {DAILY_HISTORY_FILE}")
    log(f"⚙   Mode d'exécution           : {'100% RAG Pur' if getattr(args, 'rag_only', False) else 'Hybride RAG + LLM'}")

    # Rattrapage au démarrage : vérifier si le mot d'aujourd'hui est déjà résolu
    skip_on_start = getattr(args, "no_run_on_start", False)
    if not skip_on_start:
        today_str = now.strftime("%Y-%m-%d")
        history = load_history()
        solved, past_entry = has_solved_today(history, today_str)
        if solved and past_entry:
            log(f"✓   Puzzle du jour ({today_str}) déjà résolu précédemment : "
                f"« {past_entry.get('word', '').upper()} » en {past_entry.get('tries')} coups.")
        else:
            log(f"🚀  Puzzle du jour ({today_str}) non résolu dans l'historique : résolution immédiate...")
            try:
                run_daily_solver(args)
            except Exception as e:
                log(f"❌  Erreur lors de la résolution initiale : {e}")

    # Boucle de veille permanente
    while running:
        seconds_left, next_target = get_next_run(target_hour=0, target_minute=0, buffer_seconds=10)
        target_str = next_target.strftime("%Y-%m-%d %H:%M:%S %Z")
        log(f"\n💤  Mise en veille du démon jusqu'à 00h00 Paris (prochain réveil : {target_str}, dans {format_duration(seconds_left)}).")

        # Sommeil par tranche de 1 seconde pour réactivité immédiate à SIGINT/SIGTERM
        while running and datetime.now(PARIS_TZ) < next_target:
            time.sleep(1)

        if not running:
            break

        log("\n⏰  Réveil du démon Cémantix — Minuit passé, lancement de la résolution !")
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                run_daily_solver(args)
                break
            except Exception as e:
                log(f"⚠️  Échec lors de la tentative {attempt}/{max_attempts} : {e}")
                if attempt < max_attempts and running:
                    log("⏳  Nouvel essai dans 60 secondes...")
                    for _ in range(60):
                        if not running:
                            break
                        time.sleep(1)

    log("👋  Démon Cémantix arrêté.")
