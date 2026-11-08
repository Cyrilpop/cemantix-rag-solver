"""
Cémantix Solver — Simulation IA de Faux Joueurs Réalistes (Jalon M15)
====================================================================
Simule les trajectoires sémantiques crédibles d'un échantillon de 7 à 10 joueurs
issus du pool fixe des 20 habitués si aucun humain n'a encore gagné à 6h30.
Orchestre un appel groupé (batch JSON) vers Gemini avec repli algorithmique local.
"""
import json
import random
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np

from ..config import log
from ..db.players import FIXED_BOT_HABITUES, get_bot_uuid
from ..game.common import get_weather_tier


# Taux de succès calibrés selon la difficulté du jour
DIFFICULTY_WIN_RATES = {
    "facile": 0.95,
    "normal": 0.75,
    "moyen": 0.75,
    "difficile": 0.25,
    "expert": 0.25,
    "extreme": 0.05,
}

SYSTEM_PROMPT_BOT_TRAJECTORIES = """Tu es un simulateur réaliste de joueurs humains pour le jeu linguistique Cémantix en français.
Dans Cémantix, le but est de trouver un mot secret français par proximité sémantique (Word2Vec).
Chaque joueur propose des mots successifs : le jeu lui indique la température sémantique.
Un joueur humain ne joue PAS comme un algorithme froid :
- Il démarre par des mots exploratoires variés (lieux, objets, actions, émotions).
- Quand il trouve une piste chaude, il creuse dans ce champ lexical.
- Parfois il s'égare sur une fausse piste sémantique ou teste un mot sans rapport.
- Les gagnants finissent par converger vers le mot secret en 35 à 75 mots.
- Les perdants (abandons) explorent 1 ou 2 fausses pistes, stagnent dans une zone tiède/froide, se découragent et abandonnent sans jamais trouver le mot secret.

RÈGLES STRICTES DE FORMAT :
1. Mots français valides exclusivement (minuscules, sans ponctuation ni chiffres).
2. Pour un joueur avec outcome='won' : le DERNIER mot de sa liste DOIT être exactement le mot secret.
3. Pour un joueur avec outcome='given_up' : le mot secret ne DOIT JAMAIS apparaître dans sa liste.
4. Réponds UNIQUEMENT sous forme d'un objet JSON strict avec la clé "trajectories".
"""


def _sample_habitues(puzzle_date: str, count: Optional[int] = None) -> List[str]:
    """Sélectionne de 7 à 10 joueurs parmi les 20 habitués avec graine déterministe."""
    rng = random.Random(f"habitues_{puzzle_date}")
    n = count if count is not None else rng.randint(7, 10)
    return rng.sample(FIXED_BOT_HABITUES, min(n, len(FIXED_BOT_HABITUES)))


def _plan_bot_players(
    puzzle_date: str,
    difficulty: str,
    sampled_names: List[str],
) -> List[Dict[str, Any]]:
    """Attribue statut (won / given_up) et nombre de coups cibles selon la difficulté."""
    rng = random.Random(f"plan_{puzzle_date}_{difficulty}")
    win_rate = DIFFICULTY_WIN_RATES.get(difficulty.lower(), 0.75)
    plans = []

    for name in sampled_names:
        is_winner = rng.random() < win_rate
        outcome = "won" if is_winner else "given_up"
        target_tries = rng.randint(35, 75) if is_winner else rng.randint(40, 85)
        plans.append({
            "username": name,
            "player_id": get_bot_uuid(name),
            "outcome": outcome,
            "target_tries": target_tries,
        })
    return plans


def _build_batch_prompt(secret_word: str, difficulty: str, plans: List[Dict[str, Any]]) -> str:
    """Construit l'invite groupée pour l'appel unique à Gemini."""
    players_desc = "\n".join(
        f"- {p['username']} : issue={p['outcome']}, cible={p['target_tries']} mots"
        for p in plans
    )
    return f"""Mot secret du jour : "{secret_word}"
Difficulté du jour : {difficulty}

Génère en une seule réponse les trajectoires complètes et réalistes pour les joueurs suivants :
{players_desc}

Format JSON strict attendu :
{{
  "trajectories": [
    {{
      "username": "<nom_joueur>",
      "outcome": "won|given_up",
      "words": ["mot1", "mot2", ..., "motN"]
    }}
  ]
}}"""


def _parse_gemini_trajectories(raw_text: str) -> Dict[str, List[str]]:
    """Extrait les listes de mots par joueur depuis la réponse Gemini."""
    if not raw_text:
        return {}
    cleaned = re.sub(r"```json\s*", "", raw_text)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        # Tentative d'extraction par regex d'un bloc JSON
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return {}
        else:
            return {}

    trajectories = data.get("trajectories") or []
    result = {}
    for item in trajectories:
        username = item.get("username")
        words = item.get("words")
        if username and isinstance(words, list):
            clean_words = []
            for w in words:
                if isinstance(w, str) and w.strip():
                    cw = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", w).strip().lower()
                    if cw:
                        clean_words.append(cw)
            if clean_words:
                result[username] = clean_words
    return result


def _simulate_fallback_trajectory(
    secret_word: str,
    outcome: str,
    target_tries: int,
    store: Any,
    rng: random.Random,
) -> List[str]:
    """Génère localement une trajectoire sémantique crédible sans dépendance réseau."""
    secret = store.normalize(secret_word)
    v_secret = store.vec(secret) if secret in store else None

    # Mots exploratoires de démarrage
    starter_pool = [
        "maison", "temps", "homme", "femme", "monde", "vie", "travail", "corps",
        "terre", "eau", "feu", "air", "jour", "nuit", "argent", "pays", "ville",
        "esprit", "pensée", "chemin", "voiture", "soleil", "livre", "arbre",
    ]
    starters = [w for w in starter_pool if w in store and w != secret]
    rng.shuffle(starters)
    trajectory = starters[:min(6, len(starters))]

    if v_secret is None:
        # Repli si secret absent du vocabulaire
        while len(trajectory) < target_tries:
            cands = store.words if hasattr(store, "words") else starter_pool
            trajectory.append(str(rng.choice(cands)))
        if outcome == "won":
            trajectory.append(secret)
        return trajectory

    if outcome == "won":
        # Trajectoire convergente : marche sémantique progressive vers le secret
        # Recherche de mots d'approche à distances décroissantes
        needed = max(15, target_tries - len(trajectory) - 1)
        # Étape 1 : mot pont tiède
        cands_warm = store.knn(v_secret, k=min(400, len(store.words)))[40:]
        bridge = rng.choice(cands_warm) if cands_warm else "pensée"
        v_bridge = store.vec(store.normalize(bridge))

        for step in range(needed):
            alpha = (step + 1) / float(needed)
            v_inter = (1.0 - alpha) * v_bridge + alpha * v_secret
            norm = np.linalg.norm(v_inter)
            if norm > 0:
                v_inter = v_inter / norm

            neighbors = store.knn(v_inter, k=25)
            # Ajout d'un voisin valide non encore joué
            picked = None
            for cand in neighbors:
                norm_c = store.normalize(cand)
                if norm_c != secret and norm_c not in trajectory and store.is_valid_french(norm_c):
                    picked = norm_c
                    break
            if picked:
                trajectory.append(picked)

        # Dernier coup = mot secret
        trajectory.append(secret)
    else:
        # Trajectoire d'échec / abandon : divagation sur une fausse piste
        needed = max(20, target_tries - len(trajectory))
        false_lead = rng.choice(["musique", "peinture", "cuisine", "espace", "sport", "fleur"])
        false_lead_norm = store.normalize(false_lead)
        v_false = store.vec(false_lead_norm) if false_lead_norm in store else v_secret * -1.0

        for _ in range(needed):
            neighbors = store.knn(v_false, k=40)
            picked = None
            for cand in neighbors:
                norm_c = store.normalize(cand)
                if norm_c != secret and norm_c not in trajectory and store.is_valid_french(norm_c):
                    picked = norm_c
                    break
            if picked:
                trajectory.append(picked)

    return trajectory


def simulate_batch_trajectories(
    secret_word: str,
    difficulty: str,
    puzzle_date: str,
    store: Any,
    client: Optional[Any] = None,
    bot_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Génère et évalue les trajectoires d'un échantillon d'habitués pour le mot secret."""
    sampled_names = bot_names or _sample_habitues(puzzle_date)
    plans = _plan_bot_players(puzzle_date, difficulty, sampled_names)
    rng = random.Random(f"sim_{puzzle_date}_{secret_word}")

    gemini_words = {}
    # Tentative d'appel unique groupé via Gemini
    if client and getattr(client, "is_configured", lambda: False)():
        try:
            prompt = _build_batch_prompt(secret_word, difficulty, plans)
            payload = {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_BOT_TRAJECTORIES}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
            }
            # Appel direct via client ou endpoint
            resp = client._call_endpoint(payload) if hasattr(client, "_call_endpoint") else None
            if resp:
                gemini_words = _parse_gemini_trajectories(resp)
        except Exception as e:
            log(f"⚠️  [SIMULATION] Appel Gemini échoué, repli algorithmique : {e}")

    # Évaluation de chaque joueur simulé
    results = []
    norm_secret = store.normalize(secret_word)
    v_secret = store.vec(norm_secret) if norm_secret in store else None

    # Précalcul des scores pour le secret si disponible
    p1000_threshold = 0.0
    top_scores = np.array([])
    if v_secret is not None:
        all_cos = store.vecs @ v_secret
        k = min(1000, len(all_cos))
        p1000_threshold = float(np.partition(all_cos, -k)[-k])
        top_scores = np.sort(all_cos[all_cos >= p1000_threshold])

    for plan in plans:
        username = plan["username"]
        player_id = plan["player_id"]
        outcome = plan["outcome"]
        target_tries = plan["target_tries"]

        raw_words = gemini_words.get(username)
        if not raw_words or len(raw_words) < 15:
            # Repli sur le générateur local
            raw_words = _simulate_fallback_trajectory(secret_word, outcome, target_tries, store, rng)

        # Assainissement de la trajectoire
        cleaned_trajectory: List[str] = []
        seen = set()
        for w in raw_words:
            nw = store.normalize(w)
            if nw in store and store.is_valid_french(nw) and nw not in seen:
                if outcome == "given_up" and nw == norm_secret:
                    continue  # Un joueur qui abandonne n'a pas trouvé le secret
                cleaned_trajectory.append(nw)
                seen.add(nw)

        if outcome == "won":
            if norm_secret in seen:
                # S'assurer que le secret est en toute fin
                cleaned_trajectory = [w for w in cleaned_trajectory if w != norm_secret]
            cleaned_trajectory.append(norm_secret)

        if not cleaned_trajectory:
            continue

        # Évaluation détaillée de chaque coup
        guesses = []
        best_score = -100.0
        best_permille = None

        for idx, w in enumerate(cleaned_trajectory):
            if w == norm_secret:
                score_deg = 100.0
                permille = 1000
            else:
                s = float(store.vec(w) @ v_secret) if v_secret is not None else 0.0
                score_deg = round(s * 100, 2)
                permille = None
                if s >= p1000_threshold and len(top_scores) > 0:
                    rank = int(np.searchsorted(top_scores, s))
                    scale = 1000.0 / len(top_scores)
                    permille = min(999, max(1, int(rank * scale)))

            if score_deg > best_score:
                best_score = score_deg
                best_permille = permille

            weather = get_weather_tier(score_deg, permille)
            guesses.append({
                "order": idx + 1,
                "word": w,
                "score": score_deg,
                "permille": permille,
                "weather": weather,
                "is_hint": False,
            })

        duration_sec = round(rng.uniform(180, 900), 2)
        results.append({
            "player_id": player_id,
            "username": username,
            "status": outcome,
            "tries_count": len(guesses),
            "duration_seconds": duration_sec,
            "best_score": best_score,
            "best_permille": best_permille,
            "guesses": guesses,
            "is_bot": True,
        })

    return results

