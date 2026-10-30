"""
Cémantix Solver — Algorithmes de Résolution & Moteurs IA (src.engine.solvers)
=============================================================================
Composants mathématiques et logiques pour la résolution autonome et assistée :
- Régression Ridge (estimation de la direction cible dans l'espace sémantique)
- Reranking multicritère par cohérence quadratique pondérée
- Génération et filtrage par LLM local (formatage strict JSON)
- Solveur autonome Cémantix (Solver / CemantixSolver)
- Joueur IA pour le mode duel (RagDuelPlayer)
- Conversion météo sémantique officielle (weather_for_score)
"""
import time
from pathlib import Path

import numpy as np

from ..config import LLM_MODEL, DISCIPLINES, ENGLISH_WORDS, SEED_WORDS, log
from .vocab import VocabStore
from .clients import CemantixClient, MockClient
from .ranking import weather_for_score, estimate_secret, rerank
from .llm import ask_llm
from .duel import RagDuelPlayer


# --------------------------------------------------------------------------- #
# Solveur autonome Cémantix (Ridge + k-NN ChromaDB + Reranking + LLM)
# --------------------------------------------------------------------------- #
class Solver:
    def __init__(self, args, store=None, game=None):
        self.args = args
        self.store = store if store else VocabStore()
        if game:
            self.game = game
        elif getattr(args, "mock", False) or getattr(args, "benchmark", 0) > 0:
            self.game = MockClient(self.store, secret=getattr(args, "secret", None))
        else:
            self.game = CemantixClient(delay=args.delay)
        self.guesses = {}   # mot -> (cosinus, permille)
        self.tried = set()
        self.win_source = None
        self.trajectory = []  # Chronologie complète de tous les coups joués pour visualisation web

    def play_word(self, word: str, source: str) -> bool:
        norm = self.store.normalize(word)
        if norm != word:
            if self.args.verbose:
                log(f"        [ACCENT RESTAURÉ] « {word} » ➔ « {norm} »")
            word = norm

        if word in self.tried:
            return False
        self.tried.add(word)

        if word in ENGLISH_WORDS:
            log(f"        {source:<4} {word:<20} (mot anglais exclu)")
            return False

        if not self.store.is_valid_french(word):
            log(f"        {source:<4} {word:<20} (inconnu du site)")
            return False

        res = self.game.score(word)
        if res is None:
            log(f"        {source:<4} {word:<20} (inconnu du site)")
            return False
        s, p = res
        
        # Échelle officielle Cémantix
        if p == 1000:
            weather = "🥳 "
        elif p and p >= 999:
            weather = "😱 "
        elif p and p >= 990:
            weather = "🔥 "
        elif p and p >= 900:
            weather = "🥵 "
        elif p and p >= 1:
            weather = "😎 "
        elif s >= 0:
            weather = "🥶 "
        else:
            weather = "🧊 "

        best = max([v[0] for v in self.guesses.values()], default=-1)
        is_new_hot_record = (s > best) and (s > 0.15)
        self.guesses[word] = (s, p)
        self.trajectory.append({
            "step": len(self.guesses),
            "word": word,
            "score": round(s * 100, 2),
            "permille": p,
            "source": source,
            "weather": weather.strip(),
            "is_record": is_new_hot_record,
        })
        rank = f"{p:>4} ‰" if p else "      "
        flag = "  ⭐" if is_new_hot_record else "    "
        log(f"  [{len(self.guesses):>3}] {source:<4} {word:<20} {s * 100:7.2f}°C  {weather}  {rank}{flag}")
        if p == 1000:
            self.win_source = source
            return True
        return False

    def ranked(self):
        return sorted(((w, s, p) for w, (s, p) in self.guesses.items()),
                      key=lambda g: g[1], reverse=True)

    def generate_optimal_seeds(self, count: int = 12, max_similarity: float = 0.22, randomize_anchor: bool = True) -> list:
        """Génération de graines orthogonales par Farthest Point Sampling (FPS) :
        maximise la couverture et l'indépendance linéaire dans l'espace à 500 dimensions.
        Restreint strictement le vivier aux disciplines fondamentales et grands concepts
        cardinaux pour garantir pertinence sémantique et indépendance géométrique."""
        if count <= 0:
            return []

        # 1. Constitution du pool des lemmes cardinaux fondamentaux
        cand_words = []
        for d in list(DISCIPLINES) + list(SEED_WORDS):
            d_norm = self.store.normalize(d)
            if self.store.is_valid_french(d_norm) and d_norm in self.store and d_norm not in cand_words:
                cand_words.append(d_norm)

        if not cand_words:
            return list(SEED_WORDS[:count])

        # 2. Construction de la matrice des candidats (vecteurs normalisés)
        C = np.vstack([self.store.vec(w) for w in cand_words])

        # 3. Choix du premier germe (ancre initiale)
        if randomize_anchor:
            first_idx = int(np.random.randint(len(cand_words)))
        else:
            mean_correlations = np.abs(C @ C.T).mean(axis=1)
            first_idx = int(np.argmin(mean_correlations))

        chosen_indices = [first_idx]
        chosen_vecs = [C[first_idx]]

        # 4. Farthest Point Sampling (FPS) / Max-Min Cosine Orthogonality
        while len(chosen_indices) < min(count, len(cand_words)):
            current_G = np.vstack(chosen_vecs)
            sim_matrix = np.abs(C @ current_G.T)  # shape: (len(cand_words), len(chosen))
            max_sims = np.max(sim_matrix, axis=1)

            # Exclure les mots déjà retenus
            max_sims[chosen_indices] = np.inf

            if randomize_anchor:
                # Tirage stochastique parmi le top-2 des mots les plus orthogonaux
                top_k = min(2, len(cand_words) - len(chosen_indices))
                top_candidates = np.argsort(max_sims)[:top_k]
                best_idx = int(np.random.choice(top_candidates))
            else:
                best_idx = int(np.argmin(max_sims))

            best_sim = float(max_sims[best_idx])
            if best_sim > max_similarity and len(chosen_indices) >= count:
                break

            chosen_indices.append(best_idx)
            chosen_vecs.append(C[best_idx])

        seeds = [cand_words[i] for i in chosen_indices]

        if getattr(self.args, "verbose", False) and len(chosen_vecs) > 1:
            G_seeds = np.vstack(chosen_vecs)
            pairwise_sim = np.abs(G_seeds @ G_seeds.T)
            np.fill_diagonal(pairwise_sim, 0.0)
            max_pair = float(pairwise_sim.max())
            avg_pair = float(pairwise_sim[pairwise_sim > 0].mean())
            log(f"  🌱  [GRAINES ORTHOGONALES RAG] {len(seeds)} graines sélectionnées "
                f"(similarité max: {max_pair:.3f}, moy: {avg_pair:.3f})")

        return seeds

    def get_seeds(self, forced_seeds: list = None) -> list:
        if forced_seeds is not None:
            return forced_seeds
        if self.args.seeds:
            seeds = [w.strip().lower() for w in self.args.seeds.split(",") if w.strip()]
        elif self.args.seeds_file:
            path = Path(self.args.seeds_file)
            if path.exists():
                seeds = [w.strip().lower() for w in path.read_text(encoding="utf-8").splitlines() if w.strip()]
            else:
                log(f"   ⚠  Fichier graines {path} introuvable, génération pluridisciplinaire RAG.")
                count = self.args.seed_count if self.args.seed_count is not None else 12
                return self.generate_optimal_seeds(count)
        elif self.args.static_seeds:
            seeds = SEED_WORDS
        else:
            count = self.args.seed_count if self.args.seed_count is not None else 12
            return self.generate_optimal_seeds(count)

        if self.args.seed_count is not None:
            return seeds[:max(0, self.args.seed_count)]
        return seeds

    def retrieve(self, ranked, verbose: bool = None) -> list:
        if verbose is None:
            verbose = self.args.verbose
        known = [g for g in ranked if g[0] in self.store]
        G = np.vstack([self.store.vec(g[0]) for g in known])
        s = np.array([g[1] for g in known], dtype=np.float32)
        q_est = estimate_secret(G, s)
        k = max(self.args.retrieve, 60)
        fetch_k = max(k * 2, 120)
        raw_pool = list(self.store.knn(q_est, fetch_k))
        for w, sc, _ in known[:3]:  # voisins des 3 meilleurs essais
            if sc > 0.10:
                raw_pool += self.store.knn(self.store.vec(w), 35)
        
        # Normalisation canonique stricte : élimine tout doublon sans accent ou token web parasite
        pool = []
        for raw_w in raw_pool:
            w = self.store.normalize(raw_w)
            if w not in self.tried and w not in pool and self.store.is_valid_french(w):
                pool.append(w)
                if len(pool) >= k:
                    break

        reranked = rerank(self.store, pool, G, s, q_est)
        if verbose:
            log("\n  🔍  [VERBOSE RAG RETRIEVAL]")
            log(f"      ├── Contraintes Ridge     : {len(known)} mots connus utilisés")
            log(f"      ├── Voisins ChromaDB      : {len(pool)} candidats filtrés et normalisés")
            log(f"      └── Top {min(8, len(reranked))} après Reranking :")
            for rank, (w, temp, e) in enumerate(reranked[:8], 1):
                log(f"          {rank:>2}. {w:<20} est. ≈ {temp:+6.2f}°C    (err = {e:.4f})")
            log("")
        return reranked

    def run(self, forced_seeds: list = None) -> dict:
        t0 = time.time()
        is_rag_only = getattr(self.args, "rag_only", False)
        log(f"🎯  Cémantix — puzzle n°{self.game.puzzle}")
        mode_desc = "⚡ 100% RAG Pur Mathématique (Ridge + Rerank — Zéro LLM)" if is_rag_only else f"🤖 Hybride RAG + Local LLM ({LLM_MODEL})"
        log(f"⚙   Mode : {mode_desc}")
        seeds = self.get_seeds(forced_seeds)
        log(f"── Amorçage ({len(seeds)} mots graines)\n")
        
        for i, w in enumerate(seeds, 1):
            if self.play_word(w, "seed"):
                return self.win(w, time.time() - t0)

            valid_seeds = len(self.guesses)
            last_score, last_permille = self.guesses.get(w, (0.0, None))
            best_score = max(v[0] for v in self.guesses.values())

            # 1. Amorçage adaptatif : interruption précoce dès qu'un mot est chaud (Top 1000 confirmé)
            if valid_seeds >= 3 and i < len(seeds):
                is_warm = (best_score >= 0.20) or (last_permille is not None and last_permille >= 1)
                if is_warm:
                    best_word_entry = max(self.guesses.items(), key=lambda x: x[1][0])
                    bw_name = best_word_entry[0]
                    bw_score, bw_p = best_word_entry[1]
                    p_info = f", {bw_p} ‰" if bw_p else ""
                    log(f"\n🔥  [AMORÇAGE ADAPTATIF] Signal chaud détecté sur « {bw_name} » ({bw_score * 100:.2f}°C{p_info}) dès la graine {i}/{len(seeds)} !")
                    log(f"    ➔ Interruption immédiate de l'amorçage pour exploiter la zone chaude en convergence RAG.\n")
                    break

            # 2. Détection anticipée (Sniper) : dès 3 graines si candidat brûlant ou certitude
            if valid_seeds >= 3 and i < len(seeds):
                cands_quick = self.retrieve(self.ranked(), verbose=False)
                if cands_quick:
                    top_cand, top_temp, top_err = cands_quick[0]
                    if (top_temp >= 65.0 and top_err < 0.003) or (top_err < 0.0001):
                        if top_cand not in self.tried:
                            log(f"\n⚡  [SNIPER RAG] Tir d'anticipation après {valid_seeds} graines : « {top_cand} » (est: {top_temp:.1f}°C, err: {top_err:.5f})")
                            if self.play_word(top_cand, "rag"):
                                return self.win(top_cand, time.time() - t0)
                            s_snip, p_snip = self.guesses.get(top_cand, (0.0, None))
                            if s_snip >= 0.18 or (p_snip and p_snip >= 1):
                                break

        round_no = 0
        rag_k = self.args.rag_words if (self.args.rag_words != 3 or not is_rag_only) else 5
        while len(self.guesses) < self.args.max_tries:
            round_no += 1
            ranked = self.ranked()
            log(f"\n{'═' * 60}")
            log(f"── Tour {round_no} | Meilleur : {ranked[0][0]} ({ranked[0][1] * 100:.2f}°C)")
            log(f"{'═' * 60}")

            candidates_info = self.retrieve(ranked)
            cand_words = [c[0] for c in candidates_info]

            # Fast-path : si le candidat RAG n°1 est mathématiquement certain, on le teste immédiatement sans appeler le LLM
            if candidates_info and (candidates_info[0][1] >= 75.0 and candidates_info[0][2] < 0.002) and cand_words[0] not in self.tried:
                top_cand, top_temp, top_err = candidates_info[0]
                if self.args.verbose:
                    log(f"⚡  [FAST-PATH RAG] Candidat prometteur « {top_cand} » ({top_temp:.1f}°C, err={top_err:.5f}), tir direct sans attente LLM...")
                if self.play_word(top_cand, "rag"):
                    return self.win(top_cand, time.time() - t0)

            if is_rag_only:
                batch = [(w, "rag") for w in cand_words[:rag_k]]
                if self.args.verbose:
                    log(f"  🔍  [VERBOSE BATCH RAG PUR ({len(batch)})] : {', '.join(w for w, _ in batch)}\n")
            else:
                llm_words = ask_llm(
                    ranked[:15], ranked[-5:], candidates_info[:30], self.args.llm_words,
                    verbose=self.args.verbose)
                
                normalized_llm = []
                for raw_w in llm_words:
                    w = self.store.normalize(raw_w)
                    if w not in normalized_llm and w not in self.tried:
                        normalized_llm.append(w)

                valid_llm = [w for w in normalized_llm if self.store.is_valid_french(w)]
                rejected = [w for w in normalized_llm if not self.store.is_valid_french(w)]
                
                if self.args.verbose and llm_words:
                    log("\n  🔍  [VERBOSE LLM SYNTHÈSE]")
                    log(f"      ├── Mots proposés  : {', '.join(llm_words)}")
                    if rejected:
                        log(f"      ├── Mots filtrés   : {', '.join(rejected)} (hors dictionnaire officiel)")
                    log(f"      └── Mots retenus   : {', '.join(valid_llm) if valid_llm else 'aucun'}\n")
                elif rejected:
                    log(f"        llm  filtrés (hors dictionnaire officiel) : {', '.join(rejected)}")

                batch = [(w, "rag") for w in cand_words[:self.args.rag_words]]
                batch += [(w, "llm") for w in valid_llm]
                
                if self.args.verbose:
                    rag_list = [w for w, src in batch if src == "rag"]
                    llm_list = [w for w, src in batch if src == "llm"]
                    log("  🔍  [VERBOSE BATCH DU TOUR]")
                    if rag_list:
                        log(f"      ├── RAG ({len(rag_list)}) : {', '.join(rag_list)}")
                    if llm_list:
                        log(f"      └── LLM ({len(llm_list)}) : {', '.join(llm_list)}")
                    log("")

            if not batch:
                log("Plus de candidats.")
                break
            for w, src in batch:
                if self.play_word(w, src):
                    return self.win(w, time.time() - t0)
                # Si le coup joué apporte un gain chaud majeur vers la cible, recalcul Ridge immédiat
                s_cur, p_cur = self.guesses.get(w, (0.0, None))
                if s_cur >= 0.28 or (p_cur and p_cur >= 600):
                    break

        secret_name = getattr(self.game, "secret", "inconnu")
        elapsed = time.time() - t0
        log(f"\n❌  Non trouvé après {len(self.guesses)} essais (mot secret : {secret_name}). Top 10 :")
        for w, s, p in self.ranked()[:10]:
            log(f"   {w:<20} {s * 100:6.2f}°C {p or ''}")
        top = [
            {"word": w, "score": round(s * 100, 2), "permille": p}
            for w, s, p in self.ranked()[:10]
        ]
        return {
            "word": secret_name,
            "tries": len(self.guesses),
            "attempts": len(self.tried),
            "source": None,
            "win": False,
            "time": elapsed,
            "top_guesses": top,
            "trajectory": list(self.trajectory),
        }

    def win(self, word: str, elapsed: float = 0.0) -> dict:
        time_str = f" en {elapsed:.2f}s" if elapsed > 0 else ""
        log(f"\n🥳  Mot trouvé : « {word.upper()} » en {len(self.guesses)} essais "
            f"({len(self.tried)} tentatives) [par {self.win_source}]{time_str}.")
        top = [
            {"word": w, "score": round(s * 100, 2), "permille": p}
            for w, s, p in self.ranked()[:10]
        ]
        return {
            "word": word,
            "tries": len(self.guesses),
            "attempts": len(self.tried),
            "source": self.win_source,
            "win": True,
            "time": elapsed,
            "top_guesses": top,
            "trajectory": list(self.trajectory),
        }


CemantixSolver = Solver


__all__ = [
    "Solver",
    "CemantixSolver",
    "RagDuelPlayer",
    "estimate_secret",
    "rerank",
    "ask_llm",
    "weather_for_score",
]
