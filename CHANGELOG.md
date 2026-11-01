# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-11-01 · Jalon M7 : Optimisation SEO des Métadonnées (Indices, Synonymes et Mots Proches)

### Ajouté
- **Enrichissement sémantique des métadonnées avec les 10 mots indices du jour (`src/services/seo_templates.py`, `seo_archives.py`, `seo_hubs.py`, `seo.py`)** :
  - Fonction utilitaire `format_clue_words_list` extrayant et normalisant les 10 premiers mots indices du thermomètre (minuscules, séparés par des virgules, filtrage du masque `••••••••`).
  - Injection automatique de la liste descriptive des 10 indices thermiques dans les balises `<meta name="description">`, `og:description` et `twitter:description` des pages d'archives quotidiennes (`/puzzles/AAAA-MM-JJ/`) et du hub Mot du jour (`/mot-du-jour/`).
  - Intégration des indices et synonymes dans le résumé statique pré-rendu du tableau de bord (`_daily_summary`, `prerender_dashboard`).

### Modifié
- **Réalignement des balises `<title>`, `<h1>` et métadonnées sur les intentions de recherche cibles** :
  - Balises `<title>` et `<h1>` des archives orientées vers la longue traîne : « Indice Cémantix #{puzzle} du {date_fr} : 10 indices, synonymes et solution ».
  - Titre du hub Mot du jour actualisé : « Indice Cémantix du jour ({date_fr}) : indices, synonymes et mot du jour ».
  - Titres de l'index paginé des archives axés sur les indices : « Indice Cémantix du jour : archives des mots du jour, indices et solutions par date » (page 1) et « ...page {page} » (page N).
  - Synchronisation stricte des propriétés Schema.org JSON-LD (`Article.headline`, `Article.description`, `CollectionPage.headline`, `CollectionPage.description`).
- **Sanctuaire de tests & Non-régression (`tests/test_seo_*.py`)** :
  - Adaptation complète des assertions de titrage, de description et de structure JSON-LD dans `test_seo_archives.py`, `test_seo_characterization.py`, `test_seo_hubs.py` et `test_seo_backward_compat.py`.
  - 331 tests unitaires validés avec succès sous Docker Python 3.12 (0 régression).

### Corrigé
- **Préservation et désérialisation garantie des indices du mot du jour (`src/db/daily.py`, `src/services/seo_templates.py`, `src/services/seo_hubs.py`, `src/services/seo.py`)** :
  - `_row_to_entry` : désérialisation JSON sécurisée (`json.loads`) des colonnes `top_guesses` et `trajectory` lorsqu'elles sont renvoyées sous forme de chaînes de caractères par SQLite, empêchant la perte silencieuse des listes d'indices.
  - `extract_clue_guesses` : chaîne de repli robuste garantissant l'extraction d'indices pour chaque puzzle (`top_guesses` -> `trajectory` ordonnée -> table relationnelle `daily_puzzle_hints`).
  - Filtrage anti-spoiler systématique : exclusion rigoureuse du mot secret (par comparaison insensible à la casse ou score maximal 100°C / 1000‰) et des leurres masqués (`••••••••`) de la liste descriptive des métadonnées et du tableau HTML d'indices.
  - Nettoyage automatique (`tearDown`) dans `TestHintsService` pour éviter toute pollution de la base SQLite locale par des puzzles de test sans indices.
  - Nouvelle suite de tests unitaires dédiée : `tests/test_seo_clues_preservation.py` (5 tests validés).

---

## [Non publié] - 2026-11-01 · Jalon M6 : Persistance Relationnelle des Paliers d'Indices & Bootstrap Idempotent (daily_puzzle_hints)

### Ajouté & Amélioré
- **Schéma relationnel multi-dialecte (`database/init.sql`, `src/db/connection.py`)** :
  - Création de la table `daily_puzzle_hints` sous PostgreSQL et SQLite avec intégrité référentielle en cascade (`REFERENCES daily_puzzles(date) ON DELETE CASCADE`), contrainte d'unicité composite `UNIQUE(puzzle_date, word)` et index optimisé `idx_daily_hints_date`.
  - Types multi-dialectes stricts (`SERIAL`/`AUTOINCREMENT`, `BOOLEAN`, `TIMESTAMPTZ`/`TEXT`, `NUMERIC(6,2)`/`REAL`).
- **Couche CRUD & Gestion du cycle de vie des indices (`src/db/daily.py`, `src/db/__init__.py`)** :
  - `save_daily_hints(puzzle_date, hints)` : insertion par lot avec gestion des conflits (`ON CONFLICT (puzzle_date, word) DO UPDATE`).
  - `get_daily_hints(puzzle_date, only_revealed=False)` : extraction ordonnée par score avec filtrage optionnel des indices révélés.
  - `reveal_daily_hint_tier(puzzle_date, tier)` : mise à jour transactionnelle du statut de révélation pour un palier donné.
- **Service RAG sémantique & Extraction des paliers (`src/services/hints.py`)** :
  - Algorithme `generate_hints_for_word(secret_word, store)` calculant les similarités cosinus et attribuant les mots candidats aux paliers thermiques cibles (800, 900, 950, 990).
  - Filtrage linguistique strict : exclusion du mot secret, stopwords, mots < 4 lettres, séparateurs, et lemmatisation par radical commun (stemming anti-triche).
  - Rattrapage idempotent (`backfill_puzzle_hints()`) détectant les puzzles sans indices en base pour les générer via le RAG local.
- **Bootstrap universel et idempotent au démarrage des conteneurs (`src/services/hints.py`, `daemon.py`, `cemantix_rag.py`)** :
  - Fonction universelle `bootstrap_database()` exécutée au démarrage de `cemantix_worker` et `cemantix_web`.
  - Exécution automatique de `init_db()` pour garantir la présence des tables et index sans aucune intervention manuelle `psql`.
  - `backfill_daily_puzzles_from_json()` : rattrapage automatique et idempotent des puzzles historiques depuis `daily_history.json` vers `daily_puzzles` (`ON CONFLICT DO UPDATE`).
  - Script CLI dédié `scripts/backfill_daily_hints.py` et option `--backfill-hints` dans `cemantix_rag.py`.
- **Validation unitaire et résilience (`tests/test_db.py`, `tests/test_hints_service.py`)** :
  - Tests unitaires complets sous SQLite du cycle CRUD, des conflits, de l'intégrité référentielle et du bootstrap.
  - Suite de 326 tests au vert sous Docker Python 3.12.

---

## [Non publié] - 2026-11-01 · Jalon M6 : Unification du Layout, Navigation Universelle & Architecture Modulaire en 4 Briques (Universal Layout, Navigation & 4-Block Modular Architecture)

### Ajouté & Amélioré
- **Architecture modulaire en 4 briques & Synchronisation automatique (`src/services/layout_sync.py`, `tools/sync_layout.py`)** :
  - Découpage strict et universel en 4 composants : En-tête (`.app-header`), Menu (`.nav-tabs`), Contenu (`main`), et Pied de page (`.app-footer`).
  - Balises de synchronisation d'en-tête `<!-- APP-HEADER:START/END -->` et d'onglets `<!-- NAV-TABS:START/END -->` sur l'ensemble des 5 vues applicatives.
  - Synchronisation automatique au démarrage des conteneurs web et worker (`ensure_seo_published`) garantissant l'alignement immédiat des vues.
- **Identité visuelle universelle & Logo haute définition (`volumes/web/icons/favicon.png`, `favicon.ico`)** :
  - Déploiement du logo officiel transparent dans le header en remplacement de l'émoji générique.
  - Balises de favicon canoniques (`favicon.png`, `favicon.ico`, `apple-touch-icon.png`) sur toutes les pages HTML.
- **Normalisation de la navigation par onglets (`layout.css`, `.nav-tabs`)** :
  - Ordre canonique harmonisé sur les 6 vues : Tableau de Bord, Jouer Solo, Mode Battle (Versus IA), Mode Multijoueur (1v1 Ami), Défier le Bot (Live), Archives.
  - Hauteur uniforme verrouillée à 42px et prévention des sauts de défilement inter-onglets (`scrollbar-gutter: stable`).
- **Harmonisation des gabarits d'archives & Hubs SEO (`src/services/seo_templates.py`, `seo_archives.py`)** :
  - Intégration du header et footer universels sur les pages d'archives `/puzzles/` avec conteneur centré à 1200px.
  - Bascule de thème sombre/clair dynamique et immédiate sans appel réseau (`localStorage`).
  - Navigation par dates repositionnée sous la solution avec des boutons d'action ergonomiques.
  - Inclusion du numéro de puzzle (`#XXX`) dans les titres d'archives et méta-données SEO.
- **Pagination par 10 de l'index des archives et de l'historique du tableau de bord** :
  - Pagination côté serveur de l'index `/puzzles/` par tranches de 10 puzzles avec contrôles complets (Précédent, Suivant, liens relatifs fiabilisés).
  - Pagination dynamique côté client de l'historique du tableau de bord (`volumes/web/js/dashboard.js`, `dashboard.css`) avec navigation par 10.
- **Sécurité HTTP & Déploiement** :
  - Retrait de la directive obsolète `interest-cohort` dans l'en-tête `Permissions-Policy` (`server.py`, `cemantix.local.conf`, `README.md`).
  - Rédaction du guide de déploiement VPS sous Docker et Caddy dans `README.md` et `docs/roadmap/2026-10-07-unification-layout-ux/`.

---

## [Non publié] - 2026-10-31 · Jalon M5.1 : Correction de la Révélation du Mot Secret & Accessibilité Clavier (Dashboard Secret Word Reveal Bugfix)

### Corrigé
- **Révélation locale du mot secret sur le tableau de bord (`volumes/web/js/dashboard.js`, `volumes/web/index.html`)** :
  - Suppression de la condition bloquante `!themeState.globalSpoiler` dans `revealSecretWord()`, permettant au clic direct sur la carte `#secret-word-card` de lever le flou et d'afficher le mot du jour sans désactiver la protection anti-spoiler globale sur les autres indices et l'historique.
  - Déduplication des requêtes en cours de vol via le drapeau `dashboardState.isRevealing` pour prévenir les doubles appels API en cas de clics répétés.
  - Préservation de la révélation locale lors des actualisations périodiques en arrière-plan (`renderDashboard`).
  - Accessibilité clavier renforcée sur la carte (`tabindex="0"`, `role="button"`, `aria-expanded`, gestion des touches `Entrée` et `Espace`).
  - Ajout de 9 tests de non-régression dans `tests/test_frontend_characterization.py` (suite portée à 277 tests unitaires déterministes, 0 échec).

---

## [Non publié] - 2026-10-31 · Jalon M5 : Simplification Frontend & Efficacité Contexte Agent (Frontend Simplification & Agent Context Efficiency)

### Modifié & Optimisé
- **Mutualisation du rendu JavaScript des tentatives (`volumes/web/js/render.js`, `game.js`)** :
  - Extension de `buildGuessesListHtml` avec l'option `orderFormat` (`"rank"`, `"brackets"`, `"default"`).
  - Délégation du rendu de `gameTopList` et `gameChronoList` dans `game.js` au module partagé `renderGuessesContainer`, réduisant `game.js` de 51 lignes (-7,3 %) tout en apportant le cache anti-scintillement DOM et la copie au clic.
- **Mutualisation des étapes de trajectoire (`volumes/web/js/trajectory.js`, `defi.js`)** :
  - Extraction de `buildTrajectoryStepHtml(item, options)` dans `trajectory.js`, partagé entre la modal de débriefing et la page live de défi bot.
  - Suppression de la fonction dupliquée `stepRowHtml` dans `defi.js` (-40 lignes, -13,1 %).
- **Allègement des gabarits HTML statiques & Injection dynamique des modales** :
  - Ajout de `ensureTrajectoryModal()` dans `trajectory.js` pour injecter dynamiquement le conteneur `#trajectory-modal` au premier appel si absent du DOM.
  - Retrait de 68 lignes de duplication HTML statique dans `volumes/web/defi/index.html` (-9,3 % de taille).
  - Suppression du gestionnaire inline `onsubmit="return false;"` sur `<form id="form-join-game">` dans `volumes/web/multi/index.html` pour renforcer la conformité CSP.
- **Dédoublonnage CSS & Régénération des bundles** :
  - Suppression des règles desktop dupliquées `.pill-group`, `.pill-btn`, `.pill-btn:hover`, `.pill-btn.active` dans `volumes/web/css/game.css` (déjà déclarées dans `base.css`).
  - Régénération des bundles via `tools/build_css_bundles.py` : allègement de 514 octets sur `play.css`, `battle.css` et `multi.css`.
- **Efficacité de Contexte & Outils d'Inspection IA (`tools/agent_find.py`, `AGENTS.md`)** :
  - Extension de `tools/agent_find.py` avec la recherche d'identifiants et de repères HTML (`id`, `header`, `nav`, `main`, `section`, `form`).
  - Détection automatique du bloc CSS critique inliné (L44-L49, ~32 ko / ~8 000 tokens) dans `file_summary` avec recommandations de plages de lecture contextuelles.
  - Ajout du mode `--safe-html` masquant le bloc CSS critique lors de l'inspection du `<head>` HTML pour économiser ~42 000 tokens par tournée d'analyse complète.
  - Actualisation du guide opérationnel `AGENTS.md` et de `project-memory.md`.
- **Suite de tests de caractérisation et non-régression** :
  - [`tests/test_frontend_characterization.py`](tests/test_frontend_characterization.py) : 15 tests vérifiant les contrats DOM, la cohérence de navigation, l'accessibilité des modales, la conformité CSP et la stabilité des exports ES Modules.
  - [`tests/test_agent_find.py`](tests/test_agent_find.py) : 5 tests validant la découverte multi-langages (Python, JS, HTML) et la protection de contexte agent.
- **Validation** : suite complète portée à **268 tests unitaires déterministes** (0 échec, 0 régression en 7,1 s sous Docker Python 3.12). 100 % de réussite sur `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check` et `tests/test_responsive.py`.

---

## [Non publié] - 2026-10-31 · Jalon M4 : Modularisation Sécurisée du Sous-Système SEO & Réduction de Contexte Agent (Safe SEO Modularization & Context Reduction)

### Modifié & Optimisé
- **Modularisation du God Module SEO (`src/services/seo.py`)** : découpage du fichier monolithique de 1 692 lignes (76 Ko) en sous-modules spécialisés à responsabilité unique, réduisant l'empreinte de `seo.py` à ~250 lignes (-85 % de contexte token) :
  - `src/services/seo_templates.py` : squelette HTML autonome (`render_page`), constantes de mise en page, formatage de dates en français (`format_date_fr`, `archive_title`), sérialisation Schema.org JSON-LD et injection CSS inline sans requête bloquante.
  - `src/services/seo_archives.py` : pages d'archives quotidiennes (`build_archive_page`) avec protection anti-spoiler `<details>` et protection "thin content" (balise `noindex` automatique si aucun indice), index paginé (`build_archives_index_page`).
  - `src/services/seo_hubs.py` : hubs thématiques rendus côté serveur ciblant la longue traîne Google (`build_mot_du_jour_page`, `build_methode_page`), accordéons FAQ natifs et micro-données `HowTo`/`FAQPage`.
  - `src/services/seo_sitemap.py` : génération conforme au protocole sitemaps.org (`build_sitemap`), écriture atomique multi-conteneurs `_write_file`.
  - `src/services/seo_agents.py` : manifestes de découverte ARD/A2A (`build_ard_manifest`, `build_agent_card`, `publish_ard_manifests`) et régénération dynamique de `llms.txt` et `agent-skills.md`.
  - `src/services/seo.py` : orchestrateur allégé (`publish_seo_pages`, `ensure_seo_published`, `prerender_dashboard`) assurant une rétrocompatibilité descendante totale via ré-exports explicites (`__all__`).
- **Rétrocompatibilité ascendante stricte & Préservation des contrats de patch** : tous les imports existants (`from src.services.seo import ...`) conservent l'identité stricte d'objet (`assertIs`), le monkeypatching historique (`ensure_seo_published`, `publish_seo_pages`, `WEB_ROOT`) est préservé sans effet de bord.
- **Suite de tests de caractérisation et rétrocompatibilité** :
  - [`tests/test_seo_characterization.py`](tests/test_seo_characterization.py) : 12 tests de caractérisation déterministe validant la structure HTML, les invariants anti-spoiler, la conformité sitemap XML et la non-régression de publication sur disque temporaire.
  - [`tests/test_seo_backward_compat.py`](tests/test_seo_backward_compat.py) : 5 tests d'identité stricte d'objets, de validation de `__all__`, d'interception par monkeypatching et d'équivalence bit à bit des sorties directes vs ré-exportées.
- **Validation** : suite complète portée à **248 tests unitaires déterministes** (0 échec, 0 régression en ~8,4 s sous conteneur Docker Python 3.12). 100 % de réussite sur `tools/check_docs.py`, `tools/check_seo.py` et `tools/build_css_bundles.py --check`.

---

## [Non publié] - 2026-10-31 · Jalon M3 : Sécurisation & Frontières de Confiance Réseau (Security Hardening & Trust Boundaries)

### Ajouté & Sécurisé
- **Gestion sécurisée des proxys de confiance (`src/api/proxy.py`)** : résolution fail-closed de l'IP effective du client via `extract_client_ip`. L'en-tête `X-Forwarded-For` n'est désormais pris en compte QUE si la connexion TCP directe provient d'un proxy explicitement déclaré dans `TRUSTED_PROXIES`. Dépilage de droite à gauche insensible à l'injection d'adresses en amont. Anonymisation RGPD (/24 en IPv4, /48 en IPv6).
- **Suppression du socket Docker dans le conteneur web (`docker-compose.yml`)** : suppression du montage `/var/run/docker.sock` et du groupe `DOCKER_GID` sur `cemantix_web`, neutralisant tout risque d'évasion vers l'hôte. Repli gracieux et informatif sur les journaux mémoire applicatifs (`source=app`).
- **Durcissement de l'API d'administration (`src/api/routes/admin.py`)** : application du rate limiting (`_api_limiter`) sur les routes `GET`, révocation immédiate de tout jeton si `ADMIN_PASSWORD` est vide, traçabilité de l'adresse IP cliente sur les échecs d'authentification.
- **Suite de tests de sécurité (`tests/test_security_hardening.py`)** : 19 tests déterministes couvrant le filtrage des proxys de confiance, l'impossibilité de contourner le rate limiting ou les quotas de défi par rotation d'en-tête, le refus d'usurpation de whitelist, et l'isolation du socket Docker. Total porté à 231 tests (0 échec).

---

## [Non publié] - 2026-10-30 · Jalon M2.1 : Durcissement de la Compatibilité Comportementale du Solveur

### Modifié & Optimisé
- **Compatibilité comportementale de monkeypatching (M2.1)** : intégration d'une résolution tardive de façade (`_resolve_ranking_fn`) dans `src/engine/duel.py`, garantissant que tout patch ciblant `src.engine.solvers.estimate_secret`, `rerank` ou `weather_for_score` intercepte immédiatement les décisions de `RagDuelPlayer` sans créer de cycle d'importation.
- **Suite de tests comportementaux (`tests/test_solver_behavioral_compat.py`)** : validation de l'interception indirecte via `Solver` et `RagDuelPlayer`, et de la stricte équivalence numérique et séquentielle des trajectoires M1 vs M2. Total porté à 212 tests (0 échec).

---

## [Non publié] - 2026-10-30 · Jalon M2 : Modularisation et Découplage Sécurisé du Solveur

### Modifié & Optimisé
- **Découplage modulaire de `src/engine/solvers.py` (M2)** : scission du fichier monolithique de 588 lignes en modules spécialisés et hautement cohésifs :
  - `src/engine/ranking.py` : fonctions mathématiques pures (Ridge `estimate_secret`, rerank multicritère `rerank`, météo officielle `weather_for_score`). Couverture unitaire : 100 %.
  - `src/engine/llm.py` : intégration du client OpenAI ChatCompletions local (`ask_llm`) et formatage strict du prompt avec candidats RAG.
  - `src/engine/duel.py` : joueur IA autonome `RagDuelPlayer` pour le mode Duel/Battle.
  - `src/engine/solvers.py` : orchestrateur autonome `Solver` (allégé à 397 lignes, -32,5 %) conservant la trajectoire, l'échantillonnage FPS et la boucle de convergence.
- **Rétrocompatibilité ascendante stricte** : tous les symboles historiques sont ré-exportés via `src.engine.solvers`, `src.engine` et `src`. Préservation validée par `tests/test_solver_backward_compat.py` (identité stricte `assertIs`, monkeypatching effectif, absence d'imports circulaires).
- **Validation** : 204 tests unitaires passés avec succès sous conteneur Docker Python 3.12 (0 échec).

---

## [Non publié] - 2026-10-30 · Évolution « Défier le bot IA » (docs/roadmap/2026-10-06-defier-le-bot)

### Ajouté
- **File de tâches tri-partite `bot_challenges` (`DEFI-01..03`)** — nouvelle table PostgreSQL/SQLite (id 128 bits aléatoire, `ip_hash` HMAC-SHA256 salé de l'IP /24, statuts `queued|running|solved|lost|error`, trajectoire JSONB incrémentale, `heartbeat_at`) + table `bot_challenge_whitelist` des IP exemptées. DAO dédié `src/db/challenges.py` : claim atomique (`UPDATE … WHERE status='queued'`), recyclage des orphelins (`requeue_stale_running` : un second orphelinat → `error`), purge RGPD à 30 jours. Repli SQLite complet, requêtes 100 % paramétrées.
- **Trois routes publiques sans aucun calcul dans le web (`DEFI-04..08`)** — `POST /api/challenge` (validation regex + lexique à message unique, anti-rafale mémoire 6 créneaux refill 10/min, **quota 10/h persisté en base** insensible aux restarts, file bornée à 20), `GET /api/challenge/<id>` (état borné : compte de coups, jamais la trajectoire), `GET /api/challenge/<id>/stream` (SSE 0,5 s, plafond global de 16 flux, durée max 15 min). Le module `src/api/routes/challenge.py` n'importe **ni le solveur ni le démon** — vérifié par grep (`DEFI-04`).
- **Pick-up et résolution dans le démon (`DEFI-09..13`)** — `src/services/challenges.py` : toutes les 3 s dans la boucle de veille, `requeue_stale_running()` puis claim atomique, résolution par le moteur existant `Solver` + `MockClient(secret=mot-du-joueur)` **en 100 % RAG pur (zéro LLM)**, trajectoire publiée toutes les 2 s avec heartbeat, plafond `CHALLENGE_TIMEOUT` (900 s), `max_tries` forcé côté serveur. La résolution nocturne de minuit reste prioritaire ; `CHALLENGE_ENABLED=0` = kill-switch sans redéploiement.
- **Page `/defi/` à l'affichage identique (`DEFI-14..17`)** — nouveau mode « 🤖 Défier le Bot » ajouté à la navigation des 5 pages, suivi en direct par `EventSource` avec **repli polling** (3 reconnexions), chrono, quota restant, rendu des coups au gabarit exact de la trajectoire du mot du jour (badges Graine/RAG/Sniper, ⭐ record, 🏆 cible) et modal de trajectoire complète réutilisée. SEO complet (title, canonical, OG, JSON-LD) audité par `tools/check_seo.py` qui couvre désormais 5 pages.
- **Whitelist administrable (`DEFI-18`)** — `GET/POST <ADMIN_BASE_PATH>/whitelist` + `DELETE …/whitelist/<ip>` (validation `ipaddress`), intégrée à la console cachée avec formulaire d'ajout et retrait en un clic ; une IP exemptée saute quota base, anti-rafale et file.
- **Suite `tests/test_defi_bot.py` (30 tests, QUAL-20)** — validation du mot, quota 10→429 **survivant au rechargement mémoire**, anti-rafale, file bornée, exemption whitelist, administration (formats IP), claim atomique à deux threads, orphelins, purge, résolution bout-en-bout (moteur simulé), kill-switch.

### Sécurité (aucune faille tolérée, `SEC-20..28`)
- Quota **persisté en base** (HMAC d'IP /24, sel `CHALLENGE_IP_SALT`/`DB_PASS`, jamais l'IP brute) ; IP jamais stockée en clair dans `bot_challenges` ; purge automatique à 30 jours (RGPD).
- Anti-XSS trois couches (regex+lexique, paramètres liés, `escapeHtml()` systématique) ; identifiants de défis non devinables ; `Cache-Control: no-store` sur toutes les réponses ; le mot du joueur n'apparaît dans **aucune** réponse avant le statut terminal, et seulement si le bot a gagné.
- Coût borné : file ≤ 20, `max_tries` serveur, timeout 900 s, SSE ≤ 16 flux ; le worker ne lit **que** `bot_challenges` (le canal admin `daemon_command.json` reste réservé à l'admin).

### Vérifications
- `python -m unittest discover -s tests` : **151 tests OK** (dont 30 nouveaux).
- Recette worker réelle (image `cemantix:latest`, mot « amour ») : `queued → running → solved` en 5 coups, 0,38 s de calcul, trajectoire incrémentale visible en base.
- `tools/check_seo.py` (5 pages) et `tools/check_docs.py` : `=== OK ===`.

---

## [Non publié] - 2026-10-30 · Roadmap : ordre chronologique des évolutions et contrôleur de documents durci

### Modifié & Optimisé
- **Dossiers d'évolution numérotés (`docs/roadmap/`)** : le préfixe `AAAA-MM` étant commun aux cinq évolutions ouvertes en octobre, l'ordre alphabétique (explorateur VS Code, GitHub, `ls`) les rangeait **par slug**, donc à l'envers de l'histoire du projet. Passage au motif `AAAA-MM-NN-slug`, `NN` étant le rang d'ouverture dans le mois : `2026-10-01-audit-web`, `2026-10-02-securite-seo-performance`, `2026-10-03-responsive-mobile`, `2026-10-04-seo-titres-archives`, `2026-10-05-seo-tendance-mot-du-jour`. Renommages purs (`git mv`, 10 fichiers, `+0/−0`), **aucune URL ni aucun contenu modifié**.
- **Contrôleur `tools/check_docs.py` rendu indépendant du nom des dossiers** : `controle_compteurs()` codait en dur `docs/roadmap/2026-10-securite-seo-performance/02-avancement.md` et plantait donc d'un `FileNotFoundError` au premier renommage. Il parcourt désormais tous les `docs/roadmap/*/02-avancement.md` et saute ceux qui n'ont pas de tableau de bord. Deux effets de bord utiles : il **couvre maintenant les quatre** évolutions dotées d'un tableau de bord au lieu d'une seule (66, 12, 4 et 5 findings, tous justes), et son motif d'identifiant générique `[A-Z][A-Z0-9]{1,5}-NN[a-z]` reconnaît enfin `A11Y-*` et `RESP-01` à `RESP-12`, que la liste `SEC|PERF|SEO|QUAL|A11Y|RGPD` écrite en dur ratait.
- **32 références reprises** sur les nouveaux noms : index §3 et exemples du `docs/roadmap/README.md` (18), renvois croisés entre plans et suivis (10), chemins cités dans le présent fichier (3), docstring de `tests/test_responsive.py` (1, cosmétique).
- **Convention documentée dans `docs/roadmap/README.md`** : le §1.2, qui prescrivait `AAAA-MM-slug` et proscrivait le numéro séquentiel « parce que la date suffit à ordonner », est corrigé — la règle devient « jamais de numéro **seul** », et une ligne explique pourquoi le mois seul ne suffit pas dès la deuxième évolution du mois.

### Vérifications
- `python tools/check_docs.py` : `=== OK ===`, **0 lien relatif cassé**, 0 tableau mal formé, 4 tableaux de bord justes.
- `grep -rE '2026-10-[a-z]'` sur les fichiers versionnés : plus aucune forme ancienne.

---

## [Non publié] - 2026-10-30 · Percée SEO sur la tendance Google : « mot du jour », « indice », « synonyme »

### Ajouté
- **Pages hub générées côté serveur (`SEO-17`, `SEO-18`, évolution `docs/roadmap/2026-10-05-seo-tendance-mot-du-jour/`)** — la tendance Google Cémantix place « mot du jour » dans 5 des 10 requêtes en hausse (+30 %), « indice » aux 1ʳᵉ et 2ᵉ places et « synonyme » en hausse ; aucune page du site ne les ciblait :
  - Nouvelle fonction `build_mot_du_jour_page()` → `volumes/web/mot-du-jour/index.html`, titrée **« Mot du jour Cémantix du lundi 26 octobre 2026 : indices et solution »** : résumé du jour, table des dix indices mesurés (degrés Celsius + pour mille), solution derrière un `<details>` (le mot secret n'apparaît qu'une fois dans le document), FAQ `FAQPage` de 4 questions et archives récentes. Publiée **même sur historique vide** (état d'attente qui maille vers les archives), `priority 0.95` / `changefreq daily` dans le sitemap.
  - Nouvelle fonction `build_methode_page()` → `volumes/web/methode/index.html`, **« Indice Cémantix : lire le thermomètre, les scores et les synonymes »** : guide de 1 000 mots (paliers du thermomètre, pour mille, synonymes / antonymes / champs lexicaux) avec `HowTo` de 5 étapes et `FAQPage` de 4 questions, chaque étape structurée étant aussi lisible en clair. `priority 0.9` / `changefreq monthly`.
  - Les deux pages sont rendues avec le gabarit `render_page()` des archives (**zéro JavaScript**, style injecté), écrites en atomique, **ignorées par git** comme `/puzzles/` et `sitemap.xml`, et recréées par `ensure_seo_published()` au démarrage des conteneurs.
- **Suite de tests `tests/test_seo_hubs.py` (22 tests)** : contrat de titre et de `<h1>` des hubs, table des indices lisible sans JavaScript, absence du leurre `••••••••`, longueur et occurrences du guide, cohérence **accordéon ↔ `FAQPage`/`HowTo` JSON-LD mot pour mot**, unicité d'un `<h1>` par page applicative, et **maillage croisé** de chaque page vers les hubs.

### Modifié & Optimisé
- **Hub `/puzzles/` recentré sur le cluster dominant (`SEO-19`)** : titre « Cémantix du jour : mot du jour, indices et solutions par date », `<h1>` « Archives Cémantix du jour : le mot du jour, ses indices et sa solution », et nouvelles ancres internes via `archive_anchor()` — « Indices et solution du Cémantix du lundi 26 octobre 2026 ». Le titre « Solution Cémantix du <date> » (`SEO-13`) reste la spécialité des pages datées, le cluster « solution » n'étant que dernier de la tendance (+8 %).
- **Un `<h1>` descriptif par page (`SEO-20`)** : la marque « Cémantix Solver », répétée à l'identique dans le `<h1>` des quatre vues, devient un `<span class="brand-title">` (rendu identique via le sélecteur `.brand-text .brand-title`) ; chaque page reçoit un `<h1 class="page-heading">` unique — accueil « Cémantix du jour : indices, mot du jour et solution », `/play/` « Jouer à Cémantix en ligne : mode illimité et défi du jour », `/battle/` « Cémantix Battle : jouez contre l'IA en duel tour par tour », `/multi/` « Cémantix multijoueur : duel 1v1 entre amis au tour par tour » — suivi d'une `p.page-intro` qui maille vers les hubs.
- **FAQ et libellés d'accueil alignés sur la tendance (`SEO-21`)** : `<title>`, Open Graph et Twitter recentrés sur « Mot du Jour », trois questions ajoutées à la FAQ (5 → **8 questions**, texte identique en accordéon et en JSON-LD) sur le mot du jour, la lecture des indices et les synonymes.
- **Maillage interne croisé** : archives → hubs, hubs → archives et jeu, accueil → hubs via le pré-rendu quotidien (`resume-title`, `resume-link`) ; `llms.txt` déclare les deux nouvelles pages aux agents IA et oriente les questions de méthode vers `/methode/`.
- **CSS et bundles régénérés** : règles `.brand-text .brand-title`, `.page-heading` et `.page-intro` dans `volumes/web/css/layout.css` (variante `clamp()` sous 768 px), bundles `css/dist/*.css` et `<style id="critical-css">` des quatre pages reconstruits par `tools/build_css_bundles.py`.
- **Audit élargi (`tools/check_seo.py`)** : le contrôle audite désormais les gabarits hub **rendus en mémoire** (titre, description, canonical, Open Graph, JSON-LD, `<h1>`, absence du leurre) — ces pages n'étant jamais versionnées, seul un rendu protège la CI ; l'audit s'annonce et s'efface proprement (`[i] Pages générées non auditées`) quand les dépendances ne sont pas installées.

### Vérifications
- `tests/test_seo_archives.py` (17) + `tests/test_seo_hubs.py` (22) + `tests/test_docs_agent.py` (7) : **46 tests verts**.
- `python tools/check_seo.py` : `[OK]` sur 4 pages principales + `[OK]` sur les pages hub + `[OK]` audit agentique ; `python tools/check_docs.py` : `=== OK ===` ; `python tools/build_css_bundles.py --check` : 6 bundles et 4 CSS critiques à jour.
- Un `<h1>` par page et quatre `<h1>` uniques sur les pages applicatives ; `/mot-du-jour/` et `/methode/` présentes dans `sitemap.xml` et dans `llms.txt`.

### Limite
Une tendance Google ne donne que des variations relatives, sans volume absolu ni difficulté SERP. Le pari éditorial — viser les **formes combinées** (`mot du jour cemantix`, `mot cemantix du jour`) et le contenu **informationnel** (`indice cemantix`, `synonyme`) plutôt que `mot du jour` sec — se valide par la Search Console, 4 à 8 semaines après mise en ligne.

---

## [Non publié] - 2026-10-30 · Quick Win SEO : « Solution Cémantix du lundi 26 octobre 2026 »

### Ajouté
- **Libellé d'archive orienté mot-clé (`SEO-13`, `SEO-14`, évolution `docs/roadmap/2026-10-04-seo-titres-archives/`)** :
  - Nouvelle constante `ARCHIVE_TITLE_PREFIX` et nouvelle fonction `archive_title()` dans `src/services/seo.py` : chaque page `/puzzles/AAAA-MM-JJ/` est désormais titrée **« Solution Cémantix du lundi 26 octobre 2026 »** (date française longue, 42 caractères contre 85 auparavant) et non plus « Cémantix du … : indices, solution et trajectoire du solveur IA ».
  - Le même libellé porte le `<title>`, le `<h1>`, `og:title`, `twitter:title`, le `headline` JSON-LD et la `meta description`, qui **commence** par le mot-clé puis enchaîne sur le mot secret, les mots les plus proches, le nombre de coups, la méthode et le numéro de puzzle (≤ 175 caractères).
  - Index `/puzzles/` (`SEO-14`) : titre « Solution Cémantix : archives de tous les puzzles résolus par l'IA », `<h1>` aligné, `name` du `CollectionPage` JSON-LD et **textes d'ancre** reprenant le titre complet de chaque archive — plus de date nue dans le maillage interne. Pagination, URLs et `rel="prev"/"next"` inchangés (aucune redirection à prévoir).
- **Suite de tests `tests/test_seo_archives.py` (15 tests)** : contrat du titre (date française, absence de date ISO, longueur SERP), propagation `<title>`/`<h1>`/Open Graph/JSON-LD/fil d'Ariane, `noindex` conservé sur les archives non résolues, ancres de l'index, et **contrat ISO du sitemap**.

### Modifié & Optimisé
- **Fil d'Ariane des archives en français** : le dernier maillon, visible et dans le `BreadcrumbList` JSON-LD, affiche « lundi 26 octobre 2026 » au lieu de `2026-10-26` ; `datePublished` et l'URL restent en ISO, seuls formats valides.
- **Contrat `sitemap.xml` verrouillé (`SEO-15`)** : le générateur reste volontairement inchangé — `<loc>` en `/puzzles/AAAA-MM-JJ/` et `<lastmod>` W3C/ISO, seuls formats acceptés par le protocole sitemaps.org. La date en français long vit dans les libellés de la page et de l'index ; un test échoue dès qu'une chaîne française (« octobre », « Solution Cémantix ») apparaît dans le XML.
- **Découvrabilité pour agents IA (`SEO-16`)** : le bloc `AGENT-DYNAMIC` de `llms.txt` et `agent-skills.md` publie l'archive la plus récente sous son titre complet, la date ISO entre contre-gouttières et le motif « Solution Cémantix du <date en français long> » à citer ; la compétence `dated-archive` de `.well-known/agent-card.json` décrit ce motif (tag `solution`, exemple « Quelle est la solution du Cémantix du 26 octobre 2026 ? ») ; le catalogue ARD gagne la requête représentative « Quelle est la solution du Cémantix du lundi 26 octobre 2026 ? » ; `llms.md` documente le contrat titre français / URL ISO et se débarrasse d'un exemple d'URL daté figé.
- **Manifestes versionnés régénérés** : `volumes/web/.well-known/{ai-catalog,ard,agent-card}.json`, `llms.txt`, `llms.md` et `agent-skills.md` régénérés par `publish_ard_manifests()` et `refresh_agent_docs()`, et vérifiés identiques à leur générateur.

### Vérifications
- `tests/test_seo_archives.py` : **15 tests verts** ; suite conjointe avec `tests/test_docs_agent.py` : **22 tests verts**.
- `python tools/check_seo.py` : `[OK] Audit SEO reussi sur 4 pages principales` + `[OK] Audit agentique reussi` ; `python tools/check_docs.py` : `=== OK ===`.
- `grep -c "octobre" volumes/web/sitemap.xml` → `0` ; `<loc>` d'archives toujours en `/puzzles/AAAA-MM-JJ/`.

---

## [Non publié] - 2026-10-29 · Refonte Responsive Mobile, PageSpeed 100/100 & Résilience SEO/ARD

### Ajouté
- **Génération automatique et atomique de `sitemap.xml` et `.well-known/` au démarrage des conteneurs** :
  - Nouvelles fonctions `ensure_seo_published()` et `publish_ard_manifests()` dans `src/services/seo.py`, invoquées automatiquement au démarrage de `cemantix_web` (`start_api_server()`) et en secours au démarrage de `cemantix_worker` (`run_daemon_loop()`), garantissant la recréation immédiate de `volumes/web/sitemap.xml`, `volumes/web/.well-known/{ai-catalog,ard,agent-card}.json` et `/puzzles/` après un `git pull`, une suppression accidentelle ou sur une base vierge.
  - Écriture atomique multi-conteneurs (`_write_file` via fichier temporaire aléatoire + `chmod 0644` + `replace`) éliminant tout risque de troncature ou d'erreur `EACCES` entre `cemantix_web` et `cemantix_worker`.
  - Exécution garantie de la publication SEO dans `export_web_data()` (`finally`) même en cas d'erreur de permission sur `cemantix_data/data.json`, couverte par `tests/test_seo_startup.py`.
- **Feuille de route & Suite de tests Responsive Mobile (`docs/roadmap/2026-10-03-responsive-mobile/`, `tests/test_responsive.py`)** :
  - 12 chantiers (`RESP-01` à `RESP-12`) qualifiés sur GP8 Pro (`412×915`), Gboard ouvert (`412×420`), iPhone (`393×852`) et Compact (`360×740`) avec sanctuarisation stricte de l'affichage Bureau (`> 768px`).

### Corrigé & Optimisé
- **Disposition Responsive Smartphone (`RESP-01` à `RESP-12`)** :
  - Verrouillage du débordement horizontal (`overflow-x: clip`, `min-width: 0`), en-tête condensé sur 1 ligne et cibles tactiles portées à `44×44px` minimum.
  - Barre `.nav-tabs` défilante sans rognage gauche (`justify-content: flex-start`) avec centrage automatique de l'onglet actif (`initMobileNavScroll()`).
  - Empilement vertical de la zone de saisie solo/battle/multi (`font-size: 16px` sans zoom forcé), hauteur dynamique des listes (`max-height: min(260px, 38dvh)`) et mode compact à l'ouverture du clavier virtuel (`visualViewport`).
  - Grille adaptative `2 + 1` des métriques du mot du jour, pastilles thermiques empilées sur 2 lignes, sous-onglets du lobby multijoueur sans chevauchement, scoreboard Battle symétrique sur 3 colonnes et prise en compte de `env(safe-area-inset-bottom)`.
- **Optimisation PageSpeed Insights Mobile & Conformité ARD (Lighthouse 13.5+)** :
  - Suppression de l'ajustement forcé de mise en page (`103 ms` sur `/js/theme.js:63:13`) et de la tâche longue associée : écriture conditionnelle de `data-theme`, court-circuit immédiat sur le premier onglet actif et lecture géométrique différée dans `requestAnimationFrame`.
  - Élimination des requêtes CSS bloquantes (`530 ms` d'économie LCP/FCP mobile, chaîne critique réduite à 1 saut) : injection du CSS critique minifié en `<style id="critical-css">` dans les 4 pages principales et dans `src/services/seo.py` (`/puzzles/*`), couplée au chargement différé de `css/dist/modal.css` (`media="print"` + activation JS respectant `script-src 'self'`).
  - Mise en conformité du schéma ARD (`volumes/web/.well-known/ai-catalog.json` avec objet `host.displayName` valide + miroir `volumes/web/.well-known/ard.json` pour ARD v0.91+) faisant passer l'audit « Navigation agentique » de `3/4` à `4/4`.

---

## [Non publié] - 2026-10-27 · Roadmap Sécurité, SEO, Performance & Qualité

### Ajouté
- **Tests unitaires exhaustifs (QUAL-01)** : Suite de **81 tests unitaires** automatisés avec repli SQLite pur (`tests/`), couvrant l'architecture, le serveur HTTP, les fuites de connexions, la sanitisation des entrées et la logique multi.
- **CI GitHub Actions & Lighthouse (QUAL-02, SEO-12)** : Workflow multi-jobs `.github/workflows/ci.yml` intégrant tests bloquants, vérification documentaire automatique (`tools/check_docs.py`), lint statique `ruff`, audit de dépendances `pip-audit` et contrôle Lighthouse CI.
- **Rendu front mutualisé (QUAL-08)** : Module `volumes/web/js/render.js` factorisant la génération HTML et l'injection DOM des tuiles de coups entre le mode multijoueur (`multi.js`) et le mode battle (`battle.js`), avec cache de comparaison anti-scintillement.
- **Contrôle d'intégrité des téléchargements (SEC-11)** : Validation structurelle et empreinte SHA-256 (`W2V_SHA256`, `LEXIQUE_SHA256`) lors de la récupération des modèles et lexiques.
- **Garde-fous de configuration (QUAL-04, QUAL-16)** : Fail-fast au démarrage interdisant le mot de passe d'exemple en environnement non-dev, et syntaxe stricte `${VAR:?erreur}` dans `docker-compose.yml` empêchant toute substitution silencieuse vide.
- **Observabilité et conformité RGPD (SEC-09, RGPD-01, RGPD-02, RGPD-03)** : Anonymisation des adresses IP en sous-réseaux `/24` (IPv4) et `/48` (IPv6) avant journalisation, traçage explicite des statuts d'erreur HTTP 4xx/429/5xx, exclusion des pseudonymes des logs d'accès, et cadrage du cookie de révélation comme strictement nécessaire.
- **Extraction des stopwords et templates de prompt (QUAL-09)** : Fichiers dédiés `src/engine/english_stopwords.txt` et `src/engine/prompt_template.txt` découplés de `src/config.py`.

### Modifié & Optimisé
- **Performance base de données & Pool de connexions (PERF-06, PERF-06b, PERF-05)** :
  - Fin de la fuite de connexions PostgreSQL via un pool réutilisable thread-safe borné (`max_size=8`) dans `src/db/connection.py`.
  - Contrôle `SELECT 1` conditionnel espacé de 30 s au lieu de systématique par requête.
  - Persistance ciblée $O(1)$ par coup joué (`save_solo_session`, `save_multi_session`) dans `GameManager` éliminant la réécriture complète de toutes les sessions.
- **Cache mémoire & ETag sur `/api/daily` (PERF-01, PERF-02, PERF-03)** : Cache TTL 15 s avec verrou, réponse `304 Not Modified` via ETag MD5, suppression du paramètre cache-buster `?t=`, et polling conditionnel suspendu lorsque l'onglet est masqué.
- **Sécurité des clés & sessions (SEC-05, SEC-05b)** : Clés de session portées à 96-128 bits d'entropie (`secrets.token_hex(12)`), hachage cryptographique HMAC-SHA256 des clés stockées en base (`multi_rooms`) et rétrocompatibilité transparente.
- **Sécurité des conteneurs (SEC-13, QUAL-13)** : Exécution de l'image sous utilisateur dédié non-root `cemantix` (UID 1000), durcissement Compose (`no-new-privileges: true`, `cap_drop: [ALL]`), et `.dockerignore` réduisant le contexte de build de 2,7 Go à < 800 ko.
- **SEO & AEO (SEO-01b, SEO-06, SEO-07, SEO-11)** : Balise anti thin-content conditionnelle sur les archives non résolues, métadonnées JSON-LD enrichies (auteur Cyril Randon, `sameAs`, `isPartOf`), cartes Open Graph 1200x630 dédiées, et publication d'une spécification statique `openapi.json` liée à `.well-known/ai-catalog.json`.
- **Accessibilité, Contraste WCAG & Pré-rendu SEO (A11Y-04, SEO-01)** : Rehaussement des ratios de contraste sur tous les éléments du pied de page et de la section Daily (`#resume-du-jour`, sous-titres, gras, liens avec soulignement explicite, boutons `.btn-ghost`), harmonisation du balisage du footer sur les 4 pages (`index.html`, `play/`, `battle/`, `multi/`), et fiabilisation de l'idempotence du remplacement de balises `data-seo` dans `src/services/seo.py` éliminant tout risque de duplication de texte lors de la publication quotidienne.

---

## [Non publié] - 2026-10-26 · Architecture & Persistance

### Ajouté
- **Architecture 3-Tiers Découplée (PostgreSQL 16 + Worker RAG + API Web)** :
  - Découpage de l'application monolithique en 3 conteneurs autonomes et durcis (`cemantix_db`, `cemantix_worker`, `cemantix_web`).
  - Persistance relationnelle ACID dans PostgreSQL (`daily_puzzles`, `multi_rooms`, `solo_sessions`) avec schéma déclaratif `database/init.sql`.
  - Couche d'accès aux données thread-safe dans `src/db/` (`connection.py`, `daily.py`, `multi.py`, `solo.py`) avec gestionnaire de transactions et repli automatique transparent sur SQLite pour les tests unitaires et le dev local.
  - Découplage mémoire haute performance : le conteneur web partage la mémoire physique des vecteurs NumPy (`np.memmap`) en lecture seule (`:ro`) et exclut le chargement lourd de ChromaDB, assurant un démarrage instantané en 0.1s et une empreinte RAM totale < 200 Mo sur l'hôte.
  - Élimination des race conditions sur les parties multijoueurs grâce à la synchronisation relationnelle immédiate en base de données.
  - Script de migration d'historique `scripts/migrate_json_to_pg.py` pour importer les puzzles quotidiens archivés vers PostgreSQL.
  - Fichier de configuration sécurisé `.env.example` et externalisation complète des identifiants et variables d'environnement hors de Git.

## [Non publié] - 2026-10-26 · Sécurité

### Corrigé
- **Fuite du mot secret du jour (anti-spoiler contournable)** :
  - `GET /api/daily` acceptait le paramètre public `?reveal=true` et renvoyait la solution à n'importe quel `curl`, `prefetch` ou crawler : le bouclier anti-spoiler n'était que visuel. La solution est désormais **absente de toute réponse `GET`** ; sa consultation passe par la nouvelle route `POST /api/daily/reveal`, qui exige une action volontaire.
  - `_scrub_secret()` masque aussi le mot cible dans `trajectory`, `top_guesses` et l'entrée du jour de `history` : jusqu'ici la solution restait intégralement lisible dans ces tableaux annexes alors que le champ `word` était vidé.
  - `dashboard.js` n'exploite plus `current.word` (source de la fuite côté client) et appelle la route POST pour révéler ou copier le mot.
  - Le mot révélé n'est plus effacé par le polling de 30 s, l'API ne le renvoyant plus.
- **Exposition de `data.json` dans le webroot** : le fichier, qui contient l'historique complet des solutions, était documenté comme devant être publié dans `./volumes/web` et se récupérait par un simple `curl https://…/data.json`. `export_web_data()` refuse désormais toute cible située dans le webroot ou l'un de ses sous-répertoires, et la documentation corrige l'emplacement réel (`./cemantix_data`).
- **Serviteur HTTP non durci** :
  - Corps de requête illimité : un `Content-Length` mensonge forçait l'allocation mémoire. Le corps est plafonné à `API_MAX_BODY_BYTES` (32 ko) et **validé avant tout traitement** (le test du gestionnaire était passé avant la lecture) ; au-delà : `413`.
  - CORS ouvert par `Access-Control-Allow-Origin: *` (et `Authorization` déclaré) : remplacé par une liste blanche d'origine (`API_ALLOWED_ORIGIN`) avec `Vary: Origin`.
  - Absence de limitation de débit : nouveau module `src/api/ratelimit.py` (seau à jetons par IP via `X-Forwarded-For`, thread-safe, mémoire bornée, `429` + `retry_after`), `/api/health` en étant exempté pour ne pas casser le `healthcheck` Docker.
  - Un thread créé par connexion sans plafond : `BoundedHTTPServer` limite les workers (`API_MAX_WORKERS`, 64) et renvoie un `503` propre.
  - En-têtes de sécurité ajoutés à chaque réponse : `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store` ; version Python retirée de l'en-tête `Server` ; timeout socket de 10 s ; écriture tolérante aux déconnexions navigateur.
- **XSS dans tous les rendus dynamiques** : aucune fonction d'échappement n'existait ; mots, dates, numéros de puzzle, identifiants de salon et pseudonymes d'adversaire étaient injectés bruts dans `innerHTML`.
  - Introduction de `escapeHtml()` (et `safeNumber()`) dans `js/utils.js`, appliqués aux indices, à l'historique, aux listes de coups, à la trajectoire, aux cartes de duel et aux cibles révélées en multijoueur.
  - Suppression des gestionnaires construits par concaténation — `onclick="copyToClipboard('${mot}')"`, `onclick="window.multiResumeGame('${room}', '${clé}')"` — qui permettaient de fermer la chaîne JS avec une simple apostrophe ; remplacés par des attributs `data-copy` / `data-resume-room` / `data-delete-room` et une délégation d'événements enregistrée une seule fois.
- **Clé de salon laissée dans l'URL** : le lien d'invitation `/multi/?r=…&k=…` conservait la clé du joueur dans la barre d'adresse — donc dans l'historique du navigateur, le champ d'URL et les captures d'écran — et restait cliquable des heures plus tard, soit une prise de contrôle du duel sur un ordinateur partagé. Le polling passait en outre la clé en query string `GET`, c'est-à-dire dans la ligne de requête transmise au proxy. `stripKeyFromUrl()` retire la clé dès le chargement (avant même la requête de connexion) et à chaque changement d'état, ne laissant que le code de salon, qui n'autorise aucune action ; les deux points de polling basculent sur `POST /api/multi/status` (charge utile identique, dans le corps) ; `handle_multi_get` ne sert plus aucune route, la voie GET étant fermée avec un message indiquant le POST équivalent. Le lien de partage conserve sa clé — c'est la fonctionnalité — mais elle n'est lue qu'une fois.
- **Surface globale laissée par les `onclick` supprimés** : les quatre fonctions que les gestionnaires inline appelaient restaient publiées sur `window` (`copyToClipboard`, `showConfirmDialog`, `multiResumeGame`, `multiDeleteGame`) alors qu'elles n'avaient plus aucun appelant global — vérifié : zéro `onclick=` dans les quatre pages, zéro appel `window.<ces noms>` dans tout `volumes/web/`, tous les appels passant par `import` ES modules ou par la délégation `data-copy`. Rendues locales à leur module : une CSP `script-src 'self'` stricte reste tenable même si un `onclick` inline réapparaissait, et l'API interne du jeu n'est plus atteignable depuis la console.
- **Codes du multijoueur énumérables** : `room_id` et clés `J1-` / `J2-` n'avaient que 4 chiffres hexadécimaux (65 536 valeurs) avec des salons actifs 7 jours, ce qui permettait un balayage systématique pour retomber sur une partie ouverte. Portés à 8 chiffres hexadécimaux (`uuid.uuid4`, 4,3 milliards de valeurs, facteur ×65 536) ; comparaison toujours par égalité de chaîne, les parties en cours restent utilisables.
- **Sessions inactives jamais purgées** : le TTL existait mais `_cleanup_stale()` n'était déclenché qu'à la **création** d'une partie — un serveur qui tourne des semaines sans nouvelle partie ne libérait rien, et la mémoire croissait avec le volume de parties jouées. Pire, `_load_sessions()` écartait les entrées périmées **sans jamais réécrire le fichier** : `web_sessions.json` conservait à vie toutes les parties depuis la création du volume, le filtrage étant rejoué à chaque démarrage.
  - `_maybe_cleanup()` cadence la purge au plus une fois par 5 minutes sur les points d'accès chauds (`get_session`, `get_multiplayer`) : un simple comparateur d'horodatage le plus souvent, sans thread ni cycle de vie supplémentaire.
  - TTL distincts assumés : 2 h pour une partie solo ou battle abandonnée, 7 jours pour un duel dont les deux joueurs se reconnectent souvent le lendemain.
  - `_compact_session_file()` réécrit le fichier sans les entrées écartées, en écriture atomique comme `_save_sessions`, pour qu'un arrêt en cours de compactage ne laisse pas un JSON tronqué.
  - La purge s'exécute sous `self.lock`, qui est un `Lock` simple **non réentrant** : le reprendre dans `_cleanup_stale()` aurait bloqué le thread.

### Ajouté
- **`.gitignore`** : le dépôt n'en avait aucun ; `data.json`, les fichiers de sessions et les `__pycache__` produits à l'exécution pouvaient être commités par erreur. Vérifié : aucun fichier actuellement suivi (`cemantix_data/lexique_fr.txt`) n'est masqué par ces règles.
- **Documentation de sécurité** : nouvelle section « 🔐 Sécurité » (chemin d'accès à la solution, tableau des protections du serveur avec leurs variables, échappement XSS, entropie des codes de salon, trois commandes `curl` de vérification après déploiement) ; le `Caddyfile` documenté gagne une `Content-Security-Policy` (`script-src 'self'`, le site n'emploie aucune ressource externe), une CSP durcie sur `/puzzles/*`, HSTS, `Permissions-Policy` et `Cross-Origin-Opener-Policy`, plus un bloc `@intercepted` renvoyant `404` sur `data.json`, les historiques, les sessions, `.env`, `.git`, `*.py`, `*.pyc`, `*.log` et `*.bin`.
- Variables d'environnement documentées : `API_ALLOWED_ORIGIN`, `API_MAX_BODY_BYTES`, `API_MAX_WORKERS`, `API_SOCKET_TIMEOUT`, `DASHBOARD_DATA_FILE`.
- **`Caddyfile` versionné à la racine du dépôt** : la configuration du serveur web (CSP, en-têtes de sécurité, politique de cache, bloc `@intercepted`) n'existait que en prose dans le README, où elle avait déjà divergé du code. Le fichier fait désormais foi ; le README y renvoie avec la commande de rechargement à chaud.
- **Outils de contrôle sans dépendance** : `tools/check_og_image.py` compare le poids et les dimensions réels de `og-image.jpg` aux balises `og:image` (code de sortie `1` si hors norme, exploitable en CI) et `tools/check_js_balance.py` vérifie l'équilibre des délimiteurs JavaScript en l'absence de `node`.

### Refactorisé
- **Journalisation des requêtes** : `log_message()` était réduit à `pass`, ce qui rendait tout abus invisible ; les requêtes sont désormais tracées de façon minimale avec l'IP cliente, sans le débit du flux d'origine.

## [Non publié] - 2026-10-26 · Performance

### Corrigé
- **Politique de cache incohérente avec la règle « no-cache, pas de `?v=` »** : le `max-age=3600` posé sur `@html` et les `max-age` suggérés pour les archives contredisaient la revalidation par ETag ; tout ce qui change repasse en `no-cache, must-revalidate`, seules les polices gardent un `max-age` d'un an.
- **Pages d'archives sans `Cache-Control`** : le sélecteur `@html path *.html` ne matche pas une URL comme `/puzzles/2026-10-26/` (servie par `try_files`, sans extension) ; un bloc `@pages` couvre désormais ces URLs, ainsi que `sitemap.xml`, `robots.txt`, `llms.md` et `.well-known/*`.
- **`X-Frame-Options` contradictoire** : le README documentait `SAMEORIGIN` alors que le serveur envoie `DENY` ; aligné sur `DENY`, avec `frame-ancestors 'none'` dans les deux CSP qui autorisaient pourtant l'encadrement par le site lui-même.
- **Polling de la salle d'attente multijoueur** : un `setInterval` fixe de 2 s ignorait l'onglet masqué (~1 800 requêtes/heure d'onglet ouvert). Le rythme devient adaptatif (2 s → 10 s, réinitialisé à chaque changement d'état), aucune requête n'est émise quand l'onglet est caché, et un `visibilitychange` resonde immédiatement au retour. Le `setInterval` a été remplacé par une chaîne de `setTimeout` : `stopPolling()` appelait `clearTimeout`, qui ne stoppe pas un `setInterval` — le polling continuait donc de tourner après le retour au lobby.
- **Métadonnées d'image de partage incomplètes** : `play/` déclarait `og:image` sans dimensions ni texte alternatif, et aucune page n'avait de `twitter:image:alt` ; les quatre pages portent désormais `og:image:width/height/alt` et `twitter:image:alt`.
- **Compte à rebours coûteux et faux à minuit** : `new Intl.DateTimeFormat(...)` — l'objet le plus onéreux de l'API Intl — était reconstruit dans le tick, soit 86 400 allocations par jour et par onglet pour une configuration invariable. Le formatter est hoisté hors de la boucle, le DOM n'est écrit que si la valeur change, le tick est suspendu onglet masqué. Corrige au passage l'affichage « 24:00:00 » pendant la première seconde du jour (`currentSeconds == 0` donnait un reste de 86 400 s) ; vérifié sur les 86 400 secondes de la journée, plus aucune valeur supérieure à 23.
- **Re-rendu inutile de l'historique** : la recherche reconstruisait le tableau à chaque frappe (débounced à 150 ms) et le polling de 30 s réinjectait un `innerHTML` identique alors que l'historique ne change qu'une fois par jour (comparaison du gabarit avant écriture, ce qui préserve aussi focus et défilement). Sans effet sur l'anti-spoiler, porté par la classe `is-hidden` basculée en direct.
- **Pollings actifs en arrière-plan** : le tableau de bord (30 s) et la salle d'attente (2 s) continuaient d'émettre des requêtes onglet masqué ; les timers sont suspendus à la masque et relancés avec une resynchronisation immédiate à la reprise.
- **Poids des feuilles et des modules par page** : chaque page chargeait 5 à 6 feuilles CSS et un point d'entrée JavaScript important statiquement des modules inutilisés.
  - `tools/build_css_bundles.py` génère une feuille par page dans `css/dist/` (index 48 054 o/5 requêtes → 37 586 o/1, play 43 453/5 → 33 829/1, battle 60 844/6 → 46 489/1, multi 59 658/6 → 45 124/1). Le gain porte sur le **nombre de requêtes**, pas sur le poids : chaque page ne chargeait déjà que le CSS utile, il n'y avait pas de CSS mort. Le mode `--check` échoue si les bundles sont périmés. La minification se limite aux commentaires et aux blancs ; validée par comparaison canonique des règles, imbrication `@media`/`@keyframes` comprise : **519 règles sur 8 fichiers, 0 perdue**.
  - `js/app.js` charge désormais `dashboard.js` et `game.js` en `import()` dynamique : un `import` statique fait télécharger **et** évaluer le module même quand la branche `if` ne s'exécute pas — depuis `/play/`, `dashboard.js` + `trajectory.js` + `countdown.js` coûtaient ~27 ko sur les ~93 ko du graphe statique d'import (29 %).
  - Les sources `css/*.css` sont conservées : `src/services/seo.py` lit `variables.css` pour injecter les tokens dans les pages d'archives.
  - Branche Battle supprimée de `app.js` : morte, puisque `/battle/` charge `js/battle.js` directement et que ce module s'auto-initialise.
- **Faux positifs de `tools/check_js_balance.py`** : l'outil échouait (code de sortie `1`) sur 7 des 9 modules du projet, ce qui le rendait inexploitable en CI. Trois ambiguïtés du JavaScript étaient mal tranchées — la regex confondue avec une division (dans `.replace(/"/g, "&quot;")`, le guillemet ouvrait une chaîne et tout le reste du fichier était mal lu), le `/` de `</span>` pris pour une regex à l'intérieur d'un template literal, et une interpolation `${…}` consommée par une boucle interne qui perdait la position de fermeture du gabarit. La lecture devient une machine à états plate (une seule position de cours, une pile de gabarits pour les interpolations imbriqués, test de contexte pour regex/division) : **9/9 modules acceptés, 13/13 cas valides, 5/6 fautes réelles détectées**. Le cas non couvert — un gabarit jamais fermé — est assumé et documenté.
- **Taille annoncée à tort dans `app.js`** : le commentaire indiquait « 67 ko du point d'entrée », valeur sans correspondance mesurable ; le graphe statique pesait 94 794 o (~93 ko), dont 27 794 o (~27 ko, 29 %) inutilisés depuis `/play/`.

### Optimisé
- **Rendu différé des blocs bas de page** : le résumé du jour, le guide et la FAQ constituent le bas du tableau de bord, jamais visible à l'arrivée, mais payaient une mise en page et une peinture à chaque chargement et à chaque changement de thème. `content-visibility: auto` saute ce travail tant que le bloc approche du viewport. `contain-intrinsic-size` porte le mot-clé `auto`, qui mémorise la hauteur réelle après le premier rendu — sans lui la barre de défilement sauterait à chaque passage. Un garde-fou `@media print` remet `content-visibility: visible` pour que rien ne reste non rendu à l'impression ; les navigateurs sans support ignorent les deux propriétés et affichent normalement.

## [Non publié] - 2026-10-26 · SEO

### Ajouté
- **Archives Quotidiennes Indexables & Sitemap Dynamique (Référencement de la longue traîne)** :
  - Nouveau sous-package `src/services/seo.py` qui convertit l'historique des résolutions en **contenu indexable rendu côté serveur**, là où le tableau de bord ne publiait son contenu qu'après exécution de JavaScript.
  - **Pages par date `/puzzles/AAAA-MM-JJ/`** : titre et meta description datés (« Cémantix du lundi 26 octobre 2026 : indices, solution et trajectoire du solveur IA »), URL canonique, Open Graph et Twitter Card, tableau des 10 mots les plus proches (score en °C et similarité en ‰) et solution placée derrière un bloc `<details>` dépliable.
  - **Données structurées par archive** : bloc JSON-LD `@graph` combinant un `Article` (avec `datePublished` et `dateModified` réels) et un `BreadcrumbList` à trois niveaux.
  - **Pages auto-suffisantes** : les tokens de style sont extraits de `css/variables.css` et injectés dans une balise `<style>` unique, donc aucun JavaScript requis et aucune requête CSS supplémentaire (page complète ≈ 13 ko).
  - **Index paginé `/puzzles/`** (60 archives par page) avec `rel="prev"` / `rel="next"`, schéma `CollectionPage` et navigation bornée sur les pages extrêmes.
  - **`sitemap.xml` régénéré** avec le `lastmod` réel de chaque page, l'URL `/puzzles/`, les pages de pagination et un passage de `play/`, `battle/` et `multi/` en `changefreq` `weekly` (le fichier versionné était figé au `2026-10-25`).
  - **Pré-rendu du tableau de bord** : nouvelle section « Résumé du jour » dans `index.html`, balisée par les commentaires `SEO-PRERENDER` et l'attribut `data-seo`, remplie par `prerender_dashboard()`. Le remplacement s'effectue de l'intérieur vers l'extérieur (index préservés), reste **idempotent** et retombe sur un texte neutre si l'historique est vide. Le mot secret n'y est **jamais** écrit : seuls la date, le numéro de puzzle, les coups, la durée et les mots d'approche sont publiés.
  - **Option en ligne de commande `--publish-seo`** pour régénérer uniquement les archives, l'index et le sitemap ; la publication est aussi déclenchée par `--export-web` et par le démon après chaque résolution de minuit, en non bloquant (une erreur de SEO ne casse plus l'export de `data.json`).
  - **Outil `tools/generate_icons.py`** produisant `apple-touch-icon.png` (180×180) et `icon-512.png` avec la seule bibliothèque standard (encodage PNG par `zlib`), sans dépendance de traitement d'image.
- **Installabilité & Découverte** :
  - Manifeste `manifest.webmanifest` (PWA `standalone`, `shortcuts` Solo et Archives, trois icônes) avec `apple-touch-icon` et icônes SVG `any` / `maskable`.
  - Onglet « Archives » ajouté à la navigation des quatre pages pour le maillage interne vers `/puzzles/`.
  - `robots.txt` durci : `Disallow` sur `/api/`, `/data.json`, `/.well-known/` et les paramètres spoilants `?reveal=`, `?r=`, `?k=`.
  - `llms.txt` renommé en **`llms.md`** (extension du standard) et enrichi : format des URLs d'archives, contenu garanti sans JavaScript, endpoints API et mentions légales sur frWac, Lexique 3.83 et l'absence d'affiliation avec Certitudes.
  - Manifeste ARD **`.well-known/ai-catalog.json`** : suppression du doublon en racine, réorientation de l'entrée d'outillage vers `/api/health` (sans spoiler) et déclaration des pages d'archives en ressource `text/html`.
- **Donnée structurée `HowTo` sur l'accueil** : le guide exposait déjà une liste ordonnée de trois stratégies sans l'annoncer comme telle. Le nœud rejoint le `@graph` existant (`WebApplication`, `WebSite`, `FAQPage`) en répétant **mot pour mot** le texte visible — Google déclasse les données structurées qui contredisent la page. Vérifié : 3 étapes du schéma égales aux 3 éléments de la liste, JSON-LD valide sur les quatre pages. `aggregateRating` volontairement omis (aucun avis réel : sanction manuelle). À noter, Google a supprimé les résultats enrichis `HowTo` des SERP en août 2023 : le balisage reste lu par d'autres moteurs et par les assistants, sans promesse de bloc enrichi.

### Corrigé
- **Balises SEO obsolètes sur les quatre pages** : suppression de `<meta name="title">` (doublon de `<title>`) et de `<meta name="keywords">` (ignoré par Google).
- **`theme-color` incohérent en thème clair** : deux valeurs conditionnées par `prefers-color-scheme` (`#0d1117` sombre, `#f6f8fa` clair) remplacent la valeur unique figée.
- **Bloc de code cassé du README** : la commande de synchronisation manuelle était encapsulée dans un backtick suivi d'un caractère backspace (`\bash`) au lieu d'une barrière ` ```bash `.

### Refactorisé
- **Robustesse de la génération SEO** : échappement systématique via `html.escape`, rejet des dates mal formées et des puzzles non résolus, plafond de 45 000 URLs de sitemap et 500 pages d'index, et `</` échappé en `<\/` dans le JSON-LD pour ne jamais fermer prématurément le bloc.

### Documenté
- Nouvelle section « 🔎 SEO : Archives Quotidiennes Indexables & Sitemap » dans `README.md` : arborescence publiée, contenu d'une page d'archive, régénération via `--publish-seo`, politique de cache Caddy recommandée pour `/puzzles/*` et `/sitemap.xml`, génération des icônes et étapes de soumission Search Console.

## [Non publié] - 2026-10-25

### Corrigé

- **Accessibilité & Contraste des Couleurs (PageSpeed Insights WCAG AA)** :
  - Introduction du token de couleur `--accent-btn: #1668dc` offrant un ratio de contraste supérieur à 5,2:1 avec le texte blanc sur `.btn-primary`, `.nav-tab.active` et `.pill-btn.active`.
  - Optimisation des badges d'accent (`.badge-accent`) et de succès (`.badge-success` : « ✓ TROUVÉ ») avec opacités révisées et teintes vives (`#79b8ff`, `#56d364`), garantissant un ratio de contraste supérieur à 7,2:1 (WCAG AAA).
  - Éclaircissement du texte estompé `--text-dim` de `#6e7681` à `#9198a1` garantissant la conformité du timestamp du footer (`.footer-time`, ratio 6,4:1).
- **Support des Agents IA & Navigation Agentique (Lighthouse ARD)** :
  - Création du fichier standardisé `llms.txt` documentant l'architecture et les routes d'accès de la plateforme pour les LLM.
  - Ajout des manifestes de découverte `ai-catalog.json` et `.well-known/ai-catalog.json` conformes à la spécification Agentic Resource Discovery (ARD).

### Refactorisé
- **Gestion du Cache HTTP & Suppression des Paramètres de Version (`?v=...`)** :
  - Suppression complète de tous les suffixes de version manuels (`?v=XXXXXXXXX`) dans l'ensemble des pages HTML (`index.html`, `play/`, `battle/`, `multi/`) et des imports ES Modules JavaScript (`app.js`, `game.js`, `battle.js`, `multi.js`).
  - Déplacement de la politique de cache vers le serveur web Caddy / Nginx avec en-têtes `Cache-Control: "no-cache, must-revalidate"` et ETag automatique, garantissant la mise à jour immédiate des navigateurs à chaque `git pull` sans purge manuelle.
  - Documentation de la configuration Caddy de production recommandée dans `README.md`.
- **Refonte Architecturale Complète de `src/` en 5 Sous-Packages Découplés** :
  - Disparition totale des fichiers "en vrac" à la racine de `src/` au profit d'une organisation modulaire stricte par responsabilité, avec rétrocompatibilité totale à 100% via `src/__init__.py`.
  - **1. Cœur Algorithmique & RAG (`src/engine/`)** :
    - `vocab.py` : Gestion du lexique français (Lexique 3.83), normalisation des lemmes et vector store ChromaDB (modèle frWac 500d).
    - `clients.py` : Client officiel Cémantix avec contournement d'IPv6 / retry automatique et simulateur local `MockClient`.
    - `solvers.py` : Solveur géométrique RAG pur (régression Ridge vectorielle, reranking cosinus), solveur LLM assisté et bot de duel `RagDuelPlayer`.
    - `__init__.py` : Point d'entrée centralisant et ré-exportant les composants moteurs.
  - **2. Moteurs Métier & Gestion des Sessions (`src/game/`)** :
    - `solo.py` : Moteur de session Solo & Défi du Jour (`GameSession`).
    - `battle.py` : Moteur de duel tour par tour contre l'IA (`BattleSession`).
    - `multi.py` : Moteur de salon et tours Multijoueur 1v1 (`MultiplayerSession`).
    - `manager.py` : Gestionnaire centralisé d'état, persistance atomique sur disque et pools de difficulté (`GameManager`).
    - `common.py` : Utilitaires partagés (météo sémantique, chemins de persistance).
    - `__init__.py` : Ré-export unifié des sessions et du manager.
  - **3. Couche Exposition HTTP & Passerelle REST (`src/api/`)** :
    - `server.py` : Serveur HTTP multi-threadé (`ThreadingHTTPServer`), parsing JSON, gestion CORS et cycle de vie.
    - `routes/` : Contrôleurs REST hautement découplés par domaine d'activité :
      - `system.py` : Santé, métriques et données web (`/api/health`, `/api/daily`, `/api/dashboard`).
      - `solo.py` : Défi du Jour & Mode Illimité (`/api/game/*`).
      - `battle.py` : Duel contre l'IA RAG (`/api/battle/*`).
      - `multi.py` : Mode Multijoueur 1v1 en direct (`/api/multi/*`).
      - `__init__.py` : Point d'accès unifié des routes.
    - `__init__.py` : Point d'entrée du paquet avec rétrocompatibilité des imports.
  - **4. Interface Console & Menu Interactif (`src/cli/`)** :
    - `ui.py` : Rendu console ANSI Rich, jauges thermiques ASCII et tableaux de débriefing.
    - `menu.py` : Menu interactif textuel avec configuration dynamique des modes.
    - `modes.py` : Boucles d'exécution interactives en mode terminal (solo, duel, battle, benchmark).
    - `__init__.py` : Point d'entrée et exports des boucles CLI.
  - **5. Services d'Arrière-Plan & Synchronisation (`src/services/`)** :
    - `daemon.py` : Démon planificateur 24h/24 (veille et résolution automatique à 00h00 Paris, healthcheck, heartbeat).
    - `web.py` : Générateur et exportateur atomique du fichier `data.json` pour le serveur web Caddy/Nginx.
    - `__init__.py` : Point d'entrée et exports des services de synchronisation.
  - **Isolation et Robustesse des Tests Unitaires** :
    - Suite complète de 36 tests unitaires s'exécutant en 1.7s sous Docker (`OK`).
    - Ajout du drapeau `persist=False` garantissant que l'exécution des tests n'écrase jamais les sessions réelles sur disque.
    - Nettoyage automatique des salons expirés (404) dans le frontend web (`multi.js`).

### Ajouté
- **Mode Multijoueur 1v1 Tour par Tour (`/multi/`)** :
  - **Moteur de duel multijoueur asynchrone et en direct (`src/api.py`, `MultiplayerSession`)** :
    - Gestion de deux variantes de jeu :
      - **« Même Mot »** : Les deux joueurs cherchent le même mot cible. Suivi de la progression adverse en direct (température, jauge et pourmille) avec **filtrage anti-triche côté serveur** (les mots de l'adversaire sont strictement masqués `••••••••` tant que la partie est active, puis révélés au dénouement).
      - **« Mots Choisis »** : Chaque joueur choisit secrètement le mot que son adversaire doit deviner. Cibles distinctes et affichage intégral des mots joués en clair sans risque de divulgation.
    - **Système d'identification double et sans friction** :
      - Code de salon unique court (`DUEL-XXXX`).
      - Deux clés de sécurité privées par joueur (`J1-XXXX` pour l'hôte, `J2-XXXX` pour l'invité) garantissant l'authentification sans création de compte ni mot de passe.
      - **Double modalité d'accès** : partage par **lien direct 1-clic** (`/multi/?r=CODE&k=KEY`) pour un démarrage instantané, et **formulaire de saisie manuelle** pour rejoindre ou changer d'appareil.
      - Mémorisation locale dans le navigateur (`localStorage`) pour reprendre un duel actif en 1 clic.
    - **Persistance robuste sur disque** : sauvegarde atomique dans `cemantix_data/multi_sessions.json` avec conservation prolongée (TTL 7 jours), résistant aux redémarrages de conteneurs Docker.
    - **Indices & forfaits** : jusqu'à 3 indices gradués par joueur (consommant 1 tour officiel et passant la main à l'adversaire) et bouton de forfait avec modale de confirmation unifiée `showConfirmDialog`.
    - **Réseau de routes REST dédiées** : `/api/multi/create`, `/api/multi/join`, `/api/multi/setup-word`, `/api/multi/status` (GET & POST), `/api/multi/guess`, `/api/multi/hint` et `/api/multi/giveup`.
  - **Interface Web Interactive Dédiée (`volumes/web/multi/`)** :
    - Page dédiée servie sous URL propre sans extension `/multi/` (`volumes/web/multi/index.html`).
    - Écran d'accueil à 3 volets : **Créer un Duel**, **Rejoindre avec un Code** et **Vos Duels en cours**.
    - Salle d'attente avec affichage du code de salon et copie du lien d'invitation direct en 1 clic.
    - Arène de duel avec bandeau dynamique de tour temps réel (*🟢 À vous de jouer !* ou *⏳ Tour adverse...*), double jauge thermique, saisie protégée et double tableau comparatif des mots tentés.
    - Polling adaptatif intelligent à 1.5s activé uniquement lors de l'attente du coup adverse pour préserver les ressources réseau.
  - **Intégration & Maillage Interne** :
    - Ajout de l'onglet `👥 Mode Multijoueur` dans le menu de navigation de toutes les pages (`/`, `/play/`, `/battle/`, `/multi/`).
    - Mise à jour de `volumes/web/sitemap.xml` avec l'entrée `/multi/` et balisage Schema.org complet (`WebApplication`, `GameApplication`, `BreadcrumbList`, `FAQPage`).
- **Mode Battle Interactif Web (Joueur vs Bot IA RAG, `/battle/`)** :
  - **Moteur de duel tour par tour synchronisé (`src/api.py`, `BattleSession`)** :
    - Affrontement tour par tour en direct opposant le joueur humain à un bot IA propulsé par `RagDuelPlayer` (régression Ridge vectorielle analytique sur embeddings `frWac`).
    - **Trois niveaux de difficulté globaux** : paramètre englobant la difficulté du mot secret à trouver et l'agressivité du bot (*Facile* : top 4 000 mots et exploration large ; *Moyen* : 4 000 à 16 000 mots et sélection top 2 ; *Expert* : > 16 000 mots et convergence directe sur le top 1 absolu).
    - **Système de 3 indices gradués dégressifs** : 3 indices maximum par manche (*Général*, *Intermédiaire*, *Proche*). Chaque indice consomme 1 tour officiel au compteur et déclenche la réplique instantanée du bot IA.
    - **Réseau d'API REST dédié** : routes `POST /api/battle/new`, `POST /api/battle/guess`, `POST /api/battle/hint`, `POST /api/battle/giveup` et `POST /api/battle/resume`.
  - **Interface Web Sémantique & Arène de Duel (`volumes/web/battle/`)** :
    - Page dédiée servie sous URL propre sans extension `/battle/` (`volumes/web/battle/index.html`).
    - **HUD de confrontation en direct** : double thermomètre avec jauges parallèles de progression thermique (0 à 1000 ‰) pour le joueur et le bot adverse.
    - **Spotlight face-à-face du dernier tour** : comparaison immédiate du mot joué par le joueur et de la réplique du bot IA avec leurs températures, météos et permilles.
    - **Double tableau de classement** : top 10 des meilleurs mots et historique complet synchronisé des deux camps.
    - **Bannière de résultat et débriefing d'après-match** : détection automatique des victoires du joueur, de l'IA, des égalités parfaites et des abandons avec dévoilement des mots secrets.
  - **Optimisation SEO de Pointe & Rich Snippets Google** :
    - Balises métadonnées et réseaux sociaux Open Graph / Twitter Cards ciblées sur les requêtes de duel sémantique (*battle cemantix*, *duel cemantix*, *jouer contre ia*).
    - Données structurées JSON-LD Schema.org complètes : schémas `Game`, `WebApplication`, `BreadcrumbList` et `FAQPage` dédiée au duel.
    - Réintégration et suivi dans Git de `volumes/web/sitemap.xml` et `volumes/web/robots.txt` pour un référencement pérenne.
    - Guide éditorial et stratégique sémantique indexable par les moteurs de recherche.
  - **Conception Responsive Mobile-First & Smartphone** :
    - Sélecteur tactile compact (*Segmented Control*) pour smartphone permettant de basculer en un tap entre les essais du joueur et ceux du bot sans défilement excessif.
    - Typographie fluide, input sécurisé à `font-size: 16px` (empêche le zoom automatique sur iOS Safari), hauteurs minimales de tap à 42px et respect des zones de sécurité (`safe-area-inset`).
    - Maillage interne complet reliant le Tableau de bord (`/`), le Mode Solo (`/play/`) et le Mode Battle (`/battle/`).
  - **Modale de Lancement & Personnalisation du Mot Cible du Bot IA** :
    - Fenêtre modale au premier plan avec effet de flou d'arrière-plan (*glassmorphism backdrop blur 8px*).
    - Sélection interactive du niveau de l'IA (🟢 *Facile* - Explorateur, 🟡 *Moyen* - Équilibré, 🔴 *Expert* - Redoutable) sous forme de cartes tactiles descriptives.
    - Champ de saisie optionnel permettant au joueur de choisir le mot secret assigné au bot adverse (avec validation lexicale Cémantix en temps réel et bandeau d'alerte sans rechargement) ou tirage aléatoire 🎲.
    - Déclenchement automatique au clic sur `⚔️ Nouvelle Manche`, `🔄 Manche Suivante` ou lors de la première arrivée sur la page.
  - **Modale de Confirmation Moderne & Suppression des `confirm()` Système** :
    - Composant universel asynchrone `showConfirmDialog` avec flou d'arrière-plan, icône animée, messages d'explication clairs, bouton d'action contextuel (danger rouge ou accent) et bouton d'annulation.
    - Remplacement complet des boîtes de dialogue natives du navigateur pour les abandons en Mode Solo (`🏳️ Abandonner`) et les forfaits en Mode Battle (`🏳️ Forfait`).
    - Ajout de la classe utilitaire `.btn-danger` dans `volumes/web/css/base.css` et styles complets `.confirm-modal-card` dans `volumes/web/css/modal.css`.

### Corrigé
- **Sécurisation du seuil top 1000 dans `MockClient` (`src/clients.py`)** :
  - Remplacement de la constante fixe `-1000` par `k = min(1000, len(all_cos))` pour éliminer les `ValueError: kth out of bounds` lors de l'exécution sur des vocabulaires restreints ou sous jeux de tests unitaires.

### Ajouté
- **Jeu Interactif Web & API Locale Haute Performance (`src/api.py`, `--api`)** :
  - **Serveur HTTP interne multithreadé** : micro-API Python intégrée sans dépendance externe lourde, démarrée automatiquement avec le démon ou via l'option `--api`.
  - **Deux modes de jeu disponibles** :
    - *Défi du Jour* : jouez directement sur le mot officiel du jour synchronisé avec la résolution quotidienne du démon.
    - *Mode Illimité* : parties aléatoires rejouables à volonté avec sélection du niveau de difficulté (*Facile* 4 000 mots, *Moyen* 12 000 mots, *Expert* 18 646 mots).
  - **Moteur de scoring vectoriel instantané** : calcul en mémoire des similarités cosinus et des rangs Cémantix officiels en pourmille ( ‰) en < 0.1 ms via NumPy et `VocabStore`.
  - **Système d'indices contextuels intelligents** : calcul de candidats sémantiquement proches du mot secret pour débloquer les joueurs bloqués (+1 coup décompté au score).
  - **Persistance des parties actives** : sauvegarde automatique des sessions dans `cemantix_data/web_sessions.json` permettant de basculer d'onglet ou de rafraîchir sans perdre sa partie.
  - **Interface utilisateur dédiée au jeu** : spotlight du dernier mot joué avec jauge dynamique, tableau des 10 meilleurs mots, chronologie complète et gestion des victoires.
- **Visualisation Ergonomique de la Trajectoire du Bot** :
  - **Modale interactive de débriefing** : clic sur n'importe quelle ligne de l'historique des puzzles pour afficher la chronologie complète des coups joués par le solveur.
  - **Badges de provenance et métriques précises** : identification de l'origine de chaque mot (🌱 Graine, ⚡ RAG, 🤖 LLM, 🎯 Sniper), température (°C), indicateur météo, rang en pourmille ( ‰) et étoiles signalant un nouveau record thermique (⭐).
  - **Filtrage dynamique interactif** : onglets de filtrage par catégorie (*Tous*, *Graines*, *RAG*, *Top 1000*) avec compteurs en direct.
  - **Exportation rapide** : bouton de copie du rapport complet de résolution formaté pour le partage dans le presse-papier.
  - **Commande CLI `--force-solve`** : permet de forcer la résolution immédiate du mot du jour même s'il a déjà été résolu, afin d'enregistrer l'intégralité de la trajectoire dans l'historique et `data.json`.
  - **Fallback gracieux** : reconstitution automatique des étapes depuis les meilleurs essais pour les puzzles antérieurs à l'implémentation de la trajectoire complète.
- **Optimisation SEO Complète & Rich Snippets Google** :
  - **Données structurées JSON-LD** : schémas `WebPage`, `VideoGame` et `FAQPage` pour affichage enrichi dans les résultats de recherche Google.
  - **Métadonnées sociales Open Graph & Twitter Cards** : balises complètes avec image dédiée `og-image.jpg`.
  - **Optimisation sémantique et lexicale** : ciblage naturel des graphies avec et sans accent (*Cémantix*, *Cemantix*, *Semantix*).
  - **Guide stratégique & FAQ intégrée** : section explicative sur le fonctionnement du jeu, l'échelle des températures et les astuces de recherche.
- **Réseau Docker & Intégration Caddy (`docker-compose.yml`)** :
  - **Raccordement au réseau `web-net`** : déclaration du réseau externe `web-net` pour communication directe entre le conteneur `cemantix_solver` et le reverse-proxy Caddy.
  - **Routage de l'API** : redirection transparente des requêtes `https://cemantix.cyril-randon.fr/api/*` vers `cemantix_solver:8000`.
  - **Standard typographique** : insertion systématique d'une espace insécable/normale devant tous les symboles pourmille (` ‰`).
- **Interface Web Mot du Jour & Volume Caddy (`./volumes/web`)** :
  - **Dépose des fichiers web complets dans `./volumes/web`** : mise à disposition d'une application web autonome et réactive prête à être servie directement par Caddy via un simple montage de volume (`./volumes/web`).
  - **Fichiers statiques légers sans framework lourd ni PHP** :
    - `volumes/web/index.html` : structure sémantique moderne avec carte héro du mot du jour, badges, thermomètre, compte à rebours minuit, tableau de bord des statistiques et historique archivé.
    - `volumes/web/style.css` : feuille de style complète avec thème sombre et clair commutable, glassmorphism, responsive design et animations soignées.
    - `volumes/web/app.js` : application JavaScript vanilla avec gestion d'état, auto-polling de `data.json` toutes les 30s, compte à rebours en direct vers minuit (Europe/Paris), copie presse-papier avec notifications toast et recherche instantanée.
    - `volumes/web/data.json` : fichier de données temps réel maintenu à jour automatiquement.
  - **Mode Anti-Spoiler interactif** : protection par défaut du mot secret sous un voile flouté avec bouton de révélation/masquage au clic et bouton de bascule globale, idéal pour consulter les statistiques du jour sans se gâcher le puzzle en cours.
  - **Échelle Thermique & Indices d'Approche** : visualisation des paliers Cémantix officiels (Glacial, Froid, Tiède, Chaud, Brûlant) et affichage des meilleurs candidats sémantiques ayant convergé vers la cible avec leurs températures et rangs en pourmille (‰).
  - **Compte à rebours minuit en direct** : horloge numérique décomptant en temps réel les heures, minutes et secondes jusqu'au basculement officiel de Cémantix à 00h00 heure de Paris.
  - **Tableau de bord de performance (KPIs)** : total de puzzles résolus, moyenne d'essais, temps moyen de résolution et taux de succès (100%).
  - **Module d'exportation Python (`src/web.py`)** : génération et écriture atomique (via `.tmp` sécurisé) de `data.json`, synchronisé automatiquement au démarrage et à chaque résolution du démon (`src/daemon.py`).
  - **Option CLI `--export-web`** : commande permettant d'exporter ou régénérer les données web à tout moment depuis le terminal ou Docker.
  - **Montage du volume dans `docker-compose.yml`** : ajout du point de montage `- ./volumes/web:/app/volumes/web` pour une synchronisation transparente et continue entre le solveur en tâche de fond et le serveur web Caddy.
- **Mode Démon 24h/24 & Veille automatique (`src/daemon.py`, `--daemon`)** :
  - **Exécution en arrière-plan permanente sous Docker** : le conteneur reste en sommeil léger et se réveille chaque nuit à **00h00 (heure de Paris / Europe/Paris)** pour résoudre le mot officiel Cémantix en mode 100% RAG pur.
  - **Interception gracieuse des signaux POSIX** : écoute de `SIGTERM` et `SIGINT` avec boucle de sommeil par tranche de 1 seconde permettant un arrêt immédiat sans délai (`docker stop` / `docker compose down`).
  - **Rattrapage au démarrage** : vérifie dès le lancement si le mot du jour est déjà consigné dans l'historique ; dans le cas contraire, il le résout immédiatement avant d'entamer son cycle de veille jusqu'à minuit.
  - **Historisation automatique** : enregistrement des statistiques quotidiennes dans `cemantix_data/daily_history.json` (date, puzzle, mot trouvé, nombre de coups, durée).
  - **Configuration Docker pour service autonome** : ajout de `restart: unless-stopped`, `command: ["--daemon", "--rag-only"]`, paquet Debian `tzdata` et variable `TZ=Europe/Paris`.
  - **Surveillance de santé Docker (HEALTHCHECK)** : intégration d'un heartbeat régulier et de la commande `python cemantix_rag.py --healthcheck` rapportant dynamiquement l'état `healthy` sous `docker ps` et `docker compose ps`.

### Modifié / Amélioré
- **Ergonomie des Contrôles de Jeu & Boutons d'Action (`/play/`, `/battle/`, `/multi/`)** :
  - **Repositionnement latéral en 2 colonnes** : placement des boutons d'action (*Indice* et *Abandonner / Forfait*) directement à droite du champ de saisie sous forme d'une colonne compacte à 2 lignes superposées, s'alignant sur la hauteur du champ de saisie.
  - **Maintien de la disposition sur mobile** : conservation de la disposition côte à côte sur smartphone avec typographie et espacements adaptés pour ne jamais glisser sous le champ de saisie.
  - **Harmonisation des tuiles de mots et suppression des scintillements** : élimination du clignotement / saccade lors du rafraîchissement des listes d'essais via un cache de rendu DOM différentiel, désactivation des animations `fadeIn` répétitives, et affichage thermique harmonisé (+ / °C).
- **APIsation & Sécurisation du Tableau de Bord (`GET /api/daily`)** :
  - **Migration vers l'API interne** : suppression du fichier public `volumes/web/data.json` au profit d'une route API dédiée `GET /api/daily` servie par le conteneur Python.
  - **Protection Anti-Spoiler Serveur** : par défaut, le mot secret (`current.word`) et sa présence dans la trajectoire sont masqués côté serveur (`None` / `••••••••`).
  - **Révélation Dynamique Sécurisée** : le mot secret n'est délivré que lors d'un appel explicite `GET /api/daily?reveal=true` (déclenché au clic sur l'icône de révélation ou de copie).
  - **Enrichissement SEO Schema.org (`volumes/web/play/index.html`)** : intégration du schéma structuré `GameApplication` et du fil d'Ariane `BreadcrumbList`.
  - **Arrêt du suivi Git de `volumes/web/sitemap.xml`** : exclusion du sitemap local du dépôt Git pour éviter les conflits lors des pulls et déploiements sur VPS.
- **Refonte Responsive Smartphone & Expérience Mobile (`volumes/web/`)** :
  - **Fluidification du pied de page (Footer)** : bascule du footer en positionnement statique/naturel sur mobile (`≤ 768px`) pour supprimer le blocage de l'écran et le chevauchement avec les zones d'interaction et le clavier virtuel.
  - **Navigation par onglets façon « Segmented Control »** : remplacement de l'empilement vertical volumineux par un sélecteur d'onglets compact et tactile optimisé pour smartphone.
  - **En-tête et carte Hero adaptatifs** : typographie fluide via `clamp()`, adaptation du mot secret (sans débordement sur les mots longs), indicateur d'état du démon compact et grille de métriques à 3 colonnes réactives.
  - **Grille tactile pour le jeu interactif (`/play/`)** : disposition 2 colonnes des boutons d'action (`Indice` + `Nouvelle Partie` puis `Abandonner`), taille de police de saisie fixée à 16px minimum pour éliminer le zoom automatique intempestif sur iOS Safari.
  - **Tableaux et modale de trajectoire tactiles** : défilement horizontal fluide avec containment tactile (`overscroll-behavior-x`) et adaptation responsive de la modale de trajectoire du solveur IA.
  - **Métadonnées PWA / Viewport Cover** : intégration de `viewport-fit=cover`, `mobile-web-app-capable` et prise en charge des zones de sécurité (`safe-area-inset`).
  - **Mise à jour visuelle Open Graph** : actualisation de la bannière sociale d'illustration `og-image.jpg`.
- **Refonte Modulaire & Architecture Atomique de l'Interface Web (`volumes/web/`)** :
  - **Scission de la page monolithique `index.html`** : séparation en deux pages HTML atomiques et sémantiques avec URLs propres sans extension :
    - `index.html` : Tableau de bord du mot du jour (URL `/`), métriques, thermomètre, podium des indices, KPIs, historique des puzzles archivés, modale de trajectoire IA et section SEO / FAQ.
    - `play/index.html` : Interface dédiée au jeu interactif Cémantix en ligne servie sous l'URL propre `/play/` (mode Défi du jour, mode Illimité avec sélecteur de difficulté, saisie réactive, spotlight et listes d'essais).
  - **Découpage modulaire des styles CSS (`volumes/web/css/`)** : décomposition du fichier monolithique `style.css` (~2 200 lignes) en 6 sous-modules atomiques indépendants :
    - `variables.css` : tokens de design, thèmes sombre et clair, dégradés thermiques sémantiques.
    - `base.css` : reset, typographie, boutons, badges, composants de base, boutons pill et notifications toast.
    - `layout.css` : en-tête d'application, navigation par onglets réactive et pied de page fixe.
    - `dashboard.css` : composants visuels du tableau de bord, thermomètre, compte à rebours minuit et guide SEO.
    - `game.css` : commandes de jeu, saisie, spotlight du dernier mot et listes de propositions.
    - `modal.css` : modale de visualisation de la trajectoire du bot et filtres de progression.
  - **Modularisation JavaScript en modules ES natifs (`volumes/web/js/`)** : éclatement du fichier monolithique `app.js` (~1 400 lignes) en modules autonomes sans bundler lourd :
    - `app.js` : point d'entrée unique et bootstrap de l'application selon les éléments du DOM.
    - `utils.js` : helpers de formatage de dates, calcul des classes thermiques, gestionnaire de toasts et copie presse-papier.
    - `theme.js` : commutation des thèmes clair/sombre et bascule globale du voile anti-spoiler.
    - `countdown.js` : horloge décomptant en temps réel le temps jusqu'à minuit (Europe/Paris).
    - `trajectory.js` : gestion et filtrage de la modale de trajectoire du solveur IA.
    - `dashboard.js` : synchronisation continue de `data.json`, rendu du mot du jour et recherche dans l'historique.
    - `game.js` : gestion des parties interactives, appels à la micro-API `/api/game/*`, persistance locale et spotlight.
  - **Optimisation du chargement et élimination des fichiers obsolètes** : suppression des monolithes racine `app.js` et `style.css`, liaison directe des ressources spécifiques par page pour un rendu immédiat et zéro flash de style.
- **Refonte Ergonomique & Architecture des Dégradés (`volumes/web/`)** :
  - **Mise en page 2 colonnes de la carte Hero (Mot du Jour)** : réorganisation du bloc Mot du Jour en grille à deux colonnes équilibrée sur grand écran (carte du mot secret à gauche, 3 cartes métriques empilées à droite) pour supprimer les espaces vides et offrir une lecture immédiate.
  - **Architecture à deux dégradés distincts (`--gradient-dashboard` et `--gradient-game`)** :
    - *Échelle thermique du tableau de bord (`--gradient-dashboard`)* : dégradé continu à 5 paliers avec contraste renforcé entre Glacial (`#075985`) et Froid (`#3b82f6`), et transitions resserrées pour valoriser les teintes dominantes.
    - *Jauge du jeu interactif (`--gradient-game`)* : dégradé dédié chaud débutant à moyen chaud à partir du jaune (`#fcf161`) vers le rouge carmin (`#c20000`).
  - **Modernisation de la tuile « Dernier coup joué : »** :
    - Élimination des encadrements lourds au profit d'un agencement épuré et moderne.
    - Affichage de la température en typographie monospace blanche/neutre sans coloration superflue du texte.
    - Jauge capsule horizontale fluide adoptant `--gradient-game`.
    - Affichage conditionnel de la jauge : masquée pour les températures froides ou fraîches (`< 20°C`), et affichée uniquement à partir d'une température tiède/chaude (`>= 20°C` ou mot classé au Top 1000).
  - **Finitions typographiques** : harmonisation des espaces insécables devant les symboles pourmille (` ‰`) et style épuré pour le lien auteur en pied de page.

## [0.2.0] - 2026-10-18

### Modifié
- **Refactoring architectural modulaire (`src/`)** :
  - Découpage du script monolithique `cemantix_rag.py` (~2 000 lignes) en package modulaire `src/`.\
  - `src/config.py` : centralisation des constantes, styles ANSI et configuration d'environnement.\
  - `src/vocab.py` : gestion du dictionnaire Lexique 3.83, normalisation des accents et `VocabStore` (ChromaDB).\
  - `src/clients.py` : client officiel `CemantixClient` et simulateur local `MockClient`.\
  - `src/ui.py` : composants de rendu console, thermomètres ASCII, dashboards solo/duel et débriefing.\
  - `src/solvers.py` : régression Ridge, algorithme de reranking, interface LLM local, `Solver` et `RagDuelPlayer`.\
  - `src/modes.py` : boucles d'orchestration pour benchmark, battle, solo et duel.\
  - `cemantix_rag.py` : point d'entrée CLI épuré (~80 lignes) orchestrant les modules.\
  - Mise à jour du `Dockerfile` et de la documentation (`README.md`).

### Corrigé
- **Dictionnaire & Filtrage linguistique strict (élimination des mots anglais & réhabilitation de « car »)** :
  - **Correction du refus des mots usuels en mode Solo (`car`, `faire`, `être`, `avoir`, etc.)** : suppression du filtre prématuré `w not in STOPWORDS` lors de l'extraction de l'espace vectoriel `frWac`, permettant à tous les lemmes et mots grammaticaux français légitimes d'être chargés dans le vector store et d'être joués et scorés normalement en Solo, Duel et Mock.
  - **Détection et régénération automatique du cache vectoriel** : si un cache `vecs.npy` / `words.txt` antérieur sans `car` est détecté, régénération automatique propre depuis le binaire `frWac` et synchronisation immédiate des lemmes fondamentaux dans ChromaDB.
  - **Épuration intégrale de `ENGLISH_WORDS` & Suppression totale de `FRENCH_EXCEPTIONS`** : assainissement radical de la liste noire anglophone pour n'y conserver strictement que de vrais parasites (*water*, *people*, *about*, *money*, *dog*, *cat*, etc.) et les graphies anglaises sans accent (*decision*, *region*, *creation*...). Tout mot français, homographe ou emprunt usuel (*car*, *table*, *train*, *sport*, *film*, *process*, *report*, *bug*, *job*, *coach*, *deal*, *pass*, *set*, *top*, *cool*, etc.) en a été retiré, éliminant définitivement la variable et liste d'exceptions `FRENCH_EXCEPTIONS`. Tout mot ajouté dans `lexique_fr.txt` fonctionne désormais immédiatement à 100 % sans aucune manipulation annexe ni exception à configurer.
  - **Exclusion formelle des mots anglais parasites (`ENGLISH_WORDS`)** : filtrage strict des résidus de sous-titres et tokens web anglophones (*water*, *people*, *about*, *game*, *play*, *boy*, *girl*, etc.) dans `ensure_lexique()`, `VocabStore.is_valid_french()`, le solveur RAG et les modes interactifs Solo/Duel.
  - **Renforcement des consignes du prompt LLM** : instruction linguistique stricte interdisant formellement la génération de tout mot anglophone.
- **Menu d'accueil interactif (`--play`)** :
  - Restauration de l'écran d'accueil permettant de choisir explicitement entre le mode Solo et le mode Duel croisé au lancement de `--play`.

### Optimisé & Corrigé
- **Convergence RAG Haute Efficacité & Reranking par Température Estimée** :
  - **Correction du vivier FPS** : restriction stricte du vivier de graines aux pôles disciplinaires fondamentaux (`DISCIPLINES`) et concepts cardinaux du lexique (`SEED_WORDS`), éliminant les lemmes marginaux ou périphériques.
  - **Reranking multicritère par température** : refonte de la fonction `rerank` pour ordonner les candidats par score d'excellence `pred_temp - 120.0 * sqrt(err)` au lieu de l'erreur brute seule, garantissant que les candidats les plus chauds soient joués en priorité.
  - **Pool de candidats enrichi** : élargissement de l'exploration vectorielle à 60-80 candidats combinant la direction Ridge `q_est` et les voisins des meilleurs coups connus.
  - **Amorçage adaptatif affiné (12 graines)** : interruption précoce dès 3 graines si un signal $\ge 20^\circ\text{C}$ (Top 1000) est détecté, et tir sniper dès détection d'un candidat brûlant ($\ge 65^\circ\text{C}$ et cohérence extrême).
  - **Résultat de référence** : résolution de mots cibles courants (ex: *planifier*) en 11 à 14 essais (médiane : 12 essais, min : 8 essais, temps moyen ~0.25s) contre 19 à 31 essais précédemment.
