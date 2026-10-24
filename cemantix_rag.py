#!/usr/bin/env python3
"""
Cémantix RAG Solver — Stratégie B (espace word2vec frWac)
=========================================================
Point d'entrée principal et CLI du projet Cémantix Solver.

Modes disponibles :
  - Démon 24h/24 (--daemon : veille et résolution quotidienne chaque nuit à 00h00)
  - Autonome (Hybride LLM ou 100% RAG pur via --rag-only)
  - Simulation Benchmark (--benchmark N ou --mock)
  - Tournoi Battle (--battle N ou --secrets ...)
  - Jeu interactif Solo / Duel croisé (--play ou --duel)

Architecture modulaire (package src/) :
  - src/config.py   : Constantes, styles ANSI, chemins et configuration LLM
  - src/vocab.py    : VocabStore (lexique, word2vec, embeddings ChromaDB)
  - src/clients.py  : Client API officiel (CemantixClient) & simulation locale (MockClient)
  - src/ui.py       : Rendu console, jauges ASCII, dashboard duel & débriefing
  - src/solvers.py  : Algorithmes Ridge, Rerank, interface LLM & solveurs (Solver, RagDuelPlayer)
  - src/modes.py    : Boucles d'orchestration (benchmark, battle, solo, duel)
  - src/daemon.py   : Démon planificateur 24h/24 (veille et résolution quotidienne à 00h00)
"""
import argparse
import sys

from src.config import LLM_MODEL, log
from src.ui import clear_screen
from src.solvers import Solver
from src.modes import run_benchmark, run_battle, run_game
from src.menu import run_main_menu
from src.daemon import run_daemon_loop


def main():
    clear_screen()
    has_cli_options = len(sys.argv) > 1

    ap = argparse.ArgumentParser(description="Solveur Cémantix par RAG local (frWac)")
    ap.add_argument("--menu", "-i", "--interactive", action="store_true",
                    help="ouvre le menu interactif principal")
    ap.add_argument("--daemon", action="store_true",
                    help="lance le mode démon 24h/24 : veille permanente et résolution du mot du jour chaque nuit à 00h00")
    ap.add_argument("--no-run-on-start", action="store_true",
                    help="en mode démon, ne résout pas immédiatement si non résolu, attend le prochain cycle de 00h00")
    ap.add_argument("--max-tries", type=int, default=300)
    ap.add_argument("--retrieve", type=int, default=60,
                    help="nb de voisins récupérés par requête ChromaDB")
    ap.add_argument("--rag-words", type=int, default=3,
                    help="nb de candidats rerankés joués directement par tour (défaut : 3 en hybride, 5 en RAG pur)")
    ap.add_argument("--llm-words", type=int, default=6,
                    help="nb de mots demandés au LLM par tour")
    ap.add_argument("--rag-only", "--no-llm", action="store_true", dest="rag_only",
                    help="mode 100%% RAG mathématique pur (zéro appel LLM, descente Ridge + rerank seuls)")
    ap.add_argument("--delay", type=float, default=0.25,
                    help="pause entre deux requêtes au site (s)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="affiche les détails internes (Ridge, Rerank, Prompt et Reasoning du LLM)")
    ap.add_argument("--seeds", type=str, default="",
                    help="mots graines séparés par des virgules (ex: --seeds 'micro,questionner,revue,publier')")
    ap.add_argument("--seeds-file", type=str, default="",
                    help="chemin vers un fichier de mots graines (un par ligne)")
    ap.add_argument("--seed-count", type=int, default=12,
                    help="nombre de mots graines à tester lors de l'amorçage pluridisciplinaire (défaut : 12)")
    ap.add_argument("--static-seeds", action="store_true",
                    help="utiliser l'ancienne liste fixe de 20 graines au lieu de l'extraction RAG")
    ap.add_argument("--mock", action="store_true",
                    help="mode mock : simule une partie en local avec un mot secret tiré au sort")
    ap.add_argument("--secret", type=str, default=None,
                    help="mot secret forcé en mode mock (si omis, tirage au sort total)")
    ap.add_argument("--words", type=int, default=1,
                    help="nombre de mots secrets distincts à tester en mode battle (défaut : 1)")
    ap.add_argument("--secrets", type=str, default="",
                    help="liste de mots secrets imposés séparés par des virgules (ex: --secrets 'volcan,politique,astronomie')")
    ap.add_argument("--benchmark", type=int, default=0,
                    help="exécute N parties simulées à la suite et affiche les statistiques globales")
    ap.add_argument("--battle", type=int, nargs="?", const=1, default=0,
                    help="mode battle comparatif (N manches sur le MÊME mot) : 100%% RAG Pur vs Hybride RAG+LLM. Par défaut en direct sur le mot du jour Cémantix, ou en local avec --mock")
    ap.add_argument("--play", "--game", action="store_true", dest="play_mode",
                    help="mode jeu interactif : tire un mot au sort en local et vous laisse deviner avec le calcul vectoriel")
    ap.add_argument("--duel", action="store_true",
                    help="lance directement le mode duel croisé humain vs IA RAG")
    ap.add_argument("--difficulty", "-d", choices=["facile", "moyen", "expert"], default="moyen",
                    help="niveau de difficulté de l'IA en mode duel (facile, moyen, expert; défaut: moyen)")
    args = ap.parse_args()

    # Lancement automatique du menu interactif si aucun argument CLI n'est passé ou si --menu est spécifié
    if not has_cli_options or args.menu:
        run_main_menu(args)
        return

    if args.daemon:
        run_daemon_loop(args)
        return

    if args.duel:
        args.play_mode = True

    is_rag_only = getattr(args, "rag_only", False)
    mode_str = "100% RAG Pur Mathématique (Zéro LLM)" if is_rag_only else f"Hybride RAG + Local LLM ({LLM_MODEL})"

    if args.play_mode:
        run_game(args)
    elif args.battle > 0 or args.words > 1 or bool(args.secrets):
        battle_rounds = args.battle if args.battle > 0 else 1
        run_battle(args, battle_rounds)
    elif args.benchmark > 0:
        run_benchmark(args, args.benchmark)
    elif args.mock:
        run_benchmark(args, 1)
    else:
        log("=" * 60)
        log(f"🎯  CÉMANTIX SOLVER — {mode_str}")
        log("=" * 60)
        Solver(args).run()


if __name__ == "__main__":
    sys.exit(main())
