# 📊 Avancement — Indexation Instantanée & Balisages Schema.org Avancés

> **Évolution :** [2026-11 · Indexation Instantanée & Balisages Schema.org Avancés](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m11-instant-indexing-rich-snippets` (base `origin/main`)  
> **Dernière mise à jour :** 05/11/2026  

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`IND-01` à `IND-05`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **5** | 2 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **5** | **2** |

Répartition par criticité : 🔴 `IND-01` (Google Indexing API), `IND-02` (Protocole IndexNow) · 🟠 `IND-03` (Balisages HowTo & WebApplication), `IND-04` (CLI & Orchestration) · 🟡 `IND-05` (Tests & Non-Régression).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **IND-01** | 🔴 | Client Google Indexing API (`src/services/seo_google.py`) | `✅ Fait` | Implémentation de `notify_google_indexing` et `notify_daily_urls_to_google` poussant les URLs à `https://indexing.googleapis.com/v3/urlNotifications:publish`. Preuve : `test_notify_success` et `test_notify_daily_urls` OK. |
| **IND-02** | 🔴 | Protocole Multi-Moteurs IndexNow (`src/services/seo_indexnow.py`) | `✅ Fait` | Implémentation du module IndexNow avec création automatique et exposition de la clé dans `volumes/web/<key>.txt`. Preuve : `test_get_indexnow_key_generation_and_file_creation` et `test_submit_indexnow_urls_success` OK (HTTP 200/202 validé). |
| **IND-03** | 🟠 | Balisages Schema.org Avancés : HowTo & WebApplication | `✅ Fait` | Schéma `HowTo` en 5 étapes calibré sur `/methode/` et `WebApplication` sur les pages de jeu (`/`, `/play/`, `/defi/`, `/battle/`). Preuve : `test_build_methode_page_contains_howto_schema` OK. |
| **IND-04** | 🟠 | Déclenchement Automatique & Option CLI (`cemantix_rag.py`) | `✅ Fait` | Intégration dans `publish_seo_pages()` et ajout du flag `--notify-indexing`. Preuve : exécution Docker `cemantix --notify-indexing` validée. |
| **IND-05** | 🟡 | Suite de Tests & Non-Régression | `✅ Fait` | 7 tests dans `tests/test_instant_indexing.py` + 386 tests globaux OK sous Docker. Preuve : `check_docs.py`, `check_seo.py`, `build_css_bundles.py --check` tous verts. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 05/11/2026 | — | Ouverture de l'évolution M11 et rédaction de la référence de conception. |
| 05/11/2026 | IND-01→05 | Implémentation de Google Indexing API, IndexNow, intégration CLI et tests unitaires (386 tests OK sous Docker). |
