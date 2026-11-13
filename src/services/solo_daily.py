"""
Cémantix Solver — Service Métier Solo Quotidien, Tirage & Simulation (Jalon M15)
================================================================================
Orchestre :
- Le tirage aléatoire pondéré du mot du jour Solo à 00h00 avec catégorie Extrême.
- La génération des 3 indices IA Gemini (mot + phrase) et leur rétention roulante (1j).
- La simulation réaliste à 6h30 des 7 à 10 joueurs du pool des 20 habitués si aucun humain n'a gagné.
- Le verrouillage d'idempotence et les options de forçage (--force).
"""
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np

from ..ai import GeminiClient
from ..ai.trajectory_sim import simulate_batch_trajectories
from ..config import log
from ..db.connection import db
from ..db.players import seed_bot_players_if_empty
from ..game.solo import STOPWORDS
from ..db.solo import (
    clear_solo_bots_simulated,
    finish_solo_player_game,
    get_or_create_solo_daily_puzzle,
    get_solo_ai_hints,
    get_solo_daily_puzzle,
    has_real_player_won,
    is_solo_bots_simulated,
    lock_solo_bots_simulated,
    purge_old_solo_ai_hints,
    save_solo_ai_hints,
)

PARIS_TZ = ZoneInfo("Europe/Paris")
_last_purge_date: Optional[str] = None


def maybe_purge_old_daily_data(current_date: Optional[str] = None) -> int:
    """Purge les indices IA des jours strictement antérieurs à aujourd'hui au plus une fois par jour.
    
    Règle absolue : on ne purge qu'une fois par jour, et jamais la journée en cours
    (strictement puzzle_date < today_str).
    """
    global _last_purge_date
    today_str = current_date or get_current_paris_date()
    if _last_purge_date == today_str:
        return 0
    _last_purge_date = today_str

    purged = purge_old_solo_ai_hints(today_str)
    if purged > 0:
        log(f"🧹  [SOLO] Purge quotidienne exécutée : {purged} ancien(s) indice(s) IA purgé(s) (< {today_str}).")
    return purged


def get_current_paris_date() -> str:
    """Retourne la date du jour au format YYYY-MM-DD selon le fuseau officiel de Paris."""
    return datetime.now(PARIS_TZ).strftime("%Y-%m-%d")


def ensure_solo_daily_puzzle(
    store: Any = None,
    manager: Any = None,
    puzzle_date: Optional[str] = None,
) -> dict:
    """Garantit l'existence de l'énigme solo quotidienne et de ses indices IA."""
    today_str = puzzle_date or get_current_paris_date()
    puzzle = get_solo_daily_puzzle(today_str)

    if not puzzle:
        log(f"🎲  [SOLO] Aucun mot du jour consigné pour le {today_str} : tirage au sort...")
        # Tirage d'un nouveau mot avec distribution pondérée
        if manager is None:
            from ..game.manager import GameManager
            from ..engine.vocab import VocabStore
            active_store = store or VocabStore()
            active_manager = GameManager(active_store)
        else:
            active_manager = manager

        secret_word, difficulty = active_manager.draw_solo_daily_word()
        puzzle = get_or_create_solo_daily_puzzle(
            puzzle_date=today_str,
            secret_word=secret_word,
            difficulty=difficulty,
        )
        log(f"✨  [SOLO] Nouveau mot du jour tiré : « {secret_word.upper()} » (Difficulté: {difficulty.upper()})")

    # Génération et persistance des indices IA si absents ou à calibrer
    secret_word = puzzle["secret_word"]
    existing_hints = get_solo_ai_hints(today_str)
    needs_generation = False
    if not existing_hints or len(existing_hints) < 3:
        needs_generation = True
    else:
        h1 = next((h for h in existing_hints if h.get("hint_level") == 1), None)
        h2 = next((h for h in existing_hints if h.get("hint_level") == 2), None)
        h3 = next((h for h in existing_hints if h.get("hint_level") == 3), None)

        p1 = h1.get("permille") if h1 else None
        p2 = h2.get("permille") if h2 else None
        p3 = h3.get("permille") if h3 else None

        # Exigence stricte : p1 ~350-500, p2 ~500-750, p3 > 900, et p1 < p2 < p3 croissant
        if not (
            p1 is not None and p2 is not None and p3 is not None
            and 300 <= p1 <= 550
            and 450 <= p2 <= 800
            and p3 >= 850
            and p1 < p2 < p3
        ):
            needs_generation = True

    if needs_generation:
        _generate_and_store_hints(today_str, secret_word, store)

    # Purge quotidienne unique des jours passés (< date du jour)
    maybe_purge_old_daily_data(today_str)

    return puzzle


def _find_word_at_permille(
    store: Any,
    norm_secret: str,
    target_permille: int = 500,
    excluded_words: Optional[set] = None,
    min_permille: Optional[int] = None,
    max_permille: Optional[int] = None,
) -> tuple[Optional[str], float, Optional[int]]:
    """Sélectionne dans l'espace vectoriel un mot français valide calibré au millième cible."""
    if not store or norm_secret not in store:
        return None, 0.0, None

    v_sec = store.vec(norm_secret)
    all_cos = store.vecs @ v_sec
    k = min(1000, len(all_cos))
    threshold = float(np.partition(all_cos, -k)[-k])
    top_scores = np.sort(all_cos[all_cos >= threshold])

    secret_stem = norm_secret[:min(4, len(norm_secret))]
    top_indices = np.argsort(all_cos)[-1000:]

    excluded = {norm_secret}
    if excluded_words:
        excluded.update(str(w).strip().lower() for w in excluded_words if w)

    candidates = []
    for idx in top_indices:
        w = store.words[idx]
        if w in excluded:
            continue
        if len(w) < 4 or w in STOPWORDS:
            continue
        if "-" in w or "_" in w:
            continue
        if w.startswith(secret_stem) or norm_secret.startswith(w[:min(4, len(w))]):
            continue
        if not store.is_valid_french(w):
            continue

        s = float(all_cos[idx])
        rank = int(np.searchsorted(top_scores, s))
        rank = min(999, max(1, rank))
        candidates.append((w, s, rank))

    if not candidates:
        return None, 0.0, None

    # Filtrage progressif par bornes min/max
    filtered = candidates
    if min_permille is not None:
        filtered = [c for c in filtered if c[2] >= min_permille]
    if max_permille is not None:
        filtered = [c for c in filtered if c[2] <= max_permille]

    if not filtered and min_permille is not None:
        filtered = [c for c in candidates if c[2] >= min_permille]
    if not filtered:
        filtered = candidates

    best = min(filtered, key=lambda c: abs(c[2] - target_permille))
    return best[0], round(best[1] * 100, 2), best[2]


def _generate_and_store_hints(puzzle_date: str, secret_word: str, store: Any = None) -> None:
    """Génère les 3 indices IA et précalcule leurs scores sémantiques et millièmes croissants :
    - Indice #1 : ~350 - 500‰
    - Indice #2 : ~500 - 750‰
    - Indice #3 : > 900‰
    """
    if store is None:
        from ..engine.vocab import VocabStore
        store = VocabStore(with_chroma=False)

    from .ai_hints import generate_calibrated_ai_hints
    client = GeminiClient()
    hints_to_save: Optional[List[Dict[str, Any]]] = None

    if client.is_configured():
        hints_to_save = generate_calibrated_ai_hints(secret_word, store=store, client=client, max_calls=5)

    # Repli algorithmique si Gemini indisponible ou incomplet
    if not hints_to_save or len(hints_to_save) < 3:
        norm_secret = store.normalize(secret_word)
        w1, s1, p1 = _find_word_at_permille(store, norm_secret, target_permille=425, min_permille=350, max_permille=500)
        w2, s2, p2 = _find_word_at_permille(store, norm_secret, target_permille=625, min_permille=max(500, (p1 or 400) + 20), max_permille=750, excluded_words={w1})
        w3, s3, p3 = _find_word_at_permille(store, norm_secret, target_permille=930, min_permille=max(901, (p2 or 700) + 15), max_permille=980, excluded_words={w1, w2})

        hints_to_save = [
            {
                "hint_level": 1,
                "weight": 0.33,
                "hint_word": w1 or "concept",
                "hint_phrase": "Une piste générale liée au domaine de l'énigme.",
                "score": s1,
                "permille": p1,
            },
            {
                "hint_level": 2,
                "weight": 0.66,
                "hint_word": w2 or "usage",
                "hint_phrase": "Une action ou un contexte d'usage fréquemment associé.",
                "score": s2,
                "permille": p2,
            },
            {
                "hint_level": 3,
                "weight": 1.00,
                "hint_word": w3 or "analogie",
                "hint_phrase": "Un élément marquant très proche sémantiquement.",
                "score": s3,
                "permille": p3,
            },
        ]

    if hints_to_save:
        save_solo_ai_hints(puzzle_date, hints_to_save)
        h1 = next((h for h in hints_to_save if h.get("hint_level") == 1), {})
        h2 = next((h for h in hints_to_save if h.get("hint_level") == 2), {})
        h3 = next((h for h in hints_to_save if h.get("hint_level") == 3), {})
        log(f"💡  [SOLO] 3 indices IA enregistrés pour le {puzzle_date} : #1 {h1.get('hint_word')} ({h1.get('permille')}‰) < #2 {h2.get('hint_word')} ({h2.get('permille')}‰) < #3 {h3.get('hint_word')} ({h3.get('permille')}‰).")


def simulate_solo_daily_bots(
    store: Any = None,
    force: bool = False,
    client: Optional[Any] = None,
    bot_names: Optional[List[str]] = None,
    puzzle_date: Optional[str] = None,
) -> dict:
    """Déclenche la simulation des 7 à 10 habitués avec vérification des verrous et calibration."""
    if store is None:
        from ..engine.vocab import VocabStore
        store = VocabStore(with_chroma=False)

    today_str = puzzle_date or get_current_paris_date()
    puzzle = ensure_solo_daily_puzzle(store, puzzle_date=today_str)
    secret_word = puzzle["secret_word"]
    difficulty = puzzle["difficulty"]

    # 1. Vérification du verrou d'idempotence
    if is_solo_bots_simulated(today_str) and not force:
        log(f"ℹ️  [BOTS] Simulation déjà effectuée aujourd'hui pour le {today_str} (verrou actif).")
        return {"simulated": False, "reason": "already_simulated", "puzzle_date": today_str}

    # 2. Vérification de la présence d'un vainqueur humain
    if has_real_player_won(today_str) and not force:
        log(f"ℹ️  [BOTS] Un joueur humain a déjà résolu le mot du {today_str} : simulation annulée.")
        return {"simulated": False, "reason": "human_already_won", "puzzle_date": today_str}

    if force:
        clear_solo_bots_simulated(today_str)

    log(f"🤖  [BOTS] Déclenchement de la simulation des habitués ({difficulty}) pour le {today_str}...")
    seed_bot_players_if_empty()

    # Génération groupée des trajectoires
    bot_results = simulate_batch_trajectories(
        secret_word=secret_word,
        difficulty=difficulty,
        puzzle_date=today_str,
        store=store,
        client=client,
        bot_names=bot_names,
    )

    persisted_count = 0
    for bot in bot_results:
        try:
            finish_solo_player_game(
                puzzle_date=today_str,
                player_id=bot["player_id"],
                status=bot["status"],
                tries_count=bot["tries_count"],
                duration_seconds=bot["duration_seconds"],
                best_score=bot["best_score"],
                best_permille=bot["best_permille"],
                guesses=bot["guesses"],
                is_bot=True,
            )
            persisted_count += 1
        except Exception as e:
            log(f"⚠️  [BOTS] Erreur persistance pour {bot['username']} : {e}")

    # Activation du verrou d'idempotence
    lock_solo_bots_simulated(today_str)
    log(f"🏁  [BOTS] Simulation achevée : {persisted_count} joueurs habitués enregistrés pour le {today_str}.")

    return {
        "simulated": True,
        "count": persisted_count,
        "puzzle_date": today_str,
        "difficulty": difficulty,
    }


def check_and_run_startup_simulation(
    store: Any = None,
    now: Optional[datetime] = None,
    puzzle_date: Optional[str] = None,
) -> Optional[dict]:
    """Au démarrage du conteneur Docker :
    1. Garantit l'existence du mot du jour et de ses indices IA (ensure_solo_daily_puzzle).
    2. Si l'heure courante (Europe/Paris) est > 06h30 et que rien ne figure
       dans la table du jour (`solo_player_games`), lance la procédure de remplissage des habitués.
    """
    paris_now = now or datetime.now(PARIS_TZ)
    today_str = puzzle_date or paris_now.strftime("%Y-%m-%d")

    # Assure le tirage du mot du jour et la génération des indices IA
    puzzle = ensure_solo_daily_puzzle(store, puzzle_date=today_str)

    # Condition horaire : heure courante > 6h30am Paris
    is_after_630 = (paris_now.hour > 6) or (paris_now.hour == 6 and paris_now.minute >= 30)
    if not is_after_630:
        log(f"⏰  [STARTUP DOCKER] Heure ({paris_now.strftime('%H:%M')}) <= 06h30 : pas de simulation des habitués au démarrage.")
        return None

    # Vérification si des bots habitués ont déjà été consignés pour le jour
    engine = db.get_engine_type()
    bot_filter = "is_bot = TRUE" if engine == "postgres" else "is_bot = 1"
    row = db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM solo_player_games WHERE puzzle_date = %s AND {bot_filter}",
        (today_str,),
    )
    bots_count = int(row["cnt"]) if row and "cnt" in row else 0

    if bots_count == 0:
        log(f"🚀  [STARTUP DOCKER] Heure ({paris_now.strftime('%H:%M')}) > 06h30 et aucun habitué consigné ({today_str}) -> Lancement de la procédure de remplissage...")
        return simulate_solo_daily_bots(store, force=True, puzzle_date=today_str)
    else:
        log(f"ℹ️  [STARTUP DOCKER] Table solo du jour ({today_str}) déjà pourvue ({bots_count} bot(s)) -> aucun remplissage requis.")
        return None
