# 📊 Avancement — Traçage en BDD & Métriques KPI des Défis Visiteurs

> **Évolution :** [2026-11 · Traçage & KPIs des Défis Visiteurs](../README.md) · document 2/2  
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).  
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**  
> **Branche :** `feature/m8-defi-kpi-analytics` (base `origin/main`)  
> **Dernière mise à jour :** 04/11/2026  

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`KPI-01` à `KPI-06`).
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

Répartition par criticité : 🔴 `KPI-01` (DDL idempotent & double dialecte), `KPI-02` (Pseudonymisation RGPD) · 🟠 `KPI-03` (DAO d'enregistrement atomique), `KPI-04` (Calcul & agrégation des KPIs), `KPI-05` (API REST HTTP) · 🟡 `KPI-06` (Interface utilisateur & intégration `/defi/`).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **KPI-01** | 🔴 | Schéma DDL Idempotent & Double Dialecte (PostgreSQL / SQLite) | `⬜ À faire` | Spécifié dans Jalon M8 et database/init.sql. |
| **KPI-02** | 🔴 | Pseudonymisation RGPD & Masquage de l'ID Joueur | `⬜ À faire` | Spécifié dans Jalon M8 et src/db/challenges.py. |
| **KPI-03** | 🟠 | Couche DAO d'Enregistrement Atomique & Idempotent | `⬜ À faire` | Spécifié dans Jalon M8 et src/db/challenges.py. |
| **KPI-04** | 🟠 | Moteur de Calcul & Agrégation des KPIs | `⬜ À faire` | Spécifié dans Jalon M8 et src/db/challenges.py. |
| **KPI-05** | 🟠 | Endpoint API REST `/api/challenge/kpis` | `⬜ À faire` | Spécifié dans Jalon M8 et src/api/routes/challenge.py. |
| **KPI-06** | 🟡 | Interface Utilisateur & Affichage des Statistiques (`/defi/`) | `⬜ À faire` | Spécifié dans Jalon M8 et volumes/web/defi/. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 04/11/2026 | — | Ouverture de l'évolution et rédaction de la spécification technique Jalon M8. |

