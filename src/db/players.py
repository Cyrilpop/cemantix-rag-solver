"""
Cémantix Solver — Persistance des Profils Joueurs & Dictionnaires (M14)
=======================================================================
Gère l'accès relationnel aux tables `players` et `player_dictionary` :
- Profils invités, personnalisation unique du pseudo et sécurisation.
- Dictionnaires dynamiques pour génération de pseudos et phrases de secours.
"""
from datetime import datetime, timezone
from typing import Optional

from .connection import db

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
    except Exception as e:
        from ..config import log
        log(f"⚠️  [AUTH] Erreur amorçage dictionnaire joueurs : {e}")


def create_guest_player(player_id: str, auth_token: str, username: str) -> dict:
    """Crée un joueur invité avec pseudo généré et token de session."""
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
    params = (player_id, auth_token, username, can_change, is_claimed, "local")

    db.execute(query, params)
    player = get_player_by_id(player_id)
    if not player:
        raise RuntimeError(f"Échec de création du joueur {player_id}")
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

