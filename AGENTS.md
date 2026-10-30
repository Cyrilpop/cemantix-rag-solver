# AGENTS.md — Directives d'Intervention pour Agents IA

Bienvenue sur le dépôt **Cémantix RAG Solver**. Avant toute intervention, lisez le résumé d'architecture dans [project-memory.md](project-memory.md).

---

## 1. Règles d'Or & Invariants

1. **Environnement d'Exécution des Tests :**
   - Le projet cible **Python 3.12**. Les versions hôtes plus récentes (ex. Python 3.14) n'ont pas de roues binaires précompilées pour `numpy==2.0.2` et `chromadb==1.5.9`.
   - **Toujours exécuter les tests dans le conteneur Docker Python 3.12** :
     ```bash
     docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
       "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"
     ```
2. **Préservation du Repli SQLite :**
   - Les tests s'exécutent sans serveur PostgreSQL actif grâce au basculement automatique sur SQLite local (`DATA_DIR / "cemantix.sqlite3"`). Ne jamais casser la compatibilité SQLite dans `src/db/connection.py`.
3. **Fichiers Interdits de Lecture Complète (Économie de Contexte) :**
   - ⛔ `cemantix_data/lexique_fr.txt` (465 Ko / ~116 000 tokens) — utiliser `head`, `tail` ou `grep`.
   - ⛔ `CHANGELOG.md` (77 Ko / ~18 700 tokens) — historique uniquement.
   - ⛔ `volumes/web/css/dist/*` (fichiers compilés) — modifier les sources dans `volumes/web/css/`.
4. **Gestion du CSS & Bundles :**
   - Si vous modifiez un fichier sous `volumes/web/css/*.css`, lancez obligatoirement :
     ```bash
     python tools/build_css_bundles.py
     python tools/build_css_bundles.py --check
     ```
     Ce script régénère `volumes/web/css/dist/*.css` ET réinjecte le CSS critique inline dans les fichiers HTML.

---

## 2. Commandes de Validation Indispensables

Avant de soumettre une modification, exécutez ces 4 contrôles :

```bash
# 1. Suite de tests unitaires (163 tests attendus, 0 échec)
docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
  "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"

# 2. Cohérence documentaire & roadmap
python tools/check_docs.py

# 3. Contrôle du balisage SEO & métadonnées
python tools/check_seo.py

# 4. Contrôle des bundles CSS
python tools/build_css_bundles.py --check
```

---

## 3. Navigation Rapide dans le Code

| Besoin | Fichier à Inspecter |
|---|---|
| Algorithmes RAG & Régression Ridge | [src/engine/solvers.py](src/engine/solvers.py) |
| Client Certitudes & Mock | [src/engine/clients.py](src/engine/clients.py) |
| Gestionnaire des Sessions de Jeu | [src/game/manager.py](src/game/manager.py) |
| Serveur HTTP REST & CORS | [src/api/server.py](src/api/server.py) |
| Contrôleur des Défis au Bot | [src/api/routes/challenge.py](src/api/routes/challenge.py) |
| Couche Base de Données (Pool & Dialectes) | [src/db/connection.py](src/db/connection.py) |
| Démon 24/7 & Battement | [src/services/daemon.py](src/services/daemon.py) |
| Pages HTML & SEO d'Archives | [src/services/seo.py](src/services/seo.py) |
| Frontend Javascript | [volumes/web/js/](volumes/web/js/) (`game.js`, `battle.js`, `multi.js`, `render.js`) |
