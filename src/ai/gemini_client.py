"""
Client HTTP REST pour l'API Google Gemini (M12).
"""
import os
import time
from typing import Any, Dict, List, Optional
import requests

from .model_selector import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    FALLBACK_MODELS,
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
        fallback_models: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_retries: int = 2,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        self.model = model
        self.fallback_models = fallback_models if fallback_models is not None else list(FALLBACK_MODELS)
        self.timeout = timeout if timeout is not None else float(os.getenv("GEMINI_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
        self.temperature = temperature
        self.max_retries = max_retries

    def is_configured(self) -> bool:
        """Indique si la clé d'API est présente et configurée."""
        return bool(self.api_key)

    def request_hints(self, secret_word: str) -> Optional[List[Dict[str, Any]]]:
        """Génère et valide les 3 indices pour un mot secret (alias de generate_hints)."""
        return self.generate_hints(secret_word)

    def generate_hints(self, secret_word: str) -> Optional[List[Dict[str, Any]]]:
        """Appelle l'API Gemini pour générer les 3 indices gradués pour le mot secret donné.

        Effectue un retry modéré en cas de saturation (503/429) et bascule sur un modèle
        de repli si le modèle principal est temporairement indisponible.
        """
        if not self.is_configured():
            log("⚠️  [AI] Clé d'API GEMINI_API_KEY absente ou vide. Impossible de générer les indices.")
            return None

        if not secret_word or not secret_word.strip():
            log("⚠️  [AI] Mot secret vide fourni pour la génération d'indices.")
            return None

        models_chain = [self.model]
        for fb in self.fallback_models:
            if fb not in models_chain:
                models_chain.append(fb)

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

        for model_idx, target_model in enumerate(models_chain):
            endpoint = get_model_endpoint(target_model)
            url = f"{endpoint}?key={self.api_key}"

            for attempt in range(1, self.max_retries + 1):
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=self.timeout,
                    )
                except requests.exceptions.Timeout:
                    log(f"⚠️  [AI] Timeout ({self.timeout}s) modèle '{target_model}' (tentative {attempt}/{self.max_retries}).")
                    if attempt < self.max_retries:
                        time.sleep(2.0)
                        continue
                    break
                except requests.exceptions.RequestException as e:
                    log(f"⚠️  [AI] Erreur réseau modèle '{target_model}' : {e}")
                    if attempt < self.max_retries:
                        time.sleep(2.0)
                        continue
                    break

                if response.status_code == 200:
                    try:
                        res_data = response.json()
                        candidates = res_data.get("candidates", [])
                        if not candidates:
                            log("⚠️  [AI] Réponse Gemini sans candidat généré.")
                            break
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts:
                            log("⚠️  [AI] Candidat Gemini sans contenu textuel.")
                            break
                        raw_text = parts[0].get("text", "")
                        hints = parse_gemini_hints_response(raw_text, secret_word)
                        for h in hints:
                            h["model"] = target_model
                        if target_model != self.model:
                            log(f"ℹ️  [AI] Indices générés avec succès via le modèle de repli '{target_model}'.")
                        return hints
                    except Exception as e:
                        log(f"⚠️  [AI] Échec du parsing ou validation Leak-Guard des indices Gemini ({target_model}) : {e}")
                        break

                # Erreur HTTP
                if response.status_code in (429, 500, 502, 503, 504):
                    log(f"⚠️  [AI] Modèle '{target_model}' temporairement indisponible (HTTP {response.status_code}).")
                    if attempt < self.max_retries:
                        time.sleep(2.0 * attempt)
                        continue
                    break
                else:
                    log(f"⚠️  [AI] Erreur API Gemini non rejouable (HTTP {response.status_code}) : {response.text[:200]}")
                    return None

            if model_idx < len(models_chain) - 1:
                next_model = models_chain[model_idx + 1]
                log(f"🔄  [AI] Bascule automatique vers le modèle de repli '{next_model}'...")

        return None
