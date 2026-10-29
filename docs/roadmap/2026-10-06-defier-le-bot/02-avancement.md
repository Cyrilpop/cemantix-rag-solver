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
| ✅ Fait | **0** | 0 |
| 🔨 En cours | **0** | 0 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **30** | 8 |
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

---

## 5. Suivi des actions

### 5.1 Données (plan §2)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-01** | Table `bot_challenges` & `bot_challenge_whitelist` (init.sql + PG_SCHEMA + SQLite) | ⬜ À faire | — |
| **DEFI-02** | DAO `src/db/challenges.py` (claim atomique, quota, purge, gestion whitelist) | ⬜ À faire | — |
| **DEFI-03** | Cohérence des statuts + `requeue_stale_running` | ⬜ À faire | — |

### 5.2 API web (plan §3)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-04** | `POST /api/challenge` (enqueue seul, zéro calcul) | ⬜ À faire | — |
| **DEFI-05** | `GET /api/challenge/<id>` (état borné) | ⬜ À faire | — |
| **DEFI-06** | `GET /api/challenge/<id>/stream` (SSE via `_send_sse`) | ⬜ À faire | — |
| **DEFI-07** | Rate-limiter mémoire anti-rafale | ⬜ À faire | — |
| **DEFI-08** | Validation du mot (regex + lexique, message unique) | ⬜ À faire | — |
| **DEFI-18** | Gestion admin de la whitelist IP (API REST + UI console cachée) | ⬜ À faire | — |

### 5.3 Worker (plan §4)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-09** | Pick-up dans la boucle de veille du démon | ⬜ À faire | — |
| **DEFI-10** | Résolution `Solver` + `MockClient(secret=…)` | ⬜ À faire | — |
| **DEFI-11** | Trajectoire incrémentale en base (toutes les 2 s) | ⬜ À faire | — |
| **DEFI-12** | Bornes `max_tries` / durée / statut `lost` | ⬜ À faire | — |
| **DEFI-13** | Priorité à la résolution nocturne de minuit | ⬜ À faire | — |

### 5.4 Frontend (plan §5)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **DEFI-14** | Page `defi/index.html` + onglet de navigation + SEO | ⬜ À faire | — |
| **DEFI-15** | `js/defi.js` : SSE + repli polling + quota affiché | ⬜ À faire | — |
| **DEFI-16** | Rendu des coups via `render.js` / modal trajectoire | ⬜ À faire | — |
| **DEFI-17** | CSS + accessibilité (`aria-live`, contrastes) | ⬜ À faire | — |

### 5.5 Sécurité (plan §6)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **SEC-20** | Quota 10/h persisté en base (429 + retry_after) & whitelist IP administrable sans limite | ⬜ À faire | — |
| **SEC-21** | IP hachée salée (HMAC), aucune IP brute en base | ⬜ À faire | — |
| **SEC-22** | Identifiant 128 bits, aucune liste publique | ⬜ À faire | — |
| **SEC-23** | Plafond `SSE_MAX_STREAMS` + durée max de flux | ⬜ À faire | — |
| **SEC-24** | File bornée, `max_tries` serveur, coût par coup borné | ⬜ À faire | — |
| **SEC-25** | Anti-XSS trois couches (regex, paramétré, escapeHtml) | ⬜ À faire | — |
| **SEC-26** | `no-store` + mot jamais révélé avant le statut terminal | ⬜ À faire | — |
| **SEC-27** | Purge 30 jours au réveil du démon, rien dans `data.json` | ⬜ À faire | — |
| **SEC-28** | Worker limité à la table, jamais d'ordre arbitraire | ⬜ À faire | — |

### 5.6 Qualité (plan §7)

| ID | Action | Statut | Preuve / note |
|---|---|---|---|
| **QUAL-20** | Tests (validation, quota, claim, bout-en-bout mock, purge) | ⬜ À faire | — |
| **QUAL-21** | `openapi.json`, README, CHANGELOG, `.env.example` | ⬜ À faire | — |
| **QUAL-22** | Recette docker complète (direct, quota, nuit, CPU web = 0) | ⬜ À faire | — |

---

## 6. Prochaines actions

1. **Phase 1** : `DEFI-01` → `DEFI-02` → `DEFI-03` (table + DAO + tests SQLite).
2. **Phase 2** : `DEFI-08` (validation) avant `DEFI-04` (création) — la validation conditionne
   tout le reste de la chaîne de confiance.
3. Ne pas démarrer la phase 4 (front) avant que la phase 3 publie une trajectoire incrémentale
   visible en base.
