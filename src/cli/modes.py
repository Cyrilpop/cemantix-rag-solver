"""
Cémantix Solver — Modes de Jeu & Orchestration
===============================================
Gestion des différents modes d'exécution :
- Benchmark autonome (évaluation de précision sur N parties)
- Battle comparatif (100% RAG Mathématique pur vs Hybride LLM)
- Jeu interactif Solo (tableau de bord, indices sémantiques, historique)
- Mode Duel croisé Humain vs IA RAG (adversaire IA configurable, espionnage tactique)
- Orchestrateur de session globale (run_game)
"""
import copy
import time

import numpy as np

from ..config import (
    BOLD, RESET, LLM_MODEL, STOPWORDS, ENGLISH_WORDS, DISCIPLINES, log
)
from ..engine import CemantixClient, MockClient, RagDuelPlayer, Solver, VocabStore, estimate_secret
from .ui import (
    clear_screen, weather_for_score, render_game_board,
    render_duel_board, render_duel_debrief
)


# --------------------------------------------------------------------------- #
# Mode Benchmark
# --------------------------------------------------------------------------- #
def run_benchmark(args, n_games: int, store: VocabStore = None):
    is_rag_only = getattr(args, "rag_only", False)
    mode_label = "⚡ 100% RAG Mathématique pur (Ridge + Rerank — Zéro LLM)" if is_rag_only else f"🤖 Hybride RAG + Local LLM ({LLM_MODEL})"
    log("=" * 65)
    log(f"🏆  LANCEMENT DU BENCHMARK AUTONOME ({n_games} parties simulées)")
    log(f"⚙   Mode : {mode_label}")
    log("=" * 65)
    store = store or VocabStore()
    results = []
    
    for game_idx in range(1, n_games + 1):
        log(f"\n{'#' * 65}")
        log(f"🎮  PARTIE {game_idx} / {n_games}")
        log(f"{'#' * 65}")
        solver = Solver(args, store=store, game=MockClient(store, secret=args.secret))
        res = solver.run()
        results.append(res)
    
    # Rapport statistique final
    log("\n" + "=" * 65)
    log("📊  RAPPORT DE BENCHMARK FINAL")
    log("=" * 65)
    wins = [r for r in results if r["win"]]
    tries_list = [r["tries"] for r in wins]
    sources = [r["source"] for r in wins]
    
    log(f"  Mode                 : {mode_label}")
    log(f"  Parties jouées       : {len(results)}")
    log(f"  Taux de victoire     : {len(wins)} / {len(results)} ({len(wins)/len(results)*100:.1f}%)")
    if tries_list:
        log(f"  Essais moyen         : {np.mean(tries_list):.1f}")
        log(f"  Essais médian        : {np.median(tries_list):.0f}")
        log(f"  Essais min / max     : {np.min(tries_list)} / {np.max(tries_list)}")
        sniper_wins = sum(1 for s in sources if s == "rag")
        llm_wins = sum(1 for s in sources if s == "llm")
        seed_wins = sum(1 for s in sources if s == "seed")
        log(f"  Victoires RAG/Sniper : {sniper_wins} ({sniper_wins/len(wins)*100:.1f}%)")
        log(f"  Victoires LLM        : {llm_wins} ({llm_wins/len(wins)*100:.1f}%)")
        if seed_wins:
            log(f"  Victoires direct Seed: {seed_wins}")
    log("\nDétail par partie :")
    for idx, r in enumerate(results, 1):
        status = "✓" if r["win"] else "✗"
        log(f"  Partie {idx:>2} : {status} {r['word']:<18} en {r['tries']:>2} essais  (source: {r['source']})")
    log("=" * 65 + "\n")


# --------------------------------------------------------------------------- #
# Mode Battle comparatif : 100% RAG pur vs Hybride LLM
# --------------------------------------------------------------------------- #
def run_battle(args, n_rounds: int, store: VocabStore = None):
    if getattr(args, "rag_only", False):
        log("ℹ️   [INFO] L'option --rag-only est ignorée en mode Battle : le duel oppose par définition 100% RAG Pur vs Hybride LLM.")
    store = store or VocabStore()

    # Détermination de la liste des mots secrets
    if getattr(args, "secrets", ""):
        raw_list = [store.normalize(w.strip()) for w in args.secrets.split(",") if w.strip()]
        words_list = [w for w in raw_list if w in store and store.is_valid_french(w)]
        if not words_list:
            raise ValueError(f"Aucun mot secret valide trouvé dans l'option --secrets : '{args.secrets}'.")
        is_mock = True
    elif getattr(args, "words", 1) > 1:
        n_words = args.words
        pool = store.clean_french_words if store.clean_french_words else store.words
        cands = [w for w in pool if len(w) >= 4 and w not in STOPWORDS
                 and not w.endswith(('es', 'eaux', 'eux', 'aux'))
                 and not (w.endswith('s') and not w.endswith(('is', 'us', 'as', 'ps', 'os')))]
        words_list = list(np.random.choice(cands, size=min(n_words, len(cands)), replace=False))
        is_mock = True
    elif getattr(args, "secret", None):
        secret_norm = store.normalize(args.secret)
        if secret_norm not in store or not store.is_valid_french(secret_norm):
            raise ValueError(f"Le mot secret imposé '{args.secret}' est introuvable ou non conforme.")
        words_list = [secret_norm]
        is_mock = True
    elif getattr(args, "mock", False):
        ref_mock = MockClient(store)
        words_list = [ref_mock.secret]
        is_mock = True
    else:
        # Mode LIVE par défaut : 1 seul mot (le puzzle officiel du jour)
        words_list = [None]
        is_mock = False

    total_words = len(words_list)
    total_matches = total_words * n_rounds

    log("=" * 70)
    log("⚔️   GRAND TOURNOI BATTLE : 100% RAG PUR  vs  HYBRIDE RAG + LLM")
    mode_txt = "MOCK LOCAL" if is_mock else "LIVE CÉMANTIX"
    log(f"⚔️   Mode : {mode_txt} | {total_words} mot(s) secret(s) × {n_rounds} round(s) = {total_matches} duel(s)")
    log("=" * 70)

    tournament_words_summary = []
    all_battle_results = []

    for word_idx, secret in enumerate(words_list, 1):
        word_display = secret.upper() if secret else "PUZZLE DU JOUR"
        if total_words > 1:
            log("\n" + "╔" + "═" * 68 + "╗")
            log(f"║ 🎯  MOT SECRET {word_idx:>2}/{total_words} : {word_display:<48} ║")
            log("╚" + "═" * 68 + "╝")
        elif is_mock:
            mock_desc = f"« {secret.upper()} »" if args.secret or args.secrets else "« ... » (tiré au sort pour le tournoi)"
            log(f"🎲  Mode : MOCK LOCAL | Mot secret fixé pour les {n_rounds} manche(s) : {mock_desc}")
        else:
            log(f"🌐  Mode : LIVE CÉMANTIX | Affrontement sur le mot du jour officiel ({n_rounds} manche(s))")

        # Pré-génération des graines communes pour les n_rounds de ce mot
        rounds_seeds = []
        dummy_game = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
        for k in range(1, n_rounds + 1):
            seeds_k = Solver(args, store=store, game=dummy_game).get_seeds()
            rounds_seeds.append(seeds_k)

        # =====================================================================
        # PHASE 1 : SÉRIE DU COMBATTANT A — ⚡ 100% RAG Pur (Manches 1 à N)
        # =====================================================================
        log("\n" + "█" * 70)
        log(f"⚡  PHASE 1 : SÉRIE COMBATTANT A — 100% RAG Pur ({n_rounds} manche(s))")
        log("█" * 70)
        results_a = []
        args_rag = copy.deepcopy(args)
        args_rag.rag_only = True
        args_rag.no_llm = True

        for k in range(1, n_rounds + 1):
            log(f"\n--- [100% RAG PUR] Manche {k}/{n_rounds} ---")
            game_a = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
            solver_a = Solver(args_rag, store=store, game=game_a)
            res_a = solver_a.run(forced_seeds=rounds_seeds[k - 1])
            results_a.append(res_a)

        # =====================================================================
        # PHASE 2 : SÉRIE DU COMBATTANT B — 🤖 Hybride RAG + LLM (Manches 1 à N)
        # =====================================================================
        log("\n" + "█" * 70)
        log(f"🤖  PHASE 2 : SÉRIE COMBATTANT B — Hybride RAG + Local LLM ({n_rounds} manche(s))")
        log("█" * 70)
        results_b = []
        args_llm = copy.deepcopy(args)
        args_llm.rag_only = False
        args_llm.no_llm = False

        for k in range(1, n_rounds + 1):
            log(f"\n--- [HYBRIDE LLM] Manche {k}/{n_rounds} ---")
            game_b = MockClient(store, secret=secret) if is_mock else CemantixClient(delay=args.delay)
            solver_b = Solver(args_llm, store=store, game=game_b)
            res_b = solver_b.run(forced_seeds=rounds_seeds[k - 1])
            results_b.append(res_b)

        # Confrontation manche par manche pour ce mot
        log("\n" + "=" * 70)
        log(f"📊  RÉSULTATS DES CONFRONTATIONS — MOT : {word_display}")
        log("=" * 70)
        wins_word_a = 0
        wins_word_b = 0
        draws_word = 0

        for k in range(1, n_rounds + 1):
            res_a = results_a[k - 1]
            res_b = results_b[k - 1]

            if res_a["win"] and not res_b["win"]:
                winner = "⚡ 100% RAG Pur"
                wins_word_a += 1
            elif res_b["win"] and not res_a["win"]:
                winner = "🤖 Hybride LLM"
                wins_word_b += 1
            elif res_a["win"] and res_b["win"]:
                if res_a["tries"] < res_b["tries"]:
                    winner = "⚡ 100% RAG Pur (moins d'essais)"
                    wins_word_a += 1
                elif res_b["tries"] < res_a["tries"]:
                    winner = "🤖 Hybride LLM (moins d'essais)"
                    wins_word_b += 1
                else:
                    winner = "🤝 Égalité d'essais"
                    draws_word += 1
            else:
                winner = "❌ Échec des deux"
                draws_word += 1

            t_a = f"{res_a['time']:.2f}s" if res_a.get("time") else "N/A"
            t_b = f"{res_b['time']:.2f}s" if res_b.get("time") else "N/A"
            log(f"Manche {k:>2}/{n_rounds} : RAG={res_a['tries']:>3} essais ({t_a}) | LLM={res_b['tries']:>3} essais ({t_b}) ➔ Vainqueur : {winner}")
            all_battle_results.append({"word": word_display, "round": k, "res_a": res_a, "res_b": res_b, "winner": winner})

        tournament_words_summary.append({
            "word": word_display,
            "wins_a": wins_word_a,
            "wins_b": wins_word_b,
            "draws": draws_word,
            "avg_tries_a": np.mean([r["tries"] for r in results_a]),
            "avg_tries_b": np.mean([r["tries"] for r in results_b]),
            "avg_time_a": np.mean([r["time"] for r in results_a]),
            "avg_time_b": np.mean([r["time"] for r in results_b]),
        })

    # =========================================================================
    # BILAN GLOBAL DU TOURNOI MULTI-MOTS
    # =========================================================================
    total_duels = len(all_battle_results)
    wins_a = sum(1 for r in all_battle_results if "RAG Pur" in r["winner"])
    wins_b = sum(1 for r in all_battle_results if "Hybride LLM" in r["winner"])
    draws = total_duels - wins_a - wins_b

    log("\n" + "=" * 88)
    log(f"🏆  BILAN GÉNÉRAL DU TOURNOI BATTLE ({total_words} mot(s) secret(s) × {n_rounds} manche(s) = {total_duels} duels)")
    log("=" * 88)

    if total_words > 1:
        log(f"{'Mot secret':<20} | {'Victoires RAG':<14} | {'Victoires LLM':<14} | {'Moy. Essais (RAG/LLM)':<22} | {'Moy. Temps':<15}")
        log("-" * 88)
        for s in tournament_words_summary:
            scores_tries = f"{s['avg_tries_a']:.1f} vs {s['avg_tries_b']:.1f}"
            scores_time = f"{s['avg_time_a']:.1f}s vs {s['avg_time_b']:.1f}s"
            log(f"{s['word']:<20} | {s['wins_a']:>2} ({s['wins_a']/n_rounds*100:4.1f}%)     | {s['wins_b']:>2} ({s['wins_b']/n_rounds*100:4.1f}%)     | {scores_tries:<22} | {scores_time:<15}")
        log("-" * 88)

    tries_a_all = [r["res_a"]["tries"] for r in all_battle_results if r["res_a"]["win"]]
    tries_b_all = [r["res_b"]["tries"] for r in all_battle_results if r["res_b"]["win"]]
    time_a_all = [r["res_a"]["time"] for r in all_battle_results]
    time_b_all = [r["res_b"]["time"] for r in all_battle_results]

    log("\n📊  STATISTIQUES GLOBALES SUR TOUS LES DUELS :")
    log(f"  Victoires ⚡  100% RAG Pur : {wins_a} / {total_duels} ({wins_a/total_duels*100:.1f}%)")
    log(f"  Victoires 🤖  Hybride LLM  : {wins_b} / {total_duels} ({wins_b/total_duels*100:.1f}%)")
    log(f"  Duels nuls 🤝  : {draws} / {total_duels} ({draws/total_duels*100:.1f}%)")

    if tries_a_all and tries_b_all:
        log("\n🎯  EFFICACITÉ GLOBALE (Nombre d'essais moyen) :")
        log(f"  ⚡  100% RAG Pur  : {np.mean(tries_a_all):.1f} essais (médiane: {np.median(tries_a_all):.0f}, min: {np.min(tries_a_all)}, max: {np.max(tries_a_all)})")
        log(f"  🤖  Hybride LLM   : {np.mean(tries_b_all):.1f} essais (médiane: {np.median(tries_b_all):.0f}, min: {np.min(tries_b_all)}, max: {np.max(tries_b_all)})")

    log("\n⏱️  TEMPS D'EXÉCUTION CUMULÉ :")
    log(f"  ⚡  100% RAG Pur  : {sum(time_a_all):.2f}s au total (moyenne {np.mean(time_a_all):.2f}s/duel)")
    log(f"  🤖  Hybride LLM   : {sum(time_b_all):.2f}s au total (moyenne {np.mean(time_b_all):.2f}s/duel)")
    if sum(time_a_all) > 0:
        log(f"  🚀  Facteur d'accélération RAG : {sum(time_b_all)/max(sum(time_a_all), 0.001):.1f}x plus rapide !")
    log("=" * 88 + "\n" if total_words > 1 else "=" * 70 + "\n")


# --------------------------------------------------------------------------- #
# Mode Jeu Solo
# --------------------------------------------------------------------------- #
def run_solo_loop(store: VocabStore, secret_arg=None):
    game = MockClient(store, secret=secret_arg)
    guesses = {}   # norm -> (s, p, num, w_icon, w_lbl)
    t0 = time.time()
    tries_count = 0
    last_played = None
    notice = None
    view_mode = "top"
    hints = []

    while True:
        render_game_board(game, guesses, last_played=last_played, notice=notice, view_mode=view_mode, hints=hints)
        notice = None

        try:
            raw = input(f"Essai #{tries_count + 1} (ou /duel, /aide, /indice, /rejouer, /abandon) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log(f"\n👋  Partie interrompue. Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} ».")
            return None, None

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("/duel", "duel"):
            return "duel", None
        elif cmd in ("/menu", "menu", "/accueil"):
            return None, None
        elif cmd in ("/quitter", "/quit", "/exit", "exit", "quit"):
            log(f"\n👋  Au revoir ! Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} ».")
            return None, None
        elif cmd in ("/abandon", "/giveup", "/solution"):
            elapsed = time.time() - t0
            log("\n" + "=" * 70)
            log(f"🏳️  Abandon après {tries_count} essai(s) ({elapsed:.1f}s).")
            log(f"💡  Le mot secret était : « {BOLD}{game.secret.upper()}{RESET} »")
            log("=" * 70 + "\n")
            try:
                ans = input("🎮  Que souhaitez-vous faire ? ([O]ui pour rejouer / [D]uel / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None, None
            if ans in ("d", "duel", "/duel"):
                return "duel", None
            if ans in ("m", "menu", "/menu", "/accueil"):
                return None, None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None, None
            return "solo", None
        elif cmd in ("/rejouer", "/nouveau", "/new", "/restart"):
            return "solo", None
        elif cmd in ("/aide", "/help"):
            notice = "Commandes : /duel (mode versus IA), /menu (menu principal), /top, /historique, /indice, /rejouer, /abandon, /quitter"
            continue
        elif cmd in ("/top", "/best"):
            view_mode = "top"
            notice = "Affichage basculé sur le Top des meilleurs essais."
            continue
        elif cmd in ("/historique", "/history"):
            view_mode = "history"
            notice = "Affichage basculé sur l'historique chronologique."
            continue
        elif cmd in ("/indice", "/hint"):
            ranked_words = sorted(guesses.items(), key=lambda x: x[1][0], reverse=True)
            top_word, (best_s, best_p, *_) = ranked_words[0] if ranked_words else (None, (-1.0, None))

            if best_s > 0.10 and top_word:
                v_best = store.vec(top_word)
                v_target = 0.35 * v_best + 0.65 * game.v_secret
                norm_target = np.linalg.norm(v_target)
                v_target = v_target / norm_target if norm_target > 0 else game.v_secret
                cands_knn = store.knn(v_target, k=60)
            else:
                cands_knn = store.knn(game.v_secret, k=150)[40:]

            secret_stem = game.secret[:min(5, len(game.secret))]
            valid_hints = []
            for w in cands_knn:
                w_norm = store.normalize(w)
                if (w_norm not in guesses
                        and w_norm not in hints
                        and w_norm != game.secret
                        and len(w_norm) >= 4
                        and w_norm not in STOPWORDS
                        and not w_norm.startswith(secret_stem)
                        and not game.secret.startswith(w_norm[:min(5, len(w_norm))])
                        and store.is_valid_french(w_norm)):
                    res_hint = game.score(w_norm)
                    if res_hint:
                        s_w, p_w = res_hint
                        if s_w > best_s or (p_w and p_w >= 500) or len(guesses) < 3:
                            valid_hints.append((w_norm, s_w, p_w))

            if not valid_hints:
                # Élargissement si aucun candidat filtré
                for w in store.knn(game.v_secret, k=300)[30:]:
                    w_norm = store.normalize(w)
                    if (w_norm not in guesses
                            and w_norm not in hints
                            and w_norm != game.secret
                            and len(w_norm) >= 4
                            and w_norm not in STOPWORDS
                            and not w_norm.startswith(secret_stem)
                            and not game.secret.startswith(w_norm[:min(5, len(w_norm))])
                            and store.is_valid_french(w_norm)):
                        res_hint = game.score(w_norm)
                        if res_hint:
                            valid_hints.append((w_norm, res_hint[0], res_hint[1]))

            if valid_hints:
                valid_hints.sort(key=lambda x: x[1])
                chosen_hint, s_h, p_h = valid_hints[len(valid_hints) // 2]
                hints.append(chosen_hint)
                # Un indice = 1 coup officiel au compteur
                tries_count += 1
                w_icon, w_lbl = weather_for_score(s_h, p_h)
                guesses[chosen_hint] = (s_h, p_h, tries_count, w_icon, f"{w_lbl} 💡")
                history_guesses.append((tries_count, chosen_hint, s_h, p_h, w_icon, f"{w_lbl} 💡"))
                if s_h > best_score:
                    best_score = s_h
                    best_word = chosen_hint
                rk_info = f"{p_h} ‰" if p_h else f"{s_h*100:+.2f}°C"
                notice = f"💡  Indice #{len(hints)} accordé : « {chosen_hint.upper()} » ({rk_info}, {w_icon}) — (+1 coup comptabilisé, Essai #{tries_count})"
            else:
                notice = "💡  Pas d'indice supplémentaire disponible pour le moment."
            continue


        norm = store.normalize(cmd)
        if norm in guesses:
            s, p, num, w_icon, w_lbl = guesses[norm]
            rk_str = f"{p} ‰" if p else ""
            notice = f"⚠️  Déjà essayé (#{num}) : « {norm} » ({s*100:.2f}°C  {w_icon}  {w_lbl} {rk_str})"
            continue

        if norm in ENGLISH_WORDS:
            notice = f"❌  Mot « {raw} » rejeté (mot anglais non autorisé dans Cémantix)."
            continue

        if not store.is_valid_french(norm) or norm not in store:
            notice = f"❌  Mot « {raw} » non reconnu (lemmes français au singulier uniquement)."
            continue

        res = game.score(norm)
        if res is None:
            notice = f"❌  Mot « {raw} » rejeté par le jeu."
            continue

        s, p = res
        tries_count += 1
        w_icon, w_lbl = weather_for_score(s, p)

        best_score = max([v[0] for v in guesses.values()], default=-1.0)
        is_new_best = (s > best_score) and (s > 0.15)
        guesses[norm] = (s, p, tries_count, w_icon, w_lbl)
        last_played = (norm, s, p, tries_count, w_icon, w_lbl, is_new_best)

        if p == 1000 or norm == game.secret:
            render_game_board(game, guesses, last_played=last_played, view_mode="top", hints=hints)
            elapsed = time.time() - t0
            log("\n" + "🎉" * 25)
            log("🥳  VICTOIRE ! FÉLICITATIONS !")
            log(f"    Vous avez trouvé le mot secret « {BOLD}{game.secret.upper()}{RESET} » !")
            log(f"    Nombre total d'essais : {tries_count}")
            log(f"    Temps de réflexion     : {elapsed:.1f} secondes")
            log("🎉" * 25 + "\n")
            try:
                ans = input("🎮  Que souhaitez-vous faire ? ([O]ui pour rejouer / [D]uel / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None, None
            if ans in ("d", "duel", "/duel"):
                return "duel", None
            if ans in ("m", "menu", "/menu", "/accueil"):
                return None, None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None, None
            return "solo", None


# --------------------------------------------------------------------------- #
# Mode Duel croisé Humain vs IA RAG
# --------------------------------------------------------------------------- #
def run_duel_loop(store: VocabStore, stats: dict | None = None, initial_difficulty: str = "moyen"):
    if stats is None:
        stats = {"human": 0, "ai": 0, "draws": 0, "match": 0, "difficulty": initial_difficulty}
    if "difficulty" not in stats:
        stats["difficulty"] = initial_difficulty
    stats["match"] += 1

    clear_screen()
    log("=" * 89)
    if stats["match"] > 1:
        log(f"⚔️   CÉMANTIX DUEL CROISÉ — MANCHE #{stats['match']} (Score : 🧑   {stats['human']} — {stats['ai']}  🤖)")
    else:
        log("⚔️   CÉMANTIX DUEL CROISÉ — NOUVEAU MATCH")
    log("=" * 89)
    log("L'IA a tiré son mot secret. Paramétrez la manche :\n")

    # Étape 1/2 : Niveau de difficulté de l'IA
    diff_default = stats["difficulty"].capitalize()
    while True:
        try:
            raw_diff = input(f"Étape 1/2 🎚️   Niveau de l'IA ([F]acile, [M]oyen, [E]xpert) [{diff_default}] > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            log("\n👋  Au revoir !")
            return None

        if not raw_diff:
            break
        elif raw_diff in ("/solo", "solo"):
            return "solo"
        elif raw_diff in ("/menu", "menu", "/accueil"):
            return None
        elif raw_diff in ("/quitter", "/quit", "quit", "exit"):
            return None
        elif raw_diff.startswith("f"):
            stats["difficulty"] = "facile"
            break
        elif raw_diff.startswith("e"):
            stats["difficulty"] = "expert"
            break
        elif raw_diff.startswith("m"):
            stats["difficulty"] = "moyen"
            break
        else:
            log("❌  Option invalide. Choisissez [F]acile, [M]oyen ou [E]xpert.")

    log(f"✓   Niveau sélectionné : {BOLD}{stats['difficulty'].upper()}{RESET}\n")

    # Étape 2/2 : Mot secret pour l'IA
    ai_target = None
    while not ai_target:
        try:
            raw = input("Étape 2/2 🎯   Mot secret pour l'IA (Entrée = tirage aléatoire) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log("\n👋  Au revoir !")
            return None

        cmd = raw.lower()
        if not raw or cmd in ("/random", "random"):
            valid_cands = [w for w in store.words if store.is_valid_french(w) and len(w) >= 4 and w not in STOPWORDS]
            ai_target = str(np.random.choice(valid_cands))
            log(f"🎲  Mot secret tiré au sort pour l'IA : « {BOLD}{ai_target.upper()}{RESET} »")
            time.sleep(0.8)
            break

        if cmd in ("/solo", "solo"):
            return "solo"
        if cmd in ("/menu", "menu", "/accueil"):
            return None
        if cmd in ("/quitter", "/quit", "quit", "exit"):
            return None

        norm = store.normalize(cmd)
        if store.is_valid_french(norm) and norm in store:
            ai_target = norm
            log(f"✓   Mot secret de l'IA validé : « {BOLD}{ai_target.upper()}{RESET} »")
            time.sleep(0.8)
            break
        else:
            log(f"❌  Mot « {raw} » non reconnu ou non recevable (lemmes français au singulier uniquement).")

    game_ai = MockClient(store, secret=ai_target)
    ai_player = RagDuelPlayer(store, game_ai, difficulty=stats["difficulty"])
    game_human = MockClient(store)

    guesses_human = {}
    last_human = None
    last_ai = None
    turn_no = 0
    notice = None
    spy_credits = 1
    hints = []

    while True:
        render_duel_board(game_human, guesses_human, last_human,
                          game_ai, ai_player.guesses, last_ai,
                          turn_no + 1, notice=notice, stats=stats, hints=hints)
        notice = None

        try:
            raw = input(f"Tour #{turn_no + 1} > Votre coup (ou /solo, /espion, /indice, /rejouer, /abandon) > ").strip().strip('\ufeff')
        except (KeyboardInterrupt, EOFError):
            log(f"\n👋  Duel interrompu. Votre mot secret était : « {BOLD}{game_human.secret.upper()}{RESET} ».")
            return None

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("/solo", "solo"):
            return "solo"
        elif cmd in ("/menu", "menu", "/accueil"):
            return None
        elif cmd in ("/rejouer", "/nouveau", "/restart"):
            return "duel"
        elif cmd in ("/quitter", "/quit", "/exit", "exit", "quit"):
            log(f"\n👋  Au revoir ! Votre mot secret était : « {BOLD}{game_human.secret.upper()}{RESET} ».")
            return None
        elif cmd in ("/diff", "/difficulte", "/difficulty", "/niveau"):
            notice = f"🎚️   Niveau actuel de l'IA : {stats['difficulty'].upper()} (changez avec /facile, /moyen, /expert)"
            continue
        elif cmd in ("/facile", "facile"):
            stats["difficulty"] = "facile"
            ai_player.difficulty = "facile"
            notice = "✓   Niveau de l'IA basculé sur : FACILE"
            continue
        elif cmd in ("/moyen", "moyen"):
            stats["difficulty"] = "moyen"
            ai_player.difficulty = "moyen"
            notice = "✓   Niveau de l'IA basculé sur : MOYEN"
            continue
        elif cmd in ("/expert", "expert"):
            stats["difficulty"] = "expert"
            ai_player.difficulty = "expert"
            notice = "✓   Niveau de l'IA basculé sur : EXPERT"
            continue
        elif cmd in ("/espion", "espion", "/spy", "spy"):
            if spy_credits <= 0:
                notice = "⚠️   Coup d'espionnage déjà épuisé pour cette manche (1/1 max)."
                continue
            if not ai_player.guesses:
                notice = "⚠️   L'IA n'a pas encore joué de coup à espionner."
                continue

            spy_credits -= 1
            # 1. Quartier sémantique traqué par l'IA
            known_ai = [(w, s) for w, (s, p, *_) in ai_player.guesses.items() if w in store]
            if len(known_ai) >= 2:
                G_ai = np.vstack([store.vec(w) for w, s in known_ai])
                s_ai = np.array([s for w, s in known_ai], dtype=np.float32)
                q_ai = estimate_secret(G_ai, s_ai)
            else:
                q_ai = store.vec(max(known_ai, key=lambda x: x[1])[0])

            disc_scores = []
            for d in DISCIPLINES:
                d_norm = store.normalize(d)
                if d_norm in store:
                    disc_scores.append((d, float(store.vec(d_norm) @ q_ai)))
            disc_scores.sort(key=lambda x: x[1], reverse=True)
            top_disc = f"{disc_scores[0][0]} / {disc_scores[1][0]}"

            # 2. Meilleur essai adverse
            best_ai = max(ai_player.guesses.items(), key=lambda x: x[1][0])
            w_b, (s_b, p_b, num_b, icon_b, lbl_b) = best_ai
            sc_b = f"{p_b} ‰" if p_b else f"{s_b*100:.1f}°C"

            # 3. Alerte proximité
            if p_b and p_b >= 900:
                alert = f"🚨 DANGER BRÛLANT : L'IA est dans le Top 100 ({p_b} ‰) !"
            elif p_b:
                alert = f"⚠️   ALERTE : L'IA est entrée dans le Top 1000 ({p_b} ‰) !"
            elif s_b >= 0.15:
                alert = f"👀 PISTE TIÈDE : L'IA approche votre zone ({s_b*100:.1f}°C)."
            else:
                alert = f"🧊 CALME : L'IA cherche encore dans le froid ({s_b*100:.1f}°C)."

            # 4. Le tour est consommé : l'IA joue son coup !
            turn_no += 1
            w_ai, s_ai, p_ai, icon_ai, lbl_ai = ai_player.play_turn(turn_no)
            last_ai = (w_ai, s_ai, p_ai, turn_no, icon_ai, lbl_ai)
            ai_won = (p_ai == 1000 or w_ai == ai_target)

            notice = (
                f"🕵️   [ESPIONNAGE SÉMANTIQUE — 1/1 UTILISÉ]\n"
                f"    ├── Quartier traqué par l'IA : « {top_disc} »\n"
                f"    ├── Meilleur essai adverse   : [{num_b}] {w_b} ({sc_b} — {icon_b} {lbl_b})\n"
                f"    └── {alert}\n"
                f"    (⚠️   Votre tour a été consommé : l'IA a joué « {w_ai} »)"
            )

            if ai_won:
                render_duel_board(game_human, guesses_human, last_human,
                                  game_ai, ai_player.guesses, last_ai,
                                  turn_no, notice=None, stats=stats, hints=hints)
                render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                    winner="ai", turn_no=turn_no, stats=stats)
                try:
                    ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    return None
                if ans in ("s", "solo", "/solo"):
                    return "solo"
                if ans in ("m", "menu", "/menu", "/accueil"):
                    return None
                if ans in ("n", "non", "q", "quit", "quitter"):
                    return None
                return "duel"

            continue
        elif cmd in ("/abandon", "/giveup"):
            stats["ai"] += 1
            render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                winner="abandon", turn_no=turn_no + 1, stats=stats)
            try:
                ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None
            if ans in ("s", "solo", "/solo"):
                return "solo"
            if ans in ("m", "menu", "/menu", "/accueil"):
                return None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None
            return "duel"
        elif cmd in ("/aide", "/help"):
            notice = "Commandes : /espion (rapport tactique sur l'IA), /solo, /diff, /facile, /moyen, /expert, /indice, /rejouer, /abandon, /quitter"
            continue
        elif cmd in ("/indice", "/hint"):
            ranked_words = sorted(guesses_human.items(), key=lambda x: x[1][0], reverse=True)
            top_word, (best_s, best_p, *_) = ranked_words[0] if ranked_words else (None, (-1.0, None))
            if best_s > 0.10 and top_word:
                v_best = store.vec(top_word)
                v_target = 0.35 * v_best + 0.65 * game_human.v_secret
                norm_tgt = np.linalg.norm(v_target)
                v_target = v_target / norm_tgt if norm_tgt > 0 else game_human.v_secret
                cands_knn = store.knn(v_target, k=60)
            else:
                cands_knn = store.knn(game_human.v_secret, k=150)[40:]

            secret_stem = game_human.secret[:min(5, len(game_human.secret))]
            valid_hints = []
            for w in cands_knn:
                w_norm = store.normalize(w)
                if (w_norm not in guesses_human
                        and w_norm not in hints
                        and w_norm != game_human.secret
                        and len(w_norm) >= 4
                        and w_norm not in STOPWORDS
                        and not w_norm.startswith(secret_stem)
                        and not game_human.secret.startswith(w_norm[:min(5, len(w_norm))])
                        and store.is_valid_french(w_norm)):
                    res_hint = game_human.score(w_norm)
                    if res_hint:
                        s_w, p_w = res_hint
                        if s_w > best_s or (p_w and p_w >= 500) or len(guesses_human) < 3:
                            valid_hints.append((w_norm, s_w, p_w))
            if not valid_hints:
                for w in store.knn(game_human.v_secret, k=300)[30:]:
                    w_norm = store.normalize(w)
                    if (w_norm not in guesses_human
                            and w_norm not in hints
                            and w_norm != game_human.secret
                            and len(w_norm) >= 4
                            and w_norm not in STOPWORDS
                            and not w_norm.startswith(secret_stem)
                            and not game_human.secret.startswith(w_norm[:min(5, len(w_norm))])
                            and store.is_valid_french(w_norm)):
                        res_hint = game_human.score(w_norm)
                        if res_hint:
                            valid_hints.append((w_norm, res_hint[0], res_hint[1]))

            if valid_hints:
                valid_hints.sort(key=lambda x: x[1])
                chosen_hint, s_hint, p_hint = valid_hints[len(valid_hints) // 2]
                hints.append(chosen_hint)
                # Un indice = 1 coup pour l'humain en duel (l'IA répond son coup)
                norm_h = chosen_hint
                rk_info = f"{p_hint} ‰" if p_hint else f"{s_hint*100:+.2f}°C"
                notice = f"💡  Indice #{len(hints)} accordé : « {chosen_hint.upper()} » ({rk_info}) — (+1 coup comptabilisé, l'IA joue son tour)"
            else:
                notice = "💡  Pas d'indice supplémentaire disponible pour le moment."
                continue
        else:
            norm_h = store.normalize(cmd)
            if norm_h in guesses_human:
                notice = f"⚠️   Déjà essayé : « {norm_h} »"
                continue

            if norm_h in ENGLISH_WORDS:
                notice = f"❌   Mot « {raw} » rejeté (mot anglais non autorisé dans Cémantix)."
                continue

            if not store.is_valid_french(norm_h) or norm_h not in store:
                notice = f"❌   Mot « {raw} » non reconnu (lemmes français au singulier uniquement)."
                continue


        res_h = game_human.score(norm_h)
        if res_h is None:
            notice = f"❌   Mot « {raw} » rejeté par le jeu."
            continue

        s_h, p_h = res_h
        turn_no += 1
        icon_h, lbl_h = weather_for_score(s_h, p_h)

        guesses_human[norm_h] = (s_h, p_h, turn_no, icon_h, lbl_h)
        last_human = (norm_h, s_h, p_h, turn_no, icon_h, lbl_h)
        human_won = (p_h == 1000 or norm_h == game_human.secret)

        # Coup de l'IA RAG
        w_ai, s_ai, p_ai, icon_ai, lbl_ai = ai_player.play_turn(turn_no)
        last_ai = (w_ai, s_ai, p_ai, turn_no, icon_ai, lbl_ai)
        ai_won = (p_ai == 1000 or w_ai == ai_target)

        if human_won or ai_won:
            if human_won and ai_won:
                stats["draws"] += 1
                winner = "draw"
            elif human_won:
                stats["human"] += 1
                winner = "human"
            else:
                stats["ai"] += 1
                winner = "ai"

            render_duel_board(game_human, guesses_human, last_human,
                              game_ai, ai_player.guesses, last_ai,
                              turn_no, notice=None, stats=stats, hints=hints)
            render_duel_debrief(game_human, guesses_human, game_ai, ai_player.guesses,
                                winner=winner, turn_no=turn_no, stats=stats)

            try:
                ans = input("🎮  Rejouer une manche ? ([O]ui / [S]olo / [Q]uitter) [O] > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return None
            if ans in ("s", "solo", "/solo"):
                return "solo"
            if ans in ("m", "menu", "/menu", "/accueil"):
                return None
            if ans in ("n", "non", "q", "quit", "quitter"):
                return None
            return "duel"


# --------------------------------------------------------------------------- #
# Orchestrateur de session de jeu
# --------------------------------------------------------------------------- #
def run_game(args, store: VocabStore = None):
    store = store or VocabStore()
    secret_arg = getattr(args, "secret", None)
    init_diff = getattr(args, "difficulty", "moyen")
    duel_stats = {"human": 0, "ai": 0, "draws": 0, "match": 0, "difficulty": init_diff}

    if getattr(args, "duel", False):
        mode = "duel"
    else:
        clear_screen()
        log("=" * 70)
        log("🎮  CÉMANTIX INTERACTIF — CHOISISSEZ VOTRE MODE DE JEU")
        log("=" * 70)
        log("  [1] 🧑   Mode Solo        (Recherche sémantique libre, jauges & indices)")
        log("  [2] ⚔️   Mode Duel Croisé (Vous vs IA RAG, 3 niveaux & espionnage)")
        log("  [Q] 🚪  Quitter")
        log("-" * 70)
        try:
            choice = input("Votre choix ([1] Solo / [2] Duel / [Q]uitter) [1] > ").strip().strip('\ufeff').lower()
        except (KeyboardInterrupt, EOFError):
            log("\n👋  Au revoir !")
            return

        if choice in ("2", "d", "duel", "/duel"):
            mode = "duel"
        elif choice in ("m", "menu", "/menu", "/accueil"):
            return
        elif choice in ("q", "quit", "quitter", "/quit", "/quitter", "exit", "/exit"):
            log("\n👋  Au revoir !")
            return
        else:
            mode = "solo"

    while True:
        if mode == "solo":
            mode, secret_arg = run_solo_loop(store, secret_arg)
            if mode is None:
                break
        elif mode == "duel":
            mode = run_duel_loop(store, stats=duel_stats, initial_difficulty=init_diff)
            if mode is None:
                break
