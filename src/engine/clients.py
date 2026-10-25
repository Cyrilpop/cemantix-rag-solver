"""
Cémantix Solver — Clients API & Simulation Locale (src.engine.clients)
======================================================================
Fournit les interfaces de jeu :
- CemantixClient : client HTTP communiquant avec l'API officielle de Cémantix.
- MockClient : simulateur local haute performance pour l'entraînement,
  les benchmarks et les duels hors-ligne.
"""
import time
import re
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import urllib3.util.connection as urllib3_conn
import numpy as np

from ..config import SITE, HEADERS, STOPWORDS, log

# Force la résolution IPv4 pour éviter l'erreur [Errno 101] Network is unreachable
# fréquente sous Docker / WSL2 due à l'absence de routage IPv6 dans le bridge.
urllib3_conn.allowed_gai_family = lambda: socket.AF_INET


class CemantixClient:
    """Client HTTP pour le jeu officiel en direct sur https://cemantix.certitudes.org/."""
    def __init__(self, delay: float = 0.25, max_retries: int = 3):
        self.delay = delay
        self.max_retries = max_retries
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": HEADERS["User-Agent"]})

        # Configuration de la résilience réseau (retries automatiques sur micro-coupures)
        retry_strategy = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.s.mount("https://", adapter)
        self.s.mount("http://", adapter)

        log(f"🌐  Connexion à {SITE}...")
        html = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                r = self.s.get(SITE + "/", timeout=15)
                html = r.text
                break
            except requests.RequestException as e:
                last_error = e
                if attempt < max_retries:
                    log(f"⚠️  Connexion temporairement indisponible (tentative {attempt}/{max_retries}) : {e}. Réessai...")
                    time.sleep(attempt)
                else:
                    log(f"❌  Échec de connexion à {SITE} après {max_retries} tentatives : {e}")

        if not html:
            raise RuntimeError(f"Impossible de joindre {SITE} : {last_error}")

        m = re.search(r'data-puzzle-number="(\d+)"', html)
        if not m:
            raise RuntimeError("Numéro du puzzle introuvable dans la page.")
        self.puzzle = int(m.group(1))
        log(f"✓  Puzzle du jour détecté : n°{self.puzzle}")

    def score(self, word: str):
        """Retourne (cosinus, permille|None), ou None si le site ne connaît pas le mot."""
        for attempt in range(self.max_retries):
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
        k = min(1000, len(all_cos))
        self.p1000_threshold = float(np.partition(all_cos, -k)[-k])
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
