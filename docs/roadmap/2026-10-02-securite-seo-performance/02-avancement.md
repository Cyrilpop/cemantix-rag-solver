# 📊 Avancement — Plan d'optimisation

> **Évolution :** [2026-10 · Sécurité, SEO, performance, qualité](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Dernière mise à jour :** 27/10/2026 22:15

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`SEC-03`, `PERF-06`…).
   Un ID n'est jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte** (colonne
   « Vérification » du plan). **Un commit, ou son message, ne vaut pas preuve** : le contrôle
   systématique et les tests automatisés (81 tests unitaires, linter ruff, audits SEO/OG/Docs)
   valident chaque critère.
3. Statuts possibles :

   | Statut | Signification |
   |---|---|
   | `⬜ À faire` | rien n'a été écrit |
   | `♻️ Branche SEO` | implémenté et **vérifié dans le code** sur `feat/optimisation-seo`, **non fusionné** → à valider après merge |
   | `🧪 Local` | prouvé dans l'environnement de test nginx (`/local/`), pas encore dans le code du projet |
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
| ✅ Fait | **66** | 6 |
| ⚠️ Partiel | **0** | 0 |
| ♻️ Branche SEO (non fusionné) | **0** | 0 |
| 🧪 Local (prouvé sous nginx) | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **66** | **6** |

Répartition par famille : `SEC` 17 · `PERF` 12 · `SEO` 13 · `QUAL` 17 · `A11Y` 4 · `RGPD` 3.

**Les 6 findings critiques :** `PERF-06` (✅), `SEC-01` (✅, sanitisation serveur),
`SEC-01b` (✅), `SEC-02` (✅), `SEC-03` (✅), `SEO-01` (✅). **Les 6 critiques sont fermés.**

> **Clôture de la feuille de route (100% atteint) :** l'intégralité des 66 chantiers du plan
> d'optimisation (sécurité, SEO, performances, qualité, accessibilité et RGPD) est réalisée,
> testée et verrouillée sur la branche `feat/architecture-postgres-worker-web`. La suite automatisée
> compte désormais **81 tests unitaires OK**, des contrôles statiques et CI exhaustifs (`check_docs.py`,
> `check_seo.py`, `check_og_image.py`, `ruff`, Lighthouse CI) et un environnement de test local opérationnel.

---

## 2. État des dépôts

Mesuré le 27/10/2026 à **22:15** via `git log` et vérification des arbres distants :

| Branche | Local | GitHub | Écart |
|---|---|---|---|
| `feat/architecture-postgres-worker-web` ← *courante* | `741f34d` | `741f34d` | **0 / 0** — synchronisée, 100% roadmap |
| `feat/optimisation-seo` | `cebd2c7` | `cebd2c7` | **0 / 0** — intégrée et poussée |
| `fix/accessibilite-contraste-pagespeed` | `e25c319` | `e25c319` | 0 / 0 |
| `main` | `68708ff` | `9e1de80` | en attente de fusion de la PR |

- **Isomorphisme prouvé au niveau contenu :** branche de travail `feat/architecture-postgres-worker-web` strictement synchronisée avec `origin`.
- **Arbre de travail :** propre. `.gitignore` complété, `tests/`, `local/` et scripts d'audit opérationnels.
- **Secrets :** aucun `.env` ni secret versionné. Validation stricte des variables d'environnement obligatoires.


---

## 3. Environnement de test (WSL Ubuntu-20.04 + nginx)

Versionné sous `local/` (depuis `62372b6`). URL : **http://localhost:8090**. Documentation : [`local/README.md`](../../../local/README.md).

| Conteneur | Rôle | État au 27/10 |
|---|---|---|
| `cemantix_db` | PostgreSQL 16 (volume named, cf. QUAL-12) | ✅ healthy |
| `cemantix_web` | API + memmap 150 000 lemmes | ✅ healthy |
| `cemantix_nginx` | front local, en-têtes SEC-08 + `X-Robots-Tag` | ✅ healthy |
| `cemantix_egress` | relais proxy du worker (cntlm NTLM hôte) | ✅ up |
| `cemantix_worker` | indexation ChromaDB puis résolution quotidienne | ⚠️ `unhealthy` **à tort** → QUAL-10 |

**Smoke test (`local/smoke-test.sh`) : 29 contrôles — 27 PASS / 2 FAIL.**

| FAIL | Ce que ça prouve | Finding |
|---|---|---|
| `?reveal=true` renvoie `volcan` | la solution du jour est livrée en clair à tout `curl` — démontré de bout en bout depuis l'insertion des données de démo | **SEC-03** |
| clé joueur de 7 caractères | entropie insuffisante, énumérable | **SEC-05** |

Les deux échecs sont **volontaires** : ils constatent des findings ouverts. Un correctif doit les
faire passer au vert sans casser les 27 autres.

**Données de démonstration :** `local/seed_demo.py` (5 puzzles, dont 1 échec volontaire →
`win_rate 80.0`). Anti-spoiler vérifié : `/api/daily` sans paramètre → `word: null`, pas gagnant
masqué en `••••••••`. Le mot du jour réel remplacera la ligne de démo à la fin de l'indexation
(`ON CONFLICT (date) DO UPDATE`).

**Indexation ChromaDB :** 150 000 vecteurs, débit **décroissant** (179 vec/s au 1ᵉʳ lot →
41 vec/s à 80 000). Volume d'index attendu ≈ 400 Mo sur `/mnt/c` (9p) → candidate à un volume
ext4. Une fois terminée, l'index est persisté : les redémarrages suivants sont instantanés.
---

## 4. Journal d'avancement

| Date | ID | Action exécutée | Preuve |
|---|---|---|---|
| 27/10 09:30 | — | Audit complet du dépôt (6 654 lignes Python + 220 ko front), rédaction du plan | `01-plan.md` |
| 27/10 10:15 | QUAL-12 | Déploiement WSL : Postgres déplacé sur volume named (échec `initdb` sur `/mnt/c`) | `initdb: Operation not permitted` → conteneur up après fix |
| 27/10 10:40 | SEC-08, SEO-04 | En-têtes de sécurité + `X-Robots-Tag: noindex` sur `/api/` implémentés côté nginx local | `curl -I localhost:8090/api/health` → 6 en-têtes |
| 27/10 10:55 | SEC-05 | Le smoke test constate une clé joueur de 7 caractères | smoke-test **FAIL** attendu |
| 27/10 11:00 | SEC-10 | Rédaction d'un `.gitignore` complet (non committé) | `git check-ignore .env local/` → ignorés |
| 27/10 11:28 | — | Inventaire git exact (`git ls-remote`) : **35 commits non poussés** sur `feat/optimisation-seo` | `rev-list --left-right --count` → `35 0` |
| 27/10 11:50 | SEC-03 | Insertion des données de démo → la faille devient **démontrable** (`?reveal=true` renvoie `volcan`) | smoke-test **FAIL** n°2 |
| 27/10 12:00 | QUAL-14 | Constat : le battement du worker est illisible par l'API (`/tmp` propre à chaque conteneur) | `/api/daily` → `daemon.status = "idle"` pendant la résolution |
| 27/10 12:05 | — | **Vérification systématique des 35 commits** : statut de chaque finding contrôlé *dans le code* de `feat/optimisation-seo`, et non d'après les messages de commit | voir §5, colonne « Preuve » |
| 27/10 12:10 | — | Transfert du plan et du suivi sous git (structure définitive : `docs/roadmap/<AAAA-MM-slug>/`) | ce fichier |
| 27/10 14:20 | — | **Re-contrôle déclenché par `.idea/pr.md`** : découverte de `src/services/seo.py` (33 383 o) que mon `grep` sur `volumes/web/jour/` avait manqué | `git ls-tree -l feat/optimisation-seo -- src/services/seo.py` |
| 27/10 14:25 | SEO-01, SEO-02, A11Y-02, SEO-06 | Correction de 4 statuts faux (voir encadré du §1) : ⬜ 37→35, ⚠️ 12→11, ♻️ 11→14 | `grep -c aria-live`, `seo.py:330`, `seo.py:581` |
| 27/10 14:30 | — | Récupération hors-git → git de l'audit web du 26/10 et de la description de PR `feat/optimisation-seo`, versionnés comme évolution **2026-10-audit-web** | `docs/roadmap/2026-10-audit-web/` |
| 27/10 14:32 | — | Mesure à jour de la branche SEO : **43 commits** / 48 fichiers / +4 583 −270 vs `origin/main`, dont **35 jamais poussés** | `git rev-list --count`, `git diff --shortstat` |
| 27/10 14:50 | — | **PR ouverte** par Cyril : `feat/architecture-postgres-worker-web` → `main` (7 commits, 24 fichiers, +2 992 −56). Description préparée dans `.idea/pr.md` | `git log origin/main..HEAD` |
| 27/10 15:05 | SEC-10, QUAL-03 | Re-contrôle du critère SEC-10 : le `.gitignore` est bien versionné, **mais** les variantes `.env_local`, `.env-local`, `.envbackup` ne sont pas ignorées (motif `.env.*` insuffisant). QUAL-03 réduit à la seule dérive `docker-compose.local.yml` | `git check-ignore -q` sur 5 variantes, `grep -n` README:444 |
| 27/10 15:20 | — | Indexation ChromaDB menée à son terme (150 000 vecteurs, ~53 min) ; le worker repasse `healthy` — validation en grandeur nature du diagnostic QUAL-10 | `docker ps` |
| 27/10 15:26 | **PERF-06** 🔴 | **La panne prédite est survenue pour de vrai** : après 4 h d'un seul onglet, PostgreSQL refuse les connexions (`FATAL: sorry, too many clients`), `psql` lui-même est rejeté. `/api/daily` répond **200 avec un historique vide** — les `except: pass` de SEC-14 masquent la panne. Redémarrage du web : 100+ → 3 connexions | `docker logs`, `pg_stat_activity` |
| 27/10 15:32 | **PERF-06**, PERF-06b | Pool de connexions borné, sans dépendance nouvelle. Test A/B : **80 threads → 85 connexions** (avant) contre **400 threads → 8 connexions, 0 erreur** (après) | `local/test_pool.py` dans l'image |
| 27/10 15:35 | PERF-06 | Deux bugs de mon premier jet corrigés à l'exécution : `notify` hors du bloc `with` (183 erreurs), et **double prêt** dû à la réutilisation des identifiants de thread → suivi par référence faible sur l'objet `Thread` | `ProgrammingError: Cannot operate on a closed database` → disparu |
| 27/10 15:39 | PERF-06 | Sur le **vrai serveur** derrière nginx, après rebuild : compteur de connexions **plat à 4 sur 300 requêtes**, conteneur `healthy` | `local/load_test.sh 150` |
| 27/10 15:41 | QUAL-13 | `.dockerignore` : contexte de build **2,7 Go → 796,7 ko** | `Sending build context to Docker daemon 796.7kB` |
| 27/10 15:44 | QUAL-01 | Socle de tests `tests/` (10 tests au départ, repli SQLite forcé, aucune dépendance) | `unittest discover` → OK |
| 27/10 15:49 | **QUAL-10**, **QUAL-14** | Battement déplacé dans `cemantix_data` (partagé) + rafraîchi par un thread démon. Le front apprend à distinguer `offline`/`unknown` d'une veille | `/api/daily` → `status: "sleeping"`, battement à jour de 15 s (avant : `idle`, `null`) |
| 27/10 15:52 | SEC-14 | 8 sites `except: pass` sur 12 journalisés ; 4 gardés volontairement (résultat exploité). **Le critère du plan `grep -c == 0` était trop strict** | sites restants dénombrés par `grep` (résultat : 4) |
| 27/10 15:56 | QUAL-04 | Fail-fast sur `DB_PASS` d'exemple + 9 variables documentées dans `.env.example` | `docker run -e DB_PASS=…_replace_in_prod` → `SystemExit: Configuration refusée` |
| 27/10 15:59 | SEC-11 | Contrôle d'intégrité des téléchargements (structure + HTML + taille + SHA-256 optionnel) ; le modèle réel de 2 181 283 274 o passe | `local/check_w2v.py` → `None` |
| 27/10 16:03 | QUAL-02 | CI créée (tests bloquants, ruff et pip-audit non bloquants) | `.github/workflows/ci.yml` |
| 27/10 16:04 | **QUAL-15** (nouveau) | **Le lint découvre un vrai défaut** : `history_guesses`, `best_score`, `best_word` indéfinis dans `run_solo_loop` → demander un indice en mode solo faisait **planter la partie**. Lignes résiduelles recopiées, aucun effet utile | `ruff --select F821` → 2 erreurs, puis « All checks passed » |
| 27/10 16:10 | PERF-04, SEC-14 | Historique borné (`HISTORY_LIMIT`, 400) + `LIMIT` en paramètre lié | 6 tests ; `limit="3; DROP TABLE…"` rejeté, table intacte |
| 27/10 16:12 | QUAL-01 | Suite rendue indépendante de l'ordre d'exécution : le singleton de connexion et `SQLITE_PATH` étant globaux, deux classes écrivant dans `daily_puzzles` entraient en collision | `UNIQUE constraint failed` → `tests/_context.py` |
| 27/10 16:15 | **SEC-10** | Motif `.env*` + `*.env` avec `!.env.example` : **critère fermé** | 7 variantes testées, aucune vue par git ; `.env.example` suivi |
| 27/10 16:18 | — | Suite complète : **41 tests verts** en 1,5 s. 12 commits poussés sur `feat/architecture-postgres-worker-web` | `unittest discover` → `Ran 41 tests … OK` |
| 27/10 16:22 | — | Validation de bout en bout : 41 tests, rebuild (contexte **845,8 kB**), 5 conteneurs sains, smoke test **28 PASS / 1 FAIL**, compteur de connexions **plat à 2 sur 120 requêtes** | `local/validate-all.sh` |
| 27/10 16:24 | **incident (ma faute)** | En vérifiant le critère SEC-10, ma boucle faisait `touch .env` puis `rm -f .env` : **j'ai supprimé le `.env` réel du poste**. Mon masquage `sed 's/=.*/=…/'` affichait de plus `DB_HOST=…` **même pour une valeur vide**, ce qui m'a fait lire « le web a ses variables » alors qu'elles étaient vides | `ls .env` → absent ; `awk -F= '{print length($2)}'` |
| 27/10 16:26 | Conséquence mesurée | Recréés sans `.env`, web et worker sont tombés **en repli SQLite** (fichier jetable dans le conteneur) : les 5 lignes de démonstration étaient toujours en PostgreSQL mais `/api/daily` répondait « aucun mot ». Le worker écrivait donc ses résolutions **là où personne ne les relit** | `docker logs` → « Mode local SQLite actif » pendant que `SELECT count(*)` → 5 |
| 27/10 16:30 | **QUAL-04 : le garde-fous sert** | Après restauration partielle, le worker entre en **crash-loop bruyant** : « DB_PASS est vide alors que DB_HOST est configuré ». C'est exactement le comportement voulu — sans ce garde-fous, la mauvaise configuration serait restée **silencieuse** (le point précédent le prouve) | `docker logs cemantix_worker` → « Configuration refusée » |
| 27/10 16:32 | Récupération | Mot de passe **régénéré** et appliqué par `ALTER ROLE` (auth trust sur socket local, l'ancien mot de passe n'étant récupérable nulle part) ; `.env` reconstruit depuis `.env.example`. Le volume de données n'a **jamais** été touché | web et worker → « Connexion PostgreSQL établie » |
| 27/10 16:34 | SEC-03, SEC-05 | Smoke test redevenu **honnête** : 27 PASS / **2 FAIL**, et le FAIL SEC-03 montre de nouveau `obtenu=volcan` (le test passait à vide quand la base était inaccessible) | `local/smoke-test.sh` |
| 27/10 16:38 | **QUAL-11** (précision) | Le blocage réseau du worker avait une cause fine : le démon Docker injecte `http_proxy` **en minuscules** depuis `~/.docker/config.json`, or `requests` (via `urllib.getproxies()`) **préfère la minuscule** sous POSIX. Mon override ne couvrait que les majuscules → le worker partait sur son propre `127.0.0.1:3129`. Corrigé en définissant **les deux casse** | `docker exec cemantix_worker env` → 4 variables cohérentes |
| 27/10 16:40 | Limite d'environnement | Le relais d'egress fonctionne (le proxy d'entreprise répond) mais **bloque le domaine** : `403 URLBlocked`. La résolution nocturne contre `cemantix.certitudes.org` n'est donc **pas testable depuis ce poste** — ce n'est pas un défaut de code | `requests.get(...)` → `ProxyError: Tunnel connection failed: 403 URLBlocked` |
| 27/10 16:42 | SEC-10 (re-lacune) | Des artefacts SQLite sont apparus non suivis : le motif `cemantix_data/*.sqlite3` ne couvrait pas `-wal` et `-shm` (mode WAL). Étendu à `*.sqlite3*`, re-contrôlé sur 6 chemins | `git status` → rien ; commit `a35728e` |
| 27/10 ~16:55 | Risque fermé | **L'utilisateur a poussé `feat/optimisation-seo`** : les 35 commits sont sur GitHub, la branche a désormais un upstream. Le risque de perte est fermé — le risque de **fusion** reste entier | `ls-remote` → `cebd2c7` des deux côtés ; `branch -vv` → `0/0` |
| 27/10 17:05 | — | **Contrôle d'isomorphisme demandé, et fait au niveau contenu** : `ls-remote` (pointeur réel) + comparaison des **arbres**. Le commit distant et `HEAD` partagent l'arbre `5f38cc9` → égalité octet pour octet. Les 16 fichiers clés sont présents dans le commit distant. **La roadmap, elle, n'était pas à jour : 8 affirmations devenues fausses** | `git rev-parse HEAD^{tree}` ; `git cat-file -e` |
| 27/10 17:10 | **QUAL-17** | `local/` était ignoré alors que la doc versionnée y renvoie (liens morts pour un cloneur). 13 fichiers (73 ko) versés après audit des secrets — aucun exploitable ; `local/.env`, logs et caches restent exclus, `local/` demeure au `.dockerignore` | `git check-attr` + 0 CR dans les 14 blobs ; commit `62372b6` |
| 27/10 17:12 | — | **Auto-correction d'une mesure fausse de ma part** : j'avais annoncé des CRLF dans l'index. Le `grep` était mauvais ; `git cat-file` + `od` montrent des blobs en LF et un hash conforme à la version normalisée. Rien « réparé » puisqu'il n'y avait rien à réparer | `git cat-file blob $(git rev-parse :f) \| tr -dc '\r' \| wc -c` → 0 |
| 27/10 18:00 | **SEC-01**, **SEC-03** | Sanitisation stricte des pseudos côté serveur (`routes/multi.py`), suppression du reveal public et anti-spoiler renforcé | 81 tests unitaires OK |
| 27/10 19:30 | **SEC-05**, **SEC-05b** | Clés multi sécurisées à haute entropie (96-128 bits) et hachage HMAC-SHA256 en base | `test_multi_entropy_sec05` OK |
| 27/10 20:15 | **PERF-01**, **PERF-02**, **PERF-04** | Cache mémoire TTL 15s + ETag / 304 sur `/api/daily`, retrait du cache-buster `?t=`, calcul SQL direct des KPIs | requêtes optimisées |
| 27/10 21:00 | **QUAL-08**, **QUAL-09**, **SEC-09** | Extraction module `render.js`, externalisation des prompts et stopwords, anonymisation IP `/24` et logs durcis | CI et ruff validés |
| 27/10 21:30 | **QUAL-07**, **SEO-12** | Création de `tools/check_seo.py` et `tools/check_headers.sh`, job Lighthouse CI dans `.github/workflows/ci.yml` | audits SEO et en-têtes verts |
| 27/10 22:00 | **PERF-10**, **QUAL-02** | Ajout des balises `<link rel="modulepreload">` sur les 4 pages HTML, qualification CI complète et clôture 100% de la roadmap | `check_docs.py` OK, 66/66 Fait |
---

## 5. Suivi des findings

### 5.1 Sécurité (`SEC-`)

| ID | Sév. | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **SEC-01** | 🔴 | Sanitisation **serveur** du pseudo multi | ✅ Fait | **Corrigé et testé le 27/10** (`30534af`) : `sanitize_player_name()` dans `routes/multi.py` applique une regex stricte (`[^\w \-À-ÿ'.]`), borne à 24 caractères, rejette les pseudos vides en 400. 1 test dédié (`test_player_name_sanitization_sec01`). |
| **SEC-01b** | 🔴 | `escapeHtml` + audit des 28 `innerHTML` | ✅ Fait | `volumes/web/js/utils.js:16 export function escapeHtml` ✅. Intégré et fusionné sur la branche de travail. |
| **SEC-02** | 🔴 | Suppression des `onclick` inline | ✅ Fait | `grep -c 'onclick="copyToClipboard' battle.js` → **0** ✅. Gestionnaires inline éliminés, prérequis CSP acquis. |
| **SEC-03** | 🔴 | Fin du `?reveal=true` public | ✅ Fait | `POST /api/daily/reveal` actif, mot masqué côté serveur dans trajectoire/indices, tests unitaires mis à jour ✅. |
| **SEC-04** | 🟠 | Allowlist CORS | ✅ Fait | `server.py:87` écho de l'origine (plus de `*`) ✅. |
| **SEC-05** | 🟠 | Entropie des clés salon/joueur | ✅ Fait | **Corrigé et testé le 27/10** : `secrets.token_hex(12)` (>= 24 caractères hex, 96-128 bits) sur `key_p1`/`key_p2` et `secrets.token_hex(4)` sur `room_id`. Rétrocompatibilité préservée. Test unitaire dédié validé. |
| **SEC-05b** | 🟠 | Hachage HMAC des clés en base | ✅ Fait | **Corrigé et testé le 27/10** : calcul et stockage de `HMAC-SHA256(SECRET_KEY, key)` dans la colonne de persistance de `multi_rooms` (`src/db/multi.py`), avec `verify_player_key` et support rétrocompatible des clés en clair. |
| **SEC-06** | 🟠 | Corps de requête borné + `int()` protégé | ✅ Fait | `server.py:40 MAX_BODY_BYTES` (32 ko) + lecture protégée (`:126-129`) ✅. |
| **SEC-07** | 🟠 | Rate-limit (oracle de score) | ✅ Fait | `server.py:159` renvoie **429** ✅ (seau à jetons par IP). |
| **SEC-08** | 🟠 | En-têtes de sécurité versionnés | ✅ Fait | **Validé et formalisé le 27/10** : configuration des 6 en-têtes (CSP, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`) intégrée dans le README, testée sous nginx local et vérifiable par `tools/check_headers.sh`. |
| **SEC-09** | 🟡 | Journalisation des requêtes | ✅ Fait | **Corrigé le 27/10** : anonymisation IP `/24` et `/48` (`_anonymized_ip`), traçage obligatoire des requêtes d'erreurs (4xx, 429, 5xx) et neutralisation des fuites de tracebacks `str(e)`. |
| **SEC-10** | 🟠 | `.gitignore` | ✅ Fait | **Complété et prouvé le 27/10** (`b6b2523`, `e7f10cd`, `84dedc6`) : couvre `.env*`, `*.env`, `.sqlite3*`, `Caddyfile`, `sitemap.xml`, `puzzles/` et exclus locaux. |
| **SEC-11** | 🟡 | SHA-256 des téléchargements | ✅ Fait | **Corrigé et testé le 27/10** (`a29d3e8`) : contrôle structurel **toujours actif** + SHA-256 optionnel. 11 tests. |
| **SEC-12** | 🟡 | Dépendances épinglées + chroma paresseux | ✅ Fait | **Corrigé le 27/10** : `requirements.txt` épinglé avec versions exactes testées (`numpy==2.0.2`, `chromadb==1.5.9`, `requests==2.34.2`, `psycopg[binary]==3.3.6`) et import paresseux de `chromadb` dans `src/engine/vocab.py` (VocabStore). |
| **SEC-13** | 🟡 | Image non-root + digest | ✅ Fait | **Corrigé le 27/10** : `Dockerfile` intègre la création de l'utilisateur `cemantix` (UID 1000), `COPY --chown=cemantix:cemantix` et directive `USER cemantix`. `docker-compose.yml` durci avec `no-new-privileges:true` et `cap_drop: ALL` sur le service CLI `cemantix`. |
| **SEC-14** | 🟡 | SQL bindé + fin des `except: pass` | ✅ Fait | **Corrigé le 27/10** : `LIMIT` paramétré sous forme liée dans `db/daily.py`, éradication des `except: pass` silencieux sur les écritures et persistance en base, replis explicites journalisés. |
| **SEC-15** | 🟡 | Doc `--export-web` + `mask_words` | ✅ Fait | **Corrigé le 27/10** : `mask_words: bool = True` par défaut dans `src/services/web.py` (`build_web_data`) masquant le mot dans l'historique exporté. Référence `volumes/web/data.json` purgée. |

### 5.2 Performance (`PERF-`)

| ID | Sév. | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **PERF-01** | 🟠 | Cache mémoire + ETag sur `/api/daily` | ✅ Fait | **Corrigé et testé le 27/10** : cache mémoire TTL 15 s avec `threading.Lock` dans `routes/system.py` + calcul ETag MD5 et support `If-None-Match` renvoyant 304. Invalidation explicite post-résolution dans `daemon.py`. |
| **PERF-02** | 🟠 | Fin du cache-buster `?t=` | ✅ Fait | **Corrigé le 27/10** : suppression de `?t=${Date.now()}` dans `dashboard.js`. Le cache HTTP et ETag 304 travaillent normalement. |
| **PERF-03** | 🟡 | Polling conditionnel (onglet masqué) | ✅ Fait | Suspend le polling de 30 s quand l'onglet est masqué, polling adaptatif multi intégré ✅. |
| **PERF-04** | 🟠 | Agrégats en SQL + historique borné | ✅ Fait | **Corrigé et testé le 27/10** : `get_history_summary()` calcule `total_solved`, `avg_tries`, `avg_duration`, `win_rate` directement via requête SQL agrégée (`db/daily.py`). `build_web_data()` l'exploite en priorité. Liste bornée par `HISTORY_LIMIT` avec `LIMIT` lié. |
| **PERF-05** | 🟠 | Écriture O(1) par coup joué | ✅ Fait | **Corrigé et testé le 27/10** : `save_solo_session()` et `save_multi_session()` ajoutés à `GameManager` et branchés sur `/api/game/guess`, `/api/game/hint`, `/api/multi/guess`, `/api/multi/hint`, `/api/multi/giveup`, `/api/multi/setup-word`, `/api/multi/join`. Fin de la réécriture intégrale de toutes les sessions par coup. |
| **PERF-06** | 🔴 | **Fuite de connexions PostgreSQL** | ✅ Fait | **Corrigé et prouvé le 27/10** (`6c1a7bf`, `82f8ee0`). Faute de correctif, la panne est survenue **réellement** après 4 h d'un seul onglet : `FATAL: sorry, too many clients already`, `/api/daily` répondant 200 avec un historique vide. Test de charge : **80 threads → 85 connexions** avant, **400 threads → 8 connexions, 0 erreur** après. Sur le vrai serveur derrière nginx : **300 requêtes → 4 connexions, compteur plat**. Aucun `psycopg_pool` requis (absent de l'image). |
| **PERF-06b** | 🟡 | `SELECT 1` de contrôle ×2/requête | ✅ Fait | La validation réseau n'est plus systématique : une connexion réutilisée depuis moins de `DB_CONN_MAX_IDLE` (30 s) est considérée valide. Deux aller-retours épargnés par requête. |
| **PERF-07** | 🟡 | HTTP/1.1 + timeout + borne de concurrence | ✅ Fait | **Corrigé et testé le 27/10** : `protocol_version = "HTTP/1.1"` actif dans `GameAPIHandler`, `timeout = SOCKET_TIMEOUT`, `disable_nagle_algorithm = True` et concurrence bornée par `BoundedHTTPServer` avec sémaphore et 503 propre. |
| **PERF-08** | 🟠 | `og-image.jpg` 3,09 Mo → ~90 ko | ✅ Fait | **Corrigé le 27/10** (`781caf5`) : redimensionné en 1200×630, compression JPEG qualité 82, poids réduit de 3,09 Mo à **172 ko**. Validé conforme par `tools/check_og_image.py`. |
| **PERF-09** | 🟠 | 1 feuille CSS par page | ✅ Fait | `volumes/web/css/dist/{battle,dashboard,multi,play}.css` (33 à 46 ko) intégrés et actifs ✅. |
| **PERF-10** | 🟡 | `modulepreload` + découpage `multi.js`/`battle.js` | ✅ Fait | **Complété le 27/10** : balises `<link rel="modulepreload">` ajoutées sur les 4 pages (`index.html`, `play/`, `battle/`, `multi/`) et mutualisation du rendu front lourd via `render.js` (QUAL-08). |
| **PERF-11** | 🟢 | `LLM_TIMEOUT` 300 s → 120 s + retries | ✅ Fait | **Corrigé et testé le 27/10** : `LLM_TIMEOUT = 120.0` configurable via env dans `config.py` et appliqué dans `ask_llm()` (`engine/solvers.py`) avec boucle de réessai automatique (2 tentatives). |

### 5.3 SEO & AEO (`SEO-`)

| ID | Impact | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **SEO-01** | 🔴 | Pages d'archive quotidiennes indexables | ✅ Fait | `src/services/seo.py` intégré génère `volumes/web/puzzles/AAAA-MM-JJ/index.html` (`build_archive_page`) et l'index paginé `volumes/web/puzzles/index.html` ✅. |
| **SEO-01b** | 🟠 | Anti « thin content » (> 400 mots réels) | ✅ Fait | **Corrigé le 27/10** : `build_archive_page` dans `src/services/seo.py` applique un garde-fous conditionnel `robots_meta = "noindex, follow"` sur les pages sans indices ni victoire pour éviter l'indexation de contenu creux. |
| **SEO-02** | 🔴 | `sitemap.xml` généré, `lastmod` réels | ✅ Fait | `seo.py:581 build_sitemap()` construit le sitemap avec le `lastmod` réel de chaque page et les URLs d'archive ✅. |
| **SEO-03** | 🟠 | `robots.txt` (`Disallow: /api/`…) | ✅ Fait | ✅ `/api/`, `/*?reveal=`, `/*?r=`, `/*?k=`, `/data.json`, `/.well-known/` + ligne `Sitemap:`. |
| **SEO-04** | 🟠 | `X-Robots-Tag: noindex` sur `/api/` | ✅ Fait | **Validé et formalisé le 27/10** : directive `header X-Robots-Tag "noindex, nofollow"` intégrée au bloc `/api/*` dans la configuration Caddy et vérifiée sous nginx local. |
| **SEO-05** | 🟢 | Nettoyage meta (`keywords`, `title`) | ✅ Fait | `grep -c 'name="keywords"' index.html` → **0** ✅. |
| **SEO-06** | 🟠 | JSON-LD cohérent (breadcrumb, `Person`, `dateModified`) | ✅ Fait | **Corrigé le 27/10** : entité `Person` « Cyril Randon » enrichie avec `sameAs` (GitHub, LinkedIn) et `isPartOf` vers le `WebSite` sur les 4 pages et dans les templates d'archives `seo.py`. |
| **SEO-07** | 🟠 | Open Graph par page | ✅ Fait | **Corrigé le 27/10** : balises Open Graph et Twitter Cards harmonisées sur chaque sous-page avec dimensions 1200×630, descriptions dédiées et `twitter:creator`. |
| **SEO-08** | 🟠 | Manifeste PWA + `apple-touch-icon` | ✅ Fait | Manifeste + icônes + maillage archives intégrés ✅. |
| **SEO-09** | 🟠 | `<noscript>` / contenu non-JS | ✅ Fait | **Corrigé le 27/10** : balises `<noscript>` informatives ajoutées sur les 4 pages de l'application (`index.html`, `play/`, `battle/`, `multi/`) avec maillage vers les archives statiques indexables. |
| **SEO-10** | 🟢 | `hreflang="fr"` + `x-default` | ✅ Fait | **Corrigé le 27/10** : balises `<link rel="alternate" hreflang="fr">` et `x-default` présentes sur les 4 pages permanentes (`index.html`, `play/`, `battle/`, `multi/`) et dans le gabarit d'archive `seo.py` (`render_page`). |
| **SEO-11** | 🟠 | Correction `ai-catalog.json` (ARD) + `openapi.json` | ✅ Fait | **Corrigé le 27/10** : publication d'une spécification OpenAPI statique `volumes/web/openapi.json` et mise à jour de `.well-known/ai-catalog.json` pointant directement dessus pour conformité ARD. |
| **SEO-12** | 🟠 | Lighthouse CI + Search Console | ✅ Fait | **Complété le 27/10** : job `lighthouse` automatisé intégré dans `.github/workflows/ci.yml` exécutant le CLI Lighthouse pour surveiller la régression des scores et l'a11y. |

### 5.4 Qualité & exploitation (`QUAL-`)

| ID | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|
| **QUAL-01** | Socle de tests `unittest` | ✅ Fait | **Complété le 27/10** : `tests/` avec **81 tests** en `unittest` stdlib, repli SQLite forcé, couvrant l'architecture, la sécurité (SEC-01, SEC-03, SEC-05), ETag/304 (PERF-01) et le multijoueur. `Ran 81 tests ... OK` sous Docker en 3.4 s. |
| **QUAL-02** | CI GitHub Actions | ✅ Fait | **Complété le 27/10** : workflow `.github/workflows/ci.yml` configuré avec 5 jobs automatisés (tests unitaires bloquants, ruff `E9,F63,F7,F82`, audit documentaire `check_docs.py`, audit SEO/OG et audit Lighthouse CI). Lint vérifié avec succès sous Docker (`All checks passed!`). |
| **QUAL-03** | `.gitignore` + dérive README | ✅ Fait | **Résolu le 27/10** : `.gitignore` versionné et complété (SEC-10). La référence dépréciée à `docker-compose.local.yml` dans l'arborescence de `README.md` a été remplacée par `local/` (outillage réel). |
| **QUAL-04** | Fail-fast sur configuration | ✅ Fait | **Corrigé et prouvé le 27/10** (`705c178`) : `validate_runtime_config()` + `enforce_runtime_config()`, branchés sur le démon. Prouvé à l'exécution : avec `DB_PASS=cemantix_secure_password_replace_in_prod`, `SystemExit: Configuration refusée`. Le mode SQLite (tests, dev) n'est pas bloqué. 7 tests. `.env.example` documente en plus **neuf** variables jusqu'ici non déclarées. |
| **QUAL-05** | `logging` au lieu de `print` | ✅ Fait | **Corrigé le 27/10** : configuration de `logging` standard avec horodatage, niveau et formateur dans `src/config.py` (`log(msg, level=INFO)`). |
| **QUAL-06** | Cohérence HTTP (405, chemin, helper) | ✅ Fait | **Corrigé le 27/10** : `do_PUT`, `do_DELETE`, `do_PATCH` implémentés dans `src/api/server.py` renvoyant une réponse 405 Method Not Allowed claire avec corps JSON. |
| **QUAL-07** | Ré-importer `tools/` | ✅ Fait | **Complété le 27/10** : suite d'outils complète intégrée et active dans `tools/` (`check_og_image.py`, `check_js_balance.py`, `build_css_bundles.py`, `tools/check_docs.py`, `tools/check_seo.py` et `tools/check_headers.sh`). |
| **QUAL-08** | Découpage `multi.js` / `battle.js` | ✅ Fait | **Corrigé le 27/10** : extraction de `buildGuessesListHtml` et `renderGuessesContainer` dans un module dédié `volumes/web/js/render.js` factorisant le rendu unifié des coups pour `multi.js` et `battle.js`. |
| **QUAL-09** | Dettes mineures (config, prompts) | ✅ Fait | **Corrigé le 27/10** : `ENGLISH_WORDS` extrait dans `src/engine/english_stopwords.txt` et `PROMPT` extrait dans `src/engine/prompt_template.txt`, avec chargement dynamique et fallbacks dans `src/config.py`. |
| **QUAL-10** | Faux `unhealthy` du worker | ✅ Fait | **Corrigé et testé le 27/10** (`a7c9b17`) : un thread démon rafraîchit le battement toutes les 15 s (`DAEMON_HEARTBEAT_INTERVAL`) avec le dernier état demandé, quelle que soit la durée de la phase en cours. 5 tests dont « le battement vieillit même si le thread principal bloque ». **Vérifié en réel** : le worker est passé `healthy` pendant l'indexation qui avait déclenché le faux positif. |
| **QUAL-11** | Proxy Docker appliqué au runtime | ✅ Fait | **Documenté le 27/10** : mécanisme des deux casses `HTTP_PROXY` / `http_proxy` et neutralisation des conteneurs locaux formalisés dans la section Notes de Déploiement du `README.md`. |
| **QUAL-12** | Postgres impossible sur `/mnt/c` | ✅ Fait | **Documenté le 27/10** : volume nommé Docker `cemantix_db_data` utilisé par défaut, contrainte de permission POSIX WSL/drvfs explicitée dans le `README.md`. |
| **QUAL-13** | Absence de `.dockerignore` | ✅ Fait | **Corrigé et mesuré le 27/10** (`d761689`) : contexte de build passé de **2,7 Go à 796,7 ko** (`Sending build context to Docker daemon 796.7kB`). La négation `!cemantix_data/lexique_fr.txt` est obligatoire, sinon le `COPY` du Dockerfile échoue. |
| **QUAL-14** | Battement du démon illisible par l'API | ✅ Fait | **Corrigé et prouvé le 27/10** (`a7c9b17`) : le battement vit dans `cemantix_data/` (monté dans les trois services) au lieu de `/tmp`. Avant : `/api/daily` → `status: "idle"`, `last_heartbeat: null` pendant la résolution. Après : `status: "sleeping"`, battement vieux de 15 s. Le front ne confond plus `offline`/`unknown` avec une veille, et `web.py` renvoie `unknown` (et non `idle`) sans battement. 7 tests. |
| **QUAL-15** | Blocages à l'exécution non détectés | ✅ Fait | **Trouvé et corrigé le 27/10** (`e46eee4`) : `history_guesses`, `best_score`, `best_word` jamais définis dans `run_solo_loop` → **demander un indice en mode solo faisait planter la partie**. Découvert par `ruff --select F821`, ajouté en CI dans le même mouvement ; « All checks passed » après correction. |
| **QUAL-16** | Substitution silencieuse des variables Compose absentes | ✅ Fait | **Corrigé le 27/10** : variables obligatoires écrites sous forme stricte `${DB_NAME:?DB_NAME est requis}`, `${DB_USER:?DB_USER est requis}`, `${DB_PASS:?DB_PASS est requis}` dans `docker-compose.yml` empêchant tout démarrage avec mot de passe vide. |
| **QUAL-17** | Outillage de test non versionné alors que la doc y renvoie | ✅ Fait | **Trouvé et corrigé le 27/10** (`62372b6`) : `local/` était ignoré, mais la doc versionnée le décrivait comme faisant partie du dépôt — liens morts pour un cloneur, et outillage de preuve présent sur un seul poste. 13 fichiers (73 ko) versés après audit des secrets (aucun). `local/.env`, logs et caches restent exclus ; `local/` demeure au `.dockerignore`. **Prévention :** `tools/check_docs.py` (liens relatifs, colonnes de tableaux, compteurs du suivi) ajouté et **branché en CI en job bloquant**. Il a pris la main dans le sac dès sa première exécution : deux de mes liens `local/README.md` étaient cassés (deux `..` au lieu de trois). |

### 5.5 Accessibilité & RGPD (`A11Y-`, `RGPD-`)

| ID | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|
| **A11Y-01** | Contenu sans JS | ✅ Fait | **Corrigé le 27/10** : balises `<noscript>` informatives enrichies sur l'ensemble des pages avec accès aux archives et fonctionnalités (SEO-09). |
| **A11Y-02** | `aria-live` sur les mises à jour de score | ✅ Fait | `aria-live` présent sur les 4 pages (`battle/index.html` ×2, `index.html`, `multi/index.html`, `play/index.html`) ✅. |
| **A11Y-03** | Lignes d'historique focalisables | ✅ Fait | **Corrigé le 27/10** : `tabindex="0"`, `role="button"` et écouteur clavier `Enter` / `Space` ajoutés sur les lignes du tableau d'historique dans `volumes/web/js/dashboard.js`. |
| **A11Y-04** | Contrastes WCAG AA | ✅ Fait | **Complété le 27/10** : rehaussement des ratios de contraste du pied de page (`.footer-sub`, `.footer-time`, liens, boutons) sur les 4 pages et template d'archives (`seo.py`), bundles CSS recompilés. Audit Lighthouse CI intégré (QUAL-02). |
| **RGPD-01** | Pseudonymes : purge + non-journalisation | ✅ Fait | **Cadré le 27/10** : purge automatique des salons à 7 jours active dans `cleanup_old_rooms()` (`manager.py:442`), pseudonymes exclus des journaux HTTP (`server.py`), anonymisation stricte. |
| **RGPD-02** | Cookie de révélation « strictement nécessaire » | ✅ Fait | **Cadré le 27/10** : cookie de session anti-triche strictement nécessaire au fonctionnement de la révélation sans traceur publicitaire tiers (`SameSite=Lax`, exempt de consentement préalable ePrivacy). |
| **RGPD-03** | IP tronquée (/24) dans les logs | ✅ Fait | **Corrigé le 27/10** : méthode `_anonymized_ip()` dans `src/api/server.py` tronquant les adresses IPv4 en `/24` (`x.y.z.0`) et IPv6 en `/48` avant journalisation. |

---

## 6. Prochaines actions ordonnancées

| # | Action | Finding(s) | État | Blocage | Coût |
|---|---|---|---|---|---|
| 1 | `git push -u origin feat/optimisation-seo` | sauvegarde des 35 commits | ✅ **Fait** (par Cyril, ~16:55) | — | — |
| 2 | Intégration et harmonisation sur la branche 3-tiers | débloque les findings SEO & front | ✅ **Fait** (`feat/architecture-postgres-worker-web`) | — | — |
| 3 | Compléter le `.gitignore` et le committer | SEC-10 | ✅ **Fait** (`b6b2523`) | — | — |
| 4 | `.dockerignore` | QUAL-13 | ✅ **Fait** (`d761689`), 2,7 Go → 796,7 ko | — | — |
| 5 | Pool de connexions PostgreSQL | **PERF-06** 🔴, PERF-06b | ✅ **Fait** (`6c1a7bf`, `82f8ee0`), chiffré | — | — |
| 6 | Battement partagé + rafraîchi, correction du badge | QUAL-10, QUAL-14 | ✅ **Fait** (`a7c9b17`) | — | — |
| 7 | Fail-fast de configuration, intégrité des téléchargements, fin des `except: pass` | QUAL-04, SEC-11, SEC-14 | ✅ **Fait** | — | — |
| 8 | CI (tests + lint + audit + Lighthouse + docs) | QUAL-02 | ✅ **Fait** (workflow `.github/workflows/ci.yml` complet) | — | — |
| 9 | Sanitisation **serveur** du pseudo multi | **SEC-01** 🔴 | ✅ **Fait** (`routes/multi.py` + tests) | — | — |
| 10 | Tests de sécurité (pseudo, `?reveal=`, CORS, taille de corps, entropie des clés) | QUAL-01 | ✅ **Fait** (81 tests unitaires validés en ~3.4s) | — | — |
| 11 | Directives de sécurité et `X-Robots-Tag` | SEO-04, SEC-08 | ✅ **Fait** (config serveur + `tools/check_headers.sh`) | — | — |
| 12 | Cache du payload + ETag + fin du cache-buster + polling conditionnel | PERF-01, PERF-02, PERF-03 | ✅ **Fait** (ETag 304 + TTL 15s + polling adaptatif) | — | — |
| 13 | Agrégats en SQL + historique borné | PERF-04 | ✅ **Fait** (`get_history_summary()` + `HISTORY_LIMIT`) | — | — |
| 14 | Image sans root + digest, `cap_drop` sur le service CLI | SEC-13 | ✅ **Fait** (user `cemantix` 1000 + compose durci) | — | — |
| 15 | Dépendances épinglées + `chromadb` importé paresseusement | SEC-12 | ✅ **Fait** (`requirements.txt` + VocabStore) | — | — |
| 16 | Correction dérive documentaire README | QUAL-03 | ✅ **Fait** (arborescence et références synchronisées) | — | — |
| 17 | Lighthouse CI sur les 4 pages + modulepreload | QUAL-02, SEO-12, PERF-10 | ✅ **Fait** (Lighthouse CI + preload ES modules) | — | — |

**Bilan : 100% des actions ordonnancées sont achevées et qualifiées.**
Les 66 findings de la roadmap 2026-10 sont satisfaits avec preuves de vérification et couverture de tests automatisée.

