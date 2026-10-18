"""
Cémantix Solver — Configuration & Constantes
=============================================
Centralise l'ensemble des constantes métier, chemins de données,
paramètres d'environnement, styles ANSI et listes de référence.
"""
import os
import re
from pathlib import Path

# --------------------------------------------------------------------------- #
# Styles ANSI & Dimensions console
# --------------------------------------------------------------------------- #
BOLD = "\033[34m"
RESET = "\033[0m"
ANSI_RE = re.compile(r'\033\[[0-9;]*m')

BOARD_WIDTH = 89
COL_WIDTH = 43
DUEL_TOP_WORDS = int(os.getenv("DUEL_TOP_WORDS", "10"))

# --------------------------------------------------------------------------- #
# Chemins & Modèles vectoriels
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "cemantix_data"

LEXIQUE_FILE = DATA_DIR / "lexique_fr.txt"
LEXIQUE_URL = "https://www.lexique.org/databases/Lexique383/Lexique383.zip"

W2V_FILE = os.getenv("W2V_FILE", "frWac_no_postag_phrase_500_cbow_cut10.bin")
W2V_URL = "https://embeddings.net/embeddings/" + W2V_FILE
MAX_VOCAB = int(os.getenv("MAX_VOCAB", "150000"))

CHROMA_DIR = DATA_DIR / "chroma_w2v"
COLLECTION = "frwac_" + re.sub(r"\W", "_", Path(W2V_FILE).stem)[-50:]

# --------------------------------------------------------------------------- #
# Endpoints Réseau & API
# --------------------------------------------------------------------------- #
SITE = "https://cemantix.certitudes.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cemantix-rag-tp",
    "Origin": SITE,
    "Referer": SITE + "/",
    "Content-Type": "application/x-www-form-urlencoded",
}

LM_API = os.getenv("LM_API", "http://host.docker.internal:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2")

# --------------------------------------------------------------------------- #
# Données linguistiques & Amorçages
# --------------------------------------------------------------------------- #
WORD_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæ\-]{3,}")

STOPWORDS = set("""
les des une est pas que qui vous nous ils elles elle lui leur mes tes ses mon
ton son notre votre nos vos cet cette ces dans pour par sur avec sans sous mais
donc car plus moins très tout tous toute toutes rien quoi dont quand comme
comment pourquoi alors aussi bien encore déjà être avoir faire aux celui celle
ceux celles moi toi soi ici plusieurs autre autres quelque quelques aucun aucune
certain certains certaines chaque
""".split())

SEED_WORDS = [
    "animal", "nourriture", "maison", "voyage", "guerre", "amour", "science",
    "musique", "argent", "corps", "nature", "politique", "sport", "temps",
    "travail", "famille", "religion", "machine", "couleur", "maladie",
]

# 24 grands pôles pluridisciplinaires de la connaissance
DISCIPLINES = [
    "médecine", "justice", "musique", "astronomie", "géographie",
    "sport", "journalisme", "agriculture", "philosophie", "chimie",
    "cinéma", "banque", "littérature", "informatique", "religion",
    "gastronomie", "politique", "architecture", "histoire", "psychologie",
    "transport", "industrie", "animal", "vêtement"
]

# Graines d'amorçage pour les profils IA du mode duel
SEEDS_FACILE = [
    "animal", "temps", "science", "musique", "justice", "corps",
    "voyage", "nourriture", "nature", "travail", "couleur", "argent"
]
SEEDS_MOYEN = [
    "animal", "temps", "science", "musique", "justice", "corps",
    "voyage", "nourriture", "nature", "travail"
]
SEEDS_EXPERT = [
    "animal", "science", "musique", "justice"
]

# --------------------------------------------------------------------------- #
# Prompt LLM Local
# --------------------------------------------------------------------------- #
PROMPT = """Tu joues à Cémantix : trouver un mot secret français par proximité \
sémantique (modèle word2vec).
RÈGLE STRICTE : uniquement des lemmes — nom ou adjectif au MASCULIN SINGULIER, \
verbe à l'INFINITIF. Jamais de pluriel, jamais de féminin, pas de nom propre.
Température de -100 à 100 ; au-delà de ~25°C on est dans le top 1000 (rang ‰, \
1000 = trouvé).

Meilleurs essais réels (mot : température, rang ‰) :
{best}

Mots les plus froids (direction à éviter) : {worst}

Candidats estimés par la recherche vectorielle (les premiers sont les plus \
cohérents avec tous les scores réels) :
{candidates}

Déduis le champ sémantique du mot secret et propose {n} NOUVEAUX mots, non \
déjà testés, les plus susceptibles d'être le secret. Tu peux reprendre des \
candidats ou proposer tes propres idées.
Réponds UNIQUEMENT par un tableau JSON de chaînes, ex: ["mot1", "mot2"]."""
