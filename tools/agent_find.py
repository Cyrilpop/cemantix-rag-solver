#!/usr/bin/env python3
"""
Outil de découverte ciblée de symboles pour agents IA (M0.1 & M5).
Permet de localiser immédiatement fonctions, classes, routes et éléments DOM
sans saturer la fenêtre de contexte par des lectures massives.

Usage:
    python tools/agent_find.py <nom_symbole_ou_mot_clé>
    python tools/agent_find.py --summary <fichier>
    python tools/agent_find.py --safe-html <fichier_html> [Lstart] [Lend]

Zéro dépendance externe (stdlib Python uniquement : ast, os, re, sys, pathlib).
"""
import ast
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git", "__pycache__", ".pytest_cache", "chroma_w2v",
    "node_modules", "dist", "roadmap", "audits"
}


def find_python_symbols(query: str, root: Path):
    matches = []
    q = query.lower()
    for path in root.rglob("*.py"):
        if any(exc in path.parts for exc in EXCLUDED_DIRS):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if q in node.name.lower():
                        rel = path.relative_to(BASE_DIR)
                        end = getattr(node, "end_lineno", node.lineno)
                        kind = "class" if isinstance(node, ast.ClassDef) else "def"
                        matches.append((str(rel), node.lineno, end, kind, node.name))
        except Exception:
            continue
    return sorted(matches, key=lambda x: (x[0], x[1]))


def find_js_symbols(query: str, root: Path):
    matches = []
    q = query.lower()
    fn_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)"
        r"|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>"
    )
    for path in root.rglob("*.js"):
        if any(exc in path.parts for exc in EXCLUDED_DIRS):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, 1):
                    m = fn_re.search(line)
                    if m:
                        name = m.group(1) or m.group(2)
                        if name and q in name.lower():
                            rel = path.relative_to(BASE_DIR)
                            matches.append((str(rel), idx, idx, "js-function", name))
        except Exception:
            continue
    return sorted(matches, key=lambda x: (x[0], x[1]))


def find_html_symbols(query: str, root: Path):
    matches = []
    q = query.lower()
    id_re = re.compile(r'id=["\']([^"\']+)["\']')
    tag_re = re.compile(r'<(header|nav|main|footer|dialog|section|form)\b([^>]*)', re.I)

    for path in root.rglob("*.html"):
        if any(exc in path.parts for exc in EXCLUDED_DIRS):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, 1):
                    # Recherche d'identifiants
                    for m in id_re.finditer(line):
                        el_id = m.group(1)
                        if q in el_id.lower():
                            rel = path.relative_to(BASE_DIR)
                            matches.append((str(rel), idx, idx, "html-id", f"#{el_id}"))

                    # Recherche de balises structurelles majeures
                    tag_match = tag_re.search(line)
                    if tag_match:
                        tag_name = tag_match.group(1).lower()
                        attrs = tag_match.group(2)
                        if q in tag_name:
                            rel = path.relative_to(BASE_DIR)
                            id_in_tag = id_re.search(attrs)
                            desc = f"<{tag_name}" + (f' id="{id_in_tag.group(1)}"' if id_in_tag else "") + ">"
                            matches.append((str(rel), idx, idx, "html-tag", desc))
        except Exception:
            continue
    return sorted(matches, key=lambda x: (x[0], x[1]))


def file_summary(filepath_str: str):
    p = BASE_DIR / filepath_str
    if not p.exists():
        print(f"❌ Fichier introuvable : {filepath_str}")
        return
    size = p.stat().st_size
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    print(f"📄 {filepath_str} : {len(lines)} lignes | {size:,} octets | ~{size // 4:,} tokens")

    # Détection spécifique HTML et avertissement CSS critique
    if p.suffix.lower() == ".html":
        critical_line = None
        critical_len = 0
        for i, line in enumerate(lines, 1):
            if '<style id="critical-css"' in line:
                critical_line = i
                critical_len = len(line)
                break

        if critical_line:
            tokens_saved = critical_len // 4
            print(f"⚠️  CSS critique généré inliné : L{critical_line} ({critical_len:,} car. | ~{tokens_saved:,} tokens)")
            print(f"💡 Conseil de navigation : inspecter L1-L{critical_line-1} ou L{critical_line+3}-L{len(lines)} pour préserver le contexte.")
            print(f"   Ou utiliser : python tools/agent_find.py --safe-html {filepath_str}")

        print("Repères structurels HTML :")
        landmark_re = re.compile(r'<(header|nav|main|footer|dialog|section|form)\b[^>]*id=["\']([^"\']+)["\']|<(header|nav|main|footer)\b', re.I)
        for i, line in enumerate(lines, 1):
            if i == critical_line:
                continue
            m = landmark_re.search(line)
            if m:
                tag = m.group(1) or m.group(3)
                el_id = m.group(2)
                ident = f"#{el_id}" if el_id else ""
                print(f"  L{i:4d}: <{tag}{ident}> {line.strip()[:65]}")
        return

    print("Top repères :")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("class ", "def ", "function ", "export function ")) or (stripped.startswith("# ---") and len(stripped) > 10):
            print(f"  L{i:4d}: {stripped[:75]}")


def safe_read_html(filepath_str: str, start: int = 1, end: int = None):
    """Affiche les lignes d'un fichier HTML en masquant le bloc CSS critique généré."""
    p = BASE_DIR / filepath_str
    if not p.exists():
        print(f"❌ Fichier introuvable : {filepath_str}")
        return

    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    total = len(lines)
    s = max(1, start)
    e = min(total, end) if end else total

    print(f"=== {filepath_str} (L{s}-L{e} sur {total} lignes, CSS critique masqué) ===")
    for i in range(s, e + 1):
        line = lines[i - 1]
        if '<style id="critical-css"' in line:
            m = re.search(r'data-bundle=["\']([^"\']+)["\']', line)
            bundle = m.group(1) if m else "css"
            print(f"/* L{i} */ <style id=\"critical-css\" data-bundle=\"{bundle}\">/* [CSS critique masqué: {len(line):,} octets — généré par tools/build_css_bundles.py] */</style>")
        else:
            print(f"/* L{i} */ {line.rstrip()}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/agent_find.py <symbole>")
        print("       python tools/agent_find.py --summary <fichier>")
        print("       python tools/agent_find.py --safe-html <fichier_html> [Lstart] [Lend]")
        sys.exit(1)

    if sys.argv[1] == "--summary" and len(sys.argv) > 2:
        file_summary(sys.argv[2])
        return

    if sys.argv[1] == "--safe-html" and len(sys.argv) > 2:
        start_line = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        end_line = int(sys.argv[4]) if len(sys.argv) > 4 else None
        safe_read_html(sys.argv[2], start_line, end_line)
        return

    query = sys.argv[1]
    py_matches = find_python_symbols(query, BASE_DIR / "src")
    test_matches = find_python_symbols(query, BASE_DIR / "tests")
    js_matches = find_js_symbols(query, BASE_DIR / "volumes" / "web" / "js")
    html_matches = find_html_symbols(query, BASE_DIR / "volumes" / "web")

    all_matches = py_matches + test_matches + js_matches + html_matches
    if not all_matches:
        print(f"Aucun symbole trouvé pour : « {query} »")
        sys.exit(0)

    print(f"🔍 Résultats pour « {query} » ({len(all_matches)} trouvé(s)) :")
    for filepath, start, end, kind, name in all_matches:
        span = f"L{start}-L{end}" if start != end else f"L{start}"
        print(f"  - {filepath}:{span} -> [{kind}] {name}")
    print("\n💡 Pour lire uniquement la plage utile dans l'agent :")
    f, s, e, _, _ = all_matches[0]
    print(f"   read_file(Path='{f}', StartLine={max(1, s-2)}, EndLine={e+5})")


if __name__ == "__main__":
    main()
