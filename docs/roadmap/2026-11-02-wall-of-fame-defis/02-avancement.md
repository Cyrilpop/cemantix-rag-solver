# 📊 Avancement — Wall of Fame, Exploitation des KPIs & Visualisation Interactive des Défis

> **Évolution :** [2026-11 · Wall of Fame & Replay des Défis Visiteurs](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m9-wall-of-fame-ui` (base `origin/main`)  
> **Dernière mise à jour :** 04/11/2026  

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`WOF-01` à `WOF-06`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **0** | 0 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **6** | 2 |
| **Total suivis** | **6** | **2** |

Répartition par criticité : 🔴 `WOF-01` (API KPIs avec cache TTL), `WOF-02` (API Replay cheminement) · 🟠 `WOF-03` (Composants Wall of Fame), `WOF-04` (Cartes KPIs dynamiques), `WOF-05` (Bandeau joueur & quota) · 🟡 `WOF-06` (Branchement modale de trajectoire).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **WOF-01** | 🔴 | Endpoint API /api/challenge/kpis avec Cache TTL 15s | `⬜ À faire` | Spécifié dans Jalon M9 et src/api/routes/challenge.py. |
| **WOF-02** | 🔴 | Endpoint API /api/challenge/<id>/guesses (Replay du Chemin) | `⬜ À faire` | Spécifié dans Jalon M9 et src/api/routes/challenge.py. |
| **WOF-03** | 🟠 | Composants HTML & Design du Wall of Fame (/defi/) | `⬜ À faire` | Spécifié dans Jalon M9 et volumes/web/defi/index.html. |
| **WOF-04** | 🟠 | Cartes de Métriques KPIs Communautaires | `⬜ À faire` | Spécifié dans Jalon M9 et volumes/web/defi/index.html. |
| **WOF-05** | 🟠 | Bandeau Statut Joueur & Quota Restant | `⬜ À faire` | Spécifié dans Jalon M9 et volumes/web/defi/index.html. |
| **WOF-06** | 🟡 | Replay Interactif du Cheminement via Modale | `⬜ À faire` | Spécifié dans Jalon M9 et volumes/web/js/defi.js. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 04/11/2026 | — | Ouverture de l'évolution M9 et rédaction du plan de conception. |

