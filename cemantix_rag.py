#!/usr/bin/env python3
"""
Cémantix RAG Solver — stratégie B (espace word2vec frWac)
=========================================================
Joue à https://cemantix.certitudes.org/ :

  1. Base de connaissance : vocabulaire + vecteurs word2vec frWac
     (J.-P. Fauconnier, la source citée par le site). frWac est entraîné sur un
     corpus lemmatisé : pas de pluriels ni de féminins, comme les mots acceptés
     par Cémantix. Les vecteurs sont indexés dans ChromaDB.
  2. Retrieval : on estime la direction du mot secret par moindres carrés
     (on cherche q tel que cos(q, essai_i) ≈ score_i), on récupère ses voisins
     + ceux du meilleur essai, puis on RERANK ces candidats selon leur cohérence
     avec TOUS les scores observés.
  3. Generation : le LLM local reçoit les essais et les candidats rerankés et
     propose des mots. Ses propositions sont filtrées contre le vocabulaire
     (= lemmes uniquement, aucun mot refusé par le site).
  4. Feedback : chaque score renvoyé par le site enrichit le tour suivant.

API du site (reverse engineering de cemantix.js) :
  POST /score?n=<puzzle>   body: word=<mot>  (x-www-form-urlencoded)
  -> {"s": cosinus, "p": rang ‰ (si top 1000)}  ou  {"e": "Je ne connais pas..."}
  Température = 100 * s.  p == 1000 => trouvé.

Usage (container agent_ia) :
  python /app/projects/formation_rag/travaux_pratiques/cemantix_rag.py
  python .../cemantix_rag.py --no-llm          # retrieval + rerank seuls
  W2V_FILE=frWac_no_postag_no_phrase_500_cbow_cut100.bin python .../cemantix_rag.py
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import chromadb
import numpy as np
import requests

# --------------------------------------------------------------------------- #
# Configuration & Styles
# --------------------------------------------------------------------------- #
BOLD = "\033[34m"
RESET = "\033[0m"

LM_API = os.getenv("LM_API", "http://host.docker.internal:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2")

# Nombre de meilleurs mots affichés par colonne en mode duel
DUEL_TOP_WORDS = int(os.getenv("DUEL_TOP_WORDS", "10"))

SITE = "https://cemantix.certitudes.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cemantix-rag-tp",
    "Origin": SITE,
    "Referer": SITE + "/",
    "Content-Type": "application/x-www-form-urlencoded",
}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "cemantix_data"
W2V_FILE = os.getenv("W2V_FILE", "frWac_no_postag_phrase_500_cbow_cut10.bin")
W2V_URL = "https://embeddings.net/embeddings/" + W2V_FILE
MAX_VOCAB = int(os.getenv("MAX_VOCAB", "150000"))  # mots les plus fréquents
CHROMA_DIR = DATA_DIR / "chroma_w2v"
COLLECTION = "frwac_" + re.sub(r"\W", "_", Path(W2V_FILE).stem)[-50:]

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

LEXIQUE_FILE = DATA_DIR / "lexique_fr.txt"
LEXIQUE_URL = "https://www.lexique.org/databases/Lexique383/Lexique383.zip"


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def ensure_lexique() -> Path:
    if LEXIQUE_FILE.exists() and LEXIQUE_FILE.stat().st_size > 100000:
        return LEXIQUE_FILE
    log("⬇  Téléchargement et extraction du dictionnaire Lexique 3.83...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import zipfile, io, csv
        r = requests.get(LEXIQUE_URL, timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open("Lexique383.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="ignore"), delimiter="\t")
            lemmes = set()
            for row in reader:
                cg = row.get("cgram", "")
                if cg in ("NOM", "ADJ", "VER", "ADV", "AUX") or cg.startswith("ADJ:") or cg.startswith("PRO:"):
                    w = row.get("lemme", "").strip().lower()
                    if len(w) >= 3 and re.fullmatch(r"[a-zàâäçéèêëîïôöùûüÿœæ\-]+", w):
                        lemmes.add(w)
            LEXIQUE_FILE.write_text("\n".join(sorted(lemmes)), encoding="utf-8")
            log(f"✓  {len(lemmes)} lemmes officiels enregistrés dans {LEXIQUE_FILE.name}")
    except Exception as e:
        log(f"⚠  Impossible de télécharger Lexique 3.83 : {e}")
    return LEXIQUE_FILE


def load_lexique() -> tuple[set[str], dict[str, str]]:
    path = ensure_lexique()
    if not path.exists():
        return set(), {}
    words = set(path.read_text(encoding="utf-8").splitlines())
    accent_map = {}
    for w in words:
        s = strip_accents(w)
        if s != w and s not in accent_map:
            accent_map[s] = w
    return words, accent_map


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# Couche 1 : client du jeu
# --------------------------------------------------------------------------- #
class CemantixClient:
    def __init__(self, delay: float = 0.25):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": HEADERS["User-Agent"]})
        self.delay = delay
        log(f"🌐  Connexion à {SITE}...")
        html = self.s.get(SITE + "/", timeout=15).text
        m = re.search(r'data-puzzle-number="(\d+)"', html)
        if not m:
            raise RuntimeError("Numéro du puzzle introuvable dans la page.")
        self.puzzle = int(m.group(1))
        log(f"✓  Puzzle du jour détecté : n°{self.puzzle}")

    def score(self, word: str):
        """(cosinus, permille|None), ou None si le site ne connaît pas le mot."""
        for attempt in range(3):
            try:
                r = self.s.post(f"{SITE}/score?n={self.puzzle}",
                                data={"word": word}, headers=HEADERS, timeout=15)
                time.sleep(self.delay)
                data = r.json()
                if "e" in data:
                    return None
                return float(data["s"]), data.get("p")
            except (requests.RequestException, ValueError):
                time.sleep(1 + attempt)
        return None


class MockClient:
    """Client simulé local : tire un mot secret aléatoire dans le dictionnaire officiel
    et calcule les scores réels (produits scalaires) et rangs permille à la volée en 0.05ms."""
    def __init__(self, store, secret: str = None):
        self.store = store
        if secret:
            secret_norm = self.store.normalize(secret)
            if secret_norm in store:
                self.secret = secret_norm
            else:
                raise ValueError(f"Le mot secret '{secret}' n'est pas dans la base vectorielle.")
        else:
            # Tirage au sort totalement impartial parmi les vrais lemmes français du vector store
            pool = store.clean_french_words if store.clean_french_words else store.words
            cands = [w for w in pool if len(w) >= 4 and w not in STOPWORDS
                     and not w.endswith(('es', 'eaux', 'eux', 'aux'))
                     and not (w.endswith('s') and not w.endswith(('is', 'us', 'as', 'ps', 'os')))]
            self.secret = str(np.random.choice(cands))
        
        self.puzzle = f"MOCK-{self.secret.upper()}"
        self.v_secret = store.vec(self.secret)
        # Précalcul du seuil top 1000 pour les rangs permille exacts
        all_cos = self.store.vecs @ self.v_secret
        self.p1000_threshold = float(np.partition(all_cos, -1000)[-1000])
        self.top_scores = np.sort(all_cos[all_cos >= self.p1000_threshold])
        log(f"🎲  [MOCK] Nouveau mot secret tiré au sort (dissimulé) | Seuil top 1000 : {self.p1000_threshold * 100:.2f}°C")

    def score(self, word: str):
        # Cémantix rejette tout mot absent du vector store ou non conforme au dictionnaire français
        if word not in self.store or not self.store.is_valid_french(word):
            return None
        s = float(self.store.vec(word) @ self.v_secret)
        if word == self.secret:
            return 1.0, 1000
        p = None
        if s >= self.p1000_threshold:
            rank = int(np.searchsorted(self.top_scores, s))
            p = min(999, max(1, rank))
        return s, p


# --------------------------------------------------------------------------- #
# Couche 2 : base de connaissance word2vec -> ChromaDB
# --------------------------------------------------------------------------- #
def download_w2v(path: Path) -> None:
    log(f"⬇  Téléchargement de {W2V_FILE} (une seule fois)...")
    tmp = path.with_suffix(".part")
    offset = tmp.stat().st_size if tmp.exists() else 0
    headers = {**HEADERS, "Range": f"bytes={offset}-"} if offset else HEADERS
    
    with requests.get(W2V_URL, headers=headers, stream=True, timeout=60) as r:
        if r.status_code == 416:  # Fichier déjà complet
            tmp.rename(path); return
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        total = int(r.headers.get("content-length", 0)) + (offset if mode == "ab" else 0)
        done = offset if mode == "ab" else 0
        with open(tmp, mode) as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
                done += len(chunk)
                if total and done % (200 << 20) < (1 << 22):
                    log(f"   {done >> 20}/{total >> 20} Mo")
    tmp.rename(path)


def load_w2v():
    """Lit le binaire word2vec (trié par fréquence) et garde les MAX_VOCAB
    premiers lemmes simples (pas d'expressions 'a_b', pas de mots-outils)."""
    path = DATA_DIR / W2V_FILE
    cache_npy = DATA_DIR / f"{path.stem}_{MAX_VOCAB}_vecs.npy"
    cache_words = DATA_DIR / f"{path.stem}_{MAX_VOCAB}_words.txt"
    cache_npz = DATA_DIR / f"{path.stem}_{MAX_VOCAB}.npz"
    
    # Format ultra-rapide (mmap mémoire : ~0.05 seconde)
    if cache_npy.exists() and cache_words.exists():
        log(f"📦  Chargement rapide des {MAX_VOCAB} lemmes (mmap instantané)...")
        words = cache_words.read_text(encoding="utf-8").splitlines()
        vecs = np.load(cache_npy, mmap_mode="r")
        return words, vecs

    if cache_npz.exists():
        log(f"📦  Décompression du cache vectoriel ({MAX_VOCAB} lemmes)...")
        z = np.load(cache_npz)
        words, vecs = list(z["words"]), z["vecs"]
        # Conversion au format mmap rapide pour les prochains démarrages
        np.save(cache_npy, vecs)
        cache_words.write_text("\n".join(words), encoding="utf-8")
        return words, vecs

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        download_w2v(path)
    log("⏳  Lecture du modèle binaire word2vec...")
    words, vecs = [], []
    with open(path, "rb") as f:
        n, dim = map(int, f.readline().split())
        size = 4 * dim
        for _ in range(n):
            raw = bytearray()
            while (c := f.read(1)) != b" ":
                if c != b"\n":
                    raw += c
            v = f.read(size)
            w = raw.decode("utf-8", "ignore")
            if WORD_RE.fullmatch(w) and w not in STOPWORDS:
                words.append(w)
                vecs.append(np.frombuffer(v, dtype=np.float32))
                if len(words) >= MAX_VOCAB:
                    break
    vecs = np.vstack(vecs)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    np.save(cache_npy, vecs)
    cache_words.write_text("\n".join(words), encoding="utf-8")
    log(f"   {len(words)} lemmes retenus sur {n} ({dim} dimensions)")
    return words, vecs


class VocabStore:
    def __init__(self):
        words, vecs = load_w2v()
        self.words = words
        self.index = {w: i for i, w in enumerate(words)}
        self.vecs = vecs
        self.valid_lemmas, self.accent_map = load_lexique()
        self.clean_french_words = [w for w in self.words if w in self.valid_lemmas]
        if self.valid_lemmas:
            log(f"📖  Dictionnaire officiel français : {len(self.valid_lemmas)} lemmes ({len(self.clean_french_words)} dans frWac)")
        log("⚡  Connexion à la base vectorielle ChromaDB...")
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.col = client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"})
        if self.col.count() < len(words):
            self._ingest(words, vecs)
        log(f"📚  Vector store prêt : {self.col.count()} lemmes ({W2V_FILE})")

    def normalize(self, word: str) -> str:
        """Restaure la casse canonique et les accents manquants d'après le dictionnaire officiel."""
        w = word.strip().lower()
        if w in self.valid_lemmas:
            return w
        s = strip_accents(w)
        if s in self.accent_map:
            return self.accent_map[s]
        return w

    def is_valid_french(self, word: str) -> bool:
        """Vérifie qu'un mot est un lemme français officiel sous son orthographe exacte (avec accents) et présent dans l'espace vectoriel."""
        return (word in self.valid_lemmas or not self.valid_lemmas) and (word in self.index)

    def _ingest(self, words, vecs, batch: int = 5000) -> None:
        log(f"⏳  Indexation ChromaDB de {len(words)} lemmes (une seule fois)...")
        t0 = time.time()
        for i in range(0, len(words), batch):
            self.col.upsert(ids=words[i:i + batch],
                            embeddings=vecs[i:i + batch].tolist())
            log(f"   {min(i + batch, len(words))}/{len(words)} ({time.time() - t0:.0f}s)")

    def __contains__(self, word: str) -> bool:
        return word in self.index

    def vec(self, word: str) -> np.ndarray:
        return self.vecs[self.index[word]]

    def knn(self, query: np.ndarray, k: int) -> list:
        res = self.col.query(query_embeddings=[query.tolist()], n_results=k)
        return res["ids"][0]


# --------------------------------------------------------------------------- #
# Couche 3 : retrieval + rerank
# --------------------------------------------------------------------------- #
def estimate_secret(G: np.ndarray, s: np.ndarray, lam: float = 0.1) -> np.ndarray:
    """Ridge : q = Gᵀ (G Gᵀ + λI)⁻¹ s  -> direction telle que G q ≈ s."""
    q = G.T @ np.linalg.solve(G @ G.T + lam * np.eye(len(s)), s)
    return q / np.linalg.norm(q)


def rerank(store: VocabStore, cands: list, G: np.ndarray, s: np.ndarray, q_est: np.ndarray):
    """Erreur quadratique entre cos(candidat, essai_i) et le score observé s_i,
    pondérée vers les essais chauds (là où l'information est la plus fiable)."""
    if not cands:
        return []
    C = np.vstack([store.vec(w) for w in cands])
    weights = np.exp((s - s.max()) / 0.1)
    err = (((C @ G.T) - s) ** 2 * weights).sum(axis=1) / weights.sum()
    pred_temp = (C @ q_est) * 100.0
    order = np.argsort(err)
    return [(cands[i], float(pred_temp[i]), float(err[i])) for i in order]


# --------------------------------------------------------------------------- #
# Couche 4 : génération (LLM local)
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


def ask_llm(best, worst, candidates_info, n: int, verbose: bool = False) -> list:
    fmt_guess = lambda g: f"- {g[0]} : {g[1] * 100:.2f}°C" + (f", {g[2]}‰" if g[2] else "")
    fmt_cand = lambda c: f"- {c[0]} (temp. estimée : {c[1]:+.2f}°C)"
    cands_str = "\n".join(fmt_cand(c) for c in candidates_info[:25])
    prompt = PROMPT.format(best="\n".join(map(fmt_guess, best)),
                           worst=", ".join(g[0] for g in worst) or "-",
                           candidates=cands_str or "-", n=n)
    if verbose:
        log("\n  🔍  [VERBOSE CANDIDATS RAG INJECTÉS DANS LE PROMPT (Top 15)]")
        for rank, (w, temp, err) in enumerate(candidates_info[:15], 1):
            log(f"      {rank:>2}. {w:<20} est. ≈ {temp:+6.2f}°C    (cohérence err = {err:.4f})")
        log("")
    try:
        r = requests.post(f"{LM_API}/chat/completions", json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7, "max_tokens": 3000,
        }, timeout=300)
        msg = r.json()["choices"][0]["message"]
        reasoning = msg.get("reasoning_content") or ""
        content = msg.get("content") or ""
        if verbose and reasoning:
            log("\n  🔍  [VERBOSE LLM REASONING]")
            non_empty_lines = [l.strip() for l in reasoning.strip().splitlines() if l.strip()]
            for line in non_empty_lines[:8]:
                log(f"     | {line}")
            if len(non_empty_lines) > 8:
                log("     | ... (suite du raisonnement masquée)")
        text = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
        arrays = re.findall(r"\[[^\[\]]*\]", text)
        words = [str(w).strip().lower() for w in json.loads(arrays[-1])] if arrays else []
        if verbose:
            log(f"  🔍  [VERBOSE LLM OUTPUT BRUT] : {words}")
        return words
    except Exception as exc:
        log(f"   ⚠  LLM : {exc}")
        return []


# --------------------------------------------------------------------------- #
# Boucle de jeu
# --------------------------------------------------------------------------- #
class Solver:
    def __init__(self, args, store=None, game=None):
        self.args = args
        self.store = store if store else VocabStore()
        if game:
            self.game = game
        elif getattr(args, "mock", False) or getattr(args, "benchmark", 0) > 0:
            self.game = MockClient(self.store, secret=getattr(args, "secret", None))
        else:
            self.game = CemantixClient(delay=args.delay)
        self.guesses = {}   # mot -> (cosinus, permille)
        self.tried = set()
        self.win_source = None

    def play_word(self, word: str, source: str) -> bool:
        norm = self.store.normalize(word)
        if norm != word:
            if self.args.verbose:
                log(f"        [ACCENT RESTAURÉ] « {word} » ➔ « {norm} »")
            word = norm

        if word in self.tried:
            return False
        self.tried.add(word)

        if not self.store.is_valid_french(word):
            log(f"        {source:<4} {word:<20} (inconnu du site)")
            return False

        res = self.game.score(word)
        if res is None:
            log(f"        {source:<4} {word:<20} (inconnu du site)")
            return False
        s, p = res
        
        # Échelle officielle Cémantix
        if p == 1000:
            weather = "🥳 "
        elif p and p >= 999:
            weather = "😱 "
        elif p and p >= 990:
            weather = "🔥 "
        elif p and p >= 900:
            weather = "🥵 "
        elif p and p >= 1:
            weather = "😎 "
        elif s >= 0:
            weather = "🥶 "
        else:
            weather = "🧊 "

        best = max([v[0] for v in self.guesses.values()], default=-1)
        is_new_hot_record = (s > best) and (s > 0.15)
        self.guesses[word] = (s, p)
        rank = f"{p:>4}‰" if p else "     "
        flag = "  ⭐" if is_new_hot_record else "    "
        log(f"  [{len(self.guesses):>3}] {source:<4} {word:<20} {s * 100:7.2f}°C  {weather}  {rank}{flag}")
        if p == 1000:
            self.win_source = source
            return True
        return False

    def ranked(self):
        return sorted(((w, s, p) for w, (s, p) in self.guesses.items()),
                      key=lambda g: g[1], reverse=True)

    def generate_optimal_seeds(self, count: int = 16) -> list:
        """Génération pluridisciplinaire par RAG : interroge ChromaDB pour extraire
        dynamiquement les lemmes représentatifs des grands domaines de la connaissance."""
        if count <= 0:
            return []
        disciplines = list(DISCIPLINES)
        np.random.shuffle(disciplines)
        selected = disciplines[:min(count, len(disciplines))]

        seeds = []
        for d in selected:
            d_norm = self.store.normalize(d)
            if d_norm in self.store and self.store.is_valid_french(d_norm):
                vec = self.store.vec(d_norm)
                neighbors = self.store.knn(vec, k=30)
                cands = [d_norm]
                for raw_w in neighbors:
                    w = self.store.normalize(raw_w)
                    if (self.store.is_valid_french(w)
                            and len(w) >= 4 and w not in STOPWORDS
                            and not w.endswith(('es', 'eaux', 'eux', 'aux'))
                            and not (w.endswith('s') and not w.endswith(('is', 'us', 'as', 'ps', 'os')))
                            and w not in cands):
                        cands.append(w)
                top_pool = cands[:6]
                chosen = str(np.random.choice(top_pool))
                if chosen not in seeds:
                    seeds.append(chosen)
        return seeds

    def get_seeds(self, forced_seeds: list = None) -> list:
        if forced_seeds is not None:
            return forced_seeds
        if self.args.seeds:
            seeds = [w.strip().lower() for w in self.args.seeds.split(",") if w.strip()]
        elif self.args.seeds_file:
            path = Path(self.args.seeds_file)
            if path.exists():
                seeds = [w.strip().lower() for w in path.read_text(encoding="utf-8").splitlines() if w.strip()]
            else:
                log(f"   ⚠  Fichier graines {path} introuvable, génération pluridisciplinaire RAG.")
                count = self.args.seed_count if self.args.seed_count is not None else 16
                return self.generate_optimal_seeds(count)
        elif self.args.static_seeds:
            seeds = SEED_WORDS
        else:
            count = self.args.seed_count if self.args.seed_count is not None else 16
            return self.generate_optimal_seeds(count)

        if self.args.seed_count is not None:
            return seeds[:max(0, self.args.seed_count)]
        return seeds

    def retrieve(self, ranked, verbose: bool = None) -> list:
        if verbose is None:
            verbose = self.args.verbose
        known = [g for g in ranked if g[0] in self.store]
        G = np.vstack([self.store.vec(g[0]) for g in known])
        s = np.array([g[1] for g in known], dtype=np.float32)
        q_est = estimate_secret(G, s)
        k = self.args.retrieve
        fetch_k = max(k * 3, 100)
        raw_pool = self.store.knn(q_est, fetch_k)
        for w, _, _ in known[:3]:  # voisins des 3 meilleurs essais
            raw_pool += self.store.knn(self.store.vec(w), fetch_k // 2)
        
        # Normalisation canonique stricte : élimine tout doublon sans accent ou token web parasite
        pool = []
        for raw_w in raw_pool:
            w = self.store.normalize(raw_w)
            if w not in self.tried and w not in pool and self.store.is_valid_french(w):
                pool.append(w)
                if len(pool) >= k:
                    break

        reranked = rerank(self.store, pool, G, s, q_est)
        if verbose:
            log("\n  🔍  [VERBOSE RAG RETRIEVAL]")
            log(f"      ├── Contraintes Ridge     : {len(known)} mots connus utilisés")
            log(f"      ├── Voisins ChromaDB      : {len(pool)} candidats filtrés et normalisés")
            log(f"      └── Top {min(8, len(reranked))} après Reranking :")
            for rank, (w, temp, e) in enumerate(reranked[:8], 1):
                log(f"          {rank:>2}. {w:<20} est. ≈ {temp:+6.2f}°C    (err = {e:.4f})")
            log("")
        return reranked

    def run(self, forced_seeds: list = None) -> dict:
        t0 = time.time()
        is_rag_only = getattr(self.args, "rag_only", False)
        log(f"🎯  Cémantix — puzzle n°{self.game.puzzle}")
        mode_desc = "⚡ 100% RAG Pur Mathématique (Ridge + Rerank — Zéro LLM)" if is_rag_only else f"🤖 Hybride RAG + Local LLM ({LLM_MODEL})"
        log(f"⚙   Mode : {mode_desc}")
        seeds = self.get_seeds(forced_seeds)
        log(f"── Amorçage ({len(seeds)} mots graines)\n")
        
        for i, w in enumerate(seeds, 1):
            if self.play_word(w, "seed"):
                return self.win(w, time.time() - t0)

            # Détection anticipée (Sniper) : dès 4 graines valides enregistrées
            valid_seeds = len(self.guesses)
            if valid_seeds >= 4 and i < len(seeds):
                cands_quick = self.retrieve(self.ranked(), verbose=False)
                if cands_quick:
                    top_cand, _, top_err = cands_quick[0]
                    if top_err < 0.00005 and top_cand not in self.tried:
                        log(f"\n⚡  [SNIPER RAG] Certitude mathématique après {valid_seeds} graines : « {top_cand} » (err = {top_err:.5f})")
                        if self.play_word(top_cand, "rag"):
                            return self.win(top_cand, time.time() - t0)

        round_no = 0
        rag_k = self.args.rag_words if (self.args.rag_words != 3 or not is_rag_only) else 5
        while len(self.guesses) < self.args.max_tries:
            round_no += 1
            ranked = self.ranked()
            log(f"\n{'═' * 60}")
            log(f"── Tour {round_no} | Meilleur : {ranked[0][0]} ({ranked[0][1] * 100:.2f}°C)")
            log(f"{'═' * 60}")

            candidates_info = self.retrieve(ranked)
            cand_words = [c[0] for c in candidates_info]

            # Fast-path : si le candidat RAG n°1 est mathématiquement certain, on le teste immédiatement sans appeler le LLM
            if candidates_info and candidates_info[0][2] < 0.00005 and cand_words[0] not in self.tried:
                top_cand, _, top_err = candidates_info[0]
                if self.args.verbose:
                    log(f"⚡  [FAST-PATH RAG] Candidat certain « {top_cand} » (err={top_err:.5f}), tir direct sans attente LLM...")
                if self.play_word(top_cand, "rag"):
                    return self.win(top_cand, time.time() - t0)

            if is_rag_only:
                batch = [(w, "rag") for w in cand_words[:rag_k]]
                if self.args.verbose:
                    log(f"  🔍  [VERBOSE BATCH RAG PUR ({len(batch)})] : {', '.join(w for w, _ in batch)}\n")
            else:
                llm_words = ask_llm(
                    ranked[:15], ranked[-5:], candidates_info[:30], self.args.llm_words,
                    verbose=self.args.verbose)
                
                normalized_llm = []
                for raw_w in llm_words:
                    w = self.store.normalize(raw_w)
                    if w not in normalized_llm and w not in self.tried:
                        normalized_llm.append(w)

                valid_llm = [w for w in normalized_llm if self.store.is_valid_french(w)]
                rejected = [w for w in normalized_llm if not self.store.is_valid_french(w)]
                
                if self.args.verbose and llm_words:
                    log("\n  🔍  [VERBOSE LLM SYNTHÈSE]")
                    log(f"      ├── Mots proposés  : {', '.join(llm_words)}")
                    if rejected:
                        log(f"      ├── Mots filtrés   : {', '.join(rejected)} (hors dictionnaire officiel)")
                    log(f"      └── Mots retenus   : {', '.join(valid_llm) if valid_llm else 'aucun'}\n")
                elif rejected:
                    log(f"        llm  filtrés (hors dictionnaire officiel) : {', '.join(rejected)}")

                batch = [(w, "rag") for w in cand_words[:self.args.rag_words]]
                batch += [(w, "llm") for w in valid_llm]
                
                if self.args.verbose:
                    rag_list = [w for w, src in batch if src == "rag"]
                    llm_list = [w for w, src in batch if src == "llm"]
                    log("  🔍  [VERBOSE BATCH DU TOUR]")
                    if rag_list:
                        log(f"      ├── RAG ({len(rag_list)}) : {', '.join(rag_list)}")
                    if llm_list:
                        log(f"      └── LLM ({len(llm_list)}) : {', '.join(llm_list)}")
                    log("")

            if not batch:
                log("Plus de candidats.")
                break
            for w, src in batch:
                if self.play_word(w, src):
                    return self.win(w, time.time() - t0)

        secret_name = getattr(self.game, "secret", "inconnu")
        elapsed = time.time() - t0
        log(f"\n❌  Non trouvé après {len(self.guesses)} essais (mot secret : {secret_name}). Top 10 :")
        for w, s, p in self.ranked()[:10]:
            log(f"   {w:<20} {s * 100:6.2f}°C {p or ''}")
        return {
            "word": secret_name,
            "tries": len(self.guesses),
            "attempts": len(self.tried),
            "source": None,
            "win": False,
            "time": elapsed,
        }

    def win(self, word: str, elapsed: float = 0.0) -> dict:
        time_str = f" en {elapsed:.2f}s" if elapsed > 0 else ""
        log(f"\n🥳  Mot trouvé : « {word.upper()} » en {len(self.guesses)} essais "
            f"({len(self.tried)} tentatives) [par {self.win_source}]{time_str}.")
        return {
            "word": word,
            "tries": len(self.guesses),
            "attempts": len(self.tried),
            "source": self.win_source,
            "win": True,
            "time": elapsed,
        }


def run_benchmark(args, n_games: int):
    is_rag_only = getattr(args, "rag_only", False)
    mode_label = "⚡ 100% RAG Mathématique pur (Ridge + Rerank — Zéro LLM)" if is_rag_only else f"🤖 Hybride RAG + Local LLM ({LLM_MODEL})"
    log("=" * 65)
    log(f"🏆  LANCEMENT DU BENCHMARK AUTONOME ({n_games} parties simulées)")
    log(f"⚙   Mode : {mode_label}")
    log("=" * 65)
    store = VocabStore()
    results = []
    
    for game_idx in range(1, n_games + 1):
        log(f"\n{'#' * 65}")
        log(f"🎮  PARTIE {game_idx} / {n_games}")
        log(f"{'#' * 65}")
        solver = Solver(args, store=store, game=MockClient(store, secret=args.secret))
        res = solver.run()
        results.append(res)
    
    # Rapport statistique final
    log("\n" + "=" * 65)
    log("📊  RAPPORT DE BENCHMARK FINAL")
    log("=" * 65)
    wins = [r for r in results if r["win"]]
    tries_list = [r["tries"] for r in wins]
    sources = [r["source"] for r in wins]
    
    log(f"  Mode                 : {mode_label}")
    log(f"  Parties jouées       : {len(results)}")
    log(f"  Taux de victoire     : {len(wins)} / {len(results)} ({len(wins)/len(results)*100:.1f}%)")
    if tries_list:
        log(f"  Essais moyen         : {np.mean(tries_list):.1f}")
        log(f"  Essais médian        : {np.median(tries_list):.0f}")
        log(f"  Essais min / max     : {np.min(tries_list)} / {np.max(tries_list)}")
        sniper_wins = sum(1 for s in sources if s == "rag")
        llm_wins = sum(1 for s in sources if s == "llm")
        seed_wins = sum(1 for s in sources if s == "seed")
        log(f"  Victoires RAG/Sniper : {sniper_wins} ({sniper_wins/len(wins)*100:.1f}%)")
        log(f"  Victoires LLM        : {llm_wins} ({llm_wins/len(wins)*100:.1f}%)")
        if seed_wins:
            log(f"  Victoires direct Seed: {seed_wins}")
    log("\nDétail par partie :")
    for idx, r in enumerate(results, 1):
        status = "✓" if r["win"] else "✗"
        log(f"  Partie {idx:>2} : {status} {r['word']:<18} en {r['tries']:>2} essais  (source: {r['source']})")
    log("=" * 65 + "\n")


def run_battle(args, n_rounds: int):
    import copy
    if getattr(args, "rag_only", False):
        log("ℹ️   [INFO] L'option --rag-only est ignorée en mode Battle : le duel oppose par définition 100% RAG Pur vs Hybride LLM.")
    store = VocabStore()

    # Détermination de la liste des mots secrets
    if getattr(args, "secrets", ""):
        raw_list = [store.normalize(w.strip()) for w in args.secrets.split(",") if w.strip()]
        words_list = [w for w in raw_list if w in store and store.is_valid_french(w)]
        if not words_list:
            raise ValueError(f"Aucun mot secret valide trouvé dans l'option --secrets : '{args.secrets}'.")
        is_mock = True
    elif getattr(args, "words", 1) > 1:
        n_words = args.words
        pool = store.clean_french_words if store.clean_french_words else store.words
        cands = [w for w in pool if len(w) >= 4 and w not in STOPWORDS
                 and not w.endswith(('es', 'eaux', 'eux', 'aux'))
                 and not (w.endswith('s') and not w.endswith(('is', 'us', 'as', 'ps', 'os')))]
        words_list = list(np.random.choice(cands, size=min(n_words, len(cands)), replace=False))
        is_mock = True
    elif getattr(args, "secret", None):
        secret_norm = store.normalize(args.secret)
        if secret_norm not in store or not store.is_valid_french(secret_norm):
            raise ValueError(f"Le mot secret imposé '{args.secret}' est introuvable ou non conforme.")
        words_list = [secret_norm]
        is_mock = True
    elif getattr(args, "mock", False):
        ref_mock = MockClient(store)
        words_list = [ref_mock.secret]
        is_mock = True
    else:
        # Mode LIVE par défaut : 1 seul mot (le puzzle officiel du jour)
        words_list = [None]
        is_mock = False

    total_words = len(words_list)
    total_matches = total_words * n_rounds

    log("=" * 70)
    log("⚔️   GRAND TOURNOI BATTLE : 100% RAG PUR  vs  HYBRIDE RAG + LLM")
    mode_txt = "MOCK LOCAL" if is_mock else "LIVE CÉMANTIX"
    log(f"⚔️   Mode : {mode_txt} | {total_words} mot(s) secret(s) × {n_rounds} round(s) = {total_matches} duel(s)")
    log("=" * 70)

    tournament_words_summary = []
    all_battle_results = []

    for word_idx, secret in enumerate(words_list, 1):
        word_display = secret.upper() if secret else "PUZZLE DU JOUR"
        if total_words > 1:
            log("\n" + "╔" + "═" * 68 + "╗")
            log(f"║ 🎯  MOT SECRET {word_idx:>2}/{total_words} : {word_display:<48} ║")
            log("╚" + "═" * 68 + "╝")
        elif is_mock:
            mock_desc = f"« {secret.upper()} »" if args.secret or args.secrets else "« ... » (tiré au sort pour le tournoi)"
            log(f"🎲  Mode : MOCK LOCAL | Mot secret fixé pour les {n_rounds} manche(s) : {mock_desc}")
        else:
            log(f"🌐  Mode : LIVE CÉMANTIX | Affrontement sur le mot du jour officiel ({n_rounds} manche(s))")

        # Pré-génération des graines communes pour les n_rounds de ce mot
        rounds_seeds = []
        dummy_game = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
        for k in range(1, n_rounds + 1):
            seeds_k = Solver(args, store=store, game=dummy_game).get_seeds()
            rounds_seeds.append(seeds_k)

        # =====================================================================
        # PHASE 1 : SÉRIE DU COMBATTANT A — ⚡ 100% RAG Pur (Manches 1 à N)
        # =====================================================================
        log("\n" + "█" * 70)
        log(f"⚡  PHASE 1 : SÉRIE COMBATTANT A — 100% RAG Pur ({n_rounds} manche(s))")
        log("█" * 70)
        results_a = []
        args_rag = copy.deepcopy(args)
        args_rag.rag_only = True
        args_rag.no_llm = True

        for round_idx in range(1, n_rounds + 1):
            log("\n" + "─" * 60)
            log(f"🥊  [100% RAG PUR] MANCHE {round_idx} / {n_rounds} (Mot {word_idx}/{total_words})")
            log("─" * 60)
            seeds_k = rounds_seeds[round_idx - 1]
            log(f"🌱  Graines communes ({len(seeds_k)} mots) : {', '.join(seeds_k[:6])}...")
            game_a = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
            solver_a = Solver(args_rag, store=store, game=game_a)
            res_a = solver_a.run(forced_seeds=list(seeds_k))
            results_a.append(res_a)

        # =====================================================================
        # PHASE 2 : SÉRIE DU COMBATTANT B — 🤖 Hybride RAG + LLM (Manches 1 à N)
        # =====================================================================
        log("\n" + "█" * 70)
        log(f"🤖  PHASE 2 : SÉRIE COMBATTANT B — Hybride RAG + LLM ({LLM_MODEL}) ({n_rounds} manche(s))")
        log("█" * 70)
        results_b = []
        args_hyb = copy.deepcopy(args)
        args_hyb.rag_only = False
        args_hyb.no_llm = False

        for round_idx in range(1, n_rounds + 1):
            log("\n" + "─" * 60)
            log(f"🥊  [HYBRIDE LLM] MANCHE {round_idx} / {n_rounds} (Mot {word_idx}/{total_words})")
            log("─" * 60)
            seeds_k = rounds_seeds[round_idx - 1]
            log(f"🌱  Graines communes ({len(seeds_k)} mots) : {', '.join(seeds_k[:6])}...")
            game_b = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
            solver_b = Solver(args_hyb, store=store, game=game_b)
            res_b = solver_b.run(forced_seeds=list(seeds_k))
            results_b.append(res_b)

        # =====================================================================
        # PHASE 3 : ARBITRAGE DU MOT
        # =====================================================================
        if total_words == 1:
            log("\n" + "█" * 70)
            log(f"⚖️   PHASE 3 : RÉSULTATS COMPARATIFS DES {n_rounds} MANCHE(S)")
            log("█" * 70)

        word_secret = results_a[0]["word"] or results_b[0]["word"] or (secret or "SECRET")
        word_wins_a = 0
        word_wins_b = 0
        word_draws = 0
        word_tries_a = []
        word_tries_b = []
        word_time_a = []
        word_time_b = []

        for round_idx in range(1, n_rounds + 1):
            res_a = results_a[round_idx - 1]
            res_b = results_b[round_idx - 1]

            tries_a = res_a["tries"]
            tries_b = res_b["tries"]
            win_a = res_a["win"]
            win_b = res_b["win"]
            time_a = res_a["time"]
            time_b = res_b["time"]

            if win_a: word_tries_a.append(tries_a)
            if win_b: word_tries_b.append(tries_b)
            word_time_a.append(time_a)
            word_time_b.append(time_b)

            if win_a and not win_b:
                winner = "⚡ RAG Pur"
                lead = "Victoire par K.O. (Hybride échoué)"
                word_wins_a += 1
            elif win_b and not win_a:
                winner = "🤖 Hybride LLM"
                lead = "Victoire par K.O. (RAG échoué)"
                word_wins_b += 1
            elif not win_a and not win_b:
                winner = "❌ Aucun"
                lead = "Double échec"
                word_draws += 1
            elif tries_a < tries_b:
                winner = "⚡ RAG Pur"
                diff = tries_b - tries_a
                speedup = time_b / max(time_a, 0.001)
                speedup_txt = f" ({speedup:.1f}x plus rapide)" if speedup >= 1.2 else ""
                lead = f"+{diff} essai(s) d'avance{speedup_txt}"
                word_wins_a += 1
            elif tries_b < tries_a:
                winner = "🤖 Hybride LLM"
                diff = tries_a - tries_b
                lead = f"+{diff} essai(s) d'avance"
                word_wins_b += 1
            else:
                winner = "🤝 Égalité"
                if time_b > time_a * 1.5:
                    lead = f"Même nombre d'essais ({tries_a}), RAG {time_b/max(time_a, 0.001):.1f}x plus rapide"
                else:
                    lead = f"Même nombre d'essais ({tries_a})"
                word_draws += 1

            if total_words == 1:
                log("\n" + "━" * 60)
                log(f"🏁  MANCHE {round_idx} / {n_rounds} (Mot secret : « {word_secret.upper()} »)")
                log(f"    ⚡ 100% RAG Pur  : {tries_a:>3} essais  ({time_a:6.2f}s)  {'✓' if win_a else '✗'}")
                log(f"    🤖 Hybride LLM   : {tries_b:>3} essais  ({time_b:6.2f}s)  {'✓' if win_b else '✗'}")
                log(f"    🏆 VAINQUEUR     : {winner} — {lead}")
                log("━" * 60)

            all_battle_results.append({
                "word_idx": word_idx,
                "round": round_idx,
                "word": word_secret,
                "res_a": res_a,
                "res_b": res_b,
                "winner": winner,
                "lead": lead,
            })

        mean_tries_a = np.mean(word_tries_a) if word_tries_a else 999.0
        mean_tries_b = np.mean(word_tries_b) if word_tries_b else 999.0
        mean_time_a = np.mean(word_time_a) if word_time_a else 0.0
        mean_time_b = np.mean(word_time_b) if word_time_b else 0.0
        speedup_word = mean_time_b / max(mean_time_a, 0.001)

        if word_wins_a > word_wins_b:
            word_winner = "⚡ RAG Pur"
        elif word_wins_b > word_wins_a:
            word_winner = "🤖 Hybride LLM"
        elif mean_tries_a < mean_tries_b:
            word_winner = "⚡ RAG Pur"
        elif mean_tries_b < mean_tries_a:
            word_winner = "🤖 Hybride LLM"
        else:
            word_winner = "🤝 Égalité"

        tournament_words_summary.append({
            "word_idx": word_idx,
            "word": word_secret,
            "rounds": n_rounds,
            "mean_tries_a": mean_tries_a,
            "mean_tries_b": mean_tries_b,
            "mean_time_a": mean_time_a,
            "mean_time_b": mean_time_b,
            "speedup": speedup_word,
            "wins_a": word_wins_a,
            "wins_b": word_wins_b,
            "draws": word_draws,
            "winner": word_winner,
        })

        if total_words > 1:
            log(f"\n📊  Bilan Mot #{word_idx} (« {word_secret.upper()} ») : RAG {mean_tries_a:.1f} ess ({mean_time_a:.2f}s) | LLM {mean_tries_b:.1f} ess ({mean_time_b:.2f}s) ➔ Vainqueur : {word_winner}")

    # =========================================================================
    # AFFICHAGE DU GRAND TABLEAU D'HONNEUR FINAL
    # =========================================================================
    if total_words > 1:
        log("\n" + "=" * 88)
        log(f"⚔️   TABLEAU RÉCAPITULATIF DU TOURNOI MULTI-MOTS ({total_words} mots × {n_rounds} rounds = {total_matches} duels)")
        log("=" * 88)
        log(f" {'#':<3} | {'Mot Secret':<16} | {'Rounds':<6} | {'⚡ RAG (moy)':<14} | {'🤖 LLM (moy)':<14} | {'Speedup':<9} | {'Vainqueur':<14}")
        log("-" * 88)
        for w in tournament_words_summary:
            rag_col = f"{w['mean_tries_a']:.1f} ess ({w['mean_time_a']:.1f}s)"
            llm_col = f"{w['mean_tries_b']:.1f} ess ({w['mean_time_b']:.1f}s)"
            spd_col = f"{w['speedup']:.1f}x"
            log(f" {w['word_idx']:<3} | {w['word'].upper():<16} | {w['rounds']:<6} | {rag_col:<14} | {llm_col:<14} | {spd_col:<9} | {w['winner']:<14}")
        log("=" * 88)

        # Statistiques macro sur les mots
        words_won_a = sum(1 for w in tournament_words_summary if "⚡ RAG Pur" in w["winner"])
        words_won_b = sum(1 for w in tournament_words_summary if "🤖 Hybride LLM" in w["winner"])
        words_draw = sum(1 for w in tournament_words_summary if "Égalité" in w["winner"])

        log("\n🏆  BILAN DU TOURNOI PAR MOT :")
        log(f"  Mots remportés par ⚡ 100% RAG Pur : {words_won_a} / {total_words} ({words_won_a/total_words*100:.1f}%)")
        log(f"  Mots remportés par 🤖 Hybride LLM  : {words_won_b} / {total_words} ({words_won_b/total_words*100:.1f}%)")
        log(f"  Mots nuls 🤝                       : {words_draw} / {total_words} ({words_draw/total_words*100:.1f}%)")

    else:
        # Tableau manche par manche pour 1 seul mot
        log("\n" + "=" * 70)
        log("⚔️   TABLEAU D'HONNEUR DU GRAND TOURNOI BATTLE")
        log("=" * 70)
        log(f" {'Manche':<8} | {'Mot Secret':<16} | {'⚡ RAG Pur':<14} | {'🤖 Hybride LLM':<14} | {'Vainqueur':<14}")
        log("-" * 70)
        for r in all_battle_results:
            a_txt = f"{r['res_a']['tries']} essais ({r['res_a']['time']:.1f}s)" if r["res_a"]["win"] else "Échec"
            b_txt = f"{r['res_b']['tries']} essais ({r['res_b']['time']:.1f}s)" if r["res_b"]["win"] else "Échec"
            log(f" #{r['round']:<7} | {r['word'].upper():<16} | {a_txt:<14} | {b_txt:<14} | {r['winner']:<14}")
        log("=" * 70)

    # Statistiques globales consolidées (sur tous les duels)
    total_duels = len(all_battle_results)
    wins_a = sum(1 for r in all_battle_results if "⚡ RAG Pur" in r["winner"])
    wins_b = sum(1 for r in all_battle_results if "🤖 Hybride LLM" in r["winner"])
    draws = sum(1 for r in all_battle_results if "Égalité" in r["winner"])

    tries_a_all = [r["res_a"]["tries"] for r in all_battle_results if r["res_a"]["win"]]
    tries_b_all = [r["res_b"]["tries"] for r in all_battle_results if r["res_b"]["win"]]
    time_a_all = [r["res_a"]["time"] for r in all_battle_results]
    time_b_all = [r["res_b"]["time"] for r in all_battle_results]

    log("\n📊  STATISTIQUES GLOBALES SUR TOUS LES DUELS :")
    log(f"  Victoires ⚡  100% RAG Pur : {wins_a} / {total_duels} ({wins_a/total_duels*100:.1f}%)")
    log(f"  Victoires 🤖  Hybride LLM  : {wins_b} / {total_duels} ({wins_b/total_duels*100:.1f}%)")
    log(f"  Duels nuls 🤝  : {draws} / {total_duels} ({draws/total_duels*100:.1f}%)")

    if tries_a_all and tries_b_all:
        log("\n🎯  EFFICACITÉ GLOBALE (Nombre d'essais moyen) :")
        log(f"  ⚡  100% RAG Pur  : {np.mean(tries_a_all):.1f} essais (médiane: {np.median(tries_a_all):.0f}, min: {np.min(tries_a_all)}, max: {np.max(tries_a_all)})")
        log(f"  🤖  Hybride LLM   : {np.mean(tries_b_all):.1f} essais (médiane: {np.median(tries_b_all):.0f}, min: {np.min(tries_b_all)}, max: {np.max(tries_b_all)})")

    log("\n⏱️  TEMPS D'EXÉCUTION CUMULÉ :")
    log(f"  ⚡  100% RAG Pur  : {sum(time_a_all):.2f}s au total (moyenne {np.mean(time_a_all):.2f}s/duel)")
    log(f"  🤖  Hybride LLM   : {sum(time_b_all):.2f}s au total (moyenne {np.mean(time_b_all):.2f}s/duel)")
    if sum(time_a_all) > 0:
        log(f"  🚀  Facteur d'accélération RAG : {sum(time_b_all)/max(sum(time_a_all), 0.001):.1f}x plus rapide !")
    log("=" * 88 + "\n" if total_words > 1 else "=" * 70 + "\n")


def clear_screen():
    """Efface l'écran du terminal proprement pour tous les OS et environnements."""
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def make_gauge(s: float, p: int | None, threshold: float, width: int = 20) -> str:
    """Génère un thermomètre visuel ASCII adapté à la proximité sémantique."""
    if p is not None:
        ratio = 0.35 + (min(1000, max(1, p)) / 1000.0) * 0.65
        pct_lbl = f"{p:>4}‰"
    else:
        norm_s = max(0.0, s) / max(threshold, 0.01)
        ratio = min(0.35, norm_s * 0.35)
        pct_lbl = f"{s*100:5.1f}°C"
    filled = int(round(ratio * width))
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct_lbl}"


ANSI_RE = re.compile(r'\033\[[0-9;]*m')


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub('', s)


def visible_width(s: str) -> int:
    clean = strip_ansi(s)
    w = 0
    for ch in clean:
        if ch in "🥶🧊😎🥵🔥😱🥳⭐🎯🤖🧑⚔️":
            w += 2
        else:
            w += 1
    return w


def pad_visible(s: str, target_width: int) -> str:
    vw = visible_width(s)
    pad = max(0, target_width - vw)
    return s + " " * pad


def weather_for_score(s: float, p: int | None) -> tuple[str, str]:
    if p == 1000:
        return "🥳", "GAGNÉ"
    elif p and p >= 999:
        return "😱", "BRÛL."
    elif p and p >= 990:
        return "🔥", "CHAUD"
    elif p and p >= 900:
        return "🥵", "CHAUD"
    elif p and p >= 1:
        return "😎", "TIÈDE"
    elif s >= 0.15:
        return "🥶", "FRAIS"
    elif s >= 0:
        return "🥶", "FROID"
    else:
        return "🧊", "GLAC."


def render_game_board(game, guesses, last_played=None, notice=None, view_mode="top", hints=None):
    clear_screen()
    tries_count = len(guesses)
    best_tuple = max(guesses.values(), key=lambda v: v[0], default=None)
    best_score_str = f"{best_tuple[0]*100:6.2f}°C" if best_tuple else "Aucun"
    best_word = [w for w, v in guesses.items() if v == best_tuple][0] if best_tuple else "-"

    log("=" * 70)
    log("🎮  CÉMANTIX INTERACTIF — À VOUS DE JOUER !")
    log("=" * 70)
    log(f"Essais joués : {tries_count:>3}  |  Meilleur : {best_word:<15} ({best_score_str})")
    log(f"Seuil Top 1000 : {game.p1000_threshold * 100:.2f}°C")
    log("-" * 70)

    if not guesses:
        log("\n  💡  Proposez un premier mot pour démarrer la recherche sémantique !\n")
    else:
        if view_mode == "history":
            log("📜  HISTORIQUE DES ESSAIS (Ordre chronologique) :")
            items = sorted(guesses.items(), key=lambda x: x[1][2])[-15:]
        else:
            log("🏆  TABLEAU RÉCAPITULATIF DES MEILLEURS ESSAIS :")
            items = sorted(guesses.items(), key=lambda x: x[1][0], reverse=True)[:15]

        log(f"  {'#':<5}  {'Mot':<20} {'Température':<12}  {'Météo':<14}  {'Rang'}")
        log("  " + "─" * 60)
        for w, (s, p, num, w_icon, w_lbl) in items:
            rk_str = f"{p:>4}‰" if p else "     "
            is_last = (last_played and w == last_played[0])
            w_disp = f"{BOLD}{w:<20}{RESET}" if is_last else f"{w:<20}"
            log(f"  [{num:>3}]  {w_disp} {s*100:6.2f}°C     {w_icon}  {w_lbl:<10}  {rk_str}")
        log("  " + "─" * 60)

    if last_played:
        w, s, p, num, w_icon, w_lbl, is_best = last_played
        rk_str = f"({p}‰)" if p else ""
        rec_str = "  ⭐  (Nouveau record !)" if is_best else ""
        gauge = make_gauge(s, p, game.p1000_threshold, width=20)
        log(f"Dernier coup : [{num:>3}] {BOLD}{w}{RESET} ({s*100:.2f}°C  {w_icon}  {w_lbl} {rk_str}){rec_str}")
        log(f"Thermomètre  : {gauge}  {w_icon}  {w_lbl}")

    if hints:
        log("\n💡  INDICES RAG DÉBLOQUÉS :")
        for i, h in enumerate(hints, 1):
            log(f"  • Indice #{i} : Explorez le champ de « {BOLD}{h}{RESET} »")

    if notice:
        log(f"\n{notice}")

    log("-" * 70)


def format_duel_cell(num: int, w: str, s: float, p: int | None, icon: str, lbl: str, is_last: bool = False) -> str:
    num_str = f" [{num:>2}] "
    raw_w = f"{w[:17]:<17}"
    w_str = f"{BOLD}{raw_w}{RESET} " if is_last else f"{raw_w} "
    score_val = f"{p}‰" if p else f"{s*100:5.2f}°C"
    score_str = f"{score_val:>8}  "
    meteo_str = f"{icon}  {lbl:<5}"
    cell = num_str + w_str + score_str + meteo_str
    return pad_visible(cell, 43)


def render_duel_board(game_human, guesses_human, last_human,
                      game_ai, guesses_ai, last_ai,
                      turn_no: int, notice=None, stats: dict | None = None,
                      hints=None):
    clear_screen()
    log("=" * 89)
    if stats and stats.get("match"):
        diff_tag = f" [{stats.get('difficulty', 'moyen').upper()}]" if stats.get('difficulty') else ""
        log(f"⚔️   DUEL CROISÉ — Manche #{stats['match']} (🧑   {stats['human']} — {stats['ai']}  🤖){diff_tag} — Tour #{turn_no}")
    else:
        log(f"⚔️   CÉMANTIX DUEL CROISÉ — 🧑   VOUS vs 🤖   IA RAG (Tour #{turn_no})")
    log("=" * 89)

    sec = game_ai.secret.upper()
    if len(sec) <= 19:
        r_title = f"  🤖  IA RAG (Cible : {sec})"
    elif len(sec) <= 23:
        r_title = f"  🤖  IA (Cible : {sec})"
    else:
        r_title = f"  🤖  IA : {sec[:21]}…"
    col_l_title = pad_visible("  🧑  VOS ESSAIS (Cible : ???)", 43)
    col_r_title = pad_visible(r_title, 43)
    log(f"{col_l_title} │ {col_r_title}")

    col_head = pad_visible(" #    Mot                 Score   Météo", 43)
    log(f"{col_head} │ {col_head}")
    log("─" * 43 + "─┼─" + "─" * 43)

    items_h = sorted(guesses_human.items(), key=lambda x: x[1][0], reverse=True)[:DUEL_TOP_WORDS]
    items_a = sorted(guesses_ai.items(), key=lambda x: x[1][0], reverse=True)[:DUEL_TOP_WORDS]
    max_rows = max(len(items_h), len(items_a), 1)

    for i in range(max_rows):
        if i < len(items_h):
            w, (s, p, num, icon, lbl) = items_h[i]
            is_last = (last_human and w == last_human[0])
            c_left = format_duel_cell(num, w, s, p, icon, lbl, is_last=is_last)
        else:
            c_left = pad_visible("  -", 43) if (i == 0 and not guesses_human) else " " * 43

        if i < len(items_a):
            w, (s, p, num, icon, lbl) = items_a[i]
            is_last = (last_ai and w == last_ai[0])
            c_right = format_duel_cell(num, w, s, p, icon, lbl, is_last=is_last)
        else:
            c_right = pad_visible("  -", 43) if (i == 0 and not guesses_ai) else " " * 43

        log(f"{c_left} │ {c_right}")

    log("─" * 43 + "─┼─" + "─" * 43)

    lh_score = f"{last_human[2]}‰" if (last_human and last_human[2]) else (f"{last_human[1]*100:.1f}°C" if last_human else "")
    la_score = f"{last_ai[2]}‰" if (last_ai and last_ai[2]) else (f"{last_ai[1]*100:.1f}°C" if last_ai else "")

    lh_str = f"  Dernier : [{last_human[3]:>2}] {last_human[0]} ({lh_score})" if last_human else "  Dernier : -"
    la_str = f"  Dernier : [{last_ai[3]:>2}] {last_ai[0]} ({la_score})" if last_ai else "  Dernier : -"
    log(f"{pad_visible(lh_str, 43)} │ {pad_visible(la_str, 43)}")

    gh_str = f"  Jauge   : {make_gauge(last_human[1], last_human[2], game_human.p1000_threshold, width=10)}" if last_human else "  Jauge   : -"
    ga_str = f"  Jauge   : {make_gauge(last_ai[1], last_ai[2], game_ai.p1000_threshold, width=10)}" if last_ai else "  Jauge   : -"
    log(f"{pad_visible(gh_str, 43)} │ {pad_visible(ga_str, 43)}")
    log("=" * 89)

    if hints:
        log("💡  INDICES RAG DÉBLOQUÉS :")
        for i, h in enumerate(hints, 1):
            log(f"  • Indice #{i} : Explorez le champ de « {BOLD}{h}{RESET} »")
        log("=" * 89)

    if notice:
        log(f"\n{notice}")


def render_duel_debrief(game_human, guesses_human, game_ai, guesses_ai,
                        winner: str, turn_no: int, stats: dict):
    """Affiche le tableau comparatif d'après-match côte à côte sur 89 colonnes."""
    log("\n" + "=" * 89)
    log(f"📊   DÉBRIEFING DU MATCH — MANCHE #{stats.get('match', 1)}")
    log("=" * 89)

    if winner == "human":
        win_str = f"  Vainqueur : 🥳  HUMAIN (en {turn_no} tours)"
    elif winner == "ai":
        win_str = f"  Vainqueur : 🤖  IA RAG (en {turn_no} tours)"
    elif winner == "draw":
        win_str = f"  Résultat  : 🤝  ÉGALITÉ ({turn_no} tours)"
    else:
        win_str = f"  Résultat  : 🏳️  ABANDON (au tour #{turn_no})"

    score_str = f"  Score session : 🧑  {stats.get('human', 0)} — {stats.get('ai', 0)}  🤖"
    log(f"{pad_visible(win_str, 43)} │ {pad_visible(score_str, 43)}")
    log("─" * 43 + "─┼─" + "─" * 43)

    diff_tag = stats.get("difficulty", "moyen").upper()
    title_l = "  🧑  PARCOURS HUMAIN"
    title_r = f"  🤖  PARCOURS IA RAG [{diff_tag}]"
    log(f"{pad_visible(title_l, 43)} │ {pad_visible(title_r, 43)}")

    target_l = f"  • Cible        : {game_human.secret.upper()[:21]}"
    target_r = f"  • Cible        : {game_ai.secret.upper()[:21]}"
    log(f"{pad_visible(target_l, 43)} │ {pad_visible(target_r, 43)}")

    h_won = (winner == "human" or game_human.secret in guesses_human)
    a_won = (winner == "ai" or game_ai.secret in guesses_ai)
    t_h = guesses_human.get(game_human.secret, (0, 0, turn_no))[2] if h_won else None
    t_a = guesses_ai.get(game_ai.secret, (0, 0, turn_no))[2] if a_won else None

    stat_l = f"  • Statut       : TROUVÉ (Tour #{t_h})" if h_won else "  • Statut       : Non trouvé"
    stat_r = f"  • Statut       : TROUVÉ (Tour #{t_a})" if a_won else "  • Statut       : Non trouvé"
    log(f"{pad_visible(stat_l, 43)} │ {pad_visible(stat_r, 43)}")

    def fmt_best(guesses):
        if not guesses:
            return "-"
        b = max(guesses.items(), key=lambda x: x[1][0], default=None)
        if not b:
            return "-"
        w, (s, p, num, *_) = b
        sc = f"{p}‰" if p else f"{s*100:.1f}°C"
        max_w = 43 - 19 - len(f"[{num:>2}] ") - len(f" ({sc})")
        return f"[{num:>2}] {w[:max_w]} ({sc})"

    bm_l = f"  • Meilleur mot : {fmt_best(guesses_human)}"
    bm_r = f"  • Meilleur mot : {fmt_best(guesses_ai)}"
    log(f"{pad_visible(bm_l, 43)} │ {pad_visible(bm_r, 43)}")

    def fmt_spark(guesses):
        sparks = [(w, v[0], v[1], v[2]) for w, v in guesses.items() if (v[0] >= 0.15 or v[1] is not None)]
        if not sparks:
            return "-"
        first = min(sparks, key=lambda x: x[3])
        max_w = 43 - 20 - len(f"Tour #{first[3]} ()")
        return f"Tour #{first[3]} ({first[0][:max_w]})"

    spk_l = f"  • 1ère étincelle: {fmt_spark(guesses_human)}"
    spk_r = f"  • 1ère étincelle: {fmt_spark(guesses_ai)}"
    log(f"{pad_visible(spk_l, 43)} │ {pad_visible(spk_r, 43)}")

    def count_weather(guesses):
        hot = sum(1 for v in guesses.values() if v[1] and v[1] >= 900)
        warm = sum(1 for v in guesses.values() if v[1] and v[1] < 900)
        cold = sum(1 for v in guesses.values() if not v[1])
        return hot, warm, cold

    hot_h, warm_h, cold_h = count_weather(guesses_human)
    hot_a, warm_a, cold_a = count_weather(guesses_ai)

    met_l = f"  • Météo        : 🔥 {hot_h:<2} 😎 {warm_h:<2} 🥶 {cold_h:<2}"
    met_r = f"  • Météo        : 🔥 {hot_a:<2} 😎 {warm_a:<2} 🥶 {cold_a:<2}"
    log(f"{pad_visible(met_l, 43)} │ {pad_visible(met_r, 43)}")
    log("─" * 43 + "─┼─" + "─" * 43 + "\n")


class RagDuelPlayer:
    """Agent RAG mathématique jouant un coup par tour pour le mode Duel."""
    def __init__(self, store: VocabStore, game: MockClient, difficulty: str = "moyen"):
        self.store = store
        self.game = game
        self.difficulty = difficulty.lower() if difficulty else "moyen"
        if self.difficulty not in ("facile", "moyen", "expert"):
            self.difficulty = "moyen"
        self.tried = set()
        self.guesses = {}   # norm -> (s, p, num, w_icon, w_lbl)

        if self.difficulty == "facile":
            self.seeds = ["animal", "temps", "science", "musique", "justice", "corps", "voyage", "nourriture", "nature", "travail", "couleur", "argent"]
            self.min_seeds = 6
        elif self.difficulty == "expert":
            self.seeds = ["animal", "science", "musique", "justice"]
            self.min_seeds = 2
        else:  # moyen
            self.seeds = ["animal", "temps", "science", "musique", "justice", "corps", "voyage", "nourriture", "nature", "travail"]
            self.min_seeds = 4
        self.seed_idx = 0

    def play_turn(self, turn_no: int) -> tuple[str, float, int | None, str, str]:
        word_to_play = None
        known = [(w, s) for w, (s, p, *_) in self.guesses.items() if w in self.store]
        best_score = max([s for w, s in known], default=-1.0)

        # 1. Amorçage initial selon niveau
        warm_threshold = 0.22 if self.difficulty == "facile" else (0.12 if self.difficulty == "expert" else 0.15)
        if (len(known) < self.min_seeds or best_score < warm_threshold) and self.seed_idx < len(self.seeds):
            while self.seed_idx < len(self.seeds):
                candidate_seed = self.store.normalize(self.seeds[self.seed_idx])
                self.seed_idx += 1
                if candidate_seed not in self.tried and candidate_seed in self.store:
                    word_to_play = candidate_seed
                    break

        # 2. Régression Ridge + k-NN + Rerank
        if not word_to_play and len(known) >= 2:
            G = np.vstack([self.store.vec(w) for w, s in known])
            s = np.array([s for w, s in known], dtype=np.float32)
            q_est = estimate_secret(G, s)
            k_knn = 150 if self.difficulty == "expert" else (100 if self.difficulty == "moyen" else 60)
            raw_pool = self.store.knn(q_est, k_knn)

            # Ajoute les voisins des meilleurs coups
            sorted_known = sorted(known, key=lambda x: x[1], reverse=True)
            k_best = 3 if self.difficulty == "expert" else 2
            for w, _ in sorted_known[:k_best]:
                raw_pool += self.store.knn(self.store.vec(w), 50)

            cands = []
            for raw_w in raw_pool:
                w = self.store.normalize(raw_w)
                if (w not in self.tried
                        and w not in cands
                        and len(w) >= 4
                        and w not in STOPWORDS
                        and self.store.is_valid_french(w)):
                    cands.append(w)
                    if len(cands) >= 60:
                        break

            if cands:
                reranked = rerank(self.store, cands, G, s, q_est)
                if reranked:
                    if self.difficulty == "expert":
                        # Expert : joue toujours le top 1 absolu
                        word_to_play = reranked[0][0]
                    elif self.difficulty == "facile":
                        # Facile : sélectionne parmi le pool (rangs 3 à 8) pour ne pas converger trop vite
                        cand_pool = [c[0] for c in reranked[min(2, len(reranked)-1):min(8, len(reranked))]]
                        word_to_play = str(np.random.choice(cand_pool)) if cand_pool else reranked[0][0]
                    else:
                        # Moyen : équilibré, choisit dans le top 2
                        cand_pool = [c[0] for c in reranked[:min(2, len(reranked))]]
                        word_to_play = str(np.random.choice(cand_pool))

        # 3. Fallback sécurité
        if not word_to_play:
            for seed in SEED_WORDS:
                s_norm = self.store.normalize(seed)
                if s_norm not in self.tried and s_norm in self.store:
                    word_to_play = s_norm
                    break

        if not word_to_play:
            word_to_play = "science"

        self.tried.add(word_to_play)
        res = self.game.score(word_to_play)
        s, p = res if res else (0.0, None)
        w_icon, w_lbl = weather_for_score(s, p)

        self.guesses[word_to_play] = (s, p, turn_no, w_icon, w_lbl)
        return word_to_play, s, p, w_icon, w_lbl


def run_solo_loop(store: VocabStore, secret_arg=None):
    game = MockClient(store, secret=secret_arg)
    guesses = {}   # norm -> (s, p, num, w_icon, w_lbl)
    t0 = time.time()
    tries_count = 0
    last_played = None
    notice = None
    view_mode = "top"
    hints = []

    while True:
        render_game_board(game, guesses, last_played=last_played, notice=notice, view_mode=view_mode, hints=hints)
        notice = None

        try:
            raw = input(f"Essai #{tries_count + 1} (ou /duel, /aide, /indice, /rejouer, /abandon) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log(f"\n👋  Partie interrompue. Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} ».")
            return None, None

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("/duel", "duel"):
            return "duel", None
        elif cmd in ("/quitter", "/quit", "/exit", "exit", "quit"):
            log(f"\n👋  Au revoir ! Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} ».")
            return None, None
        elif cmd in ("/abandon", "/giveup", "/solution"):
            elapsed = time.time() - t0
            log("\n" + "=" * 70)
            log(f"🏳️  Abandon après {tries_count} essai(s) ({elapsed:.1f}s).")
            log(f"💡  Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} »")
            log("=" * 70 + "\n")
            try:
                ans = input("🎮  Que souhaitez-vous faire ? ([O]ui pour rejouer / [D]uel / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None, None
            if ans in ("d", "duel", "/duel"):
                return "duel", None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None, None
            return "solo", None
        elif cmd in ("/rejouer", "/nouveau", "/new", "/restart"):
            return "solo", None
        elif cmd in ("/aide", "/help"):
            notice = "Commandes : /duel (mode versus IA), /top, /historique, /indice, /rejouer, /abandon, /quitter"
            continue
        elif cmd in ("/top", "/best"):
            view_mode = "top"
            notice = "Affichage basculé sur le Top des meilleurs essais."
            continue
        elif cmd in ("/historique", "/history"):
            view_mode = "history"
            notice = "Affichage basculé sur l'historique chronologique."
            continue
        elif cmd in ("/indice", "/hint"):
            if len(guesses) < 3:
                notice = "💡  Jouez au moins 3 mots pour que le RAG puisse calculer un indice pertinent."
                continue

            ranked_words = sorted(guesses.items(), key=lambda x: x[1][0], reverse=True)
            top_word, (best_s, best_p, *_) = ranked_words[0]

            if best_s > 0.10:
                v_best = store.vec(top_word)
                v_target = 0.35 * v_best + 0.65 * game.v_secret
                v_target = v_target / np.linalg.norm(v_target)
                cands_knn = store.knn(v_target, k=60)
            else:
                cands_knn = store.knn(game.v_secret, k=150)[40:]

            secret_stem = game.secret[:min(5, len(game.secret))]
            valid_hints = []
            for w in cands_knn:
                w_norm = store.normalize(w)
                if (w_norm not in guesses
                        and w_norm not in hints
                        and w_norm != game.secret
                        and len(w_norm) >= 4
                        and w_norm not in STOPWORDS
                        and not w_norm.startswith(secret_stem)
                        and not game.secret.startswith(w_norm[:min(5, len(w_norm))])
                        and store.is_valid_french(w_norm)):
                    res_hint = game.score(w_norm)
                    if res_hint:
                        s_w, p_w = res_hint
                        if s_w > best_s or (p_w and p_w >= 500):
                            valid_hints.append((w_norm, s_w, p_w))

            if valid_hints:
                valid_hints.sort(key=lambda x: x[1])
                chosen_hint = valid_hints[len(valid_hints) // 2][0]
                hints.append(chosen_hint)
                notice = f"💡  Nouvel indice #{len(hints)} débloqué : « {chosen_hint} » !"
            else:
                notice = "💡  Pas d'indice supplémentaire disponible pour le moment."
            continue

        norm = store.normalize(cmd)
        if norm in guesses:
            s, p, num, w_icon, w_lbl = guesses[norm]
            rk_str = f"{p}‰" if p else ""
            notice = f"⚠️  Déjà essayé (#{num}) : « {norm} » ({s*100:.2f}°C  {w_icon}  {w_lbl} {rk_str})"
            continue

        if not store.is_valid_french(norm) or norm not in store:
            notice = f"❌  Mot « {raw} » non reconnu (lemmes français au singulier uniquement)."
            continue

        res = game.score(norm)
        if res is None:
            notice = f"❌  Mot « {raw} » rejeté par le jeu."
            continue

        s, p = res
        tries_count += 1
        w_icon, w_lbl = weather_for_score(s, p)

        best_score = max([v[0] for v in guesses.values()], default=-1.0)
        is_new_best = (s > best_score) and (s > 0.15)
        guesses[norm] = (s, p, tries_count, w_icon, w_lbl)
        last_played = (norm, s, p, tries_count, w_icon, w_lbl, is_new_best)

        if p == 1000 or norm == game.secret:
            render_game_board(game, guesses, last_played=last_played, view_mode="top", hints=hints)
            elapsed = time.time() - t0
            log("\n" + "🎉" * 25)
            log("🥳  VICTOIRE ! FÉLICITATIONS !")
            log(f"    Vous avez trouvé le mot secret « {BOLD}{game.secret.upper()}{RESET} » !")
            log(f"    Nombre total d'essais : {tries_count}")
            log(f"    Temps de réflexion     : {elapsed:.1f} secondes")
            log("🎉" * 25 + "\n")
            try:
                ans = input("🎮  Que souhaitez-vous faire ? ([O]ui pour rejouer / [D]uel / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None, None
            if ans in ("d", "duel", "/duel"):
                return "duel", None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None, None
            return "solo", None


def run_duel_loop(store: VocabStore, stats: dict | None = None, initial_difficulty: str = "moyen"):
    if stats is None:
        stats = {"human": 0, "ai": 0, "draws": 0, "match": 0, "difficulty": initial_difficulty}
    if "difficulty" not in stats:
        stats["difficulty"] = initial_difficulty
    stats["match"] += 1

    clear_screen()
    log("=" * 89)
    if stats["match"] > 1:
        log(f"⚔️   CÉMANTIX DUEL CROISÉ — MANCHE #{stats['match']} (Score : 🧑   {stats['human']} — {stats['ai']}  🤖)")
    else:
        log("⚔️   CÉMANTIX DUEL CROISÉ — NOUVEAU MATCH")
    log("=" * 89)
    log("L'IA a tiré son mot secret. Paramétrez la manche :\n")

    # Étape 1/2 : Niveau de difficulté de l'IA
    diff_default = stats["difficulty"].capitalize()
    while True:
        try:
            raw_diff = input(f"Étape 1/2 🎚️   Niveau de l'IA ([F]acile, [M]oyen, [E]xpert) [{diff_default}] > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            log("\n👋  Au revoir !")
            return None

        if not raw_diff:
            break
        elif raw_diff in ("/solo", "solo"):
            return "solo"
        elif raw_diff in ("/quitter", "/quit", "quit", "exit"):
            return None
        elif raw_diff.startswith("f"):
            stats["difficulty"] = "facile"
            break
        elif raw_diff.startswith("e"):
            stats["difficulty"] = "expert"
            break
        elif raw_diff.startswith("m"):
            stats["difficulty"] = "moyen"
            break
        else:
            log("❌  Option invalide. Choisissez [F]acile, [M]oyen ou [E]xpert.")

    log(f"✓   Niveau sélectionné : {BOLD}{stats['difficulty'].upper()}{RESET}\n")

    # Étape 2/2 : Mot secret pour l'IA
    ai_target = None
    while not ai_target:
        try:
            raw = input("Étape 2/2 🎯   Mot secret pour l'IA (Entrée = tirage aléatoire) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log("\n👋  Au revoir !")
            return None

        cmd = raw.lower()
        if not raw or cmd in ("/random", "random"):
            valid_cands = [w for w in store.words if store.is_valid_french(w) and len(w) >= 4 and w not in STOPWORDS]
            ai_target = str(np.random.choice(valid_cands))
            log(f"🎲  Mot secret tiré au sort pour l'IA : « {BOLD}{ai_target.upper()}{RESET} »")
            time.sleep(0.8)
            break

        if cmd in ("/solo", "solo"):
            return "solo"
        if cmd in ("/quitter", "/quit", "quit", "exit"):
            return None

        norm = store.normalize(cmd)
        if store.is_valid_french(norm) and norm in store:
            ai_target = norm
            log(f"✓   Mot secret de l'IA validé : « {BOLD}{ai_target.upper()}{RESET} »")
            time.sleep(0.8)
            break
        else:
            log(f"❌  Mot « {raw} » non reconnu ou non recevable (lemmes français au singulier uniquement).")

    game_ai = MockClient(store, secret=ai_target)
    ai_player = RagDuelPlayer(store, game_ai, difficulty=stats["difficulty"])
    game_human = MockClient(store)

    guesses_human = {}
    last_human = None
    last_ai = None
    turn_no = 0
    notice = None
    spy_credits = 1
    hints = []

    while True:
        render_duel_board(game_human, guesses_human, last_human,
                          game_ai, ai_player.guesses, last_ai,
                          turn_no + 1, notice=notice, stats=stats, hints=hints)
        notice = None

        try:
            raw = input(f"Tour #{turn_no + 1} > Votre coup (ou /solo, /espion, /indice, /rejouer, /abandon) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log(f"\n👋  Duel interrompu. Votre mot secret était : « {BOLD}{game_human.secret.upper()}{RESET} ».")
            return None

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("/solo", "solo"):
            return "solo"
        elif cmd in ("/rejouer", "/nouveau", "/restart"):
            return "duel"
        elif cmd in ("/quitter", "/quit", "/exit", "exit", "quit"):
            log(f"\n👋  Au revoir ! Votre mot secret était : « {BOLD}{game_human.secret.upper()}{RESET} ».")
            return None
        elif cmd in ("/diff", "/difficulte", "/difficulty", "/niveau"):
            notice = f"🎚️   Niveau actuel de l'IA : {stats['difficulty'].upper()} (changez avec /facile, /moyen, /expert)"
            continue
        elif cmd in ("/facile", "facile"):
            stats["difficulty"] = "facile"
            ai_player.difficulty = "facile"
            notice = "✓   Niveau de l'IA basculé sur : FACILE"
            continue
        elif cmd in ("/moyen", "moyen"):
            stats["difficulty"] = "moyen"
            ai_player.difficulty = "moyen"
            notice = "✓   Niveau de l'IA basculé sur : MOYEN"
            continue
        elif cmd in ("/expert", "expert"):
            stats["difficulty"] = "expert"
            ai_player.difficulty = "expert"
            notice = "✓   Niveau de l'IA basculé sur : EXPERT"
            continue
        elif cmd in ("/espion", "espion", "/spy", "spy"):
            if spy_credits <= 0:
                notice = "⚠️   Coup d'espionnage déjà épuisé pour cette manche (1/1 max)."
                continue
            if not ai_player.guesses:
                notice = "⚠️   L'IA n'a pas encore joué de coup à espionner."
                continue

            spy_credits -= 1
            # 1. Quartier sémantique traqué par l'IA
            known_ai = [(w, s) for w, (s, p, *_) in ai_player.guesses.items() if w in store]
            if len(known_ai) >= 2:
                G_ai = np.vstack([store.vec(w) for w, s in known_ai])
                s_ai = np.array([s for w, s in known_ai], dtype=np.float32)
                q_ai = estimate_secret(G_ai, s_ai)
            else:
                q_ai = store.vec(max(known_ai, key=lambda x: x[1])[0])

            disc_scores = []
            for d in DISCIPLINES:
                d_norm = store.normalize(d)
                if d_norm in store:
                    disc_scores.append((d, float(store.vec(d_norm) @ q_ai)))
            disc_scores.sort(key=lambda x: x[1], reverse=True)
            top_disc = f"{disc_scores[0][0]} / {disc_scores[1][0]}"

            # 2. Meilleur essai adverse
            best_ai = max(ai_player.guesses.items(), key=lambda x: x[1][0])
            w_b, (s_b, p_b, num_b, icon_b, lbl_b) = best_ai
            sc_b = f"{p_b}‰" if p_b else f"{s_b*100:.1f}°C"

            # 3. Alerte proximité
            if p_b and p_b >= 900:
                alert = f"🚨 DANGER BRÛLANT : L'IA est dans le Top 100 ({p_b}‰) !"
            elif p_b:
                alert = f"⚠️   ALERTE : L'IA est entrée dans le Top 1000 ({p_b}‰) !"
            elif s_b >= 0.15:
                alert = f"👀 PISTE TIÈDE : L'IA approche votre zone ({s_b*100:.1f}°C)."
            else:
                alert = f"🧊 CALME : L'IA cherche encore dans le froid ({s_b*100:.1f}°C)."

            # 4. Le tour est consommé : l'IA joue son coup !
            turn_no += 1
            w_ai, s_ai, p_ai, icon_ai, lbl_ai = ai_player.play_turn(turn_no)
            last_ai = (w_ai, s_ai, p_ai, turn_no, icon_ai, lbl_ai)
            ai_won = (p_ai == 1000 or w_ai == ai_target)

            notice = (
                f"🕵️   [ESPIONNAGE SÉMANTIQUE — 1/1 UTILISÉ]\n"
                f"    ├── Quartier traqué par l'IA : « {top_disc} »\n"
                f"    ├── Meilleur essai adverse   : [{num_b}] {w_b} ({sc_b} — {icon_b} {lbl_b})\n"
                f"    └── {alert}\n"
                f"    (⚠️   Votre tour a été consommé : l'IA a joué « {w_ai} »)"
            )

            if ai_won:
                render_duel_board(game_human, guesses_human, last_human,
                                  game_ai, ai_player.guesses, last_ai,
                                  turn_no, notice=None, stats=stats, hints=hints)
                render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                    winner="ai", turn_no=turn_no, stats=stats)
                try:
                    ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    return None
                if ans in ("s", "solo", "/solo"):
                    return "solo"
                if ans in ("n", "non", "q", "quit", "quitter"):
                    return None
                return "duel"

            continue
        elif cmd in ("/abandon", "/giveup"):
            stats["ai"] += 1
            render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                winner="abandon", turn_no=turn_no + 1, stats=stats)
            try:
                ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None
            if ans in ("s", "solo", "/solo"):
                return "solo"
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None
            return "duel"
        elif cmd in ("/aide", "/help"):
            notice = "Commandes : /espion (rapport tactique sur l'IA), /solo, /diff, /facile, /moyen, /expert, /indice, /rejouer, /abandon, /quitter"
            continue
        elif cmd in ("/indice", "/hint"):
            if len(guesses_human) < 3:
                notice = "💡  Jouez au moins 3 mots pour calculer un indice pertinent."
                continue
            ranked_words = sorted(guesses_human.items(), key=lambda x: x[1][0], reverse=True)
            top_word, (best_s, best_p, *_) = ranked_words[0]
            if best_s > 0.10:
                v_best = store.vec(top_word)
                v_target = 0.35 * v_best + 0.65 * game_human.v_secret
                v_target = v_target / np.linalg.norm(v_target)
                cands_knn = store.knn(v_target, k=60)
            else:
                cands_knn = store.knn(game_human.v_secret, k=150)[40:]

            secret_stem = game_human.secret[:min(5, len(game_human.secret))]
            valid_hints = []
            for w in cands_knn:
                w_norm = store.normalize(w)
                if (w_norm not in guesses_human
                        and w_norm not in hints
                        and w_norm != game_human.secret
                        and len(w_norm) >= 4
                        and w_norm not in STOPWORDS
                        and not w_norm.startswith(secret_stem)
                        and not game_human.secret.startswith(w_norm[:min(5, len(w_norm))])
                        and store.is_valid_french(w_norm)):
                    res_hint = game_human.score(w_norm)
                    if res_hint:
                        s_w, p_w = res_hint
                        if s_w > best_s or (p_w and p_w >= 500):
                            valid_hints.append((w_norm, s_w, p_w))
            if valid_hints:
                valid_hints.sort(key=lambda x: x[1])
                chosen_hint = valid_hints[len(valid_hints) // 2][0]
                hints.append(chosen_hint)
                notice = f"💡  Nouvel indice #{len(hints)} débloqué : « {chosen_hint} » !"
            else:
                notice = "💡  Pas d'indice supplémentaire disponible pour le moment."
            continue

        norm_h = store.normalize(cmd)
        if norm_h in guesses_human:
            notice = f"⚠️   Déjà essayé : « {norm_h} »"
            continue

        if not store.is_valid_french(norm_h) or norm_h not in store:
            notice = f"❌   Mot « {raw} » non reconnu (lemmes français au singulier uniquement)."
            continue

        res_h = game_human.score(norm_h)
        if res_h is None:
            notice = f"❌   Mot « {raw} » rejeté par le jeu."
            continue

        s_h, p_h = res_h
        turn_no += 1
        icon_h, lbl_h = weather_for_score(s_h, p_h)

        guesses_human[norm_h] = (s_h, p_h, turn_no, icon_h, lbl_h)
        last_human = (norm_h, s_h, p_h, turn_no, icon_h, lbl_h)
        human_won = (p_h == 1000 or norm_h == game_human.secret)

        # Coup de l'IA RAG
        w_ai, s_ai, p_ai, icon_ai, lbl_ai = ai_player.play_turn(turn_no)
        last_ai = (w_ai, s_ai, p_ai, turn_no, icon_ai, lbl_ai)
        ai_won = (p_ai == 1000 or w_ai == ai_target)

        if human_won or ai_won:
            if human_won and ai_won:
                stats["draws"] += 1
                winner = "draw"
            elif human_won:
                stats["human"] += 1
                winner = "human"
            else:
                stats["ai"] += 1
                winner = "ai"

            render_duel_board(game_human, guesses_human, last_human,
                              game_ai, ai_player.guesses, last_ai,
                              turn_no, notice=None, stats=stats, hints=hints)
            render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                winner=winner, turn_no=turn_no, stats=stats)

            try:
                ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None
            if ans in ("s", "solo", "/solo"):
                return "solo"
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None
            return "duel"


def run_game(args):
    store = VocabStore()
    secret_arg = getattr(args, "secret", None)
    mode = "duel" if getattr(args, "duel", False) else "solo"
    init_diff = getattr(args, "difficulty", "moyen")
    duel_stats = {"human": 0, "ai": 0, "draws": 0, "match": 0, "difficulty": init_diff}

    while True:
        if mode == "solo":
            mode, secret_arg = run_solo_loop(store, secret_arg)
            if mode is None:
                break
        elif mode == "duel":
            mode = run_duel_loop(store, stats=duel_stats, initial_difficulty=init_diff)
            if mode is None:
                break


def main():
    clear_screen()
    ap = argparse.ArgumentParser(description="Solveur Cémantix par RAG local (frWac)")
    ap.add_argument("--max-tries", type=int, default=300)
    ap.add_argument("--retrieve", type=int, default=60,
                    help="nb de voisins récupérés par requête ChromaDB")
    ap.add_argument("--rag-words", type=int, default=3,
                    help="nb de candidats rerankés joués directement par tour (défaut : 3 en hybride, 5 en RAG pur)")
    ap.add_argument("--llm-words", type=int, default=6,
                    help="nb de mots demandés au LLM par tour")
    ap.add_argument("--rag-only", "--no-llm", action="store_true", dest="rag_only",
                    help="mode 100%% RAG mathématique pur (zéro appel LLM, descente Ridge + rerank seuls)")
    ap.add_argument("--delay", type=float, default=0.25,
                    help="pause entre deux requêtes au site (s)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="affiche les détails internes (Ridge, Rerank, Prompt et Reasoning du LLM)")
    ap.add_argument("--seeds", type=str, default="",
                    help="mots graines séparés par des virgules (ex: --seeds 'micro,questionner,revue,publier')")
    ap.add_argument("--seeds-file", type=str, default="",
                    help="chemin vers un fichier de mots graines (un par ligne)")
    ap.add_argument("--seed-count", type=int, default=16,
                    help="nombre de mots graines à tester lors de l'amorçage pluridisciplinaire (défaut : 16)")
    ap.add_argument("--static-seeds", action="store_true",
                    help="utiliser l'ancienne liste fixe de 20 graines au lieu de l'extraction RAG")
    ap.add_argument("--mock", action="store_true",
                    help="mode mock : simule une partie en local avec un mot secret tiré au sort")
    ap.add_argument("--secret", type=str, default=None,
                    help="mot secret forcé en mode mock (si omis, tirage au sort total)")
    ap.add_argument("--words", type=int, default=1,
                    help="nombre de mots secrets distincts à tester en mode battle (défaut : 1)")
    ap.add_argument("--secrets", type=str, default="",
                    help="liste de mots secrets imposés séparés par des virgules (ex: --secrets 'volcan,politique,astronomie')")
    ap.add_argument("--benchmark", type=int, default=0,
                    help="exécute N parties simulées à la suite et affiche les statistiques globales")
    ap.add_argument("--battle", type=int, nargs="?", const=1, default=0,
                    help="mode battle comparatif (N manches sur le MÊME mot) : 100%% RAG Pur vs Hybride RAG+LLM. Par défaut en direct sur le mot du jour Cémantix, ou en local avec --mock")
    ap.add_argument("--play", "--game", action="store_true", dest="play_mode",
                    help="mode jeu interactif : tire un mot au sort en local et vous laisse deviner avec le calcul vectoriel")
    ap.add_argument("--duel", action="store_true",
                    help="lance directement le mode duel croisé humain vs IA RAG")
    ap.add_argument("--difficulty", "-d", choices=["facile", "moyen", "expert"], default="moyen",
                    help="niveau de difficulté de l'IA en mode duel (facile, moyen, expert; défaut: moyen)")
    args = ap.parse_args()

    if args.duel:
        args.play_mode = True

    is_rag_only = getattr(args, "rag_only", False)
    mode_str = "100% RAG Pur Mathématique (Zéro LLM)" if is_rag_only else f"Hybride RAG + Local LLM ({LLM_MODEL})"

    if args.play_mode:
        run_game(args)
    elif args.battle > 0 or args.words > 1 or bool(args.secrets):
        battle_rounds = args.battle if args.battle > 0 else 1
        run_battle(args, battle_rounds)
    elif args.benchmark > 0:
        run_benchmark(args, args.benchmark)
    elif args.mock:
        run_benchmark(args, 1)
    else:
        log("=" * 60)
        log(f"🎯  CÉMANTIX SOLVER — {mode_str}")
        log("=" * 60)
        Solver(args).run()


if __name__ == "__main__":
    sys.exit(main())
