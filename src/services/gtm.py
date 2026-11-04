"""
Cémantix Solver — Injection Google Tag Manager (gtm)
====================================================
Injecte le bloc de suivi Google Tag Manager dans le <head> de toutes les pages
HTML du site (les 5 vues statiques versionnées et les pages SEO générées :
archives ``/puzzles/``, hubs ``/mot-du-jour/`` et ``/methode/``), à l'exception
notable de la console d'exploitation ``/panier-9x/`` qui reste 100 % exempte de
trackers (page privée ``noindex, nofollow``).

Sécurité du secret (exigence « ne pas fuiter sur git ») :
    L'identifiant de conteneur vit **uniquement** dans la variable
    d'environnement ``GOOGLE_TAG_MANAGER_ID`` (fichier ``.env`` jamais versionné
    — voir ``.gitignore``). Ce qui est écrit sur le disque — fichiers statiques
    comme pages générées — n'est que le gabarit générique :

        <script async src="https://www.googletagmanager.com/gtm.js?id=GOOGLE_TAG_MANAGER_ID"></script>

    Le jeton ``GOOGLE_TAG_MANAGER_ID`` est substitué par l'ID réel **à la
    livraison HTTP**, jamais à la génération :

    * pages servies par le proxy Caddy (les vues et les archives statiques) :
      directive ``replace_response`` alimentée par ``{env.GOOGLE_TAG_MANAGER_ID}``
      (voir le Caddyfile documenté dans ``README.md``) ;
    * pages servies par l'API HTTP : ``resolve_gtm_for_delivery()`` appliqué sur
      la réponse.

    Aucun outil de build, aucun test et aucune exécution du démon n'écrit l'ID
    réel dans un fichier suivi par git ; ``tools/check_seo.py`` échoue la CI si
    un identifiant ``GTM-XXXXXXXX`` venait à apparaître sous ``volumes/web``.

Idempotence :
    ``inject_gtm_block()`` remplace tout bloc existant délimité par les
    commentaires ``GTM:START`` / ``GTM:END`` : relancer l'injection ne duplique
    jamais le script, quel que soit l'environnement d'exécution.
"""
import os
import re
from pathlib import Path
from typing import Dict, Optional

# RÉSOLUTION DU CHEMIN : gtm.py ne dépend que de la stdlib et calcule sa propre
# racine, sans importer src.config. Le package `src` tire numpy/chromadb/requests
# à l'import ; or ce module est aussi chargé par des outils de build et de CI
# (tools/build_css_bundles.py, tools/check_seo.py) qui tournent sur un poste nu,
# sans requirements.txt. BASE_DIR = <racine du dépôt> (gtm.py est à src/services/).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

WEB_ROOT = BASE_DIR / "volumes" / "web"

GTM_ENV_VAR = "GOOGLE_TAG_MANAGER_ID"
GTM_START = "<!-- GTM:START -->"
GTM_END = "<!-- GTM:END -->"

# Gabarit livré dans les fichiers (statiques comme générés) : strictement
# indépendant de l'environnement, donc identique quel que soit le poste — c'est
# ce qui rend les contrôles `--check` reproductibles et le diff git neutre.
GTM_PLACEHOLDER = "GOOGLE_TAG_MANAGER_ID"

# Gabarit générique (placeholder) inséré dans les fichiers HTML.
GTM_SNIPPET = f"""{GTM_START}
  <script async src="https://www.googletagmanager.com/gtm.js?id={GTM_PLACEHOLDER}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
  </script>
  {GTM_END}"""

# Pages HTML statiques versionnées (racine relative à volumes/web).
# La console /panier-9x/ est volontairement EXCLUE du suivi (page privée).
STATIC_PAGES = (
    "index.html",
    "play/index.html",
    "battle/index.html",
    "multi/index.html",
    "defi/index.html",
)

# Le gabarit s'insère juste avant </head> ; les pages générées par
# src/services/seo_templates.py (archives, index paginé, hubs mot-du-jour et
# méthode) héritent du même point d'ancrage.
_HEAD_CLOSE_RE = re.compile(r"[ \t]*</head>", re.IGNORECASE)

# Remplacement ciblé du placeholder par l'ID réel au rendu HTTP (server.py).
_GTM_URL_PLACEHOLDER_RE = re.compile(
    rf"(googletagmanager\.com/gtm\.js\?id=){re.escape(GTM_PLACEHOLDER)}"
)


def gtm_id_from_env() -> str:
    """Retourne l'identifiant GTM lu dans l'environnement, ou une chaîne vide."""
    return os.environ.get(GTM_ENV_VAR, "").strip()


def render_gtm_snippet(gtm_id: Optional[str] = None) -> str:
    """Gabarit GTM avec l'ID résolu, réservé à la livraison HTTP.

    Ne jamais utiliser pour écrire un fichier : l'ID réel ne doit jamais toucher
    le disque (voir le docstring du module). Retourne une chaîne vide si aucune
    variable d'environnement ne fournit d'ID — aucun script de suivi fantôme en
    développement ou en test.
    """
    gtm_id = gtm_id if gtm_id is not None else gtm_id_from_env()
    if not gtm_id:
        return ""
    return GTM_SNIPPET.replace(GTM_PLACEHOLDER, gtm_id)


def inject_gtm_block(html: str) -> str:
    """Insère (ou remplace) le bloc GTM placeholder générique avant ``</head>``.

    Idempotent : tout bloc existant délimité par GTM:START/GTM:END est
    d'abord retiré, puis le gabarit est réinséré avant ``</head>``. Lève
    ``ValueError`` si aucun ``</head>`` n'est trouvé (page mal formée).
    """
    # 1. Retirer un éventuel bloc existant (idempotence + migrations de format).
    existing_re = re.compile(
        rf"\s*{re.escape(GTM_START)}.*?{re.escape(GTM_END)}",
        re.DOTALL,
    )
    html = existing_re.sub("", html, count=1)

    # 2. Réinsérer le gabarit générique juste avant </head>.
    match = _HEAD_CLOSE_RE.search(html)
    if not match:
        raise ValueError("Point d'injection GTM introuvable : </head> absent")
    insert_at = match.start()
    indent = "  "
    return html[:insert_at] + indent + GTM_SNIPPET + "\n" + html[insert_at:]


def resolve_gtm_for_delivery(html: str, gtm_id: Optional[str] = None) -> str:
    """Substitue le placeholder par l'ID réel, pour la réponse HTTP uniquement.

    No-op si la page ne contient pas le gabarit ou si l'environnement ne
    fournit pas d'ID (le placeholder est alors servi tel quel, inoffensif).
    """
    if GTM_START not in html:
        return html
    gtm_id = gtm_id if gtm_id is not None else gtm_id_from_env()
    if not gtm_id:
        return html
    return _GTM_URL_PLACEHOLDER_RE.sub(rf"\g<1>{gtm_id}", html)


# Filet de sécurité livraison : si le jeton placeholder a été altéré dans le
# fichier servi (proxy, éditeur, corruption), le gabarit est régénéré proprement
# plutôt que livré avec un `id=` cassé. Aucun caractère du fichier ne peut ainsi
# s'échapper du bloc de script.
_GTM_URL_ANY_RE = re.compile(
    r"(https://www\.googletagmanager\.com/gtm\.js\?id=)[^\"'<>]*"
)


def harden_gtm_for_delivery(html: str, gtm_id: Optional[str] = None) -> str:
    """Garantit que l'attribut ``id=`` de l'URL GTM est soit le placeholder,
    soit l'ID environné — jamais une valeur corrompue ou vide."""
    if GTM_START not in html:
        return html
    gtm_id = gtm_id if gtm_id is not None else gtm_id_from_env()
    replacement = gtm_id if gtm_id else GTM_PLACEHOLDER
    return _GTM_URL_ANY_RE.sub(rf"\g<1>{replacement}", html)


def sync_static_pages(web_root: Optional[Path] = None) -> Dict[str, bool]:
    """Injecte le bloc GTM dans toutes les pages statiques versionnées."""
    root = web_root if web_root is not None else WEB_ROOT
    results: Dict[str, bool] = {}
    for rel_path in STATIC_PAGES:
        target = root / rel_path
        if not target.exists():
            results[rel_path] = False
            continue
        original = target.read_text(encoding="utf-8")
        updated = inject_gtm_block(original)
        if updated != original:
            target.write_text(updated, encoding="utf-8")
        results[rel_path] = True
    return results


__all__ = [
    "WEB_ROOT",
    "GTM_ENV_VAR",
    "GTM_START",
    "GTM_END",
    "GTM_PLACEHOLDER",
    "GTM_SNIPPET",
    "STATIC_PAGES",
    "gtm_id_from_env",
    "render_gtm_snippet",
    "inject_gtm_block",
    "resolve_gtm_for_delivery",
    "harden_gtm_for_delivery",
    "sync_static_pages",
]
