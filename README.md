# 🎯 Cémantix RAG Solver — IA & Régression Géométrique

Solveur haute performance pour le jeu sémantique [Cémantix](https://cemantix.certitudes.org/).

Ce projet implémente deux approches d'Intelligence Artificielle en compétition :
1. ⚡ **100% RAG Mathématique Pur** : Estimation analytique par régression Ridge de la direction du mot secret dans l'espace vectoriel, reranking géométrique multi-indices et détection vectorielle directe (*Sniper RAG*). **Zéro appel LLM, zéro GPU requis, résolution en moins d'une seconde.**
2. 🤖 **Hybride RAG + Local LLM** : Coopération itérative entre l'espace vectoriel et un LLM local (via [LM Studio](https://lmstudio.ai/)) pour explorer le champ lexical et affiner les hypothèses sémantiques.
3. ⚔️ **Mode Battle** : Tournoi en face-à-face sur $N$ manches comparant rigoureusement les deux approches sur le **même mot secret** et avec les **mêmes mots graines** de départ.
4. ⏰ **Démon 24h/24 & Veille Quotidienne** : Fonctionnement permanent en conteneur Docker en mode sommeil, réveil automatique chaque nuit à 00h00 (heure de Paris) pour trouver le mot officiel du jour dès sa parution et historisation automatique.
5. 🌐 **Page Web & Publication Caddy** : Interface web moderne et réactive servant le mot du jour en direct depuis le volume obligatoire ./volumes/web (protection anti-spoiler, thermomètre sémantique, compte à rebours minuit et KPIs).

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

### Option B : Déploiement avec Docker

Le conteneur Docker isole l'environnement et monte un volume hôte pour conserver les données vectorielles entre les exécutions.

#### 1. Construire l'image Docker
```bash
docker compose build
```

#### 2. Lancement du Démon 24h/24 (Veille Permanente & Résolution à 00h00)
Le conteneur est configuré par défaut pour tourner en tâche de fond permanente (`restart: unless-stopped`). Il se met en sommeil léger et se réveille chaque nuit à **00h00 (heure de Paris)** pour résoudre le mot du jour en mode RAG pur :

```bash
# Lancer le démon en arrière-plan :
docker compose up -d

# Suivre les logs de veille et les résolutions en temps réel :
docker compose logs -f cemantix

# Arrêter proprement le démon :
docker compose down
```

> [!NOTE]
> - **Historique automatique** : Chaque mot trouvé est consigné dans `./cemantix_data/daily_history.json` (date, numéro du puzzle, mot secret, nombre d'essais, durée).
> - **Rattrapage au démarrage** : Si le mot d'aujourd'hui n'a pas encore été résolu, le démon le trouve dès le démarrage avant de s'endormir jusqu'au prochain minuit.

#### 3. Lancer une commande ponctuelle ou interactive
Sans arrêter le démon, vous pouvez exécuter n'importe quelle commande interactive ou de test :

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
├── css/              # Feuilles de style atomiques
│   ├── variables.css # Thèmes clair/sombre, tokens de couleurs et dégradés thermiques
│   ├── base.css      # Reset, boutons, badges, cartes et notifications toast
│   ├── layout.css    # En-tête, navigation par onglets et pied de page fixe
│   ├── dashboard.css # Styles du tableau de bord, thermomètre et guide SEO
│   ├── game.css      # Styles de l'interface de jeu, saisie et spotlight
│   ├── battle.css    # Styles dédiés au duel contre l'IA
│   ├── multi.css     # Styles dédiés au multijoueur 1v1 et arène de duel
│   └── modal.css     # Modales de configuration, débriefing et confirmation
├── js/               # Modules JavaScript atomiques (ES Modules)
│   ├── app.js        # Point d'entrée léger et initialisation ciblée
│   ├── utils.js      # Formatage, dates, presse-papier, helpers
│   ├── theme.js      # Gestion du thème clair/sombre et protection anti-spoiler
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

#### Configuration Caddy (Production & Anti-Cache Automatique) :
Dans votre conteneur Caddy ou votre machine hôte, pointez la racine sur `./volumes/web` et appliquez la politique de cache HTTP optimisée.

> [!TIP]
> **Pourquoi aucun paramètre de version (`?v=...`) dans le code HTML/JS ?**
> Les paramètres de requête manuels (`?v=202610...`) sont proscrits : ils compliquent les imports ES modules imbriqués et sont redondants avec les capacités natives de Caddy / Nginx. En configurant `Cache-Control: "no-cache, must-revalidate"` sur les fichiers `.js` et `.css`, le navigateur valide automatiquement l'empreinte ETag du fichier auprès du serveur. Dès qu'un `git pull` met à jour un fichier sur disque, le navigateur reçoit instantanément la nouvelle version sans nécessiter de purge manuelle de cache (`Ctrl+F5`).

```caddy
cemantix.cyril-randon.fr {
    root * /volumes/web

    # En-têtes de sécurité (toutes les réponses)
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        Cross-Origin-Opener-Policy "same-origin"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"

        # Politique de sécurité du contenu. Le site n'utilise AUCUNE ressource externe
        # (ni CDN, ni police, ni script tiers) : la politique peut donc être
        # restrictive. 'unsafe-inline' pour les styles est nécessaire car les feuilles
        # de style sont locales et les style="…" posés par le JS sont des valeurs codées
        # en dur, jamais des données utilisateur.
        # script-src 'self' suffit : seul js/app.js (module ES local) est chargé, donc
        # tout <script> injecté par une faille XSS est bloqué par le navigateur.
        Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; manifest-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; object-src 'none'"
    }

    # Pages d'archives : contenu statique, aucun script ni connexion sortante.
    header /puzzles/* {
        Content-Security-Policy "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    }

    # 1. Polices web immuables (cache 1 an)
    @fonts path *.woff *.woff2
    header @fonts Cache-Control "public, max-age=31536000, immutable"

    # 2. Images revalidées automatiquement (cache 24h avec ETag)
    @images path *.ico *.png *.jpg *.jpeg *.webp *.svg
    header @images Cache-Control "public, max-age=86400, must-revalidate"

    # 3. Code applicatif JS & CSS : rechargement immédiat sans mise en cache bloquante
    @code path *.css *.js *.mjs
    header @code Cache-Control "no-cache, must-revalidate"

    # 4. Pages HTML : revalidation rapide
    @html path *.html
    header @html Cache-Control "public, max-age=3600, must-revalidate"

    # API du Solveur (prioritaire et exclusive)
    handle /api/* {
        reverse_proxy cemantix_solver:8000
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
├── llms.md                            # Documentation pour agents IA (standard llms)
├── manifest.webmanifest               # PWA installable (shortcuts Solo & Archives)
└── .well-known/ai-catalog.json        # Découverte ARD (endpoint non spoilant)
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

### Régénérer uniquement le SEO
```bash
docker compose run --rm cemantix --publish-seo
```
La publication est aussi déclenchée automatiquement par `--export-web` et par le démon
après chaque résolution de minuit. En cas d'échec, le log signale l'erreur sans bloquer
l'export de `data.json`.

### Cache HTTP des pages d'archives
Une page `/puzzles/<date>/` ne change plus jamais une fois publiée : elle peut être
cachée longtemps, alors que l'accueil et `sitemap.xml` doivent être revalidés. Ajoutez
ces deux règles **avant** le bloc `@code` existant de votre `Caddyfile` :

```caddy
    # 5. Archives quotidiennes : immuables une fois publiées
    @archives path /puzzles/*
    header @archives Cache-Control "public, max-age=86400, must-revalidate"

    # 6. Sitemap : revalidation systématique
    @sitemap path /sitemap.xml
    header @sitemap Cache-Control "public, max-age=600, must-revalidate"
```

### Icônes du site
Les icônes PNG (`apple-touch-icon.png`, `icon-512.png`) sont générées par un script sans
dépendance externe (stdlib Python uniquement) :
```bash
python tools/generate_icons.py
```

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

### XSS : échappement côté rendu
Aucune donnée extérieure n'est injectée brute dans `innerHTML`. Le helper
`escapeHtml()` de `js/utils.js` est appliqué aux mots, dates, numéros de puzzle,
identifiants de salon et pseudonymes d'adversaire.

Les gestionnaires construits par concaténation (`onclick="copyToClipboard('${mot}')"`)
ont été supprimés au profit d'attributs `data-*` et d'une délégation d'événements :
une apostrophe dans un mot ou un pseudonyme ne peut plus fermer la chaîne et exécuter
de code.

### Codes du multijoueur
Les `room_id` et clés `J1-` / `J2-` sont générés sur **8 chiffres hexadécimaux**
(`uuid.uuid4`, aléatoire cryptographique), soit 4,3 milliards de valeurs. À 4
caractères, les 65 536 combinaisons se parcouraient par balayage, et les salons
restaient ouverts 7 jours.

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
| `--export-web` | Flag | `False` | Exporte `data.json` pour le serveur web et régénère les pages d'archives SEO + `sitemap.xml`. |
| `--publish-seo` | Flag | `False` | Régénère uniquement les pages `/puzzles/<date>/`, l'index paginé et `sitemap.xml` depuis l'historique. |
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
| `TZ` | `Europe/Paris` | Fuseau horaire officiel pour le planificateur de veille 00h00. |
| `LM_API` | `http://host.docker.internal:1234/v1` (ou `http://localhost:1234/v1`) | URL de l'API OpenAI compatible de LM Studio. |
| `LLM_MODEL` | `qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2` | Identifiant du modèle chargé dans LM Studio. |
| `W2V_FILE` | `frWac_no_postag_phrase_500_cbow_cut10.bin` | Nom du fichier word2vec hébergé sur embeddings.net. |
| `API_ALLOWED_ORIGIN` | `https://cemantix.cyril-randon.fr` | Origine(s) autorisée(s) par le CORS, séparées par des virgules. À changer si vous changez de domaine. |
| `API_MAX_BODY_BYTES` | `32768` | Taille maximale acceptée pour le corps d'une requête `POST` (au-delà : `413`). |
| `API_MAX_WORKERS` | `64` | Nombre maximal de requêtes traitées en parallèle par le serveur d'API. |
| `API_SOCKET_TIMEOUT` | `10` | Timeout de socket en secondes, libère les connexions dormantes. |
| `DASHBOARD_DATA_FILE` | `cemantix_data/data.json` | Emplacement de `data.json`. **Ne doit pas** pointer dans `volumes/web` (refusé par `export_web_data`). |

---

## 📁 Arborescence du Projet

```
cemantix-rag-solver/
├── cemantix_rag.py          # Point d'entrée CLI et orchestration générale
├── requirements.txt         # Dépendances Python (NumPy, ChromaDB, Requests)
├── Dockerfile               # Image conteneurisée prête à l'emploi (tzdata, Python 3.12)
├── docker-compose.yml       # Configuration Docker Daemon (restart: unless-stopped)
├── .gitignore               # Exclut les fichiers binaires volumineux et caches
├── README.md                # Documentation complète du projet
├── CHANGELOG.md             # Historique des versions et refactorings
├── volumes/                 # Volumes partagés
│   └── web/                 # Application web servie par Caddy (mot du jour, jeu & API)
│       ├── index.html       # Tableau de bord principal (URL : /)
│       ├── play/            # Interface de jeu interactif Solo (URL : /play/)
│       │   └── index.html   # Page de jeu (défi du jour, illimité)
│       ├── battle/          # Arène de duel tour par tour contre l'IA (URL : /battle/)
│       │   └── index.html   # Page Mode Battle (versus IA, double jauge, indices)
│       ├── multi/           # Mode Multijoueur 1v1 entre amis (URL : /multi/)
│       │   └── index.html   # Page Multijoueur (Même Mot, Mots Choisis, lien direct)
│       ├── css/             # Styles atomiques (variables, base, layout, dashboard, game, battle, multi, modal)
│       ├── js/              # Modules JavaScript atomiques (app, utils, theme, game, battle, multi, dashboard...)
│       ├── robots.txt       # Directives d'exploration pour les moteurs de recherche
│       └── sitemap.xml      # Plan de site XML officiel pour l'indexation Google
├── cemantix_data/           # Cache local (lexique_fr.txt, modèles w2v, ChromaDB)
│   ├── lexique_fr.txt       # Dictionnaire de référence (46 272 lemmes officiels)
│   └── daily_history.json   # Historique persistant des résolutions quotidiennes
└── src/                     # Architecture modulaire découplée
    ├── __init__.py          # Expose les classes et fonctions du package avec rétrocompatibilité
    ├── config.py            # Constantes, styles ANSI, chemins et configuration LLM
    ├── engine/              # Moteur mathématique, RAG & clients réseau (Core Engine)
    │   ├── __init__.py      # Point d'entrée et exports du moteur
    │   ├── vocab.py         # VocabStore (lexique Lexique383, vecteurs frWac, ChromaDB)
    │   ├── clients.py       # Clients API Cémantix officiel (IPv4/retry) & local (MockClient)
    │   └── solvers.py       # Régression Ridge, Rerank, interface LLM & solveurs (Solver, RagDuelPlayer)
    ├── game/                # Moteurs de jeu purs et gestionnaires de session (Domain Layer)
    │   ├── __init__.py      # Point d'accès et ré-exports des sessions
    │   ├── common.py        # Utilitaires partagés (météo sémantique, fichiers de persistance)
    │   ├── solo.py          # Moteur de session Solo & Défi du Jour (GameSession)
    │   ├── battle.py        # Moteur de duel Joueur vs Bot IA (BattleSession)
    │   ├── multi.py         # Moteur de salon et tours Multijoueur 1v1 (MultiplayerSession)
    │   └── manager.py       # Gestionnaire d'état, persistance disque et pools (GameManager)
    ├── api/                 # Couche d'exposition HTTP & API REST modulaire (Web API)
    │   ├── __init__.py      # Point d'accès du paquet API & exports rétrocompatibles
    │   ├── server.py        # Serveur HTTP, parsing JSON, gestion CORS & cycle de vie
    │   └── routes/          # Contrôleurs HTTP découplés par domaine
    │       ├── __init__.py  # Point d'accès unifié des routes
    │       ├── system.py    # Métriques système et données web (/api/health, /api/daily)
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
        ├── daemon.py        # Démon planificateur 24h/24 (veille et résolution quotidienne à 00h00)
        └── web.py           # Générateur et exportateur de données web pour Caddy/Nginx (data.json)
```

---

## ⚖️ Licence

Ce projet est distribué sous licence MIT. Les vecteurs pré-entraînés `frWac` proviennent des travaux de Jean-Philippe Fauconnier (*French Web as Corpus*).
