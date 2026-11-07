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

La création des tables doit être **100 % idempotente** :
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

-- 10. Dictionnaire dynamique de vocabulaire pour identités & récupération (M14)
-- Types : 'noun' (Noms), 'adjective' (Adjectifs), 'recovery' (Mots de secours)
CREATE TABLE IF NOT EXISTS player_dictionary (
    id SERIAL PRIMARY KEY,
    word_type VARCHAR(16) NOT NULL,            -- 'noun', 'adjective', 'recovery'
    word VARCHAR(32) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word_type, word)
);
CREATE INDEX IF NOT EXISTS idx_dict_type ON player_dictionary(word_type, is_active);
```

### 2.2 Repli Local Idempotent SQLite (`src/db/connection.py`)

Afin de garantir le fonctionnement des tests unitaires et du mode autonome sans conteneur PostgreSQL :
- Intégration du schéma DDL équivalent dans `PG_SCHEMA` et `SQLITE_SCHEMA`.
- Gestion des migrations douces idempotentes au démarrage applicatif Python : vérification de l'existence des tables `players` et `player_dictionary`, création automatique si absentes et amorçage (*seeding*) automatique du dictionnaire par défaut si la table est vide.

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

CREATE TABLE IF NOT EXISTS player_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_type TEXT NOT NULL,
    word TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word_type, word)
);
CREATE INDEX IF NOT EXISTS idx_dict_type ON player_dictionary(word_type, is_active);
```

### 2.3 Service Métier d'Authentification (`src/services/player_auth.py`)

Ce service centralise :
1. **Générateur de pseudos loufoques (Syntaxe stricte : `[Nom][Adjectif]`) :**
   - **Règle grammaticale absolue en français :** Ordre strict `Nom` suivi de l'`Adjectif` (ex: `CastorCosmique`, `PangolinFurtif`, `SuricateFlamboyant`). Aucun mélange inversé `AdjectifNom`.
   - **Contrainte de longueur et casse :** CamelCase sans espace, longueur totale bornée entre 8 et 24 caractères. En cas de collision en base, ajout d'un suffixe numérique aléatoire (ex: `CastorCosmique42`).
   - **Chargement dynamique :** Lecture en base de données (`player_dictionary`) avec cache mémoire optimisé pour la performance, et repli de secours sur une liste codée en dur si la table est momentanément inaccessible.
2. **Générateur de phrases de secours :**
   - Sélection aléatoire cryptographiquement sûre (`secrets.choice`) de 4 mots issus de `player_dictionary` (`word_type = 'recovery'`).
   - Dictionnaire de base : au moins 256 mots concrets simples de la langue française, sans ambiguïté orthographique ni accents piégeux (ex: *falaise, boussole, navire, volcan, cristal, citron, cascade, comete, horizon, galaxie, nuage, riviere...*).
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
| `GET` | `/api/snap-9x/dictionary` | (Admin) Liste des mots par catégorie | Header Admin Token / Session | `{ "nouns": [...], "adjectives": [...], "recovery": [...] }` |
| `POST` | `/api/snap-9x/dictionary` | (Admin) Ajout d'un mot dans le dictionnaire | `{ "word_type": "noun|adjective|recovery", "word": "..." }` | `{ "success": true, "id": 123 }` |
| `DELETE` | `/api/snap-9x/dictionary/<id>` | (Admin) Désactivation ou suppression d'un mot | Header Admin Token / Session | `{ "success": true }` |

#### Précision Routage & Reverse-Proxy (`Caddyfile` hors Git) :
- **Routage automatique :** Dans `Caddyfile`, toutes les requêtes préfixées par `/api/*` sont déjà captées et transmises au conteneur web :
  ```caddy
  handle /api/* {
      header X-Robots-Tag "noindex, nofollow"
      reverse_proxy cemantix_web:8000
  }
  ```
- **Conséquence directe :** En positionnant l'intégralité des endpoints sous `/api/player/*` et `/api/snap-9x/dictionary`, **aucune modification de route n'est nécessaire dans `Caddyfile`**. Tout arrive directement sur `cemantix_web:8000`.
- **Cache-Control & Sécurité :** Le backend Python doit impérativement émettre les en-têtes `Cache-Control: no-store, private` sur tous les endpoints `/api/player/*` afin d'éviter toute mise en cache de jetons de session ou de phrases de secours par les mandataires ou navigateurs.
- **Rappel opérationnel (`Caddyfile` hors Git) :** Le fichier `Caddyfile` étant ignoré par Git (`.gitignore`), si une directive spécifique venait à être ajoutée (ex: limitation de débit *rate-limiting* ou en-têtes spécifiques), elle devra être appliquée manuellement sur le fichier local et sur le VPS `/docker/cemantix-rag-solver/Caddyfile` puis rechargée via `docker compose exec caddy caddy reload`.

### 2.5 Console d'Exploitation Administrateur (`volumes/web/panier-9x`)

Ajout d'un panneau d'administration dans la console sécurisée `/panier-9x` (section "Gestion des vocabulaires" dans Actions ou onglet dédié) :
- **Maintenance des Listes de Vocabulaire Joueurs :**
  - Affichage paginé ou groupé par type :
    - 🐻 **Noms (Animaux / Personnages)** (1er élément du pseudo).
    - ✨ **Adjectifs (Qualificatifs français)** (2nd élément du pseudo).
    - 🔑 **Mots de Récupération** (phrase secrète de 4 mots).
  - Formulaire d'ajout immédiat avec validation (pas d'espaces, pas de caractères spéciaux, respect de la casse).
  - Suppression ou bascule actif/inactif sans redémarrage de conteneur.

### 2.6 Spécification UX Détaillée & Garantie d'Innocuité SEO

L'architecture UX concilie une découverte immédiate et ludique pour le joueur avec le respect absolu des critères **Core Web Vitals** et des directives Google sur les interstitiels mobiles :

1. **Garantie d'Innocuité SEO (Zéro Pénalité Google & CLS = 0) :**
   - **Interdiction formelle des modales bloquantes à l'arrivée :** Conformément à l'algorithme Google contre les *« Intrusive Interstitials »*, aucune boîte de dialogue modale masquant le plateau de jeu ne doit s'ouvrir automatiquement au chargement initial.
   - **Zéro pollution pour Googlebot :** Les composants d'accueil et d'identité joueur sont injectés côté client via JavaScript (`volumes/web/js/auth.js`) après vérification du `localStorage`. Le HTML initial servi aux moteurs de recherche demeure 100 % dédié au jeu et au mot du jour.
   - **Stabilité visuelle (CLS = 0) :** L'emplacement du badge d'identité dans le Header réserve sa largeur ou s'intègre en flexbox sans provoquer de décalage d'éléments lors de son initialisation asynchrone.

2. **Toast / Bannière d'Accueil Non Intrusive (Première Visite) :**
   - Lors de la toute première visite d'un joueur (absence de session dans le `localStorage`), un bandeau élégant et flottant glisse discrètement en bas de l'écran ou sous l'en-tête, sans recouvrir les champs de saisie du jeu :
     ```text
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │ 👋 Bienvenue ! Ton identité de jeu est CastorCosmique.                       │
     │    [ ✏️ Personnaliser mon pseudo ]       [ C'est parti ! ]       [×]         │
     └──────────────────────────────────────────────────────────────────────────────┘
     ```
   - **Comportement des actions :**
     - Clic sur `[ ✏️ Personnaliser mon pseudo ]` : ouvre immédiatement la modale de profil centrée sur le champ de renommage.
     - Clic sur `[ C'est parti ! ]` ou sur la croix `[×]` : masque immédiatement le bandeau et enregistre la préférence `cemantix_welcome_dismissed = true` dans le `localStorage`.
     - Case à cocher ou comportement automatique « Ne plus afficher ce message ».

3. **Badge Permanent dans l'En-tête (`src/services/layout_sync.py`) :**
   - Dans le Header unifié (à côté de la bascule thème sombre/clair), affichage d'une pilule interactive discrète :
     ```text
     [ 👤 CastorCosmique ▾ ]
     ```
   - Cliquer sur ce badge ouvre à tout moment la modale de profil, sur n'importe quelle vue (`/`, `/play/`, `/battle/`, `/multi/`, `/defi/`).

4. **Modale Profil Joueur (`<dialog class="modal">`) :**
   - Utilisation de la balise HTML standard native `<dialog>` avec le style déjà éprouvé dans le projet (`volumes/web/panier-9x/console.css` et `volumes/web/css/`).
   - L'ouverture de la modale ne s'effectue **qu'à la suite d'un clic volontaire du joueur** (bouton "Personnaliser" ou clic sur le badge Header), ce qui garantit une expérience utilisateur optimale et zéro pénalité SEO.
   - La modale gère 3 vues dynamiques :
     - **Vue A (Profil & Renommage unique) :** Affiche le pseudo actuel, un avertissement clair *"Personnalisation possible une seule fois"*, le champ de saisie du nouveau pseudo (validé côté serveur 8 à 24 car.), et un bouton `[ 🔒 Protéger mon compte ]`.
     - **Vue B (Sécurisation & Phrase de 4 mots) :** Saisie du mot de passe souhaité, génération et affichage de la phrase de 4 mots concrets (`navire - falaise - citron - vortex`) avec bouton 📋 `[Copier la phrase]` et avertissement sans email.
     - **Vue C (Connexion / Récupération multi-appareils) :** Formulaire de reconnexion pour restaurer son identité sur un nouveau smartphone ou PC (`Pseudo + Mot de passe`), avec onglet de secours par phrase secrète en cas d'oubli.

5. **Cycle de Vie & Synchronisation `localStorage` :**
   - Clé `cemantix_player_session` : `{ playerId, authToken, username, isClaimed, canChangeUsername }`.
   - Clé `cemantix_welcome_dismissed` : `true`.
   - Initialisation silencieuse : si aucune session n'est détectée, un appel transparent en tâche de fond est émis vers `POST /api/player/guest` pour enregistrer l'UUID et le pseudo loufoque sans bloquer l'interactivité de la page.

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

