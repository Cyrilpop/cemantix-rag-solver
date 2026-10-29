"""Outil de diagnostic de l'image de partage Open Graph.

Le projet ne dépend d'aucune bibliothèque de traitement d'image, et l'environnement
de développement n'en fournit aucune (ni Pillow, ni ImageMagick). Ce script se contente
donc de mesurer l'écart entre l'image réellement servie et ce que déclarent les
balises, et indique la commande de correction.

    python tools/check_og_image.py     → diagnostic, code de sortie 1 si hors norme

Le fichier `og-image.jpg` actuel pèse 2,95 Mo pour du 2752×1536, alors que les balises
`og:image:width/height` annoncent 1200×630 : chaque partage social et chaque crawl
paient 3 Mo pour une vignette affichée en 1200 px. Facebook redimensionne de toute
façon et recommande de rester sous 1 Mo.

Correction (ImageMagick ou ffmpeg, à exécuter sur la machine qui héberge l'image) :

    convert volumes/web/og-image.jpg -resize 1200x630 -quality 82 volumes/web/og-image.jpg
    ffmpeg -i volumes/web/og-image.jpg -vf scale=1200:630 -q:v 3 volumes/web/og-image.jpg

Puis relancer ce script : le poids doit passer sous 200 ko et le code de sortie à 0.
"""
import argparse
import struct
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OG_IMAGE = BASE_DIR / "volumes" / "web" / "og-image.jpg"
INDEX_HTML = BASE_DIR / "volumes" / "web" / "index.html"

# Dimensions annoncées par les balises et recommandées par les clients sociaux.
TARGET_W, TARGET_H = 1200, 630
# Seuils : Facebook recadre au-delà de 1 Mo, mais l'objectif utile est bien plus bas.
HARD_LIMIT = 1_000_000
TARGET_LIMIT = 200_000


def jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    """Retourne (largeur, hauteur) en lisant le marqueur de début de trame JPEG."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        segment_length = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + segment_length
    return None


def declared_dimensions(path: Path) -> tuple[str, str]:
    """Lit `og:image:width` et `og:image:height` déclarés dans le HTML."""
    import re
    html = path.read_text(encoding="utf-8")
    width = re.search(r'og:image:width"\s+content="(\d+)"', html)
    height = re.search(r'og:image:height"\s+content="(\d+)"', html)
    return (width.group(1) if width else "?", height.group(1) if height else "?")


def diagnose() -> int:
    """Affiche le diagnostic et retourne un code de sortie non nul si hors norme."""
    if not OG_IMAGE.exists():
        print(f"✖ {OG_IMAGE.name} introuvable")
        return 1

    size = OG_IMAGE.stat().st_size
    dims = jpeg_dimensions(OG_IMAGE)
    declared_w, declared_h = declared_dimensions(INDEX_HTML)

    print(f"Fichier      : {OG_IMAGE.name}")
    print(f"Poids réel   : {size:,} octets ({size / 1_048_576:.2f} Mo)")
    print(f"Dimensions   : {dims[0]}×{dims[1]}" if dims else "Dimensions   : illisibles")
    print(f"Balises OG   : {declared_w}×{declared_h}")

    problems = []
    if dims and (dims[0] != TARGET_W or dims[1] != TARGET_H):
        problems.append(
            f"dimensions {dims[0]}×{dims[1]} ≠ {TARGET_W}×{TARGET_H} annoncés "
            f"(les clients sociaux redimensionnent, le poids est payé deux fois)"
        )
    if size > HARD_LIMIT:
        problems.append(f"{size / 1_048_576:.2f} Mo dépasse la limite stricte de 1 Mo (Facebook)")
    elif size > TARGET_LIMIT:
        problems.append(f"{size / 1_048_576:.2f} Mo au-dessus de l'objectif de 200 ko")

    if problems:
        print("\n[!] Problemes :")
        for problem in problems:
            print(f"   - {problem}")
        print("\n-> Regenere une vignette 1200x630 avec un encodeur externe, par exemple :")
        print("    convert volumes/web/og-image.jpg -resize 1200x630 -quality 82 volumes/web/og-image.jpg")
        print("  ou : ffmpeg -i volumes/web/og-image.jpg -vf scale=1200:630 "
              "-q:v 3 volumes/web/og-image.jpg")
        return 1

    print("\n[OK] Conforme : dimensions attendues et poids sous l'objectif.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostic de l'image Open Graph")
    parser.parse_args()
    sys.exit(diagnose())
