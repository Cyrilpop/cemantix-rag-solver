# 📊 Avancement — Percer sur la tendance Google : « mot du jour », « indice », « synonyme »

> **Évolution :** [2026-10 · Tendance Google](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Branche :** `feat/seo-titre-archives-solution` (base `main` @ `384079b`) — branche commune
> aux deux quick wins SEO, `SEO-13` à `SEO-16` puis `SEO-17` à `SEO-21`.
> **Dernière mise à jour :** 30/10/2026

---

## 0. Règles de tenue

1. Une ligne = un finding du plan (`SEO-17` à `SEO-21`), ID jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte** ; un
   commit ou son message ne vaut pas preuve.
3. Statuts : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut est journalisé au §3 avec sa preuve mesurée.

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **5** | 1 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **5** | **1** |

Répartition par criticité : 🔴 `SEO-17` (hub mot du jour, 5 requêtes sur 10) · 🟠 `SEO-18`
(guide des indices), `SEO-19` (hub archives recentré), `SEO-20` (`<h1>` par page) · 🟡 `SEO-21`
(FAQ et maillage).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **SEO-17** | 🔴 | Page hub `/mot-du-jour/` rendue côté serveur, prioritaire dans le sitemap | `✅ Fait` | `build_mot_du_jour_page()` ; titre et `<h1>` relevés sur la page rendue : `Mot du jour Cémantix du lundi 26 octobre 2026 : indices et solution` ; 430 mots visibles avec un historique d'un coup (dont 5× « mot du jour »), table des indices, solution sous `<details>` (le mot n'apparaît **qu'une fois** dans le document), `FAQPage` de 4 questions ; sitemap : `<priority>0.95</priority>`, `<changefreq>daily</changefreq>`, `<lastmod>2026-10-26</lastmod>` |
| **SEO-18** | 🟠 | Page hub `/methode/`, guide des indices et des synonymes | `✅ Fait` | `build_methode_page()` ; **1000 mots visibles**, 10× « indice », 13× « synonyme », « pour mille » et « 1000 ‰ » présents ; `HowTo` de 5 étapes + `FAQPage` de 4 questions, chaque `name` d'étape retrouvé dans le texte clair (test dédié) |
| **SEO-19** | 🟠 | Hub `/puzzles/` recentré sur le cluster dominant et ancres enrichies | `✅ Fait` | `<title>` « Cémantix du jour : mot du jour, indices et solutions par date », `<h1>` « Archives Cémantix du jour : le mot du jour, ses indices et sa solution » ; ancres rendues `Indices et solution du Cémantix du lundi 26 octobre 2026` et `… du dimanche 25 octobre 2026` ; `tests/test_seo_archives.py` **17 tests verts** |
| **SEO-20** | 🟠 | Un `<h1>` descriptif par page applicative, marque hors `<h1>` | `✅ Fait` | `<h1>` relevés — accueil « Cémantix du jour : indices, mot du jour et solution », `/play/` « Jouer à Cémantix en ligne : mode illimité et défi du jour », `/battle/` « Cémantix Battle : jouez contre l'IA en duel tour par tour », `/multi/` « Cémantix multijoueur : duel 1v1 entre amis au tour par tour » : **un seul `<h1>` par page, quatre uniques** ; marque en `<span class="brand-title">` ; `tools/build_css_bundles.py --check` → 6 bundles et 4 CSS critiques « à jour » |
| **SEO-21** | 🟡 | FAQ alignée sur la tendance et maillage interne croisé | `✅ Fait` | `FAQPage` de l'accueil porté de 5 à **8 questions** (mot du jour, lecture des indices, synonymes), texte identique en accordéon et en JSON-LD (test) ; liens `mot-du-jour/` et `methode/` présents sur les 4 pages applicatives, dans les archives, dans les hubs et dans le pré-rendu quotidien (`resume-title`, `resume-link`) |
---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 30/10/2026 | — | Cadrage à partir de la tendance Google fournie : 5 requêtes sur 10 sur « mot du jour », « indice » en #1 et #2, « solution » dernière (+8 %). Le quick win `SEO-13` est conservé mais ne titre plus le hub `/puzzles/` (`SEO-19`). |
| 30/10/2026 | SEO-17, SEO-18 | Implémentation des deux hubs, publication même sur historique vide, entrées de sitemap ; `publish_seo_pages()` renvoie `{'archives': 2, 'index_pages': 1, 'hub_pages': 2, 'ard_manifests': 3}` sur un historique de contrôle. |
| 30/10/2026 | SEO-17, SEO-18 | **Régression attrapée par les tests** : les hubs, de profondeur 1, utilisaient `_rel()` (`../../`) réservé aux archives (profondeur 2) — trois tests rouges, liens internes cassés. Corrigé en `_rel_index()` ; le contrôle de résolution des liens entre pages générées (4 pages, 31 liens internes) ne remonte plus que les 4 pages applicatives, absentes du répertoire jetable. |
| 30/10/2026 | SEO-20, SEO-21 | `<h1>` descriptifs + intro maillée sur les 4 pages, marque en `.brand-title`, CSS et bundles régénérés ; deux pages (`/battle/`, `/multi/`) oubliées sans lien vers `/mot-du-jour/`, rattrapées par `test_chaque_page_maille_vers_les_hubs`. |
| 30/10/2026 | SEO-17 → SEO-21 | Recette : **46 tests SEO/agents verts** (`test_seo_archives`, `test_seo_hubs`, `test_docs_agent`), `tools/check_seo.py` vert (4 pages + 2 gabarits générés + audit agentique), `tools/check_docs.py` `=== OK ===`, `tools/build_css_bundles.py --check` vert. |

---

## 4. Environnement de vérification, limites et prochaines actions

- Vérifications exécutées sous **Python 3.14** avec la seule bibliothèque standard : la chaîne
  SEO (`src/services/seo.py`) n'importe aucune dépendance lourde. Le poste de développement n'a
  pas d'accès réseau pour installer `requirements.txt`, donc `local/run_seo_tests.py` charge
  `src/config.py` et `src/services/seo.py` sans exécuter `src/__init__.py` (qui tire `numpy`,
  `requests` et `urllib3` via le moteur) et lance les trois suites concernées :
  `py local/run_seo_tests.py` → **46 tests verts**. La suite complète (`numpy`, `requests`,
  `chromadb`, `psycopg`) n'est pas exécutable sur ce poste et reste couverte par le job `tests`
  de la CI.
- `tools/check_seo.py` audite les gabarits générés en mémoire ; sur un poste sans
  `requirements.txt`, il l'annonce (`[i] Pages générées non auditées`) sans faire échouer le
  contrôle — en CI, l'audit est effectif.
- **Limite de la donnée :** une tendance Google donne des variations relatives, ni volumes
  absolus ni difficulté SERP. Le pari éditorial (formes combinées + contenu informationnel) se
  valide par la Search Console, 4 à 8 semaines après mise en ligne.
- **Prochaines actions** :
  1. Recette visuelle des 4 pages applicatives à 360 / 412 / 768 px (phase 5 du plan) : le
     `<h1 class="page-heading">` et son intro décalent la ligne de flottaison du tableau de bord.
  2. Publier, puis demander l'indexation de `/mot-du-jour/` et `/methode/` dans la Search
     Console et suivre l'impression sur les requêtes combinées.
  3. Surveiller la richesse de `/mot-du-jour/` au fil de l'historique : 430 mots avec un seul
     puzzle publié, elle monte avec les dix indices et les archives récentes.

