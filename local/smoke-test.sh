#!/usr/bin/env bash
# =============================================================================
# Cémantix Solver — Smoke test de la stack locale (hors git)
# -----------------------------------------------------------------------------
# Usage :  bash /mnt/c/dev/cemantix-rag-solver/local/smoke-test.sh [base_url]
# Défaut : http://localhost:8090
#
# IMPORTANT : le WSL expose http_proxy/https_proxy (proxy d'entreprise). Sans
# --noproxy, curl envoie « localhost » au proxy corporate, qui répond
#   403 Forbidden / Server: BigIP
# Ce n'est PAS nginx. Toutes les requêtes du script court-circuitent donc le proxy.
# =============================================================================
set -uo pipefail

BASE="${1:-http://localhost:8090}"
curl_nx() { curl -s --noproxy "*" "$@"; }
PASS=0
FAIL=0

check() {   # check "libellé" "attendu" "obtenu"
    if [ "$2" = "$3" ]; then
        printf '  \033[32mPASS\033[0m  %-46s %s\n' "$1" "$3"
        PASS=$((PASS + 1))
    else
        printf '  \033[31mFAIL\033[0m  %-46s attendu=%s obtenu=%s\n' "$1" "$2" "$3"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 1. Statuts HTTP (nginx -> fichiers statiques) ==="
for pair in "/:200" "/play/:200" "/battle/:200" "/multi/:200" \
            "/robots.txt:200" "/sitemap.xml:200" "/llms.txt:200" \
            "/ai-catalog.json:200" "/.well-known/ai-catalog.json:200" \
            "/css/variables.css:200" "/js/app.js:200" \
            "/nexiste-pas:404" "/api/sans-objet:404"; do
    url="${pair%:*}"; want="${pair##*:}"
    code=$(curl_nx -o /dev/null -w '%{http_code}' "$BASE$url")
    check "GET $url" "$want" "$code"
done

echo "=== 2. En-têtes de sécurité (plan SEC-08) ==="
H=$(curl_nx -D - -o /dev/null "$BASE/")
for h in "X-Content-Type-Options: nosniff" \
         "X-Frame-Options: SAMEORIGIN" \
         "Referrer-Policy: strict-origin-when-cross-origin" \
         "Permissions-Policy:" \
         "Content-Security-Policy-Report-Only:" \
         "Cache-Control: no-cache, must-revalidate"; do
    if printf '%s' "$H" | grep -qi "^$h"; then check "present: $h" "oui" "oui"
    else check "present: $h" "oui" "non"; fi
done

echo "=== 3. X-Robots-Tag : API only (plan SEO-04) ==="
API_H=$(curl_nx -D - -o /dev/null "$BASE/api/health")
printf '%s' "$API_H" | grep -qi "^X-Robots-Tag: noindex" && r=oui || r=non
check "X-Robots-Tag sur /api/health" "oui" "$r"
printf '%s' "$H" | grep -qi "^X-Robots-Tag:" && r=oui || r=non
check "X-Robots-Tag absent des pages" "non" "$r"

echo "=== 4. API de santé ==="
HEALTH=$(curl_nx "$BASE/api/health")
printf '%s' "$HEALTH" | grep -q '"status": *"ok"' && r=ok || r="$HEALTH"
check "GET /api/health" "ok" "$r"

echo "=== 5. Anti-spoiler : le mot du jour ne doit PAS fuiter (plan SEC-03) ==="
DAILY=$(curl_nx "$BASE/api/daily")
if printf '%s' "$DAILY" | grep -q '"current": *null'; then
    check "/api/daily sans historique" "null" "null"
else
    WORD=$(printf '%s' "$DAILY" | python3 -c 'import json,sys
d=json.load(sys.stdin)
print(d.get("current",{}).get("word") if d.get("current") else "null")' 2>/dev/null)
    check "/api/daily masque le mot" "None" "$WORD"
fi
REVEAL=$(curl_nx "$BASE/api/daily?reveal=true")
WORD2=$(printf '%s' "$REVEAL" | python3 -c 'import json,sys
d=json.load(sys.stdin)
w = d.get("current",{}).get("word") if d.get("current") else None
print("AUCUN_MOT" if not w else w)' 2>/dev/null)
check "?reveal=true ne doit rien reveler" "AUCUN_MOT" "$WORD2"

echo "=== 6. Parcours de jeu reel (solo) ==="
NEW=$(curl_nx -X POST -H 'Content-Type: application/json' -d '{"mode":"unlimited","difficulty":"facile"}' "$BASE/api/game/new")
GID=$(printf '%s' "$NEW" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("game_id",""))' 2>/dev/null)
[ -n "$GID" ] && check "POST /api/game/new -> game_id" "oui" "oui" || check "POST /api/game/new -> game_id" "oui" "non"
SECRET=$(printf '%s' "$NEW" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("secret"))' 2>/dev/null)
check "le secret n'est pas renvoye en debut de partie" "None" "$SECRET"
if [ -n "$GID" ]; then
    GUESS=$(curl_nx -X POST -H 'Content-Type: application/json' -d "{\"game_id\":\"$GID\",\"word\":\"maison\"}" "$BASE/api/game/guess")
    printf '%s' "$GUESS" | grep -q '"score"' && r=ok || r="$(printf '%s' "$GUESS" | head -c 60)"
    check "POST /api/game/guess renvoie un score" "ok" "$r"
fi

echo "=== 7. Multijoueur : creation de salon ==="
ROOM=$(curl_nx -X POST -H 'Content-Type: application/json' -d '{"mode":"same_word","difficulty":"moyen","player_name":"Test WSL"}' "$BASE/api/multi/create")
RID=$(printf '%s' "$ROOM" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("room_id",""))' 2>/dev/null)
if printf '%s' "$RID" | grep -qE '^DUEL-[0-9A-F]{4,8}$'; then
    check "POST /api/multi/create -> room_id" "ok" "ok"
    # Vérification du point SEC-05 du plan : la clé joueur ne fait que 4 hex,
    # donc 65 536 valeurs -> le test échoue volontairement tant que SEC-05 n'est
    # pas corrigé (la longueur attendue sera alors bien plus grande).
    KEY=$(printf '%s' "$ROOM" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("player_key",""))' 2>/dev/null)
    KEYLEN=${#KEY}
    if [ "$KEYLEN" -ge 20 ]; then
        check "longueur de cle joueur (SEC-05)" ">=20" "$KEYLEN"
    else
        check "longueur de cle joueur (SEC-05)" ">=20" "$KEYLEN (dettable)"
    fi
else
    check "POST /api/multi/create -> room_id" "DUEL-<hex>" "$RID"
fi

echo
echo "================================================================"
printf '  \033[32mPASS %s\033[0m   \033[31mFAIL %s\033[0m      (%s)\n' "$PASS" "$FAIL" "$BASE"
echo "================================================================"
[ "$FAIL" -eq 0 ]
