# Project Memory — Cémantix RAG Solver

**Dernière mise à jour :** 30 octobre 2026 (Milestone M2.1 — Durcissement Compatibilité Solveur)  
**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Statut du Projet :** Production active / Maintenance & Modernisation incrémentale  

---

## 1. Objectif & Périmètre

Le projet **Cémantix RAG Solver** fournit :
1. Un **solveur sémantique autonome** capable de découvrir le mot secret quotidien du jeu Cémantix via une descente mathématique par régression Ridge sur l'espace vectoriel word2vec `frWac` (500 dimensions) et reranking quadratique, assisté optionnellement d'un LLM local compatible OpenAI ChatCompletions.
2. Une **plateforme de jeu multimodale** :
   - Mode Solo interactif (Web & CLI).
   - Mode Duel croisé Humain vs IA (Web & CLI).
   - Mode Multijoueur 1v1 en temps réel / tour par tour par code de salon (Web).
   - Défi au bot avec file d'attente asynchrone (Web `/defi/`).
   - Tableau de bord quotidien sans spoiler avec indices thermiques progressifs.
3. Un **générateur SEO & API pour agents** :
   - Pages d'archives quotidiennes indexables (`/puzzles/<date>/`) lisibles sans JavaScript.
   - Sitemap XML dynamique, métadonnées Schema.org (FAQ, HowTo, Breadcrumb).
   - API REST sans spoiler (`/api/daily`, `/api/health`).
   - Fiches de découverte agentique ARD (`llms.txt`, `agent-card.json`, `openapi.json`).

---

## 2. Carte Architecturale & Composants Majeurs

L'architecture s'organise en 3 tiers orchestrés par Docker Compose :

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CADDY / NGINX REVERSE PROXY                     │
│  - Sert le volume statique ./volumes/web                               │
│  - Proxifie /api/* vers le conteneur cemantix_web (port 8000)          │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌────────────────────────────────────┐ ┌─────────────────────────────────┐
│     cemantix_web (API HTTP)        │ │   cemantix_worker (Démon 24/7)  │
│ - ThreadingHTTPServer (port 8000)  │ │ - Boucle permanente 24h/24      │
│ - Contrôleurs routes REST          │ │ - Résolution quotidienne 00h00  │
│ - GameManager (sessions mémoire)   │ │ - Traitement file bot_challenges│
└──────────────────┬─────────────────┘ └─────────────────┬───────────────┘
                   │                                     │
                   ▼                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   cemantix_db (PostgreSQL 16 Alpine)                   │
│ - daily_puzzles, multi_rooms, solo_sessions, bot_challenges            │
│ * Repli transparent sur SQLite local si DB_HOST est non configuré      │
└────────────────────────────────────────────────────────────────────────┘
```

### Sous-Packages dans `src/`
- [src/config.py](src/config.py) : Constantes système, styles ANSI, chemins de données, validation d'environnement.
- [src/engine/](src/engine/) : Cœur algorithmique RAG :
  - `vocab.py` : `VocabStore` (gestion du lexique, word2vec, embeddings ChromaDB).
  - `ranking.py` : Fonctions pures Ridge (`estimate_secret`), rerank quadratique et météo (`weather_for_score`).
  - `llm.py` : Intégration HTTP prompt/ChatCompletions du LLM local (`ask_llm`).
  - `duel.py` : Agent bot tour par tour (`RagDuelPlayer`) avec heuristiques adaptatives.
  - `solvers.py` : Orchestration du solveur autonome (`Solver`, `CemantixSolver`) et ré-exports rétrocompatibles.
  - `clients.py` : `CemantixClient` (site officiel) et `MockClient` (simulation déterministe).
- [src/game/](src/game/) : Modèle de domaine et règles métier :
  - `common.py` : Calculs thermiques officiels (icônes météo, pour mille, paliers de score).
  - `solo.py` : Logique de session solo en mémoire.
  - `battle.py` : Logique de session duel contre IA.
  - `multi.py` : Logique de salon 1v1 multijoueur.
  - `manager.py` : `GameManager` unifié coordonnant les sessions et la persistance.
- [src/api/](src/api/) : Passerelle REST :
  - `server.py` : `ThreadingHTTPServer`, gestion CORS et en-têtes de sécurité.
  - `routes/` : Contrôleurs modulaires (`system`, `solo`, `battle`, `multi`, `challenge`, `admin`).
  - `ratelimit.py` : Token bucket en mémoire par IP.
- [src/services/](src/services/) : Services autonomes :
  - `daemon.py` : Boucle planificatrice 00h00 et surveillance de battement (*heartbeat*).
  - `challenges.py` : Traitement de la file des défis lancés au bot.
  - `seo.py` : Orchestrateur de publication SEO, pré-rendu du tableau de bord et ré-exports universels.
  - `seo_templates.py` : Gabarits HTML autonomes, composants Schema.org et tokens de style.
  - `seo_archives.py` : Pages d'archives quotidiennes et index paginé.
  - `seo_hubs.py` : Hubs thématiques « mot du jour » et « méthode & indices » (rendu serveur).
  - `seo_sitemap.py` : Génération conforme du sitemap XML et écriture atomique multi-conteneurs.
  - `seo_agents.py` : Manifestes ARD/A2A et documentation agentique dynamique (`llms.txt`).
  - `web.py` : Synchronisation et export de `data.json`.
- [src/cli/](src/cli/) : Expérience console :
  - `menu.py` : Menu interactif principal ANSI.
  - `modes.py` : Boucles de jeu terminal (solo, duel, battle, benchmark).
  - `ui.py` : Jauges et tableaux console.

---

## 3. Points d'Entrée & Flux d'Exécution

| Flux | Point d'Entrée | Commande / Déclencheur | Description |
|---|---|---|---|
| **Démon 24/7** | `cemantix_rag.py` | `python cemantix_rag.py --daemon --no-api` | Cycle de veille permanente ; résout le mot à 00h00 Paris, exporte `data.json` et publie le SEO. |
| **API Web** | `cemantix_rag.py` | `python cemantix_rag.py --api --api-port 8000` | Lance le serveur HTTP REST desservant l'application front. |
| **Healthcheck** | `cemantix_rag.py` | `python cemantix_rag.py --healthcheck` | Vérifie la fraîcheur de `daemon_heartbeat.json` (< 90s). |
| **Jeu Solo CLI** | `cemantix_rag.py` | `python cemantix_rag.py --play` (ou `--mock`) | Lance la boucle console du jeu solo. |
| **Duel IA CLI** | `cemantix_rag.py` | `python cemantix_rag.py --duel` | Affronte l'IA RAG au tour par tour dans le terminal. |
| **Simulation** | `cemantix_rag.py` | `python cemantix_rag.py --benchmark 10 --mock` | Exécute N parties simulées pour benchmarker l'algorithme. |
| **Publication SEO** | `cemantix_rag.py` | `python cemantix_rag.py --publish-seo` | Régénère les pages HTML d'archives et le sitemap XML. |

---

## 4. Stack Technologique & Dépendances Runtime

### Dépendances Python (`requirements.txt`)
- `numpy==2.0.2` : Calculs vectoriels, inversion Ridge et calculs d'erreurs quadratiques.
- `chromadb==1.5.9` : Base vectorielle locale stockant les plongements frWac (500d).
- `requests==2.34.2` : Requêtes HTTP vers l'API Cémantix et vers le LLM local (LM Studio / Ollama).
- `psycopg[binary]==3.3.6` : Pilote PostgreSQL 3 natif avec pool de connexions et support JSONB.

### Runtime & Infrastructure
- **Python cible :** Python **3.12** (image officielle `python:3.12-slim`).
- **Base relationnelle :** PostgreSQL 16 (ou fallback `sqlite3` intégré à Python).
- **Frontend :** Vanilla HTML5, CSS natif, JavaScript ES Modules (zéro outil de build JS requis).
- **Reverse Proxy :** Caddy (production avec TLS automatique et HTTP/2) / Nginx (local WSL).

---

## 5. Invariants Architecturaux Inviolables

1. **Politique Anti-Spoiler Absolue :**
   - Le mot secret du jour ne doit JAMAIS transiter par l'API publique (`/api/daily` masque le mot tant que le puzzle n'est pas terminé).
   - Dans les pages d'archives SEO, la solution est encapsulée dans une balise `<details>` fermée pour éviter tout affichage involontaire.
2. **Repli SQLite Transparent :**
   - La couche d'accès aux données bascule automatiquement sur SQLite local (`DATA_DIR / "cemantix.sqlite3"`) si `DB_HOST` est absent. **Cet invariant permet d'exécuter la suite de tests unitaires sans base de données active.**
3. **Autonomie RAG Pure (`--rag-only`) :**
   - L'algorithme de résolution doit impérativement pouvoir converger par la descente Ridge et le reranking seuls, sans aucun appel au LLM externe.
4. **Zéro Requête CSS Bloquante en Production :**
   - Le CSS critique est injecté en `<style>` inline dans le `<head>` des pages principales pour garantir un score FCP/LCP optimal sous Lighthouse mobile.

---

## 6. Dette Technique Connue (Synthèse M0)

- **Sécurité (Résolue en M3) :** Filtrage fail-closed de `X-Forwarded-For` par proxys de confiance (`TRUSTED_PROXIES`) via [`src/api/proxy.py`](src/api/proxy.py). Suppression du montage de `/var/run/docker.sock` dans `cemantix_web` ([docker-compose.yml](docker-compose.yml)) éliminant le vecteur d'évasion vers l'hôte. Durcissement de l'API admin (rate limiting sur GET, fail-closed).
- **Couverture de tests :** Sanctuarisée par 248 tests unitaires déterministes (suite à M1, M2, M2.1, M3 et M4). Le cœur algorithmique (`solvers.py`), le domaine de jeu (`manager.py`), la sécurité réseau/admin et l'ensemble de la génération SEO sont validés sans dépendance externe en 8,4 s.
- **Harnais de non-régression (M1-M4) :** [`tests/test_engine_solvers.py`](tests/test_engine_solvers.py), [`tests/test_game_manager.py`](tests/test_game_manager.py), [`tests/test_solver_behavioral_compat.py`](tests/test_solver_behavioral_compat.py), [`tests/test_security_hardening.py`](tests/test_security_hardening.py), [`tests/test_seo_characterization.py`](tests/test_seo_characterization.py) et [`tests/test_seo_backward_compat.py`](tests/test_seo_backward_compat.py).
- **God Module SEO (Résolu en M4) :** Modularisation de [`src/services/seo.py`](src/services/seo.py) (réduit de 1 692 à ~250 lignes, soit -85 % de contexte token) en sous-modules spécialisés (`seo_templates.py`, `seo_archives.py`, `seo_hubs.py`, `seo_sitemap.py`, `seo_agents.py`) avec parité bit à bit et rétrocompatibilité ascendante totale via `__all__`.
- **Duplication :** Triple stockage CSS (source, `dist/`, inliné dans HTML).
- *Détails complets et feuille de route : voir [docs/audits/M0_TECHNICAL_DEBT.md](docs/audits/M0_TECHNICAL_DEBT.md) et [docs/audits/M0_REFACTORING_ROADMAP.md](docs/audits/M0_REFACTORING_ROADMAP.md).*

---

## 7. Règles d'Intervention & Commandes Opérationnelles

Les règles d'exécution, d'isolation du contexte agent et les 4 commandes de validation obligatoires sont consignées dans [AGENTS.md](AGENTS.md).
