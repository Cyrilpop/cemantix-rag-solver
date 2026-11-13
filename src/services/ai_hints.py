"""
Service d'orchestration et de persistance des indices IA Google Gemini (M12).
"""
import itertools
from typing import Any, Dict, List, Optional

from ..ai import GeminiClient, build_user_prompt
from ..db import (
    get_all_daily_puzzles,
    get_daily_ai_hints,
    get_daily_puzzle,
    get_latest_daily_puzzle,
    has_daily_ai_hints,
    save_daily_ai_hints,
)
from ..engine.ranking import WordScorer

try:
    from ..config import log
except ImportError:
    def log(msg: str) -> None:
        print(msg)


def _evaluate_triplet(c1: Dict[str, Any], c2: Dict[str, Any], c3: Dict[str, Any]) -> tuple[bool, float]:
    """Évalue si un triplet de candidats satisfait les contraintes cibles strictes :
    c1 dans [350, 500], c2 dans [500, 750], c3 > 900, et p1 < p2 < p3.
    Retourne (est_valide, score_distance).
    """
    p1 = c1.get("permille")
    p2 = c2.get("permille")
    p3 = c3.get("permille")

    if p1 is None or p2 is None or p3 is None:
        return False, float("inf")

    # Strictement croissant
    if not (p1 < p2 < p3):
        return False, float("inf")

    # Plages cibles
    if not (350 <= p1 <= 500 and 500 <= p2 <= 750 and p3 > 900):
        return False, float("inf")

    # Distance aux centres cibles (425, 625, 950)
    dist = abs(p1 - 425) + abs(p2 - 625) + abs(p3 - 950)
    return True, dist


def _triplet_fallback_cost(c1: Dict[str, Any], c2: Dict[str, Any], c3: Dict[str, Any]) -> float:
    """Calcule le coût de pénalité d'un triplet ordonné par rapport aux plages idéales :
    - c1 idéalement [350, 500] (centre 425)
    - c2 idéalement [500, 750] (centre 625)
    - c3 idéalement > 900 (centre 950)
    """
    def _val(c):
        if c.get("permille") is not None:
            return float(c["permille"])
        return float(c.get("score") or 0.0) - 1000.0

    v1, v2, v3 = _val(c1), _val(c2), _val(c3)
    if not (v1 < v2 < v3):
        return float("inf")

    def _pen(v, low, high):
        if v < low:
            return low - v
        if v > high:
            return v - high
        return 0.0

    pen1 = _pen(v1, 350.0, 500.0)
    pen2 = _pen(v2, 500.0, 750.0)
    pen3 = _pen(v3, 901.0, 1000.0)

    # Forte pénalité pour non-respect des plages, plus écart fin aux centres idéaux
    cost = (pen1 + pen2 + pen3) * 1000.0 + abs(v1 - 425.0) + abs(v2 - 625.0) + abs(v3 - 950.0)
    return cost


def generate_calibrated_ai_hints(
    secret_word: str,
    store: Optional[Any] = None,
    client: Optional[GeminiClient] = None,
    max_calls: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """Génère 3 indices IA avec calibrage sémantique strict de la température/millièmes :
    - Indice #1 : ~350 - 500 millièmes (zone tiède, weight 0.33)
    - Indice #2 : ~500 - 750 millièmes (zone chaude, weight 0.66)
    - Indice #3 : > 900 millièmes (zone brûlante, weight 1.00)

    Processus :
    1. Si l'IA répond 3 indices respectant ces plages mais désordonnés, réorganisation croissante.
    2. Si les indices ne sont pas dans les plages souhaitées, nouvelle requête (avec feedback)
       jusqu'à concurrence de 5 appels max (sécurité quota).
    3. Si après 5 appels aucune combinaison parfaite n'est atteinte, sélection des 3 candidats
       disponibles les plus proches des cibles dans un ordre strictement croissant (p1 < p2 < p3).
    4. Intégrité stricte mot/phrase : la phrase est liée à son mot d'origine et n'est jamais dissociée.
    """
    clean_secret = str(secret_word or "").strip()
    if not clean_secret:
        log("⚠️  [AI] Mot secret vide fourni pour generate_calibrated_ai_hints.")
        return None

    ai_client = client or GeminiClient()
    if not ai_client.is_configured():
        log("⚠️  [AI] Client Gemini non configuré. Génération annulée.")
        return None

    scorer = None
    if store is not None:
        scorer = WordScorer(clean_secret, store)

    if scorer is None:
        # Aucun VocabStore fourni : un seul appel direct sans calibrage vectoriel
        raw = ai_client.request_hints(clean_secret)
        return raw

    candidate_pool: List[Dict[str, Any]] = []
    seen_words: set[str] = set()
    feedback: Optional[str] = None

    for attempt in range(1, max_calls + 1):
        prompt_text = build_user_prompt(clean_secret, feedback=feedback) if feedback else None
        log(f"🧠  [AI] Appel Gemini pour '{clean_secret}' (tentative {attempt}/{max_calls})...")
        raw_hints = ai_client.generate_hints(clean_secret, user_prompt=prompt_text)

        if raw_hints:
            for h in raw_hints:
                w = str(h.get("word") or h.get("hint_word") or "").strip().lower()
                ph = str(h.get("phrase") or h.get("hint_phrase") or "").strip()
                if not w or not ph:
                    continue
                if w in seen_words:
                    continue
                score, permille = scorer.score(w)
                candidate_pool.append({
                    "word": w,
                    "hint_word": w,
                    "phrase": ph,
                    "hint_phrase": ph,
                    "score": score,
                    "permille": permille,
                    "model": str(h.get("model") or "gemini-3.8-flash"),
                })
                seen_words.add(w)

        # Recherche d'un triplet parfait dans le pool accumulé
        if len(candidate_pool) >= 3:
            best_triplet = None
            best_dist = float("inf")
            for trip in itertools.permutations(candidate_pool, 3):
                is_valid, dist = _evaluate_triplet(*trip)
                if is_valid and dist < best_dist:
                    best_dist = dist
                    best_triplet = trip

            if best_triplet is not None:
                log(f"✨  [AI] Triplet d'indices calibré trouvé à la tentative {attempt}/{max_calls} : "
                    f"#1 {best_triplet[0]['word']} ({best_triplet[0]['permille']}‰) < "
                    f"#2 {best_triplet[1]['word']} ({best_triplet[1]['permille']}‰) < "
                    f"#3 {best_triplet[2]['word']} ({best_triplet[2]['permille']}‰).")
                return [
                    {
                        "hint_level": 1,
                        "level": 1,
                        "weight": 0.33,
                        "hint_word": best_triplet[0]["word"],
                        "word": best_triplet[0]["word"],
                        "hint_phrase": best_triplet[0]["phrase"],
                        "phrase": best_triplet[0]["phrase"],
                        "score": best_triplet[0]["score"],
                        "permille": best_triplet[0]["permille"],
                        "model": best_triplet[0]["model"],
                    },
                    {
                        "hint_level": 2,
                        "level": 2,
                        "weight": 0.66,
                        "hint_word": best_triplet[1]["word"],
                        "word": best_triplet[1]["word"],
                        "hint_phrase": best_triplet[1]["phrase"],
                        "phrase": best_triplet[1]["phrase"],
                        "score": best_triplet[1]["score"],
                        "permille": best_triplet[1]["permille"],
                        "model": best_triplet[1]["model"],
                    },
                    {
                        "hint_level": 3,
                        "level": 3,
                        "weight": 1.00,
                        "hint_word": best_triplet[2]["word"],
                        "word": best_triplet[2]["word"],
                        "hint_phrase": best_triplet[2]["phrase"],
                        "phrase": best_triplet[2]["phrase"],
                        "score": best_triplet[2]["score"],
                        "permille": best_triplet[2]["permille"],
                        "model": best_triplet[2]["model"],
                    },
                ]

        # Pas de triplet parfait : préparer feedback pour la tentative suivante
        if attempt < max_calls:
            missing = []
            has_t1 = any(c.get("permille") is not None and 350 <= c["permille"] <= 500 for c in candidate_pool)
            has_t2 = any(c.get("permille") is not None and 500 <= c["permille"] <= 750 for c in candidate_pool)
            has_t3 = any(c.get("permille") is not None and c["permille"] > 900 for c in candidate_pool)

            if not has_t1:
                missing.append("Niveau 1 (~350 à 500 millièmes)")
            if not has_t2:
                missing.append("Niveau 2 (~500 à 750 millièmes)")
            if not has_t3:
                missing.append("Niveau 3 (> 900 millièmes)")

            if missing:
                feedback = f"Il manque des indices dans les plages thermiques suivantes : {', '.join(missing)}."
            else:
                feedback = "Veille à ce que les températures soient strictement croissantes et dans les plages 350-500‰, 500-750‰ et >900‰."

    # Repli après épuisement du quota (max_calls atteint) : sélection des 3 candidats les plus proches
    if len(candidate_pool) >= 3:
        best_fallback_triplet = None
        best_cost = float("inf")
        for trip in itertools.permutations(candidate_pool, 3):
            cost = _triplet_fallback_cost(*trip)
            if cost < best_cost:
                best_cost = cost
                best_fallback_triplet = trip

        if best_fallback_triplet is not None:
            log(f"⚠️  [AI] Quota de {max_calls} appels atteint sans triplet parfait : sélection de repli ordonnée ("
                f"#1 {best_fallback_triplet[0]['word']} ({best_fallback_triplet[0]['permille']}‰) < "
                f"#2 {best_fallback_triplet[1]['word']} ({best_fallback_triplet[1]['permille']}‰) < "
                f"#3 {best_fallback_triplet[2]['word']} ({best_fallback_triplet[2]['permille']}‰)).")
            return [
                {
                    "hint_level": 1,
                    "level": 1,
                    "weight": 0.33,
                    "hint_word": best_fallback_triplet[0]["word"],
                    "word": best_fallback_triplet[0]["word"],
                    "hint_phrase": best_fallback_triplet[0]["phrase"],
                    "phrase": best_fallback_triplet[0]["phrase"],
                    "score": best_fallback_triplet[0]["score"],
                    "permille": best_fallback_triplet[0]["permille"],
                    "model": best_fallback_triplet[0]["model"],
                },
                {
                    "hint_level": 2,
                    "level": 2,
                    "weight": 0.66,
                    "hint_word": best_fallback_triplet[1]["word"],
                    "word": best_fallback_triplet[1]["word"],
                    "hint_phrase": best_fallback_triplet[1]["phrase"],
                    "phrase": best_fallback_triplet[1]["phrase"],
                    "score": best_fallback_triplet[1]["score"],
                    "permille": best_fallback_triplet[1]["permille"],
                    "model": best_fallback_triplet[1]["model"],
                },
                {
                    "hint_level": 3,
                    "level": 3,
                    "weight": 1.00,
                    "hint_word": best_fallback_triplet[2]["word"],
                    "word": best_fallback_triplet[2]["word"],
                    "hint_phrase": best_fallback_triplet[2]["phrase"],
                    "phrase": best_fallback_triplet[2]["phrase"],
                    "score": best_fallback_triplet[2]["score"],
                    "permille": best_fallback_triplet[2]["permille"],
                    "model": best_fallback_triplet[2]["model"],
                },
            ]

    # Si le pool a moins de 3 candidats (échec total API)
    log(f"❌  [AI] Échec : moins de 3 candidats valides obtenus après {max_calls} appels.")
    return None


def generate_and_store_ai_hints(
    puzzle_date: str,
    secret_word: str,
    force: bool = False,
    client: Optional[GeminiClient] = None,
    store: Optional[Any] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Génère et stocke les indices IA pour un puzzle quotidien de façon idempotente.

    Règle stricte anti-gaspillage : si on a déjà les indices pour le même mot à la même date
    et que force=False, aucun appel à l'API Gemini n'est effectué et les indices existants sont retournés.
    """
    if not puzzle_date or not secret_word:
        log("⚠️  [AI] Paramètres manquants pour generate_and_store_ai_hints.")
        return None

    date_str = str(puzzle_date)
    clean_secret = str(secret_word).strip()

    # Vérification d'existence préalable : si les indices existent déjà pour cette date et ce mot
    if not force and has_daily_ai_hints(date_str):
        existing = get_daily_ai_hints(date_str)
        if existing and len(existing) >= 3:
            puzzle = get_daily_puzzle(date_str)
            if puzzle:
                stored_word = str(puzzle.get("secret_word") or puzzle.get("word") or "").strip().lower()
                # Si le puzzle en base a un mot différent, on régénère ; sinon on réutilise sans appel API
                if not stored_word or stored_word == clean_secret.lower():
                    log(f"ℹ️  [AI] Indices IA déjà complets ({len(existing)} indices) pour le mot '{clean_secret}' du {date_str}, appel API Gemini ignoré.")
                    return existing
            else:
                log(f"ℹ️  [AI] Indices IA déjà existants ({len(existing)} indices) pour le {date_str}, appel API Gemini ignoré.")
                return existing

    ai_client = client or GeminiClient()
    if not ai_client.is_configured():
        log("⚠️  [AI] Client Gemini non configuré (GEMINI_API_KEY absente). Génération abandonnée.")
        return None

    hints = generate_calibrated_ai_hints(clean_secret, store=store, client=ai_client, max_calls=5)
    if not hints:
        log(f"⚠️  [AI] Impossible de générer les indices IA pour le {date_str} (mot='{clean_secret}').")
        return None

    save_daily_ai_hints(date_str, hints)
    log(f"✨  [AI] {len(hints)} indices IA enregistrés avec succès pour le {date_str}.")
    return hints


def backfill_ai_hints(force: bool = False, limit: Optional[int] = None) -> int:
    """Rattrapage idempotent des indices IA pour l'ensemble des puzzles quotidiens."""
    puzzles = get_all_daily_puzzles(limit=limit)
    if not puzzles:
        # Repli si base vide ou chargement via historique
        try:
            from .daemon import load_history
            puzzles = load_history()
        except Exception:
            puzzles = []

    if not puzzles:
        log("ℹ️  [AI] Aucun puzzle trouvé pour le rattrapage des indices IA.")
        return 0

    to_process = []
    for p in puzzles:
        date_str = str(p.get("date") or "")
        word = str(p.get("secret_word") or p.get("word") or "").strip()
        if not date_str or not word:
            continue
        if not force and has_daily_ai_hints(date_str):
            continue
        to_process.append((date_str, word))

    if not to_process:
        log("✓  [AI] Tous les puzzles possèdent déjà leurs indices IA Gemini, aucun appel nécessaire.")
        return 0

    client = GeminiClient()
    if not client.is_configured():
        log("⚠️  [AI] Clé GEMINI_API_KEY absente, impossible d'exécuter le backfill.")
        return 0

    count = 0
    for date_str, word in to_process:
        res = generate_and_store_ai_hints(date_str, word, force=force, client=client)
        if res:
            count += 1

    log(f"✨  [AI] Rattrapage terminé : indices générés pour {count} puzzle(s).")
    return count


def _print_hints_summary(puzzle_date: str, secret_word: str, hints: List[Dict[str, Any]]) -> None:
    """Affiche un récapitulatif formaté des indices générés dans la console."""
    print("\n" + "=" * 65)
    print(f"✨  INDICES IA GOOGLE GEMINI — CÉMANTIX ({puzzle_date})")
    print(f"🎯  Mot secret : {secret_word}")
    print("=" * 65)
    for h in hints:
        level = h.get("hint_level", h.get("level"))
        weight = float(h.get("weight", 0.0))
        word = h.get("hint_word", h.get("word", ""))
        phrase = h.get("hint_phrase", h.get("phrase", ""))
        print(f"📍 Niveau {level} (poids {weight:.2f}) :")
        print(f"   • Mot repère   : {word}")
        print(f"   • Phrase guide : {phrase}")
    print("=" * 65 + "\n")


def generate_ai_hints_cli(target_date: Optional[str] = None, force: bool = False) -> None:
    """Point d'entrée pour la commande CLI --generate-ai-hints."""
    entry = None
    if target_date:
        entry = get_daily_puzzle(target_date)
        if not entry:
            try:
                from .daemon import load_history
                for item in load_history():
                    if str(item.get("date")) == target_date:
                        entry = item
                        break
            except Exception:
                pass
        if not entry:
            log(f"❌  [AI] Aucun puzzle trouvé en base ou dans l'historique pour la date : {target_date}")
            return
    else:
        entry = get_latest_daily_puzzle(winning_only=False)
        if not entry:
            try:
                from .daemon import load_history
                h = load_history()
                if h:
                    entry = h[-1]
            except Exception:
                pass

    if not entry:
        log("❌  [AI] Aucun puzzle disponible pour générer des indices IA.")
        return

    p_date = str(entry.get("date"))
    secret_word = str(entry.get("secret_word") or entry.get("word") or "").strip()

    if not secret_word:
        log(f"❌  [AI] Mot secret absent pour le puzzle du {p_date}.")
        return

    if not force and has_daily_ai_hints(p_date):
        log(f"📋  [AI] Indices IA déjà présents en base pour le mot '{secret_word}' du {p_date} (force=False). Récupération immédiate sans appel API.")
    else:
        log(f"🧠  [AI] Appel à l'API Gemini pour générer les indices du {p_date} (mot='{secret_word}', force={force})...")

    hints = generate_and_store_ai_hints(p_date, secret_word, force=force)
    if hints:
        _print_hints_summary(p_date, secret_word, hints)
    else:
        log("❌  [AI] Échec de la génération des indices IA.")
