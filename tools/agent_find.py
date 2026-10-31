#!/usr/bin/env python3
"""
Outil de découverte ciblée de symboles pour agents IA (M0.1).
Permet de localiser immédiatement fonctions, classes et routes sans lire de gros fichiers.

Usage:
    python tools/agent_find.py <nom_symbole_ou_mot_clé>
    python tools/agent_find.py --route <chemin_route>
    python tools/agent_find.py --summary <fichier>

Zéro dépendance externe (stdlib Python uniquement : ast, os, re, sys).
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
                            matches.append((str(rel), idx, idx, "function", name))
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
    print("Top repères :")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("class ", "def ", "function ", "export function ")) or (stripped.startswith("# ---") and len(stripped) > 10):
            print(f"  L{i:4d}: {stripped[:75]}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/agent_find.py <symbole>")
        print("       python tools/agent_find.py --summary <fichier>")
        sys.exit(1)

    if sys.argv[1] == "--summary" and len(sys.argv) > 2:
        file_summary(sys.argv[2])
        return

    query = sys.argv[1]
    py_matches = find_python_symbols(query, BASE_DIR / "src")
    test_matches = find_python_symbols(query, BASE_DIR / "tests")
    js_matches = find_js_symbols(query, BASE_DIR / "volumes" / "web" / "js")

    all_matches = py_matches + test_matches + js_matches
    if not all_matches:
        print(f"Aucun symbole trouvé pour : « {query} »")
        sys.exit(0)

    print(f"🔍 Résultats pour « {query} » ({len(all_matches)} trouvé(s)) :")
    for filepath, start, end, kind, name in all_matches:
        span = f"L{start}-L{end}" if start != end else f"L{start}"
        print(f"  - {filepath}:{span} -> {kind} {name}")
    print("\n💡 Pour lire uniquement la plage utile dans l'agent :")
    f, s, e, _, _ = all_matches[0]
    print(f"   read_file(Path='{f}', StartLine={max(1, s-2)}, EndLine={e+5})")


if __name__ == "__main__":
    main()
