#!/usr/bin/env python3
"""
Benchmark reproductible de consommation de tokens agent (M0.1).
Mesure les octets réels retournés à l'agent et estime les tokens consommés
pour 4 tâches représentatives selon deux stratégies :
  - Stratégie A : Naïve / Non optimisée (chargement monolithique README + full files)
  - Stratégie B : Context-Aware / Optimisée (AGENTS.md + project-memory + line-ranges ciblés)

Usage:
    python tools/benchmark_agent_context.py
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def read_bytes(rel_path: str, start_line: int = None, end_line: int = None) -> int:
    p = BASE_DIR / rel_path
    if not p.exists():
        return 0
    if start_line is None and end_line is None:
        return p.stat().st_size
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    start_idx = max(0, (start_line or 1) - 1)
    end_idx = min(len(lines), end_line or len(lines))
    chunk = "".join(lines[start_idx:end_idx])
    return len(chunk.encode("utf-8"))


TASKS = [
    {
        "id": "TASK-A",
        "name": "SEO & Sitemap : Ajustement priorité d'indexation",
        "subsystem": "src/services/seo.py",
        "naive_reads": [
            ("README.md", None, None),
            ("CHANGELOG.md", None, None),
            ("src/services/seo.py", None, None),
            ("volumes/web/index.html", None, None),
        ],
        "optimized_reads": [
            ("AGENTS.md", None, None),
            ("project-memory.md", 1, 100),  # section architecture & SEO
            ("src/services/seo_sitemap.py", 1, 75),  # fonctions sitemap ciblées
        ],
        "validation_cmd": "python tools/check_seo.py",
    },
    {
        "id": "TASK-B",
        "name": "API & Sécurité : Audit validation endpoint bot challenge",
        "subsystem": "src/api/routes/challenge.py",
        "naive_reads": [
            ("README.md", None, None),
            ("src/api/server.py", None, None),
            ("src/api/routes/challenge.py", None, None),
            ("src/db/challenges.py", None, None),
        ],
        "optimized_reads": [
            ("AGENTS.md", None, None),
            ("src/api/routes/challenge.py", 100, 160),  # handle_challenge_post
            ("src/api/ratelimit.py", 1, 60),  # limiteur token bucket
        ],
        "validation_cmd": "python -m unittest tests.test_defi_bot",
    },
    {
        "id": "TASK-C",
        "name": "Frontend : Cohérence du composant de rendu des coups",
        "subsystem": "volumes/web/js/render.js",
        "naive_reads": [
            ("README.md", None, None),
            ("volumes/web/multi/index.html", None, None),
            ("volumes/web/js/multi.js", None, None),
            ("volumes/web/js/game.js", None, None),
        ],
        "optimized_reads": [
            ("AGENTS.md", None, None),
            ("volumes/web/js/render.js", 1, 88),  # module partagé entier
            ("volumes/web/js/game.js", 640, 695),  # renderGameLists dupliqué
        ],
        "validation_cmd": "python tools/check_js_balance.py",
    },
    {
        "id": "TASK-D",
        "name": "Algorithme RAG : Inspection régularisation Ridge (lam)",
        "subsystem": "src/engine/solvers.py",
        "naive_reads": [
            ("README.md", None, None),
            ("cemantix_rag.py", None, None),
            ("src/engine/solvers.py", None, None),
            ("src/engine/vocab.py", None, None),
        ],
        "optimized_reads": [
            ("AGENTS.md", None, None),
            ("src/engine/solvers.py", 48, 72),  # estimate_secret & rerank
        ],
        "validation_cmd": "python -m unittest tests.test_integrite",
    },
]


def run_benchmark():
    print("# Rapport de Benchmark Contexte Agent (M0.1)\n")
    print("| Tâche | Stratégie Naïve (Octets / Tokens) | Stratégie Optimisée (Octets / Tokens) | Économie Réalisée |")
    print("|---|---:|---:|---:|")

    total_naive_bytes = 0
    total_opt_bytes = 0

    for t in TASKS:
        naive_bytes = sum(read_bytes(f, s, e) for f, s, e in t["naive_reads"])
        opt_bytes = sum(read_bytes(f, s, e) for f, s, e in t["optimized_reads"])

        naive_tokens = naive_bytes // 4
        opt_tokens = opt_bytes // 4

        saving_pct = (1.0 - (opt_bytes / naive_bytes)) * 100.0 if naive_bytes > 0 else 0.0

        total_naive_bytes += naive_bytes
        total_opt_bytes += opt_bytes

        print(f"| **{t['id']}** : {t['name'][:35]}... | {naive_bytes:,} o (~{naive_tokens:,} t) | {opt_bytes:,} o (~{opt_tokens:,} t) | **-{saving_pct:.1f} %** |")

    tot_naive_tok = total_naive_bytes // 4
    tot_opt_tok = total_opt_bytes // 4
    tot_saving = (1.0 - (total_opt_bytes / total_naive_bytes)) * 100.0 if total_naive_bytes > 0 else 0.0

    print("|---|---:|---:|---:|")
    print(f"| **TOTAL CUMULÉ (4 tâches)** | **{total_naive_bytes:,} o (~{tot_naive_tok:,} t)** | **{total_opt_bytes:,} o (~{tot_opt_tok:,} t)** | **-{tot_saving:.1f} %** |")

    print("\n## Détail par Tâche")
    for t in TASKS:
        print(f"\n### {t['id']} — {t['name']}")
        print(f"- **Sous-système :** `{t['subsystem']}`")
        print(f"- **Validation associée :** `{t['validation_cmd']}`")
        print("- **Lectures Naïves :**")
        for f, s, e in t["naive_reads"]:
            b = read_bytes(f, s, e)
            span = f"L{s}-L{e}" if s else "100%"
            print(f"  - `{f}` ({span}) : {b:,} octets (~{b//4:,} tokens)")
        print("- **Lectures Optimisées :**")
        for f, s, e in t["optimized_reads"]:
            b = read_bytes(f, s, e)
            span = f"L{s}-L{e}" if s else "100%"
            print(f"  - `{f}` ({span}) : {b:,} octets (~{b//4:,} tokens)")


if __name__ == "__main__":
    run_benchmark()
