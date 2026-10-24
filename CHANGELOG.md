# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-24

### Ajouté
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
