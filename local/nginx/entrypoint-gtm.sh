#!/bin/sh
# =============================================================================
# Cémantix Solver — Démarrage nginx avec identifiant Google Tag Manager
# -----------------------------------------------------------------------------
# Les pages HTML (versionnées et générées) ne portent que le jeton littéral
# GOOGLE_TAG_MANAGER_ID. L'identifiant réel, fourni par .env via la variable
# d'environnement du conteneur, n'est inséré QUE dans la réponse HTTP, via la
# directive nginx `sub_filter`. Il ne touche donc jamais le disque suivi par git.
#
# Le fichier de configuration est monté en lecture seule (:ro) : on ne peut pas
# le réécrire en place. On le copie donc dans /tmp (writable, déjà utilisé par
# nginx pour ses chemins temporaires) en résolvant le marqueur %%GTM_ID%% par la
# valeur de $GOOGLE_TAG_MANAGER_ID, puis on démarre nginx sur cette copie.
#
# Sans variable d'environnement (développement, CI), le marqueur est résolu en
# le jeton GOOGLE_TAG_MANAGER_ID lui-même : cible et remplacement deviennent
# identiques, `sub_filter` ne modifie rien, et le navigateur ne part jamais en
# quête d'un conteneur `id=` vide — aucun suivi actif, aucun échec de démarrage.
#
# Usage (entrypoint du service cemantix_nginx) :
#   /docker-entrypoint.sh /local/nginx/entrypoint-gtm.sh
# =============================================================================
set -eu

CONF_SRC="/etc/nginx/conf.d/default.conf"
CONF_DIR="/tmp/conf.d"
CONF_DST="$CONF_DIR/default.conf"
NGINX_CONF="/tmp/nginx.conf"

mkdir -p "$CONF_DIR"

# 1. Copie du point d'entrée http vers /tmp, en redirigeant l'inclusion des
#    conf de serveur vers le répertoire writable.
sed 's#include /etc/nginx/conf.d/\*.conf;#include /tmp/conf.d/*.conf;#' \
    /etc/nginx/nginx.conf > "$NGINX_CONF"

# 2. Résolution du marqueur GTM dans la copie du serveur.
#    %%GTM_ID%% (et rien d'autre) est remplacé : la cible de sub_filter, qui
#    contient le mot GOOGLE_TAG_MANAGER_ID, reste intacte.
#    Le guillemet simple protège le $ de la substitution shell : nginx reçoit
#    bien la valeur de la variable, pas une référence à une variable nginx.
sed "s|%%GTM_ID%%|${GOOGLE_TAG_MANAGER_ID:-GOOGLE_TAG_MANAGER_ID}|g" "$CONF_SRC" > "$CONF_DST"

if [ -n "${GOOGLE_TAG_MANAGER_ID:-}" ]; then
    echo "[gtm] Mesure d'audience active : sub_filter vers $GOOGLE_TAG_MANAGER_ID"
else
    echo "[gtm] GOOGLE_TAG_MANAGER_ID absent : placeholder livré, aucun suivi actif"
fi

# 3. Validation puis démarrage sur la configuration résolue.
exec nginx -g 'daemon off;' -c "$NGINX_CONF"
