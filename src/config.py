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
# Mots et tokens anglais parasites à exclure impérativement du vocabulaire Cémantix
# (Mots anglais purs issus de sous-titres, corpus web ou hallucinations LLM,
# ainsi que les graphies anglaises sans accent de mots français : decision, region, etc.)
# ATTENTION : Ne contient STRICTEMENT AUCUN mot français ni anglicisme admis par Cémantix.
# --------------------------------------------------------------------------- #
ENGLISH_WORDS = set("""
about after again against all also always another any around ask baby back bad
be beat beautiful because become before begin behind believe best better between
big black blood blue body book both boy bring brother build business buy
call can cat child children city clear close cold come company could country
create creation dark day dead death decide decision deep develop die different do dog door
down draw early east easy eat economic economy education end enough even evening
ever every expect eye fact fall family far fast father feel few fight fill
find finish first fly follow food friend from full game generation get girl give go
good great ground group grow hair half hand happen hard have head hear
heart heavy help here high history hold home hope horse hot house how
huge human hundred husband idea include industry inside instead
interest into join just keep kill kind king kitchen know land last
late later laugh lead learn leave left let letter level lie life light
like line listen little live lose love low make man many market
marry matter mean measure meet member middle military mind
money month more morning most mother move much music name
near need never new news next night north not nothing now
number officer often oil old once one only operation order other others
our out outside over own party pay people person phone picture
play player political power president price problem produce
product program project provide push put quick quite
raise reach read ready real really reason receive red remain remember
reaction region require research resource response return right rise roll room
rule run same save say school sea season seat security seek seem
selection send sense series serve seven several sex shake share she
should shoulder side sign since sing sister sit
size skill skin small smile society soldier somebody someone something
sometimes song soon sound south space speak special specific spend
spring start state statement stay step
still story strategy street strong student study stuff
subject success successful such suddenly suffer suggest summer sure
system take talk task tax teach teacher team technology television tell ten term
than thank that the their them themselves then theory there these they thing
think third this those though thought thousand through throughout throw thus time
today together tonight too tough toward town trade traditional training
travel treat treatment tree trial trip true truth try turn two under
understand unit until upon usually value various very victim view visit
voice wait walk wall want war watch water weapon wear week weight well west
what whatever when where whether which while white who whole whom whose why wide
wife will win wind window wish with within without woman wonder word work worker
world worry would write writer wrong yard yeah year yes yet young your yourself
shit fuck sorry online download website thread feed definition revolution
evolution preparation
""".split())


# --------------------------------------------------------------------------- #
# Prompt LLM Local
# --------------------------------------------------------------------------- #
PROMPT = """Tu joues à Cémantix : trouver un mot secret français par proximité \
sémantique (modèle word2vec).
RÈGLE STRICTE LINGUISTIQUE : uniquement des mots de la LANGUE FRANÇAISE ! Tout mot anglais \
ou anglicisme non français est formellement interdit.
RÈGLE GRAMMATICALE STRICTE : uniquement des lemmes — nom ou adjectif au MASCULIN SINGULIER, \
verbe à l'INFINITIF. Jamais de pluriel, jamais de féminin, pas de nom propre.
Température de -100 à 100 ; au-delà de ~25°C on est dans le top 1000 (rang ‰, \
1000 = trouvé).

Meilleurs essais réels (mot : température, rang ‰) :
{best}

Mots les plus froids (direction à éviter) : {worst}

Candidats estimés par la recherche vectorielle (les premiers sont les plus \
cohérents avec tous les scores réels) :
{candidates}

Déduis le champ sémantique du mot secret et propose {n} NOUVEAUX mots français, non \
déjà testés, les plus susceptibles d'être le secret. Tu peux reprendre des \
candidats ou proposer tes propres idées en français.
Réponds UNIQUEMENT par un tableau JSON de chaînes, ex: ["mot1", "mot2"]."""


def log(msg: str = "") -> None:
    print(msg, flush=True)


