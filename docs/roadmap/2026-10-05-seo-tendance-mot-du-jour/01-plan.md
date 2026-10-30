# 📈 Plan — Percer sur la tendance Google : « mot du jour », « indice », « synonyme »

> **Évolution :** [2026-10 · Tendance Google](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ce fichier décrit **quoi faire et comment le vérifier**, sans état d'avancement.
> **Branche de travail :** `feat/seo-titre-archives-solution` — même branche que l'évolution
> [Titres « Solution Cémantix du <date> »](../2026-10-seo-titres-archives/01-plan.md), les deux
> quick wins SEO visant le même périmètre (`src/services/seo.py` et ses libellés) et devant être
> fusionnés ensemble pour éviter deux PR qui se marchent dessus.
> **Base de référence :** `main` @ `384079b` + évolution [Titres « Solution Cémantix du <date> »](../2026-10-seo-titres-archives/01-plan.md)
> **Date de conception :** 30/10/2026
> **Périmètre exclusif :** libellés et contenu indexable (`src/services/seo.py`, `volumes/web/*.html`, `volumes/web/css/layout.css`, `tools/check_seo.py`). Aucun changement de jeu, d'API, d'URL existante ou de base de données.

**Convention de lecture :** chaque finding porte un identifiant permanent, `SEO-17` à `SEO-21`.
Les identifiants `SEO-01` à `SEO-16` sont déjà attribués par les évolutions
[Sécurité, SEO, performance, qualité](../2026-10-securite-seo-performance/01-plan.md) et
[Titres d'archives](../2026-10-seo-titres-archives/01-plan.md) et ne sont pas réutilisés.

---

## 0. Donnée d'entrée : la tendance Google

Mesure Google Trends sur l'expression `cemantix` (10 requêtes liées, toutes en hausse) :

| # | Requête liée | Variation | Cluster | Couverture du site avant l'évolution |
|---|---|---|---|---|
| 1 | `cemantix indice` | +20 % | **B · indice** | ❌ un seul paragraphe du guide d'accueil |
| 2 | `indice cemantix` | +20 % | **B · indice** | ❌ idem |
| 3 | `cemantix du jour` | +10 % | C · du jour | 🟠 accueil seulement (`<title>`, pas de `<h1>`) |
| 4 | `mot cemantix` | +30 % | **A · mot du jour** | ❌ aucune page dédiée |
| 5 | `mot du jour` | +30 % | **A · mot du jour** | ❌ terme trusté par la presse, hors de portée seul |
| 6 | `cemantix mot du jour` | +30 % | **A · mot du jour** | ❌ |
| 7 | `mot cemantix du jour` | +20 % | **A · mot du jour** | ❌ |
| 8 | `mot du jour cemantix` | +30 % | **A · mot du jour** | ❌ |
| 9 | `synonyme` | +20 % | **D · synonyme** | ❌ zéro contenu |
| 10 | `cemantix solution` | +8 % | E · solution | ✅ pages d'archive par date (`SEO-13`) |

**Lecture de la donnée.** Le cluster **A (mot du jour) concentre 5 requêtes sur 10 et les plus
fortes hausses (+30 %)** ; le cluster **B (indice) occupe les deux premières positions** ; le
cluster **E (solution), traité par l'évolution précédente, est le plus faible (+8 %)**. Celui-ci
reste utile — il capte la longue traîne datée et les pages déjà indexées — mais il ne doit pas
devenir le mot-clé principal du site : c'était le risque du quick win précédent.

**Hypothèse de travail :** on ne gagne pas `mot du jour` sec (la presse et les clones s'en
partagent les résultats), on gagne les **formes combinées** (`mot du jour cemantix`,
`mot cemantix du jour`) et les requêtes **informationnelles** (`indice cemantix`, `synonyme`),
où la concurrence est éditoriale et non institutionnelle.

---

## 1. Diagnostic mesuré sur le dépôt

| Constat | Preuve |
|---|---|
| Un seul `<h1>` pour tout le site, et c'est la marque | `grep -n "<h1>" volumes/web/{index,play,battle,multi}/index.html` → `Cémantix Solver` sur les 4 pages |
| Aucune page ne cible « mot du jour » ni « indice » comme sujet | aucun fichier de `volumes/web/` ne porte de page dédiée ; le guide d'accueil est un `<h2>` parmi d'autres |
| Le mot secret du jour est un `<h2>` rempli en JavaScript | `volumes/web/index.html` : `<h2 id="secret-word">--------</h2>` |
| Le maillage interne des archives ne parle que de « solution » | `build_archives_index_page` : l'ancre reprend le titre de la page cible, cluster faible |
| Un seul contenu long pour toutes les intentions (règles, solveur, FAQ, jeu) | `#guide-faq` de `volumes/web/index.html` : 4 articles, 5 questions |
| Le sitemap ne référence aucune page de destination de ces requêtes | `build_sitemap` : 5 URLs fixes + les archives |

---

## 2. Matrice des findings & correctifs

| # | Sév. | Composant | Problème constaté | Correctif spécifié | Critère de vérification |
|---|---|---|---|---|---|
| **SEO-17** | 🔴 | Page hub `/mot-du-jour/` | 5 requêtes sur 10 sur « mot du jour », aucune page cible | Page rendue côté serveur par `build_mot_du_jour_page()` : `<title>` et `<h1>` « Mot du jour Cémantix du <date française> : indices et solution », résumé du jour, table des dix indices, solution derrière un `<details>`, FAQ `FAQPage`, archives récentes ; publiée même sur historique vide ; `priority 0.95`, `changefreq daily` | `python -m unittest tests.test_seo_hubs -v` vert ; `python tools/check_seo.py` vert |
| **SEO-18** | 🟠 | Page hub `/methode/` | « indice » (#1 et #2) et « synonyme » sans contenu informationnel | Guide ≥ 700 mots `build_methode_page()` : paliers du thermomètre, pour mille, synonymes / antonymes / champs lexicaux, méthode en 5 étapes (`HowTo`) et `FAQPage` ; chaque étape structurée est aussi lisible en clair | `python -m unittest tests.test_seo_hubs -v` vert (longueur et occurrences vérifiées) |
| **SEO-19** | 🟠 | Hub `/puzzles/` | Titre et ancres alignés sur le cluster faible (+8 %) alors que le hub est la page la plus maillée | Titre, `<h1>` et `CollectionPage` recentrés « Cémantix du jour : mot du jour, indices et solutions par date » ; ancres internes via `archive_anchor()` = « Indices et solution du Cémantix du <date> » ; les pages datées conservent leur titre `SEO-13` | `python -m unittest tests.test_seo_archives -v` vert |
| **SEO-20** | 🟠 | Pages applicatives | `<h1>` de marque dupliqué à l'identique sur 4 pages : aucun signal thématique | Marque dégradée en `<span class="brand-title">` (sélecteur `.brand-text .brand-title`, rendu identique), un `<h1 class="page-heading">` descriptif et unique par page, plus une intro qui maille vers les hubs ; bundles et CSS critique reconstruits | `python -m unittest tests.test_seo_hubs -v` (une `<h1>` par page, toutes uniques) ; `python tools/build_css_bundles.py --check` vert |
| **SEO-21** | 🟡 | FAQ & maillage interne | FAQ d'accueil hors sujet tendance ; aucun lien interne vers les nouvelles pages | Trois questions alignées sur la tendance (mot du jour, lecture des indices, synonymes) en accordéon **et** dans le `FAQPage` JSON-LD, texte identique ; liens croisés accueil / archives / hubs, dont le pré-rendu quotidien `resume-link` | `python -m unittest tests.test_seo_hubs -v` vert ; `grep -c "mot-du-jour/" volumes/web/index.html` ≥ 1 |
---

## 3. Spécifications

### 3.1 Une page par intention, jamais deux (`SEO-17`, `SEO-18`, `SEO-19`)

| URL | Intention servie | Mot-clé principal | Mot-clé secondaire |
|---|---|---|---|
| `/` | jouer, tableau de bord, solveur | `cemantix du jour` | `cemantix solution` |
| `/mot-du-jour/` | connaître le mot du jour et ses indices | `mot du jour cemantix` | `mot cemantix du jour` |
| `/methode/` | comprendre et progresser | `indice cemantix` | `synonyme cemantix` |
| `/puzzles/` | retrouver un puzzle passé | `archives cemantix` | `cemantix par date` |
| `/puzzles/AAAA-MM-JJ/` | la réponse d'un jour précis | `solution cemantix du <date>` | `indices cemantix du <date>` |

Aucune page ne vise deux fois le même mot-clé : c'est la fin de la cannibalisation entre
l'accueil, les archives et le nouveau hub.

### 3.2 Les pages hub sont des livrables générés (`SEO-17`, `SEO-18`)

- Rendues par `src/services/seo.py` avec le gabarit `render_page()` des archives : **aucun
  JavaScript**, style injecté, donc indexables telles quelles.
- Écrites dans `volumes/web/mot-du-jour/index.html` et `volumes/web/methode/index.html`, toutes
  deux **ignorées par git** comme `/puzzles/` et `sitemap.xml`, et recréées par
  `ensure_seo_published()` au démarrage de `cemantix_web` / `cemantix_worker`.
- Publiées **même sans historique** : l'URL doit exister et vivre ; elle affiche alors l'état
  d'attente et renvoie vers les archives.
- Profondeur d'URL 1 : les liens relatifs utilisent `_rel_index()` (`../`), et non `_rel()`
  (`../../`, réservé aux archives de profondeur 2). Confondues une première fois, elles ont
  fait tomber trois tests — d'où le contrôle de résolution des liens dans l'audit.

### 3.3 Le `<h1>` devient un titre de page (`SEO-20`)

```html
<!-- avant, à l'identique sur les quatre pages -->
<div class="brand-text"><h1>Cémantix Solver</h1><span class="brand-subtitle">…</span></div>

<!-- après : la marque reste visible et stylée, le h1 décrit la page -->
<div class="brand-text"><span class="brand-title">Cémantix Solver</span><span class="brand-subtitle">…</span></div>
…
<h1 class="page-heading">Cémantix du jour : indices, mot du jour et solution</h1>
<p class="page-intro">… <a href="mot-du-jour/">mot du jour Cémantix</a> … <a href="methode/">méthode des indices</a> …</p>
```

- `layout.css` : `.brand-text h1` devient `.brand-text .brand-title` (+ `display: block`, la
  marque était un élément de bloc) ; nouvelles règles `.page-heading` et `.page-intro`, avec une
  variante `@media (max-width: 768px)` en `clamp()` pour tenir sur 360 px.
- Les bundles `css/dist/*.css` et le `<style id="critical-css">` des quatre pages sont
  **régénérés** par `tools/build_css_bundles.py` : un bundle oublié afficherait un `<h1>` brut de
  navigateur et ferait regresser la validation responsive des évolutions `RESP-*`.

### 3.4 FAQ et données structurées cohérentes (`SEO-21`)

Le texte d'une question en accordéon et son `acceptedAnswer` JSON-LD sont **identiques mot pour
mot** — exigence Google, vérifiée par `test_faq_visible_et_structee` et
`test_howto_et_faq_structures_et_lisibles`.

---

## 4. Plan d'exécution, risques et rollback

| Phase | Action | Commande de recette |
|---|---|---|
| 1 | Hubs `/mot-du-jour/` et `/methode/`, sitemap, `.gitignore` | `python -m unittest tests.test_seo_hubs -v` |
| 2 | `<h1>` descriptifs, CSS, bundles et CSS critique | `python tools/build_css_bundles.py --check` |
| 3 | FAQ, maillage, pré-rendu quotidien | `python -m unittest tests.test_seo_archives tests.test_seo_hubs -v` |
| 4 | Audit global et publication | `python tools/check_seo.py`, `python tools/check_docs.py`, puis redémarrage de `cemantix_web` |
| 5 | Recette visuelle des 4 pages à 360 / 412 / 768 px (le `<h1>` ajouté décale la ligne de flottaison) | captures navigateur, même protocole que `RESP-*` |

| Risque | Impact | Parade |
|---|---|---|
| Confusion `_rel()` / `_rel_index()` selon la profondeur d'URL | liens internes cassés, hubs orphelins | tests de liens et audit `check_seo.py` sur les gabarits rendus en mémoire |
| Bundle CSS non régénéré après modification de `layout.css` | `<h1>` non stylé, régression responsive `RESP-*` | `tools/build_css_bundles.py --check` dans la recette ; un test vérifie que le CSS critique contient `.page-heading` |
| Cannibalisation entre `/` et `/mot-du-jour/` | les deux pages se concurrencent et perdent | matrice d'intentions du §3.1, un mot-clé principal par page |
| Contenu hub jugé insuffisant sans historique | page non classée | version datée publiée dès le premier puzzle résolu ; version d'attente qui maille vers les archives |
| Régression visuelle du tableau de bord | UX mobile dégradée | recette de la phase 5 ; aucune classe existante modifiée hors le sélecteur de marque |

**Rollback :** `git revert` du commit de changement. Les hubs étant régénérés à chaque
publication, ils cessent simplement d'être écrits après rollback ; aucune URL existante n'est
modifiée, donc aucune redirection à configurer.

