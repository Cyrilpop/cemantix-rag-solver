# Environnement de test local — WSL Ubuntu-20.04 + nginx

> **Hors git** : ce répertoire est ignoré par `/.gitignore` (`/local/`).
> Il ne remplace **pas** la configuration de production (Caddy) : il la **miroite**
> pour pouvoir valider les correctifs du plan avant de les écrire dans le Caddyfile.

---

## 1. Accès

```
http://localhost:8090            # accueil + tableau de bord du mot du jour
http://localhost:8090/play/      # mode solo
http://localhost:8090/battle/    # duel contre l'IA
http://localhost:8090/multi/     # multijoueur 1v1
http://localhost:8090/api/health # API (via le même nginx que les pages)
```

Le relais de ports WSL2 → Windows est automatique : `localhost:8090` et
`127.0.0.1:8090` fonctionnent depuis le navigateur Windows. Le PAC d'entreprise
contient bien une exception `localhost` / `127.0.0.1` → `DIRECT`, le navigateur
ne passera donc pas par le proxy (contrairement à `curl` dans le WSL, voir §5).

---

## 2. Démarrer / arrêter

```bash
# depuis le WSL
cd /mnt/c/dev/cemantix-rag-solver

# préparation (idempotent) : .env, proxy du démon, réseau web-net, groupe docker
bash local/setup-wsl.sh

# démarrage complet (db + worker + web + nginx + relais d'egress)
docker compose -f docker-compose.yml -f local/docker-compose.test.yml up -d

# après une modification du Dockerfile uniquement :
# le builder BuildKit ne propagee pas le proxy du demon pour resoudre l'image de
# base -> passer par le builder classique en reseau hote.
docker pull python:3.12-slim
env DOCKER_BUILDKIT=0 docker build --network=host -t cemantix:latest .
docker compose -f docker-compose.yml -f local/docker-compose.test.yml up -d

# journalisation / arrêt
docker compose -f docker-compose.yml -f local/docker-compose.test.yml logs -f cemantix_web
docker compose -f docker-compose.yml -f local/docker-compose.test.yml down        # conserve les données
docker compose -f docker-compose.yml -f local/docker-compose.test.yml down -v     # reinitialise la BDD
```

## 3. Vérifier

```bash
bash local/smoke-test.sh                    # 29 contrôles (statuts, en-têtes, API, jeu)
bash local/smoke-test.sh http://localhost:8090
```

Résultat attendu sur l'état actuel du code : **28 PASS, 1 FAIL**.
Le FAIL est **volontaire** : il constate le point **SEC-05** du plan (la clé joueur
fait 7 caractères, `J1-` + 4 hex = 65 536 valeurs). Il passera quand SEC-05 sera corrigé.

## 4. Contenu du répertoire

| Fichier | Rôle |
|---|---|
| `setup-wsl.sh` | Lève les 4 blocages de l'hôte : `.env` absent, réseau `web-net` externe manquant, egress du démon Docker, utilisateur hors groupe `docker`. |
| `docker-compose.test.yml` | Empilement de test : ajoute nginx, déplace les données Postgres, neutralise le proxy au runtime, fournit le relais d'egress. |
| `nginx/cemantix.local.conf` | Sert `volumes/web`, proxifie `/api/`, applique les en-têtes de sécurité du plan (SEC-08) dont une CSP en **Report-Only**. |
| `smoke-test.sh` | Contrôles de bout en bout, réutilisables à chaque correctif. |

## 5. Pièges rencontrés et traités (à lire avant de toucher à cette config)

1. **Postgres refuse de vivre sur `/mnt/c`** — `initdb: could not change
   permissions ... Operation not permitted` : le montage Windows (drvfs/9p) ne
   gère pas les permissions POSIX. → données PG sur un volume nommé (`ext4`).
2. **Le proxy d'entreprise est obligatoire mais NTLM** — le proxy parent répond
   en 407 ; c'est `cntlm` local qui porte l'authentification, et il écoute sur
   **`127.0.0.1:3129`** (et non 3128/7566). Le démon Docker est configuré via un
   drop-in systemd créé par `setup-wsl.sh`.
3. **`~/.docker/config.json` injecte le proxy AUSSI au runtime**, pas seulement
   au build. Conséquences observées : l'API partait télécharger le modèle sur son
   propre loopback, et le `wget` du healthcheck nginx se connectait au proxy au
   lieu de nginx (conteneur « unhealthy » alors qu'il répondait très bien).
   → neutralisé par `HTTP_PROXY=` vide pour `web` et `nginx`.
4. **Un conteneur de build en bridge ne voit pas `127.0.0.1:3129`** (c'est son
   propre loopback) → build avec `--network=host`.
5. **`cap_drop: ALL` retire `CAP_CHOWN`** : nginx root n'arrive plus à créer ses
   répertoires temporaires. → image `nginx-unprivileged` (uid 101, port 8080)
   plutôt que de rendre 5 capabilities.
6. **Un `tmpfs` sur `/var/log/nginx` casse l'image** : il écrase les symlinks
   `access.log → /dev/stdout`, et le serveur doit alors créer de vrais fichiers en
   rootfs lecture seule. De même, un tmpfs monté sans options appartient à `root`
   et bloque un serveur en uid 101 → `:/var/cache/nginx:uid=101,gid=101,mode=1777`.
7. **`log_format` doit précéder son utilisation** dans la config nginx, sinon
   `unknown log format` au démarrage.
8. **`add_header` dans un `location` annule ceux hérités du `server`** : les
   en-têtes de sécurité disparaîtraient des pages. → `add_header` uniquement au
   niveau `server`, valeur `Cache-Control` calculée par `map`.
9. **`curl` du WSL passe par le proxy corporate** : il répond
   `403 Forbidden / Server: BigIP` au lieu d'atteindre nginx. Toujours utiliser
   `curl --noproxy '*'` (le `smoke-test.sh` le fait déjà).

## 6. Limites assumées

- Pas de TLS en local : `Strict-Transport-Security` est commenté dans la config
  (un HSTS sur `localhost` serait sans effet, et un certificat auto-signé
  ajouterait du bruit sans valeur de test).
- Les CSP sont en `Report-Only` : les pages utilisent encore des `style="…"` et
  `onclick="…"` inline (`game.js:195,209,553,582`, `battle.js:687`,
  `multi.js:938`). Les rapports arrivent dans
  `docker exec cemantix_nginx cat /tmp/csp.log`.
- Le worker télécharge et indexe ChromaDB **une seule fois** (~150 000 vecteurs,
  ~20 min sur ce poste) avant de résoudre le mot du jour. Le tableau de bord
  reste vide tant que `daily_puzzles` ne contient rien.
- `volumes/db/data` du dépôt n'est **pas** utilisé ici : pour éviter toute
  confusion, ne pas le committer (le `.gitignore` l'exclut déjà).
