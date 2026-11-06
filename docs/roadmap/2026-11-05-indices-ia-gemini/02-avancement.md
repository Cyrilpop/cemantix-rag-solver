# 📊 Avancement — Génération & Persistance d'Indices IA par Google Gemini

> **Évolution :** [2026-11 · Génération & Persistance d'Indices IA par Google Gemini](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m12-gemini-ai-hints` (base `origin/main`)  
> **Dernière mise à jour :** 06/11/2026  

---

## 0. Règles de Tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`AI-01` à `AI-06`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.**
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

Répartition par criticité : 🔴 `AI-01` (Schéma BDD & CRUD), `AI-02` (Ingénierie des Prompts), `AI-03` (Client Gemini & Sélecteur de Modèle) · 🟠 `AI-04` (Service Métier & Daemon), `AI-05` (Interface CLI) · 🟡 `AI-06` (Tests & Non-Régression).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **AI-01** | 🔴 | Schéma BDD & Fonctions CRUD (`database/init.sql`, `src/db/connection.py`, `src/db/daily.py`) | `⬜ À faire` | Cadrage établi. Table `daily_puzzle_ai_hints` à déclarer sous PostgreSQL et SQLite avec fonctions CRUD `save_daily_ai_hints` et `get_daily_ai_hints`. |
| **AI-02** | 🔴 | Ingénierie des Prompts Cémantix (`src/ai/prompts.py`) | `⬜ À faire` | Spécification définie : 3 indices gradués (éloigné, intermédiaire, proche) avec mot et phrase, schéma JSON strict et contrainte anti-divulgation. |
| **AI-03** | 🔴 | Client Gemini & Sélecteur de Modèle (`src/ai/gemini_client.py`, `src/ai/model_selector.py`) | `⬜ À faire` | Spécification définie : intégration HTTP REST avec `requests`, clé `GEMINI_API_KEY`, modèle `gemini-3.8-flash` et gestion propre des erreurs. |
| **AI-04** | 🟠 | Service Métier & Orchestration Démon (`src/services/ai_hints.py`, `src/services/daemon.py`) | `⬜ À faire` | Branchement prévu dans le flux de minuit du démon nocturne et fonction de rattrapage des puzzles passés. |
| **AI-05** | 🟠 | Interface CLI Dédiée (`cemantix_rag.py`) | `⬜ À faire` | Options CLI `--generate-ai-hints`, `--date` et `--force` spécifiées. |
| **AI-06** | 🟡 | Suite de Tests & Contrôles Qualité (`tests/test_ai_hints.py`) | `⬜ À faire` | Mocks HTTP, tests SQL SQLite et validation globale sous conteneur Docker Python 3.12 prévus. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 06/11/2026 | — | Ouverture de l'évolution M12, création de la branche `feature/m12-gemini-ai-hints` et rédaction de la référence de conception. |

