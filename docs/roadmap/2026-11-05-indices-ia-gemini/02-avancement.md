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
| ✅ Fait | **6** | 3 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **6** | **3** |

Répartition par criticité : 🔴 `AI-01` (Schéma BDD & CRUD), `AI-02` (Ingénierie des Prompts), `AI-03` (Client Gemini & Sélecteur de Modèle) · 🟠 `AI-04` (Service Métier & Daemon), `AI-05` (Interface CLI) · 🟡 `AI-06` (Tests & Non-Régression).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **AI-01** | 🔴 | Schéma BDD & Fonctions CRUD (`database/init.sql`, `src/db/connection.py`, `src/db/daily.py`) | `✅ Fait` | Table `daily_puzzle_ai_hints` déclarée sous PostgreSQL et SQLite avec index et contrainte UNIQUE. Fonctions CRUD `save_daily_ai_hints` et `get_daily_ai_hints` implémentées et exportées. Validé par `tests/test_ai_hints.py` (`TestSQLPersistence`). |
| **AI-02** | 🔴 | Ingénierie des Prompts Cémantix (`src/ai/prompts.py`) | `✅ Fait` | Prompts calibrés (`SYSTEM_PROMPT`, `build_user_prompt`), format dual mot + phrase validé. Parseur avec filtre Leak-Guard (`check_leak_guard`) rejetant toute fuite directe, pluriel ou radical. Validé par `tests/test_ai_hints.py` (`TestPromptsAndLeakGuard`). |
| **AI-03** | 🔴 | Client Gemini & Sélecteur de Modèle (`src/ai/gemini_client.py`, `src/ai/model_selector.py`) | `✅ Fait` | Client HTTPS REST `GeminiClient` via `requests`, modèle `gemini-3.8-flash`, température 0.3, timeout 10s et gestion résiliente des erreurs HTTP/réseau. Validé par `tests/test_ai_hints.py` (`TestGeminiClient`). |
| **AI-04** | 🟠 | Service Métier & Orchestration Démon (`src/services/ai_hints.py`, `src/services/daemon.py`) | `✅ Fait` | Service `generate_and_store_ai_hints` idempotent, fonction `backfill_ai_hints`, et branchement dans le démon nocturne `daemon.py`. Validé par `tests/test_ai_hints.py` (`TestOrchestrationService`). |
| **AI-05** | 🟠 | Interface CLI Dédiée (`cemantix_rag.py`) | `✅ Fait` | Commande CLI `--generate-ai-hints` avec options `--date` et `--force`, affichage formaté des 3 niveaux d'indices dans la console. Validé via `tests/test_ai_hints.py`. |
| **AI-06** | 🟡 | Suite de Tests & Contrôles Qualité (`tests/test_ai_hints.py`) | `✅ Fait` | Suite de 23 tests unitaires créée dans `tests/test_ai_hints.py` (0 échec). Non-régression complète validée sur l'ensemble de la suite (412 tests OK sous conteneur Docker Python 3.12). |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 06/11/2026 | — | Ouverture de l'évolution M12, création de la branche `feature/m12-gemini-ai-hints` et rédaction de la référence de conception. |
| 06/11/2026 | AI-01 | Schéma relationnel `daily_puzzle_ai_hints` créé sous PostgreSQL et SQLite ; fonctions CRUD validées (`TestSQLPersistence`). |
| 06/11/2026 | AI-02 | Prompts calibrés, format dual mot + phrase et filtre Leak-Guard anti-triche validés (`TestPromptsAndLeakGuard`). |
| 06/11/2026 | AI-03 | Client HTTPS REST `GeminiClient` et sélecteur de modèle implémentés avec mocks unitaires (`TestGeminiClient`). |
| 06/11/2026 | AI-04 | Intégration démon nocturne et fonctions de génération / backfill idempotentes validées (`TestOrchestrationService`). |
| 06/11/2026 | AI-05 | Interface CLI `--generate-ai-hints` avec options `--date` et `--force` intégrée et validée. |
| 06/11/2026 | AI-06 | Exécution verte des 23 tests unitaires M12 et validation globale des 412 tests sous conteneur Docker Python 3.12. |

