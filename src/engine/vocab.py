"""
Cémantix Solver — Gestion du Vocabulaire & Espace Vectoriel (src.engine.vocab)
==============================================================================
Gère le téléchargement et l'indexation de l'espace vectoriel frWac,
le dictionnaire officiel Lexique 3.83, la normalisation des accents
et la classe centrale VocabStore (recherche k-NN via ChromaDB).
"""
import io
import os
import time
import hashlib
import unicodedata
import zipfile
import csv
import re
from pathlib import Path

import numpy as np
import requests

from ..config import (
    DATA_DIR, LEXIQUE_FILE, LEXIQUE_URL, W2V_FILE, W2V_URL,
    MAX_VOCAB, CHROMA_DIR, COLLECTION, WORD_RE, STOPWORDS, ENGLISH_WORDS,
    HEADERS, log
)


def strip_accents(text: str) -> str:
    """Supprime les signes diacritiques (accents) d'une chaîne."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# --------------------------------------------------------------------------- #
# Contrôle d'intégrité des fichiers téléchargés (SEC-11)
# --------------------------------------------------------------------------- #
# Un modèle de mots corrompu n'est pas une erreur visible : il fausse tous les
# scores de similarité, donc toutes les réponses du jeu. Le contrôle est structurel
# (toujours actif) et, si W2V_SHA256 / LEXIQUE_SHA256 sont fournis dans l'environnement,
# complété par une empreinte SHA-256.
MIN_W2V_BYTES = 50 << 20      # le modèle frWac 500 dims pèse ~2 Go
MIN_LEMMES = 100_000          # Lexique 3.83 filtré en fournit ~350 000


def _looks_like_html(head: bytes) -> bool:
    """Détecte une page HTML reçue à la place du binaire attendu.

    Cas réel de ce poste : un proxy d'entreprise répond 200 OK avec un message de
    blocage. Sans contrôle, ce fichier est ensuite lu comme un modèle vectoriel.
    """
    low = head.lstrip()[:400].lower()
    return low.startswith(b"<!doctype") or low.startswith(b"<html") or b"<html" in low


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_checksum(path: Path, expected: str, label: str) -> None:
    """Compare l'empreinte du fichier à celle attendue, si elle est configurée."""
    if not expected:
        return
    actual = _sha256_of(path)
    if actual.lower() != expected.strip().lower():
        raise ValueError(
            f"{label} : empreinte SHA-256 inattendue\n"
            f"   attendu : {expected.strip()}\n   obtenu  : {actual}"
        )
    log(f"✓  {label} : empreinte SHA-256 vérifiée")


def verify_w2v_file(path: Path) -> None:
    """Valide la structure d'un modèle word2vec avant de le mettre en service.

    Le format s'ouvre par « <nb_mots> <dimension>\\n ». Un fichier tronqué, une
    page de proxy ou une reprise mal reprise ne passe pas ce contrôle.
    """
    if not path.exists():
        raise ValueError(f"{path.name} : fichier absent")
    size = path.stat().st_size
    if size < MIN_W2V_BYTES:
        raise ValueError(
            f"{path.name} : taille suspecte ({size} octets, attendu >= {MIN_W2V_BYTES})"
        )
    with open(path, "rb") as handle:
        head = handle.read(4096)
    if _looks_like_html(head):
        raise ValueError(
            f"{path.name} : contenu HTML reçu à la place du modèle "
            "(proxy ou portail captif ?)"
        )
    first_line = head.split(b"\n", 1)[0].decode("utf-8", "replace").strip()
    parts = first_line.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"{path.name} : en-tête word2vec invalide (lu {first_line[:60]!r})"
        )
    vocab_size, dimension = int(parts[0]), int(parts[1])
    if not (1000 <= vocab_size <= 5_000_000) or not (10 <= dimension <= 2000):
        raise ValueError(
            f"{path.name} : en-tête incohérent (vocab={vocab_size}, dim={dimension})"
        )
    _verify_checksum(path, os.getenv("W2V_SHA256", ""), path.name)


def ensure_lexique() -> Path:
    """Télécharge et extrait le dictionnaire Lexique 3.83 s'il n'existe pas localement."""
    if LEXIQUE_FILE.exists() and LEXIQUE_FILE.stat().st_size > 100000:
        words = set(LEXIQUE_FILE.read_text(encoding="utf-8").splitlines())
        polluted = [w for w in ("water", "people", "about", "shit", "fuck", "game", "play") if w in words]
        if not polluted:
            return LEXIQUE_FILE
        log(f"🧹  Assainissement du dictionnaire {LEXIQUE_FILE.name} (suppression des résidus anglais)...")
        clean_words = sorted(w for w in words if w not in ENGLISH_WORDS)
        LEXIQUE_FILE.write_text("\n".join(clean_words), encoding="utf-8")
        return LEXIQUE_FILE

    log("⬇  Téléchargement et extraction du dictionnaire Lexique 3.83...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(LEXIQUE_URL, timeout=60)
        r.raise_for_status()
        if _looks_like_html(r.content[:4096]):
            raise ValueError(
                "réponse HTML reçue à la place de l'archive (proxy ou portail captif ?)"
            )
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open("Lexique383.tsv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="ignore"), delimiter="\t")
            lemmes = set()
            for row in reader:
                cg = row.get("cgram", "")
                if (cg in ("NOM", "ADJ", "VER", "ADV", "AUX", "CON", "PRE")
                        or cg.startswith("ADJ:") or cg.startswith("PRO:")):
                    w = row.get("lemme", "").strip().lower()
                    if (len(w) >= 3
                            and re.fullmatch(r"[a-zàâäçéèêëîïôöùûüÿœæ\-]+", w)
                            and w not in ENGLISH_WORDS):
                        lemmes.add(w)
            clean_lemmes = sorted(w for w in lemmes if w not in ENGLISH_WORDS)
            if len(clean_lemmes) < MIN_LEMMES:
                # Une archive tronquée donnerait un dictionnaire partiel : le jeu
                # refuserait ensuite des mots valides, sans qu'on sache pourquoi.
                raise ValueError(
                    f"dictionnaire incomplet ({len(clean_lemmes)} lemmes, "
                    f"attendu >= {MIN_LEMMES})"
                )
            LEXIQUE_FILE.write_text("\n".join(clean_lemmes), encoding="utf-8")
            log(f"✓  {len(clean_lemmes)} lemmes officiels enregistrés dans {LEXIQUE_FILE.name}")
    except Exception as e:
        # Sans dictionnaire, le jeu est injouable : ce n'est pas un détail à taire.
        log(f"❌  Impossible de télécharger Lexique 3.83 : {e}")
        log("   Le dictionnaire est indispensable : corrigez l'accès réseau puis relancez.")
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
    """Télécharge le modèle binaire word2vec pré-entraîné avec support de reprise.

    Le fichier n'est mis en place (`rename`) qu'après contrôle de structure : un
    téléchargement interrompu ou détourné par un proxy ne doit jamais devenir la
    source de vérité de l'espace vectoriel.
    """
    log(f"⬇  Téléchargement de {W2V_FILE} (une seule fois)...")
    tmp = path.with_suffix(".part")
    offset = tmp.stat().st_size if tmp.exists() else 0
    headers = {**HEADERS, "Range": f"bytes={offset}-"} if offset else HEADERS

    try:
        with requests.get(W2V_URL, headers=headers, stream=True, timeout=60) as r:
            if r.status_code == 416:  # Fichier déjà complet : à valider, pas à accepter
                tmp.rename(path)
                verify_w2v_file(path)
                return
            r.raise_for_status()
            # Pas de lecture anticipée du flux ici : consommer le premier bloc le
            # ferait manquer au fichier. Le contenu HTML est détecté par
            # verify_w2v_file, qui relit le fichier écrit.
            mode = "ab" if r.status_code == 206 else "wb"
            if mode == "wb" and offset:
                # Le serveur ignore la reprise : on repart proprement.
                offset = 0
            total = int(r.headers.get("content-length", 0)) + (offset if mode == "ab" else 0)
            done = offset if mode == "ab" else 0
            with open(tmp, mode) as f:
                for chunk in r.iter_content(1 << 22):
                    f.write(chunk)
                    done += len(chunk)
                    if total and done % (200 << 20) < (1 << 22):
                        log(f"   {done >> 20}/{total >> 20} Mo")
        if total and done != total:
            raise ValueError(f"téléchargement tronqué : {done} octets reçus sur {total}")
        tmp.rename(path)
        verify_w2v_file(path)
    except Exception:
        # Un `.part` conservé serait repris tel quel au prochain lancement : la
        # corruption deviendrait permanente.
        tmp.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        raise


def load_w2v():
    """Lit le binaire word2vec (trié par fréquence) et garde les MAX_VOCAB
    premiers lemmes simples (pas d'expressions 'a_b', mots français valides)."""
    path = DATA_DIR / W2V_FILE
    cache_npy = DATA_DIR / f"{path.stem}_{MAX_VOCAB}_vecs.npy"
    cache_words = DATA_DIR / f"{path.stem}_{MAX_VOCAB}_words.txt"
    cache_npz = DATA_DIR / f"{path.stem}_{MAX_VOCAB}.npz"

    # Format ultra-rapide (mmap mémoire : ~0.05 seconde)
    if cache_npy.exists() and cache_words.exists():
        words = cache_words.read_text(encoding="utf-8").splitlines()
        # Si le cache contient le mot "car", il est sain et à jour
        if "car" in words:
            log(f"📦  Chargement rapide des {len(words)} lemmes (mmap instantané)...")
            vecs = np.load(cache_npy, mmap_mode="r")
            return words, vecs
        log("🔄  Ancien cache incomplet détecté (sans 'car'). Régénération propre depuis frWac...")
        cache_npy.unlink(missing_ok=True)
        cache_words.unlink(missing_ok=True)
        if cache_npz.exists():
            cache_npz.unlink(missing_ok=True)

    if cache_npz.exists():
        log(f"📦  Décompression du cache vectoriel ({MAX_VOCAB} lemmes)...")
        z = np.load(cache_npz)
        words, vecs = list(z["words"]), z["vecs"]
        if "car" in words:
            np.save(cache_npy, vecs)
            cache_words.write_text("\n".join(words), encoding="utf-8")
            return words, vecs
        cache_npz.unlink(missing_ok=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        download_w2v(path)  # valide déjà le fichier qu'il vient de télécharger
    else:
        # Fichier déjà en place (téléchargé avant l'ajout de ce contrôle) : on le
        # valide à la lecture plutôt que de lui faire une confiance aveugle.
        verify_w2v_file(path)
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
            # Conserve tous les lemmes au format valide sans exclure les mots français usuels
            if WORD_RE.fullmatch(w):
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
    def __init__(self, with_chroma: bool = True):
        words, vecs = load_w2v()
        self.words = words
        self.index = {w: i for i, w in enumerate(words)}
        self.vecs = vecs
        self.valid_lemmas, self.accent_map = load_lexique()
        self.clean_french_words = [w for w in self.words if w in self.valid_lemmas]
        if self.valid_lemmas:
            log(f"📖  Dictionnaire officiel français : {len(self.valid_lemmas)} lemmes ({len(self.clean_french_words)} dans frWac)")

        self.col = None
        if not with_chroma:
            log("⚡  [API WEB] Mode sans ChromaDB actif (calcul cosinus NumPy memmap instantané).")
            return

        try:
            import chromadb
            log("⚡  Connexion à la base vectorielle ChromaDB...")
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self.col = client.get_or_create_collection(
                COLLECTION, metadata={"hnsw:space": "cosine"})
            if self.col.count() < len(words):
                self._ingest(words, vecs)
            else:
                # Synchronisation rapide des lemmes fondamentaux réintégrés
                key_words = [w for w in ["car", "faire", "être", "avoir", "bien", "rien", "autre"] if w in self.index]
                try:
                    existing = set(self.col.get(ids=key_words)["ids"])
                    missing = [w for w in key_words if w not in existing]
                    if missing:
                        missing_vecs = [self.vec(w) for w in missing]
                        self.col.upsert(ids=missing, embeddings=[v.tolist() for v in missing_vecs])
                        log(f"✓  Synchronisation ChromaDB : {len(missing)} lemmes essentiels réintégrés ({', '.join(missing)})")
                except Exception as e:
                    log(f"⚠️  Vérification ChromaDB : {e}")
            log(f"📚  Vector store prêt : {self.col.count()} lemmes ({W2V_FILE})")
        except Exception as e:
            log(f"ℹ️  ChromaDB non chargé ({e}). Poursuite en mode NumPy memmap.")
            self.col = None


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
        """Vérifie qu'un mot est un lemme français valide (non anglais) et présent dans l'espace vectoriel."""
        w = word.strip().lower()
        if w in ENGLISH_WORDS:
            return False
        return (w in self.valid_lemmas or not self.valid_lemmas) and (w in self.index)

    def has_word(self, word: str) -> bool:
        """Vérifie si un mot est indexé dans le store vectoriel."""
        return word.strip().lower() in self.index

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
        if self.col is not None:
            res = self.col.query(query_embeddings=[query.tolist()], n_results=k)
            return res["ids"][0]
        # Repli NumPy memmap : ChromaDB n'est pas chargé (désactivé par l'API web
        # ou indisponible au démarrage). Sans cette branche, le solver échouait
        # sur « 'NoneType' object has no attribute 'query' » en pleine résolution.
        sims = self.vecs @ query
        k = min(k, len(self.words))
        top = np.argpartition(sims, -k)[-k:]
        top = top[np.argsort(sims[top])[::-1]]
        return [self.words[i] for i in top]
