# ⚡ Plan — Génération & Persistance d'Indices IA par Google Gemini

> **Évolution :** [2026-11 · Génération & Persistance d'Indices IA par Google Gemini](../README.md) · document 1/2  
> **Statut du document :** référence de conception, versionnée.  
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.  
> **Jalon technique associé :** [`docs/milestones/M12_GEMINI_AI_HINTS.md`](../../milestones/M12_GEMINI_AI_HINTS.md)  
> **Socle technique prérequis :** [`docs/milestones/M6_PROGRESSIVE_DISCOVERY.md`](../../milestones/M6_PROGRESSIVE_DISCOVERY.md) & [`docs/milestones/M11_INSTANT_INDEXING_RICH_SNIPPETS.md`](../../milestones/M11_INSTANT_INDEXING_RICH_SNIPPETS.md)  
> **Branche :** `feature/m12-gemini-ai-hints` (base `origin/main`)  
> **Date d'ouverture :** 06/11/2026  

**Convention de lecture :** chaque action porte un identifiant permanent (`AI-01` à `AI-06`) utilisé comme **clé de suivi** dans `02-avancement.md`.

---

## 0. Méthodologie & Périmètre

Cette évolution introduit l'IA générative Google Gemini au cœur de Cémantix Solver pour enrichir le jeu avec des indices contextuels hautement qualitatifs :

1. Définition du modèle de données relationnel `daily_puzzle_ai_hints` (PostgreSQL + SQLite) avec stockage dual mot (`hint_word`) et phrase (`hint_phrase`), pondérations (`weight`) et niveau de difficulté (`hint_level`).
2. Création du module `src/ai/` (`gemini_client.py`, `model_selector.py`, `prompts.py`) pour appeler l'API Gemini v1beta avec une clé API sécurisée (`GEMINI_API_KEY`).
3. Ingénierie de prompts en français garantissant 3 indices croissants (éloigné -> intermédiaire -> proche) sans jamais divulguer le mot cible ni sa racine étymologique directe.
4. Intégration dans le démon de résolution quotidienne (`daemon.py`) et mise à disposition d'une commande CLI (`cemantix_rag.py`) avec capacité de backfill.
5. Exclusion délibérée des modifications web frontend pour ce jalon : le périmètre se concentre sur l'infrastructure IA, la robustesse des données et le CLI.
6. Validation par tests unitaires complets sous Docker Python 3.12 et respect des 4 outils de validation documentaire et de qualité.

---

## 1. Findings & Actions Spécifiées

### AI-01 (🔴) — Schéma BDD & Fonctions CRUD (`database/init.sql`, `src/db/connection.py`, `src/db/daily.py`)
- **Problème :** Il n'existe pas de structure de table pour persister des indices IA textuels gradués (mots et phrases) avec métadonnées de modèle et pondération.
- **Correctif :** 
  - Déclarer la table `daily_puzzle_ai_hints` dans `database/init.sql` (PostgreSQL) et dans `src/db/connection.py` pour le schéma SQLite de repli.
  - Implémenter les fonctions CRUD dans `src/db/daily.py` (`save_daily_ai_hints(puzzle_date, hints)` et `get_daily_ai_hints(puzzle_date, revealed_only)`).
  - Exposer ces fonctions dans `src/db/__init__.py`.
- **Vérification :** Test unitaire validant l'insertion et la lecture sur SQLite local avec respect des contraintes d'unicité `(puzzle_date, hint_level)`.

### AI-02 (🔴) — Ingénierie des Prompts Cémantix & Format Dual Mot/Phrase (`src/ai/prompts.py`)
- **Problème :** Un prompt non calibré risque de révéler directement le mot secret, de retourner un format non structuré ou de ne pas dissocier nettement le mot indice et la phrase indice nécessaires pour le choix d'affichage ultérieur.
- **Correctif :**
  - **Prompt Système (`SYSTEM_PROMPT`) :** Rôle de Maître du jeu Cémantix avec interdiction absolue de citer le mot cible, sa racine étymologique ou sa famille morphologique. Exigence de sortie au format JSON strict sans fioritures textuelles.
  - **Dualité Mot & Phrase :** Pour chacun des 3 niveaux (1: éloigné / 0.33, 2: intermédiaire / 0.66, 3: proche / 1.00), exiger deux champs distincts :
    * `word` : un mot unique français (nom, adjectif, verbe) agissant comme balise sémantique courte.
    * `phrase` : une phrase évocatrice (15 à 30 mots) décrivant le concept, son usage ou son analogie sans le nommer.
  - **Prompt Utilisateur (`build_user_prompt`) :** Formulation explicite injectant `{secret_word}` et le schéma attendu `{secret_word, hints: [{level, weight, word, phrase}, ...]}`.
  - **Parseur Robuste & Filtre Anti-Fuite (Leak-Guard) :** Extraction du JSON même en présence de balises markdown, validation des 3 paliers, et contrôle que ni le mot secret ni sa racine n'apparaissent dans `word` ou `phrase`.
- **Vérification :** Tests unitaires validant le prompt généré, le format dual des sorties, le parseur face à des réponses JSON variées et le rejet immédiat en cas de fuite du mot secret.

### AI-03 (🔴) — Client Gemini & Sélecteur de Modèle (`src/ai/gemini_client.py`, `src/ai/model_selector.py`)
- **Problème :** L'appel à Gemini nécessite une gestion rigoureuse de la clé API, des quotas, des timeouts et des erreurs réseau sans dépendance bloquante.
- **Correctif :**
  - Créer `src/ai/model_selector.py` pour centraliser le modèle cible (`gemini-3.8-flash`), la température (0.3 pour la cohérence), et les options de génération.
  - Implémenter `src/ai/gemini_client.py` en exploitant la bibliothèque `requests` déjà intégrée au projet.
  - Récupérer `GEMINI_API_KEY` depuis les variables d'environnement (`.env`) avec log clair si manquante.
  - Gérer les exceptions réseau, les codes HTTP d'erreur (429, 500) et assurer un retour propre `None` ou exception gérée.
- **Vérification :** Tests unitaires avec mocks `unittest.mock` simulant les réponses succès, erreurs 4xx/5xx et absence de clé d'API.

### AI-04 (🟠) — Service Métier & Orchestration Démon (`src/services/ai_hints.py`, `src/services/daemon.py`)
- **Problème :** La génération d'indices IA doit s'exécuter automatiquement chaque nuit lors de la découverte du mot du jour, et pouvoir rattraper les puzzles antérieurs de manière idempotente.
- **Correctif :**
  - Créer `src/services/ai_hints.py` fournissant `generate_and_store_ai_hints(puzzle_date, secret_word, force=False)` et `backfill_ai_hints()`.
  - Intégrer l'appel dans `src/services/daemon.py` immédiatement après la résolution quotidienne et la sauvegarde du puzzle.
  - Vérifier l'existence préalable d'indices pour la date donnée afin d'éviter la surconsommation de quota d'API Gemini, sauf si `force=True`.
- **Vérification :** Test unitaire d'orchestration confirmant que l'appel API est déclenché uniquement si les indices ne sont pas encore en base.

### AI-05 (🟠) — Interface CLI Dédiée (`cemantix_rag.py`)
- **Problème :** L'administrateur ou le développeur doit pouvoir déclencher manuellement la génération ou le rattrapage des indices IA sans attendre le démon nocturne.
- **Correctif :**
  - Ajouter l'option `--generate-ai-hints` dans `cemantix_rag.py`.
  - Supporter les arguments optionnels `--date AAAA-MM-JJ` (par défaut la date du jour ou puzzle courant) et `--force`.
  - Afficher un récapitulatif clair dans la console (niveaux, mots, phrases et pondérations).
- **Vérification :** Exécution sous conteneur Docker `docker compose run --rm cemantix --help` et test de la commande CLI.

### AI-06 (🟡) — Suite de Tests & Contrôles Qualité (`tests/test_ai_hints.py`)
- **Problème :** Risque de régression sur les bases de données, les 386 tests existants ou les 4 outils de conformité du dépôt.
- **Correctif :**
  - Écrire `tests/test_ai_hints.py` couvrant : le client Gemini, les prompts, le modèle de données SQL, le service d'orchestration et le CLI.
  - Exécuter la suite complète sous Docker Python 3.12 (`docker compose run`).
  - Valider l'intégrité avec `tools/check_docs.py`, `tools/check_seo.py` et `tools/build_css_bundles.py --check`.
- **Vérification :** 100 % des tests unitaires au vert, 0 avertissement de documentation.

---

## 2. Déroulement du Workflow Git & Commits

Conformément à la règle d'or du projet, la mise en œuvre respecte un cycle strict :

1. **Base saine :** Branche `feature/m12-gemini-ai-hints` issue de `origin/main` synchronisé.
2. **Commit Initial :** Enregistrement du plan et de la roadmap :
   `docs(milestone): initialiser le cadrage et le plan M12 (indices IA Gemini)`
3. **Commits Fonctionnels Atomiques :**
   - Base de données : `feat(db): schema relationnel et fonctions CRUD pour daily_puzzle_ai_hints` (AI-01)
   - Module IA & Prompts : `feat(ai): implementation du client Gemini, des prompts calibres et du selecteur de modele` (AI-02, AI-03)
   - Services & CLI : `feat(services): orchestration de la generation d'indices IA et commande CLI` (AI-04, AI-05)
   - Tests & Assurance Qualité : `test(ai): suite de tests unitaires pour le client Gemini, les prompts et la persistance SQL` (AI-06)
4. **Commit Final :** Clôture et mise à jour de la documentation globale :
   `docs: finaliser la documentation M12 dans README et CHANGELOG`

---

## 3. Règle d'Or Docker & Commandes de Test Obligatoires

L'ensemble de la pile Cémantix Solver s'exécute **strictement sous conteneur Docker**. Aucune commande Python, pip ou pytest ne doit être exécutée sur l'environnement hôte.

### 3.1 Tests Unitaires Ciblés M12
```bash
docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix \
  -m unittest tests/test_ai_hints.py -v
```

### 3.2 Suite Globale des Tests Unitaires (Python 3.12)
```bash
docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
  "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"
```

### 3.3 Test de l'Interface CLI sous Docker
```bash
docker compose run --rm cemantix --generate-ai-hints
```


