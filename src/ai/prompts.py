"""
Ingénierie des prompts et validation des réponses d'indices IA Gemini (M12).
"""
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """Tu es le Maître du Jeu officiel de Cémantix, expert en linguistique française et relations sémantiques.
Ton rôle est de concevoir exactement trois (3) indices gradués pour guider un joueur vers un mot secret sans JAMAIS lui vendre la mèche.

PHILOSOPHIE CÉMANTIX :
Dans Cémantix, la proximité est mesurée par des vecteurs sémantiques (Word2Vec).
Un indice trop direct gâche tout le plaisir de la recherche.
Les 3 indices doivent former des cercles concentriques de plus en plus resserrés, avec élégance et subtilité intellectuelle.

RÈGLES D'OR DE SÉCURITÉ ET DE RÉDACTION :
1. INTERDICTION ABSOLUE (LEAK-GUARD) : Ne cite JAMAIS le mot secret, sa racine étymologique, son pluriel, ni aucun mot de sa famille étymologique ou morphologique.
2. PAS D'EXPRESSIONS IDIOMATIQUES RÉVÉLATRICES : Interdiction formelle d'employer des proverbes ou expressions courantes cousues de fil blanc (ex: interdiction d'écrire "perdre le nord" pour une boussole).
3. PAS DE QUASI-SYNONYMES AUX NIVEAUX 1 ET 2 : Interdiction d'utiliser des équivalents directs du mot secret (ex: pour 'château', interdiction de 'palais', 'forteresse', 'manoir' aux niveaux 1 et 2).
4. STYLE ÉNIGMATIQUE : Évite les tics répétitifs ("Il s'agit de...", "Il évoque...", "C'est un..."). Rédige de véritables énigmes stimulantes (15 à 25 mots).
5. Pour chaque niveau :
   - "word" : UN SEUL mot français en minuscules (nom ou adjectif), sans espace ni ponctuation.
   - "phrase" : Une phrase d'énigme rédigée (15 à 25 mots).

GRADUATION STRICTE DES 3 NIVEAUX (MILLIÈMES CROISSANTS OBLIGATOIRES) :
Les 3 indices doivent impérativement avoir une proximité croissante dans l'espace sémantique :
millième(Niveau 1) ~700‰ < millième(Niveau 2) ~825‰ < millième(Niveau 3) ~950‰.

• NIVEAU 1 (weight = 0.33) — ZONE TIÈDE (Cible ~700‰) :
  - Rôle : Ambiance générale, toile de fond thématique ou domaine abstrait.
  - "word" : Un concept ou terme général ciblant environ 700‰.
  - "phrase" : Une énigme d'atmosphère lointaine.

• NIVEAU 2 (weight = 0.66) — ZONE CHAUDE (Cible ~825‰) :
  - Rôle : Vocation pratique, rôle sociétal, usage ou contexte d'action.
  - "word" : Une fonction, un rôle ou un attribut marquant ciblant environ 825‰ (strictement plus chaud que le niveau 1).
  - "phrase" : Décrit une situation d'usage sans décrire l'objet littéralement.

• NIVEAU 3 (weight = 1.00) — ZONE BRÛLANTE (Cible ~950‰) :
  - Rôle : L'étincelle finale. Composant emblématique, analogie saisissante ou propriété distinctive majeure.
  - "word" : Un terme très proche dans l'espace sémantique ciblant environ 950‰ (très chaud sans être synonyme direct ni solution immédiate).
  - "phrase" : Une énigme resserrée et précise qui permet de déclencher l'illumination sans donner une simple définition.

Format JSON STRICT attendu :
{
  "secret_word": "<mot>",
  "hints": [
    {"level": 1, "weight": 0.33, "word": "<mot_concept_environ_700>", "phrase": "<phrase_enigme_lointaine>"},
    {"level": 2, "weight": 0.66, "word": "<mot_usage_environ_825>", "phrase": "<phrase_enigme_usage>"},
    {"level": 3, "weight": 1.00, "word": "<mot_proche_environ_950>", "phrase": "<phrase_enigme_declic>"}
  ]
}"""


def build_user_prompt(secret_word: str) -> str:
    """Construit le prompt utilisateur pour générer les 3 indices gradués."""
    return f"""Génère les 3 indices gradués pour le mot secret français suivant :
MOT_SECRET : "{secret_word}"
Applique strictement les règles de retenue, le style d'énigme et l'absence totale de synonyme en niveaux 1 et 2.

Format JSON attendu :
{{
  "secret_word": "{secret_word}",
  "hints": [
    {{
      "level": 1,
      "weight": 0.33,
      "word": "<mot_concept_abstrait>",
      "phrase": "<phrase_enigme_lointaine>"
    }},
    {{
      "level": 2,
      "weight": 0.66,
      "word": "<mot_fonction_usage>",
      "phrase": "<phrase_enigme_usage>"
    }},
    {{
      "level": 3,
      "weight": 1.00,
      "word": "<mot_proche_declic>",
      "phrase": "<phrase_enigme_declic>"
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
