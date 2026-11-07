"""Générateur de logos vectoriels/matriciels sobres pour Cémantix Solver.
Produit des PNG nets à 120x120 et 512x512 en stdlib Python pure (sans dépendance).
"""
import math
import struct
import zlib
from pathlib import Path

BG = (13, 17, 23)          # #0d1117
BG_CARD = (22, 27, 34)     # #161b22
BORDER = (48, 54, 61)      # #30363d
ACCENT = (88, 166, 255)    # #58a6ff
WHITE = (240, 246, 252)    # #f0f6fc
CORE_RED = (248, 113, 113) # #f87171

STOPS = [
    (0.00, (56, 189, 248)),  # Bleu glacial
    (0.35, (52, 211, 153)),  # Vert frais
    (0.68, (251, 191, 36)),  # Jaune tiède / chaud
    (1.00, (248, 113, 113)), # Rouge brûlant / Top 1000
]

def interpolate_color(t: float):
    t = min(max(t, 0.0), 1.0)
    for idx in range(1, len(STOPS)):
        t0, c0 = STOPS[idx - 1]
        t1, c1 = STOPS[idx]
        if t <= t1:
            ratio = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(c0[i] + (c1[i] - c0[i]) * ratio) for i in range(3))
    return STOPS[-1][1]

def make_png(size: int, pixels: bytearray) -> bytes:
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
        + chunk(b"IDAT", zlib.compress(bytes(pixels), 9))
        + chunk(b"IEND", b"")
    )

def is_in_squircle(x: float, y: float, size: float, r: float) -> bool:
    """Vérifie si (x, y) est dans un rectangle à coins arrondis."""
    if x < r and y < r:
        return math.hypot(x - r, y - r) <= r
    if x > size - r and y < r:
        return math.hypot(x - (size - r), y - r) <= r
    if x < r and y > size - r:
        return math.hypot(x - r, y - (size - r)) <= r
    if x > size - r and y > size - r:
        return math.hypot(x - (size - r), y - (size - r)) <= r
    return 0 <= x <= size and 0 <= y <= size

def render_concept_c_thermo(size: int) -> bytes:
    """Concept 1 : Le 'C' formé par l'arc thermométrique avec cible centrale."""
    cx = cy = (size - 1) / 2.0
    r_corner = size * 0.22
    arc_r = size * 0.32
    arc_w = size * 0.055
    target_r = size * 0.08
    target_core = size * 0.035

    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            if not is_in_squircle(x, y, size, r_corner):
                raw.extend((0, 0, 0, 0)) # transparent extérieur
                continue

            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            angle_deg = (math.degrees(math.atan2(dy, dx)) + 360) % 360

            # Bordure subtile du badge
            dist_border = min(x, y, size - 1 - x, size - 1 - y)
            is_border = (x < 2 or y < 2 or x >= size - 2 or y >= size - 2)

            color = BG
            alpha = 255

            # Arc Cémantix en forme de 'C' (ouvert entre 320° et 40°)
            is_opening = (angle_deg > 325 or angle_deg < 35)
            if abs(dist - arc_r) <= arc_w and not is_opening:
                # Progression du froid (35°) au chaud (325°)
                prog = (angle_deg - 35) / (325 - 35)
                color = interpolate_color(prog)
            # Boutons arrondis aux extrémités du C
            else:
                p1x = cx + arc_r * math.cos(math.radians(35))
                p1y = cy + arc_r * math.sin(math.radians(35))
                p2x = cx + arc_r * math.cos(math.radians(325))
                p2y = cy + arc_r * math.sin(math.radians(325))
                if math.hypot(x - p1x, y - p1y) <= arc_w:
                    color = STOPS[0][1] # Bleu froid
                elif math.hypot(x - p2x, y - p2y) <= arc_w:
                    color = STOPS[-1][1] # Rouge brûlant
                # Cible centrale
                elif dist <= target_core:
                    color = WHITE
                elif dist <= target_r:
                    color = CORE_RED
                elif abs(dist - size * 0.20) <= 1.0:
                    color = BORDER

            raw.extend((*color, alpha))
    return make_png(size, raw)

def render_concept_target_canon(size: int) -> bytes:
    """Concept 2 : La cible sémantique canonique (la charte épurée du projet)."""
    cx = cy = (size - 1) / 2.0
    r_corner = size * 0.22
    outer = size * 0.33
    outer_w = size * 0.038
    inner = size * 0.20
    inner_w = size * 0.022
    core = size * 0.075
    core_white = size * 0.03

    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            if not is_in_squircle(x, y, size, r_corner):
                raw.extend((0, 0, 0, 0))
                continue

            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            color = BG
            alpha = 255

            if abs(dist - outer) <= outer_w:
                angle = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                color = interpolate_color(angle)
            elif abs(dist - inner) <= inner_w:
                color = ACCENT
            elif dist <= core_white:
                color = WHITE
            elif dist <= core:
                color = CORE_RED
            elif (abs(dx) <= 1 and abs(dist - inner) <= outer_w * 2) or (abs(dy) <= 1 and abs(dist - inner) <= outer_w * 2):
                color = BORDER

            raw.extend((*color, alpha))
    return make_png(size, raw)

def render_concept_tile_c(size: int) -> bytes:
    """Concept 3 : Tuile lexicale sobre avec lettre C et barre thermique officielle."""
    cx = cy = (size - 1) / 2.0
    r_corner = size * 0.22

    # Tuile interne
    margin = size * 0.16
    t_left, t_top = margin, margin
    t_right, t_bottom = size - margin, size - margin
    t_r = size * 0.08

    # Lettre C
    c_r = size * 0.18
    c_w = size * 0.038

    # Barre de température sous la lettre
    bar_y = size * 0.72
    bar_h = size * 0.035
    bar_left = size * 0.26
    bar_right = size * 0.74

    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            if not is_in_squircle(x, y, size, r_corner):
                raw.extend((0, 0, 0, 0))
                continue

            dx, dy = x - cx, y - (cy - size * 0.04)
            dist_c = math.hypot(dx, dy)
            angle_deg = (math.degrees(math.atan2(dy, dx)) + 360) % 360

            color = BG
            alpha = 255

            # Tuile de mot
            is_tile = (t_left <= x <= t_right and t_top <= y <= t_bottom)
            if is_tile:
                color = BG_CARD

            # Lettre C dans la tuile
            is_opening = (angle_deg > 315 or angle_deg < 45)
            if is_tile and abs(dist_c - c_r) <= c_w and not is_opening:
                color = WHITE
            # Boutons arrondis du C
            elif is_tile and math.hypot(x - (cx + c_r * math.cos(math.radians(45))), y - ((cy - size * 0.04) + c_r * math.sin(math.radians(45)))) <= c_w:
                color = WHITE
            elif is_tile and math.hypot(x - (cx + c_r * math.cos(math.radians(315))), y - ((cy - size * 0.04) + c_r * math.sin(math.radians(315)))) <= c_w:
                color = WHITE
            # Barre thermométrique en bas de la tuile
            elif bar_left <= x <= bar_right and abs(y - bar_y) <= bar_h:
                t = (x - bar_left) / (bar_right - bar_left)
                color = interpolate_color(t)

            raw.extend((*color, alpha))
    return make_png(size, raw)

if __name__ == "__main__":
    out_dir = Path("/app/volumes/web/icons")
    artifact_dir = Path("/artifact") if Path("/artifact").exists() else out_dir

    generators = [
        ("c_thermo", render_concept_c_thermo),
        ("target_canon", render_concept_target_canon),
        ("tile_c", render_concept_tile_c),
    ]

    for name, func in generators:
        for sz in (120, 512):
            filename = f"logo_{name}_{sz}.png"
            blob = func(sz)
            (out_dir / filename).write_bytes(blob)
            print(f"Generated {filename} ({sz}x{sz}, {len(blob)} bytes)")
