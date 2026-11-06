"""
Ingénierie des prompts et validation des réponses d'indices IA Gemini (M12).
"""
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """Tu es le Maître du Jeu officiel de Cémantix, expert en linguistique française et relations sémantiques.
Ton rôle est de générer exactement trois (3) indices gradués pour aider un joueur à deviner un mot secret sans jamais lui donner la solution.

RÈGLES D'OR DE SÉCURITÉ ET QUALITÉ :
1. INTERDICTION ABSOLUE de citer le mot secret, sa racine étymologique, son pluriel, ou un mot de la même famille dans n'importe quel indice (ni dans le mot, ni dans la phrase).
2. Pour chaque niveau d'indice, tu dois OBLIGATOIREMENT fournir deux éléments complémentaires :
   - "word" : UN SEUL mot français en minuscules (nom, adjectif ou verbe), sans espace ni ponctuation, servant de balise sémantique.
   - "phrase" : Une phrase d'indice rédigée en français (15 à 30 mots), évocatrice, fluide et stimulante, décrivant le concept sans le nommer.
3. Les 3 niveaux doivent respecter une graduation de difficulté et de proximité stricte :
   - Niveau 1 (weight = 0.33) : Éloigné. Domaine général, cadre thématique large ou concept abstrait englobant.
   - Niveau 2 (weight = 0.66) : Intermédiaire. Fonction, usage courant, contexte pratique ou caractéristique physique/symbolique.
   - Niveau 3 (weight = 1.00) : Proche. Indice sémantique très ciblé, quasi-synonyme ou analogie déterminante sans révéler le mot.
4. Réponds STRICTEMENT au format JSON valide, sans balises superflues, sans texte d'introduction ni de conclusion."""


def build_user_prompt(secret_word: str) -> str:
    """Construit le prompt utilisateur pour générer les 3 indices gradués."""
    return f"""Génère les 3 indices gradués (mot + phrase) pour le mot secret français suivant :
MOT_SECRET : "{secret_word}"

Format JSON attendu :
{{
  "secret_word": "{secret_word}",
  "hints": [
    {{
      "level": 1,
      "weight": 0.33,
      "word": "<mot_domaine_eloigne>",
      "phrase": "<phrase_guide_domaine>"
    }},
    {{
      "level": 2,
      "weight": 0.66,
      "word": "<mot_fonction_usage>",
      "phrase": "<phrase_guide_fonction>"
    }},
    {{
      "level": 3,
      "weight": 1.00,
      "word": "<mot_proche_analogie>",
      "phrase": "<phrase_guide_proximite>"
    }}
  ]
}}"""


def _normalize(text: str) -> str:
    """Normalise un texte : minuscules sans accents ni ponctuation superflue."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def check_leak_guard(secret_word: str, word: str, phrase: str) -> bool:
    """Vérifie si le mot secret ou sa racine apparaît dans le mot ou la phrase d'indice.

    Retourne True si une fuite est détectée (rejet obligatoire), False sinon.
    """
    if not secret_word:
        return False

    sec_norm = _normalize(secret_word).strip()
    if not sec_norm:
        return False

    # Mot indice
    w_norm = _normalize(word).strip()
    if w_norm == sec_norm:
        return True

    # Pluriel ou dérivé immédiat
    if w_norm == sec_norm + "s" or w_norm == sec_norm + "es" or sec_norm == w_norm + "s":
        return True

    # Radical étymologique/morphologique (longueur >= 4)
    stem_len = max(4, len(sec_norm) - 2) if len(sec_norm) >= 5 else len(sec_norm)
    stem = sec_norm[:stem_len]

    if len(stem) >= 4 and w_norm.startswith(stem):
        return True

    # Analyse de la phrase d'indice
    phrase_norm = _normalize(phrase)
    # 1. Présence directe de la séquence du mot secret entourée de séparateurs
    if re.search(rf"\b{re.escape(sec_norm)}\b", phrase_norm):
        return True
    if re.search(rf"\b{re.escape(sec_norm)}s\b", phrase_norm):
        return True
    if re.search(rf"\b{re.escape(sec_norm)}es\b", phrase_norm):
        return True

    # 2. Présence de tokens partageant le radical de taille >= 4
    tokens = re.findall(r"\b[a-z0-9_]+\b", phrase_norm)
    for token in tokens:
        if token == sec_norm:
            return True
        if len(stem) >= 4 and token.startswith(stem):
            if len(token) <= len(sec_norm) + 4:
                return True

    return False


def parse_gemini_hints_response(raw_text: str, secret_word: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse et valide le JSON d'indices retourné par Gemini, avec application du Leak-Guard.

    Lève ValueError si le JSON est invalide, mal structuré ou si une fuite est détectée.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Réponse Gemini vide")

    cleaned = raw_text.strip()
    # Supprimer les éventuels délimiteurs markdown ```json ... ```
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Erreur de décodage JSON de la réponse Gemini : {e}")

    if not isinstance(data, dict):
        raise ValueError("Le JSON racine doit être un objet dictionnaire")

    effective_secret = secret_word or data.get("secret_word") or ""
    raw_hints = data.get("hints")
    if not isinstance(raw_hints, list) or len(raw_hints) != 3:
        raise ValueError(
            f"La clé 'hints' doit contenir exactement 3 éléments, trouvé : {len(raw_hints) if isinstance(raw_hints, list) else 0}"
        )

    validated_hints = []
    expected_levels = {1, 2, 3}
    found_levels = set()

    for idx, hint in enumerate(raw_hints):
        if not isinstance(hint, dict):
            raise ValueError(f"L'indice #{idx+1} n'est pas un dictionnaire")

        level = hint.get("level")
        if level not in expected_levels:
            raise ValueError(f"Niveau d'indice invalide : {level} (attendu 1, 2 ou 3)")
        if level in found_levels:
            raise ValueError(f"Niveau d'indice dupliqué : {level}")
        found_levels.add(level)

        weight = hint.get("weight")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            raise ValueError(f"Poids d'indice invalide pour le niveau {level} : {weight}")

        word = str(hint.get("word") or "").strip()
        phrase = str(hint.get("phrase") or "").strip()

        if not word:
            raise ValueError(f"Mot indice vide pour le niveau {level}")
        if not phrase:
            raise ValueError(f"Phrase indice vide pour le niveau {level}")

        # Leak-Guard : rejet si fuite du mot secret
        if effective_secret and check_leak_guard(effective_secret, word, phrase):
            raise ValueError(
                f"Leak-Guard: le mot secret '{effective_secret}' ou sa racine apparaît dans l'indice niveau {level} (mot='{word}')"
            )

        validated_hints.append({
            "hint_level": level,
            "level": level,
            "weight": weight,
            "hint_word": word,
            "word": word,
            "hint_phrase": phrase,
            "phrase": phrase,
        })

    # Trier par niveau croissant
    validated_hints.sort(key=lambda h: h["hint_level"])
    return validated_hints
