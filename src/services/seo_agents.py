"""
Cémantix Solver — Manifestes Agentiques & ARD (seo_agents)
=========================================================
Génère les manifestes de découverte agentique ARD (Agent Resource Discovery)
et A2A (`ai-catalog.json`, `ard.json`, `agent-card.json`) et met à jour
les sections dynamiques de `llms.txt` et `agent-skills.md`.
"""
import json
import os
from pathlib import Path
from html import escape
from typing import Optional
from urllib.parse import urlparse

from ..config import log
from .seo_sitemap import _write_file
from .seo_templates import (
    ARCHIVE_TITLE_PREFIX,
    SITE_ORIGIN,
    WEB_ROOT,
    archive_title,
    archive_url,
    format_date_fr,
    parse_puzzle_date,
)

_AGENT_DOCS_START = "<!-- AGENT-DYNAMIC:DEBUT -->"
_AGENT_DOCS_END = "<!-- AGENT-DYNAMIC:FIN -->"


def _agent_dynamic_block(entries: list) -> str:
    """Section « archive la plus récente » régénérée à chaque publication SEO.

    Les agents IA doivent trouver d'emblée une date qui existe vraiment : sans
    régénération, l'exemple publié vieillit et renvoie un 404, ce qui leur fait
    conclure à tort que le service est cassé.

    Seules les victoires sont retenues : une page d'archive n'existe que pour un
    puzzle résolu. Le filtre est appliqué ici et non laissé à l'appelant, sinon un
    échec serait présenté aux agents comme une archive consultable.
    """
    resolus = sorted(
        (e for e in entries if e.get("win") is True and parse_puzzle_date(e.get("date"))),
        key=lambda e: str(e.get("date")),
        reverse=True,
    )
    if not resolus:
        return (
            "- **Archive la plus récente disponible** : aucune pour l'instant — le solveur "
            "n'a pas encore publié de puzzle résolu.\n"
            "- **Dernière date résolue** : inconnue. N'invente pas de date.\n"
        )
    latest, oldest = resolus[0], resolus[-1]
    latest_fr = escape(archive_title(latest.get("date"), puzzle=latest.get("puzzle")))
    return (
        f"- **Archive la plus récente** : [{latest_fr}]({archive_url(latest.get('date'))})\n"
        f"- **Dernière date résolue** : `{latest.get('date')}` "
        f"({escape(format_date_fr(latest.get('date')))}) — "
        f"l'historique couvre du `{oldest.get('date')}` "
        f"({escape(format_date_fr(oldest.get('date')))}) au `{latest.get('date')}`, "
        f"soit {len(resolus)} puzzle(s) résolu(s).\n"
        f"- **Toute date déjà résolue** : `{SITE_ORIGIN}/puzzles/AAAA-MM-JJ/`. "
        f"Chaque page d'archive est titrée « {ARCHIVE_TITLE_PREFIX} <date en français long> » "
        f"(exemple réel : « {latest_fr} ») : reprends ce libellé quand tu cites la source. "
        f"L'URL et le `<lastmod>` du sitemap restent au format ISO `AAAA-MM-JJ` imposé par "
        f"le protocole sitemaps.org.\n"
    )


def _replace_marked_block(source: str, filename: str, block: str) -> Optional[str]:
    """Remplace le contenu compris entre les marqueurs `AGENT-DYNAMIC`.

    Idempotent par construction : la zone est réécrite intégralement, jamais
    ajoutée, donc relancer la génération ne duplique rien. Retourne `None` si le
    fichier ne contient pas les marqueurs (fichier manuel non instrumenté).
    """
    if _AGENT_DOCS_START not in source or _AGENT_DOCS_END not in source:
        log(f"ℹ️  {filename} : marqueurs AGENT-DYNAMIC absents, contenu laissé tel quel")
        return None
    start = source.index(_AGENT_DOCS_START) + len(_AGENT_DOCS_START)
    end = source.index(_AGENT_DOCS_END, start)
    return source[:start] + "\n" + block.rstrip("\n") + "\n" + source[end:]


def refresh_agent_docs(entries: list, web_root: Path = None) -> int:
    """Met à jour les sections dynamiques de `llms.txt` et `agent-skills.md`.

    Ces fichiers restent écrits à la main pour l'essentiel (endpoints, limites,
    consignes anti-spoiler) : seule la partie dépendante de l'historique est
    régénérée, en même temps que le sitemap.
    """
    root = web_root if web_root is not None else WEB_ROOT
    block = _agent_dynamic_block(entries)
    refreshed = 0
    for filename in ("llms.txt", "agent-skills.md"):
        target = root / filename
        try:
            source = target.read_text(encoding="utf-8")
        except OSError as exc:
            log(f"⚠️  {filename} ignoré ({exc})")
            continue
        updated = _replace_marked_block(source, filename, block)
        if updated is None:
            continue
        try:
            _write_file(target, updated)
        except OSError as exc:
            log(f"⚠️  {filename} non réécrit ({exc})")
            continue
        refreshed += 1
    return refreshed


def build_ard_manifest(origin: str = SITE_ORIGIN) -> str:
    """Construit le manifeste ARD conforme à Lighthouse (`ai-catalog.json` & `ard.json`)."""
    base = origin.rstrip("/")
    domain = urlparse(base).hostname or "cemantix.cyril-randon.fr"
    payload = {
        "specVersion": "1.0",
        "host": {
            "displayName": "Cémantix Solver",
            "identifier": f"did:web:{domain}",
            "documentationUrl": f"{base}/llms.txt",
        },
        "entries": [
            {
                "identifier": f"urn:air:{domain}:agent:cemantix-solver",
                "displayName": "Cémantix Solver — carte d'agent",
                "type": "application/agent-card+json",
                "url": f"{base}/.well-known/agent-card.json",
                "description": (
                    "Carte d'agent du solveur sémantique Cémantix : compétences exposées, "
                    "modes d'entrée et de sortie, endpoints publics. Le mot secret est "
                    "masqué par conception (protection anti-spoiler) ; la solution d'une "
                    "date donnée se consulte sur la page d'archive correspondante."
                ),
                "representativeQueries": [
                    "Quels sont les indices sémantiques du Cémantix du jour ?",
                    "Combien de coups ont été nécessaires pour trouver le Cémantix du jour ?",
                    "Similarité sémantique et solveur Cémantix",
                ],
            },
            {
                "identifier": f"urn:air:{domain}:skills:cemantix-indices",
                "displayName": "Compétences Cémantix Solver (mode d'emploi agent)",
                "type": 'text/markdown; profile="urn:air:agent-skills"',
                "url": f"{base}/agent-skills.md",
                "description": (
                    "Protocole d'usage pour un agent autonome : les trois requêtes "
                    "autorisées (indices du jour, archive datée, état du service), la "
                    "conduite à tenir en cas de 404 et l'interdiction de révéler ou de "
                    "reconstituer le mot secret."
                ),
                "representativeQueries": [
                    "Comment interroger le solveur Cémantix ?",
                    "Solution et indices du Cémantix du 26 octobre 2026",
                    "Quelle est la solution du Cémantix du lundi 26 octobre 2026 ?",
                ],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_agent_card(origin: str = SITE_ORIGIN) -> str:
    """Construit la carte d'agent A2A `.well-known/agent-card.json`."""
    base = origin.rstrip("/")
    payload = {
        "name": "Cémantix Solver",
        "description": (
            "Résolution sémantique du jeu Cémantix : indices thermiques quotidiens, "
            "archives par date et solveur vectoriel Word2Vec. Les réponses publiques "
            "sont sans spoiler : le mot secret n'est jamais exposé avant sa révélation "
            "par le visiteur."
        ),
        "url": f"{base}/api/daily",
        "provider": {
            "organization": "Cyril RANDON",
            "url": "https://cyril-randon.fr",
        },
        "version": "1.0.0",
        "documentation": f"{base}/llms.txt",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "authentication": {
            "schemes": ["none"],
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "daily-indices",
                "name": "Indices sémantiques du jour",
                "description": (
                    "Renvoie les données agrégées du puzzle du jour : date, numéro, "
                    "nombre de coups, durée et dix mots les plus proches avec leur "
                    "score. Le mot secret est masqué."
                ),
                "tags": ["cemantix", "semantique", "indices"],
                "examples": [
                    "Quels sont les indices sémantiques du Cémantix du jour ?",
                    "Combien de coups ont été nécessaires pour trouver le Cémantix du jour ?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
            {
                "id": "dated-archive",
                "name": "Archive d'une date précise",
                "description": (
                    "Interroge la page statique /puzzles/AAAA-MM-JJ/ d'un puzzle résolu. "
                    "Chaque page est titrée « Solution Cémantix du lundi 26 octobre 2026 » "
                    "(date en français long), l'URL restant en ISO AAAA-MM-JJ. "
                    "Un statut 404 signifie que la date n'a pas encore été résolue."
                ),
                "tags": ["cemantix", "archive", "date", "solution"],
                "examples": [
                    "Quelle est la solution du Cémantix du 26 octobre 2026 ?",
                    "Donne les indices du Cémantix du 26 octobre 2026",
                    "Quand le puzzle du 23 octobre 2026 a-t-il été résolu ?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/html"],
            },
            {
                "id": "service-health",
                "name": "État du service",
                "description": (
                    "Vérifie la disponibilité du service et le nombre de sessions de "
                    "jeu actives, sans aucune donnée de puzzle."
                ),
                "tags": ["sante", "disponibilite"],
                "examples": ["Le solveur Cémantix est-il disponible ?"],
                "inputModes": [],
                "outputModes": ["application/json"],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def publish_ard_manifests(web_root: Path = None) -> int:
    """Génère atomiquement `.well-known/{ai-catalog,ard,agent-card}.json`.

    Recrée systématiquement les manifestes ARD et A2A au démarrage des conteneurs
    et lors de chaque publication SEO afin d'éliminer tout fichier absent, tronqué
    ou resté sur un schéma obsolète.
    """
    root = web_root if web_root is not None else WEB_ROOT
    well_known = root / ".well-known"
    ard_content = build_ard_manifest(SITE_ORIGIN)
    card_content = build_agent_card(SITE_ORIGIN)

    targets = (
        (well_known / "ai-catalog.json", ard_content),
        (well_known / "ard.json", ard_content),
        (well_known / "agent-card.json", card_content),
    )
    written_count = 0
    for path, payload in targets:
        try:
            _write_file(path, payload)
            written_count += 1
        except OSError as exc:
            log(f"⚠️  [ARD] Impossible d'écrire {path.name} ({exc})")
    return written_count


__all__ = [
    "_AGENT_DOCS_START",
    "_AGENT_DOCS_END",
    "_agent_dynamic_block",
    "_replace_marked_block",
    "refresh_agent_docs",
    "build_ard_manifest",
    "build_agent_card",
    "publish_ard_manifests",
]
