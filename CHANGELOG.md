# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-18

### Ajouté
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
