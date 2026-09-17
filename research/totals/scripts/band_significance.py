"""Is the market-total band split on Greenline unders statistically significant?

Tests, in order of how much they respect the selection:

1. Chi-square of independence across the six bands (pooled, history only, 2026 only).
2. One band vs the rest, Fisher exact (55-59.5 and 50-54.5; pooled, history, 2026).
3. Best-of-six correction: under a null where every band shares the pooled rate,
   how often does the best band by win rate reach the observed 55-59.5 rate, and the
   worst band fall to the observed 50-54.5 rate? Monte Carlo with observed band sizes.
4. Trend: Mann-Whitney on market total, wins vs losses; Spearman(total, win).
5. Out-of-sample ordering: score each 2026 flag by its band's 2023-25 history win
   rate, then ask whether the score predicts the 2026 outcome (Mann-Whitney / AUC).
   The history chose the bands, so this is the only test that is not
   selection-on-selection.

Run from repo root:
    python research/totals/scripts/band_significance.py [--sims 200000] [--out research/totals/docs]
    python research/totals/scripts/band_significance.py --self-check
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
from greenline_season_review import load, personal_totals, wilson  # noqa: E402
from greenline_unders import BANDS, band  # noqa: E402

LABELS = [b[0] for b in BANDS]
ORDER = ["55-59.5", "<45", "45-49.5", "60-64.5", "65+", "50-54.5"]  # the proposed queue


def unders(rows):
    return [r for r in rows if r["market"] == "total" and r["side"] == "under" and r["result"] in ("win", "loss")]


def table(rows):
    out = {}
    for b in LABELS:
        rs = [r for r in rows if band(r["line"])[0] == b]
        w = sum(r["result"] == "win" for r in rs)
        out[b] = (w, len(rs) - w)
    return out


def chi2(tab):
    m = np.array([[w, l] for w, l in tab.values() if w + l > 0])
    if len(m) < 2:
        return float("nan"), float("nan"), 0
    c, p, dof, _ = stats.chi2_contingency(m)
    return c, p, dof


def one_vs_rest(tab, b):
    w, l = tab[b]
    rw = sum(x[0] for k, x in tab.items() if k != b)
    rl = sum(x[1] for k, x in tab.items() if k != b)
    return (w, l, rw, rl, stats.fisher_exact([[w, l], [rw, rl]])[1])


def best_of_k(tab, target_hi, target_lo, sims, seed=20260917, min_n=10):
    """P(best band >= target_hi) and P(worst band <= target_lo) under a common rate."""
    rng = np.random.default_rng(seed)
    ns = np.array([w + l for w, l in tab.values()])
    keep = ns >= min_n
    ns = ns[keep]
    p0 = sum(w for w, _ in tab.values()) / sum(w + l for w, l in tab.values())
    wins = rng.binomial(ns[None, :], p0, size=(sims, len(ns)))
    rates = wins / ns[None, :]
    return p0, (rates.max(1) >= target_hi - 1e-12).mean(), (rates.min(1) <= target_lo + 1e-12).mean(), int(keep.sum())


def trend(rows):
    lines = np.array([r["line"] for r in rows])
    won = np.array([r["result"] == "win" for r in rows], dtype=float)
    mw = stats.mannwhitneyu(lines[won == 1], lines[won == 0], alternative="two-sided")
    sp = stats.spearmanr(lines, won)
    return mw.pvalue, sp.statistic, sp.pvalue, lines[won == 1].mean(), lines[won == 0].mean()


def oos_ordering(hist_tab, rows_2026):
    """Score each 2026 under by its band's history win rate. Does the score predict 2026 wins?"""
    score = {b: (w / (w + l) if w + l else 0.5) for b, (w, l) in hist_tab.items()}
    s = np.array([score[band(r["line"])[0]] for r in rows_2026])
    won = np.array([r["result"] == "win" for r in rows_2026])
    if won.all() or (~won).all():
        return float("nan"), float("nan"), float("nan")
    mw = stats.mannwhitneyu(s[won], s[~won], alternative="greater")
    auc = mw.statistic / (won.sum() * (~won).sum())
    return auc, mw.pvalue, stats.spearmanr(s, won).statistic


def rec(w, l):
    n = w + l
    lo, hi = wilson(w, n)
    return f"{w}-{l} ({w / n * 100:.0f}%, {lo * 100:.0f}–{hi * 100:.0f}%)" if n else "--"


def run(sims: int) -> tuple[str, dict]:
    graded, _ = load(2026)
    hist = [r for y in (2023, 2024, 2025) for r in personal_totals(y)]
    H, F = unders(hist), unders(graded)
    P = H + F
    th, tf, tp = table(H), table(F), table(P)

    L = [f"# Is the band split significant? Greenline unders, {date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/band_significance.py --out research/totals/docs`.",
         "Data: personal unders 2023-25 (`data/ingest/bet_history/history.csv`) and graded 2026 Greenline",
         f"under flags (`data/ingest/pff_scoreboard/pff_greenline_2026_w*.csv`). n = {len(H)} history, {len(F)} 2026,",
         f"{len(P)} pooled. Pushes dropped. Bands from `greenline_unders.py`.", "",
         "## Question", "",
         "The week 3 slate is ordered by band (55-59.5 first, 50-54.5 last). Is the band effect",
         "distinguishable from noise, once you account for the band having been chosen by looking at the same history?", "",
         "## Records by band", "",
         "| band | history 2023-25 | 2026 flags | pooled |", "|---|---|---|---|"]
    for b in LABELS:
        L.append(f"| {b} | {rec(*th[b])} | {rec(*tf[b])} | {rec(*tp[b])} |")

    out = {}
    L += ["", "## 1. All six bands at once (chi-square of independence)", "",
          "| sample | chi2 | dof | p |", "|---|---:|---:|---:|"]
    for name, t in (("pooled", tp), ("history only", th), ("2026 only", tf)):
        c, p, d = chi2(t)
        out[f"chi2_{name}"] = p
        L.append(f"| {name} | {c:.2f} | {d} | {p:.3f} |")

    L += ["", "## 2. One band against the rest (Fisher exact, two-sided)", "",
          "| band | sample | band | rest | p |", "|---|---|---|---|---:|"]
    for b in ("55-59.5", "50-54.5"):
        for name, t in (("pooled", tp), ("history only", th), ("2026 only", tf)):
            w, l, rw, rl, p = one_vs_rest(t, b)
            out[f"fisher_{b}_{name}"] = p
            L.append(f"| {b} | {name} | {w}-{l} | {rw}-{rl} | {p:.3f} |")

    hi = tp["55-59.5"][0] / sum(tp["55-59.5"])
    lo = tp["50-54.5"][0] / sum(tp["50-54.5"])
    p0, p_best, p_worst, k = best_of_k(tp, hi, lo, sims)
    out.update(p_best=p_best, p_worst=p_worst)
    L += ["", "## 3. Best-of-six correction (pooled)", "",
          f"Null: every band wins at the pooled rate {p0 * 100:.1f}%. {sims:,} simulated seasons with the observed band sizes,",
          f"{k} bands with n >= 10.", "",
          f"- P(best band reaches >= {hi * 100:.1f}% by chance) = **{p_best:.3f}**",
          f"- P(worst band falls to <= {lo * 100:.1f}% by chance) = **{p_worst:.3f}**", "",
          "These are the honest p-values for 'the strongest band looks strong' and 'the weakest band looks weak'",
          "when six bands were inspected. They still overstate the evidence for the *specific* 55-59.5 band, because",
          "the boundaries were set by hand after seeing 2023-25."]

    L += ["", "## 4. Trend in the market total (no bands)", "",
          "| sample | mean total, wins | mean total, losses | Mann-Whitney p | Spearman(total, win) | p |",
          "|---|---:|---:|---:|---:|---:|"]
    for name, rs in (("pooled", P), ("history only", H), ("2026 only", F)):
        mwp, rho, sp, mw_, ml_ = trend(rs)
        out[f"trend_{name}"] = mwp
        L.append(f"| {name} | {mw_:.1f} | {ml_:.1f} | {mwp:.3f} | {rho:+.3f} | {sp:.3f} |")

    auc, p_auc, rho = oos_ordering(th, F)
    out.update(auc=auc, p_auc=p_auc)
    L += ["", "## 5. Out-of-sample: does the history ordering predict 2026?", "",
          "Each 2026 under is scored by its band's 2023-25 win rate (the number that built the queue). If the",
          "ordering carries information, 2026 winners should carry higher scores than 2026 losers.", "",
          f"- AUC = **{auc:.3f}** (0.5 = no information), one-sided Mann-Whitney p = **{p_auc:.3f}**, Spearman {rho:+.3f}, n = {len(F)}.",
          f"- 2026 by proposed queue position: " + ", ".join(f"{b} {tf[b][0]}-{tf[b][1]}" for b in ORDER) + "."]

    L += ["", "## Reading", ""]
    sig = out["chi2_pooled"] < 0.05
    L += [
        f"- Pooled, the six-band split is {'significant' if sig else 'not significant'} at 5% (chi-square p = {out['chi2_pooled']:.3f}),",
        f"  and 55-59.5 vs rest has Fisher p = {out['fisher_55-59.5_pooled']:.3f}. That is the number the 'strongest thread' claim rests on.",
        f"- Correcting for having looked at six bands, the best band reaching 63% has p = {p_best:.3f} and the worst band",
        f"  falling to 37% has p = {p_worst:.3f}. The band pattern as a whole survives the multiple-look correction only if both are small.",
        f"- The pooled numbers include the 2023-25 history that chose the band. The clean test is 2026 alone: chi-square p = {out['chi2_2026 only']:.3f},",
        f"  55-59.5 vs rest p = {out['fisher_55-59.5_2026 only']:.3f}, history-ordering AUC {auc:.2f} (p = {p_auc:.3f}) on {len(F)} flags.",
        "- The trend test asks a different question (is win rate monotone in the total?) and is the one a skeptic would accept",
        "  without bands; its answer is in section 4.",
        "", "## What this does not support", "",
        "- Treating any band as a rule. The out-of-sample sample is one graded week.",
        "- A causal story (low totals = defensive games = under). The 50-54.5 dip breaks monotonicity; a real",
        "  mechanism would not skip a band.",
        "- Sizing by band. The bankroll projection uses one p for every flag; ordering is free, sizing is not.",
        "", "## What settles it", "",
        "Rerun after each graded week. The out-of-sample AUC in section 5 is the number to watch; ~150 2026 unders",
        "gives it power to detect AUC 0.60 at the 5% level.",
    ]
    return "\n".join(L) + "\n", out


def self_check() -> None:
    t = {"a": (60, 40), "b": (40, 60), "c": (50, 50)}
    c, p, d = chi2(t)
    assert d == 2 and p < 0.05, (c, p)
    w, l, rw, rl, p = one_vs_rest(t, "a")
    assert (w, l, rw, rl) == (60, 40, 90, 110) and p < 0.05
    p0, pb, pw, k = best_of_k({"a": (50, 50), "b": (50, 50), "c": (50, 50)}, 0.75, 0.25, 20000)
    assert abs(p0 - 0.5) < 1e-9 and pb < 0.01 and pw < 0.01 and k == 3
    rows = [{"line": 40 + i, "result": "win" if i < 10 else "loss"} for i in range(20)]
    assert trend(rows)[0] < 0.01
    hist = {b: (1, 1) for b in LABELS}
    hist["<45"] = (9, 1)
    auc, p, _ = oos_ordering(hist, [{"line": 40, "result": "win"}] * 8 + [{"line": 57, "result": "loss"}] * 8)
    assert auc == 1.0 and p < 0.01
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=200_000)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    md, _ = run(a.sims)
    if a.out:
        p = a.out / f"greenline-band-significance-{date.today().isoformat()}.md"
        p.write_text(md, encoding="utf-8")
        print("wrote", p)
    else:
        print(md)


if __name__ == "__main__":
    main()
