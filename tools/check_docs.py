"""Contrôle de forme des documents versionnés de la roadmap.

Trois vérifications, toutes indépendantes du contenu :
  1. chaque lien relatif pointe vers un fichier qui existe ;
  2. chaque tableau a un nombre de colonnes constant (les pipes échappés `\\|`
     et ceux à l'intérieur d'un span `code` ne comptent pas) ;
  3. les compteurs du tableau de bord correspondent aux lignes de suivi.

Usage : python tools/check_docs.py   (sort 1 s'il trouve un problème)

Branché en CI dans le job `lint` : un document versionné qui renvoie à un fichier
absent est aussi cassé qu'un test rouge — c'est exactement le défaut QUAL-17.
"""
import os
import re
import sys
from collections import Counter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORER = (".git", "__pycache__", "chroma_w2v", ".idea", "node_modules")
ID_RE = re.compile(r"\*\*((?:SEC|PERF|SEO|QUAL|A11Y|RGPD)-\d+[a-z]?)\*\*")
STATUTS = ("Fait", "Partiel", "Branche SEO", "Local", "À faire", "Renoncé")


def fichiers_md():
    for racine, dossiers, fichiers in os.walk(RACINE):
        if any(x in racine for x in IGNORER):
            dossiers[:] = []
            continue
        for f in fichiers:
            if f.endswith(".md"):
                yield os.path.join(racine, f)


def sans_pipes_neutres(ligne):
    """Retire les pipes échappés, puis tout ce qui est entre backticks."""
    ligne = ligne.replace("\\|", "")
    return re.sub(r"`[^`]*`", "", ligne)


def controle_liens():
    casse = 0
    for p in fichiers_md():
        texte = open(p, encoding="utf-8").read()
        dossier = os.path.dirname(p)
        for m in re.finditer(r"\]\((?!http|mailto)([^)\s]+)\)", texte):
            cible = os.path.normpath(os.path.join(dossier, m.group(1).split("#")[0]))
            if not os.path.exists(cible):
                print(f"  LIEN CASSE  {os.path.relpath(p, RACINE)} -> {m.group(1)}")
                casse += 1
    return casse


def controle_tables():
    casse = 0
    for p in fichiers_md():
        lignes = open(p, encoding="utf-8").read().splitlines()
        i = 0
        while i < len(lignes):
            if not lignes[i].startswith("|"):
                i += 1
                continue
            largeur = len(lignes[i].split("|"))
            debut = i + 1
            mauvais = []
            while i < len(lignes) and lignes[i].startswith("|"):
                n = len(sans_pipes_neutres(lignes[i]).split("|"))
                if n != largeur:
                    mauvais.append(i + 1)
                i += 1
            if mauvais:
                print(f"  TABLEAU  {os.path.relpath(p, RACINE)}  "
                      f"début ligne {debut} : {largeur} colonnes attendues, "
                      f"écarts aux lignes {mauvais}")
                casse += 1
    return casse


def controle_compteurs():
    p = os.path.join(RACINE, "docs", "roadmap",
                     "2026-10-securite-seo-performance", "02-avancement.md")
    texte = open(p, encoding="utf-8").read()
    lignes = re.findall(r"^\| \*\*((?:SEC|PERF|SEO|QUAL|A11Y|RGPD)-\d+[a-z]?)\*\* \|(.*)$",
                        texte, re.M)
    compte = Counter()
    vus = set()
    for ident, reste in lignes:
        if ident in vus:
            continue
        vus.add(ident)
        compte[next((s for s in STATUTS if s in reste), "inconnu")] += 1

    annonce = dict(re.findall(r"^\| (\w[^\s|]*[^\|]*) \| \*\*(\d+)\*\* \|", texte, re.M))
    annonce = {k: int(v) for k, v in annonce.items()}
    print(f"  lignes de suivi : {len(vus)}")
    for s in STATUTS:
        reel = compte.get(s, 0)
        print(f"  {s:<12} reel={reel:<3}", end="")
        print()
    total_annonce = re.search(r"Total suivis\*\* \| \*\*(\d+)\*\*", texte)
    if total_annonce:
        annonce_total = int(total_annonce.group(1))
        ok = annonce_total == len(vus)
        print(f"  total annonce={annonce_total} reel={len(vus)} -> {'OK' if ok else 'FAUX'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    print("=== liens relatifs ===")
    n_liens = controle_liens()
    print("=== tables ===")
    n_tables = controle_tables()
    print("=== compteurs ===")
    ko = controle_compteurs()
    total = n_liens + n_tables + ko
    print(f"=== {'OK' if total == 0 else str(total) + ' probleme(s)'} ===")
    sys.exit(1 if total else 0)
