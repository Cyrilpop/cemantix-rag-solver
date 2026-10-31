# M5 — Frontend Simplification & Agent Context Efficiency

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Date :** 31 octobre 2026  
**Branche :** `feature/audit-hey-you`  
**Statut :** Complété — Zéro régression, Architecture Vanilla préservée, 268 tests passants (20 nouveaux tests)  

---

## 1. Résumé Exécutif

Le jalon **M5** avait pour objectif de réduire la duplication frontend, d'accroître la maintenabilité du code client et de minimiser la consommation inutile de contexte par les agents IA, **sans altérer l'apparence visuelle, les règles de jeu, ni l'architecture Vanilla HTML/CSS/JavaScript**.

### Objectifs Atteints
1. **Zéro framework / Zéro complexité superflue** : aucun ajout de framework tiers (React, Vue, Vite). Maintien strict de l'architecture ES Modules natifs et du pipeline CSS.
2. **Mutualisation du rendu JavaScript** :
   - Élimination de la duplication du gabarit de trajectoire entre `defi.js` et `trajectory.js` via la fonction partagée `buildTrajectoryStepHtml`.
   - Délégation du rendu des listes de tentatives dans `game.js` au module partagé `render.js` (`renderGuessesContainer`), apportant au mode solo le cache anti-scintillement et la copie au clic.
3. **Allègement des gabarits HTML statiques** :
   - Injection dynamique de `#trajectory-modal` par `ensureTrajectoryModal()` dans `trajectory.js`, permettant de supprimer 68 lignes de duplication HTML dans `volumes/web/defi/index.html`.
   - Suppression du gestionnaire inline `onsubmit="return false;"` dans `volumes/web/multi/index.html` (durcissement CSP).
4. **Dédoublonnage CSS ciblé** :
   - Suppression des définitions dupliquées de `.pill-group` et `.pill-btn` dans `game.css` (déjà présentes dans `base.css`), allégeant les bundles compilés `play.css`, `battle.css` et `multi.css` de 514 octets chacun.
5. **Efficacité de Contexte pour Agents IA** :
   - Extension de `tools/agent_find.py` pour détecter et indexer les repères HTML (`id`, `<header>`, `<nav>`, `<main>`, `<section>`, `<form>`).
   - Détection automatique du bloc CSS critique inliné (L49, ~32 ko / ~8 000 tokens) avec avertissement et recommandation de plages de lecture sûres.
   - Ajout de la commande `--safe-html` permettant aux agents d'inspecter les `<head>` HTML sans ingérer 30 à 42 ko de CSS minifié.
   - Mise à jour des directives opérationnelles dans `AGENTS.md` et de la mémoire d'architecture dans `project-memory.md`.
6. **Sanctuarisation par les Tests** :
   - Ajout de 20 nouveaux tests déterministes (15 dans `test_frontend_characterization.py` et 5 dans `test_agent_find.py`).
   - Suite globale portée de **248 à 268 tests unitaires** (100 % passants en 7,1 s sous Docker Python 3.12).

---

## 2. Phase 1 — Audit & Baseline

### 2.1 Cartographie du Volume et de la Duplication Source

L'analyse initiale de `volumes/web/` a révélé les métriques suivantes :

| Fichier / Sous-Système | Rôle | Taille Initiale | Lignes Initiales | Problème Identifié |
|---|---|---|---|---|
| `volumes/web/js/game.js` | Moteur jeu solo | 26 096 o | 694 | Re-génération manuelle des lignes de coups dupliquant la logique de `render.js`. |
| `volumes/web/js/defi.js` | Contrôleur du défi bot | 11 083 o | 326 | Duplication de la fonction `stepRowHtml` avec `trajectory.js`. |
| `volumes/web/js/render.js` | Rendu partagé des coups | 3 512 o | 88 | Limité à `battle.js` et `multi.js` par manque d'option de préfixe de rang. |
| `volumes/web/js/trajectory.js` | Modal débriefing IA | 11 017 o | 264 | Nécessitait la présence de la structure modale statique dans chaque page appelante. |
| `volumes/web/css/game.css` | Styles du jeu solo | 15 261 o | 829 | Duplication stricte des classes `.pill-group` et `.pill-btn` définies dans `base.css`. |
| `volumes/web/defi/index.html` | Page HTML défi bot | 42 620 o | 312 | Duplication statique de 68 lignes du gabarit `#trajectory-modal`. |
| `volumes/web/multi/index.html` | Page multijoueur | 72 072 o | 582 | Attribut inline `onsubmit="return false;"` non conforme CSP. |
| `volumes/web/*/index.html` (5 pages) | Gabarits HTML principaux | 301 861 o | 2 626 | 170 042 octets de CSS critique inliné sur une seule ligne (L44-L49), saturant le contexte des agents. |

### 2.2 Typologie de la Duplication

- **Duplication Générée Intentionnelle (Sanctuarisée) :**
  - Fichiers `volumes/web/css/dist/*.css` : générés par `tools/build_css_bundles.py` pour minimiser les requêtes HTTP (5-6 requêtes $\to$ 1).
  - Blocs `<style id="critical-css">` inlinés dans `<head>` : nécessaires pour garantir 0 requête CSS bloquante et préserver les scores Lighthouse Mobile (FCP/LCP).
  - Archives statiques `/puzzles/` : générées côté serveur pour l'indexabilité SEO sans exécution JS.
- **Duplication Source Évitable (Éliminée en M5) :**
  - Rendu redondant des coups dans `game.js` vs `render.js`.
  - Gabarit HTML d'étapes de trajectoire répété dans `defi.js` vs `trajectory.js`.
  - Markup `#trajectory-modal` copié-collé dans `defi/index.html`.
  - Règles CSS desktop `.pill-btn` copiées de `base.css` vers `game.css`.

---

## 3. Phase 2 — Caractérisation Déterministe

Avant toute modification, deux suites de tests de caractérisation ont été créées :

### 3.1 [`tests/test_frontend_characterization.py`](../../tests/test_frontend_characterization.py) (15 tests)
- **Contrats DOM stricts** : vérification de la présence de tous les sélecteurs critiques pour chaque mode (`#secret-word`, `#game-spotlight`, `#battle-scoreboard`, `#room-code-input`, `#defi-status`, etc.).
- **Contrat de navigation unifiée** : présence des 6 onglets de navigation (`tab-dashboard`, `tab-play`, `tab-battle`, `tab-defi`, `tab-multi`, `tab-archives`) et correspondance rigoureuse de l'onglet actif.
- **Accessibilité & Sécurité CSP** : conformité `role="dialog"` et `aria-modal="true"` sur les modales, interdiction d'attributs inline `onclick=` et `onload=`, présence du `viewport-fit=cover`.
- **Contrats d'exports ES Modules** : stabilité des interfaces exportées par `utils.js`, `render.js`, `theme.js` et `trajectory.js`.
- **Politique anti-spoiler** : interdiction absolue de mots secrets en clair dans les sources HTML.

### 3.2 [`tests/test_agent_find.py`](../../tests/test_agent_find.py) (5 tests)
- Localisation déterministe des symboles Python, JS et HTML (`#id` et balises structurelles).
- Détection du bloc CSS critique inliné et calcul d'économie de tokens.
- Validation du mode de lecture protégé `--safe-html`.

---

## 4. Phase 3 — Simplifications Ciblées & Implémentées

### 4.1 Unification du Rendu des Coups dans `render.js` et `game.js`
- Dans [`volumes/web/js/render.js`](../../volumes/web/js/render.js) :
  Ajout du paramètre `orderFormat` (`"default"`, `"rank"`, `"brackets"`) dans `buildGuessesListHtml` et inclusion dans la clé de cache `_lastRenderCache`.
- Dans [`volumes/web/js/game.js`](../../volumes/web/js/game.js) :
  Remplacement de 52 lignes de manipulation directe de `innerHTML` par deux appels à `renderGuessesContainer` :
  ```javascript
  function renderGameLists() {
    renderGuessesContainer("game-top-list", gameState.topGuesses, {
      emptyMessage: "Vos meilleures tentatives apparaîtront ici.",
      orderFormat: "rank",
    });
    renderGuessesContainer("game-chrono-list", gameState.history, {
      emptyMessage: "Aucun mot joué pour le moment.",
      orderFormat: "brackets",
    });
  }
  ```
  *Bénéfice :* Suppression de 51 lignes (-7,3 % de taille), élimination du clignotement DOM lors des soumissions, et ajout automatique de la copie du mot au clic.

### 4.2 Unification de la Trajectoire dans `trajectory.js` et `defi.js`
- Dans [`volumes/web/js/trajectory.js`](../../volumes/web/js/trajectory.js) :
  - Extraction de `buildTrajectoryStepHtml(item, options)` réutilisable.
  - Implémentation de `ensureTrajectoryModal()` créant dynamiquement le conteneur modal dans le DOM s'il est absent.
- Dans [`volumes/web/js/defi.js`](../../volumes/web/js/defi.js) :
  - Suppression de la fonction `stepRowHtml` (40 lignes).
  - Utilisation directe de `buildTrajectoryStepHtml(s, { showGauge: false })`.
- Dans [`volumes/web/defi/index.html`](../../volumes/web/defi/index.html) :
  - Retrait des 68 lignes de modal statique dupliquée.

### 4.3 Dédoublonnage CSS et Régénération des Bundles
- Dans [`volumes/web/css/game.css`](../../volumes/web/css/game.css) :
  - Retrait des règles desktop redondantes `.pill-group`, `.pill-btn`, `.pill-btn:hover`, `.pill-btn.active`.
  - Conservation des surcharges `@media (max-width: 768px)` spécifiques au mobile.
- Régénération via `tools/build_css_bundles.py` :
  - `play.css` : 38 660 $\to$ 38 146 octets (-514 o).
  - `battle.css` : 52 262 $\to$ 51 748 octets (-514 o).
  - `multi.css` : 53 029 $\to$ 52 515 octets (-514 o).

### 4.4 Outils d'Efficacité Contexte Agent
- Amélioration de [`tools/agent_find.py`](../../tools/agent_find.py) :
  - Découverte des identifiants et balises HTML structurelles (`python tools/agent_find.py secret-word`).
  - Diagnostic d'encombrement token dans `--summary` :
    ```
    ⚠️  CSS critique généré inliné : L49 (32,333 car. | ~8,083 tokens)
    💡 Conseil de navigation : inspecter L1-L48 ou L52-L695 pour préserver le contexte.
       Ou utiliser : python tools/agent_find.py --safe-html volumes/web/index.html
    ```
  - Mode lecture masquée `--safe-html` : remplace la ligne minifiée par un repère de 120 caractères.
- Mise à jour de [`AGENTS.md`](../../AGENTS.md) : plages de lecture recommandées pour chaque page HTML excluant le bloc critique.

---

## 5. Mesures Avant / Après

### 5.1 Évolution de la Taille des Modules Modifiés

| Composant | Taille Avant | Taille Après | Évolution (Lignes) | Évolution (Octets) | Gain % |
|---|---|---|---|---|---|
| `volumes/web/js/game.js` | 26 096 o | 24 198 o | 694 $\to$ 643 (-51) | -1 898 o | **-7.3 %** |
| `volumes/web/js/defi.js` | 11 083 o | 9 631 o | 326 $\to$ 286 (-40) | -1 452 o | **-13.1 %** |
| `volumes/web/css/game.css` | 15 261 o | 14 642 o | 829 $\to$ 799 (-30) | -619 o | **-4.1 %** |
| `volumes/web/defi/index.html` | 42 620 o | 38 642 o | 312 $\to$ 245 (-67) | -3 978 o | **-9.3 %** |
| `css/dist/play.css` | 38 660 o | 38 146 o | — | -514 o | **-1.3 %** |
| `css/dist/battle.css` | 52 262 o | 51 748 o | — | -514 o | **-1.0 %** |
| `css/dist/multi.css` | 53 029 o | 52 515 o | — | -514 o | **-1.0 %** |
| **Total Gains Directs** | — | — | **-188 lignes** | **-9 489 o** | — |

### 5.2 Économie de Contexte IA par Fichier Inspecté

Grâce aux repères de navigation et au masquage `--safe-html` dans `agent_find.py` :

| Page HTML Inspectée | Taille Ligne CSS Critique | Tokens Épargnés par Inspection |
|---|---|---|
| `volumes/web/index.html` (Dashboard) | 32 333 octets | **~8 083 tokens** |
| `volumes/web/play/index.html` (Solo) | 27 110 octets | **~6 777 tokens** |
| `volumes/web/battle/index.html` (Battle) | 40 557 octets | **~10 139 tokens** |
| `volumes/web/multi/index.html` (Multi) | 41 311 octets | **~10 327 tokens** |
| `volumes/web/defi/index.html` (Défi Bot) | 27 110 octets | **~6 777 tokens** |
| **Total par tournée d'inspection complète** | **168 421 octets** | **~42 100 tokens économisés** |

---

## 6. Phase 4 — Validation Complète

Toutes les vérifications indispensables ont été exécutées avec succès :

### 6.1 Suite de Tests Unitaires (268 tests, 0 échec)
```bash
docker run --rm -v $(pwd):/app -w /app --entrypoint python cemantix:latest -m unittest discover -s tests -v
# Ran 268 tests in 7.109s — OK
```
- 248 tests de base issus de M1, M2, M2.1, M3 et M4 : **100 % passants**.
- 15 tests de caractérisation frontend (`test_frontend_characterization.py`) : **100 % passants**.
- 5 tests de l'utilitaire agent (`test_agent_find.py`) : **100 % passants**.

### 6.2 Contrôles Qualité et Rétrocompatibilité
- **Cohérence documentaire & roadmap** : `python tools/check_docs.py` $\to$ **OK**.
- **Audit SEO & ARD** : `python tools/check_seo.py` $\to$ **OK** (5 pages principales + hubs + manifestes ARD conformes).
- **Synchronisation des bundles CSS** : `python tools/build_css_bundles.py --check` $\to$ **OK** (tous les bundles à jour).
- **Tests responsive & CSP** : `test_responsive.py` $\to$ **OK** (socle desktop, 12 invariants mobiles et zéro requête bloquante vérifiés).

---

## 7. Conclusion

Le jalon M5 démontre qu'une simplification frontend ciblée et respectueuse de l'architecture vanilla permet d'obtenir des gains substantiels de maintenabilité (-188 lignes de code source, élimination des redondances HTML/JS/CSS) et de réduire massivement la charge de contexte pour les agents IA (~42 000 tokens épargnés), sans aucune rupture de contrat, sans refonte superflue et avec une couverture de test renforcée à 268 tests déterministes.
