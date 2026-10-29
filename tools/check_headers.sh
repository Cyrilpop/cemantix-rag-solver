#!/usr/bin/env bash
# Contrôle des en-têtes HTTP de sécurité (SEC-08 / QUAL-07)
# Vérifie les 6 en-têtes recommandés : HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy

URL="${1:-http://localhost:8090/}"
echo "==> Verification des en-tetes sur $URL"

HEADERS=$(curl -sI "$URL")

check_header() {
    local name="$1"
    if echo "$HEADERS" | grep -iq "^$name:"; then
        echo "  [OK] $name present"
    else
        echo "  [FAIL] $name absent"
        return 1
    fi
}

FAILURES=0
check_header "Content-Security-Policy" || ((FAILURES++))
check_header "X-Frame-Options" || ((FAILURES++))
check_header "X-Content-Type-Options" || ((FAILURES++))
check_header "Referrer-Policy" || ((FAILURES++))
check_header "Permissions-Policy" || ((FAILURES++))

if [ $FAILURES -eq 0 ]; then
    echo "==> Tous les en-tetes obligatoires sont conformes."
    exit 0
else
    echo "==> $FAILURES en-tete(s) manquant(s)."
    exit 1
fi
