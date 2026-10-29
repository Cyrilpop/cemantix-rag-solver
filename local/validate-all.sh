#!/usr/bin/env bash
# Validation de bout en bout après la série de correctifs.
#   1. tests unitaires (hors conteneur applicatif : base SQLite en mémoire)
#   2. rebuild de l'image
#   3. redéploiement des services
#   4. smoke test complet via nginx
set -u
cd /mnt/c/dev/cemantix-rag-solver || exit 1
echo "############ 1. TESTS UNITAIRES  $(date +%T)"
rm -rf /tmp/vt && mkdir -p /tmp/vt
cp -r tests src /tmp/vt/
docker run --rm -w /app -v /tmp/vt:/app:ro --entrypoint python \
  cemantix:latest -m unittest discover -s tests 2>&1 | tail -4

echo "############ 2. REBUILD  $(date +%T)"
env DOCKER_BUILDKIT=0 docker build --network=host --pull=false -t cemantix:latest . 2>&1 \
  | grep -Ei 'sending build context|^Successfully' | tail -3

echo "############ 3. REDEPLOIEMENT  $(date +%T)"
docker compose -f docker-compose.yml -f local/docker-compose.test.yml \
  up -d --force-recreate cemantix_web cemantix_worker 2>&1 | tail -2
sleep 30
docker ps --format '{{.Names}} {{.Status}}' | grep cemantix

echo "############ 4. SMOKE TEST  $(date +%T)"
bash local/smoke-test.sh 2>&1 | tail -22

echo "############ 5. NON-FUITE  $(date +%T)"
bash local/load_test.sh 60 2>&1 | tail -4
echo "############ FIN  $(date +%T)"
