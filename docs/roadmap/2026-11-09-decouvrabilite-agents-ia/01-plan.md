# 🔍 Plan — Livraison des ressources de découverte aux agents IA : `llms.txt` et catalogue ARD

> **Évolution :** [2026-11 · Découvrabilité agents IA](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ce fichier décrit **quoi faire et comment le vérifier**, sans état d'avancement.
> **Branche de travail :** `fix/livraison-ressources-agents-ia`
> **Base de référence :** `main` @ `2d271aa` (fusion PR #52, jalon M15)
> **Date de conception :** 09/11/2026
> **Périmètre exclusif :** livraison et découvrabilité des ressources lues par des robots (`volumes/web/robots.txt`, `volumes/web/llms.md`, `volumes/web/agent-skills.md`, référence Caddy du `README.md`, `local/nginx/cemantix.local.conf`, `local/smoke-test.sh`, `tools/check_seo.py`, `tests/`). Aucune URL de page ne change, aucun contenu de jeu ni aucune donnée n'est touché.

**Convention de lecture :** chaque finding porte un identifiant permanent, `SEO-22` à `SEO-25`.
Les identifiants `SEO-01` à `SEO-12` sont attribués par l'évolution
[Sécurité, SEO, performance, qualité](../2026-10-02-securite-seo-performance/01-plan.md),
`SEO-13` à `SEO-16` par [Titres d'archives](../2026-10-04-seo-titres-archives/01-plan.md) et
`SEO-17` à `SEO-21` par [Tendance Google](../2026-10-05-seo-tendance-mot-du-jour/01-plan.md) :
aucun n'est réutilisé ici.

---

## 0. Donnée d'entrée : l'audit agentique remonté en production

Deux erreurs relevées par l'audit de découvrabilité (audit llms.txt et audit du schéma ARD) :

| Audit | Message remonté | Gravité |
|---|---|---|
| llms.txt | « Il manque un en-tête H1 obligatoire dans le fichier » et « le fichier ne semble pas contenir de liens » | Erreur |
| Catalogue ARD | « Malformed JSON in manifest: Unexpected token `<`, `<!DOCTYPE ` … is not valid JSON » sur `/.well-known/ai-catalog.json` | Erreur |

**Les deux fichiers du dépôt sont conformes.** `volumes/web/llms.txt:1` commence bien par
`# Cémantix Solver` et porte vingt liens Markdown ; `volumes/web/.well-known/ai-catalog.json`
est un JSON valide conforme au schéma ARD (contrôlé par `tools/check_seo.py`). Un audit qui ne
voit **ni** un en-tête H1 **ni** un seul lien dans un fichier qui en contient vingt ne lit pas
ce fichier : il lit autre chose.

**Le message ARD est la clé.** `Unexpected token '<'` sur un fichier attendu en JSON signifie
que la réponse commence par `<!DOCTYPE html>` : le serveur a répondu **la page d'accueil**, en
HTTP 200, aux deux URLs. L'audit llms.txt, qui analyse alors du HTML comme du Markdown, ne peut
trouver ni ligne « # Titre », ni lien Markdown.

---

## 1. Diagnostic mesuré sur le dépôt

| Constat | Preuve |
|---|---|
| `robots.txt` interdit la lecture de tout `/.well-known/` : un crawleur conforme (Google, GPTBot, ClaudeBot) n'a pas le droit d'ouvrir le catalogue ARD, `ard.json` ni la carte d'agent | `git show HEAD:volumes/web/robots.txt` → ligne 11 `Disallow: /.well-known/` |
| La référence Caddy de production replie toute URL inconnue sur la page d'accueil : un manifeste absent du webroot est livré en HTML 200 (soft 404) au lieu d'un 404 | `git show HEAD:README.md` → `try_files {path} {path}/index.html {path}/ /index.html` |
| Le miroir nginx local, lui, renvoie bien un vrai 404 : les deux configurations divergeaient | `local/nginx/cemantix.local.conf` → `try_files $uri $uri/index.html $uri/ =404`, et son commentaire « un `try_files … /index.html` transforme chaque URL inconnue en 200 (soft 404) : mauvais pour le crawl » |
| Aucun texte de référence ne fixe le type MIME des ressources agents, alors que le catalogue ARD déclare lui-même `text/markdown; profile="urn:air:agent-skills"` | `README.md`, bloc Caddy version `main` : uniquement des `Cache-Control` sur `@sitemap`, aucun `Content-Type` |
| Rien ne vérifie en CI que les ressources annoncées sont livrables : `check_seo.py` validait le **contenu** des manifestes, jamais leur **accessibilité** ni les URLs qu'ils annoncent | `tools/check_seo.py` version `main` : `check_agentique()` s'arrête à la validité du schéma et à l'existence de deux fichiers |
| Le smoke test local validait un simple `200` : le soft 404 HTML passait donc comme un succès, et il attendait même un `200` sur `/ai-catalog.json`, fichier qui n'existe pas — le chemin spécifié par ARD est `/.well-known/ai-catalog.json` | `local/smoke-test.sh` version `main` : boucle `for pair in … "/ai-catalog.json:200"` |
| Seul `llms.txt` déclarait les hubs `/mot-du-jour/` et `/methode/` ; `llms.md`, `agent-skills.md` et la carte d'agent les ignoraient | `grep -c "mot-du-jour" volumes/web/llms.md volumes/web/agent-skills.md` sur `main` → `0` et `0` |

---

## 2. Matrice des findings & correctifs

| # | Sév. | Composant | Problème constaté | Correctif spécifié | Critère de vérification |
|---|---|---|---|---|---|
| **SEO-22** | 🔴 | `volumes/web/robots.txt` | `Disallow: /.well-known/` : les manifestes de découverte sont illisibles par les robots conformes, donc déclarés « non valides » alors que leur contenu est irréprochable | Suppression du `Disallow`, `Allow` explicites sur `/.well-known/`, `/llms.txt`, `/llms.md` et `/agent-skills.md`, motif du choix commenté dans le fichier ; les blocages utiles (`/api/`, `/panier-9x/`, données brutes, paramètres spoilants) restent | `python tools/check_seo.py` vert (nouveau contrôle `check_decouvrabilite_agents`) ; `python -m unittest tests.test_agent_delivery -v` vert |
| **SEO-23** | 🔴 | Proxy de livraison (référence Caddy du `README.md`, miroir nginx local) | Toute URL inconnue répond la page d'accueil en HTTP 200, et le type MIME des ressources agents n'est fixé par personne : un robot lit du HTML là où il attend du JSON ou du Markdown | Blocs `@agents_json`, `@agents_txt` et `@agents_md` déclarés **avant** le `handle` fourre-tout, qui fixent `application/json`, `text/plain` et `text/markdown` en `charset=utf-8` ; repli `try_files … =404` aligné sur le miroir nginx ; miroir nginx enrichi des mêmes types | `python -m unittest tests.test_agent_delivery -v` vert ; section 1b du smoke test verte sur la stack locale |

| **SEO-24** | 🟠 | Outillage CI (`tools/check_seo.py`, `tests/`, `local/smoke-test.sh`) | Aucun garde-fou : un `Disallow` qui revient, un lien mort annoncé aux agents ou un soft 404 réintroduit passent en production sans bruit | `check_decouvrabilite_agents()` dans `tools/check_seo.py` : aucune ressource d'agent interdite par `robots.txt`, et toute URL `cemantix.cyril-randon.fr` citée par `llms.txt`, `llms.md`, `agent-skills.md`, `ai-catalog.json` et `agent-card.json` doit être livrable (fichier du webroot, page générée listée dans `URLS_GENREES`, ou route d'API) ; suite `tests/test_agent_delivery.py` ; smoke test local durci sur le type **et** le corps (`# ` en tête de `llms.txt`, `{` en tête du catalogue) | `python tools/check_seo.py` vert ; `py local/run_seo_tests.py` vert ; le contrôle échoue quand on réintroduit `Disallow: /.well-known/` (test dédié) |
| **SEO-25** | 🟡 | `llms.md`, `agent-skills.md` | Les deux hubs créés par `SEO-17` et `SEO-18` n'étaient déclarés que dans `llms.txt` : un agent qui n'entre que par la version longue ou par la carte d'agent ne les découvre pas | `llms.md` : deux entrées de navigation (mot du jour, méthode) ; `agent-skills.md` : « Compétence 4 — Mot du jour et lecture des indices », avec la conduite anti-spoiler et le renvoi méthode | `python -m unittest tests.test_agent_delivery -v` vert ; `python tools/check_seo.py` vert |
---

## 3. Spécifications

### 3.1 Ce que « erreur de schéma » veut vraiment dire (`SEO-22`, `SEO-23`)

Un audit de découvrabilité ne juge jamais le dépôt : il juge **l'octet reçu**. Trois causes
produisent exactement les deux messages remontés, et aucune n'est un défaut de contenu :

| Cause | Ce que lit l'audit | Correctif |
|---|---|---|
| Le robot n'a pas le droit de lire la ressource (`robots.txt`) | manifeste « absent » ou « schéma non valide », sans mention du refus de crawl | `SEO-22` |
| Le proxy replie l'URL sur `/index.html` | `Unexpected token '<'` côté JSON, « ni en-tête H1 ni liens » côté Markdown | `SEO-23` |
| La ressource annoncée n'existe à ce chemin | même message, selon le fichier visé | `SEO-24` |

Le corollaire est une règle de conception pour tout ce qui s'adresse à un robot : **une
ressource de découverte ne doit jamais être masquée par un repli applicatif.** Un 404 net est un
diagnostic ; un 200 HTML est un mensonge que l'audit interprète comme un contenu invalide.

### 3.2 Le contrat de livraison (`SEO-23`)

| Ressource | Content-Type contractuel | Si le fichier manque |
|---|---|---|
| `/llms.txt` | `text/plain; charset=utf-8` | 404 |
| `/llms.md`, `/agent-skills.md` | `text/markdown; charset=utf-8` | 404 |
| `/.well-known/ai-catalog.json`, `/.well-known/ard.json`, `/.well-known/agent-card.json` | `application/json; charset=utf-8` | 404 |

Le bloc Caddy est déclaré **avant** le `handle` général : les blocs `handle` sont exclusifs et
évalués dans l'ordre d'écriture, donc placé après le repli il ne serait jamais atteint. Côté
nginx, `types {}` vide suivi de `default_type` est le seul moyen d'imposer un type sans
dupliquer l'en-tête — `add_header Content-Type` en ajouterait un second, et deux en-têtes
`Content-Type` rendent un JSON illisible côté client.

### 3.3 Où loge la vérité en CI (`SEO-24`)

`tools/check_seo.py` connaît déjà le webroot et les manifestes : c'est là que la règle est
ajoutée, et `tests/test_agent_delivery.py` **réutilise ces fonctions** au lieu d'en dupliquer
une copie, pour que le contrôle et les tests ne puissent pas diverger. Les pages produites au
démarrage (`/mot-du-jour/`, `/methode/`, `/puzzles/…`, `/sitemap.xml`, `/indexnow-key.txt`)
sont listées dans `URLS_GENREES` : un dépôt fraîchement cloné ne doit pas échouer à cause d'un
fichier que seul le déploiement produit.

---

## 4. Plan d'exécution

| # | Phase | Vérification |
|---|---|---|
| 1 | Rouvrir `robots.txt` sur les ressources de découverte (`SEO-22`) | `python tools/check_seo.py` |
| 2 | Bloc agents et vrai 404 dans la référence Caddy et son miroir nginx (`SEO-23`) | `python -m unittest tests.test_agent_delivery -v` |
| 3 | Gardes CI et smoke test durci (`SEO-24`) | `python tools/check_seo.py` puis `py local/run_seo_tests.py` |
| 4 | Déclaration des hubs dans `llms.md` et `agent-skills.md` (`SEO-25`) | `py local/run_seo_tests.py` |
| 5 | Recette documentaire (`CHANGELOG.md`, index de la roadmap) | `python tools/check_docs.py` |

---

## 5. Recette côté serveur

Le `Caddyfile` de production n'est pas versionné (`.gitignore`) : la référence du `README.md`
en tient lieu, et c'est elle qui est corrigée ici. Après déploiement :

```bash
git pull
docker compose up -d --build cemantix_web cemantix_worker   # régénère llms.txt et .well-known/
docker exec <caddy> caddy reload --config /etc/caddy/Caddyfile
curl -sI https://cemantix.cyril-randon.fr/llms.txt                     # 200, text/plain
curl -sI https://cemantix.cyril-randon.fr/.well-known/ai-catalog.json  # 200, application/json
curl -sI https://cemantix.cyril-randon.fr/inexistant                   # 404, plus jamais 200
```

---

## 6. Risques & rollbacks

| Risque | Exposition | Garde-fou |
|---|---|---|
| Le `=404` casse une URL qui vivait grâce au repli | aucune URL du site ne dépend du repli : les cinq vues, les hubs et les archives sont de vrais fichiers ou de vrais répertoires, et `try_files` conserve `{path}/index.html` puis `{path}/` | le smoke test local liste les cinq vues et attend `/nexiste-pas:404` |
| Un bloc `handle` agents mal placé ne sert jamais | les blocs `handle` sont exclusifs et ordonnés | le test verrouille la présence des trois blocs dans la référence ; la recette §5 se vérifie au `curl -sI` |
| Un `Allow` explicite serait lu comme une incitation à indexer `/llms.txt` | ces ressources ne sont pas des pages et ne portent aucune balise `noindex` | elles n'entrent pas dans le sitemap ; `robots.txt` ne les liste qu'en `Allow` |
| Rollback | `git revert` des commits de la branche : `robots.txt` et la référence Caddy reviennent à l'état précédent, sans effet sur les URLs ni sur les données | — |

