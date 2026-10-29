"""Générateur d'icônes PNG sans dépendance (stdlib uniquement).

Dessine la cible thermométrique du projet et écrit un PNG carré, utilisé comme
`apple-touch-icon` et icône de secours pour les navigateurs sans SVG.
"""
import math
import struct
import zlib
from pathlib import Path

BG = (13, 17, 23)          # --bg-app
ACCENT = (88, 166, 255)    # --accent
CORE = (248, 113, 113)     # --tier-fire
STOPS = [(0.0, (56, 189, 248)), (0.35, (52, 211, 153)), (0.65, (251, 191, 36)), (1.0, (248, 113, 113))]


def gradient(t: float):
    """Interpole la dégradée thermique pour une position t dans [0, 1]."""
    t = min(max(t, 0.0), 1.0)
    for idx in range(1, len(STOPS)):
        t0, c0 = STOPS[idx - 1]
        t1, c1 = STOPS[idx]
        if t <= t1:
            ratio = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(c0[i] + (c1[i] - c0[i]) * ratio) for i in range(3))
    return STOPS[-1][1]


def render(size: int) -> bytes:
    """Compose l'image RGBA et renvoie les octets PNG correspondants."""
    cx = cy = (size - 1) / 2.0
    outer = size * 0.33
    outer_w = size * 0.024
    inner = size * 0.19
    inner_w = size * 0.018
    core = size * 0.06

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filtre "None" par scanline
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            color = BG
            if abs(dist - outer) <= outer_w:
                angle = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                color = gradient(angle)
            elif abs(dist - inner) <= inner_w:
                color = ACCENT
            elif dist <= core:
                color = CORE
            raw.extend(color)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "volumes" / "web" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    for target, px in (("apple-touch-icon.png", 180), ("icon-512.png", 512)):
        blob = render(px)
        (out_dir / target).write_bytes(blob)
        print(f"{target}: {px}x{px}, {len(blob)} octets")
