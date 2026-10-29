"""
Cémantix Solver — Exportateur & Données Web
===========================================
Génère et maintient à jour le jeu de données web (data.json)
destiné à la page web du mot du jour servie par Caddy (volume ./volumes/web).

Fonctionnalités :
- Agrégation du mot du jour le plus récent et de ses métriques.
- Compilation des statistiques globales (essais moyens, durée, victoires).
- Calcul du compte à rebours vers le prochain puzzle (00h00 Paris).
- Suivi de l'état du démon (battement de cœur, statut).
- Écriture atomique et sécurisée de data.json pour le serveur Caddy.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import BASE_DIR, DATA_DIR, log
from .daemon import (
    DAILY_HISTORY_FILE,
    HEARTBEAT_FILE,
    PARIS_TZ,
    get_next_run,
    load_history,
)

VOLUMES_DIR = BASE_DIR / "volumes"
DASHBOARD_DATA_FILE = Path(os.getenv("DASHBOARD_DATA_FILE", str(DATA_DIR / "data.json")))
WEB_DATA_FILE = DASHBOARD_DATA_FILE  # Rétrocompatibilité

def build_web_data(
    history: list = None,
    heartbeat_path: Path = HEARTBEAT_FILE,
    now_dt: datetime = None,
    mask_words: bool = True,
) -> dict:
    """Construit la structure de données complète pour l'interface web."""
    if history is None:
        history = load_history(DAILY_HISTORY_FILE)
    if now_dt is None:
        now_dt = datetime.now(PARIS_TZ)

    # 1. Identifier le mot du jour (dernière entrée victorieuse par date/puzzle)
    winning_entries = [e for e in history if e.get("win") is True]
    if winning_entries:
        current = max(winning_entries, key=lambda x: (x.get("date", ""), str(x.get("puzzle", 0))))
    elif history:
        current = max(history, key=lambda x: (x.get("date", ""), str(x.get("puzzle", 0))))
    else:
        current = None

    # 2. Statistiques globales (priorité calcul SQL direct PERF-04, repli mémoire)
    sql_stats = None
    try:
        from ..db import get_history_summary
        sql_stats = get_history_summary()
    except Exception:
        pass

    if sql_stats is not None:
        stats = sql_stats
    else:
        total_solved = len(winning_entries)
        if total_solved > 0:
            avg_tries = round(sum(e.get("tries", 0) for e in winning_entries) / total_solved, 1)
            valid_durations = [e.get("duration_seconds", 0.0) for e in winning_entries if e.get("duration_seconds")]
            avg_duration = round(sum(valid_durations) / len(valid_durations), 2) if valid_durations else 0.0
            fastest_tries = min(e.get("tries", 9999) for e in winning_entries)
            fastest_duration = min(valid_durations) if valid_durations else 0.0
            win_rate = round((len(winning_entries) / len(history)) * 100, 1) if history else 100.0
        else:
            avg_tries = 0
            avg_duration = 0.0
            fastest_tries = 0
            fastest_duration = 0.0
            win_rate = 100.0
        stats = {
            "total_solved": total_solved,
            "avg_tries": avg_tries,
            "avg_duration_seconds": avg_duration,
            "fastest_tries": fastest_tries,
            "fastest_duration_seconds": fastest_duration,
            "win_rate": win_rate,
        }

    # 3. État du démon et prochain réveil
    seconds_left, next_target = get_next_run(target_hour=0, target_minute=0, buffer_seconds=10)
    # « unknown » et non « idle » quand aucun battement n'existe : sans le démon,
    # on ne peut pas affirmer qu'il est inactif — et le front affichait alors une
    # veille rassurante alors que rien ne tournait.
    daemon_status = "unknown"
    last_heartbeat_time = None

    if heartbeat_path and heartbeat_path.exists():
        try:
            with open(heartbeat_path, "r", encoding="utf-8") as f:
                hb_data = json.load(f)
                daemon_status = hb_data.get("status", "unknown")
                last_heartbeat_time = hb_data.get("timestamp")
                # Si le heartbeat a plus de 120s, marquer comme inactif
                age = time.time() - hb_data.get("updated_at", 0)
                if age > 120 and daemon_status != "stopped":
                    daemon_status = "offline"
        except Exception:
            daemon_status = "error"

    # 4. Historique inversé (le plus récent d'abord)
    history_sorted = sorted(
        history,
        key=lambda x: x.get("date", ""),
        reverse=True,
    )
    if mask_words:
        # Masque uniquement les puzzles non résolus ou le jour en cours
        today_str = now_dt.strftime("%Y-%m-%d")
        masked_history = []
        for item in history_sorted:
            entry = dict(item)
            if entry.get("date") == today_str and not entry.get("is_revealed"):
                entry["word"] = None
                entry["word_hidden"] = True
            masked_history.append(entry)
        history_sorted = masked_history

    return {
        "title": "Cémantix Solver — Mot du Jour",
        "last_updated": now_dt.isoformat(),
        "current": current,
        "stats": stats,
        "daemon": {
            "status": daemon_status,
            "last_heartbeat": last_heartbeat_time,
            "next_run": next_target.isoformat(),
            "next_run_seconds": round(seconds_left, 1),
            "timezone": "Europe/Paris",
        },
        "history": history_sorted,
    }


def export_web_data(
    target_dir: Path = None,
    history: list = None,
    heartbeat_path: Path = HEARTBEAT_FILE,
    publish_seo: bool = True,
) -> Path:
    """Génère et écrit de manière atomique data.json dans le répertoire cible (défaut : DATA_DIR).

    Si `publish_seo` est vrai, les pages d'archives `/puzzles/<date>/`, l'index
    paginé et `sitemap.xml` sont également (re)générés dans le webroot Caddy.

    `data.json` contient l'historique complet des solutions : il n'a donc rien à
    faire dans le webroot servi par Caddy, où un simple curl le rendrait public.
    """
    out_dir = target_dir if target_dir is not None else DATA_DIR

    from .seo import WEB_ROOT
    try:
        resolved = out_dir.resolve()
        if resolved == WEB_ROOT.resolve() or WEB_ROOT.resolve() in resolved.parents:
            raise ValueError(
                f"Répertoire cible refusé pour data.json : {out_dir} est servi "
                "publiquement par Caddy et exposerait toutes les solutions."
            )
    except OSError:
        pass

    out_dir.mkdir(parents=True, exist_ok=True)
    target_file = out_dir / "data.json"

    data = build_web_data(history=history, heartbeat_path=heartbeat_path)

    # Écriture atomique via fichier temporaire
    tmp_file = target_file.with_suffix(".tmp")
    try:
        with open(tmp_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(target_file)
        log(f"🌐  Données web synchronisées avec succès dans {target_file}")
    except Exception as e:
        log(f"⚠️  Erreur lors de l'exportation des données web : {e}")
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
        raise

    if publish_seo:
        try:
            from .seo import publish_seo_pages
            publish_seo_pages(
                history=data.get("history") or [],
                generated_at=datetime.now(PARIS_TZ),
            )
        except Exception as e:
            log(f"⚠️  Publication SEO non bloquante en échec : {e}")

    return target_file
