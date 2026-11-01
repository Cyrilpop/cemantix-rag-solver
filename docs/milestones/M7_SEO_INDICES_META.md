# Jalon M7 — Optimisation SEO des Métadonnées : Indices, Synonymes et Mots Proches

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m7-seo-indices-metas` (base `origin/main`)  
**Statut :** Spécification technique & contrat d'implémentation SEO  
**Périmètre exclusif :** `src/services/seo_templates.py`, `src/services/seo_archives.py`, `src/services/seo_hubs.py`, `src/services/seo.py`, actualisation des tests dans `tests/`, ainsi que la documentation associée (`README.md`, `CHANGELOG.md`).

---

## 1. Objectifs Métier et Intentions de Recherche

Ce jalon restructure les balises d'en-tête HTML (`<title>`, `<meta name="description">`), les protocoles OpenGraph et Twitter Cards ainsi que les données structurées Schema.org (`Article`, `CollectionPage`, `FAQPage`) pour capter les requêtes à forte croissance constatées sur le jeu Cémantix :
- Requêtes principales : « indice cemantix du jour », « cemantix indice du jour », « aide cemantix ».
- Requêtes de longue traîne : « synonyme [mot indice] », « [mot indice] synonyme ».
- Rétention : Afficher la liste des 10 mots indices les plus proches pour offrir une aide immédiate sans révéler le mot secret.

---

## 2. Spécification des Métadonnées et Formats

### 2.1 Extraction et formatage des 10 mots indices
Dans chaque contexte d'affichage d'un puzzle résolu, extraire les 10 premiers éléments de la liste `top_guesses` en excluant les valeurs masquées (`••••••••`) ou vides.
- Normalisation : mots en minuscules, séparés par une virgule et une espace.
- Exemple de rendu : `loi, décret, constitution, règle, code, juriste, texte, statut, arrêté, norme`.
- Cas limite : si la liste contient moins de 10 mots, utiliser l'intégralité des mots disponibles sans lever d'erreur. Si la liste est vide, omettre la parenthèse descriptive.

### 2.2 Balises `<title>` et `<h1>`
- **Pages d'archives (`/puzzles/AAAA-MM-JJ/`) :**
    - Avec numéro de puzzle :  
      `Indice Cémantix #{puzzle} du {date_fr} : 10 indices, synonymes et solution`
    - Sans numéro de puzzle :  
      `Indice Cémantix du {date_fr} : 10 indices, synonymes et solution`
- **Page Hub Mot du jour (`/mot-du-jour/`) :**  
  `Indice Cémantix du jour ({date_fr}) : indices, synonymes et mot du jour`
  *(En l'absence de puzzle résolu : `Indice Cémantix du jour : indices, synonymes et mot du jour`).*
- **Index paginé des archives (`/puzzles/`) :**
    - Page 1 : `Indice Cémantix du jour : archives des mots du jour, indices et solutions par date`
    - Page N : `Indice Cémantix du jour : archives des indices et solutions, page {page}`

### 2.3 Balises `<meta name="description">`, `og:description` et `twitter:description`
- **Pages d'archives (`/puzzles/AAAA-MM-JJ/`) :**
  `Indices Cémantix #{puzzle} du {date_fr} : aide sans spoiler avec les 10 mots les plus proches ({mots_indices}) et synonymes pour trouver le mot secret en {tries} coups.`  
  *(Si le nombre de coups ou le numéro de puzzle n'est pas renseigné, adapter la formulation sans rompre la grammaire).*
- **Page Hub Mot du jour (`/mot-du-jour/`) :**  
  `Indice Cémantix du jour du {date_fr} : consultez les 10 indices thermiques ({mots_indices}), les synonymes à explorer et la solution dépliable du puzzle #{puzzle}.`

### 2.4 Synchronisation Schema.org JSON-LD
Les propriétés `headline` et `description` des objets JSON-LD (`Article`, `CollectionPage`) dans `seo_archives.py` et `seo_hubs.py` doivent reprendre strictement les chaînes générées pour les balises HTML correspondantes.

---

## 3. Plan d'Implémentation Détaillé

### 3.1 Module `src/services/seo_templates.py`
1. Ajouter la fonction utilitaire :
   def format_clue_words_list(guesses: list, limit: int = 10) -> str:
   words = []
   for g in (guesses or [])[:limit]:
   w = str(g.get("word") or "").strip().lower()
   if w and w != "••••••••":
   words.append(w)
   return ", ".join(words)
2. Mettre à jour `archive_title(value, puzzle=None) -> str` :
    - Remplacer le préfixe fixe actuel par le modèle :  
      `Indice Cémantix #{p_clean} du {date_fr}` ou `Indice Cémantix du {date_fr}`.
3. Exporter `format_clue_words_list` dans `__all__`.

### 3.2 Module `src/services/seo_archives.py`
1. Dans `build_archive_page` :
    - Extraire les indices via `format_clue_words_list(guesses, limit=10)`.
    - Mettre à jour la variable `title` :  
      `title = f"{archive_title(date_str, puzzle=puzzle)} : 10 indices, synonymes et solution"`
    - Injecter les mots formatés dans `description`.
    - Mettre à jour l'objet Schema.org `Article`.

### 3.3 Module `src/services/seo_hubs.py`
1. Dans `build_mot_du_jour_page` :
    - Construire la chaîne des 10 mots indices du puzzle actif.
    - Mettre à jour `titre` et `description` selon la spécification de la section 2.
    - Synchroniser le bloc JSON-LD `Article`.
2. Dans `_render_hub_page` :
    - Assurer la cohérence des variables transmises aux composants de rendu.

### 3.4 Module `src/services/seo.py`
1. Dans `_daily_summary` :
    - Valoriser la mention des indices et des synonymes dans le texte statique.
2. Dans `prerender_dashboard` :
    - Ajuster les chaînes statiques de substitution (`resume-title`, `resume-subtitle`) avec les nouveaux libellés axés sur les indices.

### 3.5 Documentation et Suivi de Version (`README.md`, `CHANGELOG.md`)
1. Dans `CHANGELOG.md` :
    - Ajouter une entrée sous la version en cours (ou créer la section M7 / Unreleased) :
        - `### Added` : Enrichissement sémantique des métadonnées avec les 10 mots indices du jour.
        - `### Changed` : Réalignement des balises `<title>`, `<h1>` et `<meta name="description">` sur les intentions de recherche « indices », « synonymes » et « aide cemantix ».
2. Dans `README.md` :
    - Mettre à jour si nécessaire la section décrivant la génération SEO statique pour mentionner l'injection automatique des mots indices et la couverture de la longue traîne sémantique.

---

## 4. Tests et Validation de Non-Régression

1. **Mise à jour des tests existants :**
    - Mettre à jour les assertions dans `tests/test_seo_archives.py`, `tests/test_seo_characterization.py` et `tests/test_seo_backward_compat.py` pour valider les nouveaux formats de titres et de descriptions.
2. **Vérification de compilation syntaxique :**
   python -m py_compile src/services/seo_templates.py src/services/seo_archives.py src/services/seo_hubs.py src/services/seo.py
3. **Exécution de la suite de tests unitaires :**
   python -m unittest discover -s tests -v
   Critère d'acceptation : validation stricte de l'ensemble des tests sans échec.

---

## 5. Protocole Git et Commits Atomiques

Exécuter rigoureusement dans cet ordre :
1. `git stash push -u -m "m7-spec" -- docs/milestones/M7_SEO_INDICES_META.md`
2. `git fetch origin`
3. `git checkout -B feature/m7-seo-indices-metas origin/main`
4. `git stash pop`
5. `git add docs/milestones/M7_SEO_INDICES_META.md`
6. `git commit -m "docs(seo): ajout du cahier des charges M7 pour les métadonnées d'indices"`
7. Application des modifications dans `src/services/` et `tests/`.
8. Validation complète des tests.
9. Commit atomique des modifications fonctionnelles :
    - `git add src/services/ tests/`
    - `git commit -m "feat(seo): intégration des 10 mots indices et termes trends dans les métadonnées"`