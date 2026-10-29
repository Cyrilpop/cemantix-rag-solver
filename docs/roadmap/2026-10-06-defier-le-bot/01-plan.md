# ⚔️ Plan — Défier le bot IA (défi d'un mot par le joueur)

> **Évolution :** [2026-10 · Défier le bot](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas
> reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.
> **Branche :** `feat/bot_defy` @ `8144143` (base `main` fusionnée, PR #25)
> **Date d'ouverture :** 29/10/2026

**Convention de lecture :** chaque action porte un identifiant permanent (`DEFI-`, `SEC-`,
`QUAL-`) utilisé comme **clé de suivi** dans `02-avancement.md`. Un ID ne change jamais et n'est
jamais réattribué, même après abandon (statut `Renoncé` dans le suivi). La numérotation `SEC-` /
`QUAL-` **prolonge** celle de l'évolution `2026-10-02-securite-seo-performance` (qui s'arrête à
`SEC-17` / `QUAL-17`) : aucun ID n'est réutilisé entre évolutions.

---

## 0. Méthodologie & périmètre

### 0.1 L'intention

Le joueur propose un **mot secret** ; le bot IA (le solveur RAG) doit le retrouver, coup après
coup, exactement comme il le fait chaque nuit pour le mot du jour. Le joueur suit la résolution
**en direct** avec le même modèle d'affichage que les pages existantes (trajectoire, météo,
températures), et reçoit le dénouement : gagné / non-gagné, nombre de coups, durée.

**Quota anti-spam : 10 défis par heure et par visiteur.**
*Une **liste blanche (whitelist)** d'adresses IP permet d'accorder un nombre illimité de défis à une ou plusieurs adresses IP (ex. IP d'administration `12.34.56.78`). Cette liste blanche est configurable dynamiquement via la console admin et persistée.*

### 0.2 Le principe structurant : tri-partite, sans réinvention

| Tiers | Rôle | Ce qu'il ne fait PAS |
|---|---|---|
| `cemantix_web` (API + front) | Valide le mot, applique le quota, **enqueue** la demande en PostgreSQL, sert l'état et le flux en direct | **Aucun calcul** : le conteneur web ne charge ni modèle vectoriel, ni ChromaDB, ni solveur |
| PostgreSQL 16 | File de tâches + résultat : table `bot_challenges` (statut, trajectoire incrémentale) | — |
| `cemantix_worker` (démon) | **Pick-up** des défis, exécution du solveur, écriture de la trajectoire au fil de l'eau | Ne parle jamais au navigateur |

La résolution réutilise **tel quel** le moteur existant du CLI principal (`cemantix_rag.py`) :

- `Solver` (`src/engine/solvers.py:128`) : régression Ridge + k-NN ChromaDB + reranking +
  trajectoire structurée (`Solver.trajectory`, `src/engine/solvers.py:187-195`) ;
- `MockClient(store, secret=…)` (`src/engine/clients.py:88`) : c'est **déjà** l'oracle « un joueur
  impose son mot secret et je score chaque essai contre lui » — c'est l'option `--secret` du CLI.
  Scores cosinus réels, rangs permille exacts, `1.0 / 1000 ‰` sur le mot trouvé. Rien à réécrire.

Le seul travail est le **canal** (file PostgreSQL), le **quota**, le **flux en direct** et la
**page** — pas l'IA.

### 0.3 Le direct, sans réinvention non plus

La console admin (`/api/snap-9x/logs/stream`) diffuse déjà en `text/event-stream` via
`_send_sse` (`src/api/server.py:120-144`) avec un producteur qui émet des lignes au fil de l'eau.
Le défi reprend **le même mécanisme** : le producteur SSE relit la trajectoire en base (écrite par
le worker) et émet les nouveaux coups. Le front consomme ce flux comme la console admin consomme
le sien, avec repli polling.

### 0.4 Périmètre couvert

| Zone | Fichiers visés | Nature |
|---|---|---|
| Données | `database/init.sql`, `src/db/connection.py`, nouveau `src/db/challenges.py` | nouvelle table + table whitelist + DAO |
| API | nouveau `src/api/routes/challenge.py`, `src/api/routes/admin.py`, `src/api/server.py`, `src/api/routes/__init__.py` | 3 routes publiques + routes admin whitelist + dispatch |
| Worker | `src/services/daemon.py` | pick-up dans la boucle de veille |
| Frontend | nouveau `volumes/web/defi/index.html`, nouveau `volumes/web/js/defi.js`, `volumes/web/js/trajectory.js`, pages avec `nav-tabs`, console admin | 1 page + 1 module JS + section admin |
| Qualité | `tests/**`, `volumes/web/openapi.json`, `README.md`, `CHANGELOG.md` | tests + doc |

**Méthode :** chaque action est notée avec (1) l'**ancre de réutilisation `fichier:ligne` vérifiée
dans le code**, (2) la **spécification** du travail, (3) un **critère de vérification exécutable**.

**Sévérités :** 🔴 critique (faille de sécurité ou blocage fonctionnel) · 🟠 élevé · 🟡 moyen · 🟢 faible.

---

## 1. Synthèse

### 1.1 Verdict de faisabilité

Tout l'algorithmique existe déjà et tourne en production chaque nuit. L'évolution se réduit à :

1. **une table** (`bot_challenges`) qui fait office de file de tâches tri-partite ;
2. **trois routes** publiques (`POST /api/challenge`, `GET /api/challenge/<id>`,
   `GET /api/challenge/<id>/stream`) dans le conteneur web, sans aucun calcul ;
3. **un pick-up** dans la boucle de veille du démon, entre deux résolutions nocturnes ;
4. **une page** « Défier le bot » qui rejoue la trajectoire en direct avec les gabarits existants.

### 1.2 Les 7 risques à neutraliser d'office (aucune faille tolérée)

| # | Risque si c'est fait naïvement | Parade exigée par ce plan |
|---|---|---|
| 1 | L'API web exécute le solveur → conteneur web saturé (des minutes de CPU, 1 Go) | Interdit structurel : la route n'importe jamais `src.engine.solvers` ; file PostgreSQL uniquement (`DEFI-04`) |
| 2 | Un mot arbitraire lancé en boucle = oracle de similarité + DoS du worker | Quota **10/h persisté en base** (survit aux redémarrages), file d'attente bornée, `max_tries` plafonné (`SEC-20`, `SEC-24`) |
| 3 | Le mot du joueur est du HTML/JS → XSS stocké à la relecture | Validation stricte `^[a-zà-ÿ-]{3,24}$` + appartenance au lexique, `escapeHtml()` systématique (`SEC-25`, `DEFI-08`) |
| 4 | Identifiants de défi séquentiels → énumération, lecture des défis d'autrui | Identifiant aléatoire 128 bits (`SEC-22`) |
| 5 | SSE public = un thread retenu par onglet ouvert → épuisement des 64 workers | Plafond global de flux SSE simultanés + durée maximale de flux (`SEC-23`) |
| 6 | La trajectoire révèle le mot avant la fin du défi | `Cache-Control: no-store` partout ; le mot n'est renvoyé qu'au statut final (`SEC-26`) |
| 7 | Données personnelles : IP + mots saisis par le public | IP **hachée salée** (HMAC, non réversible), purge automatique à 30 jours (`SEC-21`, `SEC-27`) |

### 1.3 Chiffrage

| Phase | Contenu | Estimé |
|---|---|---|
| 1 | Données : table + DAO + purge (`DEFI-01..03`) | 0,25 j |
| 2 | API : création, statut, SSE, quota, validation (`DEFI-04..08`) | 0,5 j |
| 3 | Worker : pick-up + résolution + trajectoire incrémentale (`DEFI-09..13`) | 0,5 j |
| 4 | Front : page, JS direct, modal trajectoire (`DEFI-14..17`) | 0,5 j |
| 5 | Sécurité transverse durcie (`SEC-20..28`) | 0,25 j |
| 6 | Tests, doc, recette (`QUAL-20..22`) | 0,25 j |
| **Total** | | **2,25 jours** |

---

## 2. Données — la file de tâches tri-partite

### 2.1 Schéma cible

```sql
CREATE TABLE IF NOT EXISTS bot_challenges (
    id               VARCHAR(32) PRIMARY KEY,     -- hex aléatoire 128 bits, jamais séquentiel
    secret_word      VARCHAR(64) NOT NULL,        -- mot validé (minuscules, lexique uniquement)
    ip_hash          CHAR(64) NOT NULL,           -- HMAC-SHA256 salé de l'IP anonymisée /24
    status           VARCHAR(16) NOT NULL DEFAULT 'queued',  -- queued|running|solved|lost|error
    tries_count      INT NOT NULL DEFAULT 0,
    duration_seconds NUMERIC(8, 2),
    max_tries        INT NOT NULL DEFAULT 100,
    trajectory       JSONB NOT NULL DEFAULT '[]'::jsonb,
    error            VARCHAR(200),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    heartbeat_at     TIMESTAMPTZ                  -- preuve de vie du worker sur la tâche
);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_queue ON bot_challenges (status, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_ip ON bot_challenges (ip_hash, created_at);

-- Table des IPs exemptées de quota (whitelist administrable)
CREATE TABLE IF NOT EXISTS bot_challenge_whitelist (
    ip_address       VARCHAR(45) PRIMARY KEY,     -- IPv4 ou IPv6 exacte (ou /24)
    description      VARCHAR(100),                -- motif / nom (ex. "Bureau Cyril", "Admin")
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 Actions

| ID | Action | Spécification | Sévérité |
|---|---|---|---|
| **DEFI-01** | Table `bot_challenges` & `bot_challenge_whitelist` | Ajouter le DDL ci-dessus à `database/init.sql` **et** aux schémas auto-créés de `src/db/connection.py` (`PG_SCHEMA` + DDL SQLite équivalent, même convention que `daily_puzzles`, `src/db/connection.py:58-89`) pour que les tests hors conteneur fonctionnent | 🟠 |
| **DEFI-02** | DAO `src/db/challenges.py` | Fonctions : `create_challenge(word, ip_hash, max_tries)`, `claim_next_challenge()` (claim atomique : `UPDATE … SET status='running', started_at=now() WHERE id = (SELECT … WHERE status='queued' ORDER BY created_at LIMIT 1) RETURNING *`, décliné SQLite par le verrou de la couche `db`), `append_trajectory(id, steps, tries)`, `finish_challenge(id, status, tries, duration, error)`, `get_challenge(id)`, `count_recent_for_ip(ip_hash, window_seconds)`, `count_queued()`, `purge_older_than(days)`, `requeue_stale_running(max_age)`, et gestion de la whitelist : `is_ip_whitelisted(ip)`, `get_whitelist()`, `add_whitelist_ip(ip, description)`, `remove_whitelist_ip(ip)`. Repli SQLite + requêtes **100 % paramétrées** comme `src/db/daily.py` | 🟠 |
| **DEFI-03** | Cohérence des statuts | `lost` = `max_tries` atteint sans 1000 ‰ ; `error` = exception worker (mot subitement absent du store, ChromaDB HS). Un défi ne reste jamais `running` plus de `CHALLENGE_TIMEOUT` (défaut 900 s) : `requeue_stale_running` le repasse en `queued` une fois, puis en `error` | 🟡 |

**Vérification :** `python -c "from src.db.challenges import create_challenge, claim_next_challenge"` sort 0 ;
`docker compose exec cemantix_db psql -U $DB_USER -d $DB_NAME -c '\d bot_challenges'` affiche la table.

---

## 3. API web — enqueue, lecture, direct (zéro calcul)

Nouveau contrôleur `src/api/routes/challenge.py`, dispatché depuis `server.py` sur le préfixe
`/api/challenge` (même branchement que `/api/battle/`, `src/api/server.py:298-299`).

| ID | Route / action | Spécification | Sévérité |
|---|---|---|---|
| **DEFI-04** | `POST /api/challenge` | Corps `{"word": "…"}` (déjà plafonné à 32 ko par `API_MAX_BODY_BYTES`, `src/api/server.py:44`). Ordre strict : validation mot (`DEFI-08`) → vérification whitelist IP (`is_ip_whitelisted(client_ip)`) : si whitelistée, exemption totale de limite de débit et quota illimité ; sinon : quota mémoire (`DEFI-07`) → quota base (`SEC-20`) → file bornée (`SEC-24`) → `create_challenge()` → réponse `201 {"id": …, "status": "queued", "quota_restant": n}` (`quota_restant` : nombre ou `null`/`"unlimited"` si whitelisté). **Aucun import de `src.engine.solvers` ni `src.services.daemon` dans cette route** : le web écrit une ligne et répond | 🔴 |
| **DEFI-05** | `GET /api/challenge/<id>` | Lit la ligne, renvoie `{status, tries_count, duration_seconds, steps}` — `steps` = nombre de coups, **pas la trajectoire elle-même** (payload de polling borné ; le détail passe par le SSE). 404 à message générique pour un id inconnu ou expiré (même message, pas d'oracle) | 🟠 |
| **DEFI-06** | `GET /api/challenge/<id>/stream` (SSE) | Réutilise `_send_sse` (`src/api/server.py:120-144`). Producteur : boucle 0,5 s qui relit le défi en base et émet en JSON les coups dont `step > dernier envoyé` ; émet un dernier event `done` (statut terminal + statistiques) puis ferme. Durée maximale du flux : 15 min, puis fermeture propre (le front se reconnecte si besoin). Le SSE ne transmet **jamais** `secret_word` avant le statut terminal (`SEC-26`) | 🟠 |
| **DEFI-07** | Quota mémoire anti-rafale | Un `RateLimiter` dédié (`src/api/ratelimit.py`, même style que `_login_limiter`, `src/api/routes/admin.py:47`) : 6 créneaux, refill 10/min par IP anonymisée — protège la route et la base avant même la lecture SQL ; 429 + `retry_after` (bypasse si IP dans la whitelist) | 🟠 |
| **DEFI-08** | Validation du mot | `word = unicodedata.normalize("NFC", mot.strip().lower())` ; regex `^[a-zà-ÿ][a-zà-ÿ-]{2,23}$` ; puis `store.normalize()` (`src/engine/vocab.py:327`) et **rejet si le mot n'est pas dans le lexique du site** (`is_valid_french`, `src/engine/vocab.py:337`) — le web peut faire ce contrôle sans calcul lourd : il charge déjà `VocabStore` pour les modes de jeu (`src/api/server.py:39`). Rejet `400` à message unique « mot non reconnu » (pas de distinction regex/lexique : pas d'oracle lexikaliste) | 🔴 |
| **DEFI-18** | Gestion admin de la whitelist | Routes sous préfixe d'administration protégé (`ADMIN_BASE_PATH`) : `GET <ADMIN_BASE_PATH>/whitelist` (liste des IP whitelistées avec description et date), `POST <ADMIN_BASE_PATH>/whitelist` (ajout d'une IP avec validation format IPv4/IPv6), `DELETE <ADMIN_BASE_PATH>/whitelist/<ip>` (retrait d'une IP). Intégration dans l'interface de la console d'administration cachée avec formulaire d'ajout et liste révocable en 1 clic | 🟠 |

**Vérification :** `curl -s -X POST …/api/challenge -d '{"word":"chaussette"}'` renvoie un `id` ;
`grep -n "solvers\|daemon" src/api/routes/challenge.py` ne trouve **aucune** occurrence ;
`curl -s -X POST …/api/challenge -d '{"word":"<script>"}'` renvoie `400`.

---

## 4. Worker — pick-up et résolution dans le démon

Le démon (`src/services/daemon.py`) dort déjà en boucle de 1 s jusqu'à minuit et consomme un
fichier de commande (`check_and_consume_command`, `src/services/daemon.py:42-54`). Le pick-up des
défis s'insère **dans cette même boucle**, sans nouveau processus.

| ID | Action | Spécification | Sévérité |
|---|---|---|---|
| **DEFI-09** | Pick-up | Toutes les `CHALLENGE_POLL_SECONDS` (défaut 3 s) dans la boucle de veille : `requeue_stale_running()` puis `claim_next_challenge()`. Claim atomique → pas de double exécution même si un second worker tourne | 🟠 |
| **DEFI-10** | Résolution | Construire les mêmes `args` légers que `_SolveArgs` (`src/api/routes/admin.py:271-287`, déjà écrit pour ce besoin), avec `secret = mot_du_joueur` ; instancier `Solver(args, store, game=MockClient(store, secret))` — le `VocabStore` du worker est déjà chargé et ChromaDB déjà indexé ; appeler `solver.run()`. Le `MockClient` lève `ValueError` si le mot a disparu du store entre-temps → statut `error`, message générique | 🔴 |
| **DEFI-11** | Trajectoire incrémentale | Le worker publie `solver.trajectory` en base **tous les K coups** (défaut 3) et au moins toutes les 2 s, via `append_trajectory()`, en rafraîchissant `heartbeat_at` et `tries_count`. C'est ce que le SSE relit : le direct vient du worker, jamais du web | 🟠 |
| **DEFI-12** | Bornes d'exécution | `max_tries = min(CHALLENGE_MAX_TRIES, 100)` par défaut (variable d'env, jamais prise du client) ; plafond de durée par défi (`CHALLENGE_TIMEOUT`, 900 s) vérifié à chaque publication incrémentale ; à la sortie : `finish_challenge(id, solved|lost, tries, durée)`. Le bot peut **perdre** (statut `lost`) : c'est une issue légitime et affichée | 🟠 |
| **DEFI-13** | Cohabitation avec la nuit | La résolution nocturne de minuit reste **prioritaire** : le pick-up est suspendu tant que `run_daily_solver` tourne ; un défi en cours s'achève (borné par `CHALLENGE_TIMEOUT`) avant que la nuit ne démarre au prochain tour de boucle. Le heartbeat Docker du worker continue d'être rafraîchi par le thread dédié (déjà en place, `src/services/daemon.py:67-70`) | 🟡 |

**Vérification :** `POST /api/challenge` pendant que le démon dort → la ligne passe `queued` →
`running` → `solved` en < 5 min (`SELECT status, tries_count FROM bot_challenges ORDER BY created_at DESC LIMIT 1`) ;
les logs `docker logs cemantix_worker` montrent les coups sans que `cemantix_web` calcule quoi que ce soit.

---


---


## 5. Frontend — même modèle d'affichage, direct compris

Le site est un ensemble de pages statiques servies par Caddy ; chaque mode a sa page et son
module JS en ES modules. Le défi suit exactement ce gabarit.

| ID | Action | Spécification | Sévérité |
|---|---|---|---|
| **DEFI-14** | Page `volumes/web/defi/index.html` | Même gabarit que `play/index.html` : en-tête, `nav-tabs` (nouvel onglet « ⚔️ Défier le bot », ajouté sur les 5 pages existantes, `volumes/web/index.html:226-249`), champ mot + bouton, zone de jeu. SEO : `<title>`, meta description, canonical, Open Graph conformes aux exigences de `tools/check_seo.py` (page publique indexable) | 🟡 |
| **DEFI-15** | Module `volumes/web/js/defi.js` | `POST /api/challenge` → ouvre le SSE `EventSource("/api/challenge/<id>/stream")` ; **repli polling** `GET /api/challenge/<id>` toutes les 2 s si l'`EventSource` tombe (3 tentatives max, puis message + bouton « reprendre le suivi »). Affiche la file : position approximative, quota restant (renvoyé par l'API), chrono. Toute valeur affichée passe par `escapeHtml()` (`volumes/web/js/utils.js:16`) — règle déjà imposée projet | 🔴 |
| **DEFI-16** | Rendu des coups | Réutilise les helpers de `volumes/web/js/render.js` et le modal de trajectoire (`volumes/web/js/trajectory.js`) : chaque coup reçu en SSE est ajouté au tableau (mot, température °C, ‰, icône météo, badge RAG/LLM) avec le **même rendu** que la trajectoire du mot du jour. Écran final : gagné/perdu, coups, durée, bouton « Voir la trajectoire complète » (recharge la trajectoire finale via le SSE fermé ou `GET` détaillé au statut terminal) | 🟡 |
| **DEFI-17** | CSS & accessibilité | Styles dans `css/play.css`/`game.css` existants ou petit ajout dans un bundle dédié `css/dist/defi.css` si nécessaire (même chaîne de build que les autres bundles) ; labels ARIA sur le champ et la zone live (`aria-live="polite"`), contrastes conformes à l'existant | 🟢 |

**Vérification :** `python tools/check_seo.py` et `python tools/check_docs.py` sortent verts ;
navigation complète au clavier ; un mot refusé affiche l'erreur sans jamais injecter de HTML
(test : mot `<img src=x>` → message textuel « mot non reconnu »).

---

## 6. Sécurité — exigences transverses, à vérifier une par une

Aucune de ces lignes n'est optionnelle : la fonctionnalité est publique, sans compte, et fait
tourner du calcul sur demande d'anonymes.

| ID | Exigence | Spécification | Sévérité |
|---|---|---|---|
| **SEC-20** | Quota 10/h **persisté** & Whitelist IP | `SELECT COUNT(*) FROM bot_challenges WHERE ip_hash = %s AND created_at > now() - interval '1 hour'` (paramétré). Compteur insensible aux redémarrages de `cemantix_web` et au rechargement mémoire. Dépassement → `429` + `retry_after` + `quota_restant` dans toutes les réponses valides. **Whitelist administrable :** toute IP présente dans `bot_challenge_whitelist` (ex. `88.175.123.252` insérée par défaut/seed initial) est totalement exemptée de limite horaire et de limite mémoire. | 🔴 |
| **SEC-21** | IP hachée salée | `ip_hash = HMAC-SHA256(sel, ip_anonymisée_/24)` en hexadécimal ; sel = secret d'exploitation (dérivation à la `_token_secret`, `src/api/routes/admin.py:64-66`, jamais le mot de passe admin, jamais versionné). L'IP brute n'est **jamais** écrite dans `bot_challenges` — cohérent avec RGPD-03 déjà appliqué (`src/api/server.py:81-92`) | 🔴 |
| **SEC-22** | Identifiant non devinable | `id = secrets.token_hex(16)` (128 bits). Aucun endpoint ne liste les défis (`GET /api/challenge` sans id → 404) ; on ne peut lire qu'un défi dont on connaît l'id | 🟠 |
| **SEC-23** | Plafond de flux SSE | Compteur global thread-safe de flux ouverts ; au-delà de `SSE_MAX_STREAMS` (défaut 16) → `503` + `Retry-After: 5` (le front bascule sur le polling). Durée max par flux : 15 min. Les flux SSE comptent dans le quota de threads `API_MAX_WORKERS` existant sans pouvoir l'aggraver | 🟠 |
| **SEC-24** | File bornée, coût borné | Si `count_queued() >= CHALLENGE_MAX_QUEUE` (défaut 20) → `429` « le bot est déjà occupé ». `max_tries` forcé côté serveur (le client ne l'envoie pas). Un mot du lexique garantit un coût de scoring borné (150 000 vecteurs, une seule similarité cosinus par coup) | 🔴 |
| **SEC-25** | Anti-XSS en trois couches | (1) regex + lexique au POST (`DEFI-08`) ; (2) écriture en paramètre lié uniquement ; (3) `escapeHtml()` à chaque rendu front. Le mot est ensuite relit depuis la base vers le HTML : la couche 3 protège même si 1 et 2 régressent | 🔴 |
| **SEC-26** | Anti-spoiler & cache | Toutes les réponses `/api/challenge*` portent `Cache-Control: no-store` (déjà dans `SECURITY_HEADERS`, `src/api/server.py:48-54`). `secret_word` n'apparaît dans **aucune** réponse tant que le statut n'est pas terminal ; au terminal, il n'est renvoyé que si `status = solved` (le bot a trouvé : le mot est de toute façon dans la trajectoire) — un défi `lost` ne révèle rien de plus que les scores | 🟠 |
| **SEC-27** | Purge & RGPD | `purge_older_than(30)` appelée par le démon au réveil de minuit : les défis (mot + trajectoire + hash) disparaissent après 30 jours. Aucune donnée dans `data.json` / exports web statiques (le défi n'y entre pas) | 🟠 |
| **SEC-28** | Surface d'attaque du worker | Le worker ne lit **que** la table `bot_challenges` (aucun ordre arbitraire depuis l'API : pas de reprise du canal `daemon_command.json` pour cette fonction, qui reste réservé à l'admin). Les entrées publiques ne deviennent jamais des arguments de commande, des chemins de fichier ni des fragments SQL | 🟠 |

**Vérification :** tests automatisés dédiés (`QUAL-20`) + revue : `grep -n "f\"SELECT\|f\"INSERT\|% (" src/db/challenges.py` ne montre que des requêtes paramétrées ; le quota survit à
`docker compose restart cemantix_web` (11e défi dans l'heure → `429`).

---


## 7. Qualité — tests, documentation, recette

| ID | Action | Spécification | Sévérité |
|---|---|---|---|
| **QUAL-20** | Tests automatisés | Nouveaux tests dans `tests/` (même socle que les 81 tests existants) : validation du mot (accepte « chaussette », refuse `<script>`, `A`, mot inconnu, 25 caractères) ; quota (10 OK puis 429, rechargement API inclus en simulant la base) ; exemption whitelist (IP whitelistée passe sans quota ni blocage) ; administration whitelist (ajout, suppression, listage) ; claim atomique (deux `claim_next_challenge()` concurrents ne rendent pas deux fois la même ligne) ; résolution bout-en-bout en `--mock` sur un mot connu → statut `solved` ; `requeue_stale_running` sur une tâche orpheline ; purge | 🟠 |
| **QUAL-21** | Documentation | `volumes/web/openapi.json` : les 3 routes ; `README.md` : section « Défier le bot » + architecture 3-tiers mise à jour ; `CHANGELOG.md` : entrée d'évolution ; variables d'env documentées (`CHALLENGE_MAX_TRIES`, `CHALLENGE_TIMEOUT`, `CHALLENGE_MAX_QUEUE`, `SSE_MAX_STREAMS`, `CHALLENGE_RETENTION_DAYS`) dans `.env.example` | 🟡 |
| **QUAL-22** | Recette en conditions réelles | `docker compose up` complet : défi gagné affiché en direct (< 1 s de latence par coup), 11e défi → 429, page consultable au clavier, `docker stats` prouve 0 % CPU sur `cemantix_web` pendant une résolution, résolution de minuit non dérangée (défi lancé à 23h59) | 🟠 |

---

## 8. Plan d'exécution

Ordre d'implémentation sur `feat/bot_defy`, chaque phase qualifiée avant la suivante :

| Phase | Actions | Critère de sortie |
|---|---|---|
| 1 | DEFI-01, DEFI-02, DEFI-03 | Tests DAO verts (PostgreSQL + repli SQLite) |
| 2 | DEFI-04..08, DEFI-18, SEC-20..24 | `POST` → `queued` en base ; quotas, whitelist et validations testés ; **aucun calcul dans le web** (grep) |
| 3 | DEFI-09..13 | Défi `queued → running → solved` en environ < 5 min, trajectoire incrémentale visible en base |
| 4 | DEFI-14..17 | Direct affiché dans la page, repli polling opérationnel, `check_seo.py` vert |
| 5 | SEC-25..28 + revue | Toutes les exigences §6 cochées avec preuve |
| 6 | QUAL-20..22 | Suite de tests verte, doc à jour, recette docker complète validée |

---

## 9. Risques & rollbacks

| Risque | Probabilité | Parade | Rollback |
|---|---|---|---|
| Un défi monopolise le worker juste avant minuit | faible | `CHALLENGE_TIMEOUT` (900 s) + priorité nocturne (`DEFI-13`) | Variable d'env `CHALLENGE_ENABLED=0` : l'API répond `503` aimable, le démon n'enqueue plus rien — la page affiche « bot indisponible ». Aucun déploiement nécessaire |
| Le worker meurt en pleine résolution | faible | `heartbeat_at` + `requeue_stale_running` (`DEFI-03`) | La tâche repart en `queued` ; après un second orphelinat : `error` |
| ChromaDB absent sur le worker (index en cours de reconstruction) | faible | Le pick-up teste `store.col` avant claim ; sinon la file attend | Les défis restent `queued`, rien n'est perdu |
| Le SSE sature les threads du web | très faible | `SSE_MAX_STREAMS` + durée max (`SEC-23`) | Le front bascule sur le polling, fonctionnel sans SSE |
| Confusion « le bot triche-t-il ? » (perception) | moyenne | La page explique le fonctionnement (score cosinus local, pas le site officiel) ; la trajectoire est publique et rejouable | — (documentaire) |

Fonctionnalité **additive** : aucune table existante n'est modifiée, aucune route existante n'est
touchée. Le rollback complet = déployer l'image précédente + `DROP TABLE bot_challenges`.
