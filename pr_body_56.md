# Pull Request #56 : fix(seo): les ressources de découverte agents IA deviennent livrables (SEO-22 → SEO-25)

## 🎯 Contexte & Objectif

L'audit de découvrabilité agentique de `cemantix.cyril-randon.fr` remontait **deux erreurs bloquantes** :

| Audit | Message remonté | Gravité |
|---|---|---|
| llms.txt | « Il manque un en-tête H1 obligatoire dans le fichier » et « le fichier ne semble pas contenir de liens » | Erreur |
| Catalogue ARD | « Malformed JSON in manifest: `SyntaxError: Unexpected token '<', "<!DOCTYPE "` » sur `/.well-known/ai-catalog.json` | Erreur |

**Les fichiers du dépôt'étaient pourtant conformes** : `volumes/web/llms.txt:1` commence bien par
`# Cémantix Solver` et porte vingt liens Markdown ; `volumes/web/.well-known/ai-catalog.json` est un
JSON valide au schéma ARD, déjà contrôlé par `tools/check_seo.py`. Un audit qui ne voit **ni** un
en-tête H1 **ni** un seul lien dans un fichier qui en contient vingt ne lit pas ce fichier.

**Le second message nomme la cause** : `Unexpected token '<'` sur un JSON attendu = la réponse
commence par `<!DOCTYPE html>`. Le serveur répondait **la page d'accueil, en HTTP 200**, aux deux
URLs. L'audit llms.txt, qui analyse alors du HTML comme du Markdown, ne peut trouver ni ligne
`# Titre`, ni lien Markdown.

Cette PR ne réécrit donc **aucun contenu** : elle répare **la livraison** et empêche la panne de
revenir en silence.

---

## 🔎 Diagnostic mesuré sur le dépôt

| Cause | Ce que lit l'audit | Correctif |
|---|---|---|
| `robots.txt` tenait `Disallow: /.well-known/` : catalogue ARD, `ard.json` et `agent-card.json` interdits de lecture à tout crawleur conforme (Google, GPTBot, ClaudeBot) | manifeste « schéma non valide », sans jamais mentionner le refus de crawl | `SEO-22` |
| Le proxy repliait toute URL inconnue sur `/index.html` (soft 404) et ne fixait le type MIME d'aucune ressource agent | `Unexpected token '<'` côté JSON, « ni en-tête H1 ni liens » côté Markdown | `SEO-23` |
| Rien ne vérifiait en CI que les ressources annoncées existent et sont lisibles | la panne ne remontait qu'à Google, jamais à la CI | `SEO-24` |
| Seul `llms.txt` déclarait les hubs `/mot-du-jour/` et `/methode/` (`SEO-17`, `SEO-18`) | un agent entrant par `llms.md` ou les compétences ne les découvrait pas | `SEO-25` |

**Règle de conception posée** : une ressource de découverte ne doit jamais être masquée par un repli
applicatif. Un 404 net est un diagnostic ; un 200 HTML est un mensonge que l'audit interprète comme
un contenu invalide.

> Le repli `=404` avait déjà été posé sur `main` par `b9ee95e` (*suppression du soft-404 caddy*,
> PR #54), pour une autre raison (crawl-trap de concaténation de chemins relatifs). Cette PR la
> **verrouille par test** — c'est exactement le garde-fou qui manquait pour qu'il ne puisse pas
> régresser — et traite les trois causes que `b9ee95e` ne couvrait pas.

---

## 🛠️ Organisation des Commits

1. **`d9c7f65 fix(seo): laisser les agents lire les manifestes et livrer un vrai 404`** :
   - **`volumes/web/robots.txt`** : suppression du `Disallow: /.well-known/`, remplacé par quatre
     `Allow` explicites (`/.well-known/`, `/llms.txt`, `/llms.md`, `/agent-skills.md`) avec le motif
     du choix écrit dans le fichier. Les blocages utiles (`/api/`, `/panier-9x/`, données brutes,
     paramètres spoilants) sont conservés.
   - **`README.md` (référence Caddy)** : trois blocs `handle @agents_json` / `@agents_txt` /
     `@agents_md`, déclarés **avant** le `handle` général (les blocs `handle` sont exclusifs et
     évalués dans l'ordre d'écriture), qui fixent le type MIME contractuel de chaque ressource.
   - **`local/nginx/cemantix.local.conf`** : le miroir de test applique le même contrat
     (`types {}` vide + `default_type`, seul moyen nginx d'imposer un type sans dupliquer
     l'en-tête — `add_header Content-Type` en ajouterait un second, et deux `Content-Type` rendent
     un JSON illisible côté client).
   - **`local/smoke-test.sh`** : section **1b** sur les six `Content-Type`, le premier caractère de
     `llms.txt` (`# `) et du catalogue (`{`), l'absence du `Disallow`. Un simple `200` ne suffit
     plus : le soft 404 HTML passait l'ancien test. Attente erronée corrigée au passage
     (`/ai-catalog.json` attendu en `200` alors que le chemin spécifié par ARD est
     `/.well-known/ai-catalog.json`).

2. **`b5f9680 feat(seo): declarer les hubs mot-du-jour et methode aux agents`** :
   - `volumes/web/llms.md` : deux entrées de navigation (`/mot-du-jour/`, `/methode/`).
   - `volumes/web/agent-skills.md` : « Compétence 4 — Mot du jour et lecture des indices » (source à
     citer pour le puzzle en cours, conduite anti-spoiler, renvoi méthode).

3. **`45272e3 test(seo): gardes de decouvrabilite des ressources agents`** :
   - **`tools/check_seo.py`** : nouveau contrôle `check_decouvrabilite_agents()`, branché dans
     `main()` — aucune ressource d'agent interdite par `robots.txt` (motif `Disallow` interprété à la
     RFC 9309, joker `*` compris), et toute URL `cemantix.cyril-randon.fr` citée par `llms.txt`,
     `llms.md`, `agent-skills.md`, `ai-catalog.json` ou `agent-card.json` doit être livrable :
     fichier du webroot, route d API, ou page produite au démarrage listée dans `URLS_GENREES`
     (`/mot-du-jour/`, `/methode/`, `/puzzles/…`, `/sitemap.xml`, `/indexnow-key.txt`) pour qu'un
     dépôt fraîchement cloné ne casse pas.
   - **`tests/test_agent_delivery.py`** : 10 tests, stdlib seule, **réutilisant les fonctions du
     contrôle** pour que CI et tests ne puissent pas diverger.
   - **`local/run_seo_tests.py`** : harnais **réparé** — il ne tournait plus depuis le découpage de
     la chaîne SEO (jalon M4), son paquet `src.services` factice ne déclarant que `seo.py` ; les
     modules sont maintenant enregistrés dans l'ordre des dépendances (`gtm`, `layout_sync`, puis les
     sept modules SEO).

4. **`1f66ec1 docs(seo): evolution 2026-11-09 decouvrabilite agents et changelog`** :
   - `docs/roadmap/2026-11-09-decouvrabilite-agents-ia/{01-plan.md,02-avancement.md}`, ligne d'index
     de la roadmap, entrée `CHANGELOG.md`.

5. **`470c140 Merge branch main`** : mise à jour sur `origin/main` (PR #53, #54, #55). Deux conflits
   résolus — `README.md` (le `=404` arrivé des deux côtés, commentaire fusionné, liste de vues à
   jour avec `/defi`) et `CHANGELOG.md` (sections conservées dans l'ordre chronologique inverse).

---

## 🧱 Le contrat de livraison posé (`SEO-23`)

| Ressource | Content-Type contractuel | Si le fichier manque |
|---|---|---|
| `/llms.txt` | `text/plain; charset=utf-8` | 404 |
| `/llms.md`, `/agent-skills.md` | `text/markdown; charset=utf-8` | 404 |
| `/.well-known/ai-catalog.json`, `/.well-known/ard.json`, `/.well-known/agent-card.json` | `application/json; charset=utf-8` | 404 |

---

## 🧪 Vérifications exécutées (Python 3.14, stdlib seule)

```text
py tools/check_seo.py
  [OK] Audit SEO reussi sur 5 pages principales (title, description, canonical, OG, JSON-LD).
  [OK] Audit des pages hub generees reussi (mot-du-jour, methode).
  [OK] Audit agentique reussi (llms.txt H1 + liens, catalogue ARD conforme).
  [OK] Decouvrabilite agents : robots.txt ne bloque aucune ressource, aucun lien mort annonce.
  [OK] Anti-fuite GTM : aucun ID reel commité dans volumes/web (placeholder uniquement).

py local/run_seo_tests.py            ->  tests= 58 failures= 0 errors= 0   (4 modules)
py -m unittest discover -s tests -p "test_agent_delivery.py"  ->  10 tests verts
py tools/check_docs.py               ->  === OK ===   (4 annoncés / 4 réels)
py tools/check_og_image.py           ->  [OK] Conforme
py tools/build_css_bundles.py --check -> 11 blocs à jour
bash -n local/smoke-test.sh          ->  syntaxe OK
```

**Le garde-fou a prouvé sa valeur deux fois pendant la conception** :

1. il a rattrapé mes propres liens `mot-du-jour` / `methode` ajoutés dans `agent-skills.md` — le
   motif d'URL capturait le backtick fermant du code en ligne, signalé comme « lien mort » ;
2. il échoue bien quand on réinjecte `Disallow: /.well-known/` dans un `robots.txt` de synthèse
   (`test_le_garde_detecte_un_disallow_well_known`).

---

## 🚨 Recette de déploiement sur le VPS (obligatoire pour voir l'audit disparaître)

Le `Caddyfile` réel n'est **pas versionné** (`.gitignore`) : la référence du `README.md` en tient
lieu, et c'est elle que cette PR corrige. Après la fusion :

```bash
git pull --ff-only && grep -n 'Allow: /.well-known/' volumes/web/robots.txt   # doit répondre ligne ~12
docker compose build cemantix_web cemantix_worker
docker compose up -d cemantix_web cemantix_worker      # ensure_seo_published() au démarrage
docker compose run --rm cemantix --publish-seo         # régénère archives, hubs, sitemap, ARD, docs agents
docker compose run --rm cemantix --submit-sitemap      # resoumet le sitemap à la Search Console
```

Puis ajouter au `Caddyfile`, au niveau du matcher `@sitemap` (bloc copié du `README.md`) :

```caddy
    @agents_json path /.well-known/ai-catalog.json /.well-known/ard.json /.well-known/agent-card.json
    @agents_txt path /llms.txt
    @agents_md path /llms.md /agent-skills.md
    handle @agents_json {
        header Content-Type "application/json; charset=utf-8"
        header Cache-Control "no-cache, must-revalidate"
        file_server
    }
    handle @agents_txt {
        header Content-Type "text/plain; charset=utf-8"
        header Cache-Control "no-cache, must-revalidate"
        file_server
    }
    handle @agents_md {
        header Content-Type "text/markdown; charset=utf-8"
        header Cache-Control "no-cache, must-revalidate"
        file_server
    }
```

Valider **avant** de recharger (une directive inconnue fait refuser toute la config par Caddy) :

```bash
docker exec <caddy> caddy validate --config /etc/caddy/Caddyfile
docker exec <caddy> caddy reload  --config /etc/caddy/Caddyfile
```

Contrôle final, les six réponses attendues :

```bash
curl -sI https://cemantix.cyril-randon.fr/llms.txt                   | grep -iE '^HTTP|content-type'   # 200, text/plain
curl -sI https://cemantix.cyril-randon.fr/.well-known/ai-catalog.json| grep -iE '^HTTP|content-type'   # 200, application/json
curl -sI https://cemantix.cyril-randon.fr/agent-skills.md            | grep -iE '^HTTP|content-type'   # 200, text/markdown
curl -sI https://cemantix.cyril-randon.fr/inexistant                 | head -1                          # 404
curl -s  https://cemantix.cyril-randon.fr/robots.txt | grep -i well-known    # Allow:, jamais Disallow:
curl -s  https://cemantix.cyril-randon.fr/llms.txt | head -1                 # # Cémantix Solver
```

Côté Google, les caches ne suivent pas le déploiement : **Search Console → Vérification du fichier
robots.txt** (« Tester la demande » sur `/.well-known/ai-catalog.json`), puis **Inspection d'URL →
Tester la version publiée** sur les deux ressources, avant de rejouer l'audit.

---

## ♻️ Rollback, risques & limites

| Point | Analyse |
|---|---|
| Rollback | `git revert` des commits : `robots.txt` et la référence Caddy reviennent à l'état précédent. Aucun effet sur les URLs, les données ou le jeu. |
| Le `=404` casse-t-il une URL ? | Non : les cinq vues, les hubs et les archives sont de vrais fichiers ou répertoires, et `try_files` conserve `{path}/index.html` puis `{path}/`. Déjà en production depuis la PR #54, sans régression signalée. |
| Un `handle` agents mal placé ne sert jamais | Les blocs `handle` sont exclusifs et ordonnés : le test `test_reference_caddy_declare_le_bloc_des_ressources_agents` verrouille la présence des trois blocs dans la référence. |
| Un `Allow` explicite inciterait-il à indexer `/llms.txt` ? | Non : ces ressources ne sont pas des pages, n'entrent pas dans le sitemap et ne portent aucune balise `noindex` ; elles ne sont listées qu'en `Allow`, jamais en `Disallow`. |
| Limite assumée | Le poste de développement n'a pas d'accès réseau : la production n'a pas pu être sondée. Cette PR répare la référence et les gardes ; la recette ci-dessus valide côté serveur. Si les six `curl -sI` sont conformes alors que l'audit échoue encore, la cause est externe (WAF ou mode challenge répondant à la place de Caddy). |
| Périmètre non touché | Aucune URL de page, aucun contenu de jeu, aucune donnée, aucune migration SQL. |