# Roadmap — évolutions du produit

Trajectoire du produit, découpée en **évolutions**. Chaque évolution (audit, refonte, nouveau mode,
durcissement) occupe **un sous-dossier autonome**, versionné, qui raconte l'intégralité du
changement : le diagnostic, la spécification des correctifs, et l'état d'avancement.

Vocabulaire retenu : **roadmap** désigne le conteneur (la trajectoire et ses priorités),
**évolution** désigne l'unité (un dossier, un plan, un suivi). Les deux termes ne sont pas
interchangeables dans ce fichier.

Ce dossier ne contient **aucune** information d'avancement lui-même, hormis l'index §3.

---

## 1. Conventions

### 1.1 Arborescence

```text
docs/roadmap/
├── README.md                          <- ce fichier : index + conventions
└── 2026-10-02-securite-seo-performance/  <- une evolution = un dossier
    ├── 01-plan.md                     <- QUOI faire (reference de conception)
    └── 02-avancement.md               <- OU on en est (tableaux de statut)
```

### 1.2 Nom des dossiers

`AAAA-MM-NN-slug` en **minuscules ASCII**, mots séparés par des tirets, sans accent.
`NN` est le **rang d'ouverture dans le mois**, sur deux chiffres, à partir de `01`.

| Règle | Raison |
|---|---|
| Préfixe `AAAA-MM` (mois d'ouverture) | tri chronologique naturel dans l'explorateur, `ls` et GitHub ; évite deux slugs identiques à six mois d'écart |
| **Rang `NN` dans le mois** | le mois seul ne suffit pas à ordonner : cinq évolutions ouvertes en octobre 2026 se rangeaient **par slug**, donc à l'envers de l'histoire du projet. `NN` fait coïncider ordre alphabétique et ordre chronologique |
| Slug **thématique**, pas technique | on retrouve une évolution par son intention (« securite-seo-performance »), pas par le nom d'un fichier touché |
| Jamais de numéro **seul** | `evo-01` ne dit rien ; `NN` n'a de sens qu'adossé au mois, qui le borne et le rend non ambigu |
| Nom **figé à l'ouverture** | le dossier devient une référence stable des `CHANGELOG.md` et des messages de commit |

Renommer un dossier reste possible mais coûte cher : il faut reprendre l'index §3, les
renvois croisés entre plans et le `CHANGELOG.md` — 32 références pour le passage à `NN`.
L'outillage, lui, n'en dépend plus : `tools/check_docs.py` découvre les suivis via
`docs/roadmap/*/02-avancement.md` et non par un nom écrit en dur.

### 1.3 Nom des fichiers

| Fichier | Contenu | Interdits |
|---|---|---|
| `01-plan.md` | diagnostic, findings avec preuve `fichier:ligne`, correctifs spécifiés, critères de vérification exécutables, plan d'exécution par phases, risques et rollbacks | **aucun statut d'avancement** |
| `02-avancement.md` | tableau de bord, état des dépôts, environnement de test, journal daté, suivi de chaque finding, prochaines actions | aucune spécification nouvelle |

Le préfixe `01-` / `02-` **impose l'ordre de lecture** (le plan se lit avant son avancement) dans
l'explorateur VS Code, sur GitHub et en ligne de commande — l'ordre alphabétique naturel placerait
« avancement » avant « plan », ce qui est à l'envers du sens de lecture.

Un dossier peut accueillir des fichiers supplémentaires si l'évolution l'exige, numérotés à la suite
et dans l'ordre de lecture : `03-maquette.md`, `04-recette.md`, `05-post-mortem.md`.

### 1.4 Règles de fond

1. **Un finding = un ID permanent** (`SEC-03`, `PERF-06`, `SEO-01`…), défini dans `01-plan.md` et
   utilisé comme clé dans `02-avancement.md`. Un ID n'est jamais renommé ni réattribué, même après
   abandon (statut `🚫 Renoncé`).
2. **Une ligne du suivi passe en `✅ Fait` uniquement si la commande de vérification du plan sort
   verte.** Un commit, ou son message, ne vaut pas preuve.
3. Le suivi cite ses **preuves mesurées** (sortie de commande, taille de fichier, SHA de commit),
   jamais une intention.
4. Une évolution terminée **n'est pas supprimée** : elle devient l'historique des décisions. Son
   statut dans l'index §3 passe à `Clôturée`.
5. Chaque PR qui implémente un finding mentionne son ID dans le message (`fix(securite): SEC-01 …`)
   et le `CHANGELOG.md` reste la source de vérité *par version*, l'évolution la source *par thème*.

---

## 2. Ouvrir une nouvelle évolution

```bash
# 1. Creer le dossier au nom de l'evolution (AAAA-MM-NN-slug, NN = rang d'ouverture dans le mois)
mkdir docs/roadmap/2026-12-01-slug-de-levaluation

# 2. Reprendre la structure du dossier existant comme gabarit de mise en forme
cp docs/roadmap/2026-10-02-securite-seo-performance/01-plan.md \
   docs/roadmap/2026-12-01-slug-de-levaluation/01-plan.md
# puis vider 01-plan.md de son contenu et relancer la methodologie du §0 du modele

# 3. Declarer l'evolution dans l'index ci-dessous (statut "En cours")
```

Le contenu de `01-plan.md` du dossier existant sert de **gabarit de forme** : sa section
« Méthodologie & périmètre » et ses en-têtes de tableau sont la convention à réutiliser.

---

## 3. Index des évolutions

| Ouverture | Évolution | Périmètre | Statut | Documents |
|---|---|---|---|---|
| 2026-10 | [Audit de la partie web](2026-10-01-audit-web/01-plan.md) | `volumes/web/**`, `src/api/**`, export de données, Docker. Est à l'origine des 43 commits de `feat/optimisation-seo` | **Clôturée** — soldée par les PR #15→#18 et la branche `feat/optimisation-seo` (non fusionnée) | [plan](2026-10-01-audit-web/01-plan.md) · [avancement](2026-10-01-audit-web/02-avancement.md) |
| 2026-10 | [Sécurité, SEO, performance, qualité](2026-10-02-securite-seo-performance/01-plan.md) | Audit transverse du dépôt : 63 findings sur 6 familles (`SEC` 17 · `PERF` 12 · `SEO` 13 · `QUAL` 14 · `A11Y` 4 · `RGPD` 3), 3,75 j estimés | **Clôturée** — 100% réalisé et fusionné sur `main` (PR #21) | [plan](2026-10-02-securite-seo-performance/01-plan.md) · [avancement](2026-10-02-securite-seo-performance/02-avancement.md) |
| 2026-10 | [Refonte Responsive & Ergonomie Mobile](2026-10-03-responsive-mobile/01-plan.md) | Refonte affichage smartphone (GP8 Pro, iPhone...), suppression des débordements, saisie mobile, PageSpeed Mobile & Bureau 100/100 + 4/4 ARD, régénération auto SEO/ARD au démarrage. Zéro impact bureau. | **En cours** — 100% réalisé sur `feat/responsive-mobile` (12/12 findings + PageSpeed 100/100 Mobile & Bureau validés, PR #22) | [plan](2026-10-03-responsive-mobile/01-plan.md) · [avancement](2026-10-03-responsive-mobile/02-avancement.md) |
| 2026-10 | [Titres « Solution Cémantix du <date> » & longue traîne datée](2026-10-04-seo-titres-archives/01-plan.md) | Libellés des pages d'archives `/puzzles/AAAA-MM-JJ/` (`<title>`, `<h1>`, Open Graph, JSON-LD, description), textes d'ancre de l'index `/puzzles/`, contrat ISO de `sitemap.xml`, découvrabilité agents IA (`llms.txt`, `llms.md`, `agent-skills.md`, `.well-known/`). 4 findings (`SEO-13` à `SEO-16`), aucun changement d'URL. | **En cours** — 4/4 réalisé sur `feat/seo-titre-archives-solution` (22 tests SEO/agents verts, `tools/check_seo.py` vert) | [plan](2026-10-04-seo-titres-archives/01-plan.md) · [avancement](2026-10-04-seo-titres-archives/02-avancement.md) |

| 2026-10 | [Percée sur la tendance Google : « mot du jour », « indice », « synonyme »](2026-10-05-seo-tendance-mot-du-jour/01-plan.md) | Pages hub générées `/mot-du-jour/` et `/methode/`, recentrage du hub `/puzzles/`, un `<h1>` descriptif par page applicative, FAQ et maillage interne alignés sur la tendance Google (10 requêtes liées, `mot du jour` dans 5 d'entre elles). Trouve `SEO-17` à `SEO-21`, aucune URL existante modifiée. | **En cours** — 5/5 réalisé sur `feat/seo-titre-archives-solution` (branche commune avec l'évolution « Titres d'archives », un seul PR à ouvrir pour les deux) : 46 tests SEO/agents verts, `tools/check_seo.py` et `tools/build_css_bundles.py --check` verts | [plan](2026-10-05-seo-tendance-mot-du-jour/01-plan.md) · [avancement](2026-10-05-seo-tendance-mot-du-jour/02-avancement.md) |
| 2026-10 | [Défier le bot IA](2026-10-06-defier-le-bot/01-plan.md) | Nouveau mode public : le joueur propose un mot, le worker RAG le résout en direct (file PostgreSQL, SSE, quota 10/h + whitelist admin). 30 actions sur 3 familles (`DEFI` 18 · `SEC` 9 · `QUAL` 3), 2,25 j estimés | **En cours** — 29/30 faites sur `feat/bot_defy`, reste la recette `QUAL-22` | [plan](2026-10-06-defier-le-bot/01-plan.md) · [avancement](2026-10-06-defier-le-bot/02-avancement.md) |

Les deux évolutions se croisent sans s'opposer : la première a produit les correctifs web, la seconde
a **re-vérifié dans le code** ce qu'elles annonçaient et en a repris l'évaluation. Là où elles
divergent, c'est `2026-10-02-securite-seo-performance/02-avancement.md` qui fait foi, parce que chaque
statut y est appuyé par une preuve mesurée (`git ls-tree`, `grep` sur la branche, sortie de commande).
