# 🚀 Procédure de Déploiement en Production (VPS, Docker & Caddy)

Ce document récapitule la procédure opérationnelle pour déployer les évolutions d'interface, d'ergonomie et de sécurité sur le serveur VPS hébergeant **Cémantix Solver** avec **Docker Compose** et le reverse-proxy **Caddy**.

---

## 1. Contexte Architectural

En environnement de production :
- **Conteneurs Docker :**
  - `cemantix_web` (API REST / WebSocket Python)
  - `cemantix_worker` (Démon quotidien et résolveur 24/7)
  - `cemantix_db` (PostgreSQL / fallback SQLite)
  - `cemantix_nginx` (Serveur web interne écoutant sur le port hôte local `8090`)
- **Reverse-Proxy Frontal (VPS) :**
  - **Caddy** gère le certificat TLS Let's Encrypt automatique, la compression (gzip, zstd) et la terminaison HTTPS vers `localhost:8090`.

> [!IMPORTANT]
> **Pourquoi le rebuild Docker est obligatoire :**
> Le fichier `docker-compose.yml` monte en volume hôte `./volumes/web` (fichiers statiques) et `./cemantix_data` (bases et lexiques), mais **ne monte pas** le code Python `src/` (copié au moment du `COPY src/ ./src/` dans le `Dockerfile`).
> Toute modification du code Python (`src/services/seo_templates.py`, `src/services/seo_archives.py`, `src/services/layout_sync.py`, `src/api/server.py`) nécessite donc impérativement un `docker compose build` pour être prise en compte.

---

## 2. Procédure Pas-à-Pas sur le VPS

### Étape 1 — Récupérer le code à jour
Connectez-vous en SSH sur votre VPS et rendez-vous dans le répertoire du projet :
```bash
cd /opt/cemantix_solver  # Adaptez selon votre chemin réel
git fetch origin
git checkout feature/ui-ux-improvements  # ou 'main' après fusion
git pull
```

### Étape 2 — Reconstruire et relancer les conteneurs Docker
Lancez la compilation de l'image et recréez les conteneurs applicatifs sans interruption de la base de données :
```bash
# 1. Reconstruire l'image avec le nouveau code Python
docker compose build

# 2. Recréer et relancer les conteneurs web et worker
docker compose up -d --force-recreate cemantix_web cemantix_worker

# 3. Vérifier que tous les conteneurs sont 'Up' et sains
docker compose ps
```

Au démarrage du conteneur `cemantix_web`, le hook `ensure_seo_published()` s'exécute automatiquement, synchronise les gabarits d'en-tête et de navigation (`layout_sync.py`), et régénère les pages HTML SEO statiques.

---

## 3. Configuration du Reverse-Proxy Caddy

### Étape 3 — Corriger le `Caddyfile` sur l'hôte

L'erreur signalée par les navigateurs :
```text
Error with Permissions-Policy header: Unrecognized feature: 'interest-cohort'.
```
provient de la directive dépréciée Google FLoC (`interest-cohort=()`) qui doit être supprimée de la politique de sécurité.

Éditez le fichier de configuration de Caddy (généralement `/etc/caddy/Caddyfile` ou le fichier de conf de votre site) :
```bash
sudo nano /etc/caddy/Caddyfile
```

Vérifiez et adaptez le bloc de votre domaine comme suit :

```caddy
cemantix.cyril-randon.fr {
    # Redirection inverse vers le Nginx Docker interne
    reverse_proxy localhost:8090 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Compression moderne
    encode zstd gzip

    # En-têtes HTTP de sécurité
    header {
        # 1. Retrait strict de 'interest-cohort' (Permissions-Policy propre)
        Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        
        # 2. Transport sécurisé HSTS
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        
        # 3. Protection MIME & Framing
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

### Étape 4 — Valider et recharger Caddy
Vérifiez la syntaxe du fichier avant de recharger Caddy à chaud (sans coupure de trafic) :
```bash
# Valider la syntaxe
caddy validate --config /etc/caddy/Caddyfile

# Recharger à chaud
caddy reload --config /etc/caddy/Caddyfile

# Ou via systemd si Caddy tourne en service :
sudo systemctl reload caddy
```

---

## 4. Contrôles Post-Déploiement

Exécutez ces vérifications depuis votre terminal ou machine de test :

1. **Vérification des en-têtes HTTP de production :**
   ```bash
   curl -I https://cemantix.cyril-randon.fr/
   ```
   *Vérifier que `Permissions-Policy` ne contient plus `interest-cohort`.*

2. **Vérification de la page d'archive :**
   ```bash
   curl -sL https://cemantix.cyril-randon.fr/puzzles/ | grep -E "app-header|nav-tabs|app-footer"
   ```
   *Vérifier la présence de la navigation universelle et du footer canonique.*

3. **Console du navigateur (F12) :**
   - Aucune erreur rouge Permissions-Policy.
   - Les boutons de changement de thème sombre/clair fonctionnent instantanément et conservent l'état dans le `localStorage`.
   - La largeur est uniforme (1200px) entre le Dashboard et les Archives.
   - La barre de navigation des dates est placée sous la solution avec des boutons pills ergonomiques.

