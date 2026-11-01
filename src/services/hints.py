"""
Cémantix Solver — Service de Génération et Rattrapage des Indices Quotidiens
===========================================================================
Génère les indices gradués par paliers thermiques (800, 900, 950, 990)
via l'espace vectoriel word2vec local (RAG) et assure le rattrapage
idempotent des puzzles historiques dans daily_puzzle_hints.
"""
from typing import Optional, TYPE_CHECKING
import numpy as np

from ..config import STOPWORDS, log
from ..db import db, save_daily_hints, get_all_daily_puzzles

if TYPE_CHECKING:
    from ..engine.vocab import VocabStore


# Paliers cibles et similarités associées dans le Top 1000 :
# - Tier "800" : entrée dans la zone chaude (~820‰)
# - Tier "900" : zone très chaude (~890‰ et ~920‰)
# - Tier "950" : zone brûlante (~960‰)
# - Tier "990" : voisins immédiats (~990‰)
DEFAULT_TIER_TARGETS = [
    ("800", 820),
    ("900", 890),
    ("900", 920),
    ("950", 960),
    ("990", 990),
]


def generate_hints_for_word(
    secret_word: str,
    store: "VocabStore",
    tier_targets: Optional[list[tuple[str, int]]] = None,
) -> list[dict]:
    """Génère les indices gradués par paliers pour un mot secret donné."""
    if not secret_word:
        return []

    secret_clean = secret_word.strip().lower()
    secret_norm = store.normalize(secret_clean) if hasattr(store, "normalize") else secret_clean
    if secret_norm not in store:
        return []

    targets = tier_targets or DEFAULT_TIER_TARGETS

    v_sec = store.vec(secret_norm)
    all_cos = store.vecs @ v_sec
    k = min(1000, len(all_cos))
    threshold = float(np.partition(all_cos, -k)[-k])
    top_scores = np.sort(all_cos[all_cos >= threshold])

    secret_stem = secret_norm[:min(4, len(secret_norm))]
    top_indices = np.argsort(all_cos)[-1000:]

    candidates = []
    for idx in top_indices:
        w = store.words[idx]
        if w == secret_norm:
            continue
        if len(w) < 4 or w in STOPWORDS:
            continue
        if "-" in w or "_" in w:
            continue
        if w.startswith(secret_stem) or secret_norm.startswith(w[:min(4, len(w))]):
            continue
        if not store.is_valid_french(w):
            continue

        s = float(all_cos[idx])
        rank = int(np.searchsorted(top_scores, s))
        rank = min(999, max(1, rank))
        candidates.append((w, s, rank))

    if not candidates:
        return []

    selected_words = set()
    hints = []
    for tier, target in targets:
        available = [c for c in candidates if c[0] not in selected_words]
        if not available:
            continue
        best = min(available, key=lambda x: abs(x[2] - target))
        selected_words.add(best[0])
        hints.append({
            "tier": tier,
            "word": best[0],
            "score": float(best[2]),
            "is_revealed": False,
        })

    return hints


def backfill_puzzle_hints(store: Optional["VocabStore"] = None) -> int:
    """Rattrapage idempotent des indices pour tous les puzzles quotidiens en base.

    Pour chaque puzzle dans daily_puzzles :
    - Si daily_puzzle_hints contient déjà des indices pour cette date, le puzzle est ignoré.
    - Sinon, les indices sont générés via VocabStore et persistés.
    """
    # 1. Vérification des puzzles déjà traités (idempotence)
    query_existing = "SELECT DISTINCT puzzle_date FROM daily_puzzle_hints;"
    try:
        rows = db.fetch_all(query_existing)
        existing_dates = {str(r["puzzle_date"]) for r in rows}
    except Exception as e:
        log(f"⚠️  [HINTS] Impossible de vérifier les indices existants : {e}")
        existing_dates = set()

    # 2. Récupération des puzzles quotidiens enregistrés
    puzzles = get_all_daily_puzzles(limit=None, include_trajectory=False)
    if not puzzles:
        return 0

    to_backfill = [
        p for p in puzzles
        if str(p.get("date")) not in existing_dates and (p.get("word") or "").strip()
    ]

    if not to_backfill:
        log("✓  [HINTS] Tous les puzzles possèdent déjà leurs indices (rattrapage idempotent à jour).")
        return 0

    log(f"🚀  [HINTS] Rattrapage de {len(to_backfill)} puzzle(s) sans indices via le RAG local...")
    if store is None:
        from ..engine.vocab import VocabStore
        store = VocabStore(with_chroma=False)

    count_puzzles = 0
    total_hints = 0
    for p in to_backfill:
        p_date = str(p.get("date"))
        secret = str(p.get("word")).strip()
        hints = generate_hints_for_word(secret, store)
        if hints:
            inserted = save_daily_hints(p_date, hints)
            count_puzzles += 1
            total_hints += inserted

    log(f"✨  [HINTS] Rattrapage achevé : {total_hints} indices enregistrés pour {count_puzzles} puzzle(s).")
    return count_puzzles


def bootstrap_database(store: Optional["VocabStore"] = None, history_file: Optional[object] = None) -> dict:
    """Initialisation complète et strictement idempotente de la base de données.

    Exécutée à chaque démarrage de conteneur (worker ou API web) :
    1. init_db() : garantit que toutes les tables et index SQL (PG_SCHEMA / SQLITE_SCHEMA)
       sont créés / mis à jour sans nécessiter d'intervention manuelle.
    2. backfill_daily_puzzles_from_json() : importe de façon idempotente les puzzles
       depuis daily_history.json vers la table daily_puzzles si des puzzles manquent en base.
    3. backfill_puzzle_hints(store) : calcule et persiste les indices dans
       daily_puzzle_hints pour tous les puzzles quotidiens qui n'en ont pas encore.
    """
    from ..db import init_db, backfill_daily_puzzles_from_json

    # 1. Schéma DDL multi-dialecte (Postgres / SQLite)
    init_db()

    # 2. Rattrapage JSON -> daily_puzzles
    puzzles_count = backfill_daily_puzzles_from_json(history_file)

    # 3. Rattrapage RAG -> daily_puzzle_hints
    hints_puzzles_count = backfill_puzzle_hints(store)

    return {
        "puzzles_backfilled": puzzles_count,
        "hints_puzzles_backfilled": hints_puzzles_count,
    }



