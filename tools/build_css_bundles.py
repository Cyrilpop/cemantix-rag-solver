"""Générateur de feuilles de style par page, sans dépendance de build.

    python tools/build_css_bundles.py            # (re)génère css/dist/*.css
    python tools/build_css_bundles.py --check    # échoue si les bundles sont périmés

Pourquoi ce script existe
------------------------
Chaque page ne charge déjà que les feuilles dont elle a besoin : il n'y a pas de CSS
mort téléchargé. Le gain visé est donc le **nombre de requêtes** (5 à 6 par page → 1),
pas le poids. Le bénéfice est réel mais borné : en HTTP/2 les requêtes sont
multiplexées, et Caddy applique déjà `no-cache, must-revalidate` avec ETag.

Pourquoi des bundles séparés et non un seul fichier global
---------------------------------------------------------
Un fichier unique ferait télécharger à /play/ le CSS de /battle/ et de /multi/, soit
une régression de ~30 %. On régénère donc un bundle par page, à partir des mêmes
fichiers sources que les `<link>` actuels.

Contraintes vérifiées par le script
-----------------------------------
- `css/variables.css` doit rester un fichier à part : `src/services/seo.py` le lit
  pour injecter les tokens dans les pages d'archives. Le bundle le *copie*, il ne le
  remplace pas.
- Les feuilles ne contiennent aucun `url(...)` : la concaténation ne casse donc
  aucune référence relative. Le script le vérifie et refuse de continuer sinon.
"""
import argparse
import hashlib
import io
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "volumes" / "web"
CSS_DIR = WEB_DIR / "css"
DIST_DIR = CSS_DIR / "dist"

# Composition de chaque bundle dist/, dans l'ordre de cascade des pages.
BUNDLES = {
    "dashboard": ["variables.css", "base.css", "layout.css", "dashboard.css", "modal.css"],
    "play": ["variables.css", "base.css", "layout.css", "game.css", "modal.css"],
    "battle": ["variables.css", "base.css", "layout.css", "game.css", "modal.css", "battle.css"],
    "multi": ["variables.css", "base.css", "layout.css", "game.css", "modal.css", "multi.css"],
    "modal": ["modal.css"],
    "puzzle": ["puzzle.css"],
}

# Pages HTML dont le CSS critique (hors modales cachées) est injecté en <style> dans
# <head> afin d'éliminer toute requête CSS bloquante pour le FCP/LCP mobile, tandis
# que modal.css est différé via media="print" + activation JS conforme CSP.
CRITICAL_PAGES = {
    "dashboard": (
        WEB_DIR / "index.html",
        "",
        ["variables.css", "base.css", "layout.css", "dashboard.css"],
    ),
    "play": (
        WEB_DIR / "play" / "index.html",
        "../",
        ["variables.css", "base.css", "layout.css", "game.css"],
    ),
    "battle": (
        WEB_DIR / "battle" / "index.html",
        "../",
        ["variables.css", "base.css", "layout.css", "game.css", "battle.css"],
    ),
    "multi": (
        WEB_DIR / "multi" / "index.html",
        "../",
        ["variables.css", "base.css", "layout.css", "game.css", "multi.css"],
    ),
    "defi": (
        WEB_DIR / "defi" / "index.html",
        "../",
        ["variables.css", "base.css", "layout.css", "game.css"],
    ),
}

URL_RE = re.compile(r"url\(\s*['\"]?(?!data:)", re.I)


def strip_comments(css: str) -> str:
    """Retire les commentaires et normalise les espaces, sans toucher au sélecteurs.

    Suppression volontairement prudente : on ne réécrit pas les valeurs, on se limite
    aux blancs redondants, pour qu'un bundle reste lisible en cas de debug en prod.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"[ \t]*\n[ \t]*", "\n", css)
    css = re.sub(r"\n{2,}", "\n", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    css = css.replace("}", "}\n")
    return css.strip()


def check_sources() -> list[str]:
    """Signale les sources problématiques (introuvables ou contenant une URL relative)."""
    problems = []
    for name in sorted({f for files in BUNDLES.values() for f in files}):
        path = CSS_DIR / name
        if not path.exists():
            problems.append(f"{name} introuvable")
            continue
        if URL_RE.search(path.read_text(encoding="utf-8")):
            problems.append(
                f"{name} contient une url() : la concaténation casserait les "
                f"chemins relatifs si le bundle changeait de répertoire"
            )
    return problems


def build(bundle_name: str, sources: list[str]) -> tuple[str, bytes]:
    parts = []
    for name in sources:
        css = (CSS_DIR / name).read_text(encoding="utf-8")
        parts.append(f"/* {name} */\n{strip_comments(css)}")
    header = (
        f"/* Bundle {bundle_name} — généré par tools/build_css_bundles.py. "
        f"Ne pas éditer : modifier css/*.css puis relancer le script. */\n"
    )
    return header, ("\n".join(parts) + "\n").encode("utf-8")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:12]


def build_inline_block(bundle_name: str, prefix: str, sources: list[str]) -> str:
    """Construit le bloc <style id="critical-css"> + chargement différé de modal.css."""
    compact = "".join(
        strip_comments((CSS_DIR / name).read_text(encoding="utf-8")).replace("\n", "")
        for name in sources
    )
    if "</style" in compact.lower():
        raise ValueError(f"Séquence </style interdite détectée dans le bundle {bundle_name}")
    modal_href = f"{prefix}css/dist/modal.css"
    return (
        f'<style id="critical-css" data-bundle="{bundle_name}">{compact}</style>\n'
        f'  <link rel="stylesheet" href="{modal_href}" media="print" data-deferred-css>\n'
        f'  <noscript><link rel="stylesheet" href="{modal_href}"></noscript>'
    )


def inject_critical_into_html(html: str, bundle_name: str, prefix: str, new_block: str) -> str:
    """Remplace l'ancien <link> bloquant ou le bloc <style id="critical-css"> existant."""
    existing_re = re.compile(
        r'<style id="critical-css"[^>]*>.*?</style>\s*'
        r'<link rel="stylesheet" href="[^"]*modal\.css" media="print" data-deferred-css>\s*'
        r'<noscript><link rel="stylesheet" href="[^"]*modal\.css"></noscript>',
        flags=re.S,
    )
    if existing_re.search(html):
        return existing_re.sub(lambda _m: new_block, html, count=1)

    legacy_re = re.compile(
        rf'<link\s+rel="stylesheet"\s+href="{re.escape(prefix)}css/dist/{re.escape(bundle_name)}\.css"\s*/?>'
    )
    if legacy_re.search(html):
        return legacy_re.sub(lambda _m: new_block, html, count=1)

    raise RuntimeError(
        f"Point d'injection CSS introuvable dans la page du bundle '{bundle_name}'"
    )


def main(check_only: bool) -> int:
    problems = check_sources()
    if problems:
        for problem in problems:
            print(f"✖ {problem}")
        return 1

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    stale = False

    for bundle_name, sources in BUNDLES.items():
        header, payload = build(bundle_name, sources)
        target = DIST_DIR / f"{bundle_name}.css"
        new_content = header.encode("utf-8") + payload

        if check_only:
            current = target.read_bytes() if target.exists() else b""
            if current != new_content:
                print(f"⚠️  {target.name} périmé")
                stale = True
            else:
                print(f"✔ {target.name} à jour ({len(new_content):,} o)")
            continue

        target.write_bytes(new_content)
        print(
            f"✔ {target.name:16s} {len(new_content):>7,} o  "
            f"({len(sources)} sources, {max(0, len(sources) - 1)} requête(s) économisées)"
        )

    for bundle_name, (html_path, prefix, sources) in CRITICAL_PAGES.items():
        current_html = html_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        new_block = build_inline_block(bundle_name, prefix, sources)
        updated_html = inject_critical_into_html(current_html, bundle_name, prefix, new_block)
        rel_html = html_path.relative_to(BASE_DIR)

        if check_only:
            if html_path.read_bytes() != updated_html.encode("utf-8"):
                print(f"⚠️  {rel_html} : CSS critique inline périmé")
                stale = True
            else:
                print(f"✔ {rel_html} : CSS critique inline à jour")
            continue

        html_path.write_bytes(updated_html.encode("utf-8"))
        print(f"✔ {str(rel_html):32s} CSS critique inline injecté (0 requête bloquante)")

    if check_only and stale:
        print("\n→ Relancer : python tools/build_css_bundles.py")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bundling des feuilles de style par page")
    parser.add_argument("--check", action="store_true",
                        help="vérifie que les bundles sont à jour sans rien écrire")
    args = parser.parse_args()
    sys.exit(main(args.check))
