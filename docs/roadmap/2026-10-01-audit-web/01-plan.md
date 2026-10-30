# 🔍 Audit & Plan — Partie Web (Cémantix Solver)

> **Évolution :** [2026-10 · Audit web](../README.md) · document 1/2 · **clôturée**
> **Historique :** audit du 26/10/2026, d'abord conduit hors git dans `.idea/PLAN_WEB_AUDIT.md`.
> Versionné ici parce que c'est le document d'origine de la branche `feat/optimisation-seo`
> (43 commits sur `main`), qui en était le seul exemplaire avant son archivage ici.
> Son suivi est dans [`02-avancement.md`](02-avancement.md).
> **Ne pas confondre** avec l'évolution
> [2026-10 · Sécurité, SEO, performance, qualité](../2026-10-securite-seo-performance/01-plan.md),
> audit transverse du 27/10 qui a re-vérifié point par point ce que celui-ci annonçait comme traité.
> Périmètre analysé : `volumes/web/**` (HTML/CSS/JS), `src/api/**` (API HTTP),
> `src/services/web.py` (export données), `docker-compose.yml`, `Dockerfile`.
> Date de l'audit : 26/10/2026

---

## 0. Vue d'ensemble

La partie web est une **application 100 % statique** (4 pages) servie par **Caddy**,
alimentée par une **API Python maison** (`http.server`, pas de framework) et un
fichier `data.json` régénéré par le démon chaque nuit.

```
  Navigateur (index.html, play/, battle/, multi/)
        │  fetch()
        ▼
  Caddy (reverse proxy /api → conteneur)
        │
        ▼
  src/api/server.py (ThreadingHTTPServer, port 8000)
        ├── routes/system.py   → /api/health, /api/daily
        ├── routes/solo.py     → /api/game/*
        ├── routes/battle.py   → /api/battle/*
        └── routes/multi.py    → /api/multi/*
        ▲
  src/services/web.py → volumes/web/data.json (écriture atomique)
```

**Verdict global :** base saine et moderne (SEO on-page déjà très complet, JS sans
dépendance, écriture atomique), mais **3 failles de sécurité critiques**, un poids
image de **3 Mo**, et un **SEO qui ne capte pas la longue traîne quotidienne**
(alors que c'est exactement le mot-clé visé).

---

## 1. Ce qui est déjà bien ✅

| Domaine | Point positif | Preuve |
|---|---|---|
| SEO | 4 pages avec `lang="fr"`, un seul `<h1>`, title/description/canonical/OG/Twitter cohérents | `volumes/web/index.html:13-40` |
| SEO | JSON-LD riche et correct : `WebApplication` + `Game` + `WebSite` + `FAQPage` | `volumes/web/index.html:51-160` |
| SEO | `robots.txt`, `sitemap.xml`, `llms.txt`, `ai-catalog.json` (racine **et** `.well-known/`) | racine `volumes/web/` |
| SEO | Contenu éditorial réel (guide + FAQ) dans le HTML, pas que du JS | `index.html:408+` (`#guide-faq`) |
| Perf | CSS découpé par responsabilité, aucun framework, aucun build à maintenir | `volumes/web/css/` (8 fichiers) |
| Perf | Polling multijoueur **adaptatif** (2,5 s si tour adverse / 5 s sinon) | `js/multi.js:736-742` |
| Robustesse | Écriture atomique de `data.json` (tmp + `replace`) → pas de fichier à moitié lu | `src/services/web.py:131-136` |
| Sécurité | Anti-spoiler **côté serveur** : mot masqué + trajectoire en `••••••••` | `src/api/routes/system.py:29-38` |
| Sécurité | `rel="noopener noreferrer"` sur les liens sortants, écriture atomique des sessions | `index.html:568`, `src/game/manager.py:53-65` |

---


## 2. Problèmes détectés 🔴

### 2.1 Sécurité — **CRITIQUE**

| # | Problème | Preuve | Impact |
|---|---|---|---|
| S1 | **Fuite totale du mot du jour** : `/api/daily?reveal=true` est public, sans auth ni rate-limit. Le `?t=Date.now()` casse en plus tout cache. | `src/api/routes/system.py:27`<br>`js/dashboard.js:50,131,157` | Le mode anti-spoiler est décoratif : un simple `curl` suffit. Un aggregator peut indexer la solution. |
| S2 | **`data.json` publié dans le webroot** avec l'historique **complet des mots** (`word` non masqué) → accessible sur `https://…/data.json`. | `src/services/web.py:124-127` | Spoiler intégral de tous les puzzles passés **et du jour**, sans passer par l'API. |
| S3 | **CORS `Access-Control-Allow-Origin: *`** + `Authorization` dans `Allow-Headers`, sur toutes les réponses. | `src/api/server.py:37-40` | N'importe quel site peut consommer l'API (détournement de sessions multi via URL partagée volée). |
| S4 | **Aucun en-tête de sécurité** : ni Caddyfile versionné, ni en-têtes dans le handler. Pas de CSP, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`. | absent du dépôt | Clickjacking, MIME sniffing, downgrade HTTPS, XSS non atténué. |
| S5 | **XSS par `innerHTML` avec données serveur non échappées** : mots, dates, `data-puzzle`, messages d'erreur, noms de salon. | `js/dashboard.js:271,345-372`<br>`js/trajectory.js:215`<br>`js/multi.js:110,955,986`<br>`js/battle.js:268` | Un mot / nom de salon / erreur contenant du HTML s'exécute → vol du `localStorage` (dont les clés de salon `k=`). |
| S6 | **API sans aucune limite** : `Content-Length` lu sans plafond, pas de timeout, pas de rate-limit, threads illimités, sessions jamais purgées. | `src/api/server.py:56-64,114` | DoS mémoire trivial (POST géant), épuisement de threads, fichiers de sessions croissant à l'infini. |
| S7 | **Secrets de salon dans l'URL** `?r=DUEL-XXXX&k=J2-YYYY` | `src/api/routes/multi.py:68`<br>`js/multi.js:47-48` | Fuite via `Referer`, historique navigateur, logs Caddy → prise de contrôle d'un duel. |
| S8 | **API de jeu exposée au public** (le compose ne publie aucun port, mais Caddy proxifie `/api`) sans restriction de débit ni chemin privé. | `docker-compose.yml`, `ai-catalog.json` | Surface d'attaque maximale ; l'`ai-catalog.json` **invite** de plus les agents IA à taper `/api/daily`. |
| S9 | **API globales + `onclick` inline** : `window.copyToClipboard`, `window.showConfirmDialog`. | `js/utils.js:47,201` | Incompatible avec une CSP stricte ; toute injection HTML devient un vecteur d'exécution direct. |

### 2.2 Performance 🟠

| # | Problème | Preuve | Coût |
|---|---|---|---|
| P1 | **`og-image.jpg` = 3 091 777 o (3 Mo), 2752×1536** alors que les balises déclarent 1200×630. | `ls -la volumes/web` | 3 Mo payés à chaque crawl/partage ; souvent refusé ou redimensionné par les crawlers sociaux. |
| P2 | **5 `<link>` CSS bloquants par page**, non minifiés (77 ko), sans `preload`/`media`. `battle/` charge `game.css` **et** `battle.css`. | `index.html:44-48`, `battle/index.html:44-49` | 5 requêtes séquentielles avant le premier rendu. |
| P3 | **`app.js` importe les 4 modules de jeu sur toutes les pages**, et `multi.js` s'auto-initialise au `DOMContentLoaded`. | `js/app.js:4-8`, `js/multi.js:40` | 35 ko de JS mort sur `/` + double initialisation possible. |
| P4 | **Polling permanent** : `setInterval(fetchDashboardData, 30000)` sans pause onglet masqué, sans `ETag`, et la requête de tick renvoie **tout l'historique** avec `reveal=true`. | `js/dashboard.js:112-115,157` | Bande passante ×40/jour/utilisateur, batterie mobile, cache impossible. |
| P5 | **`Intl.DateTimeFormat` recréé chaque seconde** dans le countdown. | `js/countdown.js:17` | Allocation inutile 86 400×/jour. |
| P6 | **Recherche d'historique sans debounce** : `renderHistoryTable()` recrée tout le `<tbody>` à chaque frappe. | `js/dashboard.js:84-88` | Jank sur les gros historiques. |
| P7 | **Aucune politique de cache** nulle part dans le dépôt (aucun `Cache-Control`). | grep : 0 occurrence | Soit revalidation inutile, soit `data.json` périmé selon la config Caddy (non versionnée). |
| P8 | Aucune optimisation d'affichage : pas de `content-visibility`, `contain`, `loading="lazy"`, `fetchpriority`. | grep : 0 occurrence | LCP / INP dégradés sur mobile. |

### 2.3 SEO 🟡

| # | Problème | Preuve | Conséquence |
|---|---|---|---|
| E1 | **`sitemap.xml` figé** : `<lastmod>2026-10-25</lastmod>` en dur, jamais régénéré par `export_web_data()`. | `volumes/web/sitemap.xml` | Signal de fraîcheur mort sur un site dont le contenu change à minuit. |
| E2 | **Aucune page indexable par jour** : mot + indices injectés en JS uniquement. Pas de `/puzzles/<date>/`, pas de `Article`/`dateModified`, pas de `BreadcrumbList` (pourtant annoncé dans le commentaire de `play/index.html:41`). | rendu JS dans `js/dashboard.js` | Impossible de ranker sur « cemantix du **26 octobre** », la requête à plus fort volume du sujet. |
| E3 | **`data.json` dans le webroot** (aussi un problème SEO) : contenu dupliqué indexable de l'accueil, avec les solutions en clair. | `src/services/web.py:127` | Pages « solution » non maîtrisées dans l'index. |
| E4 | Balises obsolètes/redondantes : `<meta name="keywords">` (ignoré), `<meta name="title">` (dupliqué avec `<title>`). | `index.html:14,16` | Bruit, poids inutile. |
| E5 | Une seule `og:image` pour 4 pages ; `og:image:alt` absent des pages secondaires ; favicon uniquement en data-URI (pas d'`apple-touch-icon`, pas de `manifest.webmanifest`). | `play/index.html:27-30` | Partage social moins efficace, pas d'installation PWA. |
| E6 | `robots.txt` ne bloque ni `/api/` ni `?reveal=`. | `volumes/web/robots.txt` | Crawlers invités sur l'API et sur les URLs spoilantes. |
| E7 | `theme-color` figé à `#0d1117` alors qu'un thème clair existe. | `index.html:21` | Barre navigateur incohérente en thème clair. |

---

## 3. Plan d'action 🛠️

> Ordre imposé : **Phase 1 → 2 → 3**. La correction S1/S2 conditionne le design du
> cache (P7) et la génération des pages jour (E2).

### Phase 1 — Sécurité 🔒 *(≈ ½ journée, prioritaire)*

- [x] **1.1 Supprimer le `reveal=true` public** → `POST /api/daily/reveal` avec
      confirmation explicite (double clic), rate-limit par IP et
      `Cache-Control: no-store`. La réponse publique ne contient **plus jamais**
      `current.word` ni le mot dans `trajectory`.
      → `src/api/routes/system.py`, `js/dashboard.js:50,131,157`
- [x] **1.2 Sortir `data.json` du webroot** (écrire dans `cemantix_data/`) ; si un
      fichier public reste nécessaire, y **retirer le champ `word`**.
      → `src/services/web.py:124-130`
- [x] **1.3 CORS en liste blanche** : origine unique via `CORS_ALLOWED_ORIGIN`
      (défaut `https://cemantix.cyril-randon.fr`), retirer `Authorization`.
      → `src/api/server.py:37-40`
- [x] **1.4 Versionner un `Caddyfile`** avec :
      - `strict-transport-security` (HSTS 1 an + preload),
      - `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
        `Referrer-Policy: strict-origin-when-cross-origin`,
        `Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()`,
      - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
        img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'`,
      - `encode gzip zstd`, `Cache-Control` immuable sur `/css` `/js` (versionnés `?v=`),
        `no-store` sur `data.json` et `/api/*`,
      - blocage des dotfiles (exception `.well-known/`), log avec `status` + `duration`.
      → nouveau `Caddyfile` + service `caddy` dans `docker-compose.yml`
- [x] **1.5 Échappement systématique** : ajouter `escapeHtml()` dans `js/utils.js`,
      l'appliquer partout + préférer `textContent` / `dataset` / `<template>`.
      Supprimer les `onclick` inline et les globals `window.*` (`utils.js:47,201`)
      → événements `addEventListener` + délégation.
- [x] **1.6 Durcir le serveur** : plafond body 64 ko, `timeout` socket 10 s,
      rate-limit (jeton seau par IP, ex. 30 req/min sur `/api/multi/*`),
      TTL de purge des sessions (solo/battle/multi) dans `GameManager`.
      → `src/api/server.py`, `src/game/manager.py`
- [x] **1.7 Retirer la clé joueur de l'URL** : `sessionStorage` + jeton de reprise,
      lien de partage en `?r=` seulement (la clé est renvoyée en corps de réponse).
      → `src/api/routes/multi.py:64-68`, `js/multi.js:46-60`
- [x] **1.8 Restreindre `ai-catalog.json`** à un endpoint non spoilant
      (`/api/health` ou futur `/api/clues`) au lieu de `/api/daily`.

**Critère d'acceptation :** `curl 'https://…/api/daily?reveal=true'` ne renvoie **pas**
le mot ; `curl -I https://…/data.json` → 404 ; `curl -I https://…/` expose CSP + HSTS ;
une saisie `<img src=x onerror=alert(1)>` n'exécute rien.


### Phase 2 — Performance & Core Web Vitals ⚡ *(≈ ½ journée)*

- [ ] **2.1 `og-image`** : recadrer en 1200×630, exporter `.jpg` (q82) + `.webp`,
      viser **< 120 ko** (3 Mo → ~90 ko).
- [x] **2.2 CSS** : 1 fichier minifié par page (build léger ou pré-bundlé à la main),
      `<link rel="preload" as="style">` pour le critique, `media="print"` + `onload`
      pour le non critique, dédoublonner `game.css` de `battle/`.
      77 ko → ~35 ko, 5 requêtes → 1.
- [x] **2.3 Code-splitting** : `app.js` charge dynamiquement le module de la page
      (`import()` piloté par un attribut `data-view` sur `<body>`), retirer
      l'auto-initialisation de `multi.js`.
- [x] **2.4 Polling intelligent** : pause si `document.visibilityState === 'hidden'`,
      `AbortController`, `ETag`/`If-None-Match` → `304`, et endpoint léger
      `GET /api/daily/current` (sans `history`) pour le tick des 30 s.
- [x] **2.5 Countdown** : instancier `Intl.DateTimeFormat` **une fois** hors de
      `update()` (`js/countdown.js:17`).
- [x] **2.6 Historique** : debounce 150 ms, `DocumentFragment` +
      `requestAnimationFrame`, pagination 50 lignes.
- [x] **2.7 Rendu** : `content-visibility: auto` + `contain-intrinsic-size` sur les
      sections hors écran, `contain: layout paint` sur les listes,
      bloc `@media (prefers-reduced-motion: reduce)`.
- [x] **2.8 Cache** : assets immuables `max-age=31536000, immutable` (avec `?v=hash`),
      `data.json` / `/api/*` → `no-store` ou `max-age=60`.

**Critère d'acceptation :** Lighthouse ≥ 95 Performance mobile, LCP < 2 s,
CLS < 0.05, poids total de la 1ʳᵉ page < 300 ko.

### Phase 3 — SEO 📈 *(≈ 1 journée)*

- [x] **3.1 `sitemap.xml` généré** par `export_web_data()` : `lastmod` réel,
      inclusion des URLs `/puzzles/<aaaa-mm-jj>/` des 90 derniers jours,
      `sitemap-index` au-delà de 500 URLs. → `src/services/web.py`
- [x] **3.2 Pages par jour** `/puzzles/2026-10-26/` (générées statiquement à minuit) :
      title « Cémantix du 26 octobre 2026 : indices, thermomètre et solution »,
      contenu **servi en HTML** (top 10 des indices, échelle thermique, nb de coups),
      solution derrière un `<details>` « Afficher la solution »,
      JSON-LD `Article` + `dateModified` + `BreadcrumbList` + `FAQPage` locale,
      index paginé `/puzzles/` + maillage (derniers puzzles sur l'accueil).
      → capte la longue traîne « cemantix du jour + date ».
- [x] **3.3 Pré-rendu de l'accueil** : au moment de l'export, injecter les indices du
      jour dans le HTML (masqués en CSS pour l'anti-spoiler humain) → indexable sans JS.
- [x] **3.4 Nettoyage balises** : supprimer `meta keywords` + `meta name="title"` ;
      `og:image` propre par page + `og:image:alt` ; `apple-touch-icon.png` ;
      `manifest.webmanifest` (nom, icônes 192/512, `theme_color`,
      `display: standalone`) ; `theme-color` en 2 valeurs selon `prefers-color-scheme`.
- [x] **3.5 `robots.txt`** : `Disallow: /api/`, `Disallow: /*?reveal=`,
      `Allow: /puzzles/`, `Sitemap:` à jour ; soumission Search Console + Bing.
- [x] **3.6 Enrichissements** : `HowTo` (« comment jouer à Cémantix »),
      `BreadcrumbList` sur les 4 pages existantes, `aggregateRating` **uniquement**
      si des avis réels existent (sinon risque de pénalité schema).

**Critère d'acceptation :** `site:cemantix.cyril-randon.fr` expose les pages
`/puzzles/<date>/` ; Rich Results Test vert sur une page jour ; sitemap validé
sans erreur dans Search Console.


### Phase 4 — Vérification end-to-end ✅

```bash
# API + en-têtes
python cemantix_rag.py --api --api-port 8000
curl -I http://localhost:8000/api/health
curl -s 'http://localhost:8000/api/daily'             | grep -c '"word": null'   # attendu : >= 1
curl -s 'http://localhost:8000/api/daily?reveal=true' | grep -c '"word": null'   # attendu : >= 1 (le parametre est ignore)

# Sitemap + export
python cemantix_rag.py --export-web && head -12 volumes/web/sitemap.xml

# Lighthouse (URL déployée)
npx --yes lighthouse https://cemantix.cyril-randon.fr/ \
    --only-categories=performance,seo,accessibility,best-practices --output=html
```

Puis : validateur `validator.schema.org` sur les 4 JSON-LD, `opengraph.xyz` sur l'OG,
test d'une invitation de duel pour vérifier l'absence de fuite de `k=` dans le
`Referer`, et re-test XSS avec une saisie `<img src=x onerror=…>`.

---

### Statut d'avancement (2026-10-27)

**21 des 22 points sont traités.** Deux écarts par rapport au plan, assumés :

| Point | Le plan prévoyait | Ce qui a été fait | Pourquoi |
|---|---|---|---|
| **2.2 / 2.8 Cache & CSS** | 1 fichier minifié par page **avec `?v=hash`** et `max-age=31536000, immutable` | Bundles par page via `tools/build_css_bundles.py`, **sans** paramètre de version ; tout ce qui change en `no-cache, must-revalidate`, seules les polices gardent un an | La règle du projet est « no-cache, pas de `?v=` » (revalidation par ETag Caddy), déjà appliquée en production. Ajouter `immutable` sur des fichiers non hashés aurait servi des feuilles périmées après chaque déploiement. |
| **3.6 `aggregateRating`** | « uniquement si des avis réels existent » | Omis | Aucun avis vérifiable n'existe à ce jour ; un `aggregateRating` inventé est un motif de pénalité manuelle. |

**Reste fait : 2.1 `og-image` (3,09 Mo).** Non réalisable dans cet environnement :
`PowerShell` y est en mode langage contraint (pas d'`Add-Type`, donc pas de
`System.Drawing`), ni `Pillow`, ni ImageMagick, ni `node`, et aucun accès réseau pour
installer quoi que ce soit. L'inspection du fichier confirme qu'aucun raccourci n'existe :
**98 % des 3 091 777 octets sont les données de pixels** (baseline JPEG 2752×1536), la
segmentation ne laissant que ~30 ko de métadonnées. Seul un vrai ré-encodage change
quelque chose.

`tools/check_og_image.py` pose le diagnostic (poids et dimensions réels contre les
balises `og:image`, code de sortie `1` pour la CI). Sur ta machine :

```bash
convert volumes/web/og-image.jpg -resize 1200x630^ -gravity center -extent 1200x630 \
        -quality 82 volumes/web/og-image.jpg
```

Puis `python tools/check_og_image.py` doit sortir `0`.

## 4. Récapitulatif effort / impact

| Phase | Effort | Sécurité | Performance | SEO |
|---|---|---|---|---|
| 1 — Sécurité | ½ j | 🔴 → 🟢 | — | 🟡 (fin du contenu spoilant indexé) |
| 2 — Performance | ½ j | 🟡 (CSP devient possible) | 🔴 → 🟢 (LCP, −3 Mo OG) | 🟡 (CWV = ranking) |
| 3 — SEO | 1 j | — | 🟡 (pages statiques) | 🔴 → 🟢 (longue traîne quotidienne) |
| 4 — Vérification | ¼ j | ✅ | ✅ | ✅ |

**Quick wins à faire dans l'heure (si on doit tronquer) :**
1. Supprimer `?reveal=true` du chemin public (S1) + sortir `data.json` du webroot (S2).
2. Recadrer `og-image.jpg` (P1) — 3 Mo → ~90 ko.
3. Générer `sitemap.xml` avec le `lastmod` réel (E1).

---

## 5. Dettes techniques annexes (hors périmètre, à noter)

- `src/api/server.py:100` : `log_message()` écrase **tous** les logs HTTP → aucune
  traçabilité en cas d'abus. Mieux : journaliser les POST et les 4xx/5xx.
- `src/api/server.py:67` : `path.rstrip("/")` rend `/api/daily/` équivalent à
  `/api/daily` → normaliser une seule forme pour le cache et les règles Caddy.
- Aucun test d'API automatisé (pas de `tests/`) → les correctifs 1.1 / 1.6 / 1.7
  méritent des tests `unittest` sur le handler.
- `volumes/web/js/multi.js` (1002 lignes) et `battle.js` (839) : à découper en
  modules (`lobby.js`, `arena.js`) pour rendre le code-splitting de 2.3 possible.
- Le `Caddyfile` est hors dépôt : toute la stratégie d'en-têtes/cache dépend d'un
  fichier non versionné → à internaliser impérativement (1.4).

