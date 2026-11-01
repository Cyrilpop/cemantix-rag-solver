# 🎯 Cémantix RAG Solver — IA & Régression Géométrique

Solveur haute performance pour le jeu sémantique [Cémantix](https://cemantix.certitudes.org/).

Ce projet implémente deux approches d'Intelligence Artificielle en compétition :
1. ⚡ **100% RAG Mathématique Pur** : Estimation analytique par régression Ridge de la direction du mot secret dans l'espace vectoriel, reranking géométrique multi-indices et détection vectorielle directe (*Sniper RAG*). **Zéro appel LLM, zéro GPU requis, résolution en moins d'une seconde.**
2. 🤖 **Hybride RAG + Local LLM** : Coopération itérative entre l'espace vectoriel et un LLM local (via [LM Studio](https://lmstudio.ai/)) pour explorer le champ lexical et affiner les hypothèses sémantiques.
3. ⚔️ **Mode Battle** : Tournoi en face-à-face sur $N$ manches comparant rigoureusement les deux approches sur le **même mot secret** et avec les **mêmes mots graines** de départ.
4. ⏰ **Démon 24h/24 & Veille Quotidienne** : Fonctionnement permanent en conteneur Docker en mode sommeil, réveil automatique chaque nuit à 00h00 (heure de Paris) pour trouver le mot officiel du jour dès sa parution et historisation automatique en base relationnelle PostgreSQL 16.
5. 🌐 **Page Web & Publication Caddy** : Interface web moderne et réactive servant le mot du jour en direct depuis le volume `./volumes/web` avec reverse-proxy vers l'API `cemantix_web:8000` (protection anti-spoiler serveur, thermomètre sémantique, compte à rebours minuit et KPIs).
6. 🏗️ **Architecture 3-Tiers Découplée & Durcie** : Découpage strict entre base de données (`cemantix_db`), démon de calcul vectoriel (`cemantix_worker`), API REST légère (`cemantix_web`) et conteneur CLI (`cemantix`), avec pool de connexions borné thread-safe et conformité stricte sécurité/RGPD (anonymisation IP /24, CSP sans inline, rejet XSS, hachage HMAC-SHA256).

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
- **Garantie 0 mot refusé, Filtrage anti-anglicismes & Gestion stricte des accents** : Filtrage et normalisation canonique via le dictionnaire officiel français (Lexique 3.83, 46 200+ lemmes). Exclusion stricte des mots et tokens anglais parasites purs (`ENGLISH_WORDS`) et des graphies anglaises sans accent (*decision*, *region*...) au profit de la vraie orthographe (*décision*, *région*). Tous les lemmes et mots grammaticaux usuels (*car*, *faire*, *être*, *avoir*, *plus*, *moins*, *bien*, etc.), les homographes (*table*, *train*, *sport*, *film*, *source*, *parent*, etc.) et les emprunts acceptés (*process*, *report*, *bug*, *job*, *coach*, *deal*, *pass*, *set*, *top*, *cool*, etc.) sont immédiatement valides par simple présence dans `lexique_fr.txt`.

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

### Option B : Déploiement avec Docker (Architecture 3-Tiers Découplée)

Le déploiement s'appuie sur une **architecture 3-tiers découplée et durcie** définie dans `docker-compose.yml` :
- `cemantix_db` : Base de données relationnelle PostgreSQL 16 Alpine pour la persistance transactionnelle ACID (`daily_puzzles`, `solo_sessions`, `multi_rooms`).
- `cemantix_worker` : Démon planificateur d'arrière-plan 24h/24 (calcul vectoriel lourd ChromaDB, résolution quotidienne à 00h00 heure de Paris et publication SEO).
- `cemantix_web` : API REST HTTP haute performance (< 200 Mo RAM) servant le frontend web, le jeu Solo, le mode Battle, le Multijoueur 1v1, le mot du jour et la génération automatique de `sitemap.xml` au démarrage.
- `cemantix` : Conteneur CLI éphémère (profil `cli`) pour les commandes interactives, les benchmarks et les tests unitaires.

#### 1. Construire les images Docker
```bash
docker compose build
```

#### 2. Lancement des services en arrière-plan
Les conteneurs démarrent ensemble de manière orchestrée (la base PostgreSQL est validée par healthcheck avant le lancement du worker et du serveur web) :

```bash
# Lancer les services (base de données, worker et API web) en arrière-plan :
docker compose up -d

# Suivre les logs du démon worker (résolution quotidienne RAG) :
docker compose logs -f cemantix_worker

# Suivre les logs de l'API web :
docker compose logs -f cemantix_web

# Suivre les logs de la base de données :
docker compose logs -f cemantix_db

# Arrêter proprement l'ensemble des conteneurs :
docker compose down
```

> [!NOTE]
> - **Persistance relationnelle & ACID** : Chaque puzzle résolu est persisté de façon transactionnelle dans PostgreSQL (`daily_puzzles`) avec calcul SQL direct des métriques et miroir dans `./cemantix_data/daily_history.json`.
> - **Rattrapage au démarrage** : Si le mot d'aujourd'hui n'a pas encore été résolu, le worker le trouve dès son lancement avant de se mettre en sommeil jusqu'au prochain minuit.
> - **Génération automatique de `sitemap.xml` au démarrage** : Non versionnés sous Git (`.gitignore`) pour éviter tout conflit lors d'un `git pull`, `volumes/web/sitemap.xml` et les pages d'archives `/puzzles/` sont régénérés automatiquement et de manière atomique à chaque démarrage de `cemantix_web` et `cemantix_worker` (`ensure_seo_published()`).

> [!IMPORTANT]
> **Permissions POSIX du volume `cemantix_data` (ChromaDB & non-root UID 1000) :**
> Par conformité de sécurité (`SEC-13`), les conteneurs `cemantix_worker` et `cemantix_web` s'exécutent avec l'utilisateur non privilégié `cemantix` (`UID 1000:1000`) et en système de fichiers en lecture seule (`read_only: true`).
> Sur la machine hôte, le volume partagé `./cemantix_data` (notamment le sous-dossier `chroma_w2v/` hébergeant la base vectorielle SQLite) doit impérativement être accessible en écriture par cet utilisateur :
> ```bash
> sudo chown -R 1000:1000 ./cemantix_data
> ```
> Si ce répertoire appartient à `root`, SQLite bascule en mode lecture seule (`attempt to write a readonly database`), empêchant le chargement de ChromaDB et le traitement des défis.

#### 3. Lancer une commande ponctuelle, interactive ou les tests
Sans arrêter les services de production, vous pouvez exécuter le menu interactif ou les suites de tests via le conteneur CLI éphémère :

```bash
# Afficher l'aide CLI
docker compose run --rm cemantix --help

# Lancer le menu interactif complet
docker compose run --rm -it cemantix --menu

# Jouer une partie Solo interactive
docker compose run --rm -it cemantix --play

# Défier l'IA en mode Duel croisé
docker compose run --rm -it cemantix --play --duel

# Lancer une partie ponctuelle en mode 100% RAG pur
docker compose run --rm cemantix --rag-only

# Lancer un tournoi Battle de 3 manches
docker compose run --rm cemantix --battle 3

# Exécuter l'intégralité des 81 tests unitaires sous Docker
docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests
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

- **Mode Démon 24h/24 (Veille et résolution quotidienne chaque nuit à 00h00)** :
  ```bash
  python cemantix_rag.py --daemon --rag-only
  ```
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
- **Niveaux de difficulté :** 3 profils d'IA (`facile`, `moyen`, `expert`) sélectionnables au départ ou via `/diff`, `/facile`, `/moyen`, `/expert`.\
- **Coup spécial d'espionnage (`/espion`) :** 1 crédit par match pour intercepter les projections Ridge de l'IA (disciplines surveillées, niveau de danger).
- **Débriefing comparatif d'après-match :** Bilan exhaustif côte à côte (vainqueur, première étincelle, répartition météo).

```bash
# Lancer le mode duel croisé :
python cemantix_rag.py --duel

# Régler la difficulté initiale de l'IA :
python cemantix_rag.py --duel -d expert
```

---

---

### 6. Page Web du Mot du Jour & Serveur Caddy (./volumes/web)

Le projet intègre une interface web complète et réactive déposée dans le volume obligatoire ./volumes/web, conçue pour être servie ultra-efficacement par **Caddy** (ou tout autre serveur HTTP) :

> [!WARNING]
> **Le webroot ne doit contenir que des fichiers publics.** Les données du solveur
> (`data.json`, `daily_history.json`, `web_sessions.json`) sont écrites dans
> `./cemantix_data`, **jamais** dans `./volumes/web` : `data.json` renferme l'historique
> complet des solutions, et un fichier de ce type dans le webroot se récupère d'un simple
> `curl https://…/data.json`. `export_web_data()` refuse désormais toute cible située dans
> le webroot. Le front-end ne lit que `/api/*`.

```
volumes/web/
├── index.html        # Tableau de bord du mot du jour (URL : /)
├── puzzles/          # Archives quotidiennes indexables (générées par --publish-seo)
│   └── 2026-10-26/index.html
├── play/             # Interface dédiée au jeu interactif (URL propre : /play/)
│   └── index.html    # Page de jeu (mode défi du jour, mode illimité)
├── battle/           # Mode Battle Joueur vs Bot IA RAG (URL propre : /battle/)
│   └── index.html    # Page de duel contre l'IA, double jauge et indices
├── multi/            # Mode Multijoueur 1v1 Tour par Tour (URL propre : /multi/)
│   └── index.html    # Page de duel entre amis (Même Mot, Mots Choisis, lien direct)
├── css/              # Feuilles de style atomiques et bundles compilés
│   ├── dist/         # Bundles minifiés par page (dashboard, play, battle, multi, modal, puzzle)
│   ├── variables.css # Thèmes clair/sombre, tokens de couleurs et dégradés thermiques
│   ├── base.css      # Reset, boutons, badges, cartes, notifications toast et verrouillage mobile
│   ├── layout.css    # En-tête, navigation par onglets défilante et pied de page
│   ├── dashboard.css # Styles du tableau de bord, thermomètre et guide SEO
│   ├── game.css      # Styles de l'interface de jeu, saisie mobile et clavier virtuel
│   ├── battle.css    # Styles dédiés au duel contre l'IA et scoreboard adaptatif
│   ├── multi.css     # Styles dédiés au multijoueur 1v1, lobby et arène de duel
│   ├── modal.css     # Modales de configuration, débriefing et confirmation
│   └── puzzle.css    # Styles responsives complémentaires des pages d'archives
├── js/               # Modules JavaScript atomiques (ES Modules)
│   ├── app.js        # Point d'entrée léger et initialisation ciblée
│   ├── utils.js      # Formatage, dates, presse-papier, helpers
│   ├── render.js     # Rendu mutualisé des tuiles de coups (Battle & Multijoueur)
│   ├── theme.js      # Thème clair/sombre, anti-spoiler, scroll nav et visualViewport mobile
│   ├── countdown.js  # Horloge décomptant en temps réel le saut de minuit
│   ├── dashboard.js  # Rendu du mot du jour, des indices et polling temps réel
│   ├── trajectory.js # Visualisation et filtres de la trajectoire IA
│   ├── game.js       # Moteur complet du jeu interactif (API locale)
│   ├── battle.js     # Moteur du duel contre le bot IA RAG
│   └── multi.js      # Moteur du mode multijoueur 1v1 temps réel
```

#### Fonctionnalités clés de la page web :
- **Carte Héros du Mot du Jour** : Affiche la date, le numéro du puzzle officiel, le mot secret, le nombre d'essais et la durée de calcul.
- **Protection Anti-Spoiler Intelligente** : Le mot secret est masqué sous un voile flouté par défaut (👁️ Révéler / 🙈 Masquer, bouton de copie avec toast). Idéal pour consulter les indices ou les statistiques du jour sans se gâcher le plaisir de chercher.
- **Thermomètre Cémantix & Top Indices d'Approche** : Visualisation de l'échelle thermique officielle (Glacial, Froid, Tiède, Chaud, Brûlant) et des meilleurs mots trouvés par l'IA lors de sa convergence.
- **Compte à Rebours Minuit en Direct** : Ticker numérique en temps réel décomptant le temps restant avant la parution du prochain mot secret (00h00 heure de Paris).
- **Tableau de Bord des Performances (KPIs)** : Nombre total de puzzles résolus, moyenne de coups, durée moyenne de calcul et taux de victoire (100%).
- **Historique & Recherche Instantanée** : Filtre en temps réel pour explorer les archives des puzzles par date ou mot-clé.
- **Actualisation Automatique** : La page interroge automatiquement l'API locale `/api/daily` toutes les 30 secondes pour afficher le nouveau mot dès que le démon le trouve à minuit.
- **Ergonomie Responsive Mobile Native** : Refonte smartphone complète (`≤ 768px` / `≤ 480px`, GP8 Pro, iPhone, 360px) sans aucun impact sur l'affichage Bureau — verrouillage `overflow-x: clip`, saisie empilée `16px` sans auto-zoom, adaptation dynamique à l'ouverture du clavier virtuel (`visualViewport`), navigation défilante auto-centrée, cibles tactiles ≥ `44×44px` et support `safe-area-inset-bottom`.
- **Performance Mobile PageSpeed (Zéro requête CSS bloquante & Zéro reflow forcé)** : Injection automatique du CSS critique minifié dans `<head>` (`tools/build_css_bundles.py`), chargement différé non bloquant de `modal.css` compatible CSP (`script-src 'self'`), lecture géométrique différée via `requestAnimationFrame` dans `js/theme.js` et manifestes de découverte agentique conformes ARD (`/.well-known/ard.json` et `/.well-known/ai-catalog.json`).

#### 🤖 Défier le Bot IA (`/defi/`) :
Le visiteur propose **un mot secret** ; le solveur RAG du site doit le retrouver, coup par coup, **en direct**. L'architecture tri-partite reste stricte :

1. **`cemantix_web` enfile, ne calcule jamais** — `POST /api/challenge` valide le mot (regex + lexique du site, message unique « Mot non reconnu »), vérifie la whitelist d'exemption, l'anti-rafale mémoire, le **quota de 10 défis/heure persisté en base** (insensible aux redémarrages) et la file bornée, puis écrit une ligne dans `bot_challenges`. Le module de route n'importe ni solveur ni démon (`grep -n "solvers\|daemon" src/api/routes/challenge.py` est vide).
2. **`cemantix_worker` résout** — dans sa boucle de veille, toutes les 3 s : recyclage des orphelins, claim atomique, résolution par le moteur existant (`Solver` + `MockClient(secret=…)` de l'option `--secret` du CLI) **en 100 % RAG pur, zéro LLM**, trajectoire publiée toutes les 2 s. La résolution nocturne de minuit garde la priorité ; `CHALLENGE_ENABLED=0` coupe tout sans redéploiement.
3. **Le front affiche** — `js/defi.js` ouvre un `EventSource` sur `/api/challenge/<id>/stream` (repli polling automatique si le flux tombe) et rend chaque coup au gabarit exact de la trajectoire du mot du jour ; le bot peut **perdre** (statut `lost`), c'est une issue affichée.

Sécurité : IP hachée (HMAC-SHA256 salé, /24), purge automatique à 30 jours, identifiants de défis aléatoires 128 bits, `Cache-Control: no-store`, mot jamais révélé avant le statut terminal (et seulement si le bot a gagné), anti-XSS en trois couches, plafond de 16 flux SSE simultanés. Les IP exemptées se gèrent dans la console d'exploitation (onglet Actions).

#### Configuration Caddy (Production & Anti-Cache Automatique) :
Dans votre conteneur Caddy ou votre machine hôte, pointez la racine sur `./volumes/web` et appliquez la politique de cache HTTP optimisée.

> [!TIP]
> **Pourquoi aucun paramètre de version (`?v=...`) dans le code HTML/JS ?**
> Les paramètres de requête manuels (`?v=202610...`) sont proscrits : ils compliquent les imports ES modules imbriqués et sont redondants avec les capacités natives de Caddy / Nginx. En configurant `Cache-Control: "no-cache, must-revalidate"` sur les fichiers `.js` et `.css`, le navigateur valide automatiquement l'empreinte ETag du fichier auprès du serveur. Dès qu'un `git pull` met à jour un fichier sur disque, le navigateur reçoit instantanément la nouvelle version sans nécessiter de purge manuelle de cache (`Ctrl+F5`).

> [!IMPORTANT]
> **Le `Caddyfile` de déploiement est situé à la racine du serveur** (fichier local non versionné).
> Le bloc ci-dessous en fournit la référence complète pour la configuration du reverse-proxy Caddy.
> Pour appliquer les modifications, rechargez Caddy
> (`docker exec <caddy> caddy reload --config /etc/caddy/Caddyfile`). Le monter en
> lecture seule dans le conteneur Caddy : `./Caddyfile:/etc/caddy/Caddyfile:ro`.

```caddy
cemantix.cyril-randon.fr {
    root * /volumes/web

    # En-têtes de sécurité (toutes les réponses)
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        Cross-Origin-Opener-Policy "same-origin"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"

        # Politique de sécurité du contenu. Le site n'utilise AUCUNE ressource externe
        # (ni CDN, ni police, ni script tiers) : la politique peut donc être
        # restrictive. 'unsafe-inline' pour les styles est nécessaire car les feuilles
        # de style sont locales et les style="…" posés par le JS sont des valeurs codées
        # en dur, jamais des données utilisateur.
        # script-src 'self' suffit : seul js/app.js (module ES local) est chargé, donc
        # tout <script> injecté par une faille XSS est bloqué par le navigateur.
        Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; manifest-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
    }

    # Pages d'archives : contenu statique et script inline de bascule de thème.
    header /puzzles/* {
        Content-Security-Policy "default-src 'none'; script-src 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    }

    # 1. Polices web immuables (cache 1 an)
    @fonts path *.woff *.woff2
    header @fonts Cache-Control "public, max-age=31536000, immutable"

    # 2. Images : revalidation par ETag. Pas de max-age long ici, car le projet a
    #    supprimé les suffixes ?v= : sans revalidation, un og-image.jpg remplacé
    #    resterait invisible jusqu'à l'expiration du cache (et les partages sociaux
    #    sont justement sensibles aux anciennes vignettes).
    @images path *.ico *.png *.jpg *.jpeg *.webp *.svg
    header @images Cache-Control "no-cache, must-revalidate"

    # 3. Code applicatif JS & CSS : rechargement immédiat sans mise en cache bloquante
    @code path *.css *.js *.mjs
    header @code Cache-Control "no-cache, must-revalidate"

    # 4. Pages HTML : revalidation systématique par ETag (aucun paramètre ?v= nécessaire).
    #    Le bloc @pages ci-dessous couvre les URLs SANS extension (/puzzles/2026-10-26/),
    #    que le motif *.html ne matcherait pas.
    @html path *.html
    header @html Cache-Control "no-cache, must-revalidate"

    @pages path / /puzzles /puzzles/* /play /play/* /battle /battle/* /multi /multi/* /defi /defi/*
    header @pages Cache-Control "no-cache, must-revalidate"

    @sitemap path /sitemap.xml /robots.txt /llms.txt /llms.md /agent-skills.md /.well-known/*
    header @sitemap Cache-Control "no-cache, must-revalidate"

    # Flux « Défier le bot » en direct (SSE) — chemin plus spécifique que /api/*
    # Un défi peut rester silencieux le temps que le worker le prenne : sans
    # flush_interval -1, Caddy met le flux en tampon et le navigateur ne reçoit
    # jamais les coups (le serveur émet pourtant un battement toutes les 10 s).
    handle /api/challenge/*/stream {
        header Cache-Control "no-store"
        reverse_proxy cemantix_web:8000 {
            flush_interval -1
            transport http {
                read_timeout 900s
            }
        }
    }

    # API du Solveur (prioritaire et exclusive)
    handle /api/* {
        header X-Robots-Tag "noindex, nofollow"
        reverse_proxy cemantix_web:8000
    }

    # Blocage des fichiers de données et de configuration, même s'ils venaient
    # à atterrir dans le webroot par erreur (défense en profondeur).
    @intercepted path /data.json /daily_history.json /web_sessions.json /multi_sessions.json /.env /.env.* /.git /*.py /*.pyc /*.log /*.bin
    respond @intercepted 404

    # Fichiers statiques et routes propres (/play, /battle, /multi)
    handle {
        try_files {path} {path}/index.html {path}/ /index.html
        file_server
    }

    encode zstd gzip
}
```

#### Synchronisation manuelle des données web :
Pour actualiser ou exporter manuellement les données du mot du jour à tout moment :
```bash
docker compose run --rm cemantix --export-web
```

---

## 🔎 SEO : Archives Quotidiennes Indexables & Sitemap

Le démon ne se contente plus d'afficher le mot du jour en JavaScript : il **publie du
contenu indexable** à chaque résolution. C'est ce qui permet de capter la longue traîne
« cemantix du 26 octobre 2026 », invisible tant que le contenu est rendu côté client.

```
volumes/web/
├── puzzles/
│   ├── index.html                     # Index paginé (60 archives par page)
│   ├── page/2/index.html              # Pages d'index suivantes
│   └── 2026-10-26/index.html          # Page dédiée au puzzle du jour
├── sitemap.xml                        # Régénéré avec le lastmod réel de chaque page
├── robots.txt                         # /api/, data.json et ?reveal= exclus de l'index
├── llms.txt                           # Découverte agents IA (H1 + liens, format canonique)
├── llms.md                            # Documentation longue pour agents IA
├── agent-skills.md                    # Protocole d'usage pour agent autonome (urn:air:agent-skills)
├── manifest.webmanifest               # PWA installable (shortcuts Solo & Archives)
└── .well-known/
    ├── ard.json                       # Manifeste ARD v0.91+ (auto-régénéré au démarrage)
    ├── ai-catalog.json                # Manifeste ARD 1.0 compatible Lighthouse (auto-régénéré)
    └── agent-card.json                # Carte d'agent A2A (auto-régénérée au démarrage)
```

### Ce que contient une page `/puzzles/AAAA-MM-JJ/`
- `<title>` et meta description datés (« Cémantix du lundi 26 octobre 2026… »), URL
  canonique, Open Graph et Twitter Card ;
- **tableau des 10 mots les plus proches** avec score en °C et similarité en ‰, rendu
  **côté serveur** donc lisible sans JavaScript ;
- la solution dans un bloc `<details>` dépliable (lisible par les moteurs, masquée au
  visiteur qui ne clique pas) ;
- JSON-LD `Article` (avec `datePublished` / `dateModified` réels) + `BreadcrumbList` ;
- navigation `rel="prev"` / `rel="next"` entre les jours et vers l'index des archives.

Les pages sont **auto-suffisantes** : les tokens de style sont extraits de
`css/variables.css` et injectés dans une balise `<style>`, donc aucune requête CSS
supplémentaire et un rendu correct même sans JS.

### Régénération automatique au démarrage & option `--publish-seo`
`volumes/web/sitemap.xml` et le dossier `volumes/web/puzzles/` sont volontairement exclus de Git (`.gitignore`) afin d'éviter tout conflit lors d'un `git pull` en production. En complément, les manifestes de découverte IA `volumes/web/.well-known/{ai-catalog,ard,agent-card}.json` sont eux aussi **générés et vérifiés automatiquement de manière atomique** (garantissant un schéma ARD toujours valide même après écrasement ou déploiement vierge) :
1. **À chaque démarrage de conteneur** (`cemantix_web` via `start_api_server()` et `cemantix_worker` via `run_daemon_loop()`), y compris sur une base vierge ou momentanément indisponible ;
2. **Après chaque résolution quotidienne de minuit** et lors d'un `--export-web` (même si l'écriture de `data.json` échoue) ;
3. **À la demande** via la commande dédiée :
```bash
docker compose run --rm cemantix --publish-seo
```

### Cache HTTP : cohérence avec la politique « no-cache »
Le projet applique `Cache-Control: "no-cache, must-revalidate"` sur le code applicatif
(voir l'encadré « Pourquoi aucun paramètre de version (`?v=...`) » plus haut) : la
revalidation se fait par ETag, ce qui rend les suffixes `?v=` inutiles. **Cette règle
doit rester la source de vérité** — il ne faut pas introduire de `max-age` sur les
fichiers qui changent, sous peine de devoir ressusciter les `?v=` pour forcer le
renouvellement.

Deux points de vigilance propres aux pages d'archives :

1. **Le sélecteur `@html path *.html` ne suffit pas.** Une URL comme
   `/puzzles/2026-10-26/` ne contient pas `.html` : Caddy la sert grâce à
   `try_files {path} {path}/index.html`, mais le motif `*.html` ne la **matche pas**.
   Sans règle explicite, ces pages partent donc sans `Cache-Control`. Ajoute ce bloc
   **avant** `@code` :

```caddy
    # Pages du site (URL sans extension servies via try_files) : même traitement que le HTML
    @pages path / /puzzles /puzzles/* /play /play/* /battle /battle/* /multi /multi/*
    header @pages Cache-Control "no-cache, must-revalidate"
```

2. **`sitemap.xml` doit être revalidé**, sinon Google peut continuer à pointer des URLs
   supprimées après une régénération :

```caddy
    @sitemap path /sitemap.xml /robots.txt /llms.txt /llms.md /agent-skills.md /.well-known/*
    header @sitemap Cache-Control "no-cache, must-revalidate"
```

> Le `max-age=86400` précédemment suggéré pour `/puzzles/*` est **abandonné** : une page
> d'archive est bien immuable en théorie, mais le générateur réécrit l'index paginé et
> les liens `prev`/`next` à chaque publication. Un `max-age` rendrait ces mises à jour
> invisibles pendant des heures sans benefit mesurable (les pages pèsent 13 ko).

### Feuilles de style et modules JavaScript
Pour éliminer toute requête CSS bloquante au premier rendu mobile (LCP/FCP), chaque page embarque directement son **CSS critique minifié** dans `<style id="critical-css">` et charge `css/dist/modal.css` de façon différée (`media="print"` activé en JS, conforme `script-src 'self'`) :

```bash
python tools/build_css_bundles.py     # régénère css/dist/*.css et synchronise <style id="critical-css">
python tools/build_css_bundles.py --check   # échoue si un bundle ou un bloc inline est périmé
```

À faire **après chaque modification d'un fichier de `css/`**, avant de déployer.
Les sources (`variables.css`, `base.css`, …) et les bundles `css/dist/*.css` restent dans le dépôt : `src/services/seo.py` injecte également les tokens et `css/dist/puzzle.css` dans les pages d'archives `/puzzles/*`, qui n'emploient aucun lien CSS externe.

Côté JavaScript, `js/app.js` charge `dashboard.js` et `game.js` en `import()` dynamique :
un module n'est téléchargé et évalué que si la vue correspondante est présente dans le
DOM. `/battle/` et `/multi/` ont leur propre point d'entrée et ne passent pas par `app.js`.

### Image de partage optimisée (PERF-08)
L'image de prévisualisation sociale `volumes/web/og-image.jpg` est calibrée exactement aux dimensions recommandées Open Graph **1200×630**, pour un poids réduit de 3,09 Mo à **172 ko** (qualité 82). Son intégrité, ses dimensions et son seuil de poids (< 200 ko) sont vérifiés automatiquement en intégration continue par le script de contrôle dédié :

```bash
python tools/check_og_image.py     # valide les dimensions exactes 1200x630 et le poids sous 200 ko
```

### Icônes du site
Les icônes PNG (`apple-touch-icon.png`, `icon-512.png`) sont générées par un script sans
dépendance externe (stdlib Python uniquement) :
```bash
python tools/generate_icons.py
```

### Outillage de Contrôle Automatisé (`tools/`)
Le dossier `tools/` fournit des scripts de contrôle qualité autonomes, branchés dans la pipeline CI GitHub Actions :
- `tools/check_docs.py` : Contrôle la cohérence des documents (absence de liens relatifs cassés, validité des tableaux markdown et alignement des compteurs de la roadmap).
- `tools/check_seo.py` : Valide la présence et la conformité des balises SEO indispensables sur toutes les pages (`<title>`, meta description, canonical absolu, Open Graph, JSON-LD) ainsi que le schéma ARD des manifestes `.well-known/{ai-catalog,ard}.json`.
- `tools/check_og_image.py` : Vérifie que `og-image.jpg` respecte le gabarit 1200×630 et le plafond de 200 ko.
- `tools/check_headers.sh` : Analyse les 6 en-têtes de sécurité HTTP sur le serveur web en production.
- `tools/build_css_bundles.py` : Regroupe et minifie prudemment les feuilles de style dans `css/dist/*.css` et synchronise les blocs `<style id="critical-css">` des 4 pages HTML (avec mode `--check` bloquant en CI).

## 🔐 Sécurité

### Le mot secret ne transite jamais sans action volontaire
Le point le plus sensible du projet : la solution du jour. Elle est désormais
**absente de toute réponse `GET`**.

```
GET  /api/daily            → current.word = null, mot masqué dans trajectory,
                             top_guesses et l'entrée du jour de l'historique
POST /api/daily/reveal     → { "word": "…" }   seul chemin vers la solution
```

Le POST est choisi exprès : un crawler, un prefetch de lien ou un `curl` ne peuvent
pas récupérer la solution par accident. Le bouclier anti-spoiler n'est plus du CSS,
il est côté serveur.

`export_web_data()` refuse par ailleurs d'écrire `data.json` dans le webroot : le
fichier contient l'historique complet des solutions et se serait récupéré d'un
`curl https://…/data.json`.

### En-têtes et restrictions réseau de l'API
| Protection | Mise en œuvre | Variable d'environnement |
|---|---|---|
| Corps de requête | Refus au-delà de 32 ko (`413`), **avant** lecture du corps | `API_MAX_BODY_BYTES` |
| CORS | Liste blanche d'origine, plus de `*`, `Vary: Origin` | `API_ALLOWED_ORIGIN` |
| Débit | Seau à jetons par IP, `429` + `retry_after` ; `/api/health` exempté | — |
| Threads | Plafond de workers, `503` propre au lieu d'une création sans limite | `API_MAX_WORKERS` |
| Blocage | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` | — |
| Cache | `Cache-Control: no-store` sur toutes les réponses d'API | — |
| Silences | Version Python retirée de l'en-tête `Server`, timeout socket 10 s | `API_SOCKET_TIMEOUT` |

### Sanitisation serveur stricte des pseudonymes (SEC-01)
Tous les pseudonymes saisis en multijoueur font l'objet d'un nettoyage strict côté serveur via la fonction `sanitize_player_name()` dans `src/api/routes/multi.py` :
- Rejet systématique de toute balise HTML, balise `<script>` ou caractère de contrôle avant persistance.
- Filtrage par expression régulière stricte (`[^\w \-À-ÿ'.]`) et limitation impérative à 24 caractères.
- Toute tentative d'injection entraîne un refus immédiat en HTTP `400 Bad Request`.

### XSS : échappement côté rendu et fin des gestionnaires inline (SEC-01b & SEC-02)
Aucune donnée extérieure n'est injectée brute dans `innerHTML`. Le helper
`escapeHtml()` de `js/utils.js` est appliqué aux mots, dates, numéros de puzzle,
identifiants de salon et pseudonymes d'adversaire.

Les gestionnaires construits par concaténation (`onclick="copyToClipboard('${mot}')"`)
ont été supprimés au profit d'attributs `data-*` et d'une délégation d'événements :
une apostrophe dans un mot ou un pseudonyme ne peut plus fermer la chaîne et exécuter
de code.

Les quatre fonctions que ces `onclick` appelaient étaient exposées sur `window`
(`copyToClipboard`, `showConfirmDialog`, `multiResumeGame`, `multiDeleteGame`). Elles n'ont
plus aucun appelant global — plus aucun `onclick=` ne subsiste dans les quatre pages — et
ont été rendues locales à leur module. Cette surface globale était le dernier point qui
rendrait une CSP `script-src 'self'` intenable si un `onclick` inline réapparaissait.

### Résilience & Pool de connexions PostgreSQL borné (PERF-06)
La couche d'accès aux données (`src/db/connection.py`) implémente un pool de connexions réutilisables thread-safe borné (par défaut 8 connexions simultanées maximum via `DB_POOL_MAX`). Cette limitation protège le serveur PostgreSQL de toute saturation :
- Validé sous stress-test avec 400 threads concurrents sans aucune erreur de saturation `too many clients`.
- Élimination des vérifications réseau superflues (`SELECT 1`) grâce à une fenêtre d'inactivité de 30 secondes (`DB_CONN_MAX_IDLE`).
- Repli SQLite transparent automatique si aucune instance PostgreSQL n'est configurée (tests unitaires et développement local).

### Codes du multijoueur & Hachage cryptographique
Les `room_id` sont générés sur 8 caractères hexadécimaux et les clés joueurs sur **24 caractères hexadécimaux** (`secrets.token_hex(12)`, 96 à 128 bits d'entropie). En base de données (`multi_rooms`), les clés ne sont jamais conservées en clair : elles sont hachées cryptographiquement par `HMAC-SHA256(SECRET_KEY, key)` dès leur enregistrement (`SEC-05b`).

### Protection des conteneurs & Isolation non-root
L'image applicative s'exécute sous un utilisateur dédié non-root `cemantix` (UID 1000). Le fichier `docker-compose.yml` applique `no-new-privileges: true` et abandonne toutes les capacités Linux (`cap_drop: [ALL]`).

### Respect de la vie privée & RGPD
- **Anonymisation des journaux** : Les adresses IP sont systématiquement tronquées en sous-réseaux `/24` (IPv4) ou `/48` (IPv6) avant toute journalisation HTTP (`RGPD-03`).
- **Pseudonymes** : Aucun pseudonyme de joueur n'est inscrit dans les logs d'accès serveur, et les salons inactifs sont automatiquement purgés après 7 jours (`RGPD-01`).
- **Traceurs & Cookies** : Aucun cookie publicitaire tiers n'est déposé. Le cookie de révélation anti-triche est strictement nécessaire au fonctionnement de l'application et exempt de consentement préalable ePrivacy (`RGPD-02`).

### La clé de salon ne reste pas dans l'URL

Le lien d'invitation `/multi/?r=DUEL-XXXXXXXX&k=J2-YYYYYYYY` doit contenir la clé —
c'est ce qui permet au second joueur d'entrer. Mais rien ne justifie qu'il **y reste** :
une clé laissée dans la barre d'adresse survit dans l'historique du navigateur, dans le
champ d'URL, dans les captures d'écran, et reste cliquable des heures plus tard — sur un
ordinateur partagé, c'est une prise de contrôle du duel.

```
chargement de /multi/?r=…&k=…   → la clé est lue en mémoire, puis retirée de l'URL
                                  l'URL devient /multi/?r=…  (le code de salon seul
                                  n'autorise aucune action)
polling de l'état               → POST /api/multi/status  (corps de requête)
GET  /api/multi/*               → 404, la voie est fermée côté serveur
```

Le `GET /api/multi/status?r=…&k=…` est supprimé : une query string se retrouve dans la
ligne de requête transmise au proxy. Le `POST` équivalent existait déjà et transporte la
même charge utile.

### À vérifier après le déploiement
```bash
# Le mot du jour ne doit apparaître nulle part :
curl -s https://cemantix.cyril-randon.fr/api/daily | grep -i '"word"' | head

# Les fichiers de données doivent renvoyer 404 :
for f in data.json daily_history.json web_sessions.json; do
  printf '%s -> ' "$f"
  curl -s -o /dev/null -w '%{http_code}\n' "https://cemantix.cyril-randon.fr/$f"
done

# Les en-têtes doivent être présents :
curl -sI https://cemantix.cyril-randon.fr/ | grep -iE 'content-security|strict-transport|x-frame'
```

### Après la mise en production
1. Soumettre `https://cemantix.cyril-randon.fr/sitemap.xml` dans Google Search Console
   et Bing Webmaster Tools ;
2. vérifier le rendu avec « Inspection de l'URL » puis « Test d'affichage en temps
   réel » : les pages d'archives doivent s'afficher sans JavaScript ;
3. contrôler les données structurées sur <https://validator.schema.org>.


---

## ⚙️ Options en Ligne de Commande

| Option | Type | Défaut | Description |
| :--- | :---: | :---: | :--- |
| `--daemon` | Flag | `False` | Lance le mode démon 24h/24 : reste en veille et résout le mot du jour chaque nuit à 00h00 (Europe/Paris). |
| `--no-run-on-start` | Flag | `False` | En mode démon, ne résout pas immédiatement si non résolu, attend le cycle de 00h00. |
| `--export-web` | Flag | `False` | Exporte `data.json` pour le serveur web et régénère les pages d'archives SEO, `sitemap.xml` et `.well-known/*.json`. |
| `--publish-seo` | Flag | `False` | Régénère uniquement les pages `/puzzles/<date>/`, l'index paginé, `sitemap.xml` et `.well-known/*.json` depuis l'historique. |
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

## 💡 Notes de Déploiement & Environnement

### Stockage PostgreSQL sous WSL / Windows (QUAL-12)
Les volumes PostgreSQL **ne doivent pas** être montés directement sur le système de fichiers hôte Windows (`/mnt/c/...` sous WSL) : le pilote de partage `drvfs`/`9p` ne gère pas les permissions POSIX exigées par `initdb` (`chmod: Operation not permitted`). 
Le projet utilise donc un volume Docker nommé `cemantix_db_data` (ext4 interne Docker) pour garantir la stabilité et la performance du moteur relationnel.

### Proxy d'entreprise & Variables Docker (QUAL-11)
Si un proxy d'entreprise est configuré sur l'hôte Docker (`~/.docker/config.json`), le démon Docker peut injecter `http_proxy` en minuscules dans l'environnement des conteneurs. Pour éviter que `requests` ne contourne les exceptions locales, les variables doivent être définies en **deux casses** (`HTTP_PROXY` et `http_proxy`) ou neutralisées explicitement pour les services purement internes.

### Permissions POSIX du volume `cemantix_data` & ChromaDB (UID 1000)
Les conteneurs de production `cemantix_worker` et `cemantix_web` appliquent le principe de moindre privilège (`SEC-13`) : exécution sous l'utilisateur non-root `1000:1000`, `read_only: true` sur le système de fichiers racine, et abandon de toutes les capacités Linux (`cap_drop: - ALL`).

Lorsque Docker monte le volume hôte `./cemantix_data` dans `/app/cemantix_data`, les permissions de l'hôte s'appliquent directement dans le conteneur. Si le répertoire `cemantix_data/chroma_w2v/` a été initialisé ou touché par `root` sur l'hôte, la base SQLite de ChromaDB ne peut pas créer ses fichiers temporaires de verrouillage (`chroma.sqlite3-wal` et `-shm`) et échoue avec l'erreur :
```text
ChromaDB non chargé (error returned from database: (code: 8) attempt to write a readonly database).
```
Pour garantir le bon fonctionnement de ChromaDB et le traitement des défis sans blocage, s'assurer que le répertoire appartient à l'UID 1000 :
```bash
sudo chown -R 1000:1000 ./cemantix_data
```

---

## 🌐 Variables d'Environnement

Ces variables peuvent être définies dans votre shell ou dans un fichier `.env` (voir `.env.example`) :

| Variable | Défaut | Description |
| :--- | :--- | :--- |
| `DB_HOST` | `cemantix_db` | Nom d'hôte du conteneur ou serveur PostgreSQL. |
| `DB_PORT` | `5432` | Port de la base relationnelle PostgreSQL. |
| `DB_NAME` | `cemantix` | Nom de la base de données relationnelle. |
| `DB_USER` | `cemantix_user` | Utilisateur de connexion PostgreSQL. |
| `DB_PASS` | `—` | Mot de passe sécurisé de la base PostgreSQL. |
| `DB_POOL_MAX` | `8` | Nombre maximal de connexions simultanées dans le pool relationnel (PERF-06). |
| `DB_POOL_TIMEOUT` | `10` | Secondes d'attente maximale avant levée d'exception si le pool est saturé. |
| `DB_CONN_MAX_IDLE` | `30` | Secondes pendant lesquelles une connexion réutilisée est valide sans requêtes réseau superflues. |
| `SQLITE_PATH` | `cemantix_data/cemantix.sqlite3` | Chemin du fichier de repli SQLite automatique si PostgreSQL est absent. |
| `TZ` | `Europe/Paris` | Fuseau horaire officiel pour le planificateur de veille 00h00. |
| `LM_API` | `http://host.docker.internal:1234/v1` (ou `http://localhost:1234/v1`) | URL de l'API OpenAI compatible de LM Studio. |
| `LLM_MODEL` | `qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2` | Identifiant du modèle chargé dans LM Studio. |
| `W2V_FILE` | `frWac_no_postag_phrase_500_cbow_cut10.bin` | Nom du fichier word2vec hébergé sur embeddings.net. |
| `API_ALLOWED_ORIGIN` | `https://cemantix.cyril-randon.fr` | Origine(s) autorisée(s) par le CORS, séparées par des virgules. À changer si vous changez de domaine. |
| `API_MAX_BODY_BYTES` | `32768` | Taille maximale acceptée pour le corps d'une requête `POST` (au-delà : `413`). |
| `API_MAX_WORKERS` | `64` | Nombre maximal de requêtes traitées en parallèle par le serveur d'API. |
| `API_SOCKET_TIMEOUT` | `10` | Timeout de socket en secondes, libère les connexions dormantes. |
| `ADMIN_PASSWORD` | `—` | Mot de passe de la console d'exploitation `/panier-9x/` (vide = routes désactivées 403). |
| `ADMIN_API_PATH` | `/api/snap-9x` | Préfixe d'accès sécurisé pour l'API de supervision de la console. |
| `DOCKER_GID` | `120` | GID propriétaire du socket `/var/run/docker.sock` autorisant les logs sous utilisateur non-root. |
| `DASHBOARD_DATA_FILE` | `cemantix_data/data.json` | Emplacement de `data.json`. **Ne doit pas** pointer dans `volumes/web` (refusé par `export_web_data`). |

---

## 📁 Arborescence du Projet

```
cemantix-rag-solver/
├── cemantix_rag.py          # Point d'entrée CLI et orchestration générale
├── requirements.txt         # Dépendances Python (NumPy, ChromaDB, Requests, Psycopg 3)
├── Dockerfile               # Image conteneurisée prête à l'emploi (tzdata, Python 3.12)
├── docker-compose.yml       # Déploiement 3-tiers durci (cemantix_db, cemantix_worker, cemantix_web)
├── .github/                 # Workflows d'intégration continue (CI tests, lint, audit, Lighthouse)
│   └── workflows/ci.yml     # Pipeline automatisée GitHub Actions
├── local/                   # Environnement local de test et outillage d'évaluation (smoke-test, test compose)
├── tools/                   # Scripts de contrôle automatisé (check_docs.py, check_og_image.py, build_css_bundles.py)
├── .env.example             # Gabarit des variables d'environnement de production
├── .gitignore               # Exclut les fichiers binaires volumineux, Caddyfile et caches
├── .dockerignore            # Optimisation du contexte de build Docker (< 800 ko)
├── README.md                # Documentation complète du projet
├── CHANGELOG.md             # Historique des versions et refactorings
├── database/                # Schémas SQL relationnels
│   └── init.sql             # DDL PostgreSQL officiel (daily_puzzles, multi_rooms, solo_sessions)
├── scripts/                 # Scripts d'exploitation et de migration
│   └── migrate_json_to_pg.py# Migration d'historique daily_history.json vers PostgreSQL
├── volumes/                 # Volumes partagés
│   ├── db/data/             # Données persistantes PostgreSQL
│   └── web/                 # Application web servie par Caddy (mot du jour, jeu & API)
│       ├── index.html       # Tableau de bord principal (URL : /)
│       ├── play/            # Interface de jeu interactif Solo (URL : /play/)
│       │   └── index.html   # Page de jeu (défi du jour, illimité)
│       ├── battle/          # Arène de duel tour par tour contre l'IA (URL : /battle/)
│       │   └── index.html   # Page Mode Battle (versus IA, double jauge, indices)
│       ├── multi/           # Mode Multijoueur 1v1 entre amis (URL : /multi/)
│       │   └── index.html   # Page Multijoueur (Même Mot, Mots Choisis, lien direct)
│       ├── css/             # Styles atomiques et bundles optimisés par page (dist/)
│       ├── js/              # Modules JavaScript atomiques (app, utils, render, game, battle, multi...)
│       ├── .well-known/     # Manifestes ARD et A2A auto-régénérés (ard.json, ai-catalog.json, agent-card.json)
│       ├── robots.txt       # Directives d'exploration pour les moteurs de recherche
│       └── sitemap.xml      # Plan de site XML généré automatiquement au démarrage des conteneurs (hors Git)
├── cemantix_data/           # Cache local (lexique_fr.txt, modèles w2v, ChromaDB)
│   ├── lexique_fr.txt       # Dictionnaire de référence (46 272 lemmes officiels)
│   └── daily_history.json   # Historique persistant des résolutions quotidiennes (miroir)
└── src/                     # Architecture modulaire découplée
    ├── __init__.py          # Expose les classes et fonctions du package avec rétrocompatibilité
    ├── config.py            # Constantes, styles ANSI, chemins et configuration LLM
    ├── db/                  # Couche d'accès aux données PostgreSQL / SQLite thread-safe
    │   ├── __init__.py      # Exports des services de persistance
    │   ├── connection.py    # Pool de connexions borné (PERF-06), transactions et bascule SQLite
    │   ├── daily.py         # Persistance, requêtes agrégées SQL et consultation des puzzles
    │   ├── multi.py         # Gestion relationnelle des salons 1v1 avec hachage HMAC des clés
    │   └── solo.py          # Sauvegarde et reprise des sessions de jeu solo
    ├── engine/              # Moteur mathématique, RAG & clients réseau (Core Engine)
    │   ├── __init__.py      # Point d'entrée et exports du moteur
    │   ├── vocab.py         # VocabStore (lexique Lexique383, vecteurs frWac, import paresseux ChromaDB)
    │   ├── clients.py       # Clients API Cémantix officiel (IPv4/retry) & local (MockClient)
    │   ├── solvers.py       # Régression Ridge, Rerank, interface LLM & solveurs (Solver, RagDuelPlayer)
    │   ├── english_stopwords.txt # Stopwords anglais parasites purs découplés (QUAL-09)
    │   └── prompt_template.txt   # Gabarit de prompt pour l'hybride LLM découplé (QUAL-09)
    ├── game/                # Moteurs de jeu purs et gestionnaires de session (Domain Layer)
    │   ├── __init__.py      # Point d'accès et ré-exports des sessions
    │   ├── common.py        # Utilitaires partagés (météo sémantique, fichiers de persistance)
    │   ├── solo.py          # Moteur de session Solo & Défi du Jour (GameSession)
    │   ├── battle.py        # Moteur de duel Joueur vs Bot IA (BattleSession)
    │   ├── multi.py         # Moteur de salon et tours Multijoueur 1v1 (MultiplayerSession)
    │   └── manager.py       # Gestionnaire d'état, persistance relationnelle O(1) et pools (GameManager)
    ├── api/                 # Couche d'exposition HTTP & API REST modulaire (Web API)
    │   ├── __init__.py      # Point d'accès du paquet API & exports rétrocompatibles
    │   ├── server.py        # Serveur HTTP, parsing JSON, ratelimit, anonymisation IP /24 et logs
    │   └── routes/          # Contrôleurs HTTP découplés par domaine
    │       ├── __init__.py  # Point d'accès unifié des routes
    │       ├── system.py    # Métriques système, cache mémoire et ETag 304 (/api/health, /api/daily)
    │       ├── solo.py      # Contrôleur du Mode Solo (/api/game/*)
    │       ├── battle.py    # Contrôleur du Mode Battle IA (/api/battle/*)
    │       └── multi.py     # Contrôleur du Mode Multijoueur 1v1 (/api/multi/*)
    ├── cli/                 # Interface en ligne de commande & Terminal UI (Console UX)
    │   ├── __init__.py      # Point d'entrée du package CLI
    │   ├── ui.py            # Rendu console, jauges ASCII, dashboard duel & débriefing
    │   ├── menu.py          # Menu interactif textuel avec configuration dynamique
    │   └── modes.py         # Boucles d'exécution interactives (solo, duel, battle, benchmark)
    └── services/            # Services d'arrière-plan & synchronisation (Background Services)
        ├── __init__.py      # Point d'entrée des services
        ├── daemon.py        # Démon planificateur 24h/24 (veille, heartbeat threadé et résolution quotidienne)
        ├── web.py           # Générateur et exportateur de données web avec masquage anti-spoiler
        └── seo.py           # Génération atomique des archives /puzzles/, sitemap.xml et manifestes ARD .well-known/
```

---

## ⚖️ Licence

Ce projet est distribué sous licence MIT. Les vecteurs pré-entraînés `frWac` proviennent des travaux de Jean-Philippe Fauconnier (*French Web as Corpus*).
