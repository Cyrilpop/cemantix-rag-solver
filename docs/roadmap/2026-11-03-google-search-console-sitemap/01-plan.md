# 🌐 Plan — Soumission Automatique du Sitemap à Google Search Console

> **Évolution :** [2026-11 · Soumission Automatique du Sitemap à Google Search Console](../README.md) · document 1/2  
> **Statut du document :** référence de conception, versionnée.  
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.  
> **Jalon technique associé :** [`docs/milestones/M10_GOOGLE_SEARCH_CONSOLE_SITEMAP.md`](../../milestones/M10_GOOGLE_SEARCH_CONSOLE_SITEMAP.md)  
> **Branche :** `feature/m10-google-search-console-sitemap` (base `origin/main`)  
> **Date d'ouverture :** 05/11/2026  

**Convention de lecture :** chaque action porte un identifiant permanent (`GSC-01` à `GSC-05`) utilisé comme **clé de suivi** dans `02-avancement.md`.

---

## 0. Méthodologie & périmètre

L'évolution met en place l'interaction sécurisée et asynchrone avec l'API Google Search Console pour soumettre le fichier `volumes/web/sitemap.xml` dès sa génération :

1. Lecture sécurisée des variables d'environnement (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`).
2. Client HTTP résilient pour l'obtention de jetons OAuth 2.0 et la soumission du sitemap.
3. Déclenchement automatique non-bloquant dans [`src/services/seo.py`](../../../src/services/seo.py) lors de la publication quotidienne.
4. Outil d'assistance CLI pour l'authentification initiale et le test manuel direct.
5. Suite de tests sous Docker Python 3.12 garantissant 100 % de couverture des cas limites et défaillances réseau.

---

## 1. Findings & Actions Spécifiées

### GSC-01 (🔴) — Module Client API Google Search Console (`src/services/seo_google.py`)
- **Problème :** Aucun client n'existe pour interagir avec les endpoints OAuth2 de Google et l'API Search Console `webmasters.sitemaps.submit`. L'ancien protocole de ping (`/ping?sitemap=...`) a été désactivé par Google début 2024 (HTTP 404).
- **Correctif :** Implémentation de `src/services/seo_google.py` avec extraction robuste des credentials (tolérant `GOOCLE_CLIENT_SECRET`), rafraîchissement automatique de token d'accès OAuth 2.0, et soumission REST HTTP `PUT`.
- **Vérification :** Test unitaire simulant les échanges OAuth2 et les réponses de l'API Search Console (succès 204, erreurs HTTP 401/403/500).

### GSC-02 (🔴) — Déclenchement Automatique dans le Cycle de Vie SEO (`src/services/seo.py`)
- **Problème :** Après génération de `sitemap.xml` par `publish_seo_pages()`, aucune notification n'est transmise aux moteurs de recherche.
- **Correctif :** Ajout de l'appel à `submit_sitemap_to_google()` au sein de `publish_seo_pages()` dans `src/services/seo.py`. L'opération doit être protégée par un `try/except` global pour garantir qu'un échec réseau Google ne bloque jamais la publication locale.
- **Vérification :** Test unitaire confirmant la notification lors de `publish_seo_pages()` et la continuité de service en cas d'exception.

### GSC-03 (🟠) — Assistant CLI d'Autorisation et Déclenchement Manuel (`cemantix_rag.py`)
- **Problème :** L'authentification OAuth 2.0 avec consentement initial nécessite de récupérer le premier code d'autorisation pour obtenir le `refresh_token`.
- **Correctif :** Intégration des arguments `--google-auth` et `--submit-sitemap` dans le CLI argparse de `cemantix_rag.py`.
- **Vérification :** Exécution sous conteneur de `--submit-sitemap` et `--google-auth --help`.

### GSC-04 (🟠) — Suite de Tests Unitaires Dédiée (`tests/test_seo_google.py`)
- **Problème :** Risque de régression lors du renouvellement des jetons ou de modifications de configuration.
- **Correctif :** Création d'une suite de tests complète mockant `requests` pour valider : parsing `.env`, génération d'URL d'auth, échange de code, renouvellement du refresh token, soumission sitemap, gestion des timeouts et absence de credentials.
- **Vérification :** Exécution réussie de la suite complète sous Docker Python 3.12.

### GSC-05 (🟡) — Conformité Docker Compose & Cohérence Documentaire
- **Problème :** Les conteneurs Docker doivent pouvoir accéder aux variables d'environnement Google définies dans `.env`.
- **Correctif :** Documentation des variables requises dans `.env.example`, documentation opérationnelle dans `README.md` et validation via `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check`.
- **Vérification :** Scripts de contrôle sans aucune erreur ni lien cassé.

