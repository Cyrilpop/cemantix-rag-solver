# 📊 Avancement — Défier le bot IA

> **Évolution :** [2026-10 · Défier le bot](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Dernière mise à jour :** 30/10/2026

---

## 0. Règles de tenue

1. Une ligne = une action du plan, identifiée par son **ID permanent** (`DEFI-04`, `SEC-20`…).
   Un ID n'est jamais renommé ni réattribué.
2. **Une ligne ne passe en `✅ Fait` que si la commande de vérification de son chapitre dans
   `01-plan.md` sort verte.** Un commit, ou son message, ne vaut pas preuve.
3. Statuts possibles :

   | Statut | Signification |
   |---|---|
   | `⬜ À faire` | rien n'a été écrit |
   | `🔨 En cours` | développement engagé sur la branche |
   | `⚠️ Partiel` | une partie du correctif existe, le critère de sortie n'est pas atteint |
   | `✅ Fait` | critère de sortie atteint **sur la branche de travail**, vérification exécutée |
   | `🚫 Renoncé` | abandonné avec justification (l'ID reste réservé) |

4. Chaque changement de statut s'accompagne d'une ligne dans le **journal** (§4) : date, ID, ce qui
   a été exécuté, preuve.
5. `01-plan.md` ne porte **aucun** statut : ne pas en ajouter.

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **29** | 8 |
| 🔨 En cours | **0** | 0 |
| ⚠️ Partiel | **1** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **30** | **8** |

Répartition par famille : `DEFI` 18 · `SEC` 9 (`SEC-20` à `SEC-28`) · `QUAL` 3.

**Les 8 actions critiques :** `DEFI-04`, `DEFI-08`, `DEFI-10`, `DEFI-15`, `SEC-20`, `SEC-21`,
`SEC-24`, `SEC-25`. `QUAL-22` (recette) est en outre tenue pour bloquante à la clôture.

---

## 2. État des dépôts

Mesuré le 29/10/2026 :

| Branche | Local | GitHub | Écart |
|---|---|---|---|
| `feat/bot_defy` ← *courante* | rebasée sur `8144143` | `origin/feat/bot_defy` | **iso** (poussée en `--force-with-lease`) |
| `main` | `8144143` | `8144143` | fusion PR #25 (ordre chronologique de la roadmap) |

- **Base de travail :** `main` fusionnée (PR #25, `8144143`) — l'évolution part de l'architecture
  PostgreSQL + worker + web telle que décrite au §0.2 du plan.
- **Arbre de travail :** propre à l'ouverture.

---

## 3. Environnement de test

- `docker compose up` complet (db + worker + web) sur le poste de développement, Caddy local ou
  `curl` direct sur `:8000`.
- Résolution rapide en test : `CHALLENGE_MAX_TRIES` abaissée et mot proche des graines
  (ex. « amour ») pour valider le bout-en-bout sans attendre 100 coups.
- Tests unitaires : `python -m pytest tests/` (repli SQLite, aucun conteneur requis).

---

## 4. Journal

| Date | ID | Ce qui a été fait | Preuve |
|---|---|---|---|
| 29/10 | — | Ouverture de l'évolution : plan (`01-plan.md`) et suivi (`02-avancement.md`) rédigés, index roadmap mis à jour, branche `feat/bot_defy` ouverte sur `main` @ `4019126` | `python tools/check_docs.py` vert |
| 30/10 | — | Rebase de `feat/bot_defy` sur `main` @ `8144143` (conflit résolu sur l'index §3 du README) ; dossier renommé `2026-10-06-defier-le-bot` (convention `AAAA-MM-NN-slug` de la PR #25) | `python tools/check_docs.py` vert, branche poussée en `--force-with-lease` |
| 30/10 | DEFI-01..03 | Phase 1 : tables `bot_challenges` + `bot_challenge_whitelist` (init.sql, PG_SCHEMA, SQLite) et DAO complet (claim atomique, orphelins, purge, whitelist) — commit `9c312d3` | smoke DAO dans l'image `cemantix:latest` : claim à deux threads, orphelin → queued → error, whitelist add/list/remove, purge |
| 30/10 | DEFI-04..08, DEFI-18, SEC-20..24 | Phase 2 : `src/api/routes/challenge.py` (POST/GET/SSE) + dispatch `server.py` + routes admin whitelist + `do_DELETE` — commit `5a6d727` | smoke routes : 10×201 puis 429+retry_after, rafale 6/8, whitelist unlimited, 404 génériques, SSE step→done sans `secret_word` ; `grep solvers\|daemon` vide |
| 30/10 | DEFI-09..13 | Phase 3 : `src/services/challenges.py` + pick-up dans la boucle de veille du démon + purge RGPD aux réveils — commit `f369519` | **recette réelle** : `create_challenge(« amour »)` → `process_next_challenge()` → `solved` en 5 coups / 0,38 s, trajectoire 5 pas en base |
| 30/10 | DEFI-14..17 | Phase 4 : page `/defi/` (SEO complet, modal trajectoire), `js/defi.js` (SSE + repli polling), onglet sur les 5 pages, `check_seo.py` élargi à 5 pages — commit `c43b626` | `tools/check_seo.py` : OK sur 5 pages + hubs + llms.txt |
| 30/10 | DEFI-18 (UI) | Phase 5 : section whitelist dans la console cachée (liste, ajout, retrait 1 clic, chiffrée anti-XSS) — commit `2d48f38` | revue grep : SQL 100 % paramétré, `escapeHtml`/`esc()` systématiques |
| 30/10 | QUAL-20 | Phase 6 : `tests/test_defi_bot.py` (30 tests) + correction de lecture des bornes via le module DAO (pilotables en test) — commit `ed109a7` | `python -m unittest discover -s tests` : **151 tests OK** (image cemantix:latest) |
| 30/10 | QUAL-21 | Documentation : `openapi.json` (3 routes), README (section « Défier le Bot IA »), CHANGELOG, 11 variables `.env.example`, suivi présent — commit `f8ec1f7` | `tools/check_docs.py` vert ; `tools/check_seo.py` vert (5 pages) |
| 30/10 | QUAL-22 (partiel) | Recette backend **contre la PostgreSQL de production** : conteneur temporaire `cemantix:latest` sur `cemantix-net`, `src/` de la branche monté en ro — empilement, claim atomique, résolution RAG pur réelle | logs : `MOTEUR: postgres` → `CLAIM atomique OK` → `STATUT: solved \| coups: 5 \| durée: 0.19 \| trajectoire: 5` ; `docker stats` : `cemantix_web CPU=0.02 %` pendant la résolution ; trace nettoyée en fin de recette |
| 30/10 | — | Branche `feat/bot_defy` poussée (7 commits de développement, `b06a2be..f8ec1f7`), iso `origin/feat/bot_defy` ; suite complète verte : **151 tests OK** | `git push` OK, `python -m unittest discover -s tests` dans l'image de production |
| 30/10 | DEFI-06 (correctif) | **Défi lancé depuis la production : rien ne s'affichait et le flux mourait en `net::ERR_CONNECTION_CLOSED`.** Trois causes distinctes, toutes corrigées : (1) *le worker ne consommait pas la file* — le code est **cuit dans l'image** (`./src` n'est pas monté, seuls `cemantix_data` et `volumes/web` le sont), donc un conteneur non reconstruit ignore tout de `DEFI-09` ; (2) *le SSE restait silencieux* pendant l'attente — tout intermédiaire (`proxy_read_timeout 30s` du `location /api/` local, Caddy sans `flush_interval -1`) ferme une connexion muette : le producteur émet désormais un **event `status` immédiat** puis un **battement toutes les 10 s** ; (3) *le front tuait l'`EventSource` au premier incident* et le repli polling n'affichait jamais les mots — la coupure déclenche maintenant une **reconnexion** (3 essais, puis repli), et le polling relit les coups via `GET …?detail=1`. Côté proxy : `location ~ ^/api/challenge/[0-9a-f]+/stream$` (`proxy_buffering off`, `proxy_read_timeout 900s`) et son équivalent Caddy `flush_interval -1` documenté dans le README. NB : pas de `{32}` dans un regex nginx — l'accolade est un délimiteur de bloc (`unknown directive "32}/stream$"`) | `nginx -t` OK + reload ; **recette bout-en-bout à travers nginx** : `+24 ms status queued` → `+10 058 ms ping` → `+20 091 ms ping` → 23 coups reçus en direct → `done solved` ; suite **155 tests OK** (dont 4 nouveaux sur ce défaut) |
| 30/10 | DEFI-14 (correctif) | Console navigateur signalait `Pattern attribute value … is not a valid regular expression` : l'attribut `pattern` de `/defi/` était compilé en mode **`v`** (Unicode-sets) par le navigateur, où `[a-zA-Zà-ÿ-]` est ambigu (hyphen final + littéraux accentués). Attribut réécrit en échappements ASCII `pattern="[a-zA-Z\u00E0-\u00FF][a-zA-Z\u00E0-\u00FF]{2,23}"`, valable en modes `u` **et** `v` ; le tiret retiré aligne en plus le contrôle client sur le serveur (`WORD_RE` n'accepte pas le tiret). L'autre message console (`content.js:1 … tabs:outgoing.message.ready`) provient d'une **extension de navigateur**, d'aucune façon du site : aucun `content.js` dans `volumes/web` | `grep -n 'pattern=' volumes/web/defi/index.html` = forme échappée ; `tools/check_seo.py` vert sur 5 pages |

---

## 5. Suivi des actions

### 5.1 Données (plan §2)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-01** | Table `bot_challenges` & `bot_challenge_whitelist` (init.sql + PG_SCHEMA + SQLite) | ✅ Fait | commit 9c312d3 ; DDL dans init.sql + PG_SCHEMA + SQLite ; tables créées et testées (image cemantix:latest) |
| **DEFI-02** | DAO `src/db/challenges.py` (claim atomique, quota, purge, gestion whitelist) | ✅ Fait | src/db/challenges.py ; 12 tests dans tests/test_defi_bot.py ; grep SQL paramétré vide |
| **DEFI-03** | Cohérence des statuts + `requeue_stale_running` | ✅ Fait | tests test_requeue_orphelin_puis_error, test_release_ne_marque_pas_orphelin, test_statut_terminal_reserve |

### 5.2 API web (plan §3)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-04** | `POST /api/challenge` (enqueue seul, zéro calcul) | ✅ Fait | grep solvers/daemon dans challenge.py vide ; test test_dix_puis_quarante_deux (201 + quota_restant) |
| **DEFI-05** | `GET /api/challenge/<id>` (état borné) | ✅ Fait | tests test_get_borne_sans_spoiler, test_get_id_inconnu_404 |
| **DEFI-06** | `GET /api/challenge/<id>/stream` (SSE via `_send_sse`) | ✅ Fait | recette SSE (phase 2) : events step puis done avec mot au terminal ; aucun secret_word dans les flux |
| **DEFI-07** | Rate-limiter mémoire anti-rafale | ✅ Fait | test test_antirafale_memoire : 6x201 puis 2x429 sur une rafale de 8 |
| **DEFI-08** | Validation du mot (regex + lexique, message unique) | ✅ Fait | tests TestValidationMot (6 cas : <script>, A, inconnu, 25 car., non-texte) |
| **DEFI-18** | Gestion admin de la whitelist IP (API REST + UI console cachée) | ✅ Fait | routes GET/POST/DELETE whitelist + section console ; test test_admin_gere_la_whitelist |

### 5.3 Worker (plan §4)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-09** | Pick-up dans la boucle de veille du démon | ✅ Fait | pick-up toutes les CHALLENGE_POLL_SECONDS dans la boucle de veille (src/services/daemon.py) |
| **DEFI-10** | Résolution `Solver` + `MockClient(secret=…)` | ✅ Fait | recette réelle : mot « amour » queued → running → solved en 5 coups, 0,38 s (image cemantix:latest) |
| **DEFI-11** | Trajectoire incrémentale en base (toutes les 2 s) | ✅ Fait | publication toutes les 2 s + heartbeat (src/services/challenges.py) ; trajectoire 5 coups visible en base |
| **DEFI-12** | Bornes `max_tries` / durée / statut `lost` | ✅ Fait | max_tries serveur, timeout 900 s, statut lost testé (test_defi_perdu) |
| **DEFI-13** | Priorité à la résolution nocturne de minuit | ✅ Fait | pick-up dans la boucle de veille uniquement : minuit démarre au tour suivant, défi borné par le timeout |

### 5.4 Frontend (plan §5)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-14** | Page `defi/index.html` + onglet de navigation + SEO | ✅ Fait | page /defi/ + onglet sur les 5 pages ; tools/check_seo.py vert sur 5 pages |
| **DEFI-15** | `js/defi.js` : SSE + repli polling + quota affiché | ✅ Fait | js/defi.js : EventSource + repli polling (3 reconnexions) + quota + chrono ; escapeHtml systématique |
| **DEFI-16** | Rendu des coups via `render.js` / modal trajectoire | ✅ Fait | rendu au gabarit trajectory-step-card + modal trajectoire réutilisée (openTrajectoryModal) |
| **DEFI-17** | CSS + accessibilité (`aria-live`, contrastes) | ✅ Fait | CSS critique mutualisé de play/ ; aria-live sur statut et liste, label du champ ; check_seo vert |

### 5.5 Sécurité (plan §6)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **SEC-20** | Quota 10/h persisté en base (429 + retry_after) & whitelist IP administrable sans limite | ✅ Fait | tests test_dix_puis_quarante_deux, test_quota_survit_au_rechargement_memoire, test_ip_whitelistee_sans_quota |
| **SEC-21** | IP hachée salée (HMAC), aucune IP brute en base | ✅ Fait | ip_hash() HMAC-SHA256 salé (CHALLENGE_IP_SALT/DB_PASS) sur /24 ; aucune IP brute dans bot_challenges |
| **SEC-22** | Identifiant 128 bits, aucune liste publique | ✅ Fait | secrets.token_hex(16) ; aucun endpoint liste ; id malformé = même 404 générique (test) |
| **SEC-23** | Plafond `SSE_MAX_STREAMS` + durée max de flux | ✅ Fait | BoundedSemaphore(SSE_MAX_STREAMS=16) + deadline 15 min dans le producteur |
| **SEC-24** | File bornée, `max_tries` serveur, coût par coup borné | ✅ Fait | test test_file_bornee ; max_tries lu en base, jamais du client ; RAG pur sans LLM |
| **SEC-25** | Anti-XSS trois couches (regex, paramétré, escapeHtml) | ✅ Fait | regex+lexique → paramètres liés → escapeHtml() (6 appels dans defi.js) ; grep f-strings SQL vide |
| **SEC-26** | `no-store` + mot jamais révélé avant le statut terminal | ✅ Fait | Cache-Control: no-store (SECURITY_HEADERS) ; tests sans-spoiler + recette SSE |
| **SEC-27** | Purge 30 jours au réveil du démon, rien dans `data.json` | ✅ Fait | challenge_maintenance() au démarrage et au réveil de minuit ; test test_purge ; rien dans data.json |
| **SEC-28** | Worker limité à la table, jamais d'ordre arbitraire | ✅ Fait | le worker ne lit que bot_challenges ; daemon_command.json non utilisé par l'évolution |

### 5.6 Qualité (plan §7)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **QUAL-20** | Tests (validation, quota, claim, bout-en-bout mock, purge) | ✅ Fait | tests/test_defi_bot.py : 30 tests ; suite complete python -m unittest discover -s tests = 151 OK |
| **QUAL-21** | `openapi.json`, README, CHANGELOG, `.env.example` | ✅ Fait | openapi.json (5 paths), README (section Défier le Bot), CHANGELOG, 11 variables dans .env.example |
| **QUAL-22** | Recette docker complète (direct, quota, nuit, CPU web = 0) | ⚠️ Partiel | **Partie backend prouvée contre la PostgreSQL de production** (conteneur temporaire sur `cemantix-net`, code de la branche monté en lecture seule) : `MOTEUR: postgres`, défi empilé → claim atomique `running` → **solved en 5 coups / 0,19 s**, trajectoire 5 pas en base, trace nettoyée ; `docker stats` pendant la résolution : **cemantix_web CPU = 0,02 %** (le web ne calcule pas). Reste la partie navigateur après redéploiement : direct affiché < 1 s/coup, 11ᵉ défi → 429 vu par la page, consultabilité clavier |

---

## 6. Prochaines actions

1. **Déploiement (bloquant pour l'utilisateur)** : le code est **cuit dans l'image**, il faut
   donc `docker compose build` puis redémarrer **`cemantix_web` ET `cemantix_worker`** — un web
   seul reconstruit enfile des défis que personne ne résout. Appliquer aussi la règle proxy du
   flux direct (`flush_interval -1` côté Caddy, cf. README ; `proxy_buffering off` +
   `proxy_read_timeout 900s` côté nginx, cf. `local/nginx/cemantix.local.conf`).
2. **QUAL-22 (seule action restante)** : courir la recette en conditions réelles sur
   `docker compose up` — défi gagné affiché en direct (< 1 s de latence par coup), 11ᵉ défi de
   l'heure → `429`, `docker stats` ≈ 0 % CPU sur `cemantix_web` pendant une résolution, défi
   lancé à 23h59 sans déranger la résolution de minuit, page consultable au clavier.
3. Poser `CHALLENGE_IP_SALT` (secret d'exploitation dédié) dans le `.env` de production, à
   défaut le sel derive de `DB_PASS`.
4. À la fusion : `main` → redéploiement ; le rollback reste « image précédente +
   `DROP TABLE bot_challenges` » (fonctionnalité purement additive).
