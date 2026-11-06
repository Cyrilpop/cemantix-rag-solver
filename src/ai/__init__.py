"""
Cémantix Solver — Module IA Google Gemini (M12).
=================================================
Fournit les composants pour générer des indices sémantiques et contextuels gradués :
- GeminiClient : client HTTPS REST pour l'API Gemini v1beta
- Prompts et Parseur avec Leak-Guard anti-triche
- Sélecteur de modèle et configurations d'inférence
"""
from typing import Any, Dict, List, Optional

from .gemini_client import GeminiClient
from .model_selector import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    get_generation_config,
    get_model_endpoint,
    get_target_model,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    check_leak_guard,
    parse_gemini_hints_response,
)


def generate_hints(
    secret_word: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> Optional[List[Dict[str, Any]]]:
    """Fonction utilitaire pour générer les 3 indices d'un mot secret."""
    client = GeminiClient(api_key=api_key, model=model)
    return client.generate_hints(secret_word)


def get_model_info() -> Dict[str, Any]:
    """Retourne les informations du modèle configuré."""
    return {
        "model": get_target_model(),
        "temperature": DEFAULT_TEMPERATURE,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
    }


__all__ = [
    "GeminiClient",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_SECONDS",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "check_leak_guard",
    "parse_gemini_hints_response",
    "generate_hints",
    "get_model_info",
    "get_generation_config",
    "get_model_endpoint",
    "get_target_model",
]
