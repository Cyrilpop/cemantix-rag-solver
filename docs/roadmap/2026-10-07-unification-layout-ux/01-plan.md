# 🎨 Plan — Unification du Layout, Navigation & Architecture Modulaire en 4 Briques

> **Évolution :** [2026-10 · Unification du layout & architecture modulaire](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ce fichier décrit **quoi faire et comment le vérifier**, sans état d'avancement.
> **Branche de travail visée :** `feature/ui-ux-improvements`
> **Base de référence :** `origin/main`
> **Date de conception :** 31/10/2026
> **Périmètre exclusif :** ergonomie et identité visuelle du header, uniformisation de la navigation par onglets (`nav-tabs`), intégration de la page des archives (`/puzzles/`), et industrialisation de l'architecture en 4 briques (Header, Menu, Contenu, Footer) avec synchronisation automatique en Python au démarrage du conteneur.

**Convention de lecture :** chaque finding porte un identifiant permanent (`UX-01` à `UX-05`) utilisé comme **clé de suivi** dans `02-avancement.md`.

---

## 0. Méthodologie & périmètre

Cette évolution standardise l'ergonomie visuelle et structurelle sur l'ensemble des pages web du solveur (Dashboard, Play Solo, Battle IA, Multijoueur, Défier le Bot, Archives SEO).

Elle résout le problème de duplication du header et de la navigation en instaurant un découpage modulaire en **4 briques** :
1. **Header** (fixe, marque, favicon transparente, toggle thème, statut démon).
2. **Menu / Nav-tabs** (navigation principale, 6 vues avec badges et hauteur uniforme 42px).
3. **Contenu** (spécifique et isolé pour chaque vue).
4. **Footer** (mentions, liens officiels et auteur).

| Zone | Fichiers sources | Pages cibles impactées |
|---|---|---|
| Favicon & Logos | `volumes/web/icons/favicon.png` | Toutes (`/`, `play/`, `battle/`, `multi/`, `defi/`, `puzzles/`) |
| CSS Layout & Navigation | `volumes/web/css/layout.css` | Bundles CSS (`tools/build_css_bundles.py`) |
| Gabarit SEO & Archives | `src/services/seo_templates.py` | `volumes/web/puzzles/**`, `mot-du-jour/`, `methode/` |
| Synchronisation automatique | `src/services/seo.py` / `tools/sync_layout.py` | Injection au démarrage du conteneur |

---

## 1. Diagnostic & Findings

### UX-01 (🔴) — Identité visuelle, Logo officiel & Header propre
- **Problème :** Uniformiser l'identité de marque et les favicons sur l'ensemble des pages. Le logo officiel `favicon.png` (détouré avec transparence alpha de haute qualité) doit remplacer l'emoji générique `🎯` dans la marque `.brand` du header, et être déclaré canoniquement comme favicon de page (`<link rel="icon">`, `favicon.ico`, `apple-touch-icon`).
- **Correctif :** 
  - Remplacement de l'emoji par l'élément image `<img src="{depth}icons/favicon.png" alt="Cémantix Solver" class="brand-icon" width="48" height="48">` dans l'en-tête universel (`layout_sync.py` et `seo_templates.py`).
  - Déclaration standardisée des icônes de pages dans `<head>` sur toutes les pages HTML (`favicon.png`, `favicon.ico`, `apple-touch-icon.png`).
  - Stylisation adaptative et responsive de `.brand-icon` dans `layout.css` avec effet de halo lumineux cohérent.
- **Vérification :** Présence de `<img src="...icons/favicon.png" ... class="brand-icon"` et `<div class="brand">` dans l'en-tête de toutes les pages statiques et dynamiques.

### UX-02 (🟠) — Normalisation des onglets de navigation (`.nav-tabs`)
- **Problème :** L'ordre des boutons était incohérent d'une page à l'autre (ex. sur `/defi/`, l'onglet était interverti avec `/multi/`), et certains badges étaient absents (`Versus IA` absent sur `/multi/`).
- **Correctif :**
  - Ordre canonique strict fixé sur les 6 vues :
    1. `tab-dashboard` : Tableau de Bord
    2. `tab-play` : Jouer Solo
    3. `tab-battle` : Mode Battle (`<span class="tab-badge">Versus IA</span>`)
    4. `tab-multi` : Mode Multijoueur (`<span class="tab-badge">1v1 Ami</span>`)
    5. `tab-defi` : Défier le Bot (`<span class="tab-badge">Live</span>`)
    6. `tab-archives` : Archives
  - Attribution de la classe `active` stricte à l'onglet correspondant à la page courante.
- **Vérification :** Inspection de l'ordre des `<a>` dans `<nav class="nav-tabs">` sur les 5 fichiers HTML statiques.

### UX-03 (🟠) — Alignement dimensionnel des boutons du menu (Hauteur uniforme 42px)
- **Problème :** Les boutons avec badge (*Versus IA*, *1v1 Ami*, *Live*) sont plus hauts que les boutons sans badge (*Tableau de Bord*, *Jouer Solo*, *Archives*), créant un décroché visuel disgracieux sur la barre de navigation.
- **Correctif :**
  - Fixer sur `.nav-tab` dans `layout.css` et dans le gabarit d'archive :
    ```css
    height: 42px;
    line-height: 1;
    box-sizing: border-box;
    ```
  - Centrage parfait des icônes, libellés et badges sur un même axe horizontal.
- **Vérification :** Contrôle visuel et mesure CSS (`height == 42px` sur tous les onglets avec ou sans badge).

### UX-04 (🟠) — Restauration de l'en-tête, du thème et de la largeur sur `/puzzles/`
- **Problème :** Les pages d'archives perdaient complètement la barre de navigation (`nav-tabs`), possédaient un ancien en-tête minimaliste sans bouton de thème, et la largeur maximale (`.page`) était limitée à 960px (contre 1200px pour `.main-content`).
- **Correctif :**
  - Remplacement de `.site-header` par `.app-header` avec le logo `favicon.png`.
  - Intégration du conteneur `.header-actions` avec le bouton `#theme-toggle` et son script de persistance `localStorage`.
  - Intégration des 6 onglets `.nav-tabs` (avec `tab-archives` actif).
  - Élargissement de `.page` à `max-width: 1200px` dans `src/services/seo_templates.py`.
- **Vérification :** `python tools/check_seo.py` au vert et présence des sélecteurs dans `volumes/web/puzzles/index.html`.

### UX-05 (🔴) — Architecture modulaire en 4 briques & synchronisation Python au démarrage
- **Problème :** Risque permanent de divergence lors des futures évolutions car le HTML du header et de la navigation est recopié manuellement dans chaque fichier statique.
- **Correctif :**
  - Encadrement dans les pages statiques par des balises délimitatrices :
    - `<!-- APP-HEADER:START --> ... <!-- APP-HEADER:END -->`
    - `<!-- NAV-TABS:START --> ... <!-- NAV-TABS:END -->`
  - Automatisation d'une fonction Python de synchronisation (exécutée au démarrage du conteneur via `ensure_seo_published()`) qui propage le gabarit central vers tous les fichiers HTML statiques.
- **Vérification :** Modification test d'un libellé dans le gabarit maître et vérification de la propagation automatique dans tous les fichiers statiques sans altérer leur contenu métier.

