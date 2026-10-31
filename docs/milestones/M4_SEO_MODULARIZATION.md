# M4 — Modularisation Sécurisée du Sous-Système SEO & Réduction de Contexte Agent

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Date :** 31 octobre 2026  
**Branche :** `feature/audit-hey-you`  
**Statut :** Complété — Zéro régression, 100 % Rétrocompatible, 248 tests passants (17 nouveaux tests)  

---

## 1. Résumé Exécutif

Le jalon **M4** a procédé à la modularisation méthodique et sécurisée du « God Module » [`src/services/seo.py`](../../src/services/seo.py) (initialement 1 692 lignes et 76 Ko cumulant formats de dates, injection CSS inline, gabarits Schema.org, pages d'archives, pagination, pages hub éditoriales, génération du sitemap XML, manifestes agentiques ARD/A2A, pré-rendu HTML du tableau de bord et orchestration de publication multi-conteneurs).

### Objectifs Atteints
1. **Élimination du God Module sans réécriture algorithmique** : découpage en 5 sous-modules étanches, hautement cohésifs et inférieurs à 450 lignes chacun.
2. **Réduction drastique de la consommation de contexte IA** : le fichier central `seo.py` passe de 1 692 lignes (~19 000 tokens) à 250 lignes (~3 100 tokens), soit **-85 % de volume de contexte**. Une intervention ciblée sur le sitemap ou les archives ne charge plus que 95 à 240 lignes.
3. **Parité déterministe bit à bit** : les sorties HTML, XML (`sitemap.xml`) et JSON (`ai-catalog.json`, `ard.json`, `agent-card.json`) sont strictement identiques.
4. **Rétrocompatibilité ascendante absolue** : l'intégralité des symboles publics et internes est ré-exportée via `seo.py` et exposée dans `__all__`, préservant l'identité stricte d'objet (`assertIs`) et les contrats de monkeypatching existants (`mock.patch("src.services.seo.ensure_seo_published")`).
5. **Sanctuarisation par les tests** : création de 17 nouveaux tests déterministes portant la suite globale de **231 à 248 tests unitaires** (100 % passants en 8,35 s sous conteneur Docker Python 3.12).

---

## 2. Phase 1 — Audit & Caractérisation Déterministe

Avant toute modification du code de production, une cartographie exhaustive de tous les appelants de `src.services.seo` a été établie :
- `src/api/server.py` : invocation au démarrage de `ensure_seo_published()` en mode persistant.
- `src/services/daemon.py` : synchronisation nocturne et au démarrage via `ensure_seo_published()`.
- `src/services/web.py` : export web appelant `publish_seo_pages` et utilisant `WEB_ROOT`.
- `tools/check_seo.py` : audit qualité SEO important `build_mot_du_jour_page` et `build_methode_page`.
- Suites de tests historiques : `test_seo_startup.py`, `test_seo_archives.py`, `test_seo_hubs.py`, `test_docs_agent.py`, `test_responsive.py`.

### Harnais de Caractérisation ([`tests/test_seo_characterization.py`](../../tests/test_seo_characterization.py))
12 tests déterministes ont été créés pour figer l'ensemble des comportements attendus :
- Formatage des dates longues en français et durées lisibles (`test_formatters_deterministic_output`).
- Structure HTML5 complète, métadonnées OpenGraph/Twitter, balisage Schema.org et fil d'Ariane (`test_archive_page_structure_and_anti_spoiler`).
- **Invariant anti-spoiler strict** : le mot secret ne doit jamais apparaître en dehors de la balise `<details class="reveal">`, et le placeholder masqué `"••••••••"` est exclu des tableaux.
- **Protection anti-thin-content** : balise `<meta name="robots" content="noindex, follow">` automatique pour tout puzzle non résolu sans indices explorés (`test_archive_page_unsolved_is_noindex`).
- Pagination canonique et liens relatifs inter-pages (`test_archives_index_pagination_structure`).
- Pages hub éditoriales générées avec ou sans historique (`test_mot_du_jour_page_with_and_without_entry`, `test_methode_page_structure`).
- Format strict du sitemap XML ISO 8601 (`test_sitemap_xml_protocol_compliance`).
- Schémas JSON ARD et Agent-Card valides (`test_ard_manifest_and_agent_card_valid_json`).
- Résilience aux entrées malformées et limites (`test_malformed_and_boundary_entries_handled_safely`).
- Publication atomique multi-fichiers et pré-rendu du tableau de bord sur système de fichiers temporaire (`TestSeoFilesystemPublication`).

---

## 3. Phase 2 — Découpage & Architecture Modulaire

Le sous-système SEO est désormais structuré en composants spécialisés :

```
src/services/
├── seo_templates.py   # Gabarits HTML, helpers de formatage, tokens CSS & Schema.org (378 lignes)
├── seo_archives.py    # Pages d'archives /puzzles/<date>/ et index paginé /puzzles/ (238 lignes)
├── seo_hubs.py        # Hubs /mot-du-jour/ et /methode/ avec FAQ & HowTo Schema.org (437 lignes)
├── seo_sitemap.py     # Sitemap XML conforme et écriture atomique multi-conteneurs (94 lignes)
├── seo_agents.py      # Manifestes ARD/A2A (.well-known/) et docs agentiques llms.txt (219 lignes)
└── seo.py [ORCHESTRE] # Pré-rendu dashboard, publish_seo_pages, ensure_seo_published & ré-exports (254 lignes)
```

### 3.1 [`src/services/seo_templates.py`](../../src/services/seo_templates.py) — Gabarits & Mise en Forme
- **Responsabilités :**
  - Constantes de navigation (`NAV_LINKS`), métadonnées et préfixes de dates français (`_MONTHS_FR`, `_WEEKDAYS_FR`).
  - Formatage déterministe : `parse_puzzle_date`, `format_date_fr`, `archive_title`, `archive_anchor`, `hub_url`, `format_duration_fr`, `archive_url`.
  - Helpers de cheminement relatif : `_join`, `_rel`, `_rel_index`.
  - Chargement et inlining CSS : `_load_style_tokens` (extraction `:root` et thème clair depuis `variables.css`), `_load_puzzle_css`.
  - Gabarit HTML unifié : `render_page(...)` intégrant responsive meta, OpenGraph, JSON-LD et CSS inline.
  - Composants partagés : `_json_ld_block`, `_tier_class` (paliers thermiques), `_clue_rows` (tableau des indices).

### 3.2 [`src/services/seo_archives.py`](../../src/services/seo_archives.py) — Pages d'Archives Quotidiennes & Index
- **Responsabilités :**
  - `build_archive_page(entry, older, newer)` : page d'archive d'un puzzle résolu (`/puzzles/AAAA-MM-JJ/`) avec fil d'Ariane, micro-données `Article` et `BreadcrumbList`, tableau des scores, solution masquée sous `<details>` et pagination temporelle (liens `rel="prev"` / `rel="next"`). Règle anti-thin-content automatique (`noindex` si non résolu et sans indices).
  - `build_archives_index_page(entries, page, total_pages)` : index paginé des archives (`/puzzles/` et `/puzzles/page/N/`) avec micro-données `CollectionPage` et pagination numérique.

### 3.3 [`src/services/seo_hubs.py`](../../src/services/seo_hubs.py) — Hubs Thématiques Rendus Serveur
- **Responsabilités :**
  - `build_mot_du_jour_page(entry, entries)` : page `/mot-du-jour/` ciblant la tendance Google avec indices, solution dépliable, historique récent et FAQ Schema.org (`FAQPage`).
  - `build_methode_page()` : guide éditorial `/methode/` sur le thermomètre sémantique, les pour mille, les synonymes et antonymes avec balisage `HowTo` et `FAQPage`.

### 3.4 [`src/services/seo_sitemap.py`](../../src/services/seo_sitemap.py) — Sitemap XML & Écriture Atomique
- **Responsabilités :**
  - `build_sitemap(entries, generated_at)` : génération de `sitemap.xml` conforme au protocole sitemaps.org avec dates ISO 8601 réelles (`lastmod`), fréquences et priorités adaptées.
  - `_write_file(path, content)` : écriture atomique sur fichier temporaire masqué avec `replace`, garantissant l'intégrité même lors d'accès concurrents multi-conteneurs (`cemantix_web` / `cemantix_worker`).

### 3.5 [`src/services/seo_agents.py`](../../src/services/seo_agents.py) — Découverte Agentique & ARD
- **Responsabilités :**
  - `build_ard_manifest(origin)` : catalogue ARD (`ai-catalog.json`, `ard.json`) décrivant l'API et les compétences du solveur.
  - `build_agent_card(origin)` : carte d'agent A2A (`agent-card.json`) pour interactions inter-agents.
  - `publish_ard_manifests(web_root)` : génération atomique des 3 manifestes dans `.well-known/`.
  - `refresh_agent_docs(entries, web_root)` : mise à jour idempotente des sections dynamiques délimitées par `AGENT-DYNAMIC` dans `llms.txt` et `agent-skills.md`.

### 3.6 [`src/services/seo.py`](../../src/services/seo.py) — Orchestrateur & Ré-Export Rétrocompatible
- **Responsabilités :**
  - `prerender_dashboard(entry, web_root)` : injection idempotente du résumé du jour dans `index.html` via balises `data-seo`.
  - `publish_seo_pages(history, generated_at, web_root)` : chaîne orchestrant la publication de l'ensemble des artefacts (sitemap, manifestes ARD, archives, index, hubs, pré-rendu, docs agent).
  - `ensure_seo_published(web_root)` : point d'entrée au démarrage des conteneurs avec chargement résilient de l'historique et repli gracieux.
  - **Ré-export universel** : exposition de tous les symboles des sous-modules via `__all__`.

---

## 4. Phase 3 — Rétrocompatibilité, Monkeypatching & Non-Régression

Un module de validation dédié ([`tests/test_seo_backward_compat.py`](../../tests/test_seo_backward_compat.py)) a été mis en place pour garantir l'absence totale de régression :
1. **Identité stricte des objets (`assertIs`)** : validation que chaque fonction et constante ré-exportée depuis `seo.py` pointe vers la même référence mémoire que le sous-module extrait.
2. **Exhaustivité du contrat `__all__`** : contrôle automatisé vérifiant que chaque symbole déclaré dans `__all__` est présent sur le module.
3. **Monkeypatching transparent** :
   - Le patch de `src.services.seo.publish_seo_pages` est immédiatement honoré par `ensure_seo_published()`.
   - Le patch de `src.services.seo.ensure_seo_published` intercepte les appels des contrôleurs (`server.py`, `daemon.py`).
4. **Parité bit à bit** : comparaison directe prouvant que `seo.build_archive_page(...) == seo_archives.build_archive_page(...)`, et idem pour l'index, les hubs, le sitemap et les manifestes ARD.

---

## 5. Phase 4 — Mesure de l'Efficience de Contexte Agent

### Comparatif d'Empreinte Source

| Composant | Lignes Avant M4 | Lignes Après M4 | Octets | Économie de Lignes | Rôle Unique |
|---|---:|---:|---:|---:|---|
| `seo_templates.py` | — | 378 | 12,4 Ko | *Nouveau* | Gabarits HTML, helpers de dates, tokens CSS |
| `seo_archives.py` | — | 238 | 8,9 Ko | *Nouveau* | Pages `/puzzles/<date>/` et index `/puzzles/` |
| `seo_hubs.py` | — | 437 | 18,7 Ko | *Nouveau* | Pages `/mot-du-jour/` et `/methode/` |
| `seo_sitemap.py` | — | 94 | 2,8 Ko | *Nouveau* | Sitemap XML et écriture atomique |
| `seo_agents.py` | — | 219 | 8,2 Ko | *Nouveau* | Manifestes ARD/A2A et `llms.txt` |
| `seo.py` | **1 692** | **254** | **11,8 Ko** | **-85.0 %** | Orchestration, pré-rendu et ré-exports |

### Bénéfices pour la Navigation Contextuelle des Agents IA
1. **Élimination de la saturation de contexte** : un agent IA travaillant sur la génération du sitemap n'a plus à charger les 1 692 lignes du fichier monolithique. Il lui suffit d'inspecter `src/services/seo_sitemap.py` (94 lignes, ~700 tokens), soit un gain de **-96 %** sur cette tâche.
2. **Localisation instantanée des symboles** : `tools/agent_find.py` localise précisément chaque fonction dans son module dédié sans ambiguïté.
3. **Respect du protocole M0.1** : le benchmark automatisé (`tools/benchmark_agent_context.py`) confirme une économie moyenne de **-92.9 %** de tokens par rapport à une approche naïve.

---

## 6. Commandes de Validation Opérationnelle

Les 4 contrôles de conformité inviolables d'`AGENTS.md` ont été exécutés avec succès :

```bash
# 1. Suite de tests unitaires (248 tests attendus, 0 échec)
docker run --rm -v $(pwd):/app -v /tmp/pip-cache:/root/.cache/pip -w /app python:3.12-slim sh -c \
  "pip install -r requirements.txt && python -m unittest discover -s tests -v"
# Résultat : Ran 248 tests in 8.352s — OK (0 échec, 0 erreur)

# 2. Cohérence documentaire & roadmap
python tools/check_docs.py
# Résultat : === OK === (compteurs et liens vérifiés)

# 3. Contrôle du balisage SEO & métadonnées
python tools/check_seo.py
# Résultat : [OK] Audit SEO réussi sur 5 pages, pages hub et catalogue ARD

# 4. Contrôle des bundles CSS
python tools/build_css_bundles.py --check
# Résultat : ✔ 6 bundles dist et CSS critique inline 100 % à jour
```
