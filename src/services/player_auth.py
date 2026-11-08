"""
Cémantix Solver — Service Métier d'Authentification & Vocabulaires (M14)
========================================================================
Centralise les règles d'authentification joueur, la génération de pseudos
français [Nom][Adjectif], la gestion des phrases de secours de 4 mots,
le hachage PBKDF2 et la validation stricte de l'identité joueur.
"""
import hashlib
import hmac
import re
import secrets
import threading
import unicodedata
import uuid
from typing import Optional, Tuple

from ..config import log
from ..db.players import (
    DEFAULT_ADJECTIVES,
    DEFAULT_NOUNS,
    DEFAULT_RECOVERY_WORDS,
    claim_player_account,
    create_guest_player,
    delete_player_account,
    get_active_dictionary,
    get_player_by_id,
    get_player_by_token,
    get_player_by_username,
    touch_player_activity,
    update_player_password,
    update_player_username,
)

# Cache mémoire pour les dictionnaires
_cache_lock = threading.Lock()
_cached_nouns: Optional[list[str]] = None
_cached_adjectives: Optional[list[str]] = None
_cached_recovery: Optional[list[str]] = None

# Pseudos réservés et termes interdits
RESERVED_USERNAMES = {
    "admin", "administrator", "root", "system", "moderator", "moderateur",
    "modo", "bot", "cemantix", "staff", "support", "null", "undefined",
    "anonymous", "anonyme", "guest", "invite", "player", "joueur", "service"
}

# Regex de validation de pseudo : 8 à 24 caractères (alphanumériques, tirets, underscores)
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9À-ÿ_-]{8,24}$")


def invalidate_dictionary_cache():
    """Invalide le cache mémoire des dictionnaires (après mise à jour admin)."""
    global _cached_nouns, _cached_adjectives, _cached_recovery
    with _cache_lock:
        _cached_nouns = None
        _cached_adjectives = None
        _cached_recovery = None


def _get_nouns() -> list[str]:
    global _cached_nouns
    with _cache_lock:
        if _cached_nouns is not None and len(_cached_nouns) > 0:
            return _cached_nouns
        try:
            db_nouns = get_active_dictionary("noun")
            if db_nouns:
                _cached_nouns = db_nouns
                return _cached_nouns
        except Exception as e:
            log(f"⚠️  [AUTH] Impossible de charger les noms depuis la base : {e}")
        _cached_nouns = list(DEFAULT_NOUNS)
        return _cached_nouns


def _get_adjectives() -> list[str]:
    global _cached_adjectives
    with _cache_lock:
        if _cached_adjectives is not None and len(_cached_adjectives) > 0:
            return _cached_adjectives
        try:
            db_adjs = get_active_dictionary("adjective")
            if db_adjs:
                _cached_adjectives = db_adjs
                return _cached_adjectives
        except Exception as e:
            log(f"⚠️  [AUTH] Impossible de charger les adjectifs depuis la base : {e}")
        _cached_adjectives = list(DEFAULT_ADJECTIVES)
        return _cached_adjectives


def _get_recovery_words() -> list[str]:
    global _cached_recovery
    with _cache_lock:
        if _cached_recovery is not None and len(_cached_recovery) > 0:
            return _cached_recovery
        try:
            db_rec = get_active_dictionary("recovery")
            if db_rec:
                _cached_recovery = db_rec
                return _cached_recovery
        except Exception as e:
            log(f"⚠️  [AUTH] Impossible de charger les mots de secours depuis la base : {e}")
        _cached_recovery = list(DEFAULT_RECOVERY_WORDS)
        return _cached_recovery


# --- Sécurité Cryptographique (PBKDF2 & Tokens) ------------------------------

def hash_password(password: str) -> str:
    """Hache un mot de passe avec PBKDF2-HMAC-SHA256 et un sel aléatoire de 16 octets."""
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide")
    salt = secrets.token_bytes(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}:{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """Vérifie un mot de passe en temps constant contre son condensat PBKDF2."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split(":")
    if len(parts) != 5 or parts[0] != "pbkdf2" or parts[1] != "sha256":
        return False
    try:
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_dk = parts[4]
        calculated_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
        return hmac.compare_digest(calculated_dk, expected_dk)
    except Exception:
        return False


def normalize_recovery_phrase(phrase: str) -> str:
    """Normalise la phrase secrète : minuscules, suppression accents, séparation par tiret."""
    if not phrase:
        return ""
    # Suppression des accents
    nfkd = unicodedata.normalize("NFKD", phrase)
    ascii_text = nfkd.encode("ASCII", "ignore").decode("utf-8").lower()
    # Remplacement de toute ponctuation par des espaces
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()
    words = cleaned.split()
    return "-".join(words)


def hash_recovery_phrase(phrase: str) -> str:
    """Hache la phrase de secours normalisée."""
    normalized = normalize_recovery_phrase(phrase)
    return hash_password(normalized)


def verify_recovery_phrase(phrase: str, stored_hash: Optional[str]) -> bool:
    """Vérifie une phrase de récupération soumise par le joueur."""
    normalized = normalize_recovery_phrase(phrase)
    return verify_password(normalized, stored_hash)


def generate_auth_token() -> str:
    """Génère un jeton de session cryptographiquement sûr de 64 caractères hexadécimaux."""
    return secrets.token_hex(32)


# --- Générateur de Pseudos Loufoques [Nom][Adjectif] -------------------------

def _clean_word_for_username(word: str) -> str:
    """Nettoie et capitalise un mot en CamelCase."""
    word = word.strip()
    if not word:
        return ""
    return word[0].upper() + word[1:]


def generate_random_username() -> str:
    """Génère un pseudo respectant STRICTEMENT l'ordre [Nom][Adjectif], 8 à 24 car."""
    nouns = _get_nouns()
    adjs = _get_adjectives()

    for _ in range(50):
        n = _clean_word_for_username(secrets.choice(nouns))
        a = _clean_word_for_username(secrets.choice(adjs))
        candidate = f"{n}{a}"

        # Longueur requise : 8 à 24 caractères
        if 8 <= len(candidate) <= 24:
            # Vérification d'unicité en base
            if not get_player_by_username(candidate):
                return candidate

    # Si collisions répétées, ajout d'un suffixe numérique
    for _ in range(20):
        n = _clean_word_for_username(secrets.choice(nouns))
        a = _clean_word_for_username(secrets.choice(adjs))
        suffix = str(secrets.randbelow(900) + 100)  # ex: 142
        base = f"{n}{a}"
        # Troncature si besoin pour ne jamais dépasser 24 caractères
        max_base_len = 24 - len(suffix)
        candidate = f"{base[:max_base_len]}{suffix}"
        if 8 <= len(candidate) <= 24 and not get_player_by_username(candidate):
            return candidate

    # Repli ultime
    token_suffix = secrets.token_hex(3)
    return f"CastorCosmique{token_suffix}"[:24]


def generate_recovery_phrase(num_words: int = 4) -> str:
    """Génère une phrase secrète de secours de 4 mots concrets français."""
    recovery_words = _get_recovery_words()
    selected = [secrets.choice(recovery_words) for _ in range(num_words)]
    return " ".join(selected)


def validate_username(username: str) -> Tuple[bool, str]:
    """Valide la conformité d'un pseudo (8 à 24 car, unicité, anti-abus)."""
    if not username:
        return False, "Le pseudo ne peut pas être vide."
    cleaned = username.strip()

    if len(cleaned) < 8 or len(cleaned) > 24:
        return False, "Le pseudo doit contenir entre 8 et 24 caractères."

    if not USERNAME_REGEX.match(cleaned):
        return False, "Le pseudo contient des caractères non autorisés (seules lettres, chiffres, tirets et underscores sont acceptés)."

    lower_name = cleaned.lower()
    for reserved in RESERVED_USERNAMES:
        if lower_name == reserved or lower_name.startswith(f"{reserved}_") or lower_name.startswith(f"{reserved}-"):
            return False, f"Le pseudo '{cleaned}' utilise un terme réservé par le système."

    # Termes manifestement abusifs/vulgaires de base
    offensive_patterns = ["connard", "salope", "nazi", "hitler", "encule", "pute"]
    for off in offensive_patterns:
        if off in lower_name:
            return False, "Ce pseudo ne respecte pas les conditions d'utilisation."

    # Vérification de collision avec un joueur existant
    existing = get_player_by_username(cleaned)
    if existing:
        return False, "Ce pseudo est déjà utilisé par un autre joueur."

    return True, ""


# --- Services Métier Joueur --------------------------------------------------

def init_or_get_guest(
    player_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Initialise un profil invité transparent ou retourne la session existante validée."""
    # 1. Recherche par jeton de session (priorité absolue)
    if auth_token:
        existing = get_player_by_token(auth_token)
        if existing:
            touch_player_activity(existing["id"])
            return {
                "player_id": existing["id"],
                "auth_token": existing["auth_token"],
                "username": existing["username"],
                "can_change_username": existing["can_change_username"],
                "is_claimed": existing["is_claimed"],
            }

    # 2. Si le token n'a pas matché mais qu'un ID valide est fourni, recherche par ID
    if player_id and len(player_id) == 36:
        existing_by_id = get_player_by_id(player_id)
        if existing_by_id:
            touch_player_activity(existing_by_id["id"])
            return {
                "player_id": existing_by_id["id"],
                "auth_token": existing_by_id["auth_token"],
                "username": existing_by_id["username"],
                "can_change_username": existing_by_id["can_change_username"],
                "is_claimed": existing_by_id["is_claimed"],
            }

    # 3. Si le client avait un pseudo en local, on regarde s'il existe déjà en base
    if username:
        cleaned_user = username.strip()
        existing_by_user = get_player_by_username(cleaned_user)
        if existing_by_user and not existing_by_user.get("is_claimed"):
            # Compte invité non réclamé correspondant au pseudo : on le réassocie
            touch_player_activity(existing_by_user["id"])
            return {
                "player_id": existing_by_user["id"],
                "auth_token": existing_by_user["auth_token"],
                "username": existing_by_user["username"],
                "can_change_username": existing_by_user["can_change_username"],
                "is_claimed": existing_by_user["is_claimed"],
            }

    # 4. Création d'un nouvel invité (première visite ou profil non rattaché en base)
    new_id = str(uuid.uuid4())
    new_token = generate_auth_token()

    # Si le client avait un pseudo en local valide et disponible, on le préserve
    chosen_username = None
    if username:
        cleaned_user = username.strip()
        is_valid, _ = validate_username(cleaned_user)
        if is_valid and not get_player_by_username(cleaned_user):
            chosen_username = cleaned_user

    if not chosen_username:
        for _ in range(20):
            candidate = generate_random_username()
            if not get_player_by_username(candidate):
                chosen_username = candidate
                break

    if not chosen_username:
        chosen_username = f"Joueur{secrets.randbelow(9000) + 1000}"

    player = create_guest_player(new_id, new_token, chosen_username)
    return {
        "player_id": player["id"],
        "auth_token": player["auth_token"],
        "username": player["username"],
        "can_change_username": player["can_change_username"],
        "is_claimed": player["is_claimed"],
    }


def rename_player(auth_token: str, new_username: str) -> Tuple[bool, str, Optional[dict]]:
    """Personnalise le pseudo du joueur (une seule fois dans la vie du compte)."""
    if not auth_token:
        return False, "Jeton d'authentification manquant.", None

    player = get_player_by_token(auth_token)
    if not player:
        return False, "Session joueur introuvable ou expirée.", None

    if not player.get("can_change_username"):
        return False, "Ce compte a déjà personnalisé son pseudo (modification unique autorisée).", None

    is_valid, error_msg = validate_username(new_username)
    if not is_valid:
        return False, error_msg, None

    cleaned_username = new_username.strip()
    existing_user = get_player_by_username(cleaned_username)
    if existing_user and existing_user["id"] != player["id"]:
        return False, "Ce pseudo est déjà utilisé par un autre joueur.", None

    success = update_player_username(player["id"], cleaned_username)
    if not success:
        return False, "Erreur lors de la mise à jour du pseudo.", None

    updated_player = get_player_by_id(player["id"])
    return True, "Pseudo mis à jour avec succès.", updated_player


def claim_account(auth_token: str, password: str) -> Tuple[bool, str, Optional[str]]:
    """Sécurise le compte avec un mot de passe et émet la phrase de secours de 4 mots."""
    if not auth_token:
        return False, "Jeton d'authentification manquant.", None

    player = get_player_by_token(auth_token)
    if not player:
        return False, "Session joueur introuvable.", None

    if player.get("is_claimed"):
        return False, "Ce compte est déjà protégé par un mot de passe.", None

    if not password or len(password) < 8:
        return False, "Le mot de passe doit comporter au moins 8 caractères.", None

    pwd_hash = hash_password(password)
    recovery_phrase = generate_recovery_phrase(num_words=4)
    rec_hash = hash_recovery_phrase(recovery_phrase)

    success = claim_player_account(player["id"], pwd_hash, rec_hash)
    if not success:
        return False, "Erreur lors de la protection du compte.", None

    return True, "Compte protégé avec succès.", recovery_phrase


def login_player(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """Authentifie un joueur existant sur un nouvel appareil via son pseudo et mot de passe."""
    if not username or not password:
        return False, "Pseudo et mot de passe requis.", None

    player = get_player_by_username(username)
    if not player:
        return False, "Identifiants incorrects.", None

    if not player.get("is_claimed") or not player.get("password_hash"):
        return False, "Ce compte n'a pas été protégé par un mot de passe.", None

    if not verify_password(password, player.get("password_hash")):
        return False, "Identifiants incorrects.", None

    touch_player_activity(player["id"])
    return True, "Connexion réussie.", {
        "player_id": player["id"],
        "auth_token": player["auth_token"],
        "username": player["username"],
        "can_change_username": player["can_change_username"],
        "is_claimed": player["is_claimed"],
    }


def reset_password_with_recovery(username: str, recovery_phrase: str, new_password: str) -> Tuple[bool, str, Optional[str]]:
    """Réinitialise le mot de passe d'un compte à l'aide de sa phrase secrète de 4 mots."""
    if not username or not recovery_phrase or not new_password:
        return False, "Tous les champs sont obligatoires.", None

    if len(new_password) < 8:
        return False, "Le nouveau mot de passe doit comporter au moins 8 caractères.", None

    player = get_player_by_username(username)
    if not player:
        return False, "Compte introuvable.", None

    stored_rec_hash = player.get("recovery_key_hash")
    if not stored_rec_hash:
        return False, "Aucune phrase de secours enregistrée pour ce compte.", None

    if not verify_recovery_phrase(recovery_phrase, stored_rec_hash):
        return False, "Phrase de secours invalide.", None

    new_pwd_hash = hash_password(new_password)
    new_token = generate_auth_token()

    success = update_player_password(player["id"], new_pwd_hash, new_auth_token=new_token)
    if not success:
        return False, "Erreur lors de la réinitialisation du mot de passe.", None

    return True, "Mot de passe réinitialisé avec succès.", new_token


def delete_player(auth_token: str) -> Tuple[bool, str]:
    """Supprime définitivement un compte joueur (droit à l'effacement RGPD)."""
    if not auth_token:
        return False, "Jeton manquant."
    player = get_player_by_token(auth_token)
    if not player:
        return False, "Session introuvable."
    success = delete_player_account(player["id"])
    return (True, "Compte supprimé.") if success else (False, "Erreur lors de la suppression.")

