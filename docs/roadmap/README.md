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
└── 2026-10-securite-seo-performance/  <- une evolution = un dossier
    ├── 01-plan.md                     <- QUOI faire (reference de conception)
    └── 02-avancement.md               <- OU on en est (tableaux de statut)
```

### 1.2 Nom des dossiers

`AAAA-MM-slug` en **minuscules ASCII**, mots séparés par des tirets, sans accent.

| Règle | Raison |
|---|---|
| Préfixe `AAAA-MM` (mois d'ouverture) | tri chronologique naturel dans l'explorateur, `ls` et GitHub ; évite deux slugs identiques à six mois d'écart |
| Slug **thématique**, pas technique | on retrouve une évolution par son intention (« securite-seo-performance »), pas par le nom d'un fichier touché |
| Jamais de numéro séquentiel seul | `evo-01` ne dit rien ; la date dans le nom suffit à ordonner |
| Nom **figé à l'ouverture** | le dossier devient une référence stable des `CHANGELOG.md` et des messages de commit |

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
# 1. Creer le dossier au nom de l'evolution (AAAA-MM-slug)
mkdir docs/roadmap/2026-12-slug-de-levaluation

# 2. Reprendre la structure du dossier existant comme gabarit de mise en forme
cp docs/roadmap/2026-10-securite-seo-performance/01-plan.md \
   docs/roadmap/2026-12-slug-de-levaluation/01-plan.md
# puis vider 01-plan.md de son contenu et relancer la methodologie du §0 du modele

# 3. Declarer l'evolution dans l'index ci-dessous (statut "En cours")
```

Le contenu de `01-plan.md` du dossier existant sert de **gabarit de forme** : sa section
« Méthodologie & périmètre » et ses en-têtes de tableau sont la convention à réutiliser.

---

## 3. Index des évolutions

| Ouverture | Évolution | Périmètre | Statut | Documents |
|---|---|---|---|---|
| 2026-10 | [Sécurité, SEO, performance, qualité](2026-10-securite-seo-performance/01-plan.md) | Audit transverse du dépôt : 63 findings sur 6 familles (`SEC` 17 · `PERF` 12 · `SEO` 13 · `QUAL` 14 · `A11Y` 4 · `RGPD` 3), 3,75 j estimés | **En cours** — 1 fermé, 11 en attente de fusion | [plan](2026-10-securite-seo-performance/01-plan.md) · [avancement](2026-10-securite-seo-performance/02-avancement.md) |

**Avant 2026-10**, les travaux d'audit n'ont pas suivi cette convention : l'audit web du 26/10/2026
vit dans `.idea/PLAN_WEB_AUDIT.md` (hors git, non versionné). Ses conclusions ont été absorbées par
l'évolution 2026-10, qui a re-vérifié point par point ce qui était réellement fusionné.
