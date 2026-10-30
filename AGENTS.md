# AGENTS.md — Directives d'Intervention & Navigation pour Agents IA

Bienvenue sur le dépôt **Cémantix RAG Solver**. Avant toute intervention, lisez le résumé d'architecture dans [project-memory.md](project-memory.md).

---

## 1. Protocole de Navigation Contextuelle (Context-Aware Workflow)

Pour préserver votre fenêtre de contexte et éviter la saturation de tokens, suivez impérativement ce flux en 7 étapes :

1. **Lire `AGENTS.md`** : assimilation des règles d'or et commandes de contrôle.
2. **Consulter `project-memory.md`** : repérage du sous-système concerné sans charger le `README.md` monolithique.
3. **Identifier le sous-système cible** via la table de navigation (§4 ci-dessous).
4. **Localiser les symboles et dépendances** avec des recherches ciblées (`python tools/agent_find.py <symbole>` ou `rg`).
5. **Lire uniquement les plages de lignes pertinentes** (utiliser `read_file` avec `StartLine` et `EndLine`).
6. **Élargir le périmètre progressivement** si les dépendances ou les tests unitaires l'exigent.
7. **Ignorer les documentations historiques et fichiers compilés.**

---

## 2. Exclusions de Contexte par Défaut

Les fichiers et répertoires suivants **ne doivent jamais être lus en intégralité** lors de la prise en main d'une tâche (ce sont des règles d'économie de contexte, et non des règles de suppression git) :

- ⛔ `CHANGELOG.md` (77 Ko / ~18 700 tokens) — historique archivé.
- ⛔ `docs/roadmap/**` et `docs/audits/**` — plans et rapports historiques.
- ⛔ `cemantix_data/lexique_fr.txt` (465 Ko / ~116 000 tokens) — utiliser `head`, `tail` ou `grep`.
- ⛔ `volumes/web/css/dist/**` — fichiers compilés générés.
- ⛔ CSS minifié inliné dans `<style id="critical-css">` dans les fichiers HTML.
- ⛔ Bases de données SQLite locales (`*.sqlite3`), index vectoriels (`chroma_w2v/`), caches et images.

> **Note :** Ces exclusions n'interdisent pas une inspection ciblée et bornée d'une ligne ou d'une signature précise si la sécurité ou l'exactitude de la tâche l'exige.

---

## 3. Règles d'Or & Invariants Opérationnels

1. **Environnement d'Exécution des Tests :**
   - Le projet cible **Python 3.12**. Les versions hôtes plus récentes (ex. Python 3.14) n'ont pas de roues binaires précompilées pour `numpy==2.0.2` et `chromadb==1.5.9`.
   - **Toujours exécuter les tests dans le conteneur Docker Python 3.12** :
     ```bash
     docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
       "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"
     ```
2. **Préservation du Repli SQLite :**
   - Les tests s'exécutent sans serveur PostgreSQL actif grâce au basculement automatique sur SQLite local (`DATA_DIR / "cemantix.sqlite3"`). Ne jamais casser la compatibilité SQLite dans `src/db/connection.py`.
3. **Gestion du CSS & Bundles :**
   - Si vous modifiez un fichier sous `volumes/web/css/*.css`, lancez obligatoirement :
     ```bash
     python tools/build_css_bundles.py
     python tools/build_css_bundles.py --check
     ```
     Ce script régénère `volumes/web/css/dist/*.css` ET réinjecte le CSS critique inline dans les fichiers HTML.

---

## 4. Navigation Rapide & Outil de Découverte de Symboles

### 4.1 Outil d'Inspection Rapide (`tools/agent_find.py`)
Utilisez le script utilitaire léger (zéro dépendance) pour repérer l'emplacement exact d'une fonction ou d'une classe sans charger de gros fichiers :
```bash
python tools/agent_find.py estimate_secret      # Localise la fonction et renvoie son span Lxx-Lyy
python tools/agent_find.py --summary src/engine/solvers.py  # Affiche les repères clés sans le corps
```

### 4.2 Sous-Systèmes Clés

| Besoin | Fichier à Inspecter | Plage Typique |
|---|---|---|
| Algorithme RAG & Ridge | [src/engine/ranking.py](src/engine/ranking.py) | L15-L65 (`estimate_secret`, `rerank`, `weather`) |
| Client Certitudes & Simulation Mock | [src/engine/clients.py](src/engine/clients.py) | L20-L80 (`CemantixClient`, `MockClient`) |
| Gestionnaire des Sessions de Jeu | [src/game/manager.py](src/game/manager.py) | L230-L360 (`new_game`, `new_battle`) |
| Serveur HTTP REST & CORS | [src/api/server.py](src/api/server.py) | L65-L160 (`GameAPIHandler`) |
| Sécurité Réseau & Proxys de Confiance | [src/api/proxy.py](src/api/proxy.py) | L70-L140 (`extract_client_ip`, `anonymize_ip`) |
| Contrôleur des Défis au Bot | [src/api/routes/challenge.py](src/api/routes/challenge.py) | L100-L190 (`handle_challenge_post`) |
| Couche Base de Données (Pool & Dialectes) | [src/db/connection.py](src/db/connection.py) | L480-L560 (`transaction`, `execute`) |
| Démon 24/7 & Battement | [src/services/daemon.py](src/services/daemon.py) | L240-L350 (`run_daily_solver`, boucle) |
| Pages HTML & SEO d'Archives | [src/services/seo.py](src/services/seo.py) | L410-L600 (archives) ou L1150-L1220 (sitemap) |
| Frontend Javascript | [volumes/web/js/](volumes/web/js/) | `render.js` (rendu coups), `utils.js` (tiers météo) |

---

## 5. Commandes de Validation Indispensables

Avant de soumettre toute modification, exécutez ces 4 contrôles :

```bash
# 1. Suite de tests unitaires (231 tests attendus, 0 échec)
docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
  "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"

# 2. Cohérence documentaire & roadmap
python tools/check_docs.py

# 3. Contrôle du balisage SEO & métadonnées
python tools/check_seo.py

# 4. Contrôle des bundles CSS
python tools/build_css_bundles.py --check
```
