# Journal des modifications (Changelog)

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

## [Non publié] - 2026-10-18

### Ajouté
- **Mode jeu interactif solo (`--play` / `--game`)** :
  - Dashboard dynamique dans la console avec tableau récapitulatif Top 15 des meilleurs coups, météo et rang en pourmille (‰).
  - Thermomètre ASCII dynamique (`make_gauge`) pour visualiser en temps réel la proximité sémantique de chaque coup.
  - Système d'indice vectoriel RAG (`/indice`) par interpolation vers le vecteur secret, avec exclusion des mots vides (stopwords).
  - Boucle de jeu continue en mémoire : enchaînement instantané des parties sans recharger VocabStore ni ChromaDB.
  - Commandes en cours de partie : `/aide`, `/top`, `/historique`, `/indice`, `/rejouer`, `/abandon`, `/quitter`.

## [1.0.0] - 2026-10-18

### Ajouté
- Solveur 100% RAG mathématique par régression Ridge et reranking géométrique.
- Mode hybride RAG + LLM local (compatible LM Studio).
- Mode Battle comparatif direct sur le même mot secret.
- Intégration de l'espace vectoriel frWac (150 000 lemmes) et du dictionnaire officiel Lexique 3.83.
