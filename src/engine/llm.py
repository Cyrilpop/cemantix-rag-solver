"""
Cémantix Solver — Génération & Intégration LLM Local (src.engine.llm)
=====================================================================
Formatage des prompts et communication avec le serveur LLM local
(API OpenAI ChatCompletions : LM Studio, Ollama, etc.).
"""
import json
import re
import time
import requests

from ..config import LM_API, LLM_MODEL, LLM_TIMEOUT, PROMPT, log


def ask_llm(best, worst, candidates_info, n: int, verbose: bool = False) -> list:
    """Interroge le LLM local avec le contexte des meilleurs/pires coups et des candidats RAG."""
    fmt_guess = lambda g: f"- {g[0]} : {g[1] * 100:.2f}°C" + (f", {g[2]} ‰" if g[2] else "")
    fmt_cand = lambda c: f"- {c[0]} (temp. estimée : {c[1]:+.2f}°C)"
    cands_str = "\n".join(fmt_cand(c) for c in candidates_info[:25])
    prompt = PROMPT.format(best="\n".join(map(fmt_guess, best)),
                           worst=", ".join(g[0] for g in worst) or "-",
                           candidates=cands_str or "-", n=n)
    if verbose:
        log("\n  🔍  [VERBOSE CANDIDATS RAG INJECTÉS DANS LE PROMPT (Top 15)]")
        for rank, (w, temp, err) in enumerate(candidates_info[:15], 1):
            log(f"      {rank:>2}. {w:<20} est. ≈ {temp:+6.2f}°C    (cohérence err = {err:.4f})")
        log("")
    r = None
    for attempt in range(1, 3):
        try:
            r = requests.post(f"{LM_API}/chat/completions", json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7, "max_tokens": 3000,
            }, timeout=LLM_TIMEOUT)
            if r.status_code == 200:
                break
        except requests.RequestException as e:
            if attempt == 2:
                raise e
            time.sleep(1)
    if not r:
        return []
    try:
        msg = r.json()["choices"][0]["message"]
        reasoning = msg.get("reasoning_content") or ""
        content = msg.get("content") or ""
        if verbose and reasoning:
            log("\n  🔍  [VERBOSE LLM REASONING]")
            non_empty_lines = [l.strip() for l in reasoning.strip().splitlines() if l.strip()]
            for line in non_empty_lines[:8]:
                log(f"     | {line}")
            if len(non_empty_lines) > 8:
                log("     | ... (suite du raisonnement masquée)")
        text = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
        arrays = re.findall(r"\[[^\[\]]*\]", text)
        words = [str(w).strip().lower() for w in json.loads(arrays[-1])] if arrays else []
        if verbose:
            log(f"  🔍  [VERBOSE LLM OUTPUT BRUT] : {words}")
        return words
    except Exception as exc:
        log(f"   ⚠  LLM : {exc}")
        return []
