# 📊 Avancement — Livraison des ressources de découverte aux agents IA

> **Évolution :** [2026-11 · Découvrabilité agents IA](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Branche :** `fix/livraison-ressources-agents-ia` (base `main` @ `2d271aa`)
> **Dernière mise à jour :** 09/11/2026

---

## 0. Règles de tenue

1. Une ligne = un finding du plan (`SEO-22` à `SEO-25`), ID jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte** ; un
   commit ou son message ne vaut pas preuve.
3. Statuts : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut est journalisé au §3 avec sa preuve mesurée.

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **4** | 2 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **4** | **2** |

Répartition par criticité : 🔴 `SEO-22` (robots.txt bloquait la lecture des manifestes) et
`SEO-23` (soft 404 et types MIME non contractuels) · 🟠 `SEO-24` (gardes CI) · 🟡 `SEO-25`
(déclaration des hubs dans les deux documents d'agents restants).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **SEO-22** | 🔴 | `volumes/web/robots.txt` : laisser les robots lire les manifestes | `✅ Fait` | `Disallow: /.well-known/` supprimé, quatre `Allow` explicites (`/.well-known/`, `/llms.txt`, `/llms.md`, `/agent-skills.md`) avec le motif en commentaire ; les cinq blocages utiles restent. `py tools/check_seo.py` → « Decouvrabilite agents : robots.txt ne bloque aucune ressource » |
| **SEO-23** | 🔴 | Référence Caddy du `README.md` et miroir nginx local : type MIME contractuel et vrai 404 | `✅ Fait` | Trois blocs `handle @agents_json`, `@agents_txt`, `@agents_md` déclarés avant le `handle` général (`application/json`, `text/plain`, `text/markdown`, tous en `charset=utf-8`) ; `try_files {path} {path}/index.html {path}/ =404` remplace le repli `/index.html` ; miroir nginx aligné (`location = /llms.txt`, `default_type application/json` et `text/markdown` sur `^/\.well-known/[a-z-]+\.json$`). Équilibre des accolades vérifié sur les deux fichiers (mêmes écarts qu'avant l'édition, dus aux jetons `{{ env … }}`) |
| **SEO-24** | 🟠 | `tools/check_seo.py`, `tests/test_agent_delivery.py`, `local/smoke-test.sh` | `✅ Fait` | Nouveau contrôle `check_decouvrabilite_agents()` (robots + URLs annoncées, avec `URLS_GENREES` pour les pages produites au démarrage) branché dans `main()` ; **10 tests verts** dans `tests/test_agent_delivery.py`, dont le test de non-régression qui réinjecte `Disallow: /.well-known/` ; smoke test local : section 1b sur les six types MIME, le premier caractère de `llms.txt` et du catalogue, l'absence du `Disallow`, et correction de l'attente erronée `/ai-catalog.json:200` → `404` |
| **SEO-25** | 🟡 | `llms.md` et `agent-skills.md` déclarent enfin les deux hubs | `✅ Fait` | `llms.md` : deux entrées de navigation (`/mot-du-jour/`, `/methode/`) ; `agent-skills.md` : « Compétence 4 — Mot du jour et lecture des indices » (source à citer, conduite anti-spoiler, renvoi méthode). `test_les_hubs_sont_declares_partout` passe sur les trois documents ; le nouveau contrôle de liens valide les deux URLs ajoutées |
---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 09/11/2026 | — | Cadrage à partir des deux erreurs d'audit remontées sur `cemantix.cyril-randon.fr`. Constat décisif : les fichiers du dépôt sont conformes (`llms.txt` porte son H1 et vingt liens, le catalogue ARD est un JSON valide), donc l'audit lit une **réponse**, pas un fichier. Le `Unexpected token '<', "<!DOCTYPE "` du catalogue ARD nomme la réponse : la page d'accueil. |
| 09/11/2026 | SEO-22 | `robots.txt` tenait `/.well-known/` en `Disallow` depuis l'évolution Sécurité-SEO : le catalogue, `ard.json` et la carte d'agent étaient interdits de lecture aux robots conformes. Rétabli, avec les quatre `Allow` et le motif écrit dans le fichier. |
| 09/11/2026 | SEO-23 | Le miroir nginx local documentait déjà le soft 404 comme un défaut et appliquait `=404` ; la référence Caddy, elle, livrait `/index.html` à chaque URL inconnue. Les deux configurations sont réalignées, et le type MIME des six ressources devient contractuel des deux côtés. |
| 09/11/2026 | SEO-24 | **Régression attrapée par le propre contrôle de l'évolution** : en déclarant `/mot-du-jour/` et `/methode/` dans `agent-skills.md`, le nouveau garde-fou a signalé deux « liens morts » — le motif d'URL capturait le backtick fermant du code en ligne. Classe de délimiteurs étendue (backtick, virgule), contrôle vert. |
| 09/11/2026 | SEO-22 → SEO-25 | Recette : `py tools/check_seo.py` vert (5 pages, 2 gabarits générés, audit agentique, découvrabilité, anti-fuite GTM) ; `py -m unittest discover -s tests -p "test_agent_delivery.py"` → **10 tests verts** ; `py local/run_seo_tests.py` → **58 tests verts sur 4 modules** (`test_seo_archives`, `test_seo_hubs`, `test_docs_agent`, `test_agent_delivery`). |
| 09/11/2026 | SEO-24 | **Harnais local réparé au passage** : `local/run_seo_tests.py` ne tournait plus depuis le découpage de la chaîne SEO (jalon M4) — son paquet `src.services` factice ne déclarait que `seo.py`, qui ré-exporte désormais depuis neuf modules frères, et échouait sur « No module named 'src.services.seo_templates' ». Les modules sont maintenant enregistrés dans l'ordre des dépendances (`gtm`, `layout_sync`, puis les sept modules SEO), ce qui rend la recette ci-dessus exécutable sur un poste sans `numpy` ni `requests`. |

---

## 4. Environnement de vérification, limites et prochaines actions

- Vérifications exécutées sous **Python 3.14** avec la seule bibliothèque standard : la chaîne
  SEO et les nouveaux contrôles n'importent aucune dépendance lourde. Le poste de développement
  n'ayant pas `numpy` / `requests` / `chromadb`, `py local/run_seo_tests.py` tient lieu de suite
  SEO locale — **réparé au passage**, il ne chargeait plus `src.services.seo` depuis le découpage
  de la chaîne au jalon M4. La suite complète (moteur, API, base) reste couverte par le job
  `tests` de la CI.
- **Limite assumée :** l'audit remonté vise la production, et le `Caddyfile` réel n'est pas
  versionné (`.gitignore`). Ce dépôt corrige sa **référence** (`README.md`) et son miroir de
  test (`local/nginx`) ; la recette §5 du plan reste à exécuter sur le serveur, `curl -sI` à
  l'appui, pour que les deux erreurs disparaissent du rapport d'audit.
- Prochaines actions :
  1. appliquer le `Caddyfile` et `caddy reload` sur le serveur, puis rejouer l'audit ;
  2. si l'audit persiste malgré des `curl -sI` conformes, vérifier qu'un proxy tiers (WAF,
     mode challenge) ne répond pas à la place de Caddy aux requêtes d'audit ;
  3. envisager une entrée `mot-du-jour` dans `agent-card.json` (compétence déjà décrite dans
     `agent-skills.md` depuis `SEO-25`) si l'audit redemande une compétence dédiée.

