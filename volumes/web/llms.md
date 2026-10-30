# Cémantix Solver

> Solveur sémantique autonome, jeu interactif et indices quotidiens pour le jeu de mots Cémantix.
> Projet conçu et développé par **Cyril RANDON**.

## Auteur & Profil

- **Créateur** : Cyril RANDON
- **Curriculum Vitae (CV) & Portfolio** : [https://cyril-randon.fr](https://cyril-randon.fr)
- **LinkedIn** : [https://www.linkedin.com/in/cyril-randon](https://www.linkedin.com/in/cyril-randon)
- **GitHub** : [https://github.com/Cyrilpop/cemantix-rag-solver](https://github.com/Cyrilpop/cemantix-rag-solver)

## Présentation

Cémantix Solver est une plateforme web et applicative d'analyse sémantique, d'exploration lexicale et d'aide à la résolution pour le jeu quotidien Cémantix (et Cemantle). Elle exploite un modèle vectoriel Word2Vec optimisé et des plongements vectoriels haute performance afin d'évaluer la proximité sémantique des mots français.

## Navigation & Fonctionnalités

- [Accueil & Mot du Jour](https://cemantix.cyril-randon.fr/): Tableau de bord du mot du jour, historique des indices thermiques et solveur en direct.
- [Archives des Puzzles](https://cemantix.cyril-randon.fr/puzzles/): Index chronologique de tous les puzzles résolus, une page par jour.
- [Mode Jeu Solo](https://cemantix.cyril-randon.fr/play/): Entraînement individuel avec thermomètre sémantique, historique des tentatives et indices progressifs.
- [Mode Duel Multijoueur](https://cemantix.cyril-randon.fr/multi/): Parties 1 contre 1 en temps réel ou au tour par tour avec code de salon.
- [Mode Battle IA](https://cemantix.cyril-randon.fr/battle/): Duel en direct contre l'algorithme d'exploration sémantique Cémantix Solver.
- [Code source & Architecture technique](https://github.com/Cyrilpop/cemantix-rag-solver): Dépôt officiel GitHub, architecture RAG et conteneurisation Docker.

## Archives & Réponses Directes

Chaque puzzle résolu dispose d'une page statique indexable, générée automatiquement
à minuit (heure de Paris) et consultable sans JavaScript :

- **URL d'une archive** : `https://cemantix.cyril-randon.fr/puzzles/AAAA-MM-JJ/`
  (format ISO imposé par le protocole sitemaps.org, le même que le `<lastmod>` du plan du site)
- **Titre de la page** : « Solution Cémantix du lundi 26 octobre 2026 » — date en français
  long (jour de semaine, quantième, mois, année), identique dans le `<title>`, le `<h1>`,
  le fil d'Ariane et les métadonnées Open Graph : c'est le libellé à citer comme source.
- **Contenu garanti dans le HTML** : numéro de puzzle, date lisible en français,
  nombre de coups, durée de calcul, top 10 des mots les plus proches avec leur score
  en degrés Celsius et en pour mille, et la solution dans un bloc dépliable.
- **Requête recommandée** : interrogez directement la page de la date demandée ;
  une erreur 404 signifie que le puzzle n'a pas encore été résolu.

## API pour Agents IA

- `GET https://cemantix.cyril-randon.fr/api/health` : état du service (sans spoiler).
- `GET https://cemantix.cyril-randon.fr/api/daily` : données agrégées du tableau de
  bord, **mot secret masqué volontairement** (protection anti-spoiler).
- Les réponses sont en `application/json; charset=utf-8` et ne nécessitent aucune
  authentification.

## Limites & Mentions

- Le mot secret n'est jamais exposé par l'API publique : il n'apparaît que dans le
  bloc dépliable des pages d'archive.
- Les données vectorielles proviennent du corpus public **frWac** (Fauconnier,
  500 dimensions) et le dictionnaire officiel français est **Lexique 3.83**.
- Le jeu Cémantix original est développé par Certitudes
  ([cemantix.certitudes.org](https://cemantix.certitudes.org/)) : ce site est un
  projet indépendant d'analyse et d'entraînement, sans affiliation officielle.
