"""Contrôle de validation du balisage SEO et AEO sur les pages statiques (QUAL-07).

Vérifie sur l'ensemble des pages clés (index.html, play, battle, multi) :
1. Présence d'un <title> unique et non vide.
2. Présence d'une <meta name="description"> avec contenu substantiel.
3. Présence d'un <link rel="canonical"> absolu.
4. Présence de balises Open Graph (og:title, og:description, og:image, og:url).
5. Présence d'un bloc de métadonnées structurées JSON-LD valide.
6. Absence de meta obsolète (keywords).

Usage :
    python tools/check_seo.py
"""
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PAGES = [
    RACINE / "volumes" / "web" / "index.html",
    RACINE / "volumes" / "web" / "play" / "index.html",
    RACINE / "volumes" / "web" / "battle" / "index.html",
    RACINE / "volumes" / "web" / "multi" / "index.html",
]


def check_page(path: Path) -> list[str]:
    errors = []
    if not path.exists():
        return [f"Fichier manquant : {path}"]

    html = path.read_text(encoding="utf-8")
    rel_path = path.relative_to(RACINE)

    # 1. Title
    title_match = re.search(r"<title>([^<]+)</title>", html, re.I)
    if not title_match or not title_match.group(1).strip():
        errors.append(f"{rel_path}: Balise <title> manquante ou vide")

    # 2. Meta description
    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
    if not desc_match or len(desc_match.group(1).strip()) < 20:
        errors.append(f"{rel_path}: <meta name='description'> absente ou trop courte")

    # 3. Canonical
    canon_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', html, re.I)
    if not canon_match or not canon_match.group(1).startswith("http"):
        errors.append(f"{rel_path}: <link rel='canonical'> manquant ou non absolu")

    # 4. Open Graph
    for og_prop in ("og:title", "og:description", "og:image", "og:url"):
        if not re.search(rf'<meta\s+property=["\']{og_prop}["\']\s+content=["\'][^"\']+["\']', html, re.I):
            errors.append(f"{rel_path}: Balise Open Graph manquante : {og_prop}")

    # 5. JSON-LD
    if '<script type="application/ld+json">' not in html:
        errors.append(f"{rel_path}: Bloc JSON-LD <script type='application/ld+json'> manquant")

    # 6. Keywords (obsolète SEO-05)
    if re.search(r'<meta\s+name=["\']keywords["\']', html, re.I):
        errors.append(f"{rel_path}: Balise obsolète <meta name='keywords'> détectée")

    return errors


LLMS_TXT = RACINE / "volumes" / "web" / "llms.txt"
AI_CATALOG = RACINE / "volumes" / "web" / ".well-known" / "ai-catalog.json"
ARD_MANIFEST = RACINE / "volumes" / "web" / ".well-known" / "ard.json"
AGENT_CARD = RACINE / "volumes" / "web" / ".well-known" / "agent-card.json"
AGENT_SKILLS = RACINE / "volumes" / "web" / "agent-skills.md"

ARD_HOST_ALLOWED_KEYS = {
    "displayName",
    "identifier",
    "documentationUrl",
    "logoUrl",
    "trustManifest",
}

# Types de médias acceptés par le schéma ARD pour une entrée de catalogue. Le
# validateur externe rejette toute autre valeur (openapi+json, text/html, ...).
ARD_MEDIA_TYPES = (
    "application/ai-catalog+json",
    "application/agent-card+json",
    "application/a2a-agent-card+json",
    "application/mcp-server-card+json",
    "application/agent-skills+zip",
    "application/agent-skills+gzip",
    'text/markdown; profile="urn:air:agent-skills"',
    "application/ai-registry",
    "application/ai-registry+json",
)


def check_agentique() -> list[str]:
    """Valide les fichiers de découverte par les agents IA (llms.txt + ARD).

    Règles conformes au validateur ARD de Google Lighthouse (ard-schema) :
    - `llms.txt` doit exister, commencer par un en-tête H1 et contenir des liens ;
    - `ai-catalog.json` et `ard.json` doivent être synchronisés, porter uniquement
      les clés autorisées (`specVersion`, `host`, `entries`), un objet `host` avec
      `displayName` requis (sans propriété additionnelle), et des types de médias
      reconnus par la spécification ARD.
    """
    errors: list[str] = []

    # --- llms.txt : H1 obligatoire + liens -------------------------------- #
    if not LLMS_TXT.exists():
        errors.append("volumes/web/llms.txt manquant (les agents IA cherchent ce nom précis)")
    else:
        lignes = LLMS_TXT.read_text(encoding="utf-8").splitlines()
        if not any(re.match(r"^# \S", ligne) for ligne in lignes):
            errors.append("volumes/web/llms.txt : en-tête H1 ('# Titre') obligatoire absent")
        if not re.search(r"\[[^\]]+\]\(https?://[^)]+\)", LLMS_TXT.read_text(encoding="utf-8")):
            errors.append("volumes/web/llms.txt : aucune liste de liens Markdown détectée")

    # --- ai-catalog.json & ard.json : schéma ARD officiel ----------------- #
    if not AI_CATALOG.exists():
        errors.append("volumes/web/.well-known/ai-catalog.json manquant")
    else:
        try:
            catalogue = json.loads(AI_CATALOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"volumes/web/.well-known/ai-catalog.json : JSON invalide ({e})")
            catalogue = None

        if not ARD_MANIFEST.exists():
            errors.append("volumes/web/.well-known/ard.json manquant (requis par ARD v0.91+ / Lighthouse)")
        elif ARD_MANIFEST.read_bytes() != AI_CATALOG.read_bytes():
            errors.append("ard.json et ai-catalog.json ne sont pas synchronisés")

        if catalogue is not None:
            extra_root = set(catalogue.keys()) - {"specVersion", "host", "entries"}
            if extra_root:
                errors.append(f"ai-catalog.json : propriétés racine interdites : {sorted(extra_root)}")
            if catalogue.get("specVersion") != "1.0":
                errors.append("ai-catalog.json : 'specVersion' requis et égal à '1.0'")
            if "host" in catalogue:
                host = catalogue["host"]
                if not isinstance(host, dict):
                    errors.append(
                        "ai-catalog.json : 'host' doit être un objet JSON conforme à ai-catalog.schema.json "
                        "(une chaîne simple échoue l'audit Lighthouse ard-schema)"
                    )
                else:
                    if not isinstance(host.get("displayName"), str) or not host["displayName"].strip():
                        errors.append("ai-catalog.json : 'host.displayName' requis")
                    extra_host = set(host.keys()) - ARD_HOST_ALLOWED_KEYS
                    if extra_host:
                        errors.append(f"ai-catalog.json : propriétés 'host' non autorisées : {sorted(extra_host)}")
            entrees = catalogue.get("entries", [])
            if not entrees:
                errors.append("ai-catalog.json : au moins une entrée est requise")
            for entree in entrees:
                type_media = entree.get("type", "")
                if type_media not in ARD_MEDIA_TYPES:
                    errors.append(
                        f"ai-catalog.json : type de média non autorisé pour "
                        f"« {entree.get('displayName', '?')} » : {type_media!r}"
                    )
                url = entree.get("url", "")
                if not url.startswith("https://"):
                    errors.append(f"ai-catalog.json : URL non absolue/HTTPS pour {url!r}")

    # --- Ressources référencées : doivent exister -------------------------- #
    for fichier, nom in ((AGENT_CARD, "agent-card.json"), (AGENT_SKILLS, "agent-skills.md")):
        if not fichier.exists():
            errors.append(f"volumes/web/.well-known/{nom} manquant (référencé par le catalogue ARD)")

    if AGENT_CARD.exists():
        try:
            carte = json.loads(AGENT_CARD.read_text(encoding="utf-8"))
            for champ in ("name", "description", "url", "version", "skills"):
                if champ not in carte:
                    errors.append(f"agent-card.json : champ requis manquant : {champ}")
        except json.JSONDecodeError as e:
            errors.append(f"volumes/web/.well-known/agent-card.json : JSON invalide ({e})")

    return errors


def main() -> int:
    total_errors = []
    for page in PAGES:
        errs = check_page(page)
        total_errors.extend(errs)
    total_errors.extend(check_agentique())

    if total_errors:
        print("[!] Erreurs SEO detectees :")
        for err in total_errors:
            print(f"  - {err}")
        return 1

    print(f"[OK] Audit SEO reussi sur {len(PAGES)} pages principales (title, description, canonical, OG, JSON-LD).")
    print("[OK] Audit agentique reussi (llms.txt H1 + liens, catalogue ARD conforme).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
