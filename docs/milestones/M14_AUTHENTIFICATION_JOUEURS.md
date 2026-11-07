# Jalon M14 — Authentification Joueurs sans Email : Profils Invités, Pseudos Personnalisables & Phrase de Secours

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m14-authentification-joueurs` (base `main`)  
**Statut :** ⏳ En préparation / Cadrage initial  
**Périmètre exclusif :** `database/init.sql`, `src/db/connection.py`, `src/db/players.py` (ou `src/db/` associé), `src/services/player_auth.py`, routes API backend HTTP (`src/api/` ou serveur dédié), dictionnaire de mots loufoques et phrase de secours, injection layout header (`src/services/layout_sync.py`), composants UI frontend (`volumes/web/js/auth.js`, `volumes/web/css/auth.css`), suite de tests unitaires sous Docker (`tests/test_player_auth.py`), et documentation associée (`docs/roadmap/2026-11-07-authentification-joueurs/`, `docs/roadmap/README.md`, `README.md`, `CHANGELOG.md`).  
**Périmètre exclu pour ce jalon :** Pas d'intégration directe de Google Sign-In / OAuth (le schéma et l'architecture prévoient la colonne et l'extensibilité, mais le flux Google OAuth sera activé ultérieurement). Aucune dépendance externe payante ni outil hors conteneur.  
**Suite de validation requise :** Tests unitaires automatisés sous Docker Python 3.12 (`docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests`), `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check`.  
**Règle d'or environnement :** L'intégralité du projet s'exécute sous Docker. Aucune commande Python, pip ou test ne doit être exécutée directement sur la machine hôte.

---

## 1. Objectifs Métier et Expérience Utilisateur (UX)

Actuellement, les joueurs interagissent avec Cémantix Solver en mode totalement anonyme ou via des identifiants éphémères de salon, sans persistance de profil unifié ni possibilité de conserver leurs statistiques et défis entre plusieurs sessions ou plusieurs appareils.

Le présent **Jalon M14** introduit un système d'authentification et d'identité joueur moderne, ludique, sans friction et strictement respectueux de la vie privée (Privacy by Design / zéro email) :

1. **Attribution Automatique d'une Identité Invité (Zéro Friction) :**
   - Dès la première visite, le joueur se voit attribuer un identifiant unique (UUID) et un **pseudo loufoque en français généré aléatoirement** (style Docker : `CastorCosmique`, `PangolinFurtif`, etc.).
   - Le profil invité est stocké dans le `localStorage` du navigateur et synchronisé de manière transparente et idempotente avec la base de données.
   - Aucun formulaire d'inscription bloquant ni email requis pour jouer.

2. **Personnalisation Unique du Pseudo :**
   - Le joueur peut personnaliser son pseudo une seule et unique fois (`can_change_username = TRUE` $\rightarrow$ `FALSE`).
   - Le serveur garantit l'unicité du pseudo, la validation des caractères autorisés (3 à 24 caractères alphanumériques/tirets/underscores) et le filtrage des termes abusifs.

3. **Protection & Portabilité Multi-Appareils (Modèle IRC / NickServ) :**
   - Pour retrouver sa progression, ses scores et ses statistiques sur un autre appareil (smartphone, tablette, autre navigateur), le joueur peut "revendiquer" (*claim*) son compte en définissant un mot de passe.
   - Le mot de passe est haché de manière sécurisée en base (`bcrypt` / `argon2` / PBKDF2 standardisé).

4. **Clé de Récupération par Phrase Secrète (4 Mots Thématiques) :**
   - En l'absence d'adresse email, la réinitialisation de mot de passe s'appuie sur une phrase secrète de secours composée de **4 mots français de vocabulaire** (ex. `citron - falaise - navire - vortex`).
   - Cette phrase est affichée une seule fois lors de la protection du compte, avec bouton de copie rapide et avertissement clair.
   - La clé est stockée hachée en base (`recovery_key_hash`).

5. **Préparation à l'Extensibilité Future (Google Sign-In) :**
   - Le schéma de données et l'abstraction d'authentification prévoient nativement un champ `google_sub` (identifiant universel Google) et `auth_provider`, permettant d'activer la connexion Google OAuth en un clic dans une évolution ultérieure sans refonte de table.

---

## 2. Spécification Technique & Architecture

### 2.1 Schéma Relationnel PostgreSQL & Idempotence (`database/init.sql`)

La création de la table doit être **100 % idempotente** :
- Exécutable à l'initialisation du conteneur PostgreSQL via `/docker-entrypoint-initdb.d/init.sql`.
- Ré-exécutable sans erreur 20 fois d'affilée (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).

```sql
-- 9. Table des joueurs et authentification sans email (M14)
CREATE TABLE IF NOT EXISTS players (
    id UUID PRIMARY KEY,
    auth_token VARCHAR(64) NOT NULL UNIQUE,
    username VARCHAR(32) NOT NULL UNIQUE,
    can_change_username BOOLEAN NOT NULL DEFAULT TRUE,
    is_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255),
    recovery_key_hash VARCHAR(255),
    auth_provider VARCHAR(16) NOT NULL DEFAULT 'local',
    google_sub VARCHAR(64) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    renamed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_players_token ON players(auth_token);
CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);
CREATE INDEX IF NOT EXISTS idx_players_google_sub ON players(google_sub);
```

### 2.2 Repli Local Idempotent SQLite (`src/db/connection.py`)

Afin de garantir le fonctionnement des tests unitaires et du mode autonome sans conteneur PostgreSQL :
- Intégration du schéma DDL équivalent dans `PG_SCHEMA` et `SQLITE_SCHEMA`.
- Gestion des migrations douces idempotentes au démarrage applicatif Python : vérification de l'existence de la table `players` et création automatique si absente lors de l'appel à `init_db()` ou à la connexion.

```sql
-- Schéma SQLite équivalent
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    auth_token TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    can_change_username BOOLEAN NOT NULL DEFAULT 1,
    is_claimed BOOLEAN NOT NULL DEFAULT 0,
    password_hash TEXT,
    recovery_key_hash TEXT,
    auth_provider TEXT NOT NULL DEFAULT 'local',
    google_sub TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    renamed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_players_token ON players(auth_token);
CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);
```

### 2.3 Service Métier d'Authentification (`src/services/player_auth.py`)

Ce service centralise :
1. **Générateur de pseudos loufoques :**
   - Deux listes de vocabulaire soignées en français :
     - Adjectifs : *Cosmique, Furtif, Flamboyant, Électrique, Solaire, Malicieux, Philosophe, Gourmand, Lunaire, Véloce, Agile, Héroïque, etc.*
     - Animaux / Figurants : *Castor, Pangolin, Suricate, Caméléon, Lémurien, Tournesol, Faucon, Hérisson, Renard, Blaireau, Koala, Lynx, etc.*
   - Combinaison déterministe avec suffixe numérique aléatoire en cas de collision (ex: `CastorCosmique73`).
2. **Générateur de phrases de secours :**
   - Dictionnaire dédié de 256 ou 512 mots concrets simples de la langue française, sans ambiguïté orthographique ni accents piégeux (ex: *falaise, boussole, navire, volcan, cristal, citron, cascade, comete, horizon, galaxie, nuage, riviere...*).
   - Sélection aléatoire cryptographiquement sûre de 4 mots (`secrets.choice`).
3. **Sécurité cryptographique des mots de passe & tokens :**
   - Hachage sécurisé : `hashlib.pbkdf2_hmac` avec salt aléatoire de 16 octets et 200 000 itérations (inclus dans la bibliothèque standard Python, évitant toute dépendance C compilée fragile), ou `bcrypt` si disponible.
   - Normalisation stricte de la phrase de secours avant hachage (minuscules, retrait des accents éventuels, suppression des espaces superflus, jointure par tirets).
4. **Validation et cycle de vie :**
   - Vérification du token de session `auth_token` sur chaque requête authentifiée.
   - Mise à jour atomique de `last_seen_at`.

### 2.4 Endpoints API REST Dédiés & Routage Caddy (`Caddyfile`)

| Méthode | Route | Description | Entrée | Réponse |
|---|---|---|---|---|
| `POST` | `/api/player/guest` | Initialisation ou récupération d'un profil invité | `{ "player_id": optional_uuid, "auth_token": optional_token }` | `{ "player_id", "auth_token", "username", "can_change_username", "is_claimed" }` |
| `POST` | `/api/player/rename` | Personnalisation unique du pseudo | `{ "new_username": "MonPseudo" }` + Header `Authorization: Bearer <auth_token>` | `{ "success": true, "username": "MonPseudo", "can_change_username": false }` |
| `POST` | `/api/player/claim` | Protection du compte par mot de passe | `{ "password": "..." }` + Header `Authorization: Bearer <auth_token>` | `{ "success": true, "is_claimed": true, "recovery_phrase": "mot1 mot2 mot3 mot4" }` |
| `POST` | `/api/player/login` | Connexion depuis un autre appareil | `{ "username": "...", "password": "..." }` | `{ "player_id", "auth_token", "username", "can_change_username", "is_claimed" }` |
| `POST` | `/api/player/reset-password` | Réinitialisation par phrase secrète | `{ "username": "...", "recovery_phrase": "...", "new_password": "..." }` | `{ "success": true, "message": "Mot de passe réinitialisé avec succès" }` |

#### Précision Routage & Reverse-Proxy (`Caddyfile` hors Git) :
- **Règle de routage existante :** Dans `Caddyfile`, toutes les requêtes préfixées par `/api/*` sont déjà captées et transmises au conteneur web :
  ```caddy
  handle /api/* {
      header X-Robots-Tag "noindex, nofollow"
      reverse_proxy cemantix_web:8000
  }
  ```
- **Conséquence directe :** En positionnant l'intégralité des endpoints d'authentification sous `/api/player/*`, **aucune modification de route n'est nécessaire dans `Caddyfile`**. Tout arrive directement sur `cemantix_web:8000`.
- **Cache-Control & Sécurité :** Le backend Python doit impérativement émettre les en-têtes `Cache-Control: no-store, private` sur tous les endpoints `/api/player/*` afin d'éviter toute mise en cache de jetons de session ou de phrases de secours par les mandataires ou navigateurs.
- **Rappel opérationnel (`Caddyfile` hors Git) :** Le fichier `Caddyfile` étant ignoré par Git (`.gitignore`), si une directive spécifique venait à être ajoutée (ex: limitation de débit *rate-limiting* ou en-têtes spécifiques), elle devra être appliquée manuellement sur le fichier local et sur le VPS `/docker/cemantix-rag-solver/Caddyfile` puis rechargée via `docker compose exec caddy caddy reload`.

### 2.5 Composants Frontend & Expérience Utilisateur

1. **Badge Header (`src/services/layout_sync.py`) :**
   - Insertion dans le composant réutilisable d'en-tête (à côté du switch dark/light theme) d'un conteneur discret :
     `<div id="player-badge" class="player-badge">...</div>`.
2. **Modale Profil Joueur (`volumes/web/js/auth.js`, `volumes/web/css/auth.css`) :**
   - Interface dynamique gérant les 3 états :
     - Consultation du profil et renommage unique.
     - Sécurisation du compte (saisie du mot de passe et affichage de la phrase de 4 mots avec bouton copier).
     - Connexion / Récupération de compte.
3. **Synchronisation `localStorage` :**
   - Clé persistante `cemantix_player_session` contenant `{ playerId, authToken, username, isClaimed, canChangeUsername }`.
   - Si la clé est absente, appel transparent à `/api/player/guest` au chargement de n'importe quelle vue.

---

## 3. Plan d'Exécution & Découpage des Commits

Conformément aux directives de développement :
- Les modifications de code sont livrées par fonctionnalités cohérentes.
- Le dernier commit est impérativement la documentation.

### Découpage proposé pour la réalisation ultérieure :
1. **Commit 1 — Base de données & Migrations :**
   `feat(db): schema relationnel idempotent et persistance des profils joueurs`
2. **Commit 2 — Service Métier & Dictionnaires :**
   `feat(auth): service de generation de pseudos loufoques, tokens et phrase de secours`
3. **Commit 3 — Routes API Backend :**
   `feat(api): endpoints rest pour inscription invite, renommage, protection et reconnexion`
4. **Commit 4 — Interface Frontend & Layout :**
   `feat(web): integration du badge joueur dans le header et modale de gestion du profil`
5. **Commit 5 — Documentation & Validation :**
   `docs: documentation complete du jalon m14, roadmap et mise a jour du changelog`

---

## 4. Critères d'Acceptation & Validation

- [ ] `database/init.sql` crée la table `players` et ses index sans erreur lors d'un `docker compose up` initial.
- [ ] Le démarrage Python initialise automatiquement la table `players` dans SQLite et PostgreSQL sans erreur même si la table existe déjà (idempotence totale).
- [ ] Un visiteur arrivant sur le site se voit attribuer un pseudo loufoque et un UUID sans aucune action de sa part.
- [ ] Le renommage fonctionne une seule fois et est définitivement verrouillé ensuite côté serveur.
- [ ] La protection du compte renvoie 4 mots de vocabulaire cohérents et permet ensuite la reconnexion avec pseudo + mot de passe depuis un autre navigateur.
- [ ] La phrase de secours permet de restaurer l'accès au compte en cas d'oubli du mot de passe.
- [ ] La suite de tests unitaires Docker s'exécute avec 100 % de succès.
- [ ] `tools/check_docs.py` et `tools/check_seo.py` sortent verts.

