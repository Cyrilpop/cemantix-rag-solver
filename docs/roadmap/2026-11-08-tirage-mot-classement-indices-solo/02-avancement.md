# 📊 Avancement — Mot du Jour Solo Aléatoire Pondéré, Classement Communautaire & Indices IA Roulants

> **Évolution :** [2026-11 · Mot du Jour Solo Aléatoire & Classement](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m15-mot-du-jour-solo` (base `main`)  
> **Dernière mise à jour :** 08/11/2026  

---

## 0. Règles de Tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`SOLO-01` à `SOLO-08`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte sous Docker.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **8** | 4 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **8** | **4** |

Répartition par criticité : 🔴 `SOLO-01` (Schéma Relationnel Idempotent PostgreSQL & SQLite), `SOLO-03` (Moteur de Tirage Aléatoire Pondéré & Pool Extrême), `SOLO-05` (Simulateur IA de Faux Joueurs Réalistes à 6h30), `SOLO-06` (Refonte Moteur Jeu Solo & Endpoints API REST) · 🟠 `SOLO-02` (Estimation Volumétrie & Dimensionnement BDD), `SOLO-04` (Démon Planificateur Minuit & Indices IA Gemini Roulants), `SOLO-07` (Refonte Interface Utilisateur `/play/`) · 🟡 `SOLO-08` (Tests Unitaires & Validation sous Docker).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **SOLO-01** | 🔴 | Schéma Relationnel Idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`) | ✅ Fait | Tables idempotentes `solo_daily_puzzles` (avec lock `bots_simulated`), `solo_daily_ai_hints`, `solo_player_games` (avec `is_bot` et `hints_revealed`) et `solo_player_guesses`. DDL miroir SQLite. Validé par tests relationnels. |
| **SOLO-02** | 🟠 | Estimation de la Volumétrie & Dimensionnement BDD (`docs/milestones/M15_TIRAGE_MOT_CLASSEMENT_INDICES_SOLO.md`) | ✅ Fait | Modélisation (~234 octets/coup), enregistrement exclusif des parties gagnées ou abandonnées (~32 Mo/mois pour 60 parties finies/j) et intégration de la simulation à 6h30. |
| **SOLO-03** | 🔴 | Moteur de Tirage Aléatoire Pondéré & Pool Extrême (`src/game/manager.py`, `src/services/solo_daily.py`) | ✅ Fait | Distribution pondérée (15% facile, 75% normal, 9% difficile, 1% extrême). Extraction des 1% les moins utilisés dans le vocabulaire frWac (347 mots). Mode illimité préservé. Validé par `TestSoloDailyWordDraw`. |
| **SOLO-04** | 🟠 | Démon Planificateur (Minuit) & Indices IA Gemini Roulants (`src/services/daemon.py`, `src/ai/`) | ✅ Fait | Automatisation à 00h00 : tirage du mot, appel Gemini pour 3 indices mot/phrase, précalcul des scores et purge automatique des indices de la veille (rétention 24h). |
| **SOLO-05** | 🔴 | Simulateur IA de Faux Joueurs Réalistes & Pool des 20 Habitués à 6h30 (`src/ai/trajectory_sim.py`, `src/ai/prompts.py`) | ✅ Fait | Pool fixe de 20 habitués réservés amorcés en base, rotation 7 à 10 joueurs, 1 seul appel IA groupé (batch JSON), repli algorithmique, verrou d'idempotence (`bots_simulated`) et option `--force` CLI et admin. Validé par `TestSoloBotSimulation`. |
| **SOLO-06** | 🔴 | Refonte du Moteur de Jeu Solo & Endpoints API REST (`src/game/solo.py`, `src/api/routes/solo.py`) | ✅ Fait | Règle 1 indice = 1 coup, modale mot/phrase par indice demandé avec immuabilité par palier, endpoints unifiés `/api/game/*` et `/api/solo/*` (`daily`, `guess`, `leaderboard`, `trajectory/<id>`, `hint`, `giveup`, `finish`). Validé par `TestSoloAntiSpoilerAndLeaderboard` et `TestSoloGameAPIRoutes`. |
| **SOLO-07** | 🟠 | Refonte de l'Interface Utilisateur `/play/` (`volumes/web/play/index.html`, `volumes/web/js/game.js`) | ✅ Fait | Tuile « Tous vos mots » classés par chaleur avec barres relatives individuelles ; tuile « Classement des joueurs qui ont trouvé » visible dès le début (trajectoires verrouillées 🔒 tant que non fini) ; modale d'indice à chaque palier. Audit CSS et SEO passants. |
| **SOLO-08** | 🟡 | Suite de Tests Unitaires & Validation sous Docker (`tests/test_solo_daily.py`) | ✅ Fait | Couverture complète : 16/16 tests passants dans `test_solo_daily.py`, 446/446 tests passants sur la suite complète de non-régression (0 échec, 0 erreur). Validé sous Docker. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 08/11/2026 | — | Création de la branche `feature/m15-mot-du-jour-solo`, rédaction du jalon `docs/milestones/M15_TIRAGE_MOT_CLASSEMENT_INDICES_SOLO.md`, du plan `01-plan.md` et initialisation du suivi `02-avancement.md`. |
| 08/11/2026 | SOLO-02 | Précision des règles métier suite aux clarifications : persistance exclusive des parties abouties (gagnées/abandonnées), intégration des faux joueurs (6h30) et simulation sémantique par IA. |
| 08/11/2026 | SOLO-07 | Spécification stricte de l'étanchéité anti-spoiler : classement visible dès l'ouverture, mais trajectoire détaillée des autres joueurs inaccessible tant que le joueur n'a ni gagné ni abandonné. |
| 08/11/2026 | SOLO-06 | Ajustement de la règle d'indice : le choix mot/phrase se fait à chaque indice demandé (#1, #2, #3), avec immuabilité stricte par palier (impossible de cumuler mot et phrase pour le même indice). |
| 08/11/2026 | SOLO-05 | Intégration du mix réaliste victoires (~70 %) et échecs/abandons (~30 %) dans la simulation des faux joueurs de 6h30, avec trajectoires d'abandon sur fausses pistes sémantiques. |
| 08/11/2026 | SOLO-05 | Calibration formelle des taux de succès des faux joueurs asservis à la difficulté du jour (95% facile, 75% normal, 25% difficile, 5% extrême). |
| 08/11/2026 | SOLO-05 | Définition d'un contingent fixe de 20 profils fictifs (« les habitués ») avec pseudos réservés, et rotation quotidienne aléatoire (7 à 10 jouant chaque jour). |
| 08/11/2026 | SOLO-05 | Optimisation en 1 appel IA groupé (batch JSON), ajout du verrou d'idempotence `solo_daily_puzzles.bots_simulated` et option de forçage manuel CLI / admin. |
| 08/11/2026 | SOLO-01 | Implémentation du schéma relationnel idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`). |
| 08/11/2026 | SOLO-03 | Implémentation du tirage aléatoire pondéré (15/75/9/1) et extraction du pool extrême des 1% moins fréquents. |
| 08/11/2026 | SOLO-04 | Implémentation de la routine minuit (tirage + indices IA + purge 24h) dans le démon planificateur. |
| 08/11/2026 | SOLO-05 | Implémentation du générateur sémantique batch Gemini et repli local avec simulation des habitués à 6h30 et verrou d'idempotence. |
| 08/11/2026 | SOLO-06 | Implémentation des DAO et endpoints REST `/api/game/*` et `/api/solo/*` avec anti-spoiler et choix de format d'indice immuable. |
| 08/11/2026 | SOLO-07 | Refonte de l'interface `/play/` : Tuile « Tous vos mots », « Classement des joueurs qui ont trouvé », modale d'indice et modale de trajectoire replay. |
| 08/11/2026 | SOLO-08 | Validation sous Docker : 16/16 tests unitaires passants (`tests/test_solo_daily.py`) et 446/446 tests globaux au vert sans régression. Clôture de l'ensemble des findings SOLO-01 à SOLO-08. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 08/11/2026 | — | Création de la branche `feature/m15-mot-du-jour-solo`, rédaction du jalon `docs/milestones/M15_TIRAGE_MOT_CLASSEMENT_INDICES_SOLO.md`, du plan `01-plan.md` et initialisation du suivi `02-avancement.md`. |
| 08/11/2026 | SOLO-02 | Précision des règles métier suite aux clarifications : persistance exclusive des parties abouties (gagnées/abandonnées), intégration des faux joueurs (6h30) et simulation sémantique par IA. |
| 08/11/2026 | SOLO-07 | Spécification stricte de l'étanchéité anti-spoiler : classement visible dès l'ouverture, mais trajectoire détaillée des autres joueurs inaccessible tant que le joueur n'a ni gagné ni abandonné. |
| 08/11/2026 | SOLO-06 | Ajustement de la règle d'indice : le choix mot/phrase se fait à chaque indice demandé (#1, #2, #3), avec immuabilité stricte par palier (impossible de cumuler mot et phrase pour le même indice). |
| 08/11/2026 | SOLO-05 | Intégration du mix réaliste victoires (~70 %) et échecs/abandons (~30 %) dans la simulation des faux joueurs de 6h30, avec trajectoires d'abandon sur fausses pistes sémantiques. |
| 08/11/2026 | SOLO-05 | Calibration formelle des taux de succès des faux joueurs asservis à la difficulté du jour (95% facile, 75% normal, 25% difficile, 5% extrême). |
| 08/11/2026 | SOLO-05 | Définition d'un contingent fixe de 20 profils fictifs (« les habitués ») avec pseudos réservés, et rotation quotidienne aléatoire (7 à 10 jouant chaque jour). |
| 08/11/2026 | SOLO-05 | Optimisation en 1 appel IA groupé (batch JSON), ajout du verrou d'idempotence `solo_daily_puzzles.bots_simulated` et option de forçage manuel CLI / admin. |
