# 📊 Avancement — Authentification Joueurs sans Email : Profils Invités, Pseudos Personnalisables & Phrase de Secours

> **Évolution :** [2026-11 · Authentification Joueurs sans Email](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m14-authentification-joueurs` (base `main`)  
> **Dernière mise à jour :** 07/11/2026  

---

## 0. Règles de Tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`AUTH-01` à `AUTH-06`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte sous Docker.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **6** | 3 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **6** | **3** |

Répartition par criticité : 🔴 `AUTH-01` (Schéma Relationnel Idempotent PostgreSQL & SQLite), `AUTH-02` (Module de Données & Couche d'Accès DAO), `AUTH-03` (Service Métier d'Authentification & Dictionnaires) · 🟠 `AUTH-04` (Endpoints API REST HTTP), `AUTH-05` (Interface Utilisateur & Intégration Layout) · 🟡 `AUTH-06` (Tests Unitaires, Non-Régression & Documentation).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **AUTH-01** | 🔴 | Schéma Relationnel Idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`) | `✅ Fait` | Tables `players` et `player_dictionary` créées avec `CREATE TABLE IF NOT EXISTS`, index idempotents, DDL miroir SQLite et fonction d'auto-initialisation au démarrage Python avec seeding automatique. Testé et validé dans `tests/test_player_auth.py`. |
| **AUTH-02** | 🔴 | Module de Données & Couche d'Accès DAO (`src/db/players.py`) | `✅ Fait` | Implémentation complète et thread-safe des opérations CRUD pour `players` et `player_dictionary`, exposées dans `src/db/__init__.py`. Validé par `tests/test_player_auth.py`. |
| **AUTH-03** | 🔴 | Service Métier d'Authentification & Dictionnaires (`src/services/player_auth.py`) | `✅ Fait` | Générateur de pseudos respectant strictement l'ordre `[Nom][Adjectif]` (8-24 car), générateur de phrases secrètes de 4 mots, hachage PBKDF2-HMAC-SHA256 (200 000 itérations avec sel 16 octets) et validation de pseudo. Validé par `tests/test_player_auth.py`. |
| **AUTH-04** | 🟠 | Endpoints API REST HTTP (`src/services/server.py` ou routeur dédié) | `✅ Fait` | Routes `/api/player/guest`, `/api/player/rename`, `/api/player/claim`, `/api/player/login`, `/api/player/reset-password`, `/api/player/delete-account` avec en-tête `Cache-Control: no-store, private` et endpoints admin `/api/snap-9x/dictionary`. Validé sous Docker. |
| **AUTH-05** | 🟠 | Interface Utilisateur & Intégration Layout (`src/services/layout_sync.py`, `volumes/web/js/auth.js`) | `✅ Fait` | Badge joueur dans le Header universel, bannière première visite toast discrète, modale de profil native `<dialog>` (3 vues) et section vocabulaire dans la console `/panier-9x`. Bundles CSS recompilés et validés par `tools/build_css_bundles.py --check`. |
| **AUTH-06** | 🟡 | FAQ, CGU, Confidentialité & Tests Unitaires (`volumes/web/index.html`, `tests/test_player_auth.py`, docs) | `✅ Fait` | FAQ (#confidentialite et #conditions-utilisation) et JSON-LD enrichis (exemption CNIL, hachage, 0 email, renommage unique, phrase de secours). Suite de 435 tests 100 % passants sous Docker. `tools/check_docs.py` et `tools/check_seo.py` verts. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 07/11/2026 | — | Création de la branche `feature/m14-authentification-joueurs`, rédaction du jalon `docs/milestones/M14_AUTHENTIFICATION_JOUEURS.md`, du plan d'évolution `01-plan.md` et initialisation du suivi `02-avancement.md`. |
| 07/11/2026 | AUTH-01 | Ajout des tables idempotentes `players` et `player_dictionary` dans `database/init.sql`, `PG_SCHEMA` et `SQLITE_SCHEMA` dans `src/db/connection.py`. |
| 07/11/2026 | AUTH-02 | Création du DAO `src/db/players.py` et intégration dans `src/db/__init__.py` avec gestion thread-safe des profils et vocabulaires. |
| 07/11/2026 | AUTH-03 | Implémentation du service métier `src/services/player_auth.py` : générateur `[Nom][Adjectif]`, 4 mots de secours, hachage PBKDF2 et validation. |
| 07/11/2026 | AUTH-04 | Implémentation des contrôleurs REST dans `src/api/routes/player.py`, administration dans `src/api/routes/admin.py` et dispatching dans `src/api/server.py` avec `Cache-Control: no-store, private`. |
| 07/11/2026 | AUTH-05 | Badge joueur dans `src/services/layout_sync.py`, synchronisation des vues, création de `volumes/web/js/auth.js`, `volumes/web/css/auth.css`, compilation des bundles et panneau d'administration du dictionnaire dans `/panier-9x`. |
| 07/11/2026 | AUTH-06 | Mise à jour juridique RGPD/CNIL dans `volumes/web/index.html` (FAQ et FAQPage), création de `tests/test_player_auth.py` (8 suites de tests). Validation des 435 tests sous Docker, `check_docs.py`, `check_seo.py` et `build_css_bundles.py --check`. |

