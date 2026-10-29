"""Test de non-fuite de connexions (PERF-06).

Usage : python test_pool.py <nb_threads>
Depuis /tmp/t (copie de /app/src) pour comparer l'ancien et le nouveau code.
"""
import sys
import threading

sys.path.insert(0, "/app")  # le paquet `src` vit a la racine de l'application

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50

from src.db.connection import db  # noqa: E402

db.init_db()
print(f"moteur = {db.get_engine_type()}")

errors = []


def work(i):
    try:
        db.fetch_one("SELECT 1 AS x")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{i}: {type(exc).__name__}: {exc}")


threads = [threading.Thread(target=work, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"threads courts crees = {N}")
print(f"erreurs = {len(errors)}")
for e in errors[:3]:
    print("   ", e[:120])

# Seconde salve : c'est ce qui se passe en production (d'autres requetes arrivent
# apres la mort des threads). Sans pool, chaque salve ajoute ses connexions.
threads2 = [threading.Thread(target=work, args=(1000 + i,)) for i in range(N)]
for t in threads2:
    t.start()
for t in threads2:
    t.join()
print(f"total threads courts crees = {2 * N}")

if hasattr(db, "pool_stats"):
    print("pool =", db.pool_stats())

if db.get_engine_type() == "postgres":
    row = db.fetch_one(
        "SELECT count(*) AS n FROM pg_stat_activity WHERE usename = current_user"
    )
    print("connexions ouvertes cote PostgreSQL =", row["n"])
else:
    print("mode sqlite : mesure pg_stat_activity non applicable")
