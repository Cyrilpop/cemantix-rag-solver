"""
Cémantix Solver — Couche DAO & Métier du Compte Joueur (Jalon M16)
=================================================================
Gère la persistance et les opérations métier liées à l'espace « Mon compte » :
- Profil utilisateur, traçabilité temporelle (last_login_at, password_updated_at)
- Modification sécurisée du mot de passe avec validation de robustesse
- Mots de récupération aléatoires générés par le système (hachés en BDD)
- Consultation du statut et régénération atomique avec affichage unique
- Agrégation des statistiques de jeu personnelles (parties solo & métriques)
"""
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from ..config import log
from .connection import db
from .players import (
    get_active_dictionary,
    get_player_by_id,
    get_player_by_token,
)

DEFAULT_RECOVERY_WORDS_FALLBACK = [
    "étoile", "montagne", "rivière", "soleil", "lumière", "cascade", "horizon",
    "boussole", "flambeau", "cristal", "aurore", "comète", "galaxie", "sentier",
    "vallée", "océan", "refuge", "falaise", "bosquet", "source", "voyage"
]


def get_account_profile(player_id: str) -> Optional[dict]:
    """Récupère les informations complètes du profil connecté."""
    if not player_id:
        return None

    sql = """
        SELECT id, username, can_change_username, is_claimed, auth_provider,
               created_at, last_seen_at, password_updated_at, last_login_at
        FROM players
        WHERE id = %s
    """
    row = db.fetch_one(sql, (player_id,))
    if not row:
        return None

    def _format_dt(val) -> Optional[str]:
        if not val:
            return None
        if isinstance(val, str):
            return val
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    return {
        "id": str(row["id"]),
        "username": row["username"],
        "canChangeUsername": bool(row["can_change_username"]),
        "isClaimed": bool(row["is_claimed"]),
        "authProvider": row.get("auth_provider", "local"),
        "createdAt": _format_dt(row.get("created_at")),
        "lastSeenAt": _format_dt(row.get("last_seen_at")),
        "passwordUpdatedAt": _format_dt(row.get("password_updated_at")),
        "lastLoginAt": _format_dt(row.get("last_login_at")),
    }


def touch_last_login(player_id: str) -> None:
    """Met à jour l'horodatage de dernière connexion réussie."""
    if not player_id:
        return
    now = datetime.now(timezone.utc)
    sql = """
        UPDATE players
        SET last_login_at = %s, last_seen_at = %s
        WHERE id = %s
    """
    try:
        db.execute(sql, (now, now, player_id))
    except Exception as e:
        log(f"⚠️  [ACCOUNT] Erreur mise à jour last_login_at pour {player_id}: {e}")


def change_account_password(player_id: str, current_password: str, new_password: str) -> Tuple[bool, str]:
    """Modifie le mot de passe du compte après vérification stricte de l'ancien."""
    from ..services.player_auth import hash_password, verify_password

    if not player_id or not current_password or not new_password:
        return False, "Tous les champs de mot de passe sont obligatoires."

    player = get_player_by_id(player_id)
    if not player:
        return False, "Compte introuvable."

    if not player.get("is_claimed") or not player.get("password_hash"):
        return False, "Ce compte invité n'a pas encore été revendiqué avec un mot de passe."

    # Vérification du mot de passe actuel en temps constant
    if not verify_password(current_password, player.get("password_hash")):
        return False, "Le mot de passe actuel est incorrect."

    # Validation du nouveau mot de passe (min 8 caractères)
    new_password = str(new_password).strip()
    if len(new_password) < 8:
        return False, "Le nouveau mot de passe doit comporter au moins 8 caractères."

    new_hash = hash_password(new_password)
    now = datetime.now(timezone.utc)
    sql = """
        UPDATE players
        SET password_hash = %s, password_updated_at = %s, last_seen_at = %s
        WHERE id = %s
    """
    try:
        db.execute(sql, (new_hash, now, now, player_id))
        return True, "Mot de passe mis à jour avec succès."
    except Exception as e:
        log(f"⚠️  [ACCOUNT] Erreur lors de la mise à jour du mot de passe pour {player_id}: {e}")
        return False, "Erreur interne lors de la mise à jour du mot de passe."


def generate_system_recovery_words(count: int = 4) -> List[str]:
    """Sélectionne aléatoirement et cryptographiquement des mots uniques dans le dictionnaire système."""
    pool = get_active_dictionary("recovery")
    if not pool or len(pool) < count:
        pool = list(DEFAULT_RECOVERY_WORDS_FALLBACK)

    selected = set()
    while len(selected) < count and len(selected) < len(pool):
        w = secrets.choice(pool).strip().lower()
        if w:
            selected.add(w)

    return sorted(list(selected))


def save_player_recovery_words(player_id: str, words: List[str]) -> bool:
    """Enregistre atomiquement un nouveau jeu de mots de récupération sous forme de hash."""
    from ..services.player_auth import hash_password

    if not player_id or not words:
        return False

    engine = db.get_engine_type()
    placeholder = "%s" if engine == "postgres" else "?"

    with db.transaction() as conn:
        cursor = conn.cursor()
        # 1. Purge atomique des anciens mots du joueur
        cursor.execute(f"DELETE FROM player_recovery_words WHERE player_id = {placeholder}", (player_id,))

        # 2. Insertion des nouveaux mots hachés
        for w in words:
            normalized_word = w.strip().lower()
            if not normalized_word:
                continue
            word_h = hash_password(normalized_word)
            cursor.execute(
                f"INSERT INTO player_recovery_words (player_id, word_hash) VALUES ({placeholder}, {placeholder})",
                (player_id, word_h),
            )
    return True


def get_recovery_status(player_id: str) -> dict:
    """Consulte le statut de configuration des mots de récupération (sans jamais exposer de mot)."""
    if not player_id:
        return {"configured": False, "count": 0, "createdAt": None}

    sql = """
        SELECT COUNT(*) as count, MIN(created_at) as created_at
        FROM player_recovery_words
        WHERE player_id = %s
    """
    row = db.fetch_one(sql, (player_id,))
    cnt = int(row["count"]) if row and row.get("count") else 0
    created_at = row.get("created_at") if row else None

    # Compatibilité avec le hash initial généré lors du claim M14 (players.recovery_key_hash)
    if cnt == 0:
        player = get_player_by_id(player_id)
        if player and player.get("recovery_key_hash"):
            cnt = 4
            created_at = player.get("created_at")

    if cnt == 0:
        return {"configured": False, "count": 0, "createdAt": None}

    created_at_str = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")

    return {
        "configured": cnt > 0,
        "count": cnt,
        "createdAt": created_at_str or None,
    }


def regenerate_recovery_words(player_id: str, count: int = 4) -> Tuple[bool, str, List[str]]:
    """Régénère un nouveau jeu de mots de récupération aléatoires pour le compte (affichage unique)."""
    if not player_id:
        return False, "Identifiant joueur manquant.", []

    player = get_player_by_id(player_id)
    if not player:
        return False, "Compte introuvable.", []

    if not player.get("is_claimed"):
        return False, "Le compte doit être protégé par mot de passe avant d'activer les mots de récupération.", []

    words = generate_system_recovery_words(count=count)
    if not words or len(words) < count:
        return False, "Impossible de générer le nombre requis de mots de récupération.", []

    success = save_player_recovery_words(player_id, words)
    if not success:
        return False, "Erreur lors de l'enregistrement des mots de récupération.", []

    # Synchronisation de players.recovery_key_hash pour la compatibilité avec /api/player/reset-password
    try:
        from ..services.player_auth import hash_recovery_phrase
        phrase = " ".join(words)
        rec_hash = hash_recovery_phrase(phrase)
        placeholder = "?" if db.is_sqlite else "%s"
        db.execute(
            f"UPDATE players SET recovery_key_hash = {placeholder} WHERE id = {placeholder}",
            (rec_hash, player_id),
        )
    except Exception:
        pass

    return True, "Nouveaux mots de récupération générés avec succès.", words


def verify_recovery_words(player_id: str, words: List[str]) -> bool:
    """Vérifie si les mots fournis correspondent aux hachages enregistrés pour le compte."""
    from ..services.player_auth import verify_password

    if not player_id or not words:
        return False

    sql = "SELECT word_hash FROM player_recovery_words WHERE player_id = %s"
    rows = db.fetch_all(sql, (player_id,))
    if not rows or len(rows) != len(words):
        return False

    stored_hashes = [r["word_hash"] for r in rows]
    # Chaque mot fourni doit correspondre à exactement un hash enregistré
    matched_hashes = set()
    for w in words:
        normalized = w.strip().lower()
        matched = False
        for h in stored_hashes:
            if h not in matched_hashes and verify_password(normalized, h):
                matched_hashes.add(h)
                matched = True
                break
        if not matched:
            return False

    return len(matched_hashes) == len(stored_hashes)


def get_account_stats(player_id: str) -> dict:
    """Agrège et calcule les statistiques de jeu du joueur connecté."""
    default_stats = {
        "totalGames": 0,
        "victories": 0,
        "winRate": 0.0,
        "avgGuesses": 0.0,
        "bestScore": 0.0,
        "avgTimeSeconds": 0.0,
        "hintsUsed": 0,
    }
    if not player_id:
        return default_stats

    sql = """
        SELECT
            COUNT(*) as total_games,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as victories,
            AVG(CASE WHEN status = 'won' THEN tries_count ELSE NULL END) as avg_guesses,
            MAX(best_score) as best_score,
            AVG(CASE WHEN status = 'won' AND duration_seconds > 0 THEN duration_seconds ELSE NULL END) as avg_time,
            SUM(hints_used) as total_hints
        FROM solo_player_games
        WHERE player_id = %s AND is_bot = FALSE
    """
    try:
        row = db.fetch_one(sql, (player_id,))
        if not row:
            return default_stats

        total = int(row.get("total_games") or 0)
        victories = int(row.get("victories") or 0)
        win_rate = round((victories / total * 100.0), 1) if total > 0 else 0.0
        avg_guesses = round(float(row.get("avg_guesses") or 0.0), 1)
        best_score = round(float(row.get("best_score") or 0.0), 2)
        avg_time = round(float(row.get("avg_time") or 0.0), 1)
        hints_used = int(row.get("total_hints") or 0)

        return {
            "totalGames": total,
            "victories": victories,
            "winRate": win_rate,
            "avgGuesses": avg_guesses,
            "bestScore": best_score,
            "avgTimeSeconds": avg_time,
            "hintsUsed": hints_used,
        }
    except Exception as e:
        log(f"⚠️  [ACCOUNT] Erreur calcul statistiques pour {player_id}: {e}")
        return default_stats
