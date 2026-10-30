"""
Cémantix Solver — Défis au Bot côté Worker (2026-10-06-defier-le-bot)
=====================================================================
Cœur du tiers « worker » : la file `bot_challenges` est relue dans la boucle de
veille du démon ; chaque défi est résolu par le moteur existant — `Solver` +
`MockClient(secret=…)`, l'oracle local de l'option `--secret` du CLI — **en
100 % RAG pur** (zéro LLM : un défi doit rester borné et reproductible).

Le worker est le seul à écrire la trajectoire ; l'API web ne fait que la relire.
"""
import os
import threading
import time

from ..config import log
from ..db import (
    CHALLENGE_ENABLED,
    CHALLENGE_MAX_TRIES,
    CHALLENGE_RETENTION_DAYS,
    CHALLENGE_TIMEOUT,
    append_trajectory,
    claim_next_challenge,
    finish_challenge,
    heartbeat,
    purge_older_than,
    release_challenge,
    requeue_stale_running,
)

CHALLENGE_POLL_SECONDS = float(os.getenv("CHALLENGE_POLL_SECONDS", "3"))
CHALLENGE_PUBLISH_SECONDS = 2.0  # DEFI-11 : publication au moins toutes les 2 s

# Le worker tourne sans API : le magasin vectoriel est chargé une seule fois
# et partagé entre tous les défis (le démon nocturne garde le sien).
_shared_store = None
_store_lock = threading.Lock()


class _ChallengeArgs:
    """Arguments de résolution d'un défi : RAG pur, jamais d'LLM (défi borné)."""
    max_tries = CHALLENGE_MAX_TRIES
    retrieve = 60
    rag_words = 3
    llm_words = 6
    rag_only = True
    delay = 0.0
    verbose = False
    seeds = ""
    seeds_file = ""
    seed_count = 12
    static_seeds = False
    mock = False
    benchmark = 0
    secret = None
    store = None


def _resolve_store(store):
    """Magasin vectoriel partagé : celui de l'API si présent, sinon chargement unique."""
    global _shared_store
    if store is not None:
        return store
    with _store_lock:
        if _shared_store is None:
            log("⚔️  [DÉFI] Premier défi : chargement du magasin vectoriel côté worker…")
            from ..engine import VocabStore
            _shared_store = VocabStore()
        return _shared_store


def process_next_challenge(store=None) -> bool:
    """Prélève et résout un défi. Retourne True si un défi a été traité.

    Ordre (DEFI-09..12) : claim atomique → résolution `Solver` +
    `MockClient(secret)` en RAG pur → trajectoire incrémentale toutes les 2 s →
    statut terminal `solved` / `lost` / `error`, sous `CHALLENGE_TIMEOUT`.
    """
    if not CHALLENGE_ENABLED:
        return False

    challenge = claim_next_challenge()
    if not challenge:
        return False

    challenge_id = challenge["id"]
    secret = challenge["secret_word"]
    max_tries = min(int(challenge.get("max_tries") or CHALLENGE_MAX_TRIES),
                    CHALLENGE_MAX_TRIES)
    log(f"⚔️  [DÉFI] Défi {challenge_id[:8]}… pris en charge (max {max_tries} coups)")

    store = _resolve_store(store)
    if getattr(store, "col", None) is None:
        # Index vectoriel en cours de reconstruction : la file attend, rien n'est perdu.
        # La tâche déjà claimée est rendue à la file pour le prochain réveil.
        release_challenge(challenge_id)
        log("⚠️  [DÉFI] ChromaDB indisponible : le défi retourne en file.", level="WARNING")
        return False

    from ..engine import Solver
    from ..engine.clients import MockClient

    try:
        game = MockClient(store, secret=secret)
    except ValueError:
        # Le mot a disparu du store entre la validation web et ici : erreur propre.
        finish_challenge(challenge_id, "error", 0, 0.0, "mot absent du magasin vectoriel")
        log(f"⚠️  [DÉFI] Défi {challenge_id[:8]}… : mot subitement invalide.", level="WARNING")
        return True

    args = _ChallengeArgs()
    args.max_tries = max_tries
    solver = Solver(args, store=store, game=game)

    result = {}

    def _run():
        try:
            result.update(solver.run())
        except Exception as exc:  # le thread ne doit jamais mourir en silence
            log(f"⚠️  [DÉFI] Incident de résolution : {exc}", level="WARNING")

    worker = threading.Thread(target=_run, name="CemantixChallenge", daemon=True)
    started = time.time()
    published = 0
    worker.start()
    while worker.is_alive():
        worker.join(timeout=CHALLENGE_PUBLISH_SECONDS)
        steps = list(solver.trajectory)
        if len(steps) > published:
            append_trajectory(challenge_id, steps, len(solver.guesses))
            published = len(steps)
        else:
            heartbeat(challenge_id)
        if time.time() - started > CHALLENGE_TIMEOUT:
            # Coût borné (DEFI-12) : le solveur s'arrêtera seul à `max_tries`,
            # mais le défi est clôturé ici pour ne pas retenir la file.
            append_trajectory(challenge_id, steps, len(solver.guesses))
            finish_challenge(challenge_id, "error", len(solver.guesses),
                             time.time() - started, "délai maximal dépassé")
            log(f"⏱️  [DÉFI] Défi {challenge_id[:8]}… interrompu : délai maximal.",
                level="WARNING")
            return True

    append_trajectory(challenge_id, list(solver.trajectory), len(solver.guesses))
    if not result:
        finish_challenge(challenge_id, "error", len(solver.guesses),
                         time.time() - started, "incident interne de résolution")
        return True

    status = "solved" if result.get("win") else "lost"
    finish_challenge(challenge_id, status, int(result.get("tries") or 0),
                     float(result.get("time") or 0.0))
    log(f"⚔️  [DÉFI] Défi {challenge_id[:8]}… : {status} en {result.get('tries')} coups "
        f"({float(result.get('time') or 0.0):.1f} s)")
    return True


def challenge_tick(store=None) -> bool:
    """Un tour de pick-up : orphelins recyclés puis un défi traité au plus (DEFI-09)."""
    if not CHALLENGE_ENABLED:
        return False
    try:
        requeue_stale_running()
    except Exception as exc:
        log(f"⚠️  [DÉFI] Recyclage des orphelins impossible : {exc}", level="WARNING")
    return process_next_challenge(store)


def challenge_maintenance() -> None:
    """Purge RGPD des défis périmés (SEC-27), appelée au réveil du démon."""
    try:
        removed = purge_older_than(CHALLENGE_RETENTION_DAYS)
        if removed:
            log(f"🧹  [DÉFI] Purge : {removed} défis de plus de "
                f"{CHALLENGE_RETENTION_DAYS} jours effacés.")
    except Exception as exc:
        log(f"⚠️  [DÉFI] Purge impossible : {exc}", level="WARNING")

