"""
Sélecteur et configuration du modèle Google Gemini pour Cémantix Solver (M12).
"""
import os
from typing import Any, Dict

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TIMEOUT_SECONDS = 10.0


def get_target_model() -> str:
    """Retourne le nom du modèle cible configuré."""
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def get_model_endpoint(model: str = DEFAULT_MODEL) -> str:
    """Retourne l'URL de base pour l'appel REST generateContent de l'API Gemini."""
    clean_model = model.replace("models/", "")
    return f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent"


def get_generation_config(temperature: float = DEFAULT_TEMPERATURE) -> Dict[str, Any]:
    """Retourne la configuration de génération pour l'API Gemini."""
    return {
        "temperature": temperature,
        "topP": 0.95,
        "responseMimeType": "application/json",
    }
