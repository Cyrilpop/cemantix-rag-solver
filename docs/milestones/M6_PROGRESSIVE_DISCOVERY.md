# Jalon M6 — Persistance Relationnelle des Paliers d'Indices (daily_puzzle_hints)

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m6-db-hints` (base `main`)  
**Statut :** Spécification d'ingénierie & contrat d'implémentation BDD (Idempotent / Agent-Optimized)  
**Périmètre exclusif :** Couche de données relationnelle (`src/db/`), schéma DDL multi-dialecte (PostgreSQL / SQLite) et suite de tests unitaires.  
**Suite de validation requise :** 269 tests attendus au vert sous Docker Python 3.12 (268 existants + 1 suite M6).

---

## 1. Directives Architecturales pour l'Agent IA

⚠️ **À LIRE AVANT TOUTE MODIFICATION DE CODE :**
1. **Zéro altération de l'existant :** La table `daily_puzzles` ne doit PAS être modifiée. Aucun nouveau champ JSONB ne doit y être ajouté.
2. **Double Dialecte Obligatoire :** Toute modification du schéma DDL doit fonctionner sous PostgreSQL (production) et SQLite (tests locaux).
3. **Ordre DDL Strict :** La nouvelle table `daily_puzzle_hints` possède une clé étrangère (`REFERENCES daily_puzzles(date)`). Elle doit donc être déclarée **strictement après** la création de la table `daily_puzzles` dans tous les schémas pour satisfaire le `PRAGMA foreign_keys = ON;` de SQLite et l'idempotence de `init.sql`.
4. **Paramétrage SQL :** Dans les requêtes Python, utiliser impérativement `%s`. Ne jamais hardcoder `TRUE` ou `FALSE` dans les requêtes `UPDATE` ; passer les booléens Python (`True`/`False`) via les paramètres.

---

## 2. Modifications DDL (Infrastructure as Code)

### 2.1 Fichier cible : `database/init.sql` (PostgreSQL)
**Action :** Trouver la création de la table `daily_puzzles` et insérer le bloc suivant juste en dessous. Ce fichier garantit l'idempotence au (re)démarrage des conteneurs via le point de montage `/docker-entrypoint-initdb.d/init.sql`.

```sql
CREATE TABLE IF NOT EXISTS daily_puzzle_hints (
    id SERIAL PRIMARY KEY,
    puzzle_date DATE NOT NULL REFERENCES daily_puzzles(date) ON DELETE CASCADE,
    tier VARCHAR(8) NOT NULL,
    word VARCHAR(100) NOT NULL,
    score NUMERIC(6, 2) NOT NULL,
    is_revealed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, word)
);
CREATE INDEX IF NOT EXISTS idx_daily_hints_date ON daily_puzzle_hints(puzzle_date);
```

### 2.2 Fichier cible : `src/db/connection.py`
**Action 1 :** Trouver la constante texte `PG_SCHEMA` et y insérer le même bloc PostgreSQL (cf 2.1) juste après la table `daily_puzzles`.
**Action 2 :** Trouver la constante texte `SQLITE_SCHEMA` et y insérer le bloc SQLite suivant juste après la table `daily_puzzles` :

```sql
CREATE TABLE IF NOT EXISTS daily_puzzle_hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_date TEXT NOT NULL REFERENCES daily_puzzles(date) ON DELETE CASCADE,
    tier TEXT NOT NULL,
    word TEXT NOT NULL,
    score REAL NOT NULL,
    is_revealed BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, word)
);
CREATE INDEX IF NOT EXISTS idx_daily_hints_date ON daily_puzzle_hints(puzzle_date);
```

---

## 3. Implémentation des Fonctions CRUD

### 3.1 Fichier cible : `src/db/daily.py`
**Action :** Insérer ces trois fonctions à la fin du fichier. *Attention : Recopier la logique transactionnelle telle quelle pour garantir la compatibilité thread-safe et multi-dialecte.*

```python
def save_daily_hints(puzzle_date: str, hints: list[dict]) -> int:
    """Insère ou met à jour un lot d'indices."""
    query = """
    INSERT INTO daily_puzzle_hints (puzzle_date, tier, word, score, is_revealed)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (puzzle_date, word) DO UPDATE SET
        score = EXCLUDED.score,
        tier = EXCLUDED.tier,
        is_revealed = EXCLUDED.is_revealed;
    """
    inserted = 0
    with db.transaction() as conn:
        for hint in hints:
            q, p = db._format_query(query, (
                str(puzzle_date),
                str(hint["tier"]),
                str(hint["word"]),
                float(hint["score"]),
                bool(hint.get("is_revealed", False))
            ), db._determine_engine())
            conn.execute(q, p)
            inserted += 1
    return inserted

def get_daily_hints(puzzle_date: str, revealed_only: bool = True) -> list[dict]:
    """Récupère les indices d'un puzzle quotidien, triés par score décroissant."""
    if revealed_only:
        query = "SELECT * FROM daily_puzzle_hints WHERE puzzle_date = %s AND is_revealed = %s ORDER BY score DESC;"
        return db.fetch_all(query, (str(puzzle_date), True))
    query = "SELECT * FROM daily_puzzle_hints WHERE puzzle_date = %s ORDER BY score DESC;"
    return db.fetch_all(query, (str(puzzle_date),))

def reveal_daily_hint_tier(puzzle_date: str, tier: str) -> int:
    """Passe is_revealed à True pour un palier spécifique."""
    query = "UPDATE daily_puzzle_hints SET is_revealed = %s WHERE puzzle_date = %s AND tier = %s;"
    return db.execute(query, (True, str(puzzle_date), str(tier)))
```

### 3.2 Fichier cible : `src/db/__init__.py`
**Action :**
1. Ajouter `save_daily_hints`, `get_daily_hints`, et `reveal_daily_hint_tier` aux imports depuis `.daily`.
2. Ajouter ces trois noms de fonctions dans la liste `__all__`.

---

## 4. Stratégie de Test Unitaire

### 4.1 Fichier cible : `tests/test_db.py`
**Action :** Ajouter la méthode suivante dans la classe `TestDatabaseLayer` :

```python
    def test_daily_hints_crud(self):
        # 1. Prérequis : Sauvegarder un puzzle parent
        from src.db.daily import save_daily_hints, get_daily_hints, reveal_daily_hint_tier
        
        entry = {
            "date": "2026-11-01",
            "puzzle": 1800,
            "word": "secret",
            "tries": 10,
            "attempts": 10,
            "source": "rag",
        }
        self.assertTrue(save_daily_puzzle(entry))
        
        # 2. Insertion multi-paliers
        hints = [
            {"word": "froid", "score": 850.0, "tier": "800", "is_revealed": False},
            {"word": "tiède", "score": 910.0, "tier": "900", "is_revealed": False},
            {"word": "chaud", "score": 920.0, "tier": "900", "is_revealed": False},
            {"word": "brûlant", "score": 960.0, "tier": "950", "is_revealed": True}
        ]
        self.assertEqual(save_daily_hints("2026-11-01", hints), 4)
        
        # 3. Contrôle de lecture et filtre
        revealed = get_daily_hints("2026-11-01", revealed_only=True)
        self.assertEqual(len(revealed), 1)
        self.assertEqual(revealed[0]["word"], "brûlant")
        
        all_hints = get_daily_hints("2026-11-01", revealed_only=False)
        self.assertEqual(len(all_hints), 4)
        
        # 4. Révélation d'un palier
        affected = reveal_daily_hint_tier("2026-11-01", "900")
        self.assertEqual(affected, 2)
        
        new_revealed = get_daily_hints("2026-11-01", revealed_only=True)
        self.assertEqual(len(new_revealed), 3)
```

---

## 5. Exécution & Validation (Idempotente)

L'agent doit exécuter les commandes suivantes pour valider le code produit. Le déploiement s'appuiera nativement sur le montage de volume `init.sql`.

```bash
# 1. Vérification de la syntaxe Python
docker compose run --rm cemantix python -m py_compile src/db/connection.py src/db/daily.py tests/test_db.py

# 2. Exécution de la suite de tests (attendu: ~269 tests, 0 échecs)
docker run --rm -v $(pwd):/app -w /app python:3.12-slim sh -c \
  "pip install --no-cache-dir -r requirements.txt && python -m unittest discover -s tests -v"
```

## 6. Manuel de Déploiement Idempotent

Grâce à `init.sql` et `CREATE TABLE IF NOT EXISTS`, la mise à jour de la base se fait nativement au redémarrage des services, sans aucune commande SQL manuelle.

```bash
# 1. Reconstruction des images (pour inclure le nouveau code Python)
docker compose build

# 2. Redémarrage des services (le volume mount injectera init.sql dans Postgres)
docker compose down
docker compose up -d
```