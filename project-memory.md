# Project Memory — Cémantix RAG Solver

**Dernière mise à jour :** 30 octobre 2026 (Milestone M0)  
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
  - `solvers.py` : Algorithmes Ridge (`estimate_secret`), Rerank, `CemantixSolver`, `RagDuelPlayer`.
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
  - `seo.py` : Génération des pages HTML d'archives, sitemap XML et fiches agents.
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

## 5. Commandes de Build, Test & Déploiement

### Exécution des Tests Unitaires (Standard & Reproductible)
```bash
# Dans le conteneur Python 3.12 (méthode officielle recommandée) :
docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
  "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"

# Sur l'hôte (nécessite Python 3.12 avec les dépendances installées) :
python -m unittest discover -s tests -v
```

### Contrôles de Documentation, SEO & Bundles
```bash
python tools/check_docs.py          # Cohérence des liens, tables et compteurs
python tools/check_seo.py           # Balisage SEO, OpenGraph et JSON-LD
python tools/check_og_image.py      # Format et poids de l'image de partage
python tools/build_css_bundles.py --check  # Vérifie la synchronisation des bundles CSS
```

### Déploiement Docker Compose
```bash
docker compose up -d                # Démarre DB, Worker et Web
docker compose logs -f cemantix_worker  # Suivi des logs du solveur
docker compose logs -f cemantix_web     # Suivi des logs API
```

---

## 6. Décisions Architecturales Clés & Invariants Inviolables

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

## 7. Dette Technique & Points d'Attention Connus

- **Sécurité (P1) :** L'adresse IP cliente (`_client_ip()`) se fie au premier segment de `X-Forwarded-For` sans vérifier que la connexion émane d'un reverse proxy de confiance. Risque de contournement de rate-limiting et de quotas de défis.
- **Sécurité (P1) :** `/var/run/docker.sock` est monté dans `cemantix_web` pour permettre à la console admin de lire les logs conteneurs.
- **Couverture de tests (P1) :** 32 % de couverture globale mesurée. Les modules `solvers.py`, `game/` et `api/routes/` ont moins de 11 % de couverture.
- **God Module (P2) :** `src/services/seo.py` fait 1 692 lignes et centralise trop de responsabilités.
- **Duplication (P3) :** Le CSS existe en 3 versions (source, dist, inline) et les gabarits HTML partagent des éléments dupliqués.

---

## 8. Directives pour les Futurs Agents IA

1. **Ne pas modifier le code de production lors des audits.**
2. **Exécuter les tests dans l'image `python:3.12-slim`** pour éviter les conflits d'ABI sur les versions récentes de Python hôte.
3. **Ne jamais lire les fichiers de données volumineux en entier :** `cemantix_data/lexique_fr.txt` (465 Ko), `volumes/web/css/dist/*` (fichiers compilés), `CHANGELOG.md` (77 Ko). Utiliser des outils d'inspection ciblée (`grep`, lecture par plage de lignes).
4. **Si vous modifiez une feuille CSS dans `volumes/web/css/` :** exécuter impérativement `python tools/build_css_bundles.py` pour mettre à jour les bundles dist et les balises `<style>` inlinées dans les pages HTML.
5. **Préserver le repli SQLite :** Ne jamais forcer de syntaxe PostgreSQL exclusive sans implémenter son équivalent SQLite dans `src/db/connection.py`.
