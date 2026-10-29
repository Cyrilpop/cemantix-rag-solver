#!/usr/bin/env bash
# Rebuild de l'image avec le code corrige, puis redemarrage des services.
# DOCKER_BUILDKIT=0 + --network=host : requis sur ce poste (proxy d'entreprise,
# cntlm sur 127.0.0.1:3129 inaccessible depuis un reseau bridge de build).
set -eu
cd /mnt/c/dev/cemantix-rag-solver
echo "### debut $(date +%T)"
env DOCKER_BUILDKIT=0 docker build --network=host --pull=false -t cemantix:latest . 2>&1 \
  | grep -Ei 'sending build context|Successfully|Step 1/|error|ERROR' | head -30
echo "### build termine $(date +%T)"
docker compose -f docker-compose.yml -f local/docker-compose.test.yml up -d --force-recreate cemantix_web 2>&1 | tail -3
echo "### services relances $(date +%T)"
sleep 25
docker ps --format '{{.Names}} {{.Status}}' | grep cemantix
echo "### FIN"
