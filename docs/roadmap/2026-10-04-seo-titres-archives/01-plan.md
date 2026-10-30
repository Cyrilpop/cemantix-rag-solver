# 🔎 Plan — Titres « Solution Cémantix du <date> » & longue traîne datée

> **Évolution :** [2026-10 · Titres d'archives SEO](../README.md) · document 1/2
> **Statut du document :** référence de conception, versionnée.
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ce fichier décrit **quoi faire et comment le vérifier**, sans état d'avancement.
> **Branche de travail visée :** `feat/seo-titre-archives-solution`
> **Base de référence :** `origin/main` @ `384079b`
> **Date de conception :** 30/10/2026
> **Périmètre exclusif :** libellés des pages d'archives (`src/services/seo.py`), plan du site `sitemap.xml`, documents de découverte pour agents IA (`llms.txt`, `llms.md`, `agent-skills.md`, `.well-known/`). Aucune modification du rendu bureau, du jeu, ni de l'API.

**Convention de lecture :** chaque finding porte un identifiant permanent (`SEO-13` à `SEO-16`) utilisé comme **clé de suivi** dans `02-avancement.md`. Les identifiants `SEO-01` à `SEO-12` sont déjà attribués par l'évolution [Sécurité, SEO, performance, qualité](../2026-10-02-securite-seo-performance/01-plan.md) et ne sont pas réutilisés ici.

---

## 0. Méthodologie & périmètre

L'évolution est un **quick win** : une seule famille de libellés à aligner, sans migration de
données ni changement d'URL. La méthode reste celle des évolutions précédentes — un diagnostic
appuyé sur `fichier:ligne`, un correctif spécifié, une commande de vérification exécutable par
finding.

| Zone | Fichiers sources | Livrables générés |
|---|---|---|
| Page d'archive quotidienne | `src/services/seo.py` (`build_archive_page`) | `volumes/web/puzzles/AAAA-MM-JJ/index.html` |
| Index des archives | `src/services/seo.py` (`build_archives_index_page`) | `volumes/web/puzzles/index.html`, `volumes/web/puzzles/page/N/index.html` |
| Plan du site | `src/services/seo.py` (`build_sitemap`) | `volumes/web/sitemap.xml` (ignoré par git, régénéré au démarrage) |
| Docs agents IA | `src/services/seo.py` (`_agent_dynamic_block`, `build_agent_card`, `build_ard_manifest`) | `volumes/web/llms.txt`, `volumes/web/agent-skills.md`, `volumes/web/.well-known/*.json` |
| Verrouillage | `tests/test_seo_archives.py` | suite `unittest` exécutée par la CI |

---

## 1. Diagnostic

La page d'archive d'un puzzle résolu était titrée :

```text
Cémantix du vendredi 23 octobre 2026 : indices, solution et trajectoire du solveur IA
```

Quatre pertes de classement en découlent (`src/services/seo.py`, fonction `build_archive_page`) :

1. **Le mot-clé « solution » arrivait en 6ᵉ position** du `<title>`, derrière une formule
   descriptive. Or la requête de longue traîne d'un joueur est exactement
   « solution cemantix du 26 octobre 2026 » : le terme le plus concurrentiel doit ouvrir le titre.
2. **Le `meta description` ne commençait pas par le mot-clé** (« Indices du Cémantix du… »),
   ce qui dilue le taux de clic en page de résultats alors que la page contient bien la solution.
3. **L'index `/puzzles/` maillait avec une date nue** (`<span>lundi 26 octobre 2026</span>`) :
   le texte d'ancre, critère de classement explicite chez Google, ne disait pas ce que le lien
   contient. La page d'archive est pourtant atteinte **uniquement** par ce maillage interne.
4. **Les agents IA (AEO) ne connaissaient pas le motif de titre** : `llms.txt`,
   `agent-skills.md` et la carte d'agent décrivaient une URL ISO sans jamais donner le libellé à
   citer, ce qui pousse un agent à citer une date brute ou, pire, à inventer un titre.

Contrainte inverse à ne jamais casser : `sitemap.xml` est régi par le protocole
[sitemaps.org](https://www.sitemaps.org/protocol.html), qui n'accepte **que** les dates W3C/ISO
(`AAAA-MM-JJ`, `AAAA-MM-JJThh:mm:ss+hh:mm`). Y écrire « lundi 26 octobre 2026 » rend le fichier
invalide et fait perdre l'indexation de **toutes** les archives d'un coup.

---

## 2. Matrice des findings & correctifs

| # | Sév. | Composant | Problème constaté | Correctif spécifié | Critère de vérification |
|---|---|---|---|---|---|
| **SEO-13** | 🟠 | Page d'archive | `<title>` et `meta description` ne portent pas le mot-clé « solution » en tête (`build_archive_page`) | Constante `ARCHIVE_TITLE_PREFIX` + fonction `archive_title()` ; libellé unique « Solution Cémantix du lundi 26 octobre 2026 » propagé dans `<title>`, `<h1>`, `og:title`, `twitter:title`, `description` et `headline` JSON-LD | `python -m unittest tests.test_seo_archives -v` vert ; titre ≤ 60 caractères, sans date ISO |
| **SEO-14** | 🟡 | Index des archives | Texte d'ancre = date nue, titre et `h1` de l'index hors sujet « solution » (`build_archives_index_page`) | Titre « Solution Cémantix : archives de tous les puzzles résolus par l'IA », `h1` aligné, une ancre par date reprenant le titre complet de la page cible | L'index généré contient une ancre « Solution Cémantix du <date française> » par archive |
| **SEO-15** | 🔴 | Plan du site | Risque de régression : la date française ne doit **jamais** entrer dans `sitemap.xml` (`build_sitemap`) | Aucune modification du générateur ; le contrat ISO est verrouillé par test (`<loc>` et `<lastmod>` en `AAAA-MM-JJ`, aucune chaîne française) | `python -m unittest tests.test_seo_archives -v` vert ; `grep -c octobre volumes/web/sitemap.xml` renvoie `0` |
| **SEO-16** | 🟡 | Docs agents IA | `llms.txt`, `agent-skills.md`, `agent-card.json` et le catalogue ARD ignorent le motif de titre des archives | Bloc dynamique `AGENT-DYNAMIC` daté en français long **et** en ISO, carte d'agent `dated-archive` décrivant le motif, requêtes représentatives « solution du Cémantix du … », `llms.md` documentant le contrat titre/URL | `python tools/check_seo.py` vert ; `python -m unittest tests.test_docs_agent -v` vert ; manifestes versionnés identiques à leur générateur |
---

## 3. Spécifications

### 3.1 Libellé unique, une seule source de vérité (SEO-13)

- **Fichier impacté :** `src/services/seo.py`
- Le gabarit est défini **une fois** :

  ```python
  ARCHIVE_TITLE_PREFIX = "Solution Cémantix du"

  def archive_title(value) -> str:
      return f"{ARCHIVE_TITLE_PREFIX} {format_date_fr(value)}"
  ```

- `format_date_fr()` (déjà en place) rend `lundi 26 octobre 2026` : jour de semaine, quantième,
  mois, année. C'est la forme tapée par un chercheur francophone, et celle que la SERP affiche.
- Le libellé obtenu fait **42 caractères** : il tient intégralement dans un extrait Google
  (troncature ~60 caractères), contrairement aux **85 caractères** de l'ancien titre, tronqués
  dès la SERP mobile.
- Le `<h1>` reprend mot pour mot le `<title>` : un seul motif, répété, sans duplication de
  contenu ni bourrage de mots-clés.
- La `meta description` **commence** par le libellé puis enchaîne sur la réponse attendue
  (mot secret, nombre de mots indexés, coups, méthode, numéro de puzzle) et reste sous 175
  caractères.
- Le fil d'Ariane, visible et `BreadcrumbList`, affiche la date française ; `datePublished`
  JSON-LD reste en ISO, seul format valide pour une propriété de date Schema.org.

### 3.2 Maillage interne de l'index (SEO-14)

- Chaque ligne de `/puzzles/` devient
  `<a href="puzzles/AAAA-MM-JJ/"><span>Solution Cémantix du lundi 26 octobre 2026</span><span>9 coups</span></a>` :
  le texte d'ancre décrit la cible, la seconde pastille conserve la performance du solveur.
- L'URL, les `rel="prev"`/`rel="next"` et la pagination ne bougent pas : **aucune redirection**
  à prévoir, l'indexation et le positionnement déjà acquis sont conservés.

### 3.3 Ce que le sitemap ne peut pas contenir (SEO-15)

- `build_sitemap()` reste inchangé : `<loc>` en `/puzzles/AAAA-MM-JJ/`, `<lastmod>` en ISO.
- La date en français long vit donc **dans la page** (`<title>`, `<h1>`, fil d'Ariane, JSON-LD)
  et **dans l'index lisible** `/puzzles/`, qui joue le rôle de plan du site pour un humain comme
  pour un crawler.
- Le contrat est double et doit rester lisible dans le code comme dans les tests : *date
  française dans les libellés, ISO dans les machines*.

### 3.4 Découvrabilité pour les agents IA (SEO-16)

- **Bloc `AGENT-DYNAMIC`** de `llms.txt` et `agent-skills.md`, régénéré à chaque publication :
  l'archive la plus récente est présentée sous son titre complet, l'ISO reste cité entre
  contre-gouttières, et le motif « Solution Cémantix du <date en français long> » est donné aux
  agents comme libellé de citation.
- **`agent-card.json`** : la compétence `dated-archive` décrit le motif de titre et gagne une
  requête d'exemple « Quelle est la solution du Cémantix du 26 octobre 2026 ? », tag `solution`.
- **`ai-catalog.json` / `ard.json`** : requête représentative « Quelle est la solution du
  Cémantix du lundi 26 octobre 2026 ? ». Les trois manifestes versionnés doivent rester **byte
  pour byte** identiques à leur générateur (`tests/test_seo_startup.py` le vérifie).
- **`llms.md`** : remplace l'exemple d'URL figé (`2026-10-26`, voué à pourrir) par la description
  du contrat titre français / URL ISO.

---

## 4. Plan d'exécution & risques

| Phase | Action | Commande de recette |
|---|---|---|
| 1 | Libellés d'archive + index (`SEO-13`, `SEO-14`) | `python -m unittest tests.test_seo_archives -v` |
| 2 | Contrat sitemap verrouillé (`SEO-15`) | `python -m unittest tests.test_seo_archives.TestSitemapGardeLeFormatIso -v` |
| 3 | Docs agents + régénération des manifestes (`SEO-16`) | `python tools/check_seo.py` puis `python -m unittest tests.test_docs_agent -v` |
| 4 | Publication réelle | Redémarrage de `cemantix_web` ou `python cemantix_rag.py --export-web`, puis lecture de `volumes/web/puzzles/<date>/index.html` |

| Risque | Impact | Parade |
|---|---|---|
| Date française injectée dans `sitemap.xml` | Rejet du plan du site, perte d'indexation de toutes les archives | `TestSitemapGardeLeFormatIso` échoue dès qu'« octobre » ou « Solution Cémantix » apparaît dans le XML |
| Titre trop long tronqué en SERP | Perte du mot-clé de fin | `test_le_titre_reste_court_pour_la_serp` plafonne à 60 caractères (40 observés) |
| Manifestes `.well-known/` désynchronisés du générateur | Échec de l'audit ARD / Lighthouse | Régénération par `publish_ard_manifests()` et test de comparaison exacte |
| Clé de cache inchangée après déploiement | SERP et visiteurs servis sur l'ancien titre | Les pages sont régénérées chaque nuit et au démarrage du conteneur ; la date figure dans le nom de fichier, le HTML est réécrit |

**Rollback :** `git revert` du commit de changement. Aucune migration, aucune écriture en base,
aucun changement d'URL : les pages d'archive sont régénérées à l'identique au cycle suivant.

