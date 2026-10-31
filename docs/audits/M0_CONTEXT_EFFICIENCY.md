# M0 — AI-Agent Context Efficiency Audit

**Date :** 30 octobre 2026  
**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Statut :** Livrable M0 (Audit-First — Efficacité du Contexte Agent)  

---

## 1. Objectif & Méthodologie

Ce document évalue l'efficacité avec laquelle des agents de codage IA (agents autonomes LLM, assistants pair-programming) peuvent appréhender, naviguer et modifier ce dépôt sans saturer leur fenêtre de contexte ni subir de dégradation de raisonnement (*lost-in-the-middle*, hallucinations d'arborescence, coûts de tokens superflus).

### Méthode de Mesure des Tokens
- **Mesures réelles :** Nombre d'octets UTF-8, lignes et mots dénombrés précisément sur le système de fichiers.
- **Estimation de tokens :** Ratio conservateur calibré pour un mélange de code Python/JS/HTML et de prose technique française (1 token ≈ 3,8 à 4,1 caractères UTF-8, soit `longueur_caractères / 4`).
- **Distinction stricte :** Toutes les colonnes de ce document distinguent les données brutes mesurées des estimations de tokens résultantes.

---

## 2. Cartographie de la Consommation de Contexte

### 2.1 Les Plus Grands Consommateurs de Contexte du Dépôt

Le tableau ci-dessous classe les fichiers sources et documentaires selon le coût de chargement complet dans le contexte d'un agent IA :

| Fichier | Lignes (Mesuré) | Poids (Octets mesurés) | Mots (Mesuré) | Tokens Estimés (~char/4) | Statut & Pertinence pour l'Agent |
|---|---:|---:|---:|---:|---|
| `cemantix_data/lexique_fr.txt` | 46 219 | 465 967 o | 46 219 | **~116 500** | **Donnée lexicale brute**. Ne doit JAMAIS être lue en intégralité par un agent. |
| `CHANGELOG.md` | 484 | 77 062 o | 10 609 | **~18 770** | **Historique cumulatif**. Trop lourd pour être chargé au démarrage. |
| `src/services/seo.py` | 1 692 | 76 107 o | 7 746 | **~18 776** | **God Module**. Chargement lourd même pour une retouche minime de balise SEO. |
| `volumes/web/multi/index.html` | 583 | 72 072 o | 2 842 | **~17 926** | **HTML avec CSS inliné**. Chargé inutilement lors de retouches frontend. |
| `volumes/web/battle/index.html` | 581 | 69 438 o | 2 719 | **~17 272** | **HTML avec CSS inliné**. |
| `volumes/web/index.html` | 696 | 68 740 o | 3 552 | **~17 045** | **HTML avec CSS critique + JSON-LD**. |
| `README.md` | 898 | 61 737 o | 8 066 | **~14 628** | **Documentation monolithique**. Trop verbeux pour servir d'instructions agent. |
| `docs/roadmap/2026-10-02-.../01-plan.md` | 552 | 54 516 o | 6 789 | **~13 600** | **Roadmap historique**. Périmée, context-hog si explorée par récursion. |
| `volumes/web/css/dist/multi.css` | 530 | 53 029 o | 2 541 | **~13 250** | **Artefact généré dist/**. Ne devrait jamais être lu ni édité manuellement. |
| `volumes/web/css/dist/battle.css` | 516 | 52 262 o | 2 503 | **~13 060** | **Artefact généré dist/**. |
| `volumes/web/play/index.html` | 343 | 43 686 o | 1 894 | **~10 920** | **HTML avec CSS inliné**. |
| `volumes/web/css/dist/dashboard.css` | 468 | 43 447 o | 2 089 | **~10 860** | **Artefact généré dist/**. |
| `volumes/web/defi/index.html` | 312 | 42 620 o | 1 645 | **~10 655** | **HTML avec CSS inliné**. |
| `src/cli/modes.py` | 849 | 39 813 o | 4 054 | **~9 814** | **Logique CLI multiple**. Mélange 4 modes distincts. |
| `docs/roadmap/2026-10-02-.../02-avancement.md`| 510 | 39 556 o | 3 890 | **~9 889** | **Historique de suivi**. |
| `volumes/web/css/dist/play.css` | 421 | 38 660 o | 1 856 | **~9 665** | **Artefact généré dist/**. |
| `volumes/web/js/multi.js` | 1 064 | 37 872 o | 3 655 | **~9 409** | **Script multijoueur volumineux**. |
| `src/engine/solvers.py` | 589 | 26 721 o | 2 750 | **~6 600** | **Solveur RAG**. Dense en maths et intégration LLM. |
| `volumes/web/js/battle.js` | 808 | 26 347 o | 2 521 | **~6 547** | **Script battle**. |
| `volumes/web/js/game.js` | 695 | 26 096 o | 2 376 | **~6 494** | **Script solo**. |
| **SOUS-TOTAL (Top 20)** | **58 480** | **1 352 820 o** | **117 997** | **~333 460** | *(Représente plus de 55 % du volume total du dépôt)* |

---

## 3. Analyse des Goulots d'Étranglement Contextuels

### 3.1 La "Taxe de Documentation" (README + CHANGELOG)

Lorsqu'un agent IA démarre sur le dépôt sans instruction spécifique, les conventions d'agents (ou les prompts utilisateur par défaut) le poussent à inspecter `README.md` et `CHANGELOG.md`.

- **Coût mesuré :** 898 + 484 = 1 382 lignes, 138 799 octets, 18 675 mots.
- **Tokens estimés :** **~33 400 tokens**.
- **Contenu superflu pour un agent :**
  - Des dizaines de tableaux ASCII reproduisant des écrans de terminal.
  - De longues explications de marketing/SEO destinées aux moteurs de recherche.
  - La liste détaillée de toutes les versions historiques dans le changelog.
- **Conséquence :** L'agent démarre sa tâche avec 33 000 tokens consommés inutilement, réduisant sa capacité de travail en mémoire courte et augmentant le risque d'oubli d'instructions.

### 3.2 L'Impact des Fichiers Compilés et Générés (CSS Dist & Inliné)

- Le répertoire `volumes/web/css/dist/` contient 6 fichiers CSS compilés totalisant **214 050 octets (~52 000 tokens)**.
- Les fichiers HTML contiennent chacun entre 30 Ko et 40 Ko de CSS minifié inliné dans `<style id="critical-css">`.
- **Problème :** Lorsqu'un agent est sollicité pour ajouter une balise dans `volumes/web/index.html` ou modifier le DOM de `battle/index.html`, il doit lire un fichier de ~70 Ko dont plus de la moitié est du CSS minifié incompréhensible pour du raisonnement sémantique.
- **Risque :** Risque très élevé d'altération accidentelle du bundle critique inliné lors des opérations d'édition par patch regex ou remplacement de chaîne.

### 3.3 Absence d'Instructions pour Agents Développeurs

- Le répertoire `volumes/web/` contient `llms.txt`, `llms.md` et `agent-skills.md`.
  - **Mais ces fichiers sont conçus pour les agents web externes** (moteurs d'IA comme Perplexity ou ChatGPT cherchant la solution Cémantix sans spoiler).
  - Ils décrivent l'API publique (`/api/daily`, `/api/health`) et la politique éditoriale.
- **Il n'existait AUCUN fichier d'instructions pour les agents développeurs** à la racine (`AGENTS.md`, `project-memory.md`) pour :
  - Expliquer comment lancer les tests (nécessité de Python 3.12 ou Docker, incompatibilité Python 3.14 sans build C).
  - Indiquer l'arborescence des modules `src/` (les docstrings de `cemantix_rag.py` indiquant encore l'ancienne arborescence plate).
  - Signaler les fichiers protégés à ne pas régénérer manuellement sans les outils dédiés (`tools/build_css_bundles.py`).

### 3.4 Faux Guidage par Documentation Obsolète

Dans le fichier d'entrée principal [cemantix_rag.py](../../cemantix_rag.py) (lignes 15-24) :
```python
Architecture modulaire (package src/) :
  - src/config.py   : Constantes, styles ANSI, chemins et configuration LLM
  - src/vocab.py    : VocabStore (lexique, word2vec, embeddings ChromaDB)
  - src/clients.py  : Client API officiel (CemantixClient) & simulation locale (MockClient)
  - src/ui.py       : Rendu console, jauges ASCII, dashboard duel & débriefing
  - src/solvers.py  : Algorithmes Ridge, Rerank, interface LLM & solveurs (Solver, RagDuelPlayer)
  - src/modes.py    : Boucles d'orchestration (benchmark, battle, solo, duel)
  - src/daemon.py   : Démon planificateur 24h/24 (veille et résolution quotidienne à 00h00)
  - src/web.py      : Exportation et synchronisation des données web pour Caddy
```
Un agent qui lit ce point d'entrée cherche ces chemins dans `src/` et constate qu'ils n'existent pas à ce niveau (ils sont dans `src/engine/`, `src/cli/`, `src/services/`). Cela induit des tours d'outils inutiles (`file_not_found`, `list_dir`) pour relocaliser les fichiers.

---

## 4. Évaluation du Découpage Modulaire (Module Splitting)

La question clé est : *Le découpage de gros modules améliore-t-il réellement la navigation d'un agent IA, ou crée-t-il une surcharge de dispersion ?*

### 4.1 Cas 1 : `src/services/seo.py` (1 692 lignes, 76 Ko, ~18 800 tokens)
- **Constat :** Ce fichier unique assure 6 responsabilités distinctes :
  1. Formatage des dates et durées en français (lignes 84-145).
  2. Chargement des CSS critiques pour injection inline (lignes 165-185).
  3. Génération des pages HTML d'archives et d'index (lignes 290-675).
  4. Génération des pages hub `mot-du-jour` et `methode` (lignes 710-1155).
  5. Génération du sitemap XML (lignes 1159-1220).
  6. Génération des manifestes ARD et documentation agent (lignes 1362-1600).
- **Impact Agent :** Si un agent doit ajuster la structure du sitemap XML, il est contraint d'ingérer l'intégralité des 1 692 lignes (18 800 tokens).
- **Bénéfice prouvé du découpage :**
  - Isoler `src/services/seo/sitemap.py` (~150 lignes, ~1 500 tokens).
  - Isoler `src/services/seo/manifests.py` (~250 lignes, ~2 500 tokens).
  - Isoler `src/services/seo/hubs.py` (~450 lignes, ~4 500 tokens).
  - Isoler `src/services/seo/archives.py` (~400 lignes, ~4 000 tokens).
  - **Économie mesurée :** Un agent travaillant sur le sitemap ou les manifestes ARD ne charge que 1 500 à 2 500 tokens au lieu de 18 800 tokens, soit **une réduction de 86 % à 92 % du contexte consommé pour cette tâche**.

### 4.2 Cas 2 : `src/cli/modes.py` (849 lignes, 40 Ko, ~9 800 tokens)
- **Constat :** Mélange `run_benchmark`, `run_battle`, `run_solo_loop` et `run_duel_loop`.
- **Bénéfice prouvé du découpage :** Un agent travaillant sur le mode duel ou benchmark charge ~200 lignes (~2 000 tokens) au lieu de 9 800 tokens (**réduction de ~80 %**).

### 4.3 Cas 3 : `volumes/web/js/multi.js` (1 064 lignes, 38 Ko, ~9 400 tokens)
- **Constat :** Logique multijoueur monolithique sans séparation état / réseau / DOM.
- **Bénéfice :** Permet à l'agent de corriger un bug de synchronisation réseau sans avoir à traiter les centaines de lignes de manipulation du DOM.

---

## 5. Stratégie d'Optimisation du Contexte Agent

Pour maximiser l'efficacité des agents sur ce dépôt sans altérer le code de production :

1. **Création d'un `project-memory.md` compact (< 400 lignes, ~3 500 tokens) :**
   - Résumé exhaustif mais concis de l'architecture, des points d'entrée, des commandes de build/test et des invariants techniques.
   - Sert de contexte racine unique, dispensant l'agent de lire `README.md` (61 Ko) et `CHANGELOG.md` (77 Ko).
2. **Création d'un `AGENTS.md` opérationnel (< 120 lignes, ~1 200 tokens) :**
   - Directives d'exécution précises :
     - Utiliser le conteneur Docker Python 3.12 pour exécuter les tests (évite les échecs liés à Python 3.14 hôte sans wheels compilés).
     - Commandes exactes pour tester, vérifier les docs et contrôler le CSS.
     - Liste explicite des fichiers à NE PAS lire en entier (`lexique_fr.txt`, fichiers dans `volumes/web/css/dist/`, `CHANGELOG.md`).
3. **Règles d'Exclusion pour les Agents IA :**
   - Les fichiers suivants doivent être exclus de toute lecture globale :
     - `cemantix_data/lexique_fr.txt` (465 Ko).
     - `volumes/web/css/dist/*` (fichiers concaténés générés).
     - `docs/roadmap/` (historique archivé des phases terminées).
     - `CHANGELOG.md` (historique narratif).
