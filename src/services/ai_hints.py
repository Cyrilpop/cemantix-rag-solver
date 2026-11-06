"""
Service d'orchestration et de persistance des indices IA Google Gemini (M12).
"""
from typing import Any, Dict, List, Optional

from ..ai import GeminiClient
from ..db import (
    get_all_daily_puzzles,
    get_daily_ai_hints,
    get_daily_puzzle,
    get_latest_daily_puzzle,
    has_daily_ai_hints,
    save_daily_ai_hints,
)

try:
    from ..config import log
except ImportError:
    def log(msg: str) -> None:
        print(msg)


def generate_and_store_ai_hints(
    puzzle_date: str,
    secret_word: str,
    force: bool = False,
    client: Optional[GeminiClient] = None,
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

    hints = ai_client.request_hints(clean_secret)
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
