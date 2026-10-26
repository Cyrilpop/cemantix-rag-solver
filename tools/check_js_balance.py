"""Vérifie l'équilibre des délimiteurs d'un fichier JS, sans dépendance externe.

Approximation volontaire : les littéraux de chaîne, les gabarits (`...`) et les
commentaires sont ignorés, mais **les expressions régulières ne sont pas
distinguées des divisions**. Un fichier qui contient un guillemet ou une accolade
dans une regex — `.replace(/"/g, "&quot;")` — sera donc signalé à tort.

Ce faux positif est assumé : l'outil sert de garde-fou rapide après une retouche
manuelle, là où aucun `node` n'est disponible pour un vrai `--check`. Un signal
doit être relu, pas exécuté aveuglément.

    python tools/check_js_balance.py volumes/web/js/multi.js ...
"""
import sys

PAIRS = {"(": ")", "[": "]", "{": "}"}
OPENERS = set(PAIRS)
CLOSERS = {v: k for k, v in PAIRS.items()}
BACKSLASH = chr(92)


def check(path: str) -> str:
    source = open(path, encoding="utf-8").read()
    i, n, line = 0, len(source), 1
    stack = []

    while i < n:
        char = source[i]

        if char == "\n":
            line += 1
            i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                if source[i] == "\n":
                    line += 1
                i += 1
            i += 2
            continue

        if char in "\"'`":
            quote = char
            i += 1
            while i < n:
                if source[i] == BACKSLASH:
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                if source[i] == "\n":
                    line += 1
                i += 1
            continue

        if char in OPENERS:
            stack.append((char, line))
        elif char in CLOSERS:
            if not stack:
                return f"{path}:{line} : fermant '{char}' sans ouvrant"
            opener, opener_line = stack.pop()
            if PAIRS[opener] != char:
                return (
                    f"{path}:{line} : attendu '{PAIRS[opener]}' "
                    f"(ouvrant '{opener}' ligne {opener_line}), reçu '{char}'"
                )
        i += 1

    if stack:
        opener, opener_line = stack[-1]
        return f"{path} : '{opener}' ouvert ligne {opener_line} jamais fermé"
    return f"{path} : équilibre OK"


if __name__ == "__main__":
    failed = False
    for target in sys.argv[1:]:
        result = check(target)
        print(result)
        failed = failed or "OK" not in result
    sys.exit(1 if failed else 0)
