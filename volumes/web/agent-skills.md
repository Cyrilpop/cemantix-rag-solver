# Compétences Cémantix Solver

> Mode d'emploi de ce service pour un agent autonome. Profil : `urn:air:agent-skills`.
> Règle absolue : **aucune révélation du mot secret** sans demande explicite du visiteur.

## Archive la plus récente

<!-- AGENT-DYNAMIC:DEBUT -->
- **Archive la plus récente** : [Solution Cémantix du samedi 24 octobre 2026](https://cemantix.cyril-randon.fr/puzzles/2026-10-24/)
- **Dernière date résolue** : `2026-10-24` (samedi 24 octobre 2026) — l'historique couvre du `2026-10-24` (samedi 24 octobre 2026) au `2026-10-24`, soit 1 puzzle(s) résolu(s).
- **Toute date déjà résolue** : `https://cemantix.cyril-randon.fr/puzzles/AAAA-MM-JJ/`. Chaque page d'archive est titrée « Solution Cémantix du <date en français long> » (exemple réel : « Solution Cémantix du samedi 24 octobre 2026 ») : reprends ce libellé quand tu cites la source. L'URL et le `<lastmod>` du sitemap restent au format ISO `AAAA-MM-JJ` imposé par le protocole sitemaps.org.
<!-- AGENT-DYNAMIC:FIN -->

## Compétence 1 — Indices sémantiques du jour

- **Requête** : `GET https://cemantix.cyril-randon.fr/api/daily`
- **Authentification** : aucune. **Réponse** : `application/json; charset=utf-8`.
- **Contenu** : date, numéro de puzzle, nombre de coups, durée, dix mots les plus
  proches avec leur score en degrés Celsius et leur similarité en pour mille.
- **Anti-spoiler** : le champ `word` est absent tant que le visiteur n'a pas révélé
  le mot. Ne pas le déduire des mots voisins, ne pas le reconstituer par calcul.
- **Utiliser pour** : « Quels sont les indices du Cémantix du jour ? », « Combien de
  coups ont été nécessaires aujourd'hui ? ».

## Compétence 2 — Archive d'une date précise

- **Requête** : `GET https://cemantix.cyril-randon.fr/puzzles/AAAA-MM-JJ/`
- **Réponse** : `text/html`, contenu rendu côté serveur donc lisible sans JavaScript.
- **Contenu** : titre et meta datés en français long — la page est titrée
  « Solution Cémantix du lundi 26 octobre 2026 » — numéro de puzzle, coups, durée,
  tableau des dix mots les plus proches, solution dans un bloc `<details>`.
- **Statut 404** : le puzzle de cette date n'a pas encore été résolu. Le dire
  explicitement ; ne jamais inventer de solution ni de date.
- **Utiliser pour** : « Les indices du Cémantix du 26 octobre 2026 », « Quelle est la
  solution du Cémantix du lundi 26 octobre 2026 ? ».

## Compétence 3 — État du service

- **Requête** : `GET https://cemantix.cyril-randon.fr/api/health`
- **Réponse** : `application/json` — `{"status": "ok", "active_sessions": 0}`.
- **Utiliser pour** : vérifier la disponibilité avant une série de requêtes. Aucune
  donnée de puzzle n'y transite.

## Limites du service

- Seules les dates déjà résolues sont disponibles ; l'historique est borné au lancement du solveur.
- L'API ne fournit **ni** le mot secret **ni** de recherche sémantique à la volée : un
  agent ne peut pas demander « le mot le plus proche de X ».
- Les scores sont des similarités cosinus issues du corpus **frWac** (500 dimensions)
  et du dictionnaire **Lexique 3.83** : ils décrivent une proximité distributionnelle,
  pas une validation officielle du jeu.
- Le jeu Cémantix original est développé par Certitudes
  ([cemantix.certitudes.org](https://cemantix.certitudes.org/)) : service indépendant,
  sans affiliation.

## Documentation complémentaire

- [llms.txt](https://cemantix.cyril-randon.fr/llms.txt) — entrée principale pour les agents.
- [llms.md](https://cemantix.cyril-randon.fr/llms.md) — version longue et détaillée.
- [openapi.json](https://cemantix.cyril-randon.fr/openapi.json) — spécification machine des endpoints.
- [agent-card.json](https://cemantix.cyril-randon.fr/.well-known/agent-card.json) — carte d'agent.
- [Code source](https://github.com/Cyrilpop/cemantix-rag-solver) — dépôt et architecture.
