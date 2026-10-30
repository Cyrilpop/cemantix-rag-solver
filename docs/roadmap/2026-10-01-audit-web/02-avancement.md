# feat(web) : SEO quotidien indexable + durcissement sécurité + performance

> **Évolution :** [2026-10 · Audit web](../README.md) · document 2/2 · **clôturée**
> **Historique :** ce document est la description de la PR `feat/optimisation-seo` → `main`,
> rédigée dans `.idea/pr.md`. Versionné ici comme **suivi de l'évolution** : c'est le seul texte
> qui détaille ce que font réellement les commits de cette branche. Les chiffres ci-dessous sont
> ceux relevés à la rédaction ; au 27/10 14:30 la branche mesure **43 commits** sur `origin/main`,
> **48 fichiers**, **+4 583 / −270**. Les 35 commits qui n'étaient pas encore poussés à ce moment-là
> **le sont depuis** (27/10 dans l'après-midi) : la branche est sauvegardée sur GitHub, il ne reste
> qu'à la **fusionner**.
> **Attention :** l'évaluation finding par finding, avec preuve dans le code, est dans
> [`../2026-10-02-securite-seo-performance/02-avancement.md`](../2026-10-02-securite-seo-performance/02-avancement.md)
> — ce document-ci décrit l'intention et le contenu, pas l'état de conformité.

**Branche :** `feat/optimisation-seo` → `main`
**Étendue :** 32 commits · 51 fichiers · +4 249 / −209
**Bases de l'audit :** [`01-plan.md`](01-plan.md) — Phases 1 (sécurité), 3 (SEO) et une partie de la 2 (performance)

---

## 🎯 Pourquoi cette PR

L'audit de la partie web a révélé trois blocs de problèmes qui se traitaient en partie ensemble, parce qu'ils partagent les mêmes fichiers :

**Côté SEO, le site visait « cemantix du jour » sans jamais publier de contenu daté.** Tout le contenu du tableau de bord était rendu par JavaScript : un crawler ne voyait rien, et le `sitemap.xml` versionné était figé au `2026-10-25` sans aucune page par jour. La longue traîne « cemantix du 26 octobre 2026 » — exactement la requête visée — était donc inaccessible.

**Côté sécurité, trois brèches rendaient le jeu et les données publics :**

1. `GET /api/daily?reveal=true` renvoyait le mot du jour à n'importe qui. Pire : même **sans** ce paramètre, la solution fuitait dans les tableaux `trajectory`, `top_guesses` et `history` — le `word: null` n'était que cosmétique, et le bouclier anti-spoiler ne tenait que par le CSS.
2. `data.json` (documenté comme devant être publié dans le webroot) contient l'historique **complet** des solutions : `curl https://…/data.json` les donnait toutes, sans passer par l'API.
3. Aucune fonction d'échappement n'existait dans les ~3 000 lignes de JS. Les mots, dates, identifiants de salon et pseudonymes d'adversaire partaient bruts dans `innerHTML` — et, plus grave, dans des gestionnaires construits par concaténation : `onclick="copyToClipboard('${mot}')"`. Une apostrophe dans un mot ou un pseudo fermait la chaîne JS et exécutait du code.

**Côté performance**, le gaspillage était surtout invisible : des requêtes payées pour rien, en arrière-plan ou en double.

---

## 🔎 SEO — ce qui change

### Pages par jour `/puzzles/AAAA-MM-JJ/`

Nouveau module `src/services/seo.py` (797 l.) qui convertit l'historique des résolutions en **contenu rendu côté serveur** :

- `<title>` et meta description datés, URL canonique, Open Graph, Twitter Card ;
- **tableau des 10 mots les plus proches** (score en °C, similarité en ‰) en HTML, lisible sans JavaScript ;
- solution derrière un `<details>` dépliable — indexable par les moteurs, masquée au visiteur qui ne clique pas ;
- JSON-LD `@graph` : `Article` (avec `datePublished` / `dateModified` réels) + `BreadcrumbList` ;
- navigation `rel="prev"` / `rel="next"` entre les jours.

Les pages sont **auto-suffisantes** : les tokens de style sont lus depuis `css/variables.css` et injectés dans une `<style>` unique. Aucune requête CSS, rendu correct sans JS, **≈ 13 ko par page**.

### Reste de la phase SEO

| Livrable | Détail |
|---|---|
| Index paginé `/puzzles/` | 60 archives/page, `rel="prev"`/`next`, schéma `CollectionPage` |
| `sitemap.xml` régénéré | `lastmod` réel par page, URL `/puzzles/`, pagination ; `play`/`battle`/`multi` passent en `weekly` |
| Pré-rendu de l'accueil | Section « Résumé du jour » balisée `SEO-PRERENDER` / `data-seo`, **idempotente**, sans le mot secret |
| `robots.txt` durci | `Disallow` sur `/api/`, `/data.json`, `/.well-known/`, `?reveal=`, `?r=`, `?k=` |
| `llms.txt` → `llms.md` | Extension du standard + format d'URL des archives, endpoints, mentions frWac/Lexique/Certitudes |
| ARD | Doublon `ai-catalog.json` en racine supprimé, outillage réorienté vers `/api/health` (non spoilant) |
| PWA | `manifest.webmanifest` (shortcuts Solo/Archives), icônes SVG + PNG, `apple-touch-icon` |
| Nettoyage | `meta name="title"` (doublon de `<title>`) et `meta keywords` (ignoré par Google) supprimés ; `theme-color` en 2 valeurs selon `prefers-color-scheme` |
| Maillage | Nouvel onglet « Archives » sur les 4 pages |
| CLI | `--publish-seo` ; publication aussi par `--export-web` et le démon, **non bloquante** |

### Choix de conception

- **Anti-spoiler préservé partout** : le pré-rendu publie date, n° de puzzle, coups, durée et indices, jamais le mot.
- **Idempotence** : le pré-rendu remplace de l'intérieur vers l'extérieur et cible par `id` d'ancrage → relancer la génération ne duplique jamais le texte (vérifié : `2 → 2`).
- **Rejet des données invalides** : dates mal formées et puzzles non résolus exclus, plafond de 45 000 URLs.
- **`</` échappé en `<\/` dans le JSON-LD** pour ne jamais fermer prématurément le `<script>`.

---


## 🔐 Sécurité — ce qui change

### 1. Le mot secret ne transite plus en `GET`

```
GET  /api/daily         → current.word = null, mot masqué dans trajectory,
                          top_guesses et l'entrée du jour de history
POST /api/daily/reveal  → { "word": "…" }     seul chemin vers la solution
```

Le POST est volontaire : un crawler, un prefetch de lien ou un `curl` ne peuvent pas tomber sur la solution par accident. L'anti-spoiler est désormais côté serveur, pas en CSS.

### 2. `data.json` ne peut plus atterrir dans le webroot

`export_web_data()` lève `ValueError` si la cible est le webroot **ou l'un de ses sous-répertoires**. Le code écrivait déjà dans `cemantix_data/` — c'est le **README** qui indiquait `volumes/web/data.json`, sans vérification. Doc corrigée + bloc Caddy `@intercepted` (`404` sur `data.json`, historiques, sessions, `.env`, `.git`, `*.py`, `*.log`, `*.bin`) en défense en profondeur.

### 3. Serveur HTTP durci

| Protection | Avant | Après | Variable |
|---|---|---|---|
| Corps de requête | `Content-Length` lu sans plafond | ≤ 32 ko, **validé avant traitement**, sinon `413` | `API_MAX_BODY_BYTES` |
| CORS | `Access-Control-Allow-Origin: *` | liste blanche + `Vary: Origin` | `API_ALLOWED_ORIGIN` |
| Débit | aucun | seau à jetons par IP, `429` + `retry_after`, `/api/health` exempté | — |
| Threads | 1 thread par connexion, illimité | plafond de workers, `503` propre | `API_MAX_WORKERS` |
| En-têtes | aucun | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store` | — |
| Divers | version Python dans `Server` | retirée ; timeout socket 10 s ; écriture tolérante aux déconnexions | `API_SOCKET_TIMEOUT` |

Nouveau module `src/api/ratelimit.py` (thread-safe, mémoire bornée, purge des clés oisives).

### 4. XSS : échappement + fin des gestionnaires injectés

- `escapeHtml()` / `safeNumber()` dans `js/utils.js`, appliqués aux indices, à l'historique, aux listes de coups, à la trajectoire, aux cartes de duel et aux cibles révélées en multijoueur.
- `onclick="copyToClipboard('${mot}')"` et `onclick="window.multiResumeGame('${room}','${clé}')"` supprimés → attributs `data-copy` / `data-resume-room` / `data-delete-room` + **délégation enregistrée une seule fois**. Échapper n'aurait pas suffi : le contexte était du JavaScript, pas du texte.

### 5. Codes multijoueur (bonus hors plan)

En relisant `multi.py` : `room_id` et clés `J1-`/`J2-` n'avaient que **4 chiffres hex** (65 536 valeurs) avec des salons actifs **7 jours** → balayage systématique pour retomber sur une partie ouverte et jouer à la place d'un joueur. Portés à 8 chiffres (`uuid.uuid4`, 4,3 Md, **facteur ×65 536**), vérifié 20 000/20 000 sans collision, comparaison par égalité de chaîne donc rétro-compatible.

### 6. La clé de salon ne reste plus dans l'URL (S7)

`/multi/?r=DUEL-XXXXXXXX&k=J2-YYYYYYYY` : la clé **doit** transiter — c'est le secret d'invitation, sans elle le second joueur n'entre pas. Ce qui n'était pas défendable, c'est qu'elle **y reste** : historique du navigateur, champ d'adresse, captures d'écran, et un lien encore cliquable des heures plus tard. Sur un poste partagé, c'est la prise de contrôle du duel.

Deux précisions qui changent le diagnostic par rapport au plan d'audit :

- la fuite par **`Referer` était déjà colmatée** — `Referrer-Policy: strict-origin-when-cross-origin` est en place côté Caddy *et* côté API, et ne transmet que l'origine vers l'externe ;
- il n'y a **aucun log d'accès** dans le `Caddyfile`, donc pas de clé dans les logs.

Le vecteur réel était l'historique du navigateur, plus la query string du polling.

| Avant | Après |
|---|---|
| `replaceState(…, "?r=…&k=…")` à chaque changement d'état | `stripKeyFromUrl()` ne laisse que `?r=…` (le code de salon n'autorise aucune action) |
| Clé effacée seulement au retour au lobby | Effacée **dès le chargement**, avant même la requête de connexion |
| `GET /api/multi/status?r=…&k=…` (2 pollings) | `POST /api/multi/status`, charge utile dans le corps |
| `handle_multi_get` servait `/api/multi/status` | Ne sert plus aucune route — la voie GET est **fermée**, pas seulement évitée |

Vérifié sur les contrôleurs : `GET` refuse (404) **même avec une clé valide** et ne la renvoie pas, `POST` valide 200, clé invalide 403, salon inconnu 404, et **P2 ne reçoit pas la clé de P1** (seul P1 reçoit la clé d'invitation, c'est voulu).

Le `POST /api/multi/status` n'a pas été écrit pour l'occasion : il **existait déjà** et était simplement inutilisé par le front.

### 7. Fin de la surface globale laissée par les `onclick` (S9)

La passe XSS avait supprimé les `onclick="…"` mais pas les quatre fonctions qu'ils appelaient : `window.copyToClipboard`, `window.showConfirmDialog`, `window.multiResumeGame`, `window.multiDeleteGame`.

Avant de toucher quoi que ce soit, vérification que rien ne dépend encore de ces globals :

| Contrôle | Résultat |
|---|---|
| `onclick=` dans les 4 pages | **0** |
| Appels `window.<ces quatre noms>` dans tout `volumes/web/` | **0** |
| Appelants réels | `import` ES modules (battle, game, multi) + délégation `data-copy` |

Les deux fonctions de `multi.js` redeviennent des déclarations de fonction du module — le hoisting couvre leur usage depuis `initRoomActions`, qui ne s'exécute qu'au clic. Intérêt : une CSP `script-src 'self'` stricte reste tenable même si un `onclick` inline réapparaissait, et l'API interne du jeu n'est plus atteignable depuis la console.


## ⚡ Performance — ce qui change

Le gaspillage identifié n'était pas du poids lourd mais des **requêtes et des calculs payés pour rien**. Chiffres mesurés, pas estimés.

### Une seule feuille CSS par page

Chaque page chargeait 5 à 6 `<link>` CSS. `tools/build_css_bundles.py` (136 l.) en génère un par page dans `css/dist/`, sans outil de build ni dépendance :

| Page | Avant | Après |
|---|---|---|
| `index` | 48 054 o · 5 requêtes | 37 586 o · **1 requête** |
| `play` | 43 453 o · 5 requêtes | 33 829 o · **1 requête** |
| `battle` | 60 844 o · 6 requêtes | 46 489 o · **1 requête** |
| `multi` | 59 658 o · 6 requêtes | 45 124 o · **1 requête** |

> **Précision honnête :** le plan d'audit annonçait du « CSS mort » téléchargé. C'était faux — chaque page ne chargeait déjà que les feuilles utiles. Le gain porte donc sur le **nombre de requêtes**, pas sur le poids. En HTTP/2 les requêtes sont multiplexées : le bénéfice est réel mais borné, et c'est écrit tel quel dans le script.

Deux garde-fous intégrés : le script **refuse de générer** si une source contient un `url()` (la concaténation casserait les chemins relatifs — vérifié, le CSS du projet n'en contient aucun), et le mode `--check` échoue si les bundles sont périmés, pour une éventuelle étape de CI.

### Code-splitting JavaScript

`js/app.js` importait **statiquement** `dashboard.js`, `game.js` et `battle.js`. Un `import` statique fait télécharger **et évaluer** le module même quand la branche `if` qui l'utilise ne s'exécute jamais : depuis `/play/`, `dashboard.js` + `trajectory.js` + `countdown.js` coûtaient **~27 ko sur les ~93 ko** du graphe statique (29 %), analysés pour rien. Les modules d'écran passent en `import()` dynamique, chargé seulement si la vue est présente dans le DOM — depuis `/play/`, le graphe tombe à ~38 ko.

Au passage, suppression de la branche Battle de `app.js` : **morte**, puisque `/battle/` charge `js/battle.js` directement et que ce module s'auto-initialise.

### Pollings et calculs suspendus

| Problème | Coût réel | Correction |
|---|---|---|
| Salle d'attente multi : `setInterval` fixe de 2 s | **~1 800 requêtes/heure** d'onglet ouvert, y compris en arrière-plan | Adaptatif 2 s → 10 s (réinitialisé à chaque changement d'état), suspendu onglet masqué |
| Dashboard : resynchronisation 30 s | Requêtes + re-rendu complet de ~130 lignes, pour des données qui ne bougent qu'à minuit | Suspendu onglet masqué ; re-rendu sauté si le gabarit est identique |
| `Intl.DateTimeFormat` reconstruit **dans le tick** | **86 400 allocations/jour** et par onglet, pour l'objet le plus coûteux de l'API Intl | Hoisté hors de la boucle |
| Recherche de l'historique | 5 reconstructions complètes du DOM pour taper « 2026 » | Debounce 150 ms |

### Deux bugs préexistants corrigés en chemin

- **`stopPolling()` appelait `clearTimeout` sur un `setInterval`** — ça ne le stoppe pas. Le polling de la salle d'attente continuait donc de tourner après le retour au lobby. Remplacé par une chaîne de `setTimeout`.
- **Le compte à rebours affichait `24:00:00`** pendant la première seconde du jour : à minuit pile, `currentSeconds == 0` donnait un reste de 86 400 s. Corrigé et vérifié sur les **86 400 secondes** de la journée, plus aucune valeur supérieure à 23.

### Le Caddyfile est enfin versionné

Il **n'existait nulle part** dans le dépôt — seulement en prose dans le README, ce qui avait laissé la configuration diverger du code sans que personne s'en aperçoive. Trois incohérences trouvées et corrigées au passage :

- le README documentait `X-Frame-Options: SAMEORIGIN` alors que le serveur envoie **`DENY`** ;
- les deux CSP portaient `frame-ancestors 'self'` tout en interdisant l'encadrement ;
- **`@html path *.html` ne matche pas `/puzzles/2026-10-26/`** (URL sans extension servie par `try_files`) : les pages d'archives partaient donc **sans `Cache-Control`**. Un bloc `@pages` les couvre désormais, ainsi que `sitemap.xml`, `robots.txt`, `llms.md` et `.well-known/*`.

Politique de cache alignée sur la règle du projet — **`no-cache, must-revalidate` + ETag, aucun `?v=`** : seules les polices, immuables par nature, gardent un `max-age` d'un an. Les images y passent aussi, car sans revalidation un `og-image.jpg` remplacé resterait invisible, y compris pour les aperçus sociaux.

### Trois outils de contrôle sans dépendance

Ni Node, ni Pillow, ni ImageMagick, ni `pytest` dans l'environnement — d'où trois scripts en stdlib, tous en code de sortie `1` quand ça cloche (exploitables en CI) :

| Outil | Rôle |
|---|---|
| `tools/build_css_bundles.py` | Bundles CSS par page + `--check` de péremption |
| `tools/check_og_image.py` | Poids et dimensions réels vs balises `og:image` |
| `tools/check_js_balance.py` | Équilibre des délimiteurs JS, faute de `node --check` |

---

## ✅ Validation

| Test | Résultat |
|---|---|
| Masquage du mot secret (12 assertions : `word`, `trajectory`, `top_guesses`, `history`, cas vides) | **12/12** |
| Serveur HTTP réel (port libre, vraies requêtes) : en-têtes, `no-store`, CORS liste blanche vs origine ennemie, `413` avant allocation, `429` + `retry_after`, exemption `health`, POST valides | **16/16** |
| Charges utiles XSS (`<img onerror>`, `'><script>`, `" onmouseover`, fermeture de balise, fermeture de chaîne JS) | **5/5 neutralisées** |
| Génération SEO (10 assertions : 1 `<h1>`, canonical absolue, JSON-LD parsable, pas de double slash, dates invalides exclues, HTML intact, reset propre) | **10/10** |
| **Équivalence du CSS minifié** (comparaison canonique des règles, imbrication `@media`/`@keyframes` comprise, 8 fichiers sources) | **519 règles, 0 perdue** |
| **Calcul du compte à rebours sur les 86 400 s de la journée** | **OK** (aucune valeur > 23) |
| Idempotence du pré-rendu | **OK** (`2 → 2`) |
| Garde du webroot (racine + sous-répertoire refusés, `DATA_DIR` accepté) | **OK** |
| Entropie des codes (`uuid4`, 20 000 tirages) | **OK** (0 collision) |
| Routes multijoueur : `GET` refuse même avec une clé valide et ne la renvoie pas, `POST` valide 200 / clé invalide 403 / salon inconnu 404, P2 ne reçoit pas la clé de P1 | **9/9** |
| `py_compile` sur les 9 modules Python · JSON du manifeste et de l'ARD · `--check` des bundles | **OK** |
| `check_js_balance` sur les 9 modules JS (après correction de l'outil, qui produisait 7 faux positifs) | **9/9 OK** |
| `check_js_balance` sur 19 cas de référence (13 valides, 6 fautes réelles) | **13/13 acceptés · 5/6 détectées** |
| Non-régression front : plus aucune occurrence de `reveal=true`, les 2 appelants sur le POST, 4 pages avec 1 `<h1>` / 1 canonical / 1 JSON-LD / **1 feuille CSS** | **OK** |


---

## ⚠️ À faire après le merge (bloquants)

1. **Régénérer les archives en production** — le `daily_history.json` local est absent, le sitemap versionné n'a donc que 5 URLs :
   ```bash
   docker compose run --rm cemantix --publish-seo
   ```
2. **Déployer le `Caddyfile` versionné** (monté en lecture seule dans le conteneur Caddy) et le recharger :
   ```bash
   docker exec <caddy> caddy reload --config /etc/caddy/Caddyfile
   ```
   ⚠️ **Tester d'abord la CSP en `Content-Security-Policy-Report-Only`** — c'est le seul point non exécuté ici (pas de navigateur dans l'environnement). `style-src 'unsafe-inline'` reste nécessaire : les 13 `style="…"` posés par les gabarits JS sont des valeurs codées en dur, jamais des données utilisateur, donc sans risque fonctionnel — mais une coquille dans la chaîne de directive casserait le thème.
3. **Vérifier visuellement les 4 pages** : le CSS est désormais servi depuis `css/dist/`, produit par un minifieur maison. L'équivalence structurelle est validée (519 règles, 0 perdue), mais le rendu visuel n'a pas pu être observé ici.
4. **Ordre des directives Caddy** : le `reverse_proxy /api/*` et le bloc `@intercepted` doivent précéder le `handle` statique, sinon les fichiers restent servibles.
5. **Soumettre** `https://cemantix.cyril-randon.fr/sitemap.xml` à Search Console et Bing.
6. **Étape de build désormais obligatoire** : après toute modification de `css/*.css`, relancer `python tools/build_css_bundles.py` avant de déployer (ou `--check` en CI).
7. **Versionner `.gitignore`** — il est toujours non suivi (`?? .gitignore`) alors qu'il protège `volumes/web/data.json` (qui contient les solutions) et `cemantix_data/*.json` d'un commit accidentel, et qu'il exclut `.idea/` de tous les collaborateurs. Non committé ici pour ne pas placer un commit après celui du changelog ; à faire au premier commit de la branche suivante.



### Vérifications post-déploiement
```bash
# Le mot du jour ne doit apparaître nulle part :
curl -s https://cemantix.cyril-randon.fr/api/daily | grep -i '"word"' | head

# Les fichiers de données doivent renvoyer 404 :
for f in data.json daily_history.json web_sessions.json; do
  printf '%s -> ' "$f"
  curl -s -o /dev/null -w '%{http_code}\n' "https://cemantix.cyril-randon.fr/$f"
done

# En-têtes attendus :
curl -sI https://cemantix.cyril-randon.fr/ | grep -iE 'content-security|strict-transport|x-frame'
```

---


## 🚧 Limites connues et reste à faire

**Non traité dans cette PR** (volontairement, ou faute d'outil dans l'environnement) :

- **S8 — API de jeu exposée au public** : le rate-limiting par IP est en place, mais il n'y a toujours pas de chemin privé ni d'authentification sur les endpoints de jeu. C'est un choix assumé pour un jeu public ; à réviser si l'API sert d'autres clients à l'avenir.
- **Compression de l'`og-image`** : toujours à **3 091 777 o** (2752×1536 pour des balises qui annoncent 1200×630). Ni Pillow ni ImageMagick dans l'environnement : `tools/check_og_image.py` mesure et alerte, mais la compression reste une commande manuelle à lancer (`convert … -resize 1200x630 -quality 82`). Écrire un encodeur JPEG en stdlib aurait été déraisonnable, et le SVG est exclu d'office : les crawlers sociaux (Facebook, X, LinkedIn) ne l'acceptent pas comme `og:image`.
- **Phase 2 partielle** : restent les tâches 2.7 (`content-visibility` + contenants CSS), 2.2 avancée (vraie minification avec outil de build) et le `DocumentFragment` de la 2.6 — ce dernier a été **écarté après vérification** : `renderHistoryTable()` construit déjà un gabarit et fait une seule affectation `innerHTML`, l'ajout n'aurait rien changé.
- **Purge des sessions** dans `GameManager` : le TTL existe (`_cleanup_stale`, 2 h / 7 j) mais n'est déclenché que sur certaines écritures ; les fichiers de session peuvent croître entre-temps.
- **Aucun test automatisé en dépôt** : les ~60 assertions listées ci-dessus ont été exécutées via des scripts temporaires hors commit. Les transformer en `tests/` (`unittest` + stdlib suffisent, pas de `pytest` requis) est le chantier naturel suivant.
- **Validation visuelle et Caddy impossibles ici** : pas de navigateur, pas de `node`, pas de binaire `caddy`, et `zoneinfo`/`Europe/Paris` absent sous Windows (sans effet dans le conteneur, qui installe `tzdata`). La syntaxe du `Caddyfile` est vérifiée par équilibre des accolades et comparaison directive par directive avec le README (25/25 identiques), **pas** par `caddy validate`.

**Question du plan désormais tranchée :** l'audit prévoyait 1 fichier CSS minifié avec `?v=hash`, alors que le changelog documentait la **suppression volontaire** des `?v=` au profit des ETag Caddy. C'est la seconde option qui a été retenue, conformément à la politique du projet : **bundle pré-généré, sans hash, `no-cache, must-revalidate` + ETag**. Introduire un `max-age` sur ce qui change obligerait à ressusciter les `?v=`.

**Divers corrigé au passage :** un bloc de code du README était cassé (backtick + caractère backspace au lieu d'une barrière ```` ```bash ````) ; `log_message()` était réduit à `pass`, ce qui rendait tout abus invisible — les requêtes sont désormais tracées avec l'IP cliente.

---

## 📦 Fichiers notables

| Fichier | ± | Rôle |
|---|---|---|
| `src/services/seo.py` | +797 | Générateur d'archives, d'index, de sitemap et de pré-rendu |
| `src/api/server.py` | +175/−19 | Durcissement HTTP (corps, CORS, rate-limit, threads, en-têtes) |
| `src/api/routes/system.py` | +82/−16 | `_scrub_secret()` + `POST /api/daily/reveal` |
| `Caddyfile` | +105 | Configuration serveur versionnée (CSP, en-têtes, cache, `@intercepted`) |
| `tools/build_css_bundles.py` | +136 | Bundles CSS par page + `--check` de péremption |
| `tools/check_og_image.py` | +112 | Diagnostic poids / dimensions de la vignette sociale |
| `tools/check_js_balance.py` | +89 | Contrôle syntaxique JS faute de `node` |
| `src/api/ratelimit.py` | +68 | Seau à jetons par IP |
| `volumes/web/js/multi.js` | +74/−12 | Polling adaptatif + suspension onglet masqué |
| `volumes/web/js/dashboard.js` | +64/−39 | Debounce, re-rendu conditionnel, polling suspendu, POST reveal |
| `volumes/web/js/countdown.js` | +41/−12 | Formatter hoisté, pause hors écran, correction `24:00:00` |
| `volumes/web/css/dist/*.css` | +1 633 | 4 bundles générés (à ne pas éditer à la main) |
| `volumes/web/js/utils.js` | +66 | `escapeHtml()`, `safeNumber()`, délégation globale |
| `tools/generate_icons.py` | +77 | Icônes PNG en stdlib (`zlib`), sans Pillow |
| `volumes/web/manifest.webmanifest` | +49 | PWA installable |
| `volumes/web/llms.md` | +55 | Documentation agents IA |

---

## 📝 Commits

### SEO (phases 3.1 → 3.5)
| Commit | Objet |
|---|---|
| `f09f73a` | `robots.txt`, `llms.md`, manifeste ARD |
| `487f786` | Pages d'archives par date, index paginé, sitemap dynamique |
| `9f18845` | Nettoyage du balisage, manifeste PWA, icônes, maillage |
| `da2dbf8` | Documentation README + option `--publish-seo` |
| `e4cce9b` | Pré-rendu côté serveur du résumé du jour |
| `e4c11f7` | `sitemap.xml` régénéré (URL `/puzzles/`, `lastmod` à jour) |
| `531ee09` | Politique de cache Caddy pour archives et sitemap |
| `c72fed7` | Changelog SEO |

### Sécurité (phases 1.1 → 1.8)
| Commit | Objet |
|---|---|
| `8e53072` | Fuite du mot du jour via `?reveal=true` |
| `14e520a` | Serveur HTTP : corps plafonné, CORS, rate-limiting, en-têtes |
| `02ff699` | `data.json` interdit dans le webroot |
| `52fe994` | Échappement systématique des données `innerHTML` |
| `9861d37` | Codes de salon et clés multijoueur portés à 32 bits |
| `1dd27ce` | CSP et en-têtes Caddy, posture de sécurité |
| `7df75d4` | Régression UX induite (mot effacé au polling) |
| `2ade866` | Changelog sécurité |
| `29dd3f9` | Clé de salon retirée de l'URL, polling en POST (S7) |
| `a13d73d` | Documentation README de la clé de salon |
| `86563db` | Changelog clé de salon |
| `d32f209` | Suppression de la surface globale `window.*` (S9) |

### Performance (phase 2, partielle)
| Commit | Objet |
|---|---|
| `f709269` | Cache aligné sur `no-cache` + bloc `@pages` pour les URLs sans extension |
| `1e22655` | `Caddyfile` versionné à la racine |
| `786fe7b` | Diagnostic `og-image` + meta d'image de partage complètes |
| `78b3e55` | Polling de la salle d'attente adaptatif et suspendu |
| `30b217e` | Formatter `Intl` hoisté + compte à rebours hors écran + bug `24:00:00` |
| `fcc1c4e` | Debounce de la recherche + re-rendu conditionnel de l'historique |
| `cfe36b0` | Polling 30 s du tableau de bord suspendu onglet masqué |
| `161037d` | `import()` dynamique des modules d'écran |
| `43a1d18` | Une feuille CSS par page (bundles générés) |
| `195dbb9` | Procédure de build des bundles dans le README |
| `80e8b8e` | `check_js_balance` ne signale plus les fichiers valides |
| `d2a3d33` | Taille réelle du graphe d'import JS (93 ko, pas 67) |

> Les 3 commits d'accessibilité en tête de branche (`95a3de3`, `d4de2ca`, `e25c319`) proviennent de la branche `fix/accessibilite-contraste-pagespeed` déjà validée ; ils sont inclus ici car la branche en découle.
>
> **Le dernier commit de la branche est un commit de changelog** — la convention « le changelog est toujours dernier » est respectée. Les commits de changelog par phase sont `c72fed7` (SEO), `2ade866` et `86563db` (sécurité), `621428c` / `2408312` / `c2af240` / `3025d33` (performance et outils).

---
