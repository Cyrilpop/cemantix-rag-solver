"""
Cémantix Solver — Gestion du Vocabulaire & Espace Vectoriel
============================================================
Gère le téléchargement et l'indexation de l'espace vectoriel frWac,
le dictionnaire officiel Lexique 3.83, la normalisation des accents
et la classe centrale VocabStore (recherche k-NN via ChromaDB).
"""
import io
import time
import unicodedata
import zipfile
import csv
import re
from pathlib import Path

import chromadb
import numpy as np
import requests

from .config import (
    DATA_DIR, LEXIQUE_FILE, LEXIQUE_URL, W2V_FILE, W2V_URL,
    MAX_VOCAB, CHROMA_DIR, COLLECTION, WORD_RE, STOPWORDS,
    HEADERS, log
)


def strip_accents(text: str) -> str:
    """Supprime les signes diacritiques (accents) d'une chaîne."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def ensure_lexique() -> Path:
    """Télécharge et extrait le dictionnaire Lexique 3.83 s'il n'existe pas localement."""
    if LEXIQUE_FILE.exists() and LEXIQUE_FILE.stat().st_size > 100000:
        return LEXIQUE_FILE
    log("⬇  Téléchargement et extraction du dictionnaire Lexique 3.83...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
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
    """Charge les lemmes officiels et construit une table de correspondance sans accent -> lemme canonique."""
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


def download_w2v(path: Path) -> None:
    """Télécharge le modèle binaire word2vec pré-entraîné avec support de reprise."""
    log(f"⬇  Téléchargement de {W2V_FILE} (une seule fois)...")
    tmp = path.with_suffix(".part")
    offset = tmp.stat().st_size if tmp.exists() else 0
    headers = {**HEADERS, "Range": f"bytes={offset}-"} if offset else HEADERS

    with requests.get(W2V_URL, headers=headers, stream=True, timeout=60) as r:
        if r.status_code == 416:  # Fichier déjà complet
            tmp.rename(path)
            return
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
