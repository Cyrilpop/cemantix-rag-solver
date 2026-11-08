# Jalon M15 — Mot du Jour Solo Aléatoire Pondéré, Classement Communautaire & Indices IA Roulants

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m15-mot-du-jour-solo` (base `main`)  
**Statut :** 📝 Spécifié & Cadré (Validé pour implémentation)  
**Périmètre exclusif :** `database/init.sql`, `src/db/connection.py`, `src/db/solo.py` (ou `src/db/` associé), `src/game/solo.py`, `src/game/manager.py`, `src/services/daemon.py`, `src/services/solo_daily.py`, nouveau simulateur de trajectoire IA dans `src/ai/` (`prompts.py`, `trajectory_sim.py`), routes API REST backend (`src/api/routes/solo.py`), templates et composants UI frontend (`volumes/web/play/index.html`, `volumes/web/js/game.js`, `volumes/web/css/modal.css`), suite de tests sous Docker (`tests/test_solo_daily.py`), et documentation associée (`docs/roadmap/2026-11-08-tirage-mot-classement-indices-solo/`, `docs/roadmap/README.md`, `README.md`, `CHANGELOG.md`).  
**Périmètre exclu pour ce jalon :** Pas de modification des modes multijoueurs (`/multi/`) ni des duels IA (`/battle/`). Le mode illimité reste fonctionnel en mémoire/localStorage sans persistance BDD.  
**Suite de validation requise :** Tests unitaires automatisés sous Docker Python 3.12 (`docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests`), `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check`.  
**Règle d'or environnement :** L'intégralité du projet s'exécute sous Docker. Aucune commande Python, pip ou test ne doit être exécutée directement sur la machine hôte.

---

## 1. Objectifs Métier et Expérience Utilisateur (UX)

Actuellement, le jeu Solo accessible sur `/play/` s'appuie sur le mot officiel du jour Cémantix (résolu par le solveur à minuit) ou sur des parties illimitées non persistées. De plus, la tuile « Vos meilleurs mots » est bridée à un Top 10 strict, la tuile « Historique de vos coups » fait doublon sans valeur communautaire, et les tentatives des joueurs ne sont pas historisées en base relationnelle.

Le présent **Jalon M15** opère une refonte complète du mode Solo Quotidien pour en faire un jeu communautaire autonome, compétitif, persistant et animé :

1. **Mot du Jour Autonome Aléatoire & Unique (Pondération à 4 Niveaux) :**
   - Le mot du jour n'est plus assujetti au mot officiel Cémantix externe. Il est tiré au sort de manière autonome tous les jours à minuit (`00h00`) par le démon.
   - Le mot est **unique et strictement le même pour tous les joueurs** sur une journée donnée.
   - Le tirage applique une distribution de probabilité pondérée selon la fréquence d'usage des mots français (corpus frWac) :
     - 🟢 **Facile : 15 %** (top 4 000 mots les plus fréquents du quotidien).
     - 🟡 **Normal : 75 %** (vocabulaire courant entre le rang 4 000 et 16 000).
     - 🔴 **Difficile : 9 %** (vocabulaire plus rare et conceptuel au-delà du rang 16 000).
     - 🟣 **Extrême : 1 %** (*nouvelle catégorie exclusive* : uniquement le dernier 1 % des mots les moins usités de la base).
   - Le mode **Illimité** est conservé en parallèle pour l'entraînement libre sans écriture en base de données.

2. **Refonte Visuelle des Tuiles de Jeu (`/play/`) :**
   - **Tuile « Tous vos Mots » (remplace le Top 10 limité) :**
     - Affiche **l'intégralité** des mots testés par le joueur, ordonnés du plus chaud en haut au plus froid en bas.
     - Chaque mot dispose de sa jauge de température et de son thermomètre coloré, calculés sur le même modèle que le bandeau de spotlight du dernier coup.
   - **Tuile « Classement des Joueurs » (remplace « Historique de vos coups ») :**
     - Affiche en direct le tableau d'honneur des joueurs ayant découvert le mot secret du jour.
     - **Visible dès le début de la partie** afin de créer une dynamique compétitive et de mettre le joueur en saine émulation.
     - Trié par **nombre de coups croissants** (le plus économe en premier), avec départage au temps écoulé (`duration_seconds`).
     - Affichage du rang (🥇, 🥈, 🥉, puis rang numérique), du pseudo joueur (issu de l'identité M14), du nombre d'essais et du badge de complétion.
     - **Protection Anti-Triche & Anti-Spoiler Stricte sur les Trajectoires :**
       - Si le classement (rang, pseudo, nombre de coups) est bien visible dès l'ouverture, **la trajectoire détaillée (les mots joués par les gagnants) est strictement verrouillée**.
       - Un joueur en cours de partie ne peut en aucun cas ouvrir ou consulter la trajectoire / le replay des gagnants.
       - La consultation de la trajectoire d'un joueur du classement n'est débloquée qu'une fois la partie du joueur terminée : **soit après victoire (`won`), soit après abandon (`given_up`)**.
       - **Sécurité côté API :** Le serveur refuse de servir le détail des coups via `GET /api/solo/trajectory/{game_id}` si la session du joueur demandeur n'est pas clôturée (`won` ou `given_up`).

3. **Trois Indices IA Roulants par Joueur (Google Gemini) :**
   - Chaque joueur dispose d'un crédit maximum de **3 indices IA par jour**.
   - **Règle de coût :** **1 indice consommé = +1 coup** au compteur d'essais du joueur.
   - **Température des indices :** Le score sémantique, la température et le rang millième (‰) sont calculés vis-à-vis du mot secret comme pour un coup normal.
   - **Modale de Choix à Chaque Demande d'Indice :**
     - À chaque demande d'indice (#1, #2, #3), une modale native s'ouvre demandant au joueur le format souhaité : **Mot** ou **Phrase**.
     - Le joueur est totalement libre d'alterner les formats selon ses besoins (ex: Indice #1 en *Mot*, Indice #2 en *Phrase*, Indice #3 en *Mot*).
     - **Immuabilité stricte par indice :** Une fois qu'un indice `#k` a été demandé et servi dans un format donné, **il ne peut plus être converti ou rejoué dans l'autre format** pour ce même palier (interdiction absolue de cumuler le mot ET la phrase pour un même indice).
   - **Indices roulants stricts :** Purge quotidienne automatique à minuit lors du tirage du nouveau mot (seule la journée en cours est conservée en base pour les indices).

4. **Classement Animé & Pool Fixe de 20 « Habitués » (Anti-Désertion à 6h30) :**
   - **Pool Réservé de 20 Joueurs Fictifs Récurrents :**
     - Pour une crédibilité maximale et un sentiment de communauté authentique, on bloque un contingent fixe de **20 profils fictifs dits « les habitués »**.
     - Leurs combinaisons `[Nom][Adjectif]` (ex: `CastorCosmique`, `PangolinFurtif`, `LynxAudacieux`, etc.) sont **strictement réservées** : aucun joueur humain ne peut se renommer ou être généré avec l'un de ces 20 pseudos.
   - **Rotation Naturelle (Ils ne jouent pas tous les jours) :**
     - À partir de **6h30 du matin**, si aucun joueur réel n'a encore résolu le mot du jour, le système ne génère pas des profils jetables inconnus : il **tire au sort un échantillon de 7 à 10 joueurs parmi ce pool de 20 habitués**.
     - Les joueurs reconnaissent ainsi des pseudonymes familiers au fil des semaines, avec des présences et des absences naturelles.
   - **Mix Humain Calibré selon la Difficulté (Succès & Échecs) :**
     - Parmi les 7 à 10 habitués sélectionnés pour la journée, le taux de réussite dépend directement du niveau de difficulté tiré au sort :
       - 🟢 **Facile : 95 % de succès** (5 % d'échecs $\rightarrow$ quasi tous gagnent, 0 ou 1 abandon).
       - 🟡 **Normal : 75 % de succès** (25 % d'échecs $\rightarrow$ ~5 à 7 gagnants pour 2 à 3 abandons).
       - 🔴 **Difficile : 25 % de succès** (75 % d'échecs $\rightarrow$ seulement 2 gagnants pour 6 à 8 abandons).
       - 🟣 **Extrême : 5 % de succès** (95 % d'échecs $\rightarrow$ au plus 0 ou 1 gagnant héroïque, tous les autres abandonnent).
     - Les gagnants alimentent le tableau d'honneur public (trié par nombre de coups).
     - Les abandons alimentent les compteurs globaux `players_attempted` et `players_failed` de `solo_daily_puzzles`.
   - **Réalisme humain absolu (Sémantique vs RAG) :**
     - Un humain ne résout pas un Cémantix en 10 coups ! La distribution des coups simulés est réaliste (entre **45 et 120 coups** pour les victoires, et **30 à 70 coups** pour les abandons après errance sémantique).
     - La trajectoire n'utilise **pas le moteur RAG mathématique** (qui converge froidement par vecteurs), mais une **simulation sémantique par IA générative** (`Gemini`) reproduisant le comportement d'un joueur humain : mots de départ thématiques, association d'idées, fausses pistes, paliers de réflexion, puis convergence finale vers le mot secret (ou égarement/découragement pour les abandons).
   - **Traçabilité & Transparence Admin :**
     - Colonne `is_bot BOOLEAN NOT NULL DEFAULT FALSE` en base de données.
     - Flag visible et filtrable **uniquement par l'administrateur**, invisible pour les visiteurs.
   - **Appel Unique Groupé (Batch JSON) & Verrou d'Idempotence (Lock) :**
     - La génération de tous les profils et trajectoires s'effectue en **un seul appel global à l'API Gemini** retournant un document JSON complet.
     - **Verrouillage strict anti-rejeu :** Une colonne `bots_simulated BOOLEAN NOT NULL DEFAULT FALSE` dans `solo_daily_puzzles` agit comme un verrou : si l'injection a déjà eu lieu pour la journée, tout nouvel appel est immédiatement bloqué.
     - **Option de Déclenchement Forcé :** Possibilité de forcer l'exécution manuelle (via CLI ou console admin `/panier-9x`) sans attendre 6h30, avec gestion sécurisée du verrou.

5. **Historisation Ciblée & Économique en Base de Données :**
   - **Règle stricte d'enregistrement :** Pour préserver l'espace disque, la trajectoire détaillée (`solo_player_guesses`) et la session (`solo_player_games`) ne sont persistées en base que pour les parties du Mot du Jour, et **uniquement si le joueur a terminé la partie** :
     - Soit par **victoire** (`status = 'won'`),
     - Soit par **abandon** (`status = 'given_up'`, incrémente `players_failed` et dévoile le mot secret).
   - Les abandons passifs (visiteurs éphémères fermant l'onglet) ne polluent pas la base de données.

---

## 2. Spécification Technique & Schéma Relationnel

### 2.1 Schéma Relationnel PostgreSQL & Idempotence (`database/init.sql`)

Toutes les créations de tables et index sont strictement idempotentes (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) :

```sql
-- ============================================================================
-- 11. Tables du Mot du Jour Solo Aléatoire, Classement & Coups Joueurs (Jalon M15)
-- ============================================================================

-- A. Table des puzzles quotidiens Solo (mot unique du jour tiré au sort)
CREATE TABLE IF NOT EXISTS solo_daily_puzzles (
    id                SERIAL PRIMARY KEY,
    puzzle_date       DATE NOT NULL UNIQUE,
    secret_word       VARCHAR(64) NOT NULL,
    difficulty        VARCHAR(16) NOT NULL,     -- 'facile', 'normal', 'difficile', 'extreme'
    players_attempted INT NOT NULL DEFAULT 0,
    players_succeeded INT NOT NULL DEFAULT 0,
    players_failed    INT NOT NULL DEFAULT 0,
    bots_simulated    BOOLEAN NOT NULL DEFAULT FALSE, -- Lock anti-rejeu simulation faux joueurs
    bots_simulated_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_solo_daily_puzzles_date ON solo_daily_puzzles(puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_daily_puzzles_diff ON solo_daily_puzzles(difficulty);

-- B. Table des indices IA Gemini roulants (1 seule journée active, purge auto à minuit)
CREATE TABLE IF NOT EXISTS solo_daily_ai_hints (
    id          SERIAL PRIMARY KEY,
    puzzle_date DATE NOT NULL REFERENCES solo_daily_puzzles(puzzle_date) ON DELETE CASCADE,
    hint_level  INT NOT NULL,                  -- 1 (éloigné), 2 (intermédiaire), 3 (proche)
    weight      NUMERIC(4, 2) NOT NULL,        -- 0.33, 0.66, 1.00
    hint_word   VARCHAR(100) NOT NULL,
    hint_phrase TEXT NOT NULL,
    score       NUMERIC(6, 2) DEFAULT 0.0,
    permille    INT DEFAULT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, hint_level)
);
CREATE INDEX IF NOT EXISTS idx_solo_ai_hints_date ON solo_daily_ai_hints(puzzle_date);

-- C. Table des sessions et scores des joueurs pour le puzzle du jour
CREATE TABLE IF NOT EXISTS solo_player_games (
    id                 UUID PRIMARY KEY,
    puzzle_date        DATE NOT NULL REFERENCES solo_daily_puzzles(puzzle_date) ON DELETE CASCADE,
    player_id          UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status             VARCHAR(16) NOT NULL DEFAULT 'in_progress', -- 'won', 'given_up'
    tries_count        INT NOT NULL DEFAULT 0,
    hints_used         INT NOT NULL DEFAULT 0,                     -- Max 3
    hints_revealed     JSONB NOT NULL DEFAULT '[]'::jsonb,         -- Détail [{level, type, content}]
    best_score         NUMERIC(6, 2) DEFAULT 0.0,
    best_permille      INT DEFAULT NULL,
    duration_seconds   NUMERIC(8, 2) DEFAULT 0.0,
    is_bot             BOOLEAN NOT NULL DEFAULT FALSE,             -- Flag admin pour faux joueurs
    won_at             TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, player_id)
);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_date ON solo_player_games(puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_player ON solo_player_games(player_id);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_leaderboard ON solo_player_games(puzzle_date, status, tries_count, duration_seconds);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_bot ON solo_player_games(is_bot);

-- D. Table d'historisation des trajectoires de parties terminées (Gagnées ou Abandonnées)
CREATE TABLE IF NOT EXISTS solo_player_guesses (
    id          BIGSERIAL PRIMARY KEY,
    game_id     UUID NOT NULL REFERENCES solo_player_games(id) ON DELETE CASCADE,
    player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    puzzle_date DATE NOT NULL,
    guess_order INT NOT NULL,
    word        VARCHAR(64) NOT NULL,
    score       NUMERIC(6, 2) NOT NULL,
    permille    INT,
    weather     VARCHAR(8),
    is_hint     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, guess_order)
);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_game ON solo_player_guesses(game_id);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_player_date ON solo_player_guesses(player_id, puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_word ON solo_player_guesses(word);
```

### 2.2 Repli Local Idempotent SQLite (`src/db/connection.py`)

Les schémas DDL correspondants sont déclarés dans `PG_SCHEMA` et `SQLITE_SCHEMA` dans `src/db/connection.py` afin de supporter nativement les tests unitaires locaux sans conteneur PostgreSQL :
- `id INTEGER PRIMARY KEY AUTOINCREMENT` pour les clés auto-incrémentées SQLite.
- `UUID` représenté en `TEXT` et `BOOLEAN` sous forme `INTEGER (0/1)`.

---

## 3. Étude d'Impact & Estimation Révisée de la Volumétrie BDD

L'enregistrement exclusif des parties **abouties** (succès ou abandon explicite) modifie très avantageusement l'empreinte disque par rapport à une historisation aveugle en continu.

### 3.1 Poids Unitaire d'une Ligne

- **Ligne de coup (`solo_player_guesses`) :** ~104 octets de données + ~130 octets d'index = **~234 octets par coup**.
- **Ligne de session (`solo_player_games`) :** **~265 octets par session**.
- **Ligne de puzzle quotidien & indices IA :** **~1,2 Ko par jour** (constant grâce à la purge roulante).

### 3.2 Projections de Croissance (Parties Terminées + Faux Joueurs)

*Hypothèses :*
- Les parties terminées comptent en moyenne **65 coups** (gagnées ou abandonnées après recherche poussée).
- Ajout quotidien de **8 à 10 faux joueurs réalistes** (moyenne de ~70 coups chacun = ~160 Ko/jour).
- Taux de complétion estimé à 60 % des visiteurs uniques (les rebonds rapides ne consomment aucun octet en BDD).

| Métrique / Scénario | 🟢 Profil Modeste (60 parties finies/j) | 🟡 Profil Moyen (600 parties finies/j) | 🔴 Profil Élevé (6 000 parties finies/j) |
|---|---|---|---|
| **Coups réels enregistrés / jour** | ~3 900 coups | ~39 000 coups | ~390 000 coups |
| **Coups faux joueurs (6h30) / jour** | ~650 coups | ~650 coups | ~650 coups |
| **Volumétrie journalière totale** | **~1,06 Mo / jour** | **~9,28 Mo / jour** | **~91,4 Mo / jour** |
| **Croissance mensuelle (30 j)** | **~32 Mo / mois** | **~278 Mo / mois** | **~2,74 Go / mois** |
| **Croissance annuelle (365 j)** | **~387 Mo / an** | **~3,38 Go / an** | **~33,3 Go / an** |

> [!NOTE]
> Grâce au filtrage des seules parties achevées, la base de données économise plus de 30 % de volume par rapport à une écriture brute au fil de l'eau, tout en garantissant une intégrité parfaite des trajectoires enregistrées.

---

## 4. Tirage Aléatoire Quotidien Pondéré & Pool Extrême

### 4.1 Calibration des Probabilités
Le tirage au sort s'exécute tous les jours à `00h00:00` (ou au premier démarrage du démon s'il était arrêté).  
La difficulté est choisie selon la loi de probabilité pondérée :
- **Facile (15 %) :** Poids = 15
- **Normal (75 %) :** Poids = 75
- **Difficile (9 %) :** Poids = 9
- **Extrême (1 %) :** Poids = 1

### 4.2 Définition du Pool « Extrême »
Dans `src/game/manager.py`, les mots candidats sont ordonnés selon leur rang de fréquence dans le corpus `frWac`.
- La catégorie **Extrême** isole strictement les **1 % des mots les moins fréquents** du vocabulaire disponible après assainissement (mots d'au moins 4 lettres, hors stopwords, hors pluriels triviaux).
- Ce pool est dédié exclusivement au tirage du mode Solo quotidien.

---

## 5. Gestion des 3 Indices IA Roulants & Choix par Palier

1. **Génération à Minuit :**
   Dès que le mot du jour est tiré au sort par le démon, le service appelle `GeminiClient.generate_hints(secret_word)` (`src/ai/gemini_client.py`). Les scores cosinus et rangs ‰ de chaque indice sont précalculés.
2. **Stockage Rapide en Base :**
   Les 3 niveaux d'indices (avec `hint_word`, `hint_phrase`, `score` et `permille`) sont insérés dans `solo_daily_ai_hints`.
3. **Purge Roulante :**
   Une clause `DELETE FROM solo_daily_ai_hints WHERE puzzle_date < CURRENT_DATE` garantit qu'aucune trace des indices de la veille n'est conservée.
4. **Modale de Choix à Chaque Demande d'Indice :**
   - À chaque palier d'indice demandé (#1, #2, puis #3), une modale s'affiche et demande au joueur : `Mot` ou `Phrase` ?
   - L'utilisateur peut tout à fait choisir un mot pour l'indice #1, puis une phrase pour l'indice #2, et un mot pour l'indice #3.
   - **Immuabilité stricte par indice :** Une fois le format validé pour l'indice `#k`, cet indice reste figé sous cette forme et ne peut être re-demandé ou converti dans l'autre format (stocké dans `hints_revealed`).
5. **Comptabilisation :**
   L'indice compte comme **+1 coup** dans le total d'essais du joueur (`tries_count += 1`).

---

## 6. Simulateur de Faux Joueurs Réalistes par IA (6h30)

1. **Déclencheur Temporel :** À 6h30, le démon vérifie `SELECT COUNT(*) FROM solo_player_games WHERE puzzle_date = CURRENT_DATE AND status = 'won' AND is_bot = FALSE;`.
2. **Pool Fixe de 20 Habitués & Rotation :**
   - Le système dispose d'une table/seed de **20 profils fixes réservés** (`is_bot = TRUE`) dans `players`.
   - Leurs pseudos `[Nom][Adjectif]` sont réservés et exclus du générateur de pseudos invité M14.
   - À 6h30, si zéro gagnant, un tirage sans remise sélectionne **entre 7 et 10 joueurs parmi ces 20 habitués** (`random.sample(pool_20, k=random.randint(7, 10))`).
3. **Calibration des Résultats par Difficulté :**
   - **Taux de Victoires / Abandons asservi à la difficulté du jour :**
     - 🟢 **Facile :** 95 % de victoires / 5 % d'échecs
     - 🟡 **Normal :** 75 % de victoires / 25 % d'échecs
     - 🔴 **Difficile :** 25 % de victoires / 75 % d'échecs
     - 🟣 **Extrême :** 5 % de victoires / 95 % d'échecs
4. **Trajectoire Sémantique Simulée par Prompt Gemini :**
   - Prompt dédié (`src/ai/prompts.py`) demandant à Gemini d'élaborer une liste de mots représentant le cheminement mental d'un joueur humain :
     - **Pour les victoires (45 à 120 coups) :** mots de démarrage génériques, exploration d'une branche sémantique avec stagnation, déclic intermédiaire menant au champ lexical chaud, approche progressive finale jusqu'au mot victorieux.
     - **Pour les échecs / abandons (30 à 70 coups) :** départ exploratoire, dérive vers un contre-sens ou un champ lexical trompeur, stagnation dans le froid/tiède (< 15°C), puis abandon sans avoir trouvé.
   - Les scores et rangs vectoriels réels de ces mots sont ensuite calculés via `VocabStore` pour garantir une parfaite cohérence mathématique sur la plateforme.
5. **Drapeau de Contrôle & Traçabilité :** Marqué `is_bot = TRUE` en base. Le tableau de bord public affiche le pseudo normalement (pour les gagnants), tandis que la vue admin `/panier-9x` permet d'identifier et de filtrer l'ensemble de ces entrées.
6. **Appel Unique Groupé (Batch JSON) vers Gemini :**
   - Un unique appel REST vers l'API Gemini est déclenché avec un schéma de réponse JSON structuré contenant l'ensemble des 7 à 10 joueurs et leurs listes de mots.
   - Les calculs des scores, températures et rangs millièmes sont réalisés localement par NumPy en mémoire via `VocabStore`.
7. **Déclenchement Forcé & Verrou d'Idempotence (Lock) :**
   - Le système empêche strictement toute exécution multiple par jour grâce au verrou `solo_daily_puzzles.bots_simulated = TRUE`.
   - Si une simulation est déclenchée alors que `bots_simulated = TRUE`, le serveur renvoie immédiatement `{"status": "already_simulated", "message": "Les faux joueurs ont déjà été simulés pour cette journée."}` sans nouvel appel IA ni modification de BDD.
   - **Commande manuelle & Option Force :**
     - CLI : `cemantix --simulate-solo-bots [--force]`
     - Endpoint admin : `POST /api/snap-9x/solo/simulate-bots` (avec option `{force: true}` permettant de purger les bots du jour et de relancer si nécessaire).

---

## 7. Refonte de l'Interface Utilisateur (`/play/`)

```text
+-------------------------------------------------------------------------+
  [Header Universel : Marque, Badge Joueur, Thème, Anti-Spoiler]
+-------------------------------------------------------------------------+
  [Barre de statut : Date du Jour | Difficulté : 🟡 Normal | Essais : 14]
  [Spotlight du Dernier Coup : MOT | 🧊 Glacé 12.4°C | [====      ] 245‰]
  [Champ de Saisie : [  entrez un mot...  ] [Tester] [💡 Indice (2/3)]]
+------------------------------------+------------------------------------+
  🏆 TOUS VOS MOTS (Classés du + chaud)   🥇 CLASSEMENT DU JOUR
-------------------------------------+-------------------------------------
  1. VOILIER   38.4°C  [========] 780‰   1. 🥇 CastorCosmique   48 coups
  2. BATEAU    29.1°C  [======  ] 512‰   2. 🥈 PangolinFurtif   62 coups
  3. MAISON    11.2°C  [==      ]  --    3. 🥉 LynxAudacieux    71 coups
  4. OCÉAN      8.5°C  [=       ]  --    4.    RenardVif        89 coups
  5. TABLE     -2.1°C  [        ]  --    5.    AigleSerein     104 coups
+------------------------------------+------------------------------------+
```

---

## 8. Plan d'Exécution & Découpage des Chantiers

1. **SOLO-01 :** Schéma relationnel idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`).
2. **SOLO-02 :** Module DAO d'accès aux données (`src/db/solo.py`, `src/db/__init__.py`).
3. **SOLO-03 :** Moteur de tirage aléatoire pondéré (15/75/9/1) & pool « extrême » (`src/game/manager.py`, `src/services/solo_daily.py`).
4. **SOLO-04 :** Démon quotidien (renouvellement à minuit, génération IA Gemini & purge roulante).
5. **SOLO-05 :** Simulateur IA de faux joueurs sémantiques à 6h30 (`src/ai/trajectory_sim.py`, flag `is_bot`).
6. **SOLO-06 :** Refonte session de jeu, modale d'indice verrouillée & API REST (`src/game/solo.py`, `src/api/routes/solo.py`).
7. **SOLO-07 :** Refonte frontend (`volumes/web/play/index.html`, `volumes/web/js/game.js`, classement immédiat, tous les mots ordonnés avec barres).
8. **SOLO-08 :** Tests unitaires automatisés sous Docker (`tests/test_solo_daily.py`), audit `check_docs.py` et documentation.
