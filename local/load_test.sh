#!/usr/bin/env bash
# Charge le vrai serveur web et compte les connexions PostgreSQL cote serveur.
# Avant le correctif, ce compteur croissait d'une unite par requete.
set -u
N=${1:-200}

count() {
  docker exec cemantix_db psql -U cemantix_user -d cemantix -t -A \
    -c "SELECT count(*) FROM pg_stat_activity WHERE usename='cemantix_user';"
}

echo "connexions AVANT charge : $(count)"
for i in $(seq 1 "$N"); do
  curl -s -m 5 -o /dev/null "http://localhost:8090/api/daily?i=$i"
done
echo "apres $N requetes /api/daily : $(count)"
for i in $(seq 1 "$N"); do
  curl -s -m 5 -o /dev/null -X POST -H 'Content-Type: application/json' \
       -d '{}' "http://localhost:8090/api/game/daily-info?i=$i"
done
echo "apres $N POST supplementaires : $(count)"
echo "sante du web : $(docker ps --format '{{.Names}} {{.Status}}' | grep cemantix_web)"
