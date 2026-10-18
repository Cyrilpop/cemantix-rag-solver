"""
Cémantix Solver — Interface Utilisateur & Rendu Console
========================================================
Composants d'affichage dans le terminal :
- Nettoyage d'écran et gestion ANSI
- Jauges et thermomètres ASCII dynamiques
- Attribution des météos selon l'échelle officielle Cémantix
- Dashboards synchronisés solo et duel croisé
- Débriefing comparatif d'après-match
"""
import os
import sys

from config import (
    BOLD, RESET, ANSI_RE, BOARD_WIDTH, COL_WIDTH, DUEL_TOP_WORDS, log
)


def clear_screen() -> None:
    """Efface l'écran du terminal proprement pour tous les OS et environnements."""
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def make_gauge(s: float, p: int | None, threshold: float, width: int = 20) -> str:
    """Génère un thermomètre visuel ASCII adapté à la proximité sémantique."""
    if p is not None:
        ratio = 0.35 + (min(1000, max(1, p)) / 1000.0) * 0.65
        pct_lbl = f"{p:>4}‰"
    else:
        norm_s = max(0.0, s) / max(threshold, 0.01)
        ratio = min(0.35, norm_s * 0.35)
        pct_lbl = f"{s*100:5.1f}°C"
    filled = int(round(ratio * width))
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct_lbl}"


def strip_ansi(s: str) -> str:
    """Supprime les codes ANSI d'une chaîne pour calculer sa largeur réelle."""
    return ANSI_RE.sub('', s)


def visible_width(s: str) -> int:
    """Calcule la largeur d'affichage réelle dans le terminal (émojis = 2 colonnes)."""
    clean = strip_ansi(s)
    w = 0
    for ch in clean:
        if ch in "🥶🧊😎🥵🔥😱🥳⭐🎯🤖🧑⚔️":
            w += 2
        else:
            w += 1
    return w


def pad_visible(s: str, target_width: int) -> str:
    """Aligne une chaîne à droite avec des espaces en tenant compte de la largeur réelle des émojis."""
    vw = visible_width(s)
    pad = max(0, target_width - vw)
    return s + " " * pad


def weather_for_score(s: float, p: int | None) -> tuple[str, str]:
    """Retourne l'icône et le libellé officiel Cémantix selon le score."""
    if p == 1000:
        return "🥳", "GAGNÉ"
    elif p and p >= 999:
        return "😱", "BRÛL."
    elif p and p >= 990:
        return "🔥", "CHAUD"
    elif p and p >= 900:
        return "🥵", "CHAUD"
    elif p and p >= 1:
        return "😎", "TIÈDE"
    elif s >= 0.15:
        return "🥶", "FRAIS"
    elif s >= 0:
        return "🥶", "FROID"
    else:
        return "🧊", "GLAC."


def render_game_board(game, guesses, last_played=None, notice=None, view_mode="top", hints=None) -> None:
    """Affiche le tableau de bord du mode solo interactif."""
    clear_screen()
    tries_count = len(guesses)
    best_tuple = max(guesses.values(), key=lambda v: v[0], default=None)
    best_score_str = f"{best_tuple[0]*100:6.2f}°C" if best_tuple else "Aucun"
    best_word = [w for w, v in guesses.items() if v == best_tuple][0] if best_tuple else "-"

    log("=" * 70)
    log("🎮  CÉMANTIX INTERACTIF — À VOUS DE JOUER !")
    log("=" * 70)
    log(f"Essais joués : {tries_count:>3}  |  Meilleur : {best_word:<15} ({best_score_str})")
    log(f"Seuil Top 1000 : {game.p1000_threshold * 100:.2f}°C")
    log("-" * 70)

    if not guesses:
        log("\n  💡  Proposez un premier mot pour démarrer la recherche sémantique !\n")
    else:
        if view_mode == "history":
            log("📜  HISTORIQUE DES ESSAIS (Ordre chronologique) :")
            items = sorted(guesses.items(), key=lambda x: x[1][2])[-15:]
        else:
            log("🏆  TABLEAU RÉCAPITULATIF DES MEILLEURS ESSAIS :")
            items = sorted(guesses.items(), key=lambda x: x[1][0], reverse=True)[:15]

        log(f"  {'#':<5}  {'Mot':<20} {'Température':<12}  {'Météo':<14}  {'Rang'}")
        log("  " + "─" * 60)
        for w, (s, p, num, w_icon, w_lbl) in items:
            rk_str = f"{p:>4}‰" if p else "     "
            is_last = (last_played and w == last_played[0])
            w_disp = f"{BOLD}{w:<20}{RESET}" if is_last else f"{w:<20}"
            log(f"  [{num:>3}]  {w_disp} {s*100:6.2f}°C     {w_icon}  {w_lbl:<10}  {rk_str}")
        log("  " + "─" * 60)

    if last_played:
        w, s, p, num, w_icon, w_lbl, is_best = last_played
        rk_str = f"({p}‰)" if p else ""
        rec_str = "  ⭐  (Nouveau record !)" if is_best else ""
        gauge = make_gauge(s, p, game.p1000_threshold, width=20)
        log(f"Dernier coup : [{num:>3}] {BOLD}{w}{RESET} ({s*100:.2f}°C  {w_icon}  {w_lbl} {rk_str}){rec_str}")
        log(f"Thermomètre  : {gauge}  {w_icon}  {w_lbl}")

    if hints:
        log("\n💡  INDICES RAG DÉBLOQUÉS :")
        for i, h in enumerate(hints, 1):
            log(f"  • Indice #{i} : Explorez le champ de « {BOLD}{h}{RESET} »")

    if notice:
        log(f"\n{notice}")

    log("-" * 70)


def format_duel_cell(num: int, w: str, s: float, p: int | None, icon: str, lbl: str, is_last: bool = False) -> str:
    """Formate une cellule de tableau duel (43 caractères visibles de large)."""
    num_str = f" [{num:>2}] "
    raw_w = f"{w[:17]:<17}"
    w_str = f"{BOLD}{raw_w}{RESET} " if is_last else f"{raw_w} "
    score_val = f"{p}‰" if p else f"{s*100:5.2f}°C"
    score_str = f"{score_val:>8}  "
    meteo_str = f"{icon}  {lbl:<5}"
    cell = num_str + w_str + score_str + meteo_str
    return pad_visible(cell, COL_WIDTH)


def render_duel_board(game_human, guesses_human, last_human,
                      game_ai, guesses_ai, last_ai,
                      turn_no: int, notice=None, stats: dict | None = None,
                      hints=None) -> None:
    """Affiche le plateau de duel croisé synchronisé sur 89 colonnes."""
    clear_screen()
    log("=" * BOARD_WIDTH)
    if stats and stats.get("match"):
        diff_tag = f" [{stats.get('difficulty', 'moyen').upper()}]" if stats.get('difficulty') else ""
        log(f"⚔️   DUEL CROISÉ — Manche #{stats['match']} (🧑   {stats['human']} — {stats['ai']}  🤖){diff_tag} — Tour #{turn_no}")
    else:
        log(f"⚔️   CÉMANTIX DUEL CROISÉ — 🧑   VOUS vs 🤖   IA RAG (Tour #{turn_no})")
    log("=" * BOARD_WIDTH)

    sec = game_ai.secret.upper()
    if len(sec) <= 19:
        r_title = f"  🤖  IA RAG (Cible : {sec})"
    elif len(sec) <= 23:
        r_title = f"  🤖  IA (Cible : {sec})"
    else:
        r_title = f"  🤖  IA : {sec[:21]}…"
    col_l_title = pad_visible("  🧑  VOS ESSAIS (Cible : ???)", COL_WIDTH)
    col_r_title = pad_visible(r_title, COL_WIDTH)
    log(f"{col_l_title} │ {col_r_title}")

    col_head = pad_visible(" #    Mot                 Score   Météo", COL_WIDTH)
    log(f"{col_head} │ {col_head}")
    log("─" * COL_WIDTH + "─┼─" + "─" * COL_WIDTH)

    items_h = sorted(guesses_human.items(), key=lambda x: x[1][0], reverse=True)[:DUEL_TOP_WORDS]
    items_a = sorted(guesses_ai.items(), key=lambda x: x[1][0], reverse=True)[:DUEL_TOP_WORDS]
    max_rows = max(len(items_h), len(items_a), 1)

    for i in range(max_rows):
        if i < len(items_h):
            w, (s, p, num, icon, lbl) = items_h[i]
            is_last = (last_human and w == last_human[0])
            c_left = format_duel_cell(num, w, s, p, icon, lbl, is_last=is_last)
        else:
            c_left = pad_visible("  -", COL_WIDTH) if (i == 0 and not guesses_human) else " " * COL_WIDTH

        if i < len(items_a):
            w, (s, p, num, icon, lbl) = items_a[i]
            is_last = (last_ai and w == last_ai[0])
            c_right = format_duel_cell(num, w, s, p, icon, lbl, is_last=is_last)
        else:
            c_right = pad_visible("  -", COL_WIDTH) if (i == 0 and not guesses_ai) else " " * COL_WIDTH

        log(f"{c_left} │ {c_right}")

    log("─" * COL_WIDTH + "─┼─" + "─" * COL_WIDTH)

    lh_score = f"{last_human[2]}‰" if (last_human and last_human[2]) else (f"{last_human[1]*100:.1f}°C" if last_human else "")
    la_score = f"{last_ai[2]}‰" if (last_ai and last_ai[2]) else (f"{last_ai[1]*100:.1f}°C" if last_ai else "")

    lh_str = f"  Dernier : [{last_human[3]:>2}] {last_human[0]} ({lh_score})" if last_human else "  Dernier : -"
    la_str = f"  Dernier : [{last_ai[3]:>2}] {last_ai[0]} ({la_score})" if last_ai else "  Dernier : -"
    log(f"{pad_visible(lh_str, COL_WIDTH)} │ {pad_visible(la_str, COL_WIDTH)}")

    gh_str = f"  Jauge   : {make_gauge(last_human[1], last_human[2], game_human.p1000_threshold, width=10)}" if last_human else "  Jauge   : -"
    ga_str = f"  Jauge   : {make_gauge(last_ai[1], last_ai[2], game_ai.p1000_threshold, width=10)}" if last_ai else "  Jauge   : -"
    log(f"{pad_visible(gh_str, COL_WIDTH)} │ {pad_visible(ga_str, COL_WIDTH)}")
    log("=" * BOARD_WIDTH)

    if hints:
        log("💡  INDICES RAG DÉBLOQUÉS :")
        for i, h in enumerate(hints, 1):
            log(f"  • Indice #{i} : Explorez le champ de « {BOLD}{h}{RESET} »")
        log("=" * BOARD_WIDTH)

    if notice:
        log(f"\n{notice}")


def render_duel_debrief(game_human, guesses_human, game_ai, guesses_ai,
                        winner: str, turn_no: int, stats: dict) -> None:
    """Affiche le tableau comparatif d'après-match côte à côte sur 89 colonnes."""
    log("\n" + "=" * BOARD_WIDTH)
    log(f"📊   DÉBRIEFING DU MATCH — MANCHE #{stats.get('match', 1)}")
    log("=" * BOARD_WIDTH)

    if winner == "human":
        win_str = f"  Vainqueur : 🥳  HUMAIN (en {turn_no} tours)"
    elif winner == "ai":
        win_str = f"  Vainqueur : 🤖  IA RAG (en {turn_no} tours)"
    elif winner == "draw":
        win_str = f"  Résultat  : 🤝  ÉGALITÉ ({turn_no} tours)"
    else:
        win_str = f"  Résultat  : 🏳️  ABANDON (au tour #{turn_no})"

    score_str = f"  Score session : 🧑  {stats.get('human', 0)} — {stats.get('ai', 0)}  🤖"
    log(f"{pad_visible(win_str, COL_WIDTH)} │ {pad_visible(score_str, COL_WIDTH)}")
    log("─" * COL_WIDTH + "─┼─" + "─" * COL_WIDTH)

    diff_tag = stats.get("difficulty", "moyen").upper()
    title_l = "  🧑  PARCOURS HUMAIN"
    title_r = f"  🤖  PARCOURS IA RAG [{diff_tag}]"
    log(f"{pad_visible(title_l, COL_WIDTH)} │ {pad_visible(title_r, COL_WIDTH)}")

    target_l = f"  • Cible        : {game_human.secret.upper()[:21]}"
    target_r = f"  • Cible        : {game_ai.secret.upper()[:21]}"
    log(f"{pad_visible(target_l, COL_WIDTH)} │ {pad_visible(target_r, COL_WIDTH)}")

    h_won = (winner == "human" or game_human.secret in guesses_human)
    a_won = (winner == "ai" or game_ai.secret in guesses_ai)
    t_h = guesses_human.get(game_human.secret, (0, 0, turn_no))[2] if h_won else None
    t_a = guesses_ai.get(game_ai.secret, (0, 0, turn_no))[2] if a_won else None

    stat_l = f"  • Statut       : TROUVÉ (Tour #{t_h})" if h_won else "  • Statut       : Non trouvé"
    stat_r = f"  • Statut       : TROUVÉ (Tour #{t_a})" if a_won else "  • Statut       : Non trouvé"
    log(f"{pad_visible(stat_l, COL_WIDTH)} │ {pad_visible(stat_r, COL_WIDTH)}")

    def fmt_best(guesses):
        if not guesses:
            return "-"
        b = max(guesses.items(), key=lambda x: x[1][0], default=None)
        if not b:
            return "-"
        w, (s, p, num, *_) = b
        sc = f"{p}‰" if p else f"{s*100:.1f}°C"
        max_w = COL_WIDTH - 19 - len(f"[{num:>2}] ") - len(f" ({sc})")
        return f"[{num:>2}] {w[:max_w]} ({sc})"

    bm_l = f"  • Meilleur mot : {fmt_best(guesses_human)}"
    bm_r = f"  • Meilleur mot : {fmt_best(guesses_ai)}"
    log(f"{pad_visible(bm_l, COL_WIDTH)} │ {pad_visible(bm_r, COL_WIDTH)}")

    def fmt_spark(guesses):
        sparks = [(w, v[0], v[1], v[2]) for w, v in guesses.items() if (v[0] >= 0.15 or v[1] is not None)]
        if not sparks:
            return "-"
        first = min(sparks, key=lambda x: x[3])
        max_w = COL_WIDTH - 20 - len(f"Tour #{first[3]} ()")
        return f"Tour #{first[3]} ({first[0][:max_w]})"

    spk_l = f"  • 1ère étincelle: {fmt_spark(guesses_human)}"
    spk_r = f"  • 1ère étincelle: {fmt_spark(guesses_ai)}"
    log(f"{pad_visible(spk_l, COL_WIDTH)} │ {pad_visible(spk_r, COL_WIDTH)}")

    def count_weather(guesses):
        hot = sum(1 for v in guesses.values() if v[1] and v[1] >= 900)
        warm = sum(1 for v in guesses.values() if v[1] and v[1] < 900)
        cold = sum(1 for v in guesses.values() if not v[1])
        return hot, warm, cold

    hot_h, warm_h, cold_h = count_weather(guesses_human)
    hot_a, warm_a, cold_a = count_weather(guesses_ai)

    met_l = f"  • Météo        : 🔥 {hot_h:<2} 😎 {warm_h:<2} 🥶 {cold_h:<2}"
    met_r = f"  • Météo        : 🔥 {hot_a:<2} 😎 {warm_a:<2} 🥶 {cold_a:<2}"
    log(f"{pad_visible(met_l, COL_WIDTH)} │ {pad_visible(met_r, COL_WIDTH)}")
    log("─" * COL_WIDTH + "─┼─" + "─" * COL_WIDTH + "\n")
