# M3 — Sécurisation & Frontières de Confiance Réseau (Security Hardening & Trust Boundaries)

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Date :** 31 octobre 2026  
**Branche :** `feature/audit-hey-you`  
**Statut :** Complété — 231 tests passants (0 échec, 0 régression, 19 nouveaux tests de sécurité)  

---

## 1. Résumé Exécutif

Le jalon **M3** a audité et remédié aux risques de sécurité confirmés touchant :
1. **L'usurpation d'identité et de quota client** via l'acceptation inconditionnelle de l'en-tête `X-Forwarded-For`.
2. **L'exposition totale de l'hôte** via le montage de `/var/run/docker.sock` dans le conteneur web.
3. **Le manque de limitation de débit** sur les routes d'administration GET et la faille de révocation des jetons.

Les modifications ont été opérées dans le respect le plus strict des invariants opérationnels :
- **Zéro régression fonctionnelle** : le solveur, le gameplay, les défis au bot, l'API publique, le repli SQLite et le balisage SEO sont intacts.
- **Fail-closed strict** : aucun proxy n'est de confiance par défaut sans déclaration explicite dans `TRUSTED_PROXIES`.
- **Zéro dépendance nouvelle** : utilisation exclusive de la bibliothèque standard Python (`ipaddress`, `os`, `hmac`).
- **Sanctuarisation par les tests** : adjonction de [`tests/test_security_hardening.py`](../../tests/test_security_hardening.py) portant la suite globale de **212 à 231 tests unitaires déterministes** (100 % passants en ~8,8 s sous conteneur Docker Python 3.12).

---

## 2. Phase 1 — Analyse des Vulnérabilités & Classification des Risques

| Réf. | Vulnérabilité / Composant | Fichiers Affectés | Classification | Impact & Exploitabilité |
|---|---|---|---|---|
| **SEC-M3-01** | Confiance inconditionnelle dans `X-Forwarded-For` | [`src/api/server.py`](../../src/api/server.py) | **CONFIRMÉ** | **Critique / Élevé** — N'importe quel client direct pouvait injecter `X-Forwarded-For: <ip>` pour contourner le rate limiting (`_limiter`), contourner le quota de défis au bot (`10/h`), brute-forcer `/auth` sans blocage, ou usurper une adresse IP présente dans `whitelisted_ips`. |
| **SEC-M3-02** | Dépilage de gauche à droite sur les chaînes de relais | [`src/api/server.py`](../../src/api/server.py) | **CONFIRMÉ** | **Moyen / Élevé** — `forwarded.split(',')[0]` sélectionnait l'entrée la plus à gauche (contrôlée par le client) plutôt que l'adresse ajoutée par le reverse-proxy amont lors de la concaténation. |
| **SEC-M3-03** | Montage de `/var/run/docker.sock` dans `cemantix_web` | [`docker-compose.yml`](../../docker-compose.yml) | **CONFIRMÉ** | **Critique (Évasion d'hôte)** — Le flag `:ro` n'offre aucune restriction sur les flux HTTP bidirectionnels du socket Unix. Tout attaquant obtenant une exécution de code dans le conteneur web disposait des droits root sur l'hôte via l'API Docker daemon. |
| **SEC-M3-04** | Absence de limitation de débit sur les GET d'administration | [`src/api/server.py`](../../src/api/server.py), [`src/api/routes/admin.py`](../../src/api/routes/admin.py) | **CONFIRMÉ** | **Faible / Moyen** — `is_admin_path` court-circuitait le rate limiter public, exposant les routes de stats/logs à des dénis de service non authentifiés. |
| **SEC-M3-05** | Jeton accepté sans `ADMIN_PASSWORD` dans `_check_token` | [`src/api/routes/admin.py`](../../src/api/routes/admin.py) | **CONDITIONNEL** | **Faible (Défense en profondeur)** — Bien que `authorize()` vérifiait `_admin_password()`, un appel direct à `_check_token` validait la signature basée sur le secret statique `"cemantix-admin|"`. |
| **SEC-M3-06** | Single-hop versus multi-hop en configuration Caddy/Nginx | [`local/nginx/cemantix.local.conf`](../../local/nginx/cemantix.local.conf) | **CONDITIONNEL** | **Faible** — Nginx écrasait `$remote_addr`, mais un déploiement avec Caddy ou Cloudflare concatène les en-têtes sans assainissement amont. |

---

## 3. Phase 2 — Gestion Sécurisée des Adresses IP (`src/api/proxy.py`)

### 3.1 Conception & Architecture Fail-Closed
Un module dédié léger et zéro-dépendance a été créé : [`src/api/proxy.py`](../../src/api/proxy.py).

```
                      ┌──────────────────────────────────────────┐
                      │    Requête TCP entrante (peer_ip)        │
                      └─────────────────────┬────────────────────┘
                                            │
                             peer_ip in TRUSTED_PROXIES ?
                                   /                 \
                             [NON]                     [OUI]
                                 /                         \
                ┌─────────────────────────┐     ┌────────────────────────────┐
                │ Rejeter X-Forwarded-For │     │ Parser X-Forwarded-For     │
                │ Retourner peer_ip       │     │ de droite à gauche         │
                └─────────────────────────┘     └──────────────┬─────────────┘
                                                               │
                                               Premier IP NOT in TRUSTED_PROXIES
                                                               │
                                                ┌──────────────▼─────────────┐
                                                │ Retourner Client IP réel   │
                                                └────────────────────────────┘
```

### 3.2 Règles Opérationnelles Implémentées
1. **Défaut strict sans confiance :** Si `TRUSTED_PROXIES` est vide (par défaut), l'en-tête `X-Forwarded-For` est ignoré et le pair TCP physique (`self.client_address[0]`) est utilisé.
2. **Support IPv4, IPv6 et CIDR :** Déclaration flexible de proxys sous forme d'adresses uniques (`172.18.0.2`, `::1`) ou de sous-réseaux (`172.16.0.0/12`, `2001:db8::/32`).
3. **Parcours inversé (Right-to-Left Traversal) :** Dépilement sécurisé depuis le saut le plus proche du serveur vers l'origine. L'attaquant amont ne peut plus injecter de fausses adresses.
4. **Rejet fail-closed des malformations :** Si un segment de la chaîne contient une chaîne invalide (`<script>`, injection HTTP), le système replie immédiatement sur le pair TCP direct sans lever d'exception.
5. **Anonymisation RGPD (/24 IPv4, /48 IPv6) :** Standardisation propre via `ipaddress`.

---

## 4. Phase 3 — Élimination du Montage du Socket Docker

### 4.1 Audit de Consommation
L'analyse du code source a établi que le socket Docker n'était utilisé **que dans deux fonctions** de [`src/api/routes/admin.py`](../../src/api/routes/admin.py) :
- `container_logs(container, tail)` : lecture ponctuelle des logs stdout/stderr du worker et du web.
- `container_log_stream(container, emit)` : streaming temps-réel via SSE.

En parallèle, la console admin intègre nativement la source `source=app` qui puise directement dans le tampon en mémoire vive (`src.config._MEMORY_HANDLER`).

### 4.2 Risque Réel du Montage `:ro`
Le montage `/var/run/docker.sock:/var/run/docker.sock:ro` était **illusoire en termes de sécurité** :
- Le drapeau Linux `:ro` ne s'applique qu'aux métadonnées du nœud de système de fichiers (empêchant `unlink` ou `chmod`).
- La communication sur un socket de domaine UNIX connecté (`AF_UNIX`) est un canal HTTP en duplex intégral (`read` + `write`).
- L'appartenance de l'utilisateur au groupe `${DOCKER_GID:-120}` lui accordait les droits d'écriture sur le flux, permettant de lancer des conteneurs privilégiés montant le disque hôte (`POST /containers/create`).

### 4.3 Neutralisation dans `docker-compose.yml`
1. Suppression de la ligne `- /var/run/docker.sock:/var/run/docker.sock:ro` dans le service `cemantix_web`.
2. Suppression de la directive `group_add: ["${DOCKER_GID:-120}"]`.
3. Adaptation défensive de `container_logs` et `container_log_stream` dans [`src/api/routes/admin.py`](../../src/api/routes/admin.py) : détection de l'absence du socket et retour d'un message informatif clair orientant vers `docker compose logs` sur l'hôte.

---

## 5. Phase 4 — Durcissement des Points d'Administration

1. **Protection Brute-Force Étanchée :**
   Avec le filtrage de `X-Forwarded-For`, un attaquant ne peut plus faire tourner d'adresses IP pour contourner `_login_limiter` sur `POST /auth`. Après 6 tentatives infructueuses, le blocage temporaire (429) s'applique sans échappatoire.
2. **Limitation de Débit sur les GET d'Administration :**
   `handle_admin_get` applique désormais `_api_limiter.allow(client_ip)`. Tout balayage ou déni de service non authentifié sur `/stats`, `/logs`, `/whoami` est freiné.
3. **Invalidation Immédiate des Jetons :**
   `_check_token` refuse immédiatement tout jeton si `ADMIN_PASSWORD` est vide (`if not token or not _admin_password(): return False`), empêchant toute signature résiduelle.
4. **Traçabilité des Refus :**
   La tentative de connexion échouée journalise explicitement l'adresse IP cliente réelle (`WARNING 🛡️  [ADMIN] Tentative d'authentification refusée (IP: <client_ip>)`).

---

## 6. Phase 5 — Validation & Harnais de Non-Régression

### 6.1 Nouveaux Tests de Sécurité (`tests/test_security_hardening.py`)
19 tests automatisés ont été ajoutés, répartis en 4 classes :
- **`TestTrustedClientIP`** : validation des adresses IPv4/IPv6, rejet des malformations, comportement fail-closed sans configuration, résolution simple et multi-sauts, résistance aux en-têtes forgés, anonymisation RGPD.
- **`TestRateLimitBypassMitigation`** : échec prouvé des tentatives de contournement du rate limiter global par rotation de `X-Forwarded-For`, échec du contournement de quota défi-bot, refus d'usurpation d'une IP blanche.
- **`TestDockerSocketIsolation`** : vérification structurelle de `docker-compose.yml` (absence de socket et de GID dans `cemantix_web`), repli informatif de `container_logs` et `container_log_stream`.
- **`TestAdminSecurityHardening`** : révocation immédiate si mot de passe vide, protection anti brute-force sur `/auth` liée à l'IP réelle, application du rate-limiter sur les GET d'administration.

### 6.2 Résultats de Validation
```
Suite de tests unitaires (tests/) : Ran 231 tests in 8.875s (100% OK)
Vérification documentaire (tools/check_docs.py) : OK (0 lien cassé, tables et compteurs conformes)
Vérification SEO (tools/check_seo.py) : OK (5 pages principales + hubs + manifestes ARD)
Bundles CSS (tools/build_css_bundles.py --check) : OK (dist et inline synchronisés)
```

---

## 7. Configuration de Déploiement & Plan de Retour-Arrière (Rollback)

### 7.1 Configuration en Production
Dans le fichier `.env` sur le serveur de production :
```bash
# Déclarer l'IP ou le sous-réseau du reverse-proxy (ex. Caddy sur réseau Docker ou boucle locale)
TRUSTED_PROXIES=127.0.0.1,::1,172.16.0.0/12
```

### 7.2 Configuration Reverse Proxy (Caddy / Nginx)
- **Caddyfile** : la directive `reverse_proxy` transmet nativement `X-Forwarded-For: <client_ip>`. Avec `TRUSTED_PROXIES` configuré avec le sous-réseau Docker de Caddy, l'adresse du visiteur réel est immédiatement reconnue.
- **Nginx** : `proxy_set_header X-Forwarded-For $remote_addr;` fonctionne sans modification.

### 7.3 Procédure de Rollback
Si un environnement d'exploitation requiert impérativement le retour de la consultation brute des conteneurs via Docker :
1. Dans `docker-compose.yml`, réintroduire sous `cemantix_web` :
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock:ro
   group_add:
     - "${DOCKER_GID:-120}"
   ```
2. Si `TRUSTED_PROXIES` doit être neutralisé temporairement, laisser la variable vide dans `.env` : l'application fonctionne alors en mode pair TCP direct sans interruption.

---

## 8. Risques Résiduels & Périmètre Non Couvert

1. **Logs multi-conteneurs dans l'interface admin :**
   Sans le socket Docker monté, les boutons `source=worker` et `source=web` affichent un message explicatif invitant l'administrateur à consulter `docker compose logs` sur la machine hôte. La source `source=app` (en mémoire vive) reste accessible en temps-réel.
2. **Absence de TLS applicatif interne :**
   Le conteneur `cemantix_web` écoute en HTTP clair sur le port 8000 sur le réseau Docker interne. La terminaison TLS reste à la charge exclusive du reverse proxy Caddy/Nginx externe (ce qui est l'architecture standard du projet).

---

## 9. Recommandation pour M4

La sécurité du périmètre réseau et des frontières de confiance étant désormais sanctuarisée, l'application est prête pour le prochain jalon d'architecture :
👉 **M4 — Modularisation du God Module SEO ([`src/services/seo.py`](../../src/services/seo.py) — 1 692 lignes)**, en isolant les générateurs de templates d'archives, le constructeur de sitemap XML et les manifestes ARD agentiques.
