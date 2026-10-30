"""
Cémantix Solver — État de santé du solveur (src.api.liveness)
=============================================================
L'API web doit pouvoir dire à un joueur si le moteur qui traite les défis est
en vie, sans jamais importer le code du worker (règle structurelle DEFI-04 :
le conteneur web n'exécute aucun calcul).

Le worker écrit déjà un battement toutes les 15 s dans le volume partagé
`cemantix_data/daemon_heartbeat.json` — pour son HEALTHCHECK Docker. Ce module
ne fait que le relire : lecture d'un fichier, aucun calcul, aucune dépendance
vers `src.engine` ou `src.services`.
"""
import json
import os
import time
from pathlib import Path

from ..config import DATA_DIR

HEARTBEAT_FILE = Path(os.getenv("DAEMON_HEARTBEAT_FILE")
                      or str(DATA_DIR / "daemon_heartbeat.json"))
# Le battement est écrit toutes les 15 s (DAEMON_HEARTBEAT_INTERVAL) ; 90 s de
# silence = trois battements manquants = le worker ne tourne plus.
WORKER_SILENCE_SECONDS = 90.0


def solveur_state() -> str:
    """`vivant` | `hors-ligne` | `inconnu`.

    `inconnu` (fichier absent ou illisible) n'est JAMAIS traité comme une panne
    : un problème de lecture du battement ne doit pas faire croire à une
    indisponibilité du solveur et décourager un joueur qui va bien.
    """
    try:
        data = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("updated_at", 0))
    except Exception:
        return "inconnu"
    if data.get("status") == "stopped":
        return "hors-ligne"
    return "vivant" if age <= WORKER_SILENCE_SECONDS else "hors-ligne"
