# 📊 Avancement — Wall of Fame, Exploitation des KPIs & Visualisation Interactive des Défis

> **Évolution :** [2026-11 · Wall of Fame & Replay des Défis Visiteurs](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m9-wall-of-fame-ui` (base `origin/main`)  
> **Dernière mise à jour :** 05/11/2026  

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`WOF-01` à `WOF-06`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **6** | 2 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **6** | **2** |

Répartition par criticité : 🔴 `WOF-01` (API KPIs avec cache TTL), `WOF-02` (API Replay cheminement) · 🟠 `WOF-03` (Composants Wall of Fame), `WOF-04` (Cartes KPIs dynamiques), `WOF-05` (Bandeau joueur & quota) · 🟡 `WOF-06` (Branchement modale de trajectoire).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **WOF-01** | 🔴 | Endpoint API /api/challenge/kpis avec Cache TTL 15s | `✅ Fait` | Route `handle_kpis_get` + cache TTL 15 s (`_global_kpis_cached`), bloc `player` recalculé par visiteur. Preuve : `test_kpis_cache_avoids_second_aggregation` (1 agrégation pour 2 appels), `test_kpis_cache_expires_after_ttl`, `test_kpis_db_failure_returns_503` — 368 tests OK sous Docker 3.12. |
| **WOF-02** | 🔴 | Endpoint API /api/challenge/<id>/guesses (Replay du Chemin) | `✅ Fait` | Route `handle_guesses_get` (`dao.get_challenge_guesses`, id validé, 404 générique). Preuve : `test_guesses_ordered_and_formatted` (tri 1,2,3, 7 champs) et `test_guesses_unknown_or_malformed_id_is_404`. |
| **WOF-03** | 🟠 | Composants HTML & Design du Wall of Fame (/defi/) | `✅ Fait` | Section `#defi-wall-of-fame` (sémantique `section`/`h2`/`ul`), seuls les défis `lost` (`test_wall_of_fame_only_lost_challenges`). Preuve : `check_seo.py` OK, `build_css_bundles.py --check` OK. |
| **WOF-04** | 🟠 | Cartes de Métriques KPIs Communautaires | `✅ Fait` | Grille `#defi-kpi-grid` de 4 cartes à compteurs animés (respect de `prefers-reduced-motion`). Preuve : `test_kpis_global_values` (2/3 victoires IA = 66,7 %, moyenne 30,0, 1 mot invaincu). |
| **WOF-05** | 🟠 | Bandeau Statut Joueur & Quota Restant | `✅ Fait` | Bandeau `#defi-player-banner` rafraîchi à l'acceptation et au dénouement de chaque défi. Preuve : `test_player_block_and_quota` (1/3, 33,3 %, quota 10-3 = 7), `test_player_block_is_not_cached_between_visitors`. |
| **WOF-06** | 🟡 | Replay Interactif du Cheminement via Modale | `✅ Fait` | Bouton « 👁️ Revoir le chemin » → `GET /api/challenge/<id>/guesses` → `openTrajectoryModal` (`onWallClick` dans `defi.js`). Preuve : contrat de données couvert par les tests WOF-02 ; rendu navigateur non automatisé (non testé visuellement). |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 04/11/2026 | — | Ouverture de l'évolution M9 et rédaction du plan de conception. |
| 05/11/2026 | WOF-01→06 | Implémentation M9 : 15 tests 	ests/test_challenge_ui_api.py + 	est_challenge_kpis.py verts ; suite complète 368 tests OK (Docker Python 3.12), check_docs, check_seo, uild_css_bundles --check OK. |
