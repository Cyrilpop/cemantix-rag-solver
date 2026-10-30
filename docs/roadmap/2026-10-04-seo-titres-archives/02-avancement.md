# 📊 Avancement — Titres « Solution Cémantix du <date> » & longue traîne datée

> **Évolution :** [2026-10 · Titres d'archives SEO](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Branche :** `feat/seo-titre-archives-solution` (base `main` @ `384079b`)
> **Dernière mise à jour :** 30/10/2026

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`SEO-13` à `SEO-16`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.** Un commit,
   ou son message, ne vaut pas preuve.
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait` (vérification exécutée),
   `🚫 Renoncé` (l'ID reste réservé).
4. Chaque changement de statut s'accompagne d'une ligne dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **4** | 1 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **4** | **1** |

Répartition par criticité : 🔴 `SEO-15` (contrat ISO du sitemap) · 🟠 `SEO-13` (titre & description
des archives) · 🟡 `SEO-14` (maillage de l'index), `SEO-16` (découvrabilité agents IA).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **SEO-13** | 🟠 | `<title>`, `<h1>`, Open Graph, JSON-LD et description d'archive sur « Solution Cémantix du <date française> » | `✅ Fait` | `ARCHIVE_TITLE_PREFIX` + `archive_title()` dans `src/services/seo.py` ; titre mesuré à **42 caractères** (ancien : 85) ; `tests/test_seo_archives.py` `TestPageArchive` vert — `<title>`, `<h1>`, `og:title`, `twitter:title`, `headline` et fil d'Ariane tous égaux à « Solution Cémantix du lundi 26 octobre 2026 » |
| **SEO-14** | 🟡 | Index `/puzzles/` : titre, `h1`, JSON-LD `CollectionPage` et ancres datées | `✅ Fait` | Titre « Solution Cémantix : archives de tous les puzzles résolus par l'IA », `h1` aligné ; publication de contrôle sur historique jetable : ancres relevées `Solution Cémantix du lundi 26 octobre 2026` et `Solution Cémantix du dimanche 25 octobre 2026` (`TestIndexDesArchives` vert, 3 tests) |
| **SEO-15** | 🔴 | `sitemap.xml` : aucune date française, `<loc>` et `<lastmod>` en ISO | `✅ Fait` | Générateur inchangé ; `TestSitemapGardeLeFormatIso` vert (2 tests) ; `grep -c octobre volumes/web/sitemap.xml` → `0` ; `<loc>` relevés : `/puzzles/2026-10-27/`, `/puzzles/2026-10-26/`, `/puzzles/2026-10-25/` |
| **SEO-16** | 🟡 | `llms.txt`, `llms.md`, `agent-skills.md`, `agent-card.json`, catalogue ARD | `✅ Fait` | Bloc `AGENT-DYNAMIC` régénéré (`refresh_agent_docs` → 2 fichiers), manifestes régénérés (`publish_ard_manifests` → 3 fichiers) et comparés à leur générateur : identiques ; `python tools/check_seo.py` → `[OK] Audit agentique reussi` ; `tests/test_docs_agent.py` vert (7 tests, idempotence et absence de date figée incluses) |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 30/10/2026 | SEO-13, SEO-14, SEO-15, SEO-16 | Implémentation sur `feat/seo-titre-archives-solution` (commit `feat(seo): titre des archives "Solution Cemantix du <date en francais>"`). Suite `tests/test_seo_archives.py` : **15 tests verts** ; suite conjointe avec `tests/test_docs_agent.py` : **22 tests verts** ; `python tools/check_seo.py` : `[OK]` sur 4 pages principales + audit agentique ; `python tools/check_docs.py` : `=== OK ===` (66 suivis de l'évolution précédente toujours cohérents). |
| 30/10/2026 | SEO-13 | Correction attrapée par le test dès la première exécution : la description produisait « Solution du **Solution Cémantix** du… ». Réécriture au profit de `{titre} : le mot secret et les N mots les plus proches…`, longueur plafonnée à 175 caractères par test. |
| 30/10/2026 | SEO-16 | Nettoyage d'un exemple d'URL daté et figé (`/puzzles/2026-10-26/`) dans `llms.md`, remplacé par la description du contrat titre français / URL ISO — un exemple figé vieillit en 404 pour un agent. |

---

## 4. Environnement de vérification & limites

- Vérifications exécutées localement sous **Python 3.14** avec les seuls modules standards : la
  suite SEO (`src/services/seo.py`) ne dépend d'aucune dépendance lourde, les tests
  `test_seo_archives.py` et `test_docs_agent.py` sont donc exécutables hors conteneur. La suite
  complète (`numpy`, `requests`, `chromadb`, `psycopg`) reste exécutée par le job `tests` de la CI
  GitHub Actions, non reproductible sur ce poste sans réseau.
- Les pages d'archive et `sitemap.xml` sont **ignorés par git** (`.gitignore`) : ils sont régénérés
  par `publish_seo_pages()` au démon de minuit et par `ensure_seo_published()` au démarrage des
  conteneurs. La recette de production est donc un redémarrage de `cemantix_web`, puis la lecture
  de `volumes/web/puzzles/<date>/index.html`.
- Aucun changement d'URL, donc aucune redirection ni regénération de la Search Console à prévoir ;
  le nouveau titre est repris au prochain re- crawl de chaque page.
