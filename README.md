# 🎯 Cémantix RAG Solver — IA & Régression Géométrique

Solveur haute performance pour le jeu sémantique [Cémantix](https://cemantix.certitudes.org/).

Ce projet implémente deux approches d'Intelligence Artificielle en compétition :
1. ⚡ **100% RAG Mathématique Pur** : Estimation analytique par régression Ridge de la direction du mot secret dans l'espace vectoriel, reranking géométrique multi-indices et détection vectorielle directe (*Sniper RAG*). **Zéro appel LLM, zéro GPU requis, résolution en moins d'une seconde.**
2. 🤖 **Hybride RAG + Local LLM** : Coopération itérative entre l'espace vectoriel et un LLM local (via [LM Studio](https://lmstudio.ai/)) pour explorer le champ lexical et affiner les hypothèses sémantiques.
3. ⚔️ **Mode Battle** : Tournoi en face-à-face sur $N$ manches comparant rigoureusement les deux approches sur le **même mot secret** et avec les **mêmes mots graines** de départ.

---

## 📐 Architecture & Principes Algorithmiques

```
                              ┌──────────────────────────────────┐
                              │  Site Cémantix / Mock Local      │
                              │  (Retourne score = cosinus * 100)│
                              └─────────────────┬────────────────┘
                                                │
                                    Scores s_i  │
                                                ▼
┌───────────────────────┐             ┌──────────────────────────────────┐
│  Espace frWac         │             │  Régression Ridge (q*)           │
│  500 dimensions       │ ──────────> │  q = G^T (G G^T + λ I)^(-1) s    │
│  150 000 lemmes       │             └─────────────────┬────────────────┘
└──────────┬────────────┘                               │
           │                                            ▼
           │ k-NN                     ┌──────────────────────────────────┐
           └────────────────────────> │  Candidats Proches & Reranking   │
                                      │  Score = 0.50 cos(v,q)           │
                                      │        + 0.35 cos(v,best)        │
                                      │        - 0.15 var_err            │
                                      └─────────────────┬────────────────┘
                                                        │
                      ┌─────────────────────────────────┴─────────────────────────────────┐
                      │                                                                   │
                      ▼                                                                   ▼
       [⚡ 100% RAG Pur (Sans LLM)]                                       [🤖 Hybride RAG + LLM]
    Joue directement les meilleurs                                     Prompt contextuel avec Top-15
    candidats rerankés + Sniper RAG                                    Génération de nouveaux lemmes
                      │                                                Validation dictionnaire officiel
                      │                                                                   │
                      └─────────────────────────────────┬─────────────────────────────────┘
                                                        │
                                                        ▼
                                      ┌──────────────────────────────────┐
                                      │  Coup joué & Feedback Cémantix   │
                                      └──────────────────────────────────┘
```

- **Espace vectoriel officiel** : Utilise le corpus `frWac` (Fauconnier, 500 dimensions, continuous Bag-of-Words), source originale utilisée par Cémantix.
- **Amorçage par graines orthogonales & Détection adaptative** : Échantillonnage par *Farthest Point Sampling* (FPS) sur l'hypersphère unitaire minimisant la corrélation cosinus entre les graines (D-optimal design), avec diversification dynamique du point d'ancrage à chaque partie et interruption précoce dès qu'une zone chaude est touchée ($\ge 18^\circ\text{C}$ ou Top 1000).
- **Régression Ridge analytique** : Résout $q^* = \arg\min_q \|G q - s\|^2 + \lambda \|q\|^2$, permettant de trianguler le vecteur cible à partir des produits scalaires observés.
- **Sniper RAG** : Lorsque l'erreur résiduelle quadratique moyenne d'un candidat tombe sous un seuil critique ($\varepsilon < 5 \times 10^{-5}$), le solveur valide immédiatement une certitude mathématique sans gaspiller de coups.
- **Garantie 0 mot refusé & Gestion stricte des accents** : Filtrage et normalisation canonique via le dictionnaire officiel français (Lexique 3.83, 46 272 lemmes). Aucun mot anglais, mot inventé ou pluriel/féminin non recevable n'est émis.

---

## 🛠️ Prérequis

- **Python 3.10 ou supérieur** (testé sous Python 3.11 et 3.12).
- **RAM** : Au minimum 2 Go libres pour héberger en mémoire les matrices vectorielles pré-indexées.
- **Espace disque** : ~2.5 Go au premier lancement pour le téléchargement automatique des vecteurs `frWac`.
- *(Optionnel — uniquement pour le mode Hybride LLM)* : [LM Studio](https://lmstudio.ai/) installé avec un modèle local (ex: Qwen 2.5/3.5, Mistral, Llama 3) et le serveur local activé sur le port `1234`.

---

## 🚀 Installation & Configuration

Vous pouvez exécuter le projet soit **en natif avec Python**, soit **dans un conteneur Docker**.

### Option A : Installation Native Python (Recommandée pour développement)

#### 1. Cloner le dépôt et entrer dans le dossier
```bash
git clone https://github.com/votre-nom/cemantix-rag-solver.git
cd cemantix-rag-solver
```

#### 2. Créer un environnement virtuel isolé
- **Sous Linux / macOS :**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **Sous Windows (PowerShell) :**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

#### 3. Installer les dépendances
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> [!NOTE]
> Au tout premier lancement, le script téléchargera automatiquement le fichier d'embeddings `frWac` (~2.1 Go) depuis la source officielle et construira le cache d'accès instantané en mémoire vive (`.npy` mmap). Cette étape ne s'exécute qu'une seule fois.

---

### Option B : Déploiement avec Docker

Le conteneur Docker isole l'environnement et monte un volume hôte pour conserver les données vectorielles entre les exécutions.

#### 1. Construire l'image Docker
```bash
docker compose build
# Ou avec docker build direct :
# docker build -t cemantix-rag .
```

#### 2. Lancer une commande
Avec Docker Compose, le dossier `./cemantix_data` est automatiquement préservé sur votre machine :
```bash
# Afficher l'aide
docker compose run --rm cemantix --help

# Lancer une partie en mode 100% RAG pur
docker compose run --rm cemantix --rag-only

# Lancer un tournoi Battle de 3 manches
docker compose run --rm cemantix --battle 3
```

> [!TIP]
> Si vous utilisez LM Studio sur votre machine hôte avec Docker, le conteneur accède directement à LM Studio via l'adresse `http://host.docker.internal:1234/v1` (configurée par défaut dans `docker-compose.yml`).

---

## 🎮 Guide d'Utilisation

### 0. Menu Interactif Principal (Par défaut)

Si vous lancez le solveur **sans option** (ou avec `--menu` / `-i`), un menu d'accueil interactif s'affiche :

```bash
python cemantix_rag.py
# ou avec l'option explicite :
python cemantix_rag.py --menu
```

Ce menu centralise et permet de piloter toutes les fonctionnalités du projet :
- `[1] 🎯 Résoudre le puzzle du jour` : choix du moteur (Hybride ou 100% RAG pur), réglage des graines et répétition consécutive.
- `[2] 🧑 Mode Jeu Solo` : recherche sémantique libre avec jauges ASCII, météos et indices vectoriels.
- `[3] ⚔️ Mode Duel Croisé` : vous affrontez l'IA RAG avec 3 niveaux et espionnage sémantique (`/espion`).
- `[4] 🥊 Mode Battle comparatif` : RAG Pur vs Hybride LLM sur le même mot secret.
- `[5] 🧪 Simulation locale Mock` : résolution automatique locale par l'IA sur mot aléatoire ou imposé.
- `[6] 📊 Benchmark autonome` : évaluation statistique de précision sur $N$ parties simulées.
- `[7] ⚙️ Paramètres & Configuration` : ajustement en direct du mode verbeux, des délais, des graines et du LLM.
- `[Q] 🚪 Quitter` : quitter proprement l'application.

> [!TIP]
> Sur **absolument tous les écrans, sous-menus et invites de saisie**, tapez `/menu` (ou `menu`) pour revenir instantanément au menu principal !

---

### 1. Affronter le mot du jour officiel Cémantix en CLI direct

Vous pouvez également lancer directement le solveur en ligne de commande avec des options :

- **Mode 100% RAG Pur (Ultra-rapide, 0 LLM requis)** :
  ```bash
  python cemantix_rag.py --rag-only
  ```
- **Mode Verbose (affiche la descente Ridge, les candidats rerankés et le raisonnement du LLM)** :
  ```bash
  python cemantix_rag.py -v
  ```

---

### 2. Tournoi comparatif : Mode Battle (`--battle [N]`)

Le mode Battle oppose en duel direct **100% RAG Pur** contre **Hybride RAG + LLM** :
- Les deux solveurs s'affrontent sur le **STRICTEMENT MÊME mot secret**.
- Les deux solveurs reçoivent les **MÊMES mots graines d'amorçage**.
- La série du RAG s'exécute en premier, suivie de la série du LLM, puis un tableau d'honneur comparatif affiche les victoires, les écarts en coups et le facteur d'accélération.
- **Support Multi-Mots & Multi-Rounds** : Vous pouvez évaluer les modèles sur $M$ mots différents $\times$ $R$ rounds par mot !

```bash
# 1 manche comparative en direct sur le mot officiel du jour :
python cemantix_rag.py --battle 1

# Tournoi de 3 manches sur le mot du jour officiel :
python cemantix_rag.py --battle 3

# Tournoi de 5 manches en simulation locale (MOCK) sur un mot secret tiré au sort :
python cemantix_rag.py --battle 5 --mock

# Battle sur un mot secret imposé :
python cemantix_rag.py --battle 2 --secret "volcan"

# Tournoi multi-mots : 5 mots secrets distincts testés sur 2 rounds chacun (10 duels au total) :
python cemantix_rag.py --battle 2 --words 5

# Tournoi sur une liste précise de mots imposés :
python cemantix_rag.py --battle 2 --secrets "volcan,politique,astronomie"
```

---

### 3. Mode Simulation Locale & Entraînement (`--mock` & `--benchmark`)

Pour tester, évaluer et benchmarker vos algorithmes sans saturer l'API officielle :

- **Partie unique simulée en local (mot tiré au sort)** :
  ```bash
  python cemantix_rag.py --mock --rag-only
  ```
- **Partie simulée sur un mot secret de votre choix** :
  ```bash
  python cemantix_rag.py --mock --secret "astronomie" --verbose
  ```
- **Benchmark sur $N$ parties avec métriques globales (taux de victoire, moyenne, médiane)** :
  ```bash
  python cemantix_rag.py --benchmark 10 --rag-only
  ```

---

### 4. Mode Jeu Interactif Solo (`--play` ou `--game`)

Permet à un joueur humain de deviner le mot secret tiré au sort avec le calcul vectoriel officiel :
- **Dashboard en temps réel :** Tableau récapitulatif Top 15 des meilleurs essais avec température, météo et rang en pourmille (‰).
- **Thermomètre ASCII dynamique :** Jauge visuelle instantanée sous le dernier coup (`[████░░░░░░░░░░░░░░░░]`).
- **Indices vectoriels RAG (`/indice`) :** Calcule un pont sémantique interpolé sans trahir directement le mot secret.
- **Boucle continue :** Enchaînement instantané des parties sans rechargement de la base vectorielle.

```bash
# Lancer le mode jeu interactif :
python cemantix_rag.py --play

# Jouer avec un mot imposé pour s'entraîner :
python cemantix_rag.py --play --secret "volcan"
```

---

### 5. Mode Duel Croisé Humain vs IA (`--duel`)

Face-à-face en simultané type « Bataille Navale sémantique » opposant un joueur humain et l'IA RAG :
- **Mots secrets croisés :** L'Humain cherche le mot de l'IA ; l'IA cherche le mot choisi par l'Humain (ou tiré au sort avec `/random`).
- **Dashboard miroir synchronisé :** Affichage côte à côte des deux progressions (thermomètres ASCII, météo, Top coups).
- **Niveaux de difficulté :** 3 profils d'IA (`facile`, `moyen`, `expert`) sélectionnables au départ ou via `/diff`, `/facile`, `/moyen`, `/expert`.
- **Coup spécial d'espionnage (`/espion`) :** 1 crédit par match pour intercepter les projections Ridge de l'IA (disciplines surveillées, niveau de danger).
- **Débriefing comparatif d'après-match :** Bilan exhaustif côte à côte (vainqueur, première étincelle, répartition météo).

```bash
# Lancer le mode duel croisé :
python cemantix_rag.py --duel

# Régler la difficulté initiale de l'IA :
python cemantix_rag.py --duel -d expert
```

---

## ⚙️ Options en Ligne de Commande

| Option | Type | Défaut | Description |
| :--- | :---: | :---: | :--- |
| `--duel` | Flag | `False` | Lance le mode duel croisé interactif (Humain vs IA RAG). |
| `--difficulty`, `-d` | Choix (`facile`, `moyen`, `expert`) | `moyen` | Règle le niveau d'agressivité de l'IA en mode duel. |
| `--play`, `--game` | Flag | `False` | Active le mode jeu interactif solo dans le terminal. |
| `--rag-only`, `--no-llm` | Flag | `False` | Active le mode 100% RAG mathématique pur (zéro appel LLM). |
| `--battle [R]` | Entier | `0` | Lance un tournoi comparatif de $R$ round(s) par mot (défaut : 1). |
| `--words <M>` | Entier | `1` | Nombre de mots secrets distincts à tester en battle (active le mode mock). |
| `--secrets <mots>` | Chaîne | `""` | Liste de mots secrets imposés séparés par des virgules (active le mock). |
| `--mock` | Flag | `False` | Simule les scores en local à la volée (calcul instantané des cosinus). |
| `--secret <mot>` | Chaîne | `None` | Impose le mot secret unique à trouver (active automatiquement le mock). |
| `--benchmark <N>` | Entier | `0` | Exécute $N$ parties d'affilée en simulation locale et affiche les statistiques. |
| `-v`, `--verbose` | Flag | `False` | Affiche les détails internes (erreur Ridge, top-15 injecté, logs LLM). |
| `--seed-count <N>` | Entier | `12` | Nombre de mots graines lors de l'amorçage orthogonal RAG (Farthest Point Sampling). |
| `--seeds <mots>` | Chaîne | `""` | Mots graines manuels séparés par des virgules (ex: `"danse,science,art"`). |
| `--delay <sec>` | Float | `0.25` | Délai de politesse entre deux requêtes envoyées à l'API du site web. |
| `--max-tries <N>` | Entier | `300` | Nombre maximum de tentatives avant d'abandonner une partie. |

---

## 🌐 Variables d'Environnement

Ces variables peuvent être définies dans votre shell ou dans un fichier `.env` :

| Variable | Défaut | Description |
| :--- | :--- | :--- |
| `LM_API` | `http://host.docker.internal:1234/v1` (ou `http://localhost:1234/v1`) | URL de l'API OpenAI compatible de LM Studio. |
| `LLM_MODEL` | `qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2` | Identifiant du modèle chargé dans LM Studio. |
| `W2V_FILE` | `frWac_no_postag_phrase_500_cbow_cut10.bin` | Nom du fichier word2vec hébergé sur embeddings.net. |

---

## 📁 Arborescence du Projet

```
cemantix-rag-solver/
├── cemantix_rag.py          # Point d'entrée CLI et orchestration générale
├── requirements.txt         # Dépendances Python (NumPy, ChromaDB, Requests)
├── Dockerfile               # Image conteneurisée prête à l'emploi
├── docker-compose.yml       # Configuration Docker avec persistance du volume de données
├── .gitignore               # Exclut les fichiers binaires volumineux et caches
├── README.md                # Documentation complète du projet
├── CHANGELOG.md             # Historique des versions et refactorings
├── cemantix_data/           # Cache local (lexique_fr.txt, modèles w2v, ChromaDB)
│   └── lexique_fr.txt       # Dictionnaire de référence (46 272 lemmes officiels)
└── src/                     # Architecture modulaire
    ├── __init__.py          # Expose les classes et fonctions du package
    ├── config.py            # Constantes, styles ANSI, chemins et configuration LLM
    ├── vocab.py             # VocabStore (lexique, word2vec, embeddings ChromaDB)
    ├── clients.py           # Clients API officiel (CemantixClient) & simulation locale (MockClient)
    ├── ui.py                # Rendu console, jauges ASCII, dashboard duel & débriefing
    ├── solvers.py           # Régression Ridge, Rerank, interface LLM & solveurs (Solver, RagDuelPlayer)
    └── modes.py             # Boucles de jeu (benchmark, battle, solo, duel)
```

---

## ⚖️ Licence

Ce projet est distribué sous licence MIT. Les vecteurs pré-entraînés `frWac` proviennent des travaux de Jean-Philippe Fauconnier (*French Web as Corpus*).
