#!/usr/bin/env bash
# =============================================================================
# Cémantix Solver — Préparation de l'environnement de test WSL (hors git)
# -----------------------------------------------------------------------------
# Ce script est IDEMPOTENT : relançable sans effet de bord.
# Il lève les 4 prérequis bloquants constatés sur l'hôte :
#   1. aucun .env                -> docker compose ne peut pas démarrer Postgres
#   2. réseau externe web-net    -> exigé par docker-compose.yml:177 (external: true)
#   3. pas d'egress pour le démon -> proxy d'entreprise NTLM, porté par cntlm:3129
#   4. utilisateur hors groupe docker -> sudo nécessaire
#
# Utilisation :  bash /mnt/c/dev/cemantix-rag-solver/local/setup-wsl.sh
# =============================================================================
set -euo pipefail

REPO="/mnt/c/dev/cemantix-rag-solver"
PROXY="http://127.0.0.1:3129"          # cntlm local (porte l'auth NTLM du proxy parent)
DROPIN="/etc/systemd/system/docker.service.d/proxy.conf"
cd "$REPO"

echo "=== 1/5  Fichier .env ==="
if [ ! -f .env ]; then
    DB_PASS="$(openssl rand -hex 16 2>/dev/null || date +%s%N | sha256sum | cut -c1-32)"
    umask 077
    cat > .env <<EOF
DB_HOST=cemantix_db
DB_PORT=5432
DB_NAME=cemantix
DB_USER=cemantix_user
DB_PASS=${DB_PASS}
TZ=Europe/Paris
PYTHONUNBUFFERED=1
LM_API=http://host.docker.internal:1234/v1
LLM_MODEL=qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2
W2V_FILE=frWac_no_postag_phrase_500_cbow_cut10.bin
MAX_VOCAB=150000
EOF
    echo "[OK]  .env généré (mot de passe Postgres aléatoire, 600)"
else
    echo "[SKIP] .env déjà présent — non écrasé"
fi

echo "=== 2/5  Proxy du démon Docker (egress cntlm) ==="
if [ ! -f "$DROPIN" ]; then
    sudo mkdir -p /etc/systemd/system/docker.service.d
    sudo tee "$DROPIN" >/dev/null <<EOF
[Service]
Environment="HTTP_PROXY=${PROXY}"
Environment="HTTPS_PROXY=${PROXY}"
Environment="NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,cemantix_db,cemantix_web,cemantix_worker,web-net"
EOF
    sudo systemctl daemon-reload
    sudo systemctl restart docker
    echo "[OK]  drop-in créé, docker redémarré"
else
    echo "[SKIP] drop-in proxy déjà présent"
fi

echo "=== 3/5  Proxy de build pour les conteneurs ==="
mkdir -p "$HOME/.docker"
if [ ! -f "$HOME/.docker/config.json" ]; then
    cat > "$HOME/.docker/config.json" <<EOF
{
  "proxies": {
    "default": {
      "httpProxy":  "${PROXY}",
      "httpsProxy": "${PROXY}",
      "noProxy":    "localhost,127.0.0.1,::1,cemantix_db,cemantix_web,cemantix_worker"
    }
  }
}
EOF
    echo "[OK]  ~/.docker/config.json créé (apt + pip accessibles pendant le build)"
else
    echo "[SKIP] ~/.docker/config.json déjà présent — vérifier la clé 'proxies'"
fi

echo "=== 4/5  Accès docker sans sudo ==="
if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    echo "[INFO] '$USER' ajouté au groupe docker (effectif à la prochaine session ; sudo reste utilisé ici)"
else
    echo "[SKIP] '$USER' est déjà dans le groupe docker"
fi

echo "=== 5/5  Réseau externe web-net ==="
if sudo docker network inspect web-net >/dev/null 2>&1; then
    echo "[SKIP] réseau web-net déjà existant"
else
    sudo docker network create web-net >/dev/null
    echo "[OK]  réseau web-net créé"
fi

echo
echo "--- État du démon ---"
sudo docker info --format 'version={{.ServerVersion}}  httpProxy={{.HTTPProxy}}  httpsProxy={{.HTTPSProxy}}'
echo "--- Réseaux ---"
sudo docker network ls --filter name=web-net --format '{{.Name}} {{.Driver}}'
