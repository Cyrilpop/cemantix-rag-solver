# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-18

### Modifié
- **Refactoring architectural modulaire (`src/`)** :
  - Découpage du script monolithique `cemantix_rag.py` (~2 000 lignes) en package modulaire `src/`.
  - `src/config.py` : centralisation des constantes, styles ANSI et configuration d'environnement.
  - `src/vocab.py` : gestion du dictionnaire Lexique 3.83, normalisation des accents et `VocabStore` (ChromaDB).
  - `src/clients.py` : client officiel `CemantixClient` et simulateur local `MockClient`.
  - `src/ui.py` : composants de rendu console, thermomètres ASCII, dashboards solo/duel et débriefing.
  - `src/solvers.py` : régression Ridge, algorithme de reranking, interface LLM local, `Solver` et `RagDuelPlayer`.
  - `src/modes.py` : boucles d'orchestration pour benchmark, battle, solo et duel.
  - `cemantix_rag.py` : point d'entrée CLI épuré (~80 lignes) orchestrant les modules.
  - Mise à jour du `Dockerfile` et de la documentation (`README.md`).

### Corrigé
- **Menu d'accueil interactif (`--play`)** :
  - Restauration de l'écran d'accueil permettant de choisir explicitement entre le mode Solo et le mode Duel croisé au lancement de `--play`.

### Ajouté
- **Menu interactif principal complet (`src/menu.py`)** :
  - Lancement automatique du menu d'accueil lors d'une exécution sans argument (`python cemantix_rag.py`) ou via l'option `--menu` / `-i`.
  - Accès centralisé à l'ensemble des modes : puzzle du jour, jeu solo, duel croisé, battle comparatif, mock local, benchmark autonome et réglages.
  - Résolution du puzzle du jour avec choix dynamique du moteur (Hybride ou 100% RAG pur), réglage du nombre de graines d'amorçage et répétition de la résolution sur le même puzzle avec bilan statistique (taux de victoire, moyenne, médiane, min/max, répartition des sources et temps).
  - Navigation universelle `/menu` (ou `menu`) opérationnelle depuis n'importe quel écran, sous-menu ou prompt de saisie pour revenir instantanément au menu principal sans surcharger visuellement les invites.
  - Nettoyage d'écran automatique (`clear_screen`) avec fallback ANSI (`\033[H\033[2J`) garantissant un rendu propre et isolé sous tous les terminaux et conteneurs Docker.
  - Panneau de réglages interactif pour basculer le mode verbeux, ajuster les délais réseau, la limite d'essais, les graines et les paramètres LLM en cours de session.
- **Mode duel croisé interactif (`--duel`)** :
  - Duel en face-à-face « Bataille Navale sémantique » opposant Joueur Humain vs IA RAG.
  - Deux mots cibles distincts : l'Humain cherche le mot de l'IA ; l'IA cherche le mot de l'Humain (choisi manuellement ou tiré au sort via `/random`).
  - Dashboard console en deux colonnes synchronisées (89 colonnes, 43 caractères par colonne), thermomètres ASCII et météos Cémantix en miroir sans troncature des lemmes longs (jusqu'à 17 caractères).
  - Affichage persistant des indices vectoriels débloqués (`/indice`) conservés tout au long de la manche (`Indice #1`, `Indice #2`, etc.).
  - Affichage paramétrable des meilleurs coups via `DUEL_TOP_WORDS` (par défaut Top 10).
  - Compteur de manches et score cumulé de session persistant (`🧑   X — Y  🤖`) dans le bandeau supérieur.
  - 3 niveaux de difficulté pour l'IA (`Facile`, `Moyen`, `Expert`) ajustant le nombre de graines, le seuil de chauffe et le choix des candidats rerankés.
  - Configuration d'avant-match guidée en deux étapes (niveau puis cible de l'IA).
  - Bascule dynamique du niveau en jeu via `/diff`, `/facile`, `/moyen`, `/expert` et option CLI `--difficulty` (`-d`).
  - Tableau de débriefing comparatif d'après-match (`render_duel_debrief`) : confrontation côte à côte des cibles, statut, meilleur mot atteint, première étincelle et répartition météo.
   - Coup spécial d'espionnage sémantique (`/espion`) : 1 crédit par match permettant au joueur d'intercepter la projection Ridge de l'IA (disciplines surveillées, meilleure piste et alerte de proximité sémantique en temps réel), en consommant son tour de jeu.
  - Bascule instantanée en mémoire entre mode solo et duel via `/solo` et `/duel`.
- **Mode jeu interactif solo (`--play` / `--game`)** :
  - Dashboard dynamique dans la console avec tableau récapitulatif Top 15 des meilleurs coups, météo et rang en pourmille (‰).
  - Thermomètre ASCII dynamique (`make_gauge`) pour visualiser en temps réel la proximité sémantique de chaque coup.
  - Système d'indice vectoriel RAG (`/indice`) par interpolation vers le vecteur secret avec affichage persistant des indices débloqués à l'écran.
  - Boucle de jeu continue en mémoire : enchaînement instantané des parties sans recharger VocabStore ni ChromaDB.
  - Commandes en cours de partie : `/aide`, `/top`, `/historique`, `/indice`, `/rejouer`, `/abandon`, `/quitter`.

## [1.0.0] - 2026-10-18

### Ajouté
- Solveur 100% RAG mathématique par régression Ridge et reranking géométrique.
- Mode hybride RAG + LLM local (compatible LM Studio).
- Mode Battle comparatif direct sur le même mot secret.
- Intégration de l'espace vectoriel frWac (150 000 lemmes) et du dictionnaire officiel Lexique 3.83.
