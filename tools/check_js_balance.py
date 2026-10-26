"""Vérifie l'équilibre des délimiteurs d'un fichier JS, sans dépendance externe.

Les commentaires, les chaînes, les gabarits (`...`) et les expressions régulières
sont reconnus et ignorés : un délimiteur qui s'y trouve ne compte pas. Deux
ambiguïtés du JavaScript sont tranchées par le contexte :

- **regex ou division** — un `/` n'ouvre une regex que s'il suit un opérateur, un
  mot-clé, une ponctuation de fin d'expression ou le début du fichier. Après un
  identifiant ou un nombre, c'est une division. Sans cette règle, la regex de
  `.replace(/"/g, "&quot;")` est lue comme une chaîne et le fichier, pourtant
  valide, est signalé comme cassé ;
- **`/` dans un gabarit** — une fonction de rendu renvoie souvent `<span>…</span>` :
  à l'intérieur d'un template literal, aucun `/` n'ouvre de regex.

Les interpolations `${…}` sont suivies par une pile de compteurs, ce qui autorise
les gabarits imbriqués dans une interpolation.

Approximation assumée, pas un parseur : l'outil attrape les décalages de bloc
introduits par une retouche manuelle, là où aucun `node --check` n'est disponible.
Un signal doit être relu, pas exécuté aveuglément.

    python tools/check_js_balance.py volumes/web/js/*.js
"""
import sys

PAIRS = {"(": ")", "[": "]", "{": "}"}
OPENERS = set(PAIRS)
CLOSERS = {v: k for k, v in PAIRS.items()}
BACKSLASH = chr(92)

REGEX_PRECEDERS = set("([{,;:!&|?+-*%<>~^=")
KEYWORDS_BEFORE_REGEX = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete",
    "void", "case", "do", "else", "yield", "await",
}
CONDITION_KEYWORDS = {"if", "while", "for", "with"}


def _word_before(source: str, index: int) -> str:
    """Identifiant placé immédiatement avant `index` (vide si aucun)."""
    j = index - 1
    while j >= 0 and (source[j].isalnum() or source[j] in "_$"):
        j -= 1
    return source[j + 1:index]


def _last_significant(source: str, index: int):
    """Dernier caractère non blanc avant `index`, en sautant les commentaires."""
    j = index - 1
    while j >= 0:
        char = source[j]
        if char.isspace():
            j -= 1
        elif char == "/" and j > 0 and source[j - 1] == "*":
            start = source.rfind("/*", 0, j)
            if start == -1:
                return char, j
            j = start - 1
        else:
            return char, j
    return None, -1


def _matching_open_paren(source: str, close_index: int):
    """Index de la `(` appariée à la `)` placée en `close_index`."""
    depth = 0
    for i in range(close_index, -1, -1):
        if source[i] == ")":
            depth += 1
        elif source[i] == "(":
            depth -= 1
            if depth == 0:
                return i
    return None


def _slash_starts_regex(source: str, index: int) -> bool:
    """Décide si le `/` de `index` ouvre une regex ou effectue une division.

    Le cas piège est `.replace(/"/g, "&quot;")` : le caractère significatif
    précédent est la `(` d'une **liste d'arguments**, et non d'une condition. Une
    liste d'arguments ne peut pas se terminer par une valeur, donc le `/` qui la
    suit ouvre forcément une regex — sinon la regex échapperait au scan, le
    guillemet de `&quot;` ouvrirait une chaîne et le fichier valide serait déclaré
    cassé.
    """
    prev, prev_index = _last_significant(source, index)
    if prev is None or prev in REGEX_PRECEDERS or prev == "}":
        return True
    if prev == ")":
        opener = _matching_open_paren(source, index - 1)
        if opener is None:
            return True
        # `if (x) /re/.test(y)` : regex. `(a + b) / c` : division.
        if _word_before(source, opener) in CONDITION_KEYWORDS:
            return True
        return False
    if prev == "]":
        return False
    if prev.isalnum() or prev in "_$":
        return _word_before(source, index) in KEYWORDS_BEFORE_REGEX
    return True



def _skip_regex(source: str, index: int, n: int) -> int:
    """Retourne l'index suivant le `/` fermant d'une regex monoligne."""
    i, in_class = index + 1, False
    while i < n:
        char = source[i]
        if char == BACKSLASH:
            i += 2
            continue
        if char == "\n":
            return i
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return i + 1
        i += 1
    return i


def _skip_template_text(source: str, index: int, n: int):
    """Consomme le texte d'un gabarit jusqu'au backtick ou a une interpolation.

    Retourne `(index, termine)` : `termine` est vrai si le gabarit s'est ferme ici,
    faux si l'on s'arrete sur une interpolation `${` a traiter par la boucle
    principale. Le decompte de lignes est remonte par l'appelant via le texte
    consomme, pour garder une seule source de verite.
    """
    i = index
    while i < n:
        char = source[i]
        if char == BACKSLASH:
            i += 2
            continue
        if char == "`":
            return i + 1, True
        if char == "$" and source[i + 1:i + 2] == "{":
            return i + 2, False
        i += 1
    return i, True


def check(path: str) -> str:
    """Vérifie que chaque `( [ {` du fichier est refermée dans le bon ordre."""
    source = open(path, encoding="utf-8").read()
    n = len(source)
    i, line = 0, 1
    stack = []            # (ouvrant, ligne) en attente de fermeture
    template_depths = []  # interpolations ouvertes pour chaque gabarit en cours

    while i < n:
        char = source[i]

        if char == "\n":
            line += 1
            i += 1
            continue

        if char == "/" and source[i + 1:i + 2] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if char == "/" and source[i + 1:i + 2] == "*":
            start = i
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            line += source.count("\n", start, i)
            i += 2
            continue

        if char in "\"'":
            quote = char
            start = i
            i += 1
            while i < n:
                if source[i] == BACKSLASH:
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                if source[i] == "\n":
                    break  # chaîne non fermée : la lecture reprend ici
                i += 1
            line += source.count("\n", start, i)
            continue

        if char == "`":
            start = i
            i, closed = _skip_template_text(source, i + 1, n)
            line += source.count("\n", start, i)
            if closed:
                continue
            # Arrêté sur `${` : on empile l'accolade pour que sa `}` ferme
            # proprement l'interpolation et nous ramène dans le texte du gabarit.
            stack.append(("{", line))
            template_depths.append(1)
            continue

        if char == "/" and not template_depths and _slash_starts_regex(source, i):
            i = _skip_regex(source, i, n)
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
            # La `}` qui referme l'interpolation `${…}` (déjà dépilée ci-dessus) :
            # on repart dans le texte du gabarit, où ni accolades ni `/` ne comptent.
            if char == "}" and template_depths and template_depths[-1] > 0:
                template_depths.pop()
                start = i
                i, closed = _skip_template_text(source, i + 1, n)
                line += source.count("\n", start, i)
                if not closed:
                    stack.append(("{", line))
                    template_depths.append(1)
                continue
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
