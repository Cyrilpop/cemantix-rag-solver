#!/usr/bin/env bash
# Reconstruit .env avec un mot de passe NEUF, et l'applique a la base existante.
#
# Contexte : .env a ete supprime accidentellement, et le conteneur de base a ete
# recree sans lui — ses variables POSTGRES_* sont donc vides, alors que le volume,
# lui, a conserve le mot de passe d'initialisation. La valeur d'origine n'est
# recuperable nulle part : on en genere un nouveau et on le declare a PostgreSQL.
#
# Ca fonctionne parce que l'authentification par socket local est en trust : on
# peut donc faire un ALTER ROLE depuis l'interieur du conteneur sans connaissance
# de l'ancien mot de passe. Les connexions TCP (celles de l'appli) restent protegees.
set -eu
cd /mnt/c/dev/cemantix-rag-solver

NEWPASS=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
DB_NAME=cemantix
DB_USER=cemantix_user

# Nom reellement present en base (le volume a pu etre initialise avec d'autres valeurs).
# Pas de role `postgres` ici : le role cree a l'initialisation EST le superutilisateur.
ACTUAL_USER=$(docker exec cemantix_db psql -U postgres -tAc \
  "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg\_%' LIMIT 1;" 2>/dev/null || true)
if [ -z "${ACTUAL_USER:-}" ]; then
  ACTUAL_USER=$(docker exec cemantix_db psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT current_user;" 2>/dev/null || true)
fi
if [ -n "${ACTUAL_USER:-}" ]; then DB_USER="$ACTUAL_USER"; fi

echo "base : $DB_NAME / utilisateur : $DB_USER"

# Le role change son PROPRE mot de passe : c'est ce que permet l'authentification
# trust sur socket local, sans avoir a connaitre l'ancienne valeur.
docker exec cemantix_db psql -U "$DB_USER" -d "$DB_NAME" -c \
  "ALTER ROLE $DB_USER WITH PASSWORD '$NEWPASS';" > /dev/null
echo "mot de passe applique a PostgreSQL"


sed -e "s|^DB_HOST=.*|DB_HOST=cemantix_db|" \
    -e "s|^DB_PORT=.*|DB_PORT=5432|" \
    -e "s|^DB_NAME=.*|DB_NAME=$DB_NAME|" \
    -e "s|^DB_USER=.*|DB_USER=$DB_USER|" \
    -e "s|^DB_PASS=.*|DB_PASS=$NEWPASS|" \
    .env.example > .env
chmod 600 .env 2>/dev/null || true

# Controle : valeurs non vides, sans les afficher.
for v in DB_HOST DB_PORT DB_NAME DB_USER DB_PASS; do
  n=$(awk -F= -v k="$v" '$1==k{print length($2)}' .env)
  printf '  %-10s %s caracteres\n' "$v" "${n:-absent}"
done

# Le mot de passe doit aussi etre connu du service de base, sinon une recration
# future repartirait avec POSTGRES_PASSWORD vide.
echo "POSTGRES_PASSWORD=$NEWPASS" >> .env
echo ".env ecrit ($(wc -c < .env) octets)"

