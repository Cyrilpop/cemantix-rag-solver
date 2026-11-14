# 📊 Avancement — Jalon M16 : Espace « Mon compte », Gestion Avancée du Profil, Sécurité, Mots de Récupération & Statistiques de Jeu

> **Évolution :** [2026-11 · Espace « Mon compte », Sécurité & Statistiques](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m16-espace-mon-compte` (base `main`)  
> **Dernière mise à jour :** 14/11/2026  

---

## 0. Règles de Tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`ACC-01` à `ACC-08`). Un ID n'est jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte sous Docker.** Un commit ou une intention ne vaut pas preuve.
3. Statuts reconnus : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut est consigné chronologiquement dans le **Journal des actions** (§3) avec sa preuve mesurée.

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **8** | 4 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **8** | **4** |

Répartition par criticité : 🔴 `ACC-01` (Schéma relationnel idempotent & migrations SQL), `ACC-02` (DAO compte & mots aléatoires sécurisés), `ACC-03` (Routes API REST `/api/account/*`), `ACC-05` (Vue dédiée `/account/` & menu vertical) · 🟠 `ACC-04` (Maintien du moteur global de modales), `ACC-06` (Routage dynamique Header & reverse-proxies) · 🟡 `ACC-07` (Suite de tests unitaires sous Docker), `ACC-08` (Validation globale, bundle CSS & audit doc).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve attendue |
|---|---|---|---|---|
| **ACC-01** | 🔴 | Schéma Relationnel Idempotent PostgreSQL & SQLite (`database/init.sql`, `src/db/connection.py`) | `✅ Fait` | Table `player_recovery_words` créée avec contrainte d'unicité `(player_id, word_hash)` et index ; colonnes `password_updated_at` et `last_login_at` ajoutées conditionnellement sur `players`. DDL miroir SQLite dans `connection.py`. Preuve : `TestAccountDatabaseSchema` validé sous Docker (3/3 tests passés). |
| **ACC-02** | 🔴 | DAO & Métier Sécurité (`src/db/account.py`, `src/db/__init__.py`, `src/db/players.py`) | `✅ Fait` | Fonctions de gestion de compte, vérification/changement de mot de passe, tirage aléatoire de 4 mots de récupération système (`secrets.choice`), hachage sécurisé PBKDF2-HMAC-SHA256, purge atomique lors du renouvellement et agrégation des stats de jeu. Preuve : `TestAccountDAOSecurity` validé sous Docker (6/6 tests passés). |
| **ACC-03** | 🔴 | Endpoints API REST `/api/account/*` (`src/api/routes/account.py`, `src/api/server.py`) | `✅ Fait` | Routeur HTTP dédié avec gestion des routes `profile`, `password`, `recovery` (GET/POST), `stats` et `logout`. Extraction du token Bearer, validation stricte des formats et émission de `Cache-Control: no-store, private`. Preuve : `TestAccountAPIRoutes` validé sous Docker (6/6 tests passés). |
| **ACC-04** | 🟠 | Moteur Global de Modales (`volumes/web/css/modal.css`, `volumes/web/js/auth.js`) | `✅ Fait` | Sanctuarisation de `<dialog class="modal">` et préservation de la modale d'inscription rapide pour les visiteurs/invités et de la modale d'indices M15. Preuve : non-régression UI validée et bundle `modal.css` (10,903 o) vérifié avec `build_css_bundles.py --check`. |
| **ACC-05** | 🔴 | Vue Dédiée `/account/` (`volumes/web/account/index.html`, `account.js`, `account.css`) | `✅ Fait` | Interface complète avec menu vertical (Profil, Sécurité, Mots de récupération, Statistiques), gestion de l'affichage unique des mots de secours avec modale de confirmation/copie, et rendu des métriques de jeu. Preuve : bundle CSS généré (40,957 o), critique inline injecté, validation W3C/responsive. |
| **ACC-06** | 🟠 | Routage Dynamique Header Universel & Proxies (`layout_sync.py`, `header.js`, `Caddyfile`, `local/nginx/`) | `✅ Fait` | Aiguillage biface du badge « Mon compte » (redirection `/account/` si connecté ou modale rapide si invité) ; intégration `/account` dans `local/smoke-test.sh` (test) et dans le `Caddyfile` racine iso prod hors Git (`@pages`). Preuve : intégration `layout_sync.py` validée par `test_layout_sync.py` sous Docker. |
| **ACC-07** | 🟡 | Suite de Tests Automatisés sous Docker (`tests/test_account.py`) | `✅ Fait` | Couverture unitaire et d'intégration complète sous environnement Docker : cycle de vie du profil, hachage/sécurité des mots aléatoires, contrôleurs REST, scénarios d'erreurs et agrégation des métriques. Preuve : `test_account.py` (15/15 passés en 1.54s) et découverte complète (493 tests exécutés, 476 passés, 0 échec). |
| **ACC-08** | 🟡 | Validation Globale, Bundle CSS & Documentation (`tools/check_docs.py`, `tools/build_css_bundles.py`, `README.md`) | `✅ Fait` | Déclaration et compilation du bundle `account.css`, mise à jour de `docs/roadmap/README.md`, consignation dans `CHANGELOG.md` et validation outillée. Preuve : `tools/check_docs.py` (0 erreur, compteurs OK) et `tools/build_css_bundles.py --check` 100% verts sous Docker. |

---

## 3. Journal des actions

| Date | ID | Action & Preuve |
|---|---|---|
| 14/11/2026 | — | Cadrage initial et spécification technique du Jalon M16 à partir de `docs/milestones/M16_PAGE_MON_COMPTE.md`. Définition de la matrice des 8 findings `ACC-01` à `ACC-08`, prise en compte de la double infrastructure de livraison (Nginx local / test et Caddy prod racine hors Git) et initialisation des documents de roadmap (`01-plan.md` et `02-avancement.md`). |
| 14/11/2026 | ACC-01 | Ajout de la table `player_recovery_words` et des colonnes `password_updated_at` / `last_login_at` dans `database/init.sql` et `src/db/connection.py`. Preuve : `TestAccountDatabaseSchema` vert sous Docker (3 tests passés). |
| 14/11/2026 | ACC-02 | Création de `src/db/account.py` (DAO profil, changement de mot de passe, tirage aléatoire de 4 mots français cryptographiques, purge atomique, statistiques) et mise à jour de `src/db/players.py`. Preuve : `TestAccountDAOSecurity` vert sous Docker (6 tests passés). |
| 14/11/2026 | ACC-03 | Implémentation du routeur `src/api/routes/account.py` et intégration dans `src/api/server.py` (`do_GET`, `do_POST`). Preuve : `TestAccountAPIRoutes` vert sous Docker (6 tests passés). |
| 14/11/2026 | ACC-04 | Préservation sanctuarisée du moteur global de modales (`modal.css`, `auth.js`) pour l'onboarding invité et les indices M15. Preuve : bundle `modal.css` synchronisé et vérifié. |
| 14/11/2026 | ACC-05 | Conception de la vue dédiée `/account/` (`volumes/web/account/index.html`, `account.css`, `account.js`) avec navigation verticale à 4 sections, reveal box à tirage unique et KPIs. Preuve : bundle `account.css` compilé (40,957 o) et CSS critique inline injecté. |
| 14/11/2026 | ACC-06 | Routage dynamique du header universel (`volumes/web/js/header.js`), synchronisation déclarée dans `src/services/layout_sync.py`, directive `@pages` ajustée dans `Caddyfile` (racine iso prod hors Git) et smoke test `/account/:200`. Preuve : `test_layout_sync.py` vert sous Docker. |
| 14/11/2026 | ACC-07 | Rédaction de la suite complète `tests/test_account.py`. Preuve : `15 passés en 1.54s` sur `test_account.py`, et suite globale `493 tests exécutés, 476 passés, 0 échec` sous Docker. |
| 14/11/2026 | ACC-08 | Compilation des bundles CSS et validation outillée de la documentation. Preuve : `python tools/build_css_bundles.py --check` et `python tools/check_docs.py` 100% verts sous Docker. |

---

## 4. Environnement de vérification, limites & prochaines actions

- **Règle absolue d'environnement :** Toutes les exécutions de tests applicatifs, requêtes en base de données et scripts Python s'effectuent **exclusivement dans un conteneur Docker** via :
  ```bash
  docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests
  ```
  Aucune commande `pytest`, `python` ou `pip` ne doit être lancée sur la machine hôte.
- **Double Cible Serveur & Déploiement :**
  - **Local / Test :** Proxy web Nginx (`local/nginx/cemantix.local.conf`, `local/docker-compose.test.yml`, tests avec `local/smoke-test.sh`).
  - **Production :** Docker + Caddy. Le fichier de référence pour la production est le `Caddyfile` situé à la racine du projet (`c:\dev\docker\cemantix_solver\Caddyfile`). Il est **strictement iso production mais HORS GIT** (`.gitignore:85`). Lors de l'implémentation, `/account` et `/account/*` devront y être ajoutés dans le bloc `@pages` et rechargés à chaud via `docker exec <caddy> caddy reload --config /etc/caddy/Caddyfile`.
- **Limites assumées pour ce jalon :**
  - Les mots de récupération sont générés de façon purement aléatoire par le système (dictionnaire français) et hachés en base ; ils ne peuvent être ni personnalisés manuellement par l'utilisateur (pour éviter les faiblesses prévisibles), ni réaffichés ultérieurement par le serveur.
  - L'affichage des statistiques personnelles agrège les données de la table de jeu solo (`solo_player_games`) et des défis terminés ; les parties en cours non achevées sont exclues des métriques de victoires et de moyennes de coups.
- **Prochaines actions d'implémentation :**
  1. Créer la branche Git dédiée : `git checkout -b feature/m16-espace-mon-compte`.
  2. Implémenter les migrations SQL idempotentes (`ACC-01`) dans `database/init.sql` et `src/db/connection.py`.
  3. Développer le module métier et DAO `src/db/account.py` (`ACC-02`).
  4. Mettre en place les routes REST `/api/account/*` dans `src/api/routes/account.py` (`ACC-03`).
  5. Sanctuariser le moteur de modales et ajuster le header (`ACC-04`, `ACC-06`).
  6. Développer l'interface de la page `/account/` avec son menu vertical (`ACC-05`).
  7. Ajuster les configurations reverse-proxy : `local/nginx/cemantix.local.conf` (test) et `Caddyfile` racine iso prod hors Git (`ACC-06`).
  8. Rédiger et exécuter la suite de tests sous Docker (`ACC-07`).
  9. Compiler les bundles CSS et valider la documentation avec `tools/check_docs.py` et `local/smoke-test.sh` (`ACC-08`).
