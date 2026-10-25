"""
Cémantix Solver — Utilitaires Communs du Moteur de Jeu
=====================================================
Constantes de stockage et fonctions météo partagées entre tous les modes de jeu.
"""
from typing import Optional

from ..config import DATA_DIR

WEB_SESSIONS_FILE = DATA_DIR / "web_sessions.json"
MULTI_SESSIONS_FILE = DATA_DIR / "multi_sessions.json"


def get_weather_tier(score: float, permille: Optional[int]) -> str:
    """Retourne l'icône et libellé météo officiel de Cémantix."""
    if permille == 1000 or score >= 100.0:
        return "🥳 Trouvé !"
    if permille is not None:
        if permille >= 990:
            return "😱 Brûlant"
        if permille >= 900:
            return "🥵 Très chaud"
        return "😎 Chaud"
    if score >= 15.0:
        return "🥶 Frais"
    if score >= 0.0:
        return "🥶 Froid"
    return "🧊 Glacé"
