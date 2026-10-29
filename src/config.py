"""
Cémantix Solver — Configuration & Constantes
=============================================
Centralise l'ensemble des constantes métier, chemins de données,
paramètres d'environnement, styles ANSI et listes de référence.
"""
import collections
import logging
import os
import re
import threading
from pathlib import Path

# --------------------------------------------------------------------------- #
# Styles ANSI & Dimensions console
# --------------------------------------------------------------------------- #
BOLD = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
ANSI_RE = re.compile(r'\033\[[0-9;]*m')

BOARD_WIDTH = 89
COL_WIDTH = 43
DUEL_TOP_WORDS = int(os.getenv("DUEL_TOP_WORDS", "10"))

# --------------------------------------------------------------------------- #
# Chemins & Modèles vectoriels
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "cemantix_data"

LEXIQUE_FILE = DATA_DIR / "lexique_fr.txt"
LEXIQUE_URL = "https://www.lexique.org/databases/Lexique383/Lexique383.zip"

W2V_FILE = os.getenv("W2V_FILE", "frWac_no_postag_phrase_500_cbow_cut10.bin")
W2V_URL = "https://embeddings.net/embeddings/" + W2V_FILE
MAX_VOCAB = int(os.getenv("MAX_VOCAB", "150000"))

CHROMA_DIR = DATA_DIR / "chroma_w2v"
COLLECTION = "frwac_" + re.sub(r"\W", "_", Path(W2V_FILE).stem)[-50:]

# --------------------------------------------------------------------------- #
# Validation de la configuration (QUAL-04)
# --------------------------------------------------------------------------- #
# Valeur livrée dans .env.example : si elle survit jusqu'en exécution, la base est
# accessible avec un mot de passe public. Mieux vaut refuser de démarrer.
DB_PASS_PLACEHOLDER = "cemantix_secure_password_replace_in_prod"


def validate_runtime_config() -> list:
    """Contrôle la configuration nécessaire pour servir ou résoudre.

    Retourne la liste des problèmes détectés. Le mode SQLite (aucun DB_HOST) n'est
    pas concerné : c'est le mode des tests et du développement hors conteneur.
    """
    problems = []
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS", "")

    if db_host:
        if not db_pass:
            problems.append("DB_PASS est vide alors que DB_HOST est configuré")
        elif db_pass == DB_PASS_PLACEHOLDER:
            problems.append(
                "DB_PASS porte encore la valeur d'exemple "
                f"{DB_PASS_PLACEHOLDER!r} (: .env.example)"
            )
        for name in ("DB_NAME", "DB_USER"):
            if not os.getenv(name):
                problems.append(f"{name} est requis quand DB_HOST est configuré")
    return problems


def enforce_runtime_config() -> None:
    """Refuse de démarrer sur une configuration invalide (message actionnable)."""
    problems = validate_runtime_config()
    if problems:
        for problem in problems:
            log(f"❌  [CONFIGURATION] {problem}")
        raise SystemExit(
            "Configuration refusée : corrigez les variables d'environnement ci-dessus."
        )


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
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

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
# Mots et tokens anglais parasites à exclure impérativement du vocabulaire Cémantix (QUAL-09)
# --------------------------------------------------------------------------- #
ENGLISH_WORDS_FILE = Path(__file__).resolve().parent / "engine" / "english_stopwords.txt"

def _load_english_words() -> set[str]:
    if ENGLISH_WORDS_FILE.exists():
        try:
            with open(ENGLISH_WORDS_FILE, "r", encoding="utf-8") as f:
                words = set()
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        words.update(line.split())
                return words
        except Exception:
            pass
    return set()

ENGLISH_WORDS = _load_english_words()


# --------------------------------------------------------------------------- #
# Prompt LLM Local (chargé depuis le template src/engine/prompt_template.txt) (QUAL-09)
# --------------------------------------------------------------------------- #
PROMPT_TEMPLATE_FILE = Path(__file__).resolve().parent / "engine" / "prompt_template.txt"

def _load_prompt_template() -> str:
    if PROMPT_TEMPLATE_FILE.exists():
        try:
            with open(PROMPT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "Tu joues à Cémantix : {best} {worst} {candidates} {n}"

PROMPT = _load_prompt_template()


class _MemoryLogHandler(logging.Handler):
    """Tampon circulaire des derniers messages journalisés (console d'admin).

    L'API d'administration doit pouvoir relire l'activité récente sans accès
    disque : la boucle est bornée pour que sa mémoire reste constante, quel que
    soit le volume de logs produit.
    """

    def __init__(self, capacity: int = 800):
        super().__init__()
        self._lines: "collections.deque[tuple[int, str]]" = collections.deque(maxlen=int(capacity))
        self._seq = 0
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        with self._lock:
            self._seq += 1
            self._lines.append((self._seq, line))

    def tail(self, count: int = 200) -> list:
        with self._lock:
            lines = [l for _s, l in self._lines]
        return lines[-max(1, int(count)):]

    def since(self, last_seq: int) -> tuple[int, list[str]]:
        with self._lock:
            if not self._lines:
                return self._seq, []
            new_lines = [l for s, l in self._lines if s > last_seq]
            return self._seq, new_lines


_MEMORY_LOG_CAPACITY = int(os.getenv("ADMIN_LOG_BUFFER", "800"))

_logger = logging.getLogger("cemantix")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
_MEMORY_HANDLER = _MemoryLogHandler(_MEMORY_LOG_CAPACITY)
_MEMORY_HANDLER.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
if _MEMORY_HANDLER not in _logger.handlers:
    _logger.addHandler(_MEMORY_HANDLER)


def recent_logs(count: int = 200) -> list:
    """Retourne les `count` dernières lignes journalisées par ce processus."""
    return _MEMORY_HANDLER.tail(count)


def logs_since(last_seq: int) -> tuple[int, list[str]]:
    """Retourne les nouvelles lignes depuis le numéro de séquence `last_seq`."""
    return _MEMORY_HANDLER.since(last_seq)


def log(msg: str = "", level=logging.INFO) -> None:
    """Journalise un message avec horodatage et niveau (QUAL-05).

    `level` accepte un entier `logging` ou son nom (`"WARNING"`, `"ERROR"`) :
    l'appel est très répandu sous la forme texte et doit rester sans effet de
    bord si le nom est inconnu (on retombe sur INFO).
    """
    if not msg:
        print("", flush=True)
        return
    if isinstance(level, str):
        level = logging.getLevelName(level.upper())
        if not isinstance(level, int):
            level = logging.INFO
    _logger.log(level, msg)


