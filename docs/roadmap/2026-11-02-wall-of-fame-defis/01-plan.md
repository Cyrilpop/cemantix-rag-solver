# 🏆 Plan — Wall of Fame, Exploitation des KPIs & Visualisation Interactive des Défis

> **Évolution :** [2026-11 · Wall of Fame & Replay des Défis Visiteurs](../README.md) · document 1/2  
> **Statut du document :** référence de conception, versionnée.  
> **Avancement :** tenu à jour séparément dans [`02-avancement.md`](02-avancement.md) — ne pas reporter d'état d'avancement ici, ce fichier décrit **quoi faire et comment le vérifier**.  
> **Jalon technique associé :** [`docs/milestones/M9_WALL_OF_FAME_UI.md`](../../milestones/M9_WALL_OF_FAME_UI.md)  
> **Socle technique prérequis :** [`docs/milestones/M8_DEFI_ANALYTICS_KPIS.md`](../../milestones/M8_DEFI_ANALYTICS_KPIS.md)  
> **Branche :** `feature/m9-wall-of-fame-ui` (base `origin/main`)  
> **Date d'ouverture :** 04/11/2026  

**Convention de lecture :** chaque action porte un identifiant permanent (`WOF-01` à `WOF-06`) utilisé comme **clé de suivi** dans `02-avancement.md`.

---

## 0. Méthodologie & périmètre

Le Jalon M8 ayant rendu la persistance des défis et de leurs coups totalement pérenne en base de données, cette évolution M9 concrétise la valorisation visuelle et communautaire de ces données sur [`volumes/web/defi/index.html`](../../../volumes/web/defi/index.html) :

1. Exposition d'une section **Wall of Fame** mettant à l'honneur les mots qui ont vaincu l'IA.
2. Restitution des indicateurs de performance de l'IA (taux de victoire, moyenne de coups).
3. Replay interactif du cheminement complet d'un défi archivé via [`volumes/web/js/trajectory.js`](../../../volumes/web/js/trajectory.js).
4. Information personnalisée du joueur sur sa session (victoires personnelles et quota restant).
5. Protection de la base via un cache mémoire TTL de 15 secondes côté API REST.

---

## 1. Findings & Actions Spécifiées

### WOF-01 (🔴) — Endpoint API `/api/challenge/kpis` avec Cache Mémoire TTL 15s
- **Problème :** Recalculer l'ensemble des KPIs et du Wall of Fame à chaque chargement de page solliciterait inutilement PostgreSQL et SQLite.
- **Correctif :** Implémentation d'une route REST `GET /api/challenge/kpis` dans `src/api/routes/challenge.py` protégée par un cache mémoire à TTL court (15 secondes) pour les données globales, avec enrichissement dynamique des stats du joueur appelant.
- **Vérification :** Test unitaire mesurant qu'un appel consécutif sous 15 secondes n'exécute aucune requête SQL d'agrégation.

### WOF-02 (🔴) — Endpoint API `/api/challenge/<id>/guesses` (Replay du Chemin)
- **Problème :** La modale de trajectoire a besoin de relire les étapes complètes d'un défi archivé sans passer par le WebSocket/SSE terminé.
- **Correctif :** Route REST `GET /api/challenge/<id>/guesses` interrogeant la table relationnelle `bot_challenge_guesses` et retournant la liste ordonnée des étapes (`step_num`, `word`, `score`, `permille`, `weather`, `source`).
- **Vérification :** Test unitaire validant le format JSON et le tri chronologique strict des coups retournés.

### WOF-03 (🟠) — Composants HTML & Design du Wall of Fame (`/defi/`)
- **Problème :** Absence de section mettant en avant les mots invaincus par le bot.
- **Correctif :** Intégration d'un conteneur `#defi-wall-of-fame` dans `volumes/web/defi/index.html` avec carte de trophée, nom du mot secret vainqueur, date et joueur masqué (`Visiteur #a1b2`).
- **Vérification :** Balisage HTML sémantique conforme et validation W3C/audit SEO.

### WOF-04 (🟠) — Cartes de Métriques KPIs Communautaires
- **Problème :** Le visiteur n'a aucune visibilité sur la difficulté globale du jeu ni sur l'efficacité de l'IA.
- **Correctif :** Ajout de 4 cartes métriques (`Taux de réussite IA`, `Défis joués`, `Coups moyens`, `Mots invaincus`) avec compteurs animés et icônes adaptées au mode clair/sombre.
- **Vérification :** Calcul exact des pourcentages et mise à jour dynamique sans rechargement de page.

### WOF-05 (🟠) — Bandeau Statut Joueur & Quota Restant
- **Problème :** Le quota horaire de 10 défis par heure est invisible pour le joueur tant qu'il n'atteint pas le blocage HTTP 429.
- **Correctif :** Affichage d'un bandeau discret `#defi-player-banner` indiquant l'alias anonyme du joueur, son historique personnel de victoires/défaites et le nombre de défis restants sur l'heure en cours.
- **Vérification :** Mise à jour du solde de défis restants à chaque nouvelle soumission.

### WOF-06 (🟡) — Replay Interactif du Cheminement via Modale
- **Problème :** Impossible pour un joueur de revivre pas à pas les tentatives de l'IA sur un mot du Wall of Fame ou de son historique.
- **Correctif :** Branchement d'un bouton d'action *"👁️ Revoir le chemin"* appelant `GET /api/challenge/<id>/guesses` et injectant le résultat dans `openTrajectoryModal()` (`volumes/web/js/trajectory.js`).
- **Vérification :** Ouverture fluide de la modale de trajectoire au clic avec rendu visuel identique au mode principal.

