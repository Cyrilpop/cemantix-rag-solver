# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-25

### Ajouté
- **Mode Multijoueur 1v1 Tour par Tour (`/multi/`)** :
  - **Moteur de duel multijoueur asynchrone et en direct (`src/api.py`, `MultiplayerSession`)** :
    - Gestion de deux variantes de jeu :
      - **« Même Mot »** : Les deux joueurs cherchent le même mot cible. Suivi de la progression adverse en direct (température, jauge et pourmille) avec **filtrage anti-triche côté serveur** (les mots de l'adversaire sont strictement masqués `••••••••` tant que la partie est active, puis révélés au dénouement).
      - **« Mots Choisis »** : Chaque joueur choisit secrètement le mot que son adversaire doit deviner. Cibles distinctes et affichage intégral des mots joués en clair sans risque de divulgation.
    - **Système d'identification double et sans friction** :
      - Code de salon unique court (`DUEL-XXXX`).
      - Deux clés de sécurité privées par joueur (`J1-XXXX` pour l'hôte, `J2-XXXX` pour l'invité) garantissant l'authentification sans création de compte ni mot de passe.
      - **Double modalité d'accès** : partage par **lien direct 1-clic** (`/multi/?r=CODE&k=KEY`) pour un démarrage instantané, et **formulaire de saisie manuelle** pour rejoindre ou changer d'appareil.
      - Mémorisation locale dans le navigateur (`localStorage`) pour reprendre un duel actif en 1 clic.
    - **Persistance robuste sur disque** : sauvegarde atomique dans `cemantix_data/multi_sessions.json` avec conservation prolongée (TTL 7 jours), résistant aux redémarrages de conteneurs Docker.
    - **Indices & forfaits** : jusqu'à 3 indices gradués par joueur (consommant 1 tour officiel et passant la main à l'adversaire) et bouton de forfait avec modale de confirmation unifiée `showConfirmDialog`.
    - **Réseau de routes REST dédiées** : `/api/multi/create`, `/api/multi/join`, `/api/multi/setup-word`, `/api/multi/status` (GET & POST), `/api/multi/guess`, `/api/multi/hint` et `/api/multi/giveup`.
  - **Interface Web Interactive Dédiée (`volumes/web/multi/`)** :
    - Page dédiée servie sous URL propre sans extension `/multi/` (`volumes/web/multi/index.html`).
    - Écran d'accueil à 3 volets : **Créer un Duel**, **Rejoindre avec un Code** et **Vos Duels en cours**.
    - Salle d'attente avec affichage du code de salon et copie du lien d'invitation direct en 1 clic.
    - Arène de duel avec bandeau dynamique de tour temps réel (*🟢 À vous de jouer !* ou *⏳ Tour adverse...*), double jauge thermique, saisie protégée et double tableau comparatif des mots tentés.
    - Polling adaptatif intelligent à 1.5s activé uniquement lors de l'attente du coup adverse pour préserver les ressources réseau.
  - **Intégration & Maillage Interne** :
    - Ajout de l'onglet `👥 Mode Multijoueur` dans le menu de navigation de toutes les pages (`/`, `/play/`, `/battle/`, `/multi/`).
    - Mise à jour de `volumes/web/sitemap.xml` avec l'entrée `/multi/` et balisage Schema.org complet (`WebApplication`, `GameApplication`, `BreadcrumbList`, `FAQPage`).
- **Mode Battle Interactif Web (Joueur vs Bot IA RAG, `/battle/`)** :
  - **Moteur de duel tour par tour synchronisé (`src/api.py`, `BattleSession`)** :
    - Affrontement tour par tour en direct opposant le joueur humain à un bot IA propulsé par `RagDuelPlayer` (régression Ridge vectorielle analytique sur embeddings `frWac`).
    - **Trois niveaux de difficulté globaux** : paramètre englobant la difficulté du mot secret à trouver et l'agressivité du bot (*Facile* : top 4 000 mots et exploration large ; *Moyen* : 4 000 à 16 000 mots et sélection top 2 ; *Expert* : > 16 000 mots et convergence directe sur le top 1 absolu).
    - **Système de 3 indices gradués dégressifs** : 3 indices maximum par manche (*Général*, *Intermédiaire*, *Proche*). Chaque indice consomme 1 tour officiel au compteur et déclenche la réplique instantanée du bot IA.
    - **Réseau d'API REST dédié** : routes `POST /api/battle/new`, `POST /api/battle/guess`, `POST /api/battle/hint`, `POST /api/battle/giveup` et `POST /api/battle/resume`.
  - **Interface Web Sémantique & Arène de Duel (`volumes/web/battle/`)** :
    - Page dédiée servie sous URL propre sans extension `/battle/` (`volumes/web/battle/index.html`).
    - **HUD de confrontation en direct** : double thermomètre avec jauges parallèles de progression thermique (0 à 1000 ‰) pour le joueur et le bot adverse.
    - **Spotlight face-à-face du dernier tour** : comparaison immédiate du mot joué par le joueur et de la réplique du bot IA avec leurs températures, météos et permilles.
    - **Double tableau de classement** : top 10 des meilleurs mots et historique complet synchronisé des deux camps.
    - **Bannière de résultat et débriefing d'après-match** : détection automatique des victoires du joueur, de l'IA, des égalités parfaites et des abandons avec dévoilement des mots secrets.
  - **Optimisation SEO de Pointe & Rich Snippets Google** :
    - Balises métadonnées et réseaux sociaux Open Graph / Twitter Cards ciblées sur les requêtes de duel sémantique (*battle cemantix*, *duel cemantix*, *jouer contre ia*).
    - Données structurées JSON-LD Schema.org complètes : schémas `Game`, `WebApplication`, `BreadcrumbList` et `FAQPage` dédiée au duel.
    - Réintégration et suivi dans Git de `volumes/web/sitemap.xml` et `volumes/web/robots.txt` pour un référencement pérenne.
    - Guide éditorial et stratégique sémantique indexable par les moteurs de recherche.
  - **Conception Responsive Mobile-First & Smartphone** :
    - Sélecteur tactile compact (*Segmented Control*) pour smartphone permettant de basculer en un tap entre les essais du joueur et ceux du bot sans défilement excessif.
    - Typographie fluide, input sécurisé à `font-size: 16px` (empêche le zoom automatique sur iOS Safari), hauteurs minimales de tap à 42px et respect des zones de sécurité (`safe-area-inset`).
    - Maillage interne complet reliant le Tableau de bord (`/`), le Mode Solo (`/play/`) et le Mode Battle (`/battle/`).
  - **Modale de Lancement & Personnalisation du Mot Cible du Bot IA** :
    - Fenêtre modale au premier plan avec effet de flou d'arrière-plan (*glassmorphism backdrop blur 8px*).
    - Sélection interactive du niveau de l'IA (🟢 *Facile* - Explorateur, 🟡 *Moyen* - Équilibré, 🔴 *Expert* - Redoutable) sous forme de cartes tactiles descriptives.
    - Champ de saisie optionnel permettant au joueur de choisir le mot secret assigné au bot adverse (avec validation lexicale Cémantix en temps réel et bandeau d'alerte sans rechargement) ou tirage aléatoire 🎲.
    - Déclenchement automatique au clic sur `⚔️ Nouvelle Manche`, `🔄 Manche Suivante` ou lors de la première arrivée sur la page.
  - **Modale de Confirmation Moderne & Suppression des `confirm()` Système** :
    - Composant universel asynchrone `showConfirmDialog` avec flou d'arrière-plan, icône animée, messages d'explication clairs, bouton d'action contextuel (danger rouge ou accent) et bouton d'annulation.
    - Remplacement complet des boîtes de dialogue natives du navigateur pour les abandons en Mode Solo (`🏳️ Abandonner`) et les forfaits en Mode Battle (`🏳️ Forfait`).
    - Ajout de la classe utilitaire `.btn-danger` dans `volumes/web/css/base.css` et styles complets `.confirm-modal-card` dans `volumes/web/css/modal.css`.

### Corrigé
- **Sécurisation du seuil top 1000 dans `MockClient` (`src/clients.py`)** :
  - Remplacement de la constante fixe `-1000` par `k = min(1000, len(all_cos))` pour éliminer les `ValueError: kth out of bounds` lors de l'exécution sur des vocabulaires restreints ou sous jeux de tests unitaires.

### Ajouté
- **Jeu Interactif Web & API Locale Haute Performance (`src/api.py`, `--api`)** :
  - **Serveur HTTP interne multithreadé** : micro-API Python intégrée sans dépendance externe lourde, démarrée automatiquement avec le démon ou via l'option `--api`.
  - **Deux modes de jeu disponibles** :
    - *Défi du Jour* : jouez directement sur le mot officiel du jour synchronisé avec la résolution quotidienne du démon.
    - *Mode Illimité* : parties aléatoires rejouables à volonté avec sélection du niveau de difficulté (*Facile* 4 000 mots, *Moyen* 12 000 mots, *Expert* 18 646 mots).
  - **Moteur de scoring vectoriel instantané** : calcul en mémoire des similarités cosinus et des rangs Cémantix officiels en pourmille ( ‰) en < 0.1 ms via NumPy et `VocabStore`.
  - **Système d'indices contextuels intelligents** : calcul de candidats sémantiquement proches du mot secret pour débloquer les joueurs bloqués (+1 coup décompté au score).
  - **Persistance des parties actives** : sauvegarde automatique des sessions dans `cemantix_data/web_sessions.json` permettant de basculer d'onglet ou de rafraîchir sans perdre sa partie.
  - **Interface utilisateur dédiée au jeu** : spotlight du dernier mot joué avec jauge dynamique, tableau des 10 meilleurs mots, chronologie complète et gestion des victoires.
- **Visualisation Ergonomique de la Trajectoire du Bot** :
  - **Modale interactive de débriefing** : clic sur n'importe quelle ligne de l'historique des puzzles pour afficher la chronologie complète des coups joués par le solveur.
  - **Badges de provenance et métriques précises** : identification de l'origine de chaque mot (🌱 Graine, ⚡ RAG, 🤖 LLM, 🎯 Sniper), température (°C), indicateur météo, rang en pourmille ( ‰) et étoiles signalant un nouveau record thermique (⭐).
  - **Filtrage dynamique interactif** : onglets de filtrage par catégorie (*Tous*, *Graines*, *RAG*, *Top 1000*) avec compteurs en direct.
  - **Exportation rapide** : bouton de copie du rapport complet de résolution formaté pour le partage dans le presse-papier.
  - **Commande CLI `--force-solve`** : permet de forcer la résolution immédiate du mot du jour même s'il a déjà été résolu, afin d'enregistrer l'intégralité de la trajectoire dans l'historique et `data.json`.
  - **Fallback gracieux** : reconstitution automatique des étapes depuis les meilleurs essais pour les puzzles antérieurs à l'implémentation de la trajectoire complète.
- **Optimisation SEO Complète & Rich Snippets Google** :
  - **Données structurées JSON-LD** : schémas `WebPage`, `VideoGame` et `FAQPage` pour affichage enrichi dans les résultats de recherche Google.
  - **Métadonnées sociales Open Graph & Twitter Cards** : balises complètes avec image dédiée `og-image.jpg`.
  - **Optimisation sémantique et lexicale** : ciblage naturel des graphies avec et sans accent (*Cémantix*, *Cemantix*, *Semantix*).
  - **Guide stratégique & FAQ intégrée** : section explicative sur le fonctionnement du jeu, l'échelle des températures et les astuces de recherche.
- **Réseau Docker & Intégration Caddy (`docker-compose.yml`)** :
  - **Raccordement au réseau `web-net`** : déclaration du réseau externe `web-net` pour communication directe entre le conteneur `cemantix_solver` et le reverse-proxy Caddy.
  - **Routage de l'API** : redirection transparente des requêtes `https://cemantix.cyril-randon.fr/api/*` vers `cemantix_solver:8000`.
  - **Standard typographique** : insertion systématique d'une espace insécable/normale devant tous les symboles pourmille (` ‰`).
- **Interface Web Mot du Jour & Volume Caddy (`./volumes/web`)** :
  - **Dépose des fichiers web complets dans `./volumes/web`** : mise à disposition d'une application web autonome et réactive prête à être servie directement par Caddy via un simple montage de volume (`./volumes/web`).
  - **Fichiers statiques légers sans framework lourd ni PHP** :
    - `volumes/web/index.html` : structure sémantique moderne avec carte héro du mot du jour, badges, thermomètre, compte à rebours minuit, tableau de bord des statistiques et historique archivé.
    - `volumes/web/style.css` : feuille de style complète avec thème sombre et clair commutable, glassmorphism, responsive design et animations soignées.
    - `volumes/web/app.js` : application JavaScript vanilla avec gestion d'état, auto-polling de `data.json` toutes les 30s, compte à rebours en direct vers minuit (Europe/Paris), copie presse-papier avec notifications toast et recherche instantanée.
    - `volumes/web/data.json` : fichier de données temps réel maintenu à jour automatiquement.
  - **Mode Anti-Spoiler interactif** : protection par défaut du mot secret sous un voile flouté avec bouton de révélation/masquage au clic et bouton de bascule globale, idéal pour consulter les statistiques du jour sans se gâcher le puzzle en cours.
  - **Échelle Thermique & Indices d'Approche** : visualisation des paliers Cémantix officiels (Glacial, Froid, Tiède, Chaud, Brûlant) et affichage des meilleurs candidats sémantiques ayant convergé vers la cible avec leurs températures et rangs en pourmille (‰).
  - **Compte à rebours minuit en direct** : horloge numérique décomptant en temps réel les heures, minutes et secondes jusqu'au basculement officiel de Cémantix à 00h00 heure de Paris.
  - **Tableau de bord de performance (KPIs)** : total de puzzles résolus, moyenne d'essais, temps moyen de résolution et taux de succès (100%).
  - **Module d'exportation Python (`src/web.py`)** : génération et écriture atomique (via `.tmp` sécurisé) de `data.json`, synchronisé automatiquement au démarrage et à chaque résolution du démon (`src/daemon.py`).
  - **Option CLI `--export-web`** : commande permettant d'exporter ou régénérer les données web à tout moment depuis le terminal ou Docker.
  - **Montage du volume dans `docker-compose.yml`** : ajout du point de montage `- ./volumes/web:/app/volumes/web` pour une synchronisation transparente et continue entre le solveur en tâche de fond et le serveur web Caddy.
- **Mode Démon 24h/24 & Veille automatique (`src/daemon.py`, `--daemon`)** :
  - **Exécution en arrière-plan permanente sous Docker** : le conteneur reste en sommeil léger et se réveille chaque nuit à **00h00 (heure de Paris / Europe/Paris)** pour résoudre le mot officiel Cémantix en mode 100% RAG pur.
  - **Interception gracieuse des signaux POSIX** : écoute de `SIGTERM` et `SIGINT` avec boucle de sommeil par tranche de 1 seconde permettant un arrêt immédiat sans délai (`docker stop` / `docker compose down`).
  - **Rattrapage au démarrage** : vérifie dès le lancement si le mot du jour est déjà consigné dans l'historique ; dans le cas contraire, il le résout immédiatement avant d'entamer son cycle de veille jusqu'à minuit.
  - **Historisation automatique** : enregistrement des statistiques quotidiennes dans `cemantix_data/daily_history.json` (date, puzzle, mot trouvé, nombre de coups, durée).
  - **Configuration Docker pour service autonome** : ajout de `restart: unless-stopped`, `command: ["--daemon", "--rag-only"]`, paquet Debian `tzdata` et variable `TZ=Europe/Paris`.
  - **Surveillance de santé Docker (HEALTHCHECK)** : intégration d'un heartbeat régulier et de la commande `python cemantix_rag.py --healthcheck` rapportant dynamiquement l'état `healthy` sous `docker ps` et `docker compose ps`.

### Modifié / Amélioré
- **Ergonomie des Contrôles de Jeu & Boutons d'Action (`/play/`, `/battle/`, `/multi/`)** :
  - **Repositionnement latéral en 2 colonnes** : placement des boutons d'action (*Indice* et *Abandonner / Forfait*) directement à droite du champ de saisie sous forme d'une colonne compacte à 2 lignes superposées, s'alignant sur la hauteur du champ de saisie.
  - **Maintien de la disposition sur mobile** : conservation de la disposition côte à côte sur smartphone avec typographie et espacements adaptés pour ne jamais glisser sous le champ de saisie.
  - **Harmonisation des tuiles de mots et suppression des scintillements** : élimination du clignotement / saccade lors du rafraîchissement des listes d'essais via un cache de rendu DOM différentiel, désactivation des animations `fadeIn` répétitives, et affichage thermique harmonisé (+ / °C).
- **APIsation & Sécurisation du Tableau de Bord (`GET /api/daily`)** :
  - **Migration vers l'API interne** : suppression du fichier public `volumes/web/data.json` au profit d'une route API dédiée `GET /api/daily` servie par le conteneur Python.
  - **Protection Anti-Spoiler Serveur** : par défaut, le mot secret (`current.word`) et sa présence dans la trajectoire sont masqués côté serveur (`None` / `••••••••`).
  - **Révélation Dynamique Sécurisée** : le mot secret n'est délivré que lors d'un appel explicite `GET /api/daily?reveal=true` (déclenché au clic sur l'icône de révélation ou de copie).
  - **Enrichissement SEO Schema.org (`volumes/web/play/index.html`)** : intégration du schéma structuré `GameApplication` et du fil d'Ariane `BreadcrumbList`.
  - **Arrêt du suivi Git de `volumes/web/sitemap.xml`** : exclusion du sitemap local du dépôt Git pour éviter les conflits lors des pulls et déploiements sur VPS.
- **Refonte Responsive Smartphone & Expérience Mobile (`volumes/web/`)** :
  - **Fluidification du pied de page (Footer)** : bascule du footer en positionnement statique/naturel sur mobile (`≤ 768px`) pour supprimer le blocage de l'écran et le chevauchement avec les zones d'interaction et le clavier virtuel.
  - **Navigation par onglets façon « Segmented Control »** : remplacement de l'empilement vertical volumineux par un sélecteur d'onglets compact et tactile optimisé pour smartphone.
  - **En-tête et carte Hero adaptatifs** : typographie fluide via `clamp()`, adaptation du mot secret (sans débordement sur les mots longs), indicateur d'état du démon compact et grille de métriques à 3 colonnes réactives.
  - **Grille tactile pour le jeu interactif (`/play/`)** : disposition 2 colonnes des boutons d'action (`Indice` + `Nouvelle Partie` puis `Abandonner`), taille de police de saisie fixée à 16px minimum pour éliminer le zoom automatique intempestif sur iOS Safari.
  - **Tableaux et modale de trajectoire tactiles** : défilement horizontal fluide avec containment tactile (`overscroll-behavior-x`) et adaptation responsive de la modale de trajectoire du solveur IA.
  - **Métadonnées PWA / Viewport Cover** : intégration de `viewport-fit=cover`, `mobile-web-app-capable` et prise en charge des zones de sécurité (`safe-area-inset`).
  - **Mise à jour visuelle Open Graph** : actualisation de la bannière sociale d'illustration `og-image.jpg`.
- **Refonte Modulaire & Architecture Atomique de l'Interface Web (`volumes/web/`)** :
  - **Scission de la page monolithique `index.html`** : séparation en deux pages HTML atomiques et sémantiques avec URLs propres sans extension :
    - `index.html` : Tableau de bord du mot du jour (URL `/`), métriques, thermomètre, podium des indices, KPIs, historique des puzzles archivés, modale de trajectoire IA et section SEO / FAQ.
    - `play/index.html` : Interface dédiée au jeu interactif Cémantix en ligne servie sous l'URL propre `/play/` (mode Défi du jour, mode Illimité avec sélecteur de difficulté, saisie réactive, spotlight et listes d'essais).
  - **Découpage modulaire des styles CSS (`volumes/web/css/`)** : décomposition du fichier monolithique `style.css` (~2 200 lignes) en 6 sous-modules atomiques indépendants :
    - `variables.css` : tokens de design, thèmes sombre et clair, dégradés thermiques sémantiques.
    - `base.css` : reset, typographie, boutons, badges, composants de base, boutons pill et notifications toast.
    - `layout.css` : en-tête d'application, navigation par onglets réactive et pied de page fixe.
    - `dashboard.css` : composants visuels du tableau de bord, thermomètre, compte à rebours minuit et guide SEO.
    - `game.css` : commandes de jeu, saisie, spotlight du dernier mot et listes de propositions.
    - `modal.css` : modale de visualisation de la trajectoire du bot et filtres de progression.
  - **Modularisation JavaScript en modules ES natifs (`volumes/web/js/`)** : éclatement du fichier monolithique `app.js` (~1 400 lignes) en modules autonomes sans bundler lourd :
    - `app.js` : point d'entrée unique et bootstrap de l'application selon les éléments du DOM.
    - `utils.js` : helpers de formatage de dates, calcul des classes thermiques, gestionnaire de toasts et copie presse-papier.
    - `theme.js` : commutation des thèmes clair/sombre et bascule globale du voile anti-spoiler.
    - `countdown.js` : horloge décomptant en temps réel le temps jusqu'à minuit (Europe/Paris).
    - `trajectory.js` : gestion et filtrage de la modale de trajectoire du solveur IA.
    - `dashboard.js` : synchronisation continue de `data.json`, rendu du mot du jour et recherche dans l'historique.
    - `game.js` : gestion des parties interactives, appels à la micro-API `/api/game/*`, persistance locale et spotlight.
  - **Optimisation du chargement et élimination des fichiers obsolètes** : suppression des monolithes racine `app.js` et `style.css`, liaison directe des ressources spécifiques par page pour un rendu immédiat et zéro flash de style.
- **Refonte Ergonomique & Architecture des Dégradés (`volumes/web/`)** :
  - **Mise en page 2 colonnes de la carte Hero (Mot du Jour)** : réorganisation du bloc Mot du Jour en grille à deux colonnes équilibrée sur grand écran (carte du mot secret à gauche, 3 cartes métriques empilées à droite) pour supprimer les espaces vides et offrir une lecture immédiate.
  - **Architecture à deux dégradés distincts (`--gradient-dashboard` et `--gradient-game`)** :
    - *Échelle thermique du tableau de bord (`--gradient-dashboard`)* : dégradé continu à 5 paliers avec contraste renforcé entre Glacial (`#075985`) et Froid (`#3b82f6`), et transitions resserrées pour valoriser les teintes dominantes.
    - *Jauge du jeu interactif (`--gradient-game`)* : dégradé dédié chaud débutant à moyen chaud à partir du jaune (`#fcf161`) vers le rouge carmin (`#c20000`).
  - **Modernisation de la tuile « Dernier coup joué : »** :
    - Élimination des encadrements lourds au profit d'un agencement épuré et moderne.
    - Affichage de la température en typographie monospace blanche/neutre sans coloration superflue du texte.
    - Jauge capsule horizontale fluide adoptant `--gradient-game`.
    - Affichage conditionnel de la jauge : masquée pour les températures froides ou fraîches (`< 20°C`), et affichée uniquement à partir d'une température tiède/chaude (`>= 20°C` ou mot classé au Top 1000).
  - **Finitions typographiques** : harmonisation des espaces insécables devant les symboles pourmille (` ‰`) et style épuré pour le lien auteur en pied de page.

## [0.2.0] - 2026-10-18

### Modifié
- **Refactoring architectural modulaire (`src/`)** :
  - Découpage du script monolithique `cemantix_rag.py` (~2 000 lignes) en package modulaire `src/`.\
  - `src/config.py` : centralisation des constantes, styles ANSI et configuration d'environnement.\
  - `src/vocab.py` : gestion du dictionnaire Lexique 3.83, normalisation des accents et `VocabStore` (ChromaDB).\
  - `src/clients.py` : client officiel `CemantixClient` et simulateur local `MockClient`.\
  - `src/ui.py` : composants de rendu console, thermomètres ASCII, dashboards solo/duel et débriefing.\
  - `src/solvers.py` : régression Ridge, algorithme de reranking, interface LLM local, `Solver` et `RagDuelPlayer`.\
  - `src/modes.py` : boucles d'orchestration pour benchmark, battle, solo et duel.\
  - `cemantix_rag.py` : point d'entrée CLI épuré (~80 lignes) orchestrant les modules.\
  - Mise à jour du `Dockerfile` et de la documentation (`README.md`).

### Corrigé
- **Dictionnaire & Filtrage linguistique strict (élimination des mots anglais & réhabilitation de « car »)** :
  - **Correction du refus des mots usuels en mode Solo (`car`, `faire`, `être`, `avoir`, etc.)** : suppression du filtre prématuré `w not in STOPWORDS` lors de l'extraction de l'espace vectoriel `frWac`, permettant à tous les lemmes et mots grammaticaux français légitimes d'être chargés dans le vector store et d'être joués et scorés normalement en Solo, Duel et Mock.
  - **Détection et régénération automatique du cache vectoriel** : si un cache `vecs.npy` / `words.txt` antérieur sans `car` est détecté, régénération automatique propre depuis le binaire `frWac` et synchronisation immédiate des lemmes fondamentaux dans ChromaDB.
  - **Épuration intégrale de `ENGLISH_WORDS` & Suppression totale de `FRENCH_EXCEPTIONS`** : assainissement radical de la liste noire anglophone pour n'y conserver strictement que de vrais parasites (*water*, *people*, *about*, *money*, *dog*, *cat*, etc.) et les graphies anglaises sans accent (*decision*, *region*, *creation*...). Tout mot français, homographe ou emprunt usuel (*car*, *table*, *train*, *sport*, *film*, *process*, *report*, *bug*, *job*, *coach*, *deal*, *pass*, *set*, *top*, *cool*, etc.) en a été retiré, éliminant définitivement la variable et liste d'exceptions `FRENCH_EXCEPTIONS`. Tout mot ajouté dans `lexique_fr.txt` fonctionne désormais immédiatement à 100 % sans aucune manipulation annexe ni exception à configurer.
  - **Exclusion formelle des mots anglais parasites (`ENGLISH_WORDS`)** : filtrage strict des résidus de sous-titres et tokens web anglophones (*water*, *people*, *about*, *game*, *play*, *boy*, *girl*, etc.) dans `ensure_lexique()`, `VocabStore.is_valid_french()`, le solveur RAG et les modes interactifs Solo/Duel.
  - **Renforcement des consignes du prompt LLM** : instruction linguistique stricte interdisant formellement la génération de tout mot anglophone.
- **Menu d'accueil interactif (`--play`)** :
  - Restauration de l'écran d'accueil permettant de choisir explicitement entre le mode Solo et le mode Duel croisé au lancement de `--play`.

### Optimisé & Corrigé
- **Convergence RAG Haute Efficacité & Reranking par Température Estimée** :
  - **Correction du vivier FPS** : restriction stricte du vivier de graines aux pôles disciplinaires fondamentaux (`DISCIPLINES`) et concepts cardinaux du lexique (`SEED_WORDS`), éliminant les lemmes marginaux ou périphériques.
  - **Reranking multicritère par température** : refonte de la fonction `rerank` pour ordonner les candidats par score d'excellence `pred_temp - 120.0 * sqrt(err)` au lieu de l'erreur brute seule, garantissant que les candidats les plus chauds soient joués en priorité.
  - **Pool de candidats enrichi** : élargissement de l'exploration vectorielle à 60-80 candidats combinant la direction Ridge `q_est` et les voisins des meilleurs coups connus.
  - **Amorçage adaptatif affiné (12 graines)** : interruption précoce dès 3 graines si un signal $\ge 20^\circ\text{C}$ (Top 1000) est détecté, et tir sniper dès détection d'un candidat brûlant ($\ge 65^\circ\text{C}$ et cohérence extrême).
  - **Résultat de référence** : résolution de mots cibles courants (ex: *planifier*) en 11 à 14 essais (médiane : 12 essais, min : 8 essais, temps moyen ~0.25s) contre 19 à 31 essais précédemment.
