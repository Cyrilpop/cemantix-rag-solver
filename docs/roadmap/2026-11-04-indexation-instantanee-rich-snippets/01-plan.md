# ⚡ Plan — Indexation Instantanée (Google Indexing API, IndexNow) & Balisages Schema.org Avancés

> **Évolution :** [2026-11 · Indexation Instantanée & Balisages Schema.org Avancés](../README.md) · document 1/2  
> **Statut du document :** référence de conception, versionnée.  
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.  
> **Jalon technique associé :** [`docs/milestones/M11_INSTANT_INDEXING_RICH_SNIPPETS.md`](../../milestones/M11_INSTANT_INDEXING_RICH_SNIPPETS.md)  
> **Socle technique prérequis :** [`docs/milestones/M10_GOOGLE_SEARCH_CONSOLE_SITEMAP.md`](../../milestones/M10_GOOGLE_SEARCH_CONSOLE_SITEMAP.md)  
> **Branche :** `feature/m11-instant-indexing-rich-snippets` (base `origin/main`)  
> **Date d'ouverture :** 05/11/2026  

**Convention de lecture :** chaque action porte un identifiant permanent (`IND-01` à `IND-05`) utilisé comme **clé de suivi** dans `02-avancement.md`.

---

## 0. Méthodologie & périmètre

Cette évolution déploie l'accélération maximale d'indexation et d'affichage dans les moteurs de recherche :

1. Notification push des URLs chaudes quotidiennes via Google Indexing API.
2. Notification multi-moteurs (Bing, Yahoo, DuckDuckGo) via le protocole IndexNow.
3. Données structurées Schema.org avancées (`HowTo` sur `/methode/` et `WebApplication` sur `/` et `/play/`).
4. Intégration CLI `--notify-indexing` et orchestration automatique lors de `publish_seo_pages()`.
5. Suite de tests unitaires sous Docker et contrôle des 4 outils de validation.

---

## 1. Findings & Actions Spécifiées

### IND-01 (🔴) — Client Google Indexing API (`src/services/seo_google.py`)
- **Problème :** La soumission du sitemap ne garantit pas un crawl immédiat par Googlebot.
- **Correctif :** Implémentation de `notify_google_indexing(url, notification_type)` utilisant l'API Google Indexing v3 pour pousser les URLs fraîches (`/`, `/mot-du-jour/`, `/puzzles/AAAA-MM-JJ/`).
- **Vérification :** Test unitaire avec mock HTTP validant le payload JSON et la gestion des réponses Google.

### IND-02 (🔴) — Protocole Multi-Moteurs IndexNow (`src/services/seo_indexnow.py`)
- **Problème :** Les moteurs alternatifs (Bing, Yahoo, DuckDuckGo) ne reçoivent pas les signaux d'indexation push.
- **Correctif :** Implémentation de `src/services/seo_indexnow.py` avec gestion de clé persistante (dans `volumes/web/<key>.txt`) et soumission à l'API `https://api.indexnow.org/indexnow`.
- **Vérification :** Test unitaire confirmant la création du fichier clé et la requête HTTP vers IndexNow.

### IND-03 (🟠) — Balisages Schema.org Avancés : `HowTo` & `WebApplication`
- **Problème :** La page `/methode/` n'utilise que `Article`/`FAQPage` et n'exploite pas le format `HowTo` pour les rich snippets à étapes dans la SERP Google. L'accueil et `/play/` n'ont pas de balisage `WebApplication`.
- **Correctif :** Enrichissement du JSON-LD dans `seo_hubs.py` et `seo_templates.py` avec le schéma `HowTo` pour `/methode/` et `WebApplication` pour `/` et `/play/`.
- **Vérification :** Validation du schéma JSON-LD par `tools/check_seo.py` et tests unitaires.

### IND-04 (🟠) — Déclenchement Automatique & Option CLI (`cemantix_rag.py`)
- **Problème :** L'indexation instantanée doit être exécutée automatiquement à minuit tout en restant déclenchable manuellement.
- **Correctif :** Branchement dans `publish_seo_pages()` et ajout du flag `--notify-indexing` dans `cemantix_rag.py`.
- **Vérification :** Exécution sous conteneur Docker de `cemantix --notify-indexing`.

### IND-05 (🟡) — Suite de Tests & Non-Régression
- **Problème :** Risque de casser la suite de tests ou les scripts d'audit.
- **Correctif :** Création de `tests/test_instant_indexing.py` et exécution des 4 outils de validation (`check_docs.py`, `check_seo.py`, `build_css_bundles.py --check`, tests unitaires).
- **Vérification :** 100 % de succès sur l'ensemble de la suite.

### IND-06 (🔴) — Protection de Quota Google Indexing & Flag en Base (`google_indexed_at`)
- **Problème :** À chaque redémarrage de conteneur, régénération web ou test, les URLs chaudes sont renvoyées à Google Indexing API, risquant d'épuiser prématurément le quota journalier (200 URLs/jour).
- **Correctif :** Ajout d'une colonne `google_indexed_at` dans `database/init.sql` et dans la table `daily_puzzles` (`connection.py`, `daily.py`). Si le puzzle du jour est déjà indexé, la notification Google est sautée avec log explicite, sauf si le paramètre `force=True` (ou flag `--force`) est spécifié.
- **Vérification :** Tests unitaires validant l'évitement d'appel réseau quand le flag est présent et le bypass quand `force=True`.
