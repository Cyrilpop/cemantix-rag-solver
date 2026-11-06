"""
Client HTTP REST pour l'API Google Gemini (M12).
"""
import os
from typing import Any, Dict, List, Optional
import requests

from .model_selector import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    get_generation_config,
    get_model_endpoint,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_gemini_hints_response,
)

try:
    from ..config import log
except ImportError:
    def log(msg: str) -> None:
        print(msg)


class GeminiClient:
    """Client pour interagir avec l'API Google Gemini via HTTPS REST."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    def is_configured(self) -> bool:
        """Indique si la clé d'API est présente et configurée."""
        return bool(self.api_key)

    def request_hints(self, secret_word: str) -> Optional[List[Dict[str, Any]]]:
        """Génère et valide les 3 indices pour un mot secret (alias de generate_hints)."""
        return self.generate_hints(secret_word)

    def generate_hints(self, secret_word: str) -> Optional[List[Dict[str, Any]]]:
        """Appelle l'API Gemini pour générer les 3 indices gradués pour le mot secret donné.

        Retourne la liste des 3 indices validés ou None en cas d'erreur/indisponibilité.
        """
        if not self.is_configured():
            log("⚠️  [AI] Clé d'API GEMINI_API_KEY absente ou vide. Impossible de générer les indices.")
            return None

        if not secret_word or not secret_word.strip():
            log("⚠️  [AI] Mot secret vide fourni pour la génération d'indices.")
            return None

        endpoint = get_model_endpoint(self.model)
        url = f"{endpoint}?key={self.api_key}"

        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_prompt(secret_word)}]
                }
            ],
            "generationConfig": get_generation_config(self.temperature),
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            log(f"⚠️  [AI] Timeout ({self.timeout}s) lors de l'appel à l'API Gemini pour '{secret_word}'.")
            return None
        except requests.exceptions.RequestException as e:
            log(f"⚠️  [AI] Erreur réseau lors de l'appel à l'API Gemini : {e}")
            return None

        if response.status_code != 200:
            log(f"⚠️  [AI] Erreur API Gemini (HTTP {response.status_code}) : {response.text[:200]}")
            return None

        try:
            res_data = response.json()
            candidates = res_data.get("candidates", [])
            if not candidates:
                log("⚠️  [AI] Réponse Gemini sans candidat généré.")
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                log("⚠️  [AI] Candidat Gemini sans contenu textuel.")
                return None
            raw_text = parts[0].get("text", "")
            hints = parse_gemini_hints_response(raw_text, secret_word)
            for h in hints:
                h["model"] = self.model
            return hints
        except Exception as e:
            log(f"⚠️  [AI] Échec du parsing ou validation Leak-Guard des indices Gemini : {e}")
            return None
