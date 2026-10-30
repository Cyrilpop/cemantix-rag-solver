# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-30 · Quick Win SEO : « Solution Cémantix du lundi 26 octobre 2026 »

### Ajouté
- **Libellé d'archive orienté mot-clé (`SEO-13`, `SEO-14`, évolution `docs/roadmap/2026-10-seo-titres-archives/`)** :
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
- **Feuille de route & Suite de tests Responsive Mobile (`docs/roadmap/2026-10-responsive-mobile/`, `tests/test_responsive.py`)** :
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
