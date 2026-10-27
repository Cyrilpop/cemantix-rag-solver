# 📊 Avancement — Plan d'optimisation

> **Évolution :** [2026-10 · Sécurité, SEO, performance, qualité](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Dernière mise à jour :** 27/10/2026 12:10

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`SEC-03`, `PERF-06`…).
   Un ID n'est jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte** (colonne
   « Vérification » du plan). **Un commit, ou son message, ne vaut pas preuve** : le contrôle
   systématique des 35 commits (journal du 27/10 12:05) l'a démontré — `fix(xss)` ne couvre pas SEC-01.
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
| ✅ Fait | **1** | 0 |
| ⚠️ Partiel | **12** | 0 |
| ♻️ Branche SEO (non fusionné) | **11** | 3 |
| 🧪 Local (prouvé sous nginx) | **2** | 0 |
| ⬜ À faire | **37** | 3 |
| **Total suivis** | **63** | **6** |

Répartition par famille : `SEC` 17 · `PERF` 12 · `SEO` 13 · `QUAL` 14 · `A11Y` 4 · `RGPD` 3.

**Les 6 findings critiques :** `SEC-01` (⬜), `SEC-01b` (♻️), `SEC-02` (♻️), `SEC-03` (♻️),
`PERF-06` (⬜), `SEO-01` (⬜).

**Lecture honnête :** l'essentiel du travail déjà produit est sur une branche **non fusionnée et non
poussée**. **Sur la branche de travail actuelle, rien n'est fermé** — le seul ✅ (`A11Y-04`) l'est
parce qu'il a été fusionné dans `main` avant l'audit. Deux findings critiques sont en outre
**constatés en réel** dans l'environnement de test : `SEC-03` et `SEC-05`.

---

## 2. État des dépôts

Mesuré le 27/10/2026 à 11:28 via `git ls-remote` (état réel sur GitHub, pas le cache local).

| Branche | Local | GitHub | Écart |
|---|---|---|---|
| `feat/architecture-postgres-worker-web` ← *courante* | `03af761` | `03af761` | synchrone |
| `feat/optimisation-seo` | `cebd2c7` | `c72fed7` | ⚠️ **35 commits jamais poussés** |
| `fix/accessibilite-contraste-pagespeed` | `e25c319` | `e25c319` | synchrone |
| `main` | `68708ff` | `9e1de80` | en retard de 4 (PR #18 fusionnée en amont) |

- **Arbre de travail :** propre — seules `?? .gitignore` et `?? .idea/` en non suivi ; aucun fichier
  versionné modifié.
- **`feat/optimisation-seo` n'a pas d'upstream** (`branch.feat/optimisation-seo.remote` vide) :
  d'où l'absence d'indicateur `[ahead 35]` dans `git status`.
- **Composition des 35 commits :** `14 docs`, `9 fix`, `8 perf`, `2 feat`, `1 refactor`, `1 chore`
  — 34 fichiers, **+3 346 / −209**.
- **Push vérifié sans risque :** `git merge-base --is-ancestor origin/feat/optimisation-seo
  feat/optimisation-seo` → vrai, donc **fast-forward pur**, aucun conflit possible.
- **Secrets :** `.env` n'a **jamais** été versionné sur aucune branche (`git log --all -- .env`
  vide) → aucune purge d'historique ni rotation obligatoire.

---

## 3. Environnement de test (WSL Ubuntu-20.04 + nginx)

Hors git (`/local/`). URL : **http://localhost:8090**. Documentation : `local/README.md`.

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
| 27/10 12:10 | — | Transfert du plan et du suivi sous git dans `Evolution/ITRE/` | ce fichier |

---

## 5. Suivi des findings

### 5.1 Sécurité (`SEC-`)

| ID | Sév. | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **SEC-01** | 🔴 | Sanitisation **serveur** du pseudo multi | ⬜ À faire | **Contrairement à ce qu'annonce le commit `fix(xss)`** : `routes/multi.py:40` de la branche SEO fait encore `str(data.get("player_name") or "Joueur 1").strip()` — aucun filtre. L'échappement n'existe qu'à l'affichage (SEC-01b) : la donnée sale est toujours stockée. |
| **SEC-01b** | 🔴 | `escapeHtml` + audit des 28 `innerHTML` | ♻️ Branche SEO | `volumes/web/js/utils.js:16 export function escapeHtml` ✅. À re-vérifier après merge (couverture des 28 sites). |
| **SEC-02** | 🔴 | Suppression des `onclick` inline | ♻️ Branche SEO | `grep -c 'onclick="copyToClipboard' battle.js` → **0** ✅. Prérequis d'une CSP stricte acquis. |
| **SEC-03** | 🔴 | Fin du `?reveal=true` public | ♻️ Branche SEO | `POST /api/daily/reveal` existe, `is_revealed` forcé à `False`, **0** occurrence côté client ✅. **Mais ouvert sur la branche de travail** et **constaté en réel** (smoke test). |
| **SEC-04** | 🟠 | Allowlist CORS | ♻️ Branche SEO | `server.py:87` écho de l'origine (plus de `*`) ✅. |
| **SEC-05** | 🟠 | Entropie des clés salon/joueur | ⚠️ Partiel | Branche SEO : `uuid4().hex[:8]` = **32 bits** pour salon *et* clés (`multi.py:59-60`, `manager.py:341`). Le plan demande **128 bits** pour les clés, via `secrets` et non `uuid4`. Clé de 7 caractères **mesurée**. |
| **SEC-05b** | 🟠 | Hachage HMAC des clés en base | ⬜ À faire | `grep -e hmac -e key_hash db/multi.py database/init.sql` → **0** sur les deux branches. |
| **SEC-06** | 🟠 | Corps de requête borné + `int()` protégé | ♻️ Branche SEO | `server.py:40 MAX_BODY_BYTES` (32 ko) + lecture protégée (`:126-129`) ✅. |
| **SEC-07** | 🟠 | Rate-limit (oracle de score) | ♻️ Branche SEO | `server.py:159` renvoie **429** ✅. À valider après merge : grain IP+chemin, `X-Forwarded-For` accepté via Caddy seul. |
| **SEC-08** | 🟠 | En-têtes de sécurité versionnés | ⚠️ Partiel | `Caddyfile` **versionné à la racine** sur la branche SEO ✅, mais **sans `X-Robots-Tag`** (grep → 0). Les 6 en-têtes existent en revanche côté **nginx local** 🧪. |
| **SEC-09** | 🟡 | Journalisation des requêtes | ⚠️ Partiel | `server.py:211 log_message` redéfini sur la branche SEO ✅ ; traçage des 4xx/429 et suppression de `str(e)` à confirmer. |
| **SEC-10** | 🟠 | `.gitignore` | ⚠️ Partiel | Branche SEO : fichier existant (`e35cdf1`) mais **sans ligne `.env`**. Version locale complète (`.env`, `/local/`, `*.npy`, `*_words.txt`) **non committée** → fusionner + compléter. |
| **SEC-11** | 🟡 | SHA-256 des téléchargements | ⬜ À faire | `grep sha256 engine/vocab.py` → **0**. |
| **SEC-12** | 🟡 | Dépendances épinglées + chroma paresseux | ⬜ À faire | `requirements.txt` = 3 bornes (`numpy`, `chromadb`, `requests`), **aucun verrou**. Build mesuré : installe `kubernetes`, `onnxruntime`, `opentelemetry-*` pour un service web qui n'indexe jamais. |
| **SEC-13** | 🟡 | Image non-root + digest | ⬜ À faire | `grep -E '^USER' Dockerfile` et `grep useradd Dockerfile` → **0** sur les deux branches. |
| **SEC-14** | 🟡 | SQL bindé + fin des `except: pass` | ⬜ À faire | Toujours présents sur la branche SEO (`system.py` 2, `server.py` 2, `cli/menu.py` 4…). |
| **SEC-15** | 🟡 | Doc `--export-web` + `mask_words` | ⚠️ Partiel | La mention `volumes/web/data.json` a **disparu** de `README.md`/`cemantix_rag.py` sur la branche SEO ✅, mais `mask_words` **n'existe pas** dans `services/web.py` : l'historique exporte donc toujours `word` en clair. |

### 5.2 Performance (`PERF-`)

| ID | Sév. | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **PERF-01** | 🟠 | Cache mémoire + ETag sur `/api/daily` | ⬜ À faire | `grep -e ETag -e If-None-Match src/api` → **0** sur les deux branches. |
| **PERF-02** | 🟠 | Fin du cache-buster `?t=` | ⚠️ Partiel | Branche SEO : **1** occurrence restante de `Date.now()` dans `dashboard.js` (contre 3 sur la branche de travail). |
| **PERF-03** | 🟡 | Polling conditionnel (onglet masqué) | ♻️ Branche SEO | Commit `perf(dashboard): suspend le polling…` ✅ — patron réutilisable pour la suite. |
| **PERF-04** | 🟠 | Agrégats en SQL + historique borné | ⬜ À faire | `db/daily.py` : `SELECT *` sans `LIMIT`, colonne `trajectory` chargée dans la liste. |
| **PERF-05** | 🟠 | Écriture O(1) par coup joué | ⬜ À faire | `_save_sessions()` réécrit **toutes** les sessions à chaque guess. |
| **PERF-06** | 🔴 | **Fuite de connexions PostgreSQL** | ⬜ À faire | **Non applicable sur la branche SEO** (pré-3-tiers, pas de `db/connection.py`) → à traiter **uniquement** sur la branche courante. Mécanisme vérifié : 1 thread/requête + `threading.local()` + `_all_conns` jamais vidé (`reset()` appelé par personne). |
| **PERF-06b** | 🟡 | `SELECT 1` de contrôle ×2/requête | ⬜ À faire | Suit PERF-06. |
| **PERF-07** | 🟡 | HTTP/1.1 + timeout + borne de concurrence | ⬜ À faire | `grep protocol_version src/api/server.py` → **0** : le serveur tourne en HTTP/1.0, **keep-alive coupé**. |
| **PERF-08** | 🟠 | `og-image.jpg` 3,09 Mo → ~90 ko | ⬜ À faire | **`git ls-tree -l` sur la branche SEO : 3 091 777 octets.** L'outil de diagnostic existe (commit `perf(seo): outil de diagnostic de l'og-image`) mais **l'image n'a jamais été réduite**. |
| **PERF-09** | 🟠 | 1 feuille CSS par page | ♻️ Branche SEO | `volumes/web/css/dist/{battle,dashboard,multi,play}.css` (33 à 46 ko) ✅. |
| **PERF-10** | 🟡 | `modulepreload` + découpage `multi.js`/`battle.js` | ⚠️ Partiel | `import()` dynamique fait sur la branche SEO ✅ ; découpage en `lobby.js`/`arena.js` **non fait**. |
| **PERF-11** | 🟢 | `LLM_TIMEOUT` 300 s → 120 s + retries | ⬜ À faire | — |

### 5.3 SEO & AEO (`SEO-`)

| ID | Impact | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|---|
| **SEO-01** | 🔴 | Pages d'archive quotidiennes indexables | ⬜ À faire | Aucun `volumes/web/jour/`. **Levier n°1 du plan, non entamé.** |
| **SEO-01b** | 🟠 | Anti « thin content » (> 400 mots réels) | ⬜ À faire | Suit SEO-01. |
| **SEO-02** | 🔴 | `sitemap.xml` généré, `lastmod` réels | ⚠️ Partiel | Branche SEO : `lastmod` passé à `2026-10-26` sur 5 URLs — **toujours une date figée à la main**, pas la date réelle par URL. |
| **SEO-03** | 🟠 | `robots.txt` (`Disallow: /api/`…) | ♻️ Branche SEO | ✅ `/api/`, `/*?reveal=`, `/*?r=`, `/*?k=`, `/data.json`, `/.well-known/` + ligne `Sitemap:`. |
| **SEO-04** | 🟠 | `X-Robots-Tag: noindex` sur `/api/` | 🧪 Local | **Prouvé sous nginx local** ; **absent du Caddyfile** de la branche SEO → à y transcrire. |
| **SEO-05** | 🟢 | Nettoyage meta (`keywords`, `title`) | ♻️ Branche SEO | `grep -c 'name="keywords"' index.html` → **0** ✅. |
| **SEO-06** | 🟠 | JSON-LD cohérent (breadcrumb, `Person`, `dateModified`) | ⚠️ Partiel | Branche SEO : `HowTo` ajouté ✅ ; `BreadcrumbList`, `Person`/`sameAs` et `dateModified` dynamique restent dus. |
| **SEO-07** | 🟠 | Open Graph par page | ⚠️ Partiel | Meta de partage ajoutées ✅, mais **une seule `og-image` partagée** par les 4 pages, et toujours de 3 Mo. |
| **SEO-08** | 🟠 | Manifeste PWA + `apple-touch-icon` | ♻️ Branche SEO | Commit `9f18845` ✅ (manifeste + icônes + maillage archives). |
| **SEO-09** | 🟠 | `<noscript>` / contenu non-JS | ⬜ À faire | `grep -c noscript volumes/web` → **0** sur les deux branches. |
| **SEO-10** | 🟢 | `hreflang="fr"` + `x-default` | ⬜ À faire | `grep -c hreflang volumes/web` → **0**. |
| **SEO-11** | 🟠 | Correction `ai-catalog.json` (ARD) + `openapi.json` | ⬜ À faire | Le catalogue pointe toujours des **données** sous un `type: application/openapi+json`. |
| **SEO-12** | 🟠 | Lighthouse CI + Search Console | ⬜ À faire | Aucun `.github/` sur aucune branche. |

### 5.4 Qualité & exploitation (`QUAL-`)

| ID | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|
| **QUAL-01** | Socle de tests `unittest` | ⬜ À faire | **Aucun dossier `tests/`** sur aucune branche. |
| **QUAL-02** | CI GitHub Actions | ⬜ À faire | **Aucun `.github/`** sur aucune branche. |
| **QUAL-03** | `.gitignore` + dérive README | ⚠️ Partiel | Voir SEC-10 ; la dérive documentaire (`docker-compose.local.yml` et `.gitignore` décrits au README mais absents) reste non traitée. |
| **QUAL-04** | Fail-fast sur configuration | ⬜ À faire | `DB_PASS` d'exemple accepté au démarrage. |
| **QUAL-05** | `logging` au lieu de `print` | ⬜ À faire | `config.py:178-179` imprime avec `print(..., flush=True)`. |
| **QUAL-06** | Cohérence HTTP (405, chemin, helper) | ⬜ À faire | Patron `status_code = 400 if …` répété 8 fois. |
| **QUAL-07** | Ré-importer `tools/` | ⚠️ Partiel | `check_og_image.py`, `check_js_balance.py`, `build_css_bundles.py` existent **sur la branche SEO** ✅ ; `check_seo.py` et `check_headers.sh` à créer. |
| **QUAL-08** | Découpage `multi.js` / `battle.js` | ⬜ À faire | Rendu des coups dupliqué quasi à l'identique entre les deux fichiers. |
| **QUAL-09** | Dettes mineures (config, prompts) | ⬜ À faire | `ENGLISH_WORDS` (35 lignes de stopwords anglais) dans la config métier. |
| **QUAL-10** | Faux `unhealthy` du worker | ⬜ À faire | **Constaté en réel** : battement non rafraîchi pendant l'indexation (mesuré **1 030 s** pour un seuil de 90 s) alors que la sonde répond correctement (`exit 1`). |
| **QUAL-11** | Proxy Docker appliqué au runtime | ⬜ À faire | **Constaté en réel** : le healthcheck nginx interrogeait le proxy ; neutralisé localement (`HTTP_PROXY=`) mais **non documenté dans le README du projet**. |
| **QUAL-12** | Postgres impossible sur `/mnt/c` | 🧪 Local | **Contournement prouvé** (volume named) ; la mise en garde doit entrer dans le README. |
| **QUAL-13** | Absence de `.dockerignore` | ⬜ À faire | Contexte de build mesuré : envoie `cemantix_data/` (**2,08 Go**), `volumes/`, `.env`, `local/`, `.git/`. |
| **QUAL-14** | Battement du démon illisible par l'API | ⬜ À faire | **Constaté en réel** : `HEARTBEAT_FILE` dans `/tmp` (propre au conteneur) → le dashboard affiche un état **faux** en permanence. |

### 5.5 Accessibilité & RGPD (`A11Y-`, `RGPD-`)

| ID | Objet | Statut | Preuve / reste à faire |
|---|---|---|---|
| **A11Y-01** | Contenu sans JS | ⬜ À faire | Voir SEO-09. |
| **A11Y-02** | `aria-live` sur les mises à jour de score | ⬜ À faire | — |
| **A11Y-03** | Lignes d'historique focalisables | ⬜ À faire | À faire **avec** SEC-02 pour ne pas régresser. |
| **A11Y-04** | Contrastes WCAG AA | ✅ Fait | **Fusionné** dans `origin/main` (PR #18, `e25c319`) — seul finding fermé du plan. Reste à le **verrouiller** par Lighthouse CI (QUAL-02). |
| **RGPD-01** | Pseudonymes : purge + non-journalisation | ⬜ À faire | Purge 7 j existante ✅, journalisation à cadrer (SEC-09). |
| **RGPD-02** | Cookie de révélation « strictement nécessaire » | ⬜ À faire | Dépend de SEC-03. |
| **RGPD-03** | IP tronquée (/24) dans les logs | ⬜ À faire | Dépend de SEC-09. |

---

## 6. Prochaines actions ordonnancées

| # | Action | Finding(s) | Blocage | Coût |
|---|---|---|---|---|
| 1 | `git push -u origin feat/optimisation-seo` | — | **aucun** (fast-forward vérifié) | 1 min |
| 2 | PR `feat/optimisation-seo` → `main`, puis rebase de la branche 3-tiers | débloque 11 findings ♻️ | décision utilisateur | 0,25 j |
| 3 | Compléter/fusionner le `.gitignore` (+ `.env`, `/local/`) puis le committer | SEC-10, QUAL-03 | #2 | 15 min |
| 4 | `.dockerignore` avant le prochain build complet | QUAL-13 | aucun | 10 min |
| 5 | Sanitisation **serveur** du pseudo (le ♻️ ne couvre que l'affichage) | **SEC-01** 🔴 | #2 | 10 min |
| 6 | Tests plancher rouges + CI non bloquante | QUAL-01, QUAL-02 | #2 | 0,5 j |
| 7 | Pool de connexions PostgreSQL | **PERF-06** 🔴 | aucun (spécifique à la branche courante) | 1 h 30 |
| 8 | Transcrire `X-Robots-Tag` du nginx local vers le `Caddyfile` | SEO-04, SEC-08 | #2 | 10 min |

**Seuil de non-retour à documenter avant l'action 5 :** changer le format des clés (SEC-05) casse
les salons ouverts → garder l'ancien format 4 hex pendant 7 jours (durée de vie des salons).

