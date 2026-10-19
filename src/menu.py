"""
Cémantix Solver — Menu Interactif Principal
============================================
Menu textuel ergonomique et complet permettant d'exécuter l'ensemble des
fonctionnalités du solveur Cémantix en mode interactif :
- Résolution du puzzle du jour (en ligne) en mode Hybride ou RAG pur
  (avec réglage à la volée du nombre de graines et de répétitions consécutives)
- Jeu interactif Solo et Duel croisé Humain vs IA RAG
- Mode Battle comparatif (100% RAG Pur vs Hybride LLM)
- Simulations locales Mock (IA seule) et Benchmark autonome multi-parties
- Réglages dynamiques des paramètres et options avancées
- Support universel de la commande /menu sur n'importe quel écran
"""
import copy
import sys

import numpy as np

from .config import BOLD, CYAN, GREEN, YELLOW, DIM, RESET, LLM_MODEL, LM_API, log
from .vocab import VocabStore
from .clients import MockClient, CemantixClient
from .solvers import Solver
from .modes import run_benchmark, run_battle, run_solo_loop, run_duel_loop
from .ui import render_main_menu, render_settings_menu, clear_screen


class ReturnToMenu(Exception):
    """Exception signalant un retour immédiat demandé au menu principal via /menu."""
    pass


def prompt_choice(prompt_text: str, default: str = "") -> str:
    """Lit une entrée utilisateur avec gestion propre de Ctrl+C, Ctrl+D et retour /menu."""
    try:
        raw = input(prompt_text).strip().strip('\ufeff')
        if raw.lower() in ("/menu", "menu", "/accueil"):
            raise ReturnToMenu()
        return raw if raw else default
    except (KeyboardInterrupt, EOFError):
        return ""


def run_main_menu(args, store: VocabStore = None):
    """Boucle principale du menu interactif de Cémantix Solver."""
    store = store or VocabStore()
    duel_stats = {
        "human": 0,
        "ai": 0,
        "draws": 0,
        "match": 0,
        "difficulty": getattr(args, "difficulty", "moyen"),
    }
    notice = None

    while True:
        render_main_menu(args, notice=notice)
        notice = None

        try:
            choice = prompt_choice(f"Votre choix ([1-7] ou [Q]uitter) [1] > ", default="1").lower()
            if not choice:
                log("\n👋  Au revoir !\n")
                return

            action_notice, should_quit = handle_menu_action(choice, args, store, duel_stats)
            if should_quit:
                return
            if action_notice:
                notice = action_notice
        except ReturnToMenu:
            notice = "↩️  Retour au menu principal."
            continue


def handle_menu_action(choice: str, args, store: VocabStore, duel_stats: dict) -> tuple[str | None, bool]:
    """Exécute l'action associée au choix utilisateur.

    Retourne un tuple (notice, should_quit).
    """
    notice = None

    # ------------------------------------------------------------------- #
    # 1. Résolution du puzzle du jour (en ligne)
    # ------------------------------------------------------------------- #
    if choice == "1":
        clear_screen()
        curr_seeds = getattr(args, "seed_count", 16)
        log("─" * 76)
        log(f"🎯  {BOLD}RÉSOLUTION DU PUZZLE DU JOUR (EN LIGNE SUR CERTITUDES.ORG){RESET}")
        log("─" * 76)
        log(f"  🌱 Amorçage actuel : {curr_seeds} graines pluridisciplinaires")
        log("")
        log("  [1] 🤖  Hybride RAG + Local LLM (recommandé)")
        log("  [2] ⚡  100% RAG Pur Mathématique (Ridge + Rerank — Zéro LLM)")
        log("  [R] ↩️   Retour au menu principal")
        log("─" * 76)
        sub_c = prompt_choice("Mode de résolution ([1] Hybride / [2] RAG Pur / [R]etour) [1] > ", default="1").lower()
        if sub_c in ("r", "retour"):
            return None, False

        sub_args = copy.deepcopy(args)
        sub_args.mock = False
        sub_args.secret = None

        if sub_c == "2":
            sub_args.rag_only = True
            engine_name = "100% RAG Pur Mathématique (Zéro LLM)"
        else:
            sub_args.rag_only = False
            engine_name = f"Hybride RAG + Local LLM ({LLM_MODEL})"

        raw_seeds = prompt_choice(f"Nombre de graines d'amorçage [{curr_seeds}] > ", default=str(curr_seeds))
        try:
            sub_args.seed_count = max(0, int(raw_seeds))
            args.seed_count = sub_args.seed_count
        except ValueError:
            sub_args.seed_count = curr_seeds

        raw_runs = prompt_choice("Nombre de résolutions consécutives du même puzzle [1] > ", default="1")
        try:
            n_runs = max(1, int(raw_runs))
        except ValueError:
            n_runs = 1

        results = []
        for run_idx in range(1, n_runs + 1):
            if n_runs > 1:
                log("\n" + "=" * 65)
                log(f"🔄  RÉSOLUTION {run_idx} / {n_runs} — {engine_name}")
                log(f"🌱  Graines d'amorçage : {sub_args.seed_count}")
                log("=" * 65)
            else:
                log("\n" + "=" * 65)
                log(f"🎯  CÉMANTIX SOLVER — {engine_name}")
                log(f"🌱  Graines d'amorçage : {sub_args.seed_count}")
                log("=" * 65)

            try:
                solver = Solver(sub_args, store=store, game=CemantixClient(delay=sub_args.delay))
                res = solver.run()
                results.append(res)
            except Exception as e:
                log(f"\n❌ Erreur lors de la résolution #{run_idx} : {e}")
                results.append({"word": "erreur", "tries": 0, "win": False, "source": None, "time": 0.0})

        if n_runs > 1 and results:
            wins = [r for r in results if r.get("win")]
            tries_list = [r["tries"] for r in wins]
            times_list = [r["time"] for r in results if "time" in r and r["time"] > 0]

            log("\n" + "=" * 70)
            log(f"📊  BILAN GLOBAL — {n_runs} RÉSOLUTIONS DU PUZZLE DU JOUR")
            log("=" * 70)
            log(f"  Mode                 : {engine_name}")
            log(f"  Graines par partie   : {sub_args.seed_count}")
            log(f"  Taux de victoire     : {len(wins)} / {n_runs} ({len(wins)/n_runs*100:.1f}%)")
            if tries_list:
                log(f"  Essais moyen         : {np.mean(tries_list):.1f}")
                log(f"  Essais médian        : {np.median(tries_list):.0f}")
                log(f"  Essais min / max     : {np.min(tries_list)} / {np.max(tries_list)}")
                sniper_wins = sum(1 for r in wins if r.get("source") == "rag")
                llm_wins = sum(1 for r in wins if r.get("source") == "llm")
                seed_wins = sum(1 for r in wins if r.get("source") == "seed")
                log(f"  Victoires RAG/Sniper : {sniper_wins} ({sniper_wins/len(wins)*100:.1f}%)")
                log(f"  Victoires LLM        : {llm_wins} ({llm_wins/len(wins)*100:.1f}%)")
                if seed_wins:
                    log(f"  Victoires graines    : {seed_wins}")
            if times_list:
                log(f"  Temps moyen          : {np.mean(times_list):.1f}s (total: {sum(times_list):.1f}s)")

            log("\nDétail par manche :")
            for idx, r in enumerate(results, 1):
                st = "✓" if r.get("win") else "✗"
                mot = r.get("word", "?")
                t_str = f"({r['time']:.1f}s)" if "time" in r else ""
                log(f"  Résolution {idx:>2} : {st} {mot:<18} en {r.get('tries', 0):>3} essais {t_str} (source: {r.get('source', '-')})")
            log("=" * 70)

            notice = f"✓ {len(wins)}/{n_runs} résolutions réussies (moyenne: {np.mean(tries_list):.1f} essais)" if tries_list else f"{len(wins)}/{n_runs} résolutions terminées."
        elif results:
            res = results[0]
            if res and res.get("win"):
                notice = f"✓ Puzzle du jour résolu avec succès en {res.get('tries')} essais !"
            else:
                notice = "ℹ️ Session de résolution terminée."

        prompt_choice("\n[Entrée] pour revenir au menu principal...")
        return notice, False

    # ------------------------------------------------------------------- #
    # 2. Mode Jeu Solo
    # ------------------------------------------------------------------- #
    elif choice == "2":
        secret_arg = getattr(args, "secret", None)
        mode = "solo"
        while mode == "solo":
            mode, secret_arg = run_solo_loop(store, secret_arg)
            if mode == "duel":
                mode = run_duel_loop(store, stats=duel_stats, initial_difficulty=getattr(args, "difficulty", "moyen"))
        return None, False

    # ------------------------------------------------------------------- #
    # 3. Mode Duel Croisé
    # ------------------------------------------------------------------- #
    elif choice == "3":
        mode = "duel"
        while mode == "duel":
            mode = run_duel_loop(store, stats=duel_stats, initial_difficulty=getattr(args, "difficulty", "moyen"))
            if mode == "solo":
                mode, _ = run_solo_loop(store)
        return None, False

    # ------------------------------------------------------------------- #
    # 4. Mode Battle comparatif
    # ------------------------------------------------------------------- #
    elif choice == "4":
        clear_screen()
        log("─" * 76)
        log(f"🥊  {BOLD}MODE BATTLE COMPARATIF (100% RAG Pur vs Hybride LLM){RESET}")
        log("─" * 76)
        log("  [1] 🎯  En direct sur le puzzle du jour Cémantix (en ligne)")
        log("  [2] 🎲  Sur mot(s) secret(s) simulé(s) aléatoire(s) (en local)")
        log("  [3] ✍️   Sur mot(s) imposé(s) personnalisé(s) (en local)")
        log("  [R] ↩️   Retour au menu principal")
        log("─" * 76)
        b_c = prompt_choice("Cible du Battle ([1] En ligne / [2] Aléatoire / [3] Imposé / [R]etour) [1] > ", default="1").lower()
        if b_c in ("r", "retour"):
            return None, False

        sub_args = copy.deepcopy(args)
        if b_c == "1":
            sub_args.mock = False
            sub_args.words = 1
            sub_args.secrets = ""
        elif b_c == "2":
            sub_args.mock = True
            sub_args.secrets = ""
            raw_words = prompt_choice("Nombre de mots secrets distincts à tester [1] > ", default="1")
            try:
                sub_args.words = max(1, int(raw_words))
            except ValueError:
                sub_args.words = 1
        elif b_c == "3":
            sub_args.mock = True
            user_secrets = prompt_choice("Mots secrets imposés (séparés par des virgules, ex: volcan,politique) > ")
            if not user_secrets:
                return "⚠️ Aucun mot secret saisi, annulation du Battle.", False
            sub_args.secrets = user_secrets
            sub_args.words = len([w for w in user_secrets.split(",") if w.strip()])
        else:
            return "⚠️ Choix non reconnu.", False

        raw_rounds = prompt_choice("Nombre de manches par mot [1] > ", default="1")
        try:
            rounds = max(1, int(raw_rounds))
        except ValueError:
            rounds = 1

        try:
            run_battle(sub_args, rounds, store=store)
        except Exception as e:
            log(f"\n❌ Erreur durant le Battle : {e}")
        prompt_choice("\n[Entrée] pour revenir au menu principal...")
        return None, False

    # ------------------------------------------------------------------- #
    # 5. Partie simulée en local (Mock)
    # ------------------------------------------------------------------- #
    elif choice == "5":
        clear_screen()
        log("─" * 76)
        log(f"🧪  {BOLD}SIMULATION LOCALE MOCK (IA SEULE SUR MOT SECRET LOCAL){RESET}")
        log("─" * 76)
        log("  [1] 🤖  Hybride RAG + Local LLM (recommandé)")
        log("  [2] ⚡  100% RAG Pur Mathématique (Zéro LLM)")
        log("  [R] ↩️   Retour au menu principal")
        log("─" * 76)
        m_c = prompt_choice("Mode de résolution ([1] Hybride / [2] RAG Pur / [R]etour) [1] > ", default="1").lower()
        if m_c in ("r", "retour"):
            return None, False

        sub_args = copy.deepcopy(args)
        sub_args.mock = True
        sub_args.rag_only = (m_c == "2")

        user_word = prompt_choice("Mot secret cible (laisser vide pour tirage au sort total) > ")
        target_secret = None
        if user_word:
            norm_w = store.normalize(user_word)
            if not store.is_valid_french(norm_w) or norm_w not in store:
                log(f"⚠️  Le mot « {user_word} » n'est pas dans le lexique officiel. Tirage aléatoire.")
                target_secret = None
            else:
                target_secret = norm_w

        mode_str = "100% RAG Pur Mathématique (Zéro LLM)" if sub_args.rag_only else f"Hybride RAG + Local LLM ({LLM_MODEL})"
        log("\n" + "=" * 65)
        log(f"🧪  SIMULATION LOCALE MOCK — {mode_str}")
        if target_secret:
            log(f"🎯  Mot secret imposé : « {target_secret.upper()} »")
        else:
            log("🎲  Mot secret : tiré au sort aléatoirement")
        log("=" * 65)

        try:
            client = MockClient(store, secret=target_secret)
            solver = Solver(sub_args, store=store, game=client)
            res = solver.run()
            notice = f"✓ Simulation terminée en {res.get('tries')} essais (mot : {res.get('word')})."
        except Exception as e:
            log(f"\n❌ Erreur durant la simulation : {e}")
            notice = f"Erreur : {e}"

        prompt_choice("\n[Entrée] pour revenir au menu principal...")
        return notice, False

    # ------------------------------------------------------------------- #
    # 6. Benchmark autonome (N parties)
    # ------------------------------------------------------------------- #
    elif choice == "6":
        clear_screen()
        log("─" * 76)
        log(f"📊  {BOLD}BENCHMARK AUTONOME (ÉVALUATION STATISTIQUE SUR N PARTIES){RESET}")
        log("─" * 76)
        log("  [1] 🤖  Hybride RAG + Local LLM")
        log("  [2] ⚡  100% RAG Pur Mathématique (Zéro LLM)")
        log("  [R] ↩️   Retour au menu principal")
        log("─" * 76)
        bm_c = prompt_choice("Moteur de test ([1] Hybride / [2] RAG Pur / [R]etour) [1] > ", default="1").lower()
        if bm_c in ("r", "retour"):
            return None, False

        sub_args = copy.deepcopy(args)
        sub_args.rag_only = (bm_c == "2")
        sub_args.mock = True
        sub_args.secret = None

        n_str = prompt_choice("Nombre de parties simulées à exécuter [5] > ", default="5")
        try:
            n_games = max(1, int(n_str))
        except ValueError:
            n_games = 5

        try:
            run_benchmark(sub_args, n_games, store=store)
            notice = f"✓ Benchmark de {n_games} parties terminé avec succès."
        except Exception as e:
            log(f"\n❌ Erreur durant le benchmark : {e}")
            notice = f"Erreur : {e}"

        prompt_choice("\n[Entrée] pour revenir au menu principal...")
        return notice, False

    # ------------------------------------------------------------------- #
    # 7. Paramètres & Configuration
    # ------------------------------------------------------------------- #
    elif choice == "7":
        handle_settings_menu(args, store=store)
        return None, False

    # ------------------------------------------------------------------- #
    # Q. Quitter
    # ------------------------------------------------------------------- #
    elif choice in ("q", "quit", "quitter", "exit", "/quit", "/exit"):
        log("\n👋  Merci d'avoir utilisé Cémantix Solver. À bientôt !\n")
        return None, True
    else:
        return f"⚠️ Option « {choice} » non reconnue. Veuillez choisir entre 1 et 7, ou Q.", False


def handle_settings_menu(args, store: VocabStore = None):
    """Gère l'écran interactif de modification des paramètres de session."""
    notice = None
    while True:
        render_settings_menu(args, notice=notice)
        notice = None

        opt = prompt_choice("Modifier un paramètre ([1-9] ou [R]etour) [R] > ", default="r").lower()
        if opt in ("r", "retour", "q", "quit"):
            break

        if opt == "1":
            args.verbose = not getattr(args, "verbose", False)
            st = "activé" if args.verbose else "désactivé"
            notice = f"✓ Mode verbeux (Verbose) {st}."

        elif opt == "2":
            val = prompt_choice(f"Nouvelle limite d'essais max [{getattr(args, 'max_tries', 300)}] > ")
            if val:
                try:
                    args.max_tries = max(1, int(val))
                    notice = f"✓ Limite d'essais fixée à {args.max_tries}."
                except ValueError:
                    notice = "❌ Valeur numérique entière invalide."

        elif opt == "3":
            val = prompt_choice(f"Nouvelle pause réseau en secondes [{getattr(args, 'delay', 0.25)}] > ")
            if val:
                try:
                    args.delay = max(0.0, float(val))
                    notice = f"✓ Pause réseau fixée à {args.delay:.2f}s."
                except ValueError:
                    notice = "❌ Valeur décimale invalide."

        elif opt == "4":
            val = prompt_choice(f"Candidats Rerankés joués par tour [{getattr(args, 'rag_words', 3)}] > ")
            if val:
                try:
                    args.rag_words = max(1, int(val))
                    notice = f"✓ Candidats rerankés fixés à {args.rag_words}."
                except ValueError:
                    notice = "❌ Valeur invalide."

        elif opt == "5":
            val = prompt_choice(f"Mots demandés au LLM par tour [{getattr(args, 'llm_words', 6)}] > ")
            if val:
                try:
                    args.llm_words = max(1, int(val))
                    notice = f"✓ Mots LLM fixés à {args.llm_words}."
                except ValueError:
                    notice = "❌ Valeur invalide."

        elif opt == "6":
            clear_screen()
            log("=" * 76)
            log(f"🌱  {BOLD}STRATÉGIE D'AMORÇAGE DES GRAINES{RESET}")
            log("=" * 76)
            log("  [1] 🧠 Dynamique RAG (sélection pluridisciplinaire dans ChromaDB)")
            log("  [2] 📋 Statique (liste classique de 20 mots)")
            log("  [3] ✍️  Personnalisée (mots saisis à la main)")
            log("─" * 76)
            sub_s = prompt_choice("Votre choix [1] > ", default="1")
            if sub_s == "1":
                args.static_seeds = False
                args.seeds = ""
                raw_cnt = prompt_choice("Nombre de graines pluridisciplinaires [16] > ", default="16")
                try:
                    args.seed_count = max(1, int(raw_cnt))
                except ValueError:
                    args.seed_count = 16
                notice = f"✓ Graines RAG dynamiques activées ({args.seed_count} graines)."
            elif sub_s == "2":
                args.static_seeds = True
                args.seeds = ""
                notice = "✓ Graines statiques (20 mots) activées."
            elif sub_s == "3":
                user_s = prompt_choice("Mots graines (séparés par des virgules) > ")
                if user_s:
                    args.seeds = user_s
                    args.static_seeds = False
                    notice = f"✓ Graines personnalisées configurées : {user_s[:30]}..."
                else:
                    notice = "⚠️ Aucune graine saisie."

        elif opt == "7":
            val = prompt_choice("Niveau duel par défaut ([1] Facile / [2] Moyen / [3] Expert) [2] > ", default="2")
            if val in ("1", "facile"):
                args.difficulty = "facile"
            elif val in ("3", "expert"):
                args.difficulty = "expert"
            else:
                args.difficulty = "moyen"
            notice = f"✓ Niveau duel par défaut fixé à : {args.difficulty.upper()}."

        elif opt == "8":
            args.rag_only = not getattr(args, "rag_only", False)
            engine_str = "100% RAG Pur" if args.rag_only else "Hybride RAG + Local LLM"
            notice = f"✓ Moteur de résolution par défaut basculé sur : {engine_str}."

        elif opt == "9":
            clear_screen()
            log("=" * 70)
            log(f"ℹ️   {BOLD}MODÈLE ET ENDPOINT LLM LOCAL{RESET}")
            log("=" * 70)
            log(f"  Modèle configuré : {LLM_MODEL}")
            log(f"  Endpoint API     : {LM_API}")
            log("")
            log("  Pour modifier ces réglages au démarrage, vous pouvez définir")
            log("  les variables d'environnement suivantes dans votre terminal :")
            log("    set LLM_MODEL=<votre-modele>")
            log("    set LM_API=http://localhost:1234/v1")
            log("─" * 70)
            prompt_choice("\n[Entrée] pour continuer...")
        else:
            notice = f"⚠️ Option « {opt} » non reconnue."
