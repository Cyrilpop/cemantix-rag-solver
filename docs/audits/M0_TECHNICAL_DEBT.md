# M0 — Technical Debt & Vulnerability Registry

**Date :** 30 octobre 2026  
**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Statut :** Livrable M0 (Audit-First — Dette Technique & Sécurité)  

---

## 1. Vue d'Ensemble de la Dette Technique

L'audit approfondi du dépôt `Cyrilpop/cemantix-rag-solver` met en lumière une base de code fonctionnellement riche et performante, mais accumulant une dette technique significative résultant de phases successives de développement rapide.

### Résumé des Domaines d'Impact
```
┌────────────────────────────────────────────────────────────────────────┐
│                      RÉPARTITION DE LA DETTE TECHNIQUE                 │
├────────────────────────┬────────┬──────────────────────────────────────┤
│ Domaine                │ Niveau │ Points Saillants                     │
├────────────────────────┼────────┼──────────────────────────────────────┤
│ 1. Sécurité            │ ÉLEVÉ  │ IP spoofing (XFF), Socket Docker     │
│ 2. Couverture Tests    │ ÉLEVÉ  │ 32% global, cœur algorithmique à 6%  │
│ 3. Architecture & Code │ MOYEN  │ God modules (seo.py), cycles imports │
│ 4. Frontend & CSS      │ MOYEN  │ Triple stockage CSS, HTML dupliqué   │
│ 5. Concurrence & DB    │ MOYEN  │ ThreadingHTTPServer, pool max = 8    │
│ 6. Documentation & CI  │ BAS    │ CI permissive, README désynchronisé  │
└────────────────────────┴────────┴──────────────────────────────────────┘
```

---

## 2. Registre Détaillé des Découvertes

### 2.1 Sécurité & Contrôle d'Accès

#### [SEC-DEBT-01] Usurpation d'Adresse IP et Contournement des Quotas / Rate-Limiting via `X-Forwarded-For`
- **Gravité :** **HAUTE**
- **Confiance :** Certaine (Vérifié par analyse de code)
- **Impact :** Contournement total des limites de débit de l'API, brute-force du mot de passe admin, contournement des quotas journaliers sur la file des défis au bot, usurpation d'adresses whitelistées.
- **Effort :** Faible (1 à 2 heures)
- **Risque de Régression :** Très faible
- **Localisation :**
  - [src/api/server.py](../../src/api/server.py) (lignes 78-83)
  - [src/api/server.py](../../src/api/server.py) (ligne 242)
  - [src/api/routes/admin.py](../../src/api/routes/admin.py) (ligne 441)
  - [src/api/routes/challenge.py](../../src/api/routes/challenge.py) (ligne 115)
- **Preuve & Mécanisme :**
  ```python
  def _client_ip(self) -> str:
      """Adresse du client, en tenant compte du reverse proxy Caddy."""
      forwarded = self.headers.get("X-Forwarded-For", "")
      if forwarded:
          return forwarded.split(",")[0].strip()
      return self.client_address[0] if self.client_address else "unknown"
  ```
  Le serveur accepte inconditionnellement le premier segment de `X-Forwarded-For` sans vérifier que `self.client_address[0]` provient d'un proxy inverse de confiance (ex. `127.0.0.1`, loopback ou réseau interne Docker du proxy). Un client direct sur le port 8000 ou transitant par un proxy non filtrant peut envoyer `X-Forwarded-For: <n-importe-quelle-ip>` à chaque requête.
- **Correction recommandée :** N'extraire `X-Forwarded-For` QUE si `self.client_address[0]` appartient à une liste d'adresses de proxies de confiance (paramétrable par variable d'environnement `TRUSTED_PROXIES`, défaut `127.0.0.1,::1`). Prendre l'adresse la plus proche du proxy de confiance, ou faire confiance exclusivement à `X-Real-IP` positionné par Caddy/Nginx.

---

#### [SEC-DEBT-02] Montage du Socket Docker Unix dans le Conteneur Web Public
- **Gravité :** **HAUTE**
- **Confiance :** Certaine (Vérifié dans docker-compose)
- **Impact :** Risque critique d'évasion de conteneur. En cas de vulnérabilité applicative dans le conteneur `cemantix_web`, l'accès au socket Docker permet de contrôler le démon Docker de l'hôte.
- **Effort :** Moyen
- **Risque de Régression :** Faible (désactive la lecture directe des logs Docker depuis l'admin si non relayé)
- **Localisation :**
  - [docker-compose.yml](../../docker-compose.yml) (lignes 129-136)
  - [src/api/routes/admin.py](../../src/api/routes/admin.py) (lignes 129-175)
- **Preuve & Mécanisme :**
  ```yaml
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  group_add:
    - "${DOCKER_GID:-120}"
  ```
  Sous Linux, le flag `:ro` sur un montage bind d'un socket Unix (`AF_UNIX`) ne protège pas contre l'écriture de requêtes HTTP sur la connexion établie via `connect()`. L'utilisateur `1000` avec le GID Docker peut envoyer des ordres HTTP REST au démon.
- **Correction recommandée :** Retirer le montage de `/var/run/docker.sock` du conteneur web de production. Si la consultation des journaux conteneur est requise dans la console admin, utiliser un proxy de socket Docker à privilèges réduits (ex. `tecnativa/docker-socket-proxy`) n'autorisant que `GET /containers/{name}/logs`, ou s'appuyer exclusivement sur le tampon applicatif en mémoire (`recent_logs`).

---

#### [SEC-DEBT-03] Vulnérabilités Logicielles Connues non Corrigées dans ChromaDB
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine (Vérifié via `pip-audit`)
- **Impact :** Vulnérabilités potentielles dans les dépendances de vectorisation / embeddings.
- **Effort :** Moyen (dépend des publications amont de ChromaDB)
- **Risque de Régression :** Moyen (montée de version de ChromaDB)
- **Localisation :**
  - [requirements.txt](../../requirements.txt) (ligne 3)
  - [.github/workflows/ci.yml](../../.github/workflows/ci.yml) (lignes 86-91)
- **Preuve :** `pip-audit` identifie 5 vulnérabilités dans `chromadb==1.5.9` (`PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814`, `PYSEC-2026-3815`). La CI ignore ces CVEs et le job audit possède `continue-on-error: true`.
- **Correction recommandée :** Surveiller les publications amont de ChromaDB, mettre à jour dès qu'un wheel Python 3.12 corrigé est disponible, et rendre le job CI bloquant sur toute NOUVELLE vulnérabilité.

---

### 2.2 Couverture de Tests & Trous dans la Validation

#### [TEST-DEBT-01] Couverture Globale Faible (32%) et Absence de Tests sur le Cœur Algorithmique
- **Gravité :** **HAUTE**
- **Confiance :** Certaine (Mesuré avec `coverage run -m unittest discover -s tests`)
- **Impact :** Risque extrême de régressions invisibles lors de toute retouche sur le solveur, les règles de jeu ou les routes API principales.
- **Effort :** Moyen à Élevé
- **Risque de Régression :** Nul (ajout de tests uniquement)
- **Localisation :**
  - [src/engine/solvers.py](../../src/engine/solvers.py) : **6% de couverture** (379 lignes non couvertes sur 405)
  - [src/game/battle.py](../../src/game/battle.py) : **8% de couverture** (140 lignes non couvertes sur 152)
  - [src/game/multi.py](../../src/game/multi.py) : **9% de couverture** (236 lignes non couvertes sur 259)
  - [src/game/manager.py](../../src/game/manager.py) : **10% de couverture** (307 lignes non couvertes sur 342)
  - [src/cli/modes.py](../../src/cli/modes.py) : **2% de couverture** (616 lignes non couvertes sur 627)
  - [src/api/routes/multi.py](../../src/api/routes/multi.py) : **5% de couverture**
  - [src/api/routes/battle.py](../../src/api/routes/battle.py) : **10% de couverture**
  - [src/api/routes/solo.py](../../src/api/routes/solo.py) : **11% de couverture**
- **Preuve :** Sur 5 722 déclarations exécutables dans `src/`, 3 898 ne sont jamais atteintes par la suite de tests. Les 163 tests existants se concentrent à plus de 70% sur le SEO (`seo.py`), les défis bot (`challenges.py`) et le pool de base de données.
- **Correction recommandée :** Rédiger en priorité absolue des tests unitaires déterministes (avec `MockClient` et petits vecteurs synthétiques) pour :
  - `estimate_secret` (Ridge) et `rerank` dans `src/engine/solvers.py`.
  - La machine d'état de `GameSession`, `BattleSession` et `MultiplayerSession`.
  - Les contrôleurs API `handle_solo_post`, `handle_battle_post`, `handle_multi_post`.

---

#### [TEST-DEBT-02] Dépendance à Python 3.12 et Impossibilité de Tester sur Python 3.14 Hôte
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine (Échec mesuré : 40 tests en erreur sur Python 3.14 hôte)
- **Impact :** Les développeurs ou agents exécutant `python3 -m unittest` sur une machine hôte récente échouent immédiatement avec `ModuleNotFoundError: No module named 'numpy'`, car `numpy==2.0.2` ne dispose pas de wheel précompilé pour Python 3.14.
- **Effort :** Faible
- **Risque de Régression :** Nul
- **Correction recommandée :** Documenter formellement dans `AGENTS.md` et `project-memory.md` la commande d'exécution containerisée standard (`docker run --rm -v $(pwd):/app -w /app python:3.12-slim ...`).

---

### 2.3 Architecture Modulaire & Couplage

#### [ARCH-DEBT-01] God Module `src/services/seo.py` (1 692 lignes)
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine (Inspection de code)
- **Impact :** Violation flagrante du principe de responsabilité unique (SRP). Forte charge cognitive et saturation de contexte pour les agents IA (~18 800 tokens).
- **Effort :** Moyen
- **Risque de Régression :** Faible (protégé par 90% de couverture de tests sur le SEO)
- **Localisation :** [src/services/seo.py](../../src/services/seo.py)
- **Sous-responsabilités identifiées à scinder :**
  - Formatage français de dates et durées (`src/services/seo/formatters.py`)
  - Injection de tokens et CSS critique (`src/services/seo/styles.py`)
  - Gabarits de pages d'archives quotidiennes (`src/services/seo/archives.py`)
  - Pages hubs thématiques mot-du-jour & méthode (`src/services/seo/hubs.py`)
  - Générateur de sitemap XML (`src/services/seo/sitemap.py`)
  - Générateur des manifestes ARD et fiches agents (`src/services/seo/manifests.py`)

---

#### [ARCH-DEBT-02] Cycles d'Importation Circulaire Masqués
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine (Détecté par analyseur de graphe AST)
- **Impact :** Architecture fragile, obligation d'utiliser des `import` retardés à l'intérieur des méthodes et fonctions.
- **Effort :** Faible
- **Risque de Régression :** Faible
- **Localisation :**
  - `src.db.multi` ↔ `src.game.multi` ([src/db/multi.py](../../src/db/multi.py) L163 et [src/game/multi.py](../../src/game/multi.py) L127)
  - `src.services.daemon` ↔ `src.services.seo` ↔ `src.services.web` ([src/services/seo.py](../../src/services/seo.py) L1677, [src/services/web.py](../../src/services/web.py) L22, [src/services/daemon.py](../../src/services/daemon.py) L362)
- **Cause racine :** Constantes transversales mal localisées (`PARIS_TZ`, `DAILY_HISTORY_FILE`, `HEARTBEAT_FILE` logées dans `daemon.py` au lieu de `config.py`).
- **Correction recommandée :** Déplacer toutes les constantes partagées de chemins et de fuseaux horaires vers `src/config.py`.

---

#### [ARCH-DEBT-03] Sur-Couplage du Package Racine `src/__init__.py`
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine
- **Impact :** Tout `import src` ou sous-import non scellé importe l'intégralité du projet, y compris les dépendances lourdes C.
- **Effort :** Faible
- **Risque de Régression :** Très faible
- **Localisation :** [src/__init__.py](../../src/__init__.py) (lignes 13-101)
- **Correction recommandée :** Alléger `src/__init__.py` pour ne réexporter que les métadonnées de version, sans importer automatiquement `engine`, `api`, `cli`, `db` et `services`.

---

### 2.4 Frontend, CSS & Duplication

#### [FRONT-DEBT-01] Duplication Triple des Feuilles de Style CSS
- **Gravité :** **MOYENNE**
- **Confiance :** Certaine
- **Impact :** Une modification de style impose d'éditer la source, de lancer le script de build pour générer `dist/` (versionné sous git) et de vérifier l'HTML inliné.
- **Effort :** Moyen
- **Risque de Régression :** Faible
- **Localisation :**
  - `volumes/web/css/*.css`
  - `volumes/web/css/dist/*.css`
  - Balises `<style id="critical-css">` dans `volumes/web/**/*.html`
- **Correction recommandée :** Standardiser la chaîne de build CSS pour que `dist/` soit soit exclu de git et généré au déploiement, soit généré automatiquement par un script idempotent validé en CI.

---

#### [FRONT-DEBT-02] Duplication Structurelle des Gabarits HTML
- **Gravité :** **BASSE**
- **Confiance :** Certaine
- **Impact :** Toute modification de la barre de navigation, du footer ou des métadonnées `<head>` impose de modifier 5 fichiers HTML distincts.
- **Effort :** Moyen
- **Risque de Régression :** Faible
- **Localisation :** `volumes/web/index.html`, `play/index.html`, `battle/index.html`, `multi/index.html`, `defi/index.html`.

---

#### [FRONT-DEBT-03] Duplication du Rendu des Coups dans `game.js`
- **Gravité :** **BASSE**
- **Confiance :** Certaine
- **Impact :** Incohérence visuelle ou divergence de comportement lors des évolutions d'affichage des scores et badges.
- **Effort :** Faible
- **Risque de Régression :** Très faible
- **Localisation :** [volumes/web/js/game.js](../../volumes/web/js/game.js) (lignes 655-690) par rapport à [volumes/web/js/render.js](../../volumes/web/js/render.js) (lignes 20-64).
- **Correction recommandée :** Remplacer le code de rendu manuel dans `game.js` par l'appel à `buildGuessesListHtml` de `render.js`.

---

### 2.5 Persistance & Base de Données

#### [DB-DEBT-01] Schémas DDL Dupliqués en 3 Exemplaires
- **Gravité :** **BASSE**
- **Confiance :** Certaine
- **Impact :** Risque de désynchronisation entre le schéma Postgres initial du conteneur et les schémas Python lors des migrations de tables.
- **Localisation :**
  - [database/init.sql](../../database/init.sql)
  - `PG_SCHEMA` dans [src/db/connection.py](../../src/db/connection.py) (ligne 59)
  - `SQLITE_SCHEMA` dans [src/db/connection.py](../../src/db/connection.py) (ligne 125)
- **Correction recommandée :** Centraliser la source de vérité des schémas sous forme de fichiers SQL distincts (`schema.postgres.sql`, `schema.sqlite.sql`) lus à l'initialisation.

---

### 2.6 Concurrence & Performance

#### [PERF-DEBT-01] Modèle de Concurrence Bloquant (1 Thread / Requête) et Plafond de Pool Étroit
- **Gravité :** **MOYENNE**
- **Confiance :** Haute
- **Impact :** `ThreadingHTTPServer` alloue un thread OS par connexion. Les flux SSE (`_send_sse`) maintiennent ces threads ouverts indéfiniment. Avec `DB_POOL_MAX = 8`, un pic de trafic simultané sature rapidement le pool de connexions (timeout de 10s puis erreur 500).
- **Localisation :**
  - [src/api/server.py](../../src/api/server.py) (ligne 65)
  - [src/db/connection.py](../../src/db/connection.py) (ligne 45)
- **Correction recommandée :** Documenter cette limite volumétrique pour l'infrastructure actuelle (convient pour un usage modéré / personnel) et prévoir une évolution progressive vers un serveur asynchrone non-bloquant si la fréquentation augmente.
