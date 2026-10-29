#!/usr/bin/env python3
"""
Cémantix Solver — Jeu de données de démonstration (hors git, local/)
====================================================================
Peuple `daily_puzzles` pour pouvoir tester le rendu du tableau de bord
sans attendre la fin de l'indexation ChromaDB du worker.

Passage OBLIGATOIRE par src.db.save_daily_puzzle() : c'est exactement le chemin
d'écriture du démon (daemon.run_daily_solver), donc le format des lignes insérées
est garanti identique au réel — pas de SQL écrit à la main qui divergerait du
schéma ou de la logique de upsert.

Exécution (le fichier n'est pas copié dans l'image, on le passe par stdin) :
    wsl.exe -d Ubuntu-20.04 -- docker exec -i cemantix_worker python - \\
        < /mnt/c/dev/cemantix-rag-solver/local/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from src.db import save_daily_puzzle  # noqa: E402


def traj(steps):
    """steps: (word, score, permille, source, is_record) -> liste de pas."""
    return [
        {
            "step": i + 1,
            "word": w,
            "score": s,
            "permille": p,
            "source": src,
            "is_record": rec,
        }
        for i, (w, s, p, src, rec) in enumerate(steps)
    ]


def tops(steps, n=8):
    """Top N par score, comme le fait le solveur (meilleures tentatives)."""
    best = sorted(steps, key=lambda x: x[1], reverse=True)[:n]
    return [{"word": w, "score": s, "permille": p} for (w, s, p, _, _) in best]


# ---------------------------------------------------------------------------
# 5 puzzles : 4 résolus + 1 échec (pour que le taux de victoire ne soit pas
# artificiellement à 100 % et que le badge « Échec » soit testé lui aussi).
# ---------------------------------------------------------------------------

TODAY = ("2026-10-27", 1471, "volcan", 12, 13, 214.6, "rag", False, [
    ("montagne",  21.3,  412, "seed",   True),
    ("mer",        6.8, None, "seed",   False),
    ("lave",      48.9,  890, "rag",    True),
    ("éruption",  52.4,  934, "rag",    True),
    ("cratère",   46.1,  845, "rag",    False),
    ("chaleur",   24.7,  480, "rag",    False),
    ("magma",     55.8,  958, "rag",    True),
    ("soufre",    41.2,  760, "rag",    False),
    ("islande",   33.5,  620, "llm",    False),
    ("séisme",    29.8,  540, "rag",    False),
    ("terre",     27.4,  505, "sniper", False),
    ("volcan",   100.0, 1000, "rag",    True),
])

D26 = ("2026-10-26", 1470, "bibliothèque", 6, 7, 168.2, "rag", True, [
    ("livre",        61.2,  968, "seed",   True),
    ("librairie",    44.8,  812, "rag",    False),
    ("école",        28.4,  512, "seed",   False),
    ("lecteur",      39.6,  731, "rag",    False),
    ("roman",        33.1,  615, "rag",    False),
    ("bibliothèque", 100.0, 1000, "sniper", True),
])

D25 = ("2026-10-25", 1469, "orchestre", 7, 8, 152.9, "llm", True, [
    ("musique",     58.6,  957, "seed", True),
    ("concert",     46.9,  851, "rag",  False),
    ("symphonie",   51.3,  928, "rag",  True),
    ("violon",      43.7,  795, "rag",  False),
    ("piano",       37.2,  690, "rag",  False),
    ("philharmonie", 55.1, 944, "llm",  False),
    ("orchestre",  100.0, 1000, "llm",  True),
])

# Échec volontaire : le mot n'est jamais atteint (meilleur permille 862).
D24 = ("2026-10-24", 1468, "orage", 287, 300, 4211.9, "rag", True, [
    ("plaine",     22.1,  402, "seed", False),
    ("pluie",      44.2,  812, "seed", True),
    ("nuage",      41.8,  780, "rag",  False),
    ("vent",       38.4,  705, "seed", False),
    ("foudre",     47.6,  862, "rag",  True),
    ("tempête",    40.1,  758, "rag",  False),
    ("tonnerre",   45.3,  831, "rag",  False),
    ("grêle",      33.7,  628, "rag",  False),
    ("ouragan",    36.9,  672, "llm",  False),
    ("inondation", 25.8,  470, "rag",  False),
])

D23 = ("2026-10-23", 1467, "démocratie", 7, 7, 141.3, "rag", True, [
    ("vote",       57.3,  952, "seed", True),
    ("élection",   52.8,  933, "rag",  False),
    ("parlement",  41.6,  779, "rag",  False),
    ("république", 39.2,  726, "rag",  False),
    ("citoyen",    45.7,  835, "rag",  False),
    ("liberté",    31.4,  590, "seed", False),
    ("démocratie", 100.0, 1000, "rag", True),
])

ROWS = [TODAY, D26, D25, D24, D23]

for date, puzzle, word, tries, attempts, duration, source, revealed, steps in ROWS:
    won = 1000 in [s[2] for s in steps]
    entry = {
        "date": date,
        "puzzle": puzzle,
        "word": word,
        "tries": tries,
        "attempts": attempts,
        "source": source,
        "duration_seconds": duration,
        "win": won,
        "top_guesses": tops(steps),
        "trajectory": traj(steps),
        "is_revealed": revealed,
        "timestamp": f"{date}T00:00:{(puzzle % 60):02d}+02:00",
    }
    save_daily_puzzle(entry)
    print(f"  ✓ {date}  #{puzzle}  {word:<14} "
          f"{'trouvé' if won else 'ÉCHEC'}  {len(steps)} pas")

print("\nDonnées de démonstration insérées (upsert sur la date, ré-exécutable).")
