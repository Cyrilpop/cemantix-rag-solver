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
- Heartbeat régulier et fonction check_health pour le HEALTHCHECK Docker.
- Sauvegarde de l'historique dans cemantix_data/daily_history.json.
- Synchronisation automatique des données web pour le serveur Caddy (volumes/web/data.json).
- Logs clairs et horodatés sur stdout (visibles via docker logs -f).
"""
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import DATA_DIR, enforce_runtime_config, log
from ..db import CHALLENGE_ENABLED
from ..engine import Solver
from .challenges import (
    CHALLENGE_POLL_SECONDS,
    challenge_maintenance,
    challenge_tick,
    warm_store,
)

PARIS_TZ = ZoneInfo("Europe/Paris")
DAILY_HISTORY_FILE = DATA_DIR / "daily_history.json"
# Le battement doit être lisible par le service web : `/tmp` est propre à chaque
# conteneur, l'y écrire rendait le widget « État du démon » du tableau de bord
# structurellement faux (il affichait « inactif » pendant que le worker travaillait).
HEARTBEAT_FILE = Path(
    os.environ.get("DAEMON_HEARTBEAT_FILE", str(DATA_DIR / "daemon_heartbeat.json"))
)
DAEMON_COMMAND_FILE = DATA_DIR / "daemon_command.json"


def check_and_consume_command() -> str | None:
    """Lit et supprime un ordre déposé par l'API web (ex: solve immédiat)."""
    if not DAEMON_COMMAND_FILE.exists():
        return None
    try:
        content = DAEMON_COMMAND_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        DAEMON_COMMAND_FILE.unlink(missing_ok=True)
        return data.get("action")
    except Exception as e:
        log(f"⚠️  Erreur lecture ordre démon : {e}")
        DAEMON_COMMAND_FILE.unlink(missing_ok=True)
        return None

# Le battement est rafraîchi en arrière-plan : une phase longue (chargement du
# modèle de mots, indexation, appel LLM) bloquait le thread principal et laissait
# le battement vieillir au-delà du seuil du HEALTHCHECK — le conteneur passait
# `unhealthy` **pendant qu'il travaillait**, et tout pilotage par la santé aurait
# tué une résolution en cours.
HEARTBEAT_INTERVAL_SECONDS = float(os.environ.get("DAEMON_HEARTBEAT_INTERVAL", "15"))
_heartbeat_state = {"status": "starting", "extra": {}}
_heartbeat_stop = threading.Event()
_heartbeat_thread: threading.Thread | None = None


def _heartbeat_loop() -> None:
    while not _heartbeat_stop.wait(HEARTBEAT_INTERVAL_SECONDS):
        update_heartbeat(_heartbeat_state["status"], dict(_heartbeat_state["extra"]))


def start_heartbeat_monitor() -> None:
    """Démarre le rafraîchissement périodique du battement (idempotent)."""
    global _heartbeat_thread
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return
    _heartbeat_stop.clear()
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, name="CemantixHeartbeat", daemon=True
    )
    _heartbeat_thread.start()


def stop_heartbeat_monitor() -> None:
    """Arrête le rafraîchissement périodique (appelé avant l'écriture de « stopped »)."""
    _heartbeat_stop.set()


def update_heartbeat(status: str, extra: dict = None) -> None:
    """Met à jour le fichier de battement de cœur (heartbeat) pour le HEALTHCHECK Docker."""
    _heartbeat_state["status"] = status
    _heartbeat_state["extra"] = dict(extra or {})
    data = {
        "status": status,
        "pid": os.getpid(),
        "timestamp": datetime.now(PARIS_TZ).isoformat(),
        "updated_at": time.time(),
    }
    if extra:
        data.update(extra)
    try:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = HEARTBEAT_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        tmp_file.replace(HEARTBEAT_FILE)
    except Exception as e:
        # Muet ici, le HEALTHCHECK Docker finirait par déclarer le conteneur
        # `unhealthy` alors que le démon tourne : la cause doit rester visible.
        log(f"⚠️  [DÉMON] Impossible d'écrire le battement {HEARTBEAT_FILE} : {e}")


def check_health(max_age_seconds: int = 90) -> int:
    """Vérifie l'état de santé du démon pour le HEALTHCHECK Docker.
    Retourne 0 si sain (healthy), 1 sinon.
    """
    if not HEARTBEAT_FILE.exists():
        sys.stderr.write("HEALTHCHECK FAIL: Fichier heartbeat introuvable\n")
        return 1
    try:
        with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        updated_at = data.get("updated_at", 0.0)
        age = time.time() - updated_at
        if age > max_age_seconds:
            sys.stderr.write(f"HEALTHCHECK FAIL: Heartbeat trop ancien ({age:.1f}s > {max_age_seconds}s)\n")
            return 1
        status = data.get("status")
        if status == "stopped":
            sys.stderr.write("HEALTHCHECK FAIL: Démon marqué comme arrêté\n")
            return 1
        return 0
    except Exception as e:
        sys.stderr.write(f"HEALTHCHECK FAIL: {e}\n")
        return 1


def load_history(filepath: Path = DAILY_HISTORY_FILE) -> list:
    """Charge l'historique des résolutions quotidiennes (priorité PostgreSQL, repli JSON)."""
    # 1. Tentative de lecture en base relationnelle uniquement sur le chemin officiel
    if filepath == DAILY_HISTORY_FILE:
        try:
            from ..db import get_all_daily_puzzles
            db_entries = get_all_daily_puzzles()
            if db_entries:
                return db_entries
        except Exception as e:
            log(f"⚠️  Lecture base relationnelle indisponible ({e}), repli JSON.")

    # 2. Repli sur le fichier JSON historique
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
    """Sauvegarde l'historique des résolutions dans un fichier JSON indenté (rétrocompatibilité)."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠️  Erreur lors de la sauvegarde de {filepath} : {e}")


def has_solved_today(history: list, today_str: str) -> tuple[bool, dict | None]:
    """Vérifie si le puzzle de la date donnée a déjà été résolu avec succès."""
    if history:
        for entry in history:
            if entry.get("date") == today_str and entry.get("win") is True:
                return True, entry
        return False, None

    try:
        from ..db import get_daily_puzzle
        db_entry = get_daily_puzzle(today_str)
        if db_entry and db_entry.get("win") is True:
            return True, db_entry
    except Exception as e:
        # Une base injoignable ressemble ici à « pas encore résolu » : le démon
        # relancerait une résolution complète pour un mot déjà gagné.
        log(f"⚠️  [DÉMON] Base de données inaccessible pour le statut du jour : {e}")

    return False, None


def has_failed_entry_today(history: list, today_str: str) -> bool:
    """Indique si une tentative échouée a déjà été consignée pour cette date.

    `run_daily_solver` consigne aussi les défaites : après un échec réseau, la
    relance immédiate qui suit ne doit pas écraser cette trace par un nouvel
    échec — l'historique de la journée reste ainsi lisible.
    """
    return any(
        entry.get("date") == today_str and entry.get("win") is not True
        for entry in history or []
    )


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
    update_heartbeat("solving")
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
        "top_guesses": result.get("top_guesses", []),
        "trajectory": result.get("trajectory", []),
        "timestamp": now.isoformat(),
    }

    # Persistance relationnelle ACID dans PostgreSQL (ou repli SQLite)
    try:
        from ..db import save_daily_puzzle
        save_daily_puzzle(entry)
        log("🐘  Résultat consigné avec succès dans la table PostgreSQL daily_puzzles.")
    except Exception as e:
        log(f"⚠️  Erreur sauvegarde base relationnelle : {e}")

    # Persistance des indices par paliers dans daily_puzzle_hints (Jalon M6)
    try:
        from .hints import generate_hints_for_word
        from ..db import save_daily_hints
        store = getattr(args, "store", None) or getattr(solver, "store", None)
        if store and result.get("word"):
            hints = generate_hints_for_word(result["word"], store)
            if hints:
                save_daily_hints(today_str, hints)
                log(f"🧩  {len(hints)} indices générés et persistés dans daily_puzzle_hints.")
    except Exception as e:
        log(f"⚠️  Erreur sauvegarde indices quotidiens : {e}")

    history = load_history()
    # Remplacer toute entrée précédente pour la même date pour garantir l'enregistrement de la trajectoire
    history = [h for h in history if h.get("date") != today_str]
    history.append(entry)
    save_history(history)

    log(f"📝  Résultat enregistré dans {DAILY_HISTORY_FILE}")

    update_heartbeat("sleeping", {"last_solved_puzzle": puzzle_id, "last_solved_word": result.get("word")})

    # Synchronisation automatique de la page web pour Caddy
    try:
        from .web import export_web_data
        export_web_data(history=history)
    except Exception as e:
        log(f"⚠️  Export web automatique non disponible : {e}")

    try:
        from ..api.routes.system import invalidate_system_cache
        invalidate_system_cache()
    except Exception:
        pass

    return entry


def _wait_with_challenges(seconds: int, args, is_running) -> None:
    """Attend `seconds` secondes en servant la file des défis au bot.

    Le pick-up `DEFI-09` vit dans la boucle de veille ; sans ce relais, un démon
    occupé ailleurs (rattrapage de démarrage qui échoue et se répète, attente
    entre deux tentatives) laisse les défis empilés sans jamais les regarder —
    le joueur voit « le bot cherche… » indéfiniment.

    La résolution nocturne garde la priorité (`DEFI-13`) : cette aide n'est
    appelée que pendant les attentes, jamais pendant une résolution.
    """
    last_poll = 0.0
    for _ in range(int(seconds)):
        if not is_running():
            return
        time.sleep(1)
        last_poll += 1
        if CHALLENGE_ENABLED and last_poll >= CHALLENGE_POLL_SECONDS:
            last_poll = 0.0
            try:
                challenge_tick(getattr(args, "store", None))
            except Exception as e:
                log(f"⚠️  [DÉFI] Tour de pick-up en échec : {e}", level=logging.WARNING)


def run_daemon_loop(args) -> None:
    """Boucle principale du démon 24h/24."""
    enforce_runtime_config()
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        log(f"\n🛑  Signal {sig_name} reçu, arrêt propre du démon Cémantix...")
        running = False
        update_heartbeat("stopped")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    update_heartbeat("starting")
    start_heartbeat_monitor()
    log("=" * 60)
    log("⏰  DÉMON CÉMANTIX SOLVER — VEILLE QUOTIDIENNE (00h00)")
    log("=" * 60)
    # SEC-27 : purge RGPD des défis au bot périmés dès le démarrage du worker.
    challenge_maintenance()

    # Rattrapage idempotent des indices de puzzles quotidiens (Jalon M6)
    try:
        from .hints import backfill_puzzle_hints
        backfill_puzzle_hints(getattr(args, "store", None))
    except Exception as e:
        log(f"⚠️  [DÉMON] Erreur lors du rattrapage des indices : {e}")
    now = datetime.now(PARIS_TZ)
    log(f"📅  Heure locale (Europe/Paris) : {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log(f"💾  Fichier historique          : {DAILY_HISTORY_FILE}")
    log(f"⚙   Mode d'exécution           : {'100% RAG Pur' if getattr(args, 'rag_only', False) else 'Hybride RAG + LLM'}")

    # Synchronisation initiale de la page web et de sitemap.xml au démarrage
    seo_synced = False
    try:
        from .web import export_web_data
        export_web_data()
        seo_synced = True
    except Exception as e:
        log(f"⚠️  [DÉMON] Synchronisation initiale de la page web échouée : {e}")
        from .seo import ensure_seo_published
        if ensure_seo_published() is not None:
            seo_synced = True

    # Démarrage de l'API locale du jeu interactif (partage en mémoire du VocabStore)
    if not getattr(args, "no_api", False):
        try:
            from ..engine import VocabStore
            from ..api import start_api_thread
            store = getattr(args, "store", None) or VocabStore()
            args.store = store
            api_port = getattr(args, "api_port", 8000)
            api_host = getattr(args, "api_host", "0.0.0.0")
            start_api_thread(store, host=api_host, port=api_port, publish_seo=not seo_synced)
        except Exception as e:
            log(f"⚠️  Impossible de démarrer l'API locale du jeu : {e}")


    # DEFI-11 : le magasin vectoriel est préchargé en arrière-plan pour que le
    # premier défi ne paie pas l'ouverture de ChromaDB (~30 s d'attente muette).
    if CHALLENGE_ENABLED and getattr(args, "store", None) is None:
        warm_store(args)

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
                # Sans ce rattrapage, le dashboard reste privé de son mot du jour
                # (POST /api/daily/reveal renvoie « pas encore résolu ») et le
                # démon ne le découvrira qu'au prochain réveil de minuit.
                log(f"❌  Erreur lors de la résolution initiale : {e}", level=logging.WARNING)
                if not has_failed_entry_today(history, today_str):
                    log("🔁  Nouvel essai de résolution initiale dans 60 secondes...")
                    # Le pick-up des défis continue pendant cette attente : sinon
                    # un worker qui ne joint pas le site officiel n'en traite aucun.
                    _wait_with_challenges(60, args, lambda: running)
                    if running:
                        try:
                            run_daily_solver(args)
                        except Exception as retry_error:
                            log(f"❌  Échec définitif de la résolution initiale : {retry_error}",
                                level=logging.WARNING)

    # Boucle de veille permanente
    while running:
        seconds_left, next_target = get_next_run(target_hour=0, target_minute=0, buffer_seconds=10)
        target_str = next_target.strftime("%Y-%m-%d %H:%M:%S %Z")
        log(f"\n💤  Mise en veille du démon jusqu'à 00h00 Paris (prochain réveil : {target_str}, dans {format_duration(seconds_left)}).")
        update_heartbeat("sleeping", {"next_run": target_str})

        # Sommeil par tranche de 1 seconde pour réactivité immédiate à SIGINT/SIGTERM ou commandes admin
        tick = 0
        forced_action = None
        last_challenge_poll = 0.0
        while running and datetime.now(PARIS_TZ) < next_target:
            cmd = check_and_consume_command()
            if cmd == "solve":
                log("\n⚡  [DÉMON WORKER] Ordre de résolution immédiate reçu depuis l'API web !")
                forced_action = "solve"
                break
            time.sleep(1)
            tick += 1
            if tick % 15 == 0:
                update_heartbeat("sleeping", {"next_run": target_str})
            # DEFI-09 : défis au bot — pick-up dans la même boucle de veille,
            # sans nouveau processus. Un seul défi à la fois ; la résolution
            # nocturne de minuit reste prioritaire (DEFI-13) : elle démarre au
            # prochain tour de boucle, le défi en cours étant borné en durée.
            if CHALLENGE_ENABLED and tick - last_challenge_poll >= CHALLENGE_POLL_SECONDS:
                last_challenge_poll = tick
                try:
                    if challenge_tick(getattr(args, "store", None)):
                        update_heartbeat("sleeping", {"next_run": target_str})
                except Exception as e:
                    log(f"⚠️  [DÉFI] Tour de pick-up en échec : {e}", level=logging.WARNING)

        if not running:
            break

        if forced_action == "solve":
            try:
                run_daily_solver(args)
            except Exception as e:
                log(f"⚠️  Échec lors de la résolution commandée : {e}", level=logging.WARNING)
            continue

        log("\n⏰  Réveil du démon Cémantix — Minuit passé, lancement de la résolution !")
        challenge_maintenance()  # SEC-27 : purge des défis périmés à chaque réveil
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

    stop_heartbeat_monitor()
    update_heartbeat("stopped")
    log("👋  Démon Cémantix arrêté.")
