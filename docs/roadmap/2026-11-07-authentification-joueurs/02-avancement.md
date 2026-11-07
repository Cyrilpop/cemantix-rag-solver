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
| ✅ Fait | **0** | 0 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **6** | 3 |
| **Total suivis** | **6** | **3** |

Répartition par criticité : 🔴 `AUTH-01` (Schéma Relationnel Idempotent PostgreSQL & SQLite), `AUTH-02` (Module de Données & Couche d'Accès DAO), `AUTH-03` (Service Métier d'Authentification & Dictionnaires) · 🟠 `AUTH-04` (Endpoints API REST HTTP), `AUTH-05` (Interface Utilisateur & Intégration Layout) · 🟡 `AUTH-06` (Tests Unitaires, Non-Régression & Documentation).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **AUTH-01** | 🔴 | Schéma Relationnel Idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`) | `⬜ À faire` | Création de la table `players` avec `CREATE TABLE IF NOT EXISTS`, index idempotents, DDL miroir SQLite et fonction d'auto-initialisation au démarrage Python. |
| **AUTH-02** | 🔴 | Module de Données & Couche d'Accès DAO (`src/db/players.py`) | `⬜ À faire` | Implémentation des opérations CRUD thread-safe pour les profils, sessions et statuts de compte. |
| **AUTH-03** | 🔴 | Service Métier d'Authentification & Dictionnaires (`src/services/player_auth.py`) | `⬜ À faire` | Générateur de pseudos loufoques en français, générateur de phrase de secours de 4 mots, hachage sécurisé PBKDF2/argon2 et validation des pseudos. |
| **AUTH-04** | 🟠 | Endpoints API REST HTTP (`src/services/server.py` ou routeur dédié) | `⬜ À faire` | Routes `/api/player/guest`, `/api/player/rename`, `/api/player/claim`, `/api/player/login` et `/api/player/reset-password` avec codes HTTP et payloads JSON normalisés. |
| **AUTH-05** | 🟠 | Interface Utilisateur & Intégration Layout (`src/services/layout_sync.py`, `volumes/web/js/auth.js`) | `⬜ À faire` | Intégration du badge joueur dans le header commun, modale de profil (renommage unique, mot de passe, phrase de 4 mots, reconnexion) et persistance `localStorage`. |
| **AUTH-06** | 🟡 | FAQ, CGU, Confidentialité & Tests Unitaires (`volumes/web/index.html`, `tests/test_player_auth.py`, docs) | `⬜ À faire` | Mise à jour des sections FAQ (#confidentialite et #conditions-utilisation) et JSON-LD, suite complète de tests unitaires sous Docker couvrant le cycle joueur, tests d'idempotence, documentation `README.md` et `CHANGELOG.md`. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 07/11/2026 | — | Création de la branche `feature/m14-authentification-joueurs`, rédaction du jalon `docs/milestones/M14_AUTHENTIFICATION_JOUEURS.md`, du plan d'évolution `01-plan.md` et initialisation du suivi `02-avancement.md`. |

