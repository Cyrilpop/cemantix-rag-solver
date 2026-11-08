# Plan d'Évolution — Mot du Jour Solo Aléatoire Pondéré, Classement Communautaire & Indices IA Roulants

**Évolution :** `2026-11-08-tirage-mot-classement-indices-solo`  
**Jalon associé :** `docs/milestones/M15_TIRAGE_MOT_CLASSEMENT_INDICES_SOLO.md`  
**Branche cible :** `feature/m15-mot-du-jour-solo` (base `main`)  
**Statut du plan :** Prêt pour cadrage et exécution  

---

## 1. Contexte & Diagnostic

Actuellement, le jeu interactif Solo accessible sur `/play/` s'appuie sur le mot quotidien résolu par le bot sur le site officiel de Cémantix. Les sessions de jeu des utilisateurs ne sont pas persistées en base relationnelle, les coups ne sont pas historisés, et l'interface comporte des limitations ergonomiques :
1. **Dépendance au mot officiel :** Le mot du jour dépend du solveur officiel et des aléas réseau de récupération externe.
2. **Tuile « Vos Meilleurs Mots » limitée au Top 10 :** Les joueurs perdent de vue l'ensemble de leurs tentatives antérieures dès qu'ils dépassent 10 propositions, et la jauge de température colorée n'est présente que dans le bandeau du dernier coup joué.
3. **Tuile « Historique de vos Coups » sans intérêt compétitif :** Elle affiche une simple liste chronologique locale qui disparaît au rechargement de page.
4. **Absence de classement communautaire pour le mode Solo :** Les joueurs ne peuvent pas comparer leur efficacité (nombre de coups pour trouver le mot secret).
5. **Gestion manuelle des indices :** Les indices du mode solo sont calculés à la volée par KNN local sans enrichissement sémantique IA (Gemini), et sans mécanisme de rétention propre.

L'objectif de cette évolution est de concevoir un système pérenne, scalable et ludique pour le mode Solo de Cémantix Solver.

---

## 2. Spécification Détaillée des Actions (Findings SOLO-01 à SOLO-08)

### SOLO-01 — Schéma Relationnel Idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`)
- **Cible :** `database/init.sql`, `src/db/connection.py`.
- **Besoin :**
  - Table `solo_daily_puzzles` : enregistre le mot du jour Solo tiré au sort, sa date (clé unique), son niveau de difficulté, le nombre de joueurs ayant tenté, réussi et échoué, ainsi que le verrou anti-rejeu `bots_simulated` (BOOLEAN) et son horodatage `bots_simulated_at`.
  - Table `solo_daily_ai_hints` : stocke les 3 indices IA Gemini (mot + phrase + scores sémantiques). Rétention roulante stricte d'un jour (`ON DELETE CASCADE`).
  - Table `solo_player_games` : enregistre la session quotidienne de chaque joueur identifié (`player_id` lié à `players.id` de M14), son statut (`won`, `given_up`), ses indices révélés (`hints_revealed`), son nombre d'essais, son nombre d'indices consommés (max 3), son temps de résolution, et le drapeau d'audit `is_bot`.
  - Table `solo_player_guesses` : historise chaque coup individuel pour les parties terminées (`game_id`, `guess_order`, `word`, `score`, `permille`, `weather`, `is_hint`, `created_at`).
  - DDL miroir SQLite dans `PG_SCHEMA` et `SQLITE_SCHEMA` pour la compatibilité totale des tests unitaires sans dépendance réseau.

### SOLO-02 — Estimation de la Volumétrie & Dimensionnement BDD
- **Cible :** `docs/milestones/M15_TIRAGE_MOT_CLASSEMENT_INDICES_SOLO.md`, architecture de stockage.
- **Besoin :**
  - Modélisation du poids unitaire par tuple PostgreSQL :
    - `solo_player_guesses` : ~104 octets de données + ~130 octets d'index B-Tree = **~234 octets par coup**.
    - `solo_player_games` : **~265 octets par session quotidienne**.
  - Règle d'or : conservation de la trajectoire **uniquement pour les parties gagnées ou abandonnées** (zéro pollution par les sessions inachevées).
  - Projections de croissance pour une moyenne de 65 coups par partie finie :
    - 60 parties finies/j : ~1,06 Mo/j $\rightarrow$ **~32 Mo / mois** (~387 Mo / an).
    - 600 parties finies/j : ~9,28 Mo/j $\rightarrow$ **~278 Mo / mois** (~3,38 Go / an).
    - 6 000 parties finies/j : ~91,4 Mo/j $\rightarrow$ **~2,74 Go / mois** (~33,3 Go / an).

### SOLO-03 — Moteur de Tirage Aléatoire Pondéré & Catégorie « Extrême »
- **Cible :** `src/game/manager.py`, `src/services/solo_daily.py`.
- **Besoin :**
  - Calibration de la sélection aléatoire quotidienne :
    - **Facile : 15 %** (top 4 000 mots les plus fréquents de `frWac`).
    - **Normal : 75 %** (vocabulaire de rang 4 000 à 16 000).
    - **Difficile : 9 %** (vocabulaire au-delà de 16 000).
    - **Extrême : 1 %** (nouveau sous-ensemble réservé aux 1 % des mots les moins fréquents du vocabulaire valide).
  - Unicité absolue du mot : le tirage est effectué une seule fois par jour pour l'ensemble des joueurs.
  - Maintien du mode **Illimité** en mémoire locale sans écriture en base.

### SOLO-04 — Démon Planificateur (Minuit) & Indices IA Gemini Roulants
- **Cible :** `src/services/daemon.py`, `src/services/solo_daily.py`, `src/ai/`.
- **Besoin :**
  - À `00h00:00`, exécution du tirage du nouveau mot du jour Solo.
  - Appel à `GeminiClient.generate_hints(secret_word)` pour générer les 3 indices gradués (mot | phrase) et précalcul de leur score sémantique vis-à-vis du secret.
  - Insertion atomique dans `solo_daily_ai_hints`.
  - Purge automatique des indices des jours passés (`DELETE FROM solo_daily_ai_hints WHERE puzzle_date < CURRENT_DATE`).

### SOLO-05 — Simulateur IA de Faux Joueurs Réalistes & Pool des 20 Habitués à 6h30 (`src/ai/trajectory_sim.py`)
- **Cible :** `src/services/daemon.py`, `src/ai/trajectory_sim.py`, `src/ai/prompts.py`, `src/db/players.py`.
- **Besoin :**
  - Constitution d'un **pool fixe de 20 profils fictifs réguliers (« les habitués »)** réservés en base (`is_bot = TRUE`), dont les pseudonymes `[Nom][Adjectif]` ne peuvent être attribués aux vrais joueurs.
  - Déclenchement à **6h30 du matin** si aucun vrai joueur n'a encore résolu l'énigme du jour : sélection par rotation d'un échantillon de **7 à 10 joueurs parmi ces 20 habitués** (ils ne jouent pas tous les jours).
  - **Taux de succès asservi à la difficulté du jour :**
    - 🟢 Facile : 95 % victoires / 5 % abandons
    - 🟡 Normal : 75 % victoires / 25 % abandons
    - 🔴 Difficile : 25 % victoires / 75 % abandons
    - 🟣 Extrême : 5 % victoires / 95 % abandons
  - Génération d'une **trajectoire purement sémantique en 1 seul appel groupé à l'IA Gemini** (batch JSON) retournant l'ensemble des joueurs simulés.
  - **Verrou d'Idempotence & Option Forcée :**
    - Verrou `solo_daily_puzzles.bots_simulated = TRUE` pour bloquer toute exécution multiple par jour.
    - CLI `cemantix --simulate-solo-bots [--force]` et route d'administration `/api/snap-9x/solo/simulate-bots` pour déclencher manuellement la simulation.
  - Enregistrement en base avec drapeau `is_bot = TRUE` (accessible en lecture admin exclusive).
  - Incrémentation des compteurs `players_attempted`, `players_succeeded` et `players_failed` de `solo_daily_puzzles`.

### SOLO-06 — Refonte du Moteur de Jeu Solo & Endpoints API REST
- **Cible :** `src/game/solo.py`, `src/api/routes/solo.py`, `src/api/server.py`.
- **Besoin :**
  - Décompte : **1 indice = +1 coup**.
  - Gestion du choix de format à chaque indice demandé (Mot vs Phrase), avec immuabilité stricte par indice révélé.
  - Endpoints REST :
    - `GET /api/solo/daily` : statut du jour, date, difficulté, nombre de participants, quota d'indices restants, historique des indices déjà débloqués (sans fuite du mot secret).
    - `POST /api/solo/guess` : enregistrement du mot testé, calcul cosinus / thermomètre, mise à jour mémoire.
    - `GET /api/solo/leaderboard` : liste des gagnants du jour (vrais et faux joueurs) ordonnée par `tries_count ASC, duration_seconds ASC`. Ne livre aucun détail de trajectoire.
    - `GET /api/solo/trajectory/{game_id}` : renvoie la trajectoire détaillée d'un joueur du classement UNIQUEMENT si le joueur demandeur a lui-même terminé sa partie (`won` ou `given_up`). Renvoyer 403 Forbidden avec message anti-spoiler si la partie est encore en cours.
    - `POST /api/solo/hint` : réclame l'un des 3 indices autorisés, renvoie mot ou phrase selon le format choisi et incrémente `hints_used` et `tries_count`.
    - `POST /api/solo/giveup` : clôture la partie en échec, met à jour `players_failed`, dévoile le secret et persiste la trajectoire.
    - `POST /api/solo/finish` : persiste la trajectoire complète en base dès victoire du joueur.

### SOLO-07 — Refonte de l'Interface Utilisateur `/play/`
- **Cible :** `volumes/web/play/index.html`, `volumes/web/js/game.js`, `volumes/web/css/modal.css`.
- **Besoin :**
  - **Tuile « Tous vos Mots » :** Affiche tous les mots joués (sans limite de 10), triés du plus chaud au plus froid, chacun avec sa jauge de température colorée.
  - **Tuile « Classement des Joueurs » :** Visible dès le début de la partie pour stimuler le joueur (rang, pseudo joueur M14, nombre de coups).
  - **Verrouillage Anti-Spoiler de la Trajectoire :** Les lignes du classement ne permettent pas d'ouvrir la trajectoire détaillée d'un autre joueur tant que la partie de l'utilisateur n'est pas terminée (`won` ou `given_up`). Dès la partie terminée, un bouton replay/trajectoire devient actif sur chaque joueur du tableau.
  - **Modale de Sélection d'Indice :** À chaque clic sur « Indice », ouverture d'une modale demandant : « Souhaitez-vous cet indice sous forme de MOT ou de PHRASE ? ». Une fois l'indice révélé, il reste figé sous cette forme pour ce palier.
  - Responsive mobile : zéro débordement horizontal, maintien du PageSpeed 100/100.

### SOLO-08 — Suite de Tests Unitaires & Validation sous Docker
- **Cible :** `tests/test_solo_daily.py`, validation Docker.
- **Besoin :**
  - Tests unitaires du tirage pondéré et de l'isolement du pool « extrême ».
  - Tests de la simulation IA de faux joueurs et de la cohérence de leur trajectoire sémantique.
  - Tests du cycle de vie des sessions de jeu, de l'immuabilité par palier d'indice et de l'historisation sélective.
  - Validation de `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check`.

---

## 3. Matrice de Risques & Stratégies d'Atténuation

| Risque identifié | Niveau | Stratégie d'atténuation |
|---|---|---|
| **Saturation disque due aux coups** | Faible | Enregistrement exclusif des parties gagnées ou abandonnées ; estimation formelle (~32 Mo/mois). |
| **Fuite du mot secret dans l'API** | Élevé | Masquage strict du mot secret tant que `status != 'won'` et `status != 'given_up'`. |
| **Triche ou rejeu d'indices** | Moyen | Vérification côté serveur du compteur `hints_used <= 3` et refus de double révélation (mot+phrase) d'un même palier. |
| **Détection des faux joueurs par les utilisateurs** | Moyen | Simulation sémantique fine par IA Gemini (45 à 120 coups) plutôt qu'un solveur froid RAG. |
