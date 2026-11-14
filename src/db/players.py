"""
Cémantix Solver — Persistance des Profils Joueurs & Dictionnaires (M14)
=======================================================================
Gère l'accès relationnel aux tables `players` et `player_dictionary` :
- Profils invités, personnalisation unique du pseudo et sécurisation.
- Dictionnaires dynamiques pour génération de pseudos et phrases de secours.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from .connection import db

# Pool fixe des 20 profils fictifs réguliers (« les habitués » de 6h30, Jalon M15)
FIXED_BOT_HABITUES = [
    "CastorCosmique", "PangolinFurtif", "SuricateAudacieux", "RenardMalicieux",
    "LynxSolaire", "HibouFlamboyant", "KoalaLunaire", "BlaireauIntrepide",
    "FauconVeloce", "LoutreJoyeuse", "DauphinAgile", "PandaZen",
    "HeronMajestueux", "AigleSerein", "LoupNocturne", "OursGourmand",
    "EcureuilVif", "ToucanColore", "ChameauPlaisantin", "MarmotteDormeuse"
]
BOT_UUID_NAMESPACE = uuid.UUID("c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f")


def get_bot_uuid(username: str) -> str:
    """Génère un UUID déterministe pour un joueur fictif."""
    return str(uuid.uuid5(BOT_UUID_NAMESPACE, username.strip().lower()))

# Listes par défaut pour l'amorçage (seeding) initial
DEFAULT_NOUNS = [
    # Animaux décalés & emblématiques
    "Castor", "Pangolin", "Suricate", "Renard", "Blaireau", "Koala", "Lynx",
    "Faucon", "Hibou", "Panda", "Dauphin", "Loutre", "Guepard", "Jaguar",
    "Cameleon", "Albatros", "Flamant", "Ecureuil", "Raton", "Morse", "Phoque",
    "Tapir", "Elan", "Cerf", "Sanglier", "Loup", "Ours", "Herisson", "Aigle",
    "Condor", "Bison", "Pelican", "Toucan", "Corbeau", "Puma", "Tigre", "Lion",
    "Heron", "Vautour", "Buse", "Colibri", "Kiwi", "Saumon", "Carpe", "Triton",
    "Salamandre", "Glouton", "Ocelot", "Ornithorynque", "Ragondin", "Lama",
    "Dindon", "Pigeon", "Otarie", "Cachalot", "Poulpe", "Escargot", "Hamster",
    "Pterodactyle", "Bigorneau", "Crevette", "Chameau", "Marmotte", "Chihuahua",
    "Babouin", "Morue", "Homard", "Perroquet", "Tortue", "Crapaud",
    # Objets du quotidien & ustensiles incongrus
    "GrillePain", "Chaussette", "Babouche", "Pantoufle", "Tournevis", "Trombone",
    "Spatule", "Enclume", "Cafetiere", "Trotinette", "Salopette", "Charentaise",
    "Bouillotte", "Ventilateur", "Passoire", "Entonnoir", "Aspirateur", "Parapluie",
    "Brouette", "Marteau", "Clarinette", "Monocle", "MicroOnde", "Baignoire",
    "Savonnette", "Plumeau", "Thermos", "Shampoing", "Dentifrice", "TireBouchon",
    "Casserole", "Marmite", "Parachute", "Poubelle", "Reveil", "Microphone",
    # Gastronomie, victuailles & légumes improbables
    "Cornichon", "Courgette", "Artichaut", "Pamplemousse", "Camembert", "Poireau",
    "Navet", "Saucisson", "Brioche", "Baguette", "Croissant", "Gaufre", "Merguez",
    "ChouFleur", "Reblochon", "Frite", "Potiron", "Radis", "Epinard", "Macaron",
    "Quiche", "Tartiflette", "Knacki", "Tagliatelle", "Chouquette", "Ravioli",
    "Fondue", "Raclette", "Corniche", "Chantilly",
    # Personnages & professions hauts en couleur
    "Viking", "Troubadour", "Ninja", "Astronaute", "Yodleur", "Fakir", "Gnome",
    "Cyborg", "Centaure", "Alchimiste", "Gladiateur", "Sommelier", "Jongleur",
    "Comptable", "Dentiste", "Apiculteur", "Brocanteur", "Plombier", "Pompier",
    "Sorcier", "Lutteur", "Philosophe", "Druide", "Pirate", "Detective",
    "Barbier", "Marionnette", "Fantome", "Acrobate", "Astronome"
]

DEFAULT_ADJECTIVES = [
    # Absurdes, futuristes & cosmiques
    "Cosmique", "Furtif", "Flamboyant", "Stellaire", "Malicieux", "Audacieux",
    "Intrepide", "Lunaire", "Solaire", "Magique", "Veloce", "Agile", "Ruse",
    "Jovial", "Mystique", "Lumineux", "Temeraire", "Galactique", "Silencieux",
    "Radieux", "Majestueux", "Fantasque", "Serein", "Heroique", "Enigmatique",
    "Epique", "Brave", "Atomique", "Magnetique", "Tonique", "Farfelu",
    "Poetique", "Celeste", "Gracieux", "Robuste", "Rapide", "Brillant",
    "Vaillant", "Ethere", "Joyeux", "Mysterieux", "Invincible", "Astral",
    "Dynamique", "Spectaculaire", "Vigoureux", "Radioactif", "Fluorescent",
    "Phosphorescent", "Quantique", "Hypnotique", "Psychique", "Intergalactique",
    # Électriques, dynamiques & déjantés
    "Enrhume", "Bouillonnant", "Elastique", "Rutilant", "Barbu", "Moustachu",
    "Electrique", "Confus", "Disjoncte", "Croustillant", "Paillete", "Torsade",
    "Clignotant", "Somnambule", "Ensorcele", "Gazeux", "Vibrant", "Defroisse",
    "Panique", "Survolte", "Explosif", "Hysterique", "Gonflable", "Inodore",
    "Collant", "Visqueux", "Ebouriffe", "Rembourre", "Sideral", "Polymorphe",
    "Chancelant", "Bredouille", "Enflamme", "Microscopique", "Gigantesque",
    "Givre", "Caramelise", "Petillant", "Dejante", "Retroactif", "Telepathique",
    "Biodegradable", "Inoxydable", "Aerodynamique", "Hilarant", "Sucre",
    "Turbulent", "Insubmersible", "Volcanique", "Extraterrestre", "Incroyable"
]

DEFAULT_RECOVERY_WORDS = [
    "citron", "falaise", "navire", "vortex", "cristal", "comete", "volcan",
    "cascade", "boussole", "horizon", "galaxie", "nuage", "riviere", "canyon",
    "desert", "foret", "ocean", "sommet", "eclair", "tempete", "prairie",
    "torrent", "caverne", "etoile", "soleil", "planete", "diamant", "cuivre",
    "bronze", "argent", "rubis", "saphir", "ambre", "grenat", "quartz",
    "perle", "emeraude", "topaze", "agate", "jaspe", "platine", "cobalt",
    "marbre", "granit", "basalte", "corail", "lagon", "archipel", "glacier",
    "toundra", "savane", "oasis", "colline", "vallee", "abysse", "dune",
    "brise", "aurore", "crepuscule", "zodiaque", "eclipse", "nebuleuse", "pulsar",
    "meteore", "astre", "satellite", "orbite", "fusee", "capsule", "cabine",
    "ponton", "phare", "balise", "quai", "ancre", "gouvernail", "voile",
    "mat", "cordage", "coque", "hublot", "proue", "poupe", "compas",
    "sextant", "sablier", "horloge", "pendule", "montre", "cadran", "cloche",
    "carillon", "miroir", "lanterne", "torche", "bougie", "flambeau", "lampe",
    "vitrail", "fresque", "tableau", "toile", "pinceau", "palette", "ardoise",
    "plume", "encrier", "parchemin", "grimoire", "livre", "carnet", "registre",
    "sceau", "blason", "couronne", "sceptre", "diademe", "gemme", "tresor",
    "coffre", "malle", "cadenas", "clef", "serrure", "verrou", "armure",
    "casque", "bouclier", "heaume", "forge", "enclume", "marteau", "ciseau",
    "maillet", "rabot", "lime", "scie", "hache", "pioche", "pelle",
    "rateau", "truelle", "niveau", "regle", "equerre", "clou", "rivet",
    "boulon", "poulie", "treuil", "levier", "rouage", "engrenage", "ressort",
    "turbine", "helice", "moteur", "dynamo", "aimant", "prisme", "lentille",
    "loupe", "telescope", "lunette", "tourelle", "donjon", "rempart", "bastion",
    "forteresse", "chateau", "manoir", "moulin", "beffroi", "arche", "arcade",
    "coupole", "dome", "voute", "pilier", "colonne", "fronton", "portail",
    "vestibule", "atrium", "agora", "forum", "kiosque", "pont", "passerelle",
    "viaduc", "aqueduc", "tunnel", "galerie", "sentier", "chemin", "piste",
    "route", "avenue", "carrefour", "carrosse", "char", "caleche", "tandem",
    "bicyclette", "gondole", "pirogue", "canot", "barque", "chaloupe", "esquif",
    "felouque", "caravelle", "fregate", "goelette", "brick", "ketch", "sloop",
    "drakkar", "trimaran", "catamaran", "paquebot", "cargo", "chalutier", "aerostat",
    "ballon", "dirigeable", "zeppelin", "planeur", "biplan", "hydravion", "autogire",
    "deltaplane", "parapente", "montgolfiere", "parachute", "navette", "module", "sonde",
    "rover", "robot", "sifflet", "clochette", "tambour", "trompette", "violon",
    "guitare", "harpe", "flute", "piano", "orgue", "cithare", "accordeon",
    "xylophone", "triangle", "mandoline", "violoncelle", "clarinette", "hautbois", "basson",
    "cor", "trombone", "tuba", "gong", "banjo", "balalaika", "lyre",
    "tympanon", "castagnettes", "timbale", "maracas", "tambourin", "diapason", "partition",
    "archet", "pupitre"
]


def _row_to_player(row: dict) -> dict:
    """Harmonise le format de la ligne joueur SQL."""
    return {
        "id": str(row["id"]),
        "auth_token": str(row["auth_token"]),
        "username": str(row["username"]),
        "can_change_username": bool(row.get("can_change_username", True)),
        "is_claimed": bool(row.get("is_claimed", False)),
        "password_hash": row.get("password_hash"),
        "recovery_key_hash": row.get("recovery_key_hash"),
        "auth_provider": row.get("auth_provider", "local"),
        "google_sub": row.get("google_sub"),
        "created_at": str(row.get("created_at") or ""),
        "last_seen_at": str(row.get("last_seen_at") or ""),
        "renamed_at": str(row.get("renamed_at") or "") if row.get("renamed_at") else None,
        "password_updated_at": str(row.get("password_updated_at") or "") if row.get("password_updated_at") else None,
        "last_login_at": str(row.get("last_login_at") or "") if row.get("last_login_at") else None,
    }


def seed_default_dictionary_if_empty():
    """Alimente les listes de mots par défaut si la table player_dictionary est incomplète ou vide."""
    try:
        engine = db.get_engine_type()
        is_active_sql = "TRUE" if engine == "postgres" else "1"
        placeholder = "%s" if engine == "postgres" else "?"

        # Compte par type de mot
        type_counts = {}
        for r in db.fetch_all("SELECT word_type, COUNT(*) AS cnt FROM player_dictionary GROUP BY word_type") or []:
            type_counts[str(r["word_type"])] = int(r["cnt"])

        with db.transaction() as conn:
            cur = conn.cursor()

            # Insertion des noms si absents
            if type_counts.get("noun", 0) < len(DEFAULT_NOUNS):
                for noun in sorted(set(DEFAULT_NOUNS)):
                    if engine == "postgres":
                        cur.execute(
                            f"INSERT INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql}) ON CONFLICT DO NOTHING",
                            ("noun", noun),
                        )
                    else:
                        cur.execute(
                            f"INSERT OR IGNORE INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql})",
                            ("noun", noun),
                        )

            # Insertion des adjectifs si absents
            if type_counts.get("adjective", 0) < len(DEFAULT_ADJECTIVES):
                for adj in sorted(set(DEFAULT_ADJECTIVES)):
                    if engine == "postgres":
                        cur.execute(
                            f"INSERT INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql}) ON CONFLICT DO NOTHING",
                            ("adjective", adj),
                        )
                    else:
                        cur.execute(
                            f"INSERT OR IGNORE INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql})",
                            ("adjective", adj),
                        )

            # Insertion des mots de récupération si absents
            if type_counts.get("recovery", 0) < len(DEFAULT_RECOVERY_WORDS):
                for rec in sorted(set(DEFAULT_RECOVERY_WORDS)):
                    if engine == "postgres":
                        cur.execute(
                            f"INSERT INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql}) ON CONFLICT DO NOTHING",
                            ("recovery", rec),
                        )
                    else:
                        cur.execute(
                            f"INSERT OR IGNORE INTO player_dictionary (word_type, word, is_active) VALUES ({placeholder}, {placeholder}, {is_active_sql})",
                            ("recovery", rec),
                        )
    except Exception as e:
        from ..config import log
        log(f"⚠️  [AUTH] Erreur amorçage dictionnaire joueurs : {e}")


def seed_bot_players_if_empty():
    """Alimente les 20 profils fictifs réguliers (« les habitués » de 6h30) si absents."""
    try:
        engine = db.get_engine_type()
        is_claimed_val = True if engine == "postgres" else 1
        can_change_val = False if engine == "postgres" else 0

        for username in FIXED_BOT_HABITUES:
            bot_id = get_bot_uuid(username)
            auth_token = f"bot_token_{username.lower()}"
            existing = get_player_by_username(username)
            if not existing:
                if engine == "postgres":
                    query = """
                    INSERT INTO players (
                        id, auth_token, username, can_change_username, is_claimed, auth_provider, created_at, last_seen_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (username) DO NOTHING
                    """
                else:
                    query = """
                    INSERT OR IGNORE INTO players (
                        id, auth_token, username, can_change_username, is_claimed, auth_provider, created_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                db.execute(query, (bot_id, auth_token, username, can_change_val, is_claimed_val, "bot"))
    except Exception as e:
        from ..config import log
        log(f"⚠️  [AUTH] Erreur amorçage joueurs habitués bots : {e}")


def create_guest_player(
    player_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Crée un joueur invité avec pseudo généré et token de session."""
    import secrets
    pid = str(player_id or uuid.uuid4())
    tok = str(auth_token or f"guest_token_{secrets.token_hex(16)}")
    uname = str(username or f"Joueur{secrets.randbelow(9000) + 1000}")

    query = """
    INSERT INTO players (
        id, auth_token, username, can_change_username, is_claimed, auth_provider, created_at, last_seen_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    """
    engine = db.get_engine_type()
    # Support bool pour SQLite (1/0) ou Postgres (True/False)
    can_change = True if engine == "postgres" else 1
    is_claimed = False if engine == "postgres" else 0
    params = (pid, tok, uname, can_change, is_claimed, "local")

    db.execute(query, params)
    player = get_player_by_id(pid)
    if not player:
        raise RuntimeError(f"Échec de création du joueur {pid}")
    return player


def get_player_by_id(player_id: str) -> Optional[dict]:
    """Récupère un joueur par son identifiant UUID."""
    row = db.fetch_one("SELECT * FROM players WHERE id = %s", (player_id,))
    return _row_to_player(row) if row else None


def get_player_by_token(auth_token: str) -> Optional[dict]:
    """Récupère un joueur par son jeton de session."""
    if not auth_token:
        return None
    row = db.fetch_one("SELECT * FROM players WHERE auth_token = %s", (auth_token,))
    return _row_to_player(row) if row else None


def get_player_by_username(username: str) -> Optional[dict]:
    """Récupère un joueur par son pseudo (insensible à la casse)."""
    if not username:
        return None
    row = db.fetch_one("SELECT * FROM players WHERE LOWER(username) = LOWER(%s)", (username.strip(),))
    return _row_to_player(row) if row else None


def update_player_username(player_id: str, new_username: str) -> bool:
    """Personnalise le pseudo du joueur une seule et unique fois."""
    player = get_player_by_id(player_id)
    if not player or not player.get("can_change_username"):
        return False

    engine = db.get_engine_type()
    can_change_val = False if engine == "postgres" else 0
    can_change_cond = "can_change_username = TRUE" if engine == "postgres" else "can_change_username = 1"
    query = f"""
    UPDATE players
    SET username = %s, can_change_username = %s, renamed_at = CURRENT_TIMESTAMP, last_seen_at = CURRENT_TIMESTAMP
    WHERE id = %s AND {can_change_cond}
    """
    affected = db.execute(query, (new_username, can_change_val, player_id))
    return affected > 0


def claim_player_account(player_id: str, password_hash: str, recovery_key_hash: str) -> bool:
    """Sécurise le compte joueur avec un mot de passe et une phrase secrète."""
    engine = db.get_engine_type()
    is_claimed_val = True if engine == "postgres" else 1
    query = """
    UPDATE players
    SET password_hash = %s, recovery_key_hash = %s, is_claimed = %s, last_seen_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    affected = db.execute(query, (password_hash, recovery_key_hash, is_claimed_val, player_id))
    return affected > 0


def update_player_password(player_id: str, new_password_hash: str, new_auth_token: Optional[str] = None) -> bool:
    """Met à jour le mot de passe d'un compte (réinitialisation ou modification)."""
    if new_auth_token:
        query = """
        UPDATE players
        SET password_hash = %s, auth_token = %s, last_seen_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        affected = db.execute(query, (new_password_hash, new_auth_token, player_id))
    else:
        query = """
        UPDATE players
        SET password_hash = %s, last_seen_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        affected = db.execute(query, (new_password_hash, player_id))
    return affected > 0


def touch_player_activity(player_id: str) -> None:
    """Met à jour atomiquement la date de dernière activité."""
    try:
        db.execute("UPDATE players SET last_seen_at = CURRENT_TIMESTAMP WHERE id = %s", (player_id,))
    except Exception:
        pass


def delete_player_account(player_id: str) -> bool:
    """Supprime définitivement un compte joueur (droit à l'effacement RGPD)."""
    affected = db.execute("DELETE FROM players WHERE id = %s", (player_id,))
    return affected > 0


def get_active_dictionary(word_type: str) -> list[str]:
    """Retourne la liste des mots actifs pour un type donné (noun, adjective, recovery)."""
    engine = db.get_engine_type()
    is_active_cond = "is_active = TRUE" if engine == "postgres" else "is_active = 1"
    query = f"SELECT word FROM player_dictionary WHERE word_type = %s AND {is_active_cond} ORDER BY word ASC"
    rows = db.fetch_all(query, (word_type,))
    return [r["word"] for r in rows] if rows else []


def get_dictionary_words(word_type: Optional[str] = None) -> list[dict]:
    """Retourne l'ensemble des entrées du dictionnaire (pour l'administration)."""
    if word_type:
        query = "SELECT id, word_type, word, is_active, created_at FROM player_dictionary WHERE word_type = %s ORDER BY word ASC"
        rows = db.fetch_all(query, (word_type,))
    else:
        query = "SELECT id, word_type, word, is_active, created_at FROM player_dictionary ORDER BY word_type ASC, word ASC"
        rows = db.fetch_all(query)

    result = []
    for r in rows:
        result.append({
            "id": int(r["id"]),
            "word_type": str(r["word_type"]),
            "word": str(r["word"]),
            "is_active": bool(r.get("is_active", True)),
            "created_at": str(r.get("created_at") or ""),
        })
    return result


def add_dictionary_word(word_type: str, word: str) -> int:
    """Ajoute un mot au dictionnaire s'il n'existe pas déjà."""
    cleaned_word = word.strip()
    existing = db.fetch_one(
        "SELECT id, is_active FROM player_dictionary WHERE word_type = %s AND LOWER(word) = LOWER(%s)",
        (word_type, cleaned_word),
    )
    if existing:
        # Réactivation si inactif
        if not bool(existing.get("is_active", True)):
            toggle_dictionary_word(int(existing["id"]), True)
        return int(existing["id"])

    engine = db.get_engine_type()
    is_active_val = True if engine == "postgres" else 1

    with db.transaction() as conn:
        cur = conn.cursor()
        if engine == "postgres":
            cur.execute(
                "INSERT INTO player_dictionary (word_type, word, is_active) VALUES (%s, %s, %s) RETURNING id",
                (word_type, cleaned_word, is_active_val),
            )
            row = cur.fetchone()
            return int(row["id"]) if isinstance(row, dict) else int(row[0])
        else:
            cur.execute(
                "INSERT INTO player_dictionary (word_type, word, is_active) VALUES (?, ?, ?)",
                (word_type, cleaned_word, is_active_val),
            )
            return int(cur.lastrowid)


def toggle_dictionary_word(word_id: int, is_active: bool) -> bool:
    """Active ou désactive un mot du dictionnaire."""
    engine = db.get_engine_type()
    is_active_val = is_active if engine == "postgres" else (1 if is_active else 0)
    affected = db.execute("UPDATE player_dictionary SET is_active = %s WHERE id = %s", (is_active_val, word_id))
    return affected > 0


def delete_dictionary_word(word_id: int) -> bool:
    """Supprime définitivement un mot du dictionnaire."""
    affected = db.execute("DELETE FROM player_dictionary WHERE id = %s", (word_id,))
    return affected > 0


# ============================================================================
# Fonctions d'administration des utilisateurs (Console /panier-9x)
# ============================================================================

def list_players(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    filter_type: Optional[str] = None,
) -> list[dict]:
    """Liste paginée des joueurs avec recherche et filtrage optionnel."""
    engine = db.get_engine_type()
    conditions = []
    params: list = []

    if search:
        search_pattern = f"%{search.strip()}%"
        if engine == "postgres":
            conditions.append("(username ILIKE %s OR CAST(id AS TEXT) ILIKE %s)")
        else:
            conditions.append("(username LIKE %s OR id LIKE %s)")
        params.extend([search_pattern, search_pattern])

    if filter_type == "claimed":
        val = True if engine == "postgres" else 1
        conditions.append("is_claimed = %s")
        params.append(val)
    elif filter_type == "guest":
        val = False if engine == "postgres" else 0
        conditions.append("is_claimed = %s")
        params.append(val)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = "ORDER BY created_at DESC"
    limit_clause = f"LIMIT {max(1, min(int(limit), 200))} OFFSET {max(0, int(offset))}"

    query = f"SELECT * FROM players {where_clause} {order_clause} {limit_clause}"
    rows = db.fetch_all(query, tuple(params) if params else None)
    return [_row_to_player(r) for r in rows] if rows else []


def count_players(search: Optional[str] = None, filter_type: Optional[str] = None) -> int:
    """Nombre total de joueurs correspondant aux critères."""
    engine = db.get_engine_type()
    conditions = []
    params: list = []

    if search:
        search_pattern = f"%{search.strip()}%"
        if engine == "postgres":
            conditions.append("(username ILIKE %s OR CAST(id AS TEXT) ILIKE %s)")
        else:
            conditions.append("(username LIKE %s OR id LIKE %s)")
        params.extend([search_pattern, search_pattern])

    if filter_type == "claimed":
        val = True if engine == "postgres" else 1
        conditions.append("is_claimed = %s")
        params.append(val)
    elif filter_type == "guest":
        val = False if engine == "postgres" else 0
        conditions.append("is_claimed = %s")
        params.append(val)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT COUNT(*) AS cnt FROM players {where_clause}"
    row = db.fetch_one(query, tuple(params) if params else None)
    return int(row["cnt"]) if row and "cnt" in row else 0


def get_players_stats() -> dict:
    """Statistiques globales des joueurs (comptes, statuts, activité)."""
    engine = db.get_engine_type()
    claimed_val = "TRUE" if engine == "postgres" else "1"
    guest_val = "FALSE" if engine == "postgres" else "0"

    if engine == "postgres":
        query = f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE is_claimed = {claimed_val}) AS claimed,
            COUNT(*) FILTER (WHERE is_claimed = {guest_val}) AS guests,
            COUNT(*) FILTER (WHERE last_seen_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') AS active_7d
        FROM players
        """
    else:
        query = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_claimed = {claimed_val} THEN 1 ELSE 0 END) AS claimed,
            SUM(CASE WHEN is_claimed = {guest_val} THEN 1 ELSE 0 END) AS guests,
            SUM(CASE WHEN last_seen_at >= datetime('now', '-7 days') THEN 1 ELSE 0 END) AS active_7d
        FROM players
        """
    try:
        row = db.fetch_one(query)
        if not row:
            return {"total": 0, "claimed": 0, "guests": 0, "active_7d": 0}
        return {
            "total": int(row.get("total") or 0),
            "claimed": int(row.get("claimed") or 0),
            "guests": int(row.get("guests") or 0),
            "active_7d": int(row.get("active_7d") or 0),
        }
    except Exception:
        total = count_players()
        claimed = count_players(filter_type="claimed")
        return {"total": total, "claimed": claimed, "guests": total - claimed, "active_7d": 0}


def admin_update_player(
    player_id: str,
    username: Optional[str] = None,
    can_change_username: Optional[bool] = None,
    is_claimed: Optional[bool] = None,
) -> bool:
    """Mise à jour administrative d'un joueur (pseudo, droit de renommage, statut)."""
    player = get_player_by_id(player_id)
    if not player:
        return False

    engine = db.get_engine_type()
    updates = []
    params: list = []

    if username is not None:
        clean_user = username.strip()
        if not clean_user:
            return False
        existing = get_player_by_username(clean_user)
        if existing and existing["id"] != str(player_id):
            raise ValueError(f"Le pseudo '{clean_user}' est déjà utilisé par un autre joueur.")
        updates.append("username = %s")
        params.append(clean_user)
        updates.append("renamed_at = CURRENT_TIMESTAMP")

    if can_change_username is not None:
        val = bool(can_change_username) if engine == "postgres" else (1 if can_change_username else 0)
        updates.append("can_change_username = %s")
        params.append(val)

    if is_claimed is not None:
        val = bool(is_claimed) if engine == "postgres" else (1 if is_claimed else 0)
        updates.append("is_claimed = %s")
        params.append(val)

    if not updates:
        return True

    updates.append("last_seen_at = CURRENT_TIMESTAMP")
    query = f"UPDATE players SET {', '.join(updates)} WHERE id = %s"
    params.append(player_id)
    affected = db.execute(query, tuple(params))
    return affected > 0


def admin_create_player(username: str, is_claimed: bool = False, password_hash: Optional[str] = None) -> dict:
    """Création manuelle d'un compte joueur par l'administrateur."""
    import secrets
    import uuid

    clean_user = username.strip()
    if not clean_user:
        raise ValueError("Le pseudo ne peut pas être vide.")
    existing = get_player_by_username(clean_user)
    if existing:
        raise ValueError(f"Le pseudo '{clean_user}' existe déjà.")

    player_id = str(uuid.uuid4())
    auth_token = secrets.token_hex(32)
    engine = db.get_engine_type()
    can_change = False if engine == "postgres" else 0
    claimed_val = bool(is_claimed) if engine == "postgres" else (1 if is_claimed else 0)

    query = """
    INSERT INTO players (
        id, auth_token, username, can_change_username, is_claimed, password_hash, auth_provider, created_at, last_seen_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    """
    db.execute(query, (player_id, auth_token, clean_user, can_change, claimed_val, password_hash, "local"))
    player = get_player_by_id(player_id)
    if not player:
        raise RuntimeError(f"Échec de création du joueur {player_id}")
    return player

