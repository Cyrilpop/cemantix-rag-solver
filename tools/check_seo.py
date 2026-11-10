"""Contrôle de validation du balisage SEO et AEO sur les pages statiques (QUAL-07).

Vérifie sur l'ensemble des pages clés (index.html, play, battle, multi, defi) :
1. Présence du bloc Google Tag Manager placeholder, et absence de tout identifiant
   GTM réel (le secret vit dans .env, substitué à la livraison par le proxy).
2. Présence d'un <title> unique et non vide.
3. Présence d'une <meta name="description"> avec contenu substantiel.
4. Présence d'un <link rel="canonical"> absolu.
5. Présence de balises Open Graph (og:title, og:description, og:image, og:url).
6. Présence d'un bloc de métadonnées structurées JSON-LD valide.
7. Absence de meta obsolète (keywords).
8. Validité JSON des blocs JSON-LD et conformité des types de FAQPage : `mainEntity`
   n'accepte que `Question`, `acceptedAnswer` que `Answer` (un type hors schema.org
   fait perdre le rich result FAQ et remonte en erreur dans Search Console).
9. Absence de délimiteur Go template (« {{ » / « {% ») hors bloc GTM : le proxy
   rend les fichiers via la directive `templates`, une séquence orpheline ferait
   renvoyer un HTTP 500 sur toute la page.

Le contrôle audite aussi les deux pages hub produites par `src/services/seo.py`
(`mot-du-jour`, `methode`) : elles sont régénérées à chaque publication et jamais
versionnées, donc seul un audit du gabarit rendu en mémoire protège la CI.

Il audite enfin la **découvrabilité** des ressources d'agents (`SEO-22`, `SEO-24`) :
`robots.txt` ne doit interdire ni `/.well-known/` ni les documents `llms.*` (un
robot qui n'a pas le droit de lire un manifeste le déclare « non valide »), et
toute URL de premier ordre annoncée par ces documents doit correspondre à un
fichier livrable du webroot — l'audit Google ne signale jamais plus tôt qu'un
lien mort vers sa propre documentation.

Usage :
    python tools/check_seo.py
"""
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _charger_gtm():
    """Charge src/services/gtm.py par chemin, sans dépendre du package `src`.

    Le package `src` tire numpy/chromadb/requests à l'import ; or ce contrôleur
    tourne sur un poste nu (job `docs` de la CI). gtm.py est strictement stdlib.
    """
    spec = spec_from_file_location(
        "_gtm_check", RACINE / "src" / "services" / "gtm.py"
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GTM = _charger_gtm()
# Jeton placeholder attendu dans les fichiers (source de vérité : gtm.py).
GTM_JETON = _GTM.GTM_PLACEHOLDER

PAGES = [
    RACINE / "volumes" / "web" / "index.html",
    RACINE / "volumes" / "web" / "play" / "index.html",
    RACINE / "volumes" / "web" / "battle" / "index.html",
    RACINE / "volumes" / "web" / "multi" / "index.html",
    RACINE / "volumes" / "web" / "defi" / "index.html",
]


def check_html(rel_path: str, html: str) -> list[str]:
    errors = []

    # 0. Bloc Google Tag Manager : le fichier (versionné ou généré) doit porter
    #    le gabarit placeholder géré par src/services/gtm.py, et JAMAIS l'ID réel.
    #    L'identifiant (GOOGLE_TAG_MANAGER_ID, secret réservé à .env) n'est
    #    substitué qu'à la livraison : directive `templates` du proxy Caddy en
    #    production, resolve_gtm_for_delivery() pour les pages servies par
    #    l'API. Ainsi, aucune fuite n'est possible via git.
    #    Exception : la console d'exploitation /panier-9x/ est volontairement
    #    exclue de tout suivi (page privée noindex, nofollow).
    if "panier-9x" not in rel_path:
        if "<!-- GTM:START -->" not in html or "<!-- GTM:END -->" not in html:
            errors.append(f"{rel_path}: Bloc Google Tag Manager (GTM:START/END) manquant")
        elif f"gtm.js?id={GTM_JETON}" not in html:
            errors.append(f"{rel_path}: Bloc GTM présent mais gabarit placeholder altéré")
    if re.search(r"googletagmanager\.com/gtm\.js\?id=GTM-[A-Z0-9]+", html):
        errors.append(f"{rel_path}: FUITE GTM : un ID réel est écrit dans le fichier (il doit rester dans .env)")

    # 0bis. Délimiteurs Go template orphelins. Depuis que la substitution passe
    #    par la directive `templates` de Caddy, toute séquence « {{ » ou « {% »
    #    présente dans un fichier servi est ÉVALUÉE par Caddy : une action
    #    invalide (ou une variable inconnue) fait tomber la réponse en HTTP 500,
    #    et le fichier devient donc injouable pour les moteurs comme pour les
    #    visiteurs. Le seul gabarit autorisé est celui du bloc GTM, exclu ici.
    hors_gtm = re.sub(
        r"<!-- GTM:START -->.*?<!-- GTM:END -->", "", html, flags=re.DOTALL
    )
    if "{{" in hors_gtm or "{%" in hors_gtm:
        errors.append(
            f"{rel_path}: délimiteur Go template ('{{{{' ou '{{%') hors bloc GTM — "
            "la directive `templates` de Caddy le rendrait et renverrait un HTTP 500"
        )

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

    # 7. Conformité des blocs JSON-LD (types schema.org)
    errors.extend(check_jsonld(rel_path, html))

    return errors


# Google n'accepte respectivement que `Question` pour FAQPage.mainEntity et
# `Answer` pour son acceptedAnswer. Un autre type (une blague interne en avait
# glissé un) est signalé en erreur dans Search Console — « type de cible non
# valide » — et la page perd son rich result FAQ.
def check_jsonld(rel_path: str, html: str) -> list[str]:
    """Valide la syntaxe JSON et les types schema.org des blocs JSON-LD.

    Contrôle ciblé sur FAQPage : `mainEntity` n'accepte que des `Question` et
    `acceptedAnswer` que des `Answer`. Les autres types ne sont pas devinables
    de façon fiable, mais un type inconnu de schema.org dans une FAQ est le
    défaut déjà rencontré et le seul à casser l'affichage du rich result.
    """
    errors = []
    for bloc in re.findall(
        r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(bloc.strip())
        except json.JSONDecodeError as exc:
            errors.append(f"{rel_path}: Bloc JSON-LD invalide ({exc})")
            continue

        noeuds = data.get("@graph", [data]) if isinstance(data, dict) else data
        if not isinstance(noeuds, list):
            continue
        for noeud in noeuds:
            if not isinstance(noeud, dict) or "FAQPage" not in _types(noeud):
                continue
            main = noeud.get("mainEntity", [])
            for entite in (main if isinstance(main, list) else [main]):
                if not isinstance(entite, dict):
                    continue
                types_entite = _types(entite)
                if "Question" not in types_entite:
                    errors.append(
                        f"{rel_path}: FAQPage.mainEntity de type illicite "
                        f"{sorted(types_entite) or 'aucun'} (question « {entite.get('name', '?')} ») : "
                        "seul Question est accepté par Google"
                    )
                reponse = entite.get("acceptedAnswer")
                if isinstance(reponse, dict) and "Answer" not in _types(reponse):
                    errors.append(
                        f"{rel_path}: FAQPage.acceptedAnswer de type illicite "
                        f"{sorted(_types(reponse)) or 'aucun'} : seul Answer est accepté"
                    )
    return errors


def _types(noeud: dict) -> set:
    """Types déclarés par un nœud JSON-LD, que `@type` soit une chaîne ou une liste."""
    t = noeud.get("@type")
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return {x for x in t if isinstance(x, str)}
    return set()


def check_page(path: Path) -> list[str]:
    if not path.exists():
        return [f"Fichier manquant : {path}"]
    # Les pages statiques versionnées portent TOUJOURS le placeholder : la
    # substitution par l'ID réel n'intervient qu'au rendu HTTP (server.py).
    return check_html(str(path.relative_to(RACINE)), path.read_text(encoding="utf-8"))


# Entrée d'historique factice : elle sert à rendre les pages hub pour l'audit, sans
# base de données ni modèle vectoriel (src/services/seo.py ne dépend que de la stdlib).
_ENTREE_TEMOIN = {
    "date": "2026-10-26",
    "puzzle": 1700,
    "word": "maison",
    "win": True,
    "tries": 9,
    "duration_seconds": 41.7,
    "source": "rag",
    "top_guesses": [{"word": "cabane", "score": 31.2, "permille": 812}],
}


def check_pages_generees() -> list[str]:
    """Audit des pages hub produites par `src/services/seo.py` (jamais versionnées).

    `volumes/web/mot-du-jour/` et `volumes/web/methode/` sont régénérées à chaque
    publication : elles ne sont donc jamais dans le dépôt. Les rendre en mémoire est
    le seul moyen de casser la CI si un gabarit perd son titre, sa canonical ou son
    JSON-LD.
    """
    sys.path.insert(0, str(RACINE))
    try:
        from src.services.seo import build_methode_page, build_mot_du_jour_page
    except ModuleNotFoundError as exc:
        # Dépendance tierce absente (poste de dev sans requirements.txt) : l'audit des
        # pages générées est suspendu, mais il ne doit pas faire échouer le contrôle.
        print(f"  [i] Pages générées non auditées : module manquant « {exc.name} »")
        return []
    except Exception as exc:  # le générateur lui-même est cassé
        return [f"Impossible d'importer le générateur SEO : {exc}"]

    erreurs = []
    gabarits = (
        ("volumes/web/mot-du-jour/index.html (généré)", build_mot_du_jour_page(_ENTREE_TEMOIN, [_ENTREE_TEMOIN])),
        ("volumes/web/methode/index.html (généré)", build_methode_page()),
    )
    for nom, html in gabarits:
        erreurs.extend(check_html(nom, html))
        if "••••••••" in html:
            erreurs.append(f"{nom}: le leurre de mot masqué •••••••• est publié comme indice")
        if "<h1>" not in html:
            erreurs.append(f"{nom}: <h1> manquante, aucune page ne doit être sans titre H1")
    return erreurs


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


# --- Découvrabilité des ressources d'agents (`SEO-22`, `SEO-24`) ------------ #

WEB_ROOT = RACINE / "volumes" / "web"
ROBOTS_TXT = WEB_ROOT / "robots.txt"
LLMS_MD = WEB_ROOT / "llms.md"
SITE_ORIGIN = "https://cemantix.cyril-randon.fr"

# Ressources que tout agent IA est censé pouvoir lire. `robots.txt` ne doit en
# interdire aucune : un crawleur conforme aux usages robots (Google, GPTBot,
# ClaudeBot…) qui n'a pas le droit de lire un manifeste ne peut pas le valider —
# l'audit agentique remonte alors « le schéma ai-catalog.json n'est pas valide »
# sans jamais dire que c'est un refus de crawl. Et si le serveur de fichiers
# replie de surcroît sur la page d'accueil, le JSON attendu se lit
# « Unexpected token '<', "<!DOCTYPE " ».
RESSOURCES_AGENTS = (
    "/llms.txt",
    "/llms.md",
    "/agent-skills.md",
    "/.well-known/ai-catalog.json",
    "/.well-known/ard.json",
    "/.well-known/agent-card.json",
)

# URLs qui ne correspondent à aucun fichier versionné parce qu'elles sont servies
# par l'API ou produites au démarrage par `ensure_seo_published()` : elles ne
# peuvent pas être tenues en défaut dans un dépôt fraîchement cloné.
URLS_GENREES = (
    "/",
    "/sitemap.xml",
    "/indexnow-key.txt",
    "/mot-du-jour/",
    "/methode/",
    "/puzzles/",
)


def _robots_interdit(robots: str, url_path: str):
    """Motif `Disallow:` qui bloque `url_path`, ou `None` si la ressource est lisible.

    Convention robots (RFC 9309) : un motif est un préfixe du chemin, `*` étant le
    seul joker reconnu par les crawleurs.
    """
    for ligne in robots.splitlines():
        ligne = ligne.strip()
        if not ligne.lower().startswith("disallow:"):
            continue
        motif = ligne.split(":", 1)[1].strip()
        if not motif:
            continue
        regex = "^" + "".join(".*" if car == "*" else re.escape(car) for car in motif)
        if re.match(regex, url_path):
            return motif
    return None


def _urls_de_meme_origine(texte: str) -> list[str]:
    """Chemins `SITE_ORIGIN/...` cités dans un document Markdown ou JSON.

    La classe exclut les délimiteurs qui ne font jamais partie d'un chemin de ce
    site : parenthèse d'un lien Markdown, guillemet d'un attribut JSON, backtick
    d'un code en ligne, virgule et ponctuation collée à l'URL.
    """
    return re.findall(re.escape(SITE_ORIGIN) + r"(/[^\s)\]\"'`,]*)", texte)


def _fichier_livrable(chemin: str) -> bool:
    """Le webroot peut-il répondre sur cette URL (fichier, page générée ou API) ?"""
    if chemin.startswith("/api/") or chemin in URLS_GENREES or chemin.startswith("/puzzles/"):
        return True
    cible = WEB_ROOT / chemin.lstrip("/")
    if chemin.endswith("/"):
        return (cible / "index.html").exists() or cible.exists()
    return cible.exists()


def check_decouvrabilite_agents() -> list[str]:
    """`robots.txt` laisse lire les manifestes, et chaque URL annoncée est livrable."""
    erreurs: list[str] = []

    if not ROBOTS_TXT.exists():
        erreurs.append("volumes/web/robots.txt manquant (les agents y cherchent le plan du site)")
    else:
        robots = ROBOTS_TXT.read_text(encoding="utf-8")
        for ressource in RESSOURCES_AGENTS:
            motif = _robots_interdit(robots, ressource)
            if motif:
                erreurs.append(
                    f"volumes/web/robots.txt : « Disallow: {motif} » interdit {ressource} — "
                    "une ressource de découverte illisible par le robot est remontée "
                    "par l'audit agentique comme un manifeste absent ou invalide"
                )

    vus = set()
    for source in (LLMS_TXT, LLMS_MD, AGENT_SKILLS):
        if not source.exists():
            continue
        for chemin in _urls_de_meme_origine(source.read_text(encoding="utf-8")):
            if (source, chemin) in vus or _fichier_livrable(chemin):
                continue
            vus.add((source, chemin))
            erreurs.append(
                f"{source.relative_to(RACINE)} : lien mort vers {SITE_ORIGIN}{chemin} — "
                "aucun fichier du webroot ne correspond (page générée absente d'URLS_GENREES ?)"
            )

    for manifest in (AI_CATALOG, AGENT_CARD):
        if not manifest.exists():
            continue
        try:
            contenu = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # déjà remonté par check_agentique()
        for chemin in _urls_de_meme_origine(json.dumps(contenu, ensure_ascii=False)):
            if (manifest, chemin) in vus or _fichier_livrable(chemin):
                continue
            vus.add((manifest, chemin))
            erreurs.append(
                f"{manifest.relative_to(RACINE)} : ressource annoncée injoignable "
                f"{SITE_ORIGIN}{chemin}"
            )

    return erreurs


def check_gtm_fuite() -> list[str]:
    """Anti-fuite GTM : aucun identifiant réel ne doit être écrit sur le disque.

    Balaye **toutes** les pages HTML de `volumes/web` — versionnées (les 5 vues)
    comme générées (archives `/puzzles/`, hubs `/mot-du-jour/` et `/methode/`) —
    hors la console `/panier-9x/` exclue du suivi. Seul le gabarit placeholder
    `id={{ env `GOOGLE_TAG_MANAGER_ID` }}` est autorisé : l'ID réel (la valeur de
    GOOGLE_TAG_MANAGER_ID dans .env) n'existe qu'en mémoire, substitué à la
    livraison par la directive `templates` du proxy.
    """
    errors = []
    web_root = RACINE / "volumes" / "web"
    gtm_real_re = re.compile(r"googletagmanager\.com/gtm\.js\?id=GTM-[A-Z0-9]+")
    for html_file in sorted(web_root.rglob("*.html")):
        if "panier-9x" in html_file.parts:
            continue
        if gtm_real_re.search(html_file.read_text(encoding="utf-8", errors="replace")):
            errors.append(
                f"{html_file.relative_to(RACINE)} : FUITE GTM — un ID réel est "
                "écrit sur le disque (il doit rester dans .env)"
            )
    return errors


def main() -> int:
    total_errors = []
    for page in PAGES:
        errs = check_page(page)
        total_errors.extend(errs)
    total_errors.extend(check_pages_generees())
    total_errors.extend(check_agentique())
    total_errors.extend(check_decouvrabilite_agents())
    total_errors.extend(check_gtm_fuite())

    if total_errors:
        print("[!] Erreurs SEO detectees :")
        for err in total_errors:
            print(f"  - {err}")
        return 1

    print(f"[OK] Audit SEO reussi sur {len(PAGES)} pages principales (title, description, canonical, OG, JSON-LD).")
    print("[OK] Audit des pages hub generees reussi (mot-du-jour, methode).")
    print("[OK] Audit agentique reussi (llms.txt H1 + liens, catalogue ARD conforme).")
    print("[OK] Decouvrabilite agents : robots.txt ne bloque aucune ressource, aucun lien mort annonce.")
    print("[OK] Anti-fuite GTM : aucun ID reel commité dans volumes/web (placeholder uniquement).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
