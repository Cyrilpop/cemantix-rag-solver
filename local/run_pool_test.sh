#!/usr/bin/env bash
# Test A/B de la fuite de connexions (PERF-06).
#   A = image telle quelle (code sans pool)
#   B/C = meme image, /app/src remplace par le code corrige du depot
# Aucun `docker cp` : /tmp du conteneur web est un tmpfs, inaccessible a docker cp.
set -u
REPO=/mnt/c/dev/cemantix-rag-solver
IMG=cemantix:latest
NET=web-net

# On reprend la configuration de base de donnees du conteneur web en marche.
ENVS=""
while IFS= read -r line; do
  [ -n "$line" ] && ENVS="$ENVS -e $line"
done < <(docker exec cemantix_web env | grep -E '^(DB_|DATABASE_URL|SQLITE_PATH)')
echo "### configuration reprise du conteneur web :"
docker exec cemantix_web env | grep -E '^(DB_|DATABASE_URL|SQLITE_PATH)' | sed 's/=.*/=…/'

run() { # $1 = nb threads, $2 = "old" | "new"
  local n=$1 mode=$2 extra=""
  [ "$mode" = "new" ] && extra="-v $REPO/src:/app/src:ro"
  # shellcheck disable=SC2086
  docker run --rm --network $NET $ENVS $extra \
    -v $REPO/local:/local:ro --entrypoint python $IMG /local/test_pool.py "$n"
}

echo
echo "### A — ANCIEN code (sans pool), 40 threads courts"
run 40 old

echo
echo "### B — NOUVEAU code (avec pool), 200 threads courts"
run 200 new

echo
echo "### C — NOUVEAU code, encore 200 threads (le compteur doit rester plat)"
run 200 new

