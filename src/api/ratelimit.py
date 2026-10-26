"""
Cémantix Solver — Limiteur de Requêtes en Mémoire
=================================================
Seau à jetons par clé (adresse IP) pour protéger les endpoints de jeu sans
dépendance externe. L'API tourne derrière Caddy, mais Caddy ne limite pas le
nombre de requêtes : un client malveillant pourrait sinon créer des milliers de
sessions et saturer la mémoire du conteneur.

Le compteur est volontairement borné : les clés inactives sont purgées pour
éviter que le dictionnaire ne croisse sans limite.
"""
import threading
import time
from typing import Optional


class RateLimiter:
    """Seau à jetons par clé, thread-safe et à mémoire bornée."""

    def __init__(
        self,
        default_capacity: float = 240.0,
        refill_per_second: float = 4.0,
        burst_capacity: Optional[float] = None,
        idle_ttl: float = 900.0,
        max_keys: int = 20000,
    ):
        self.default_capacity = float(default_capacity)
        self.refill_per_second = float(refill_per_second)
        self.burst_capacity = float(burst_capacity if burst_capacity is not None else default_capacity)
        self.idle_ttl = float(idle_ttl)
        self.max_keys = int(max_keys)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0, capacity: Optional[float] = None) -> tuple[bool, float]:
        """Consomme `cost` jetons pour `key`.

        Renvoie `(autorisé, secondes_avant_nouvelle_tentative)`.
        """
        limit = float(capacity if capacity is not None else self.default_capacity)
        now = time.monotonic()

        with self._lock:
            tokens, last = self._buckets.get(key, (limit, now))
            tokens = min(limit, tokens + (now - last) * self.refill_per_second)

            if tokens < cost:
                wait = (cost - tokens) / self.refill_per_second if self.refill_per_second else 1.0
                self._buckets[key] = (tokens, now)
                self._purge(now)
                return False, wait

            self._buckets[key] = (tokens - cost, now)
            self._purge(now)
            return True, 0.0

    def _purge(self, now: float) -> None:
        """Retire les clés oisives ; doit être appelé sous verrou."""
        if len(self._buckets) <= self.max_keys:
            return
        expired = [k for k, (_, last) in self._buckets.items() if now - last > self.idle_ttl]
        for key in expired:
            self._buckets.pop(key, None)
        # Toujours sous la borne : on vide les plus anciens si nécessaire.
        while len(self._buckets) > self.max_keys:
            oldest = min(self._buckets.items(), key=lambda item: item[1][1])[0]
            self._buckets.pop(oldest, None)
