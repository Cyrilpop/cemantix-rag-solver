# Jalon M16 — Espace « Mon compte », Gestion Avancée du Profil, Sécurité, Mots de Récupération & Statistiques de Jeu

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m16-espace-mon-compte` (base `main`)  
**Statut :** ✅ Réalisé & Validé sous Docker (14/11/2026)  
**Périmètre exclusif :** `database/init.sql`, `src/db/connection.py`, `src/db/account.py`, `src/api/routes/account.py`, `volumes/web/account/index.html`, `volumes/web/js/account.js`, `volumes/web/css/account.css`, `volumes/web/js/header.js`, `volumes/web/css/modal.css` (conservation et maintien du moteur de modales, notamment pour la modale d'inscription / enregistrement rapide et les indices M15), suite de tests sous Docker (`tests/test_account.py`), et documentation associée (`docs/roadmap/2026-11-10-espace-mon-compte/`, `docs/roadmap/README.md`, `README.md`, `CHANGELOG.md`).  
**Périmètre exclu pour ce jalon :** Pas de modification des logiques de jeu solo (M15) ou multijoueur existantes, hors routage, intégration header et liens de navigation associés.  
**Suite de validation requise :** Tests unitaires automatisés sous Docker Python 3.12 (`docker compose run --rm -v ./tests:/app/tests --entrypoint python cemantix -m unittest discover -s tests`), `tools/check_docs.py`, `tools/build_css_bundles.py --check`.  
**Règle d'or environnement :** L'intégralité du projet s'exécute sous Docker. Aucune commande Python, pip ou test ne doit être exécutée directement sur la machine hôte. Toutes les variables et clés de code doivent respecter la convention camelCase en anglais.

---

## 1. Objectifs Métier et Expérience Utilisateur (UX)

Le présent **Jalon M16** structure l'espace de gestion identitaire et sécuritaire de la plateforme autour d'une page dédiée tout en préservant la fluidité d'accès via des modales contextuelles pour l'onboarding rapide :

1. **Page Dédiée « Mon compte » & Navigation par Menu Vertical :**
    - Création d'une vue dédiée accessible via une route propre (`/account/`) et reliée directement aux liens de compte existants dans le header universel.
    - Intégration d'un menu vertical de navigation interne à la page de compte permettant de basculer fluidement entre les différentes sections (Sécurité, Mots de récupération, Statistiques de jeu).
    - **Maintien du Moteur de Modales :** Le système global de modales est pleinement conservé et utilisé (notamment pour la modale d'inscription / enregistrement rapide depuis le header et la modale de choix d'indices du Jalon M15).

2. **Gestion Dynamique selon l'État d'Authentification :**
    - **Si l'utilisateur est connecté :**
        - Accès à la page dédiée `/account/` regroupant les options de sécurité, les mots de récupération, les statistiques personnelles et un bouton explicite "Se déconnecter".
    - **Si l'utilisateur n'est pas connecté :**
        - Possibilité d'utiliser la **modale d'enregistrement / inscription rapide** directement depuis le header pour un accès immédiat sans friction, ou de naviguer vers les vues publiques.

3. **Sécurité et Mots de Récupération :**
    - **Changement de mot de passe :** Formulaire sécurisé exigeant l'ancien mot de passe et un nouveau mot de passe conforme aux exigences de robustesse.
    - **Mots de récupération :** Espace dédié pour consulter le statut, générer ou régénérer des **mots de récupération aléatoires et sécurisés** attribués par le système (permettant la restauration du compte en cas d'oubli).

4. **Statistiques Personnelles de Jeu :**
    - Tableau de bord ludique et synthétique regroupant les statistiques personnelles du joueur : nombre total de parties jouées, taux de réussite, nombre moyen de coups par victoire, meilleur score, temps moyen de résolution et historique des indices utilisés.

---

## 2. Spécification Technique & Schéma Relationnel

### 2.1 Schéma Relationnel PostgreSQL & Idempotence (`database/init.sql`)

Toutes les créations de tables et modifications de colonnes sont strictement idempotentes (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, blocs de contrôle conditionnels `information_schema.columns`) :

```sql
-- ============================================================================
-- 12. Extensions de Sécurité et Mots de Récupération Compte (Jalon M16)
-- ============================================================================

-- A. Table des mots de récupération associés au profil joueur
CREATE TABLE IF NOT EXISTS player_recovery_words (
    id          SERIAL PRIMARY KEY,
    player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    word_hash   VARCHAR(255) NOT NULL,          -- Hash sécurisé du mot aléatoire de récupération
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, word_hash)
);
CREATE INDEX IF NOT EXISTS idx_player_recovery_words_player ON player_recovery_words(player_id);

-- B. Ajout de colonnes de suivi de sécurité dans la table players si non présentes
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='players' and column_name='password_updated_at') THEN
        ALTER TABLE players ADD COLUMN password_updated_at TIMESTAMPTZ DEFAULT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='players' and column_name='last_login_at') THEN
        ALTER TABLE players ADD COLUMN last_login_at TIMESTAMPTZ DEFAULT NULL;
    END IF;
END $$;
```

### 2.2 Repli Local Idempotent SQLite (`src/db/connection.py`)

Les schémas DDL correspondants sont déclarés dans `PG_SCHEMA` et `SQLITE_SCHEMA` dans `src/db/connection.py` pour supporter nativement les tests unitaires locaux sans conteneur PostgreSQL :
- `id INTEGER PRIMARY KEY AUTOINCREMENT` pour les clés auto-incrémentées SQLite.
- `UUID` représenté en `TEXT` et `BOOLEAN` sous forme `INTEGER (0/1)`.

---

## 3. Étude d'Impact & Estimation de la Volumétrie BDD

L'ajout de la table `player_recovery_words` et des métadonnées de sécurité sur `players` présente une empreinte disque négligeable et prévisible.

### 3.1 Poids Unitaire d'une Ligne
- **Ligne de mot de récupération (`player_recovery_words`) :** ~80 octets de données + ~48 octets d'index = **~128 octets par mot**.
- **Mise à jour de session / profil joueur :** Ajout de quelques octets de horodatage (`password_updated_at`, `last_login_at`) dans la table `players`.

### 3.2 Projections de Croissance
*Hypothèses :*
- Chaque utilisateur dispose de 4 mots de récupération générés par le système.
- Croissance linéaire basée sur le nombre total de comptes actifs enregistrés.

| Métrique / Scénario | 🟢 Profil Modeste (1 000 comptes) | 🟡 Profil Moyen (10 000 comptes) | 🔴 Profil Élevé (100 000 comptes) |
|---|---|---|---|
| **Mots de récupération stockés (4/compte)** | 4 000 lignes | 40 000 lignes | 400 000 lignes |
| **Volumétrie BDD globale additionnelle** | **~512 Ko** | **~5,1 Mo** | **~51,2 Mo** |

---

## 4. Implémentation Sécurité & Gestion des Mots de Récupération Aléatoires

1. **Génération Aléatoire & Hachage :**
    - Les mots de récupération ne sont **jamais saisis par l'utilisateur** (ce qui élimine les choix faibles ou prévisibles). Ils sont générés aléatoirement par le système à partir d'un dictionnaire français sécurisé (ex: 4 à 6 mots).
    - Seuls les hachages cryptographiques de ces mots sont stockés en base (`player_recovery_words`), garantissant qu'aucune lecture en clair n'est possible côté serveur.
2. **Affichage Unique & Flux de Régénération :**
    - L'ensemble des mots générés est affiché **une seule fois** en clair à l'utilisateur lors de leur création initiale ou d'une demande de régénération, avec une invitation forte à les noter.
    - Toute demande de régénération depuis la page `/account/` invalide et purge immédiatement l'ancien jeu de mots pour enregistrer le nouveau lot.
3. **Traçabilité des Connexions :**
    - Mise à jour automatique de `last_login_at` à chaque authentification réussie et de `password_updated_at` lors d'un changement de mot de passe.

---

## 5. Endpoints API REST Backend (`src/api/routes/account.py`)

Définition des endpoints dédiés à la gestion du compte sous architecture Docker :

- `GET /api/account/profile` : Récupère les informations du profil connecté (`pseudo`, `createdAt`, `passwordUpdatedAt`, `lastLoginAt`).
- `POST /api/account/password` : Modifie le mot de passe de l'utilisateur authentifié (vérification de l'ancien mot de passe, hachage, mise à jour de `password_updated_at`).
- `GET /api/account/recovery` : Récupère le statut de configuration des mots de récupération (si les mots ont été générés, date de création, nombre de mots configurés, sans exposition des mots en clair).
- `POST /api/account/recovery` : Déclenche la régénération d'un nouveau jeu de mots de récupération aléatoires et sécurisés (retournés une seule fois en clair pour affichage).
- `GET /api/account/stats` : Agrège et retourne les statistiques de jeu personnelles du joueur (parties solo jouées, taux de réussite, coups moyens, meilleur score, temps moyen, indices utilisés).
- `POST /api/account/logout` : Clôture la session active côté serveur et supprime le jeton d'authentification.

---

## 6. Schémas d'Interface & Workflows UI (Modale Rapide vs Page Dédiée)

### 6.1 Schéma de la Modale d'Inscription / Connexion Rapide (accessible depuis le Header)
Cette modale est maintenue pour fluidifier l'onboarding sans quitter la page de jeu :

```text
+---------------------------------------------------------------+
| 🔐 Cémantix — Accès Rapide Compte                      [ X ]  |
+---------------------------------------------------------------+
|  [ 🟢 Se connecter ]   |   [ ⚪ S'inscrire ]    |
+---------------------------------------------------------------+
|                                                               |
|  Nom d'utilisateur (Pseudo) :                                 |
|  [ Ex: CastorCosmique                                       ] |
|                                                               |
|  Mot de passe :                                               |
|  [ **********************************                       ] |
|                                                               |
|  *(À l'inscription, 4 mots de récupération aléatoires seront  |
|    générés et affichés immédiatement à valider)*              |
|                                                               |
|  [ Valider et Entrer ]                                        |
+---------------------------------------------------------------+
```

### 6.2 Schéma de la Page Dédiée `/account/` (Gestion Approfondie)
```text
+-------------------------------------------------------------------------+
  [Header Universel : Marque, Badge Joueur, Lien "Mon compte"]
+-------------------------------------------------------------------------+
  [Menu Vertical (/account/)] |  Contenu Principal de la Section Active
  --------------------------- |  ---------------------------------------------
  > Sécurité                  |  [Gestion des mots de récupération]
    Mots de récupération      |   - Statut : Configurés (4 mots aléatoires)
    Statistiques de jeu       |   - [ Régénérer de nouveaux mots ] *(Affichage unique)*
    Déconnexion               |  
+-----------------------------+-------------------------------------------+
```

---

## 7. Plan d'Exécution & Découpage des Chantiers

1. **ACC-01 :** Schéma relationnel et migrations SQL idempotentes (`database/init.sql`, `src/db/connection.py`).
2. **ACC-02 :** Module DAO de gestion des comptes, authentification et génération/hachage des mots de récupération aléatoires (`src/db/account.py`, `src/db/__init__.py`).
3. **ACC-03 :** Implémentation des routes API REST de gestion de compte (`src/api/routes/account.py`, enregistrement dans `src/api/main.py`).
4. **ACC-04 :** Maintien du moteur global de modales (pour l'inscription rapide et les indices M15).
5. **ACC-05 :** Développement de la page dédiée `/account/index.html`, du menu vertical et de la logique front-end incluant l'affichage unique des mots aléatoires (`volumes/web/js/account.js`, `volumes/web/css/account.css`).
6. **ACC-06 :** Mise à jour du header universel (`volumes/web/js/header.js`) pour router vers `/account/` et conserver la modale d'inscription rapide.
7. **ACC-07 :** Développement de la suite de tests unitaires sous Docker (`tests/test_account.py`).
8. **ACC-08 :** Validation finale, audit de documentation (`tools/check_docs.py`), compilation CSS et mise à jour des journaux (`CHANGELOG.md`, `README.md`).