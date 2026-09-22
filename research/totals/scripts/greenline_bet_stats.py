"""Full statistical workup of the graded totals bets: personal 2023-25 plus PFF 2026 flags.

    python research/totals/scripts/greenline_bet_stats.py
    python research/totals/scripts/greenline_bet_stats.py --out section.md
    python research/totals/scripts/greenline_bet_stats.py --self-check

Reads `greenline_results_<season>.csv` (written by `greenline_season_review.py`) and
answers, for the pooled unders and the main splits: is the win rate above break-even
(exact binomial, one-sided), what is the probability the true rate is above break-even
(Beta posterior, flat prior), what is the interval on units and ROI (bootstrap, resampling
bets), are the seasons consistent with one rate (chi-square heterogeneity), are results
independent across bets (runs test) and across game days (day-clustered SE vs iid), how
bad were the drawdowns against what the point estimate predicts, and how many splits were
examined so the reader can discount the best of them. Every number carries its
uncertainty; none is a verdict on its own.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, decimal, wilson  # noqa: E402
from greenline_unders import band  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
SPLITS_EXAMINED = 8 + 6 + 6 + 4   # bands, value buckets, edge bins, sides/sources -- looks taken across the docs


def load(season: int) -> list[dict]:
    rows = list(csv.DictReader((IN_DIR / f"greenline_results_{season}.csv").open(encoding="utf-8")))
    out = []
    for r in rows:
        if r["market"] != "total" or r["result"] == "push":
            continue
        out.append({"source": r["source"], "season": int(r["season"]), "date": r["date"], "side": r["side"],
                    "line": float(r["line"]), "price": float(r["price"]), "win": r["result"] == "win",
                    "net": (decimal(float(r["price"])) - 1) if r["result"] == "win" else -1.0})
    return sorted(out, key=lambda r: (r["date"], r["source"]))


def binom_p(w: int, n: int, p0: float = BREAK_EVEN) -> float:
    """One-sided exact P(X >= w | n, p0)."""
    try:
        from scipy.stats import binomtest
        return binomtest(w, n, p0, alternative="greater").pvalue
    except ImportError:
        return sum(math.comb(n, k) * p0 ** k * (1 - p0) ** (n - k) for k in range(w, n + 1))


def beta_post(w: int, n: int, p0: float = BREAK_EVEN) -> tuple[float, float, float]:
    """Flat Beta(1,1) prior: P(p > p0), posterior median, 5th percentile."""
    from scipy.stats import beta
    d = beta(w + 1, n - w + 1)
    return 1 - d.cdf(p0), d.median(), d.ppf(0.05)


def bootstrap(rows: list[dict], reps: int = 4000, seed: int = 7) -> tuple[float, float, float, float]:
    """95% interval on total units and on ROI, resampling bets with replacement."""
    import random
    rnd = random.Random(seed)
    nets = [r["net"] for r in rows]
    n = len(nets)
    tots = sorted(sum(rnd.choice(nets) for _ in range(n)) for _ in range(reps))
    lo, hi = tots[int(0.025 * reps)], tots[int(0.975 * reps)]
    return lo, hi, lo / n, hi / n


def heterogeneity(groups: dict[str, list[dict]]) -> tuple[float, float, int]:
    """Chi-square test that all groups share one win rate."""
    from scipy.stats import chi2
    ws = {k: sum(r["win"] for r in v) for k, v in groups.items() if v}
    ns = {k: len(v) for k, v in groups.items() if v}
    p = sum(ws.values()) / sum(ns.values())
    stat = sum((ws[k] - ns[k] * p) ** 2 / (ns[k] * p * (1 - p)) for k in ws)
    df = len(ws) - 1
    return stat, 1 - chi2.cdf(stat, df), df


def hetero_mde(ns: list[int], p_bar: float = 0.54, alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest max-min spread across len(ns) groups the `heterogeneity()` chi-square above
    would catch 80% of the time, holding each group's true rate evenly spread around p_bar.

    Bisects on the spread and scores it with the noncentral chi-square power at that
    noncentrality -- the same test statistic `heterogeneity()` computes, read backwards.
    A p-value near 1 on that test says "consistent with one rate at THIS resolution"; this
    is the resolution.
    """
    from scipy.stats import chi2, ncx2
    k = len(ns)
    if k < 2:
        return float("nan")
    crit = chi2.ppf(1 - alpha, k - 1)
    lo, hi = 0.0, 0.9
    for _ in range(60):
        spread = (lo + hi) / 2
        ps = [p_bar - spread / 2 + spread * i / (k - 1) for i in range(k)]
        pb = sum(n * p for n, p in zip(ns, ps)) / sum(ns)
        lam = sum(n * (p - pb) ** 2 for n, p in zip(ns, ps)) / (pb * (1 - pb))
        pw = 1 - ncx2.cdf(crit, k - 1, lam)
        if pw < power:
            lo = spread
        else:
            hi = spread
    return hi


def runs_test(seq: list[bool]) -> tuple[int, float, float]:
    """Wald-Wolfowitz: observed runs, expected, two-sided p. Fewer runs than expected = streaky."""
    from scipy.stats import norm
    n1, n2 = sum(seq), len(seq) - sum(seq)
    runs = 1 + sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    n = n1 + n2
    mu = 1 + 2 * n1 * n2 / n
    var = 2 * n1 * n2 * (2 * n1 * n2 - n) / (n * n * (n - 1))
    z = (runs - mu) / math.sqrt(var) if var > 0 else 0.0
    return runs, mu, 2 * (1 - norm.cdf(abs(z)))


def clustered_se(rows: list[dict]) -> tuple[float, float, int]:
    """SE of the win rate, iid vs clustered by game date (same-day games share shocks)."""
    n = len(rows)
    p = sum(r["win"] for r in rows) / n
    iid = math.sqrt(p * (1 - p) / n)
    days: dict[str, list[float]] = {}
    for r in rows:
        days.setdefault(r["date"], []).append(1.0 if r["win"] else 0.0)
    g = len(days)
    # cluster-robust variance of the mean: sum over clusters of (sum of residuals)^2 / n^2, small-G adjusted
    s = sum(sum(x - p for x in v) ** 2 for v in days.values())
    cl = math.sqrt(s / n ** 2 * g / (g - 1)) if g > 1 else float("nan")
    return iid, cl, g


def drawdown(rows: list[dict]) -> tuple[float, int, int]:
    """Max drawdown in units, longest losing streak, and bets from peak to trough."""
    cum = peak = 0.0
    mdd = 0.0
    streak = longest = 0
    for r in rows:
        cum += r["net"]
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
        streak = streak + 1 if not r["win"] else 0
        longest = max(longest, streak)
    return mdd, longest, len(rows)


def expected_longest_streak(p_loss: float, n: int) -> float:
    """Rough expectation of the longest losing run in n iid bets."""
    return math.log(n * (1 - p_loss)) / -math.log(p_loss) if 0 < p_loss < 1 else float("nan")


def rec(rows: list[dict]) -> tuple[int, int]:
    w = sum(r["win"] for r in rows)
    return w, len(rows) - w


def block(label: str, rows: list[dict]) -> list[str]:
    w, l = rec(rows)
    n = w + l
    if n < 5:
        return [f"| {label} | {w}-{l} | -- | -- | -- | -- | -- |"]
    lo, hi = wilson(w, n)
    p = binom_p(w, n)
    post, med, p5 = beta_post(w, n)
    ulo, uhi, rlo, rhi = bootstrap(rows)
    units = sum(r["net"] for r in rows)
    return [f"| {label} | {w}-{l} | {w / n * 100:.1f}% ({lo * 100:.0f}–{hi * 100:.0f}) | {p:.3f} | {post * 100:.0f}% | "
            f"{units:+.1f} ({ulo:+.1f} to {uhi:+.1f}) | {units / n * 100:+.1f}% ({rlo * 100:+.0f} to {rhi * 100:+.0f}) |"]


def report(rows: list[dict]) -> str:
    U = [r for r in rows if r["side"] == "under"]
    O = [r for r in rows if r["side"] == "over"]
    P = [r for r in U if r["source"] == "personal"]
    F = [r for r in U if r["source"] == "pff"]
    L = ["## Statistical workup of the bets", "",
         f"`research/totals/scripts/greenline_bet_stats.py`. {len(rows)} graded totals bets "
         f"({len(P)} personal unders 2023-25, {len(F)} PFF 2026 under flags, {len(O)} overs). "
         "Binomial p is one-sided against 52.4%. P(edge) is the posterior probability the true win rate exceeds "
         "break-even under a flat prior. Units and ROI intervals are 95% bootstrap over bets (4,000 resamples).", "",
         "| split | record | win% (95% CI) | binomial p | P(edge) | units (95%) | ROI (95%) |",
         "|---|---|---|---:|---:|---|---|"]
    L += block("all unders, pooled", U)
    L += block("personal 2023-25 unders", P)
    L += block("PFF 2026 under flags", F)
    for yr in sorted({r["season"] for r in P}):
        L += block(f"personal {yr} unders", [r for r in P if r["season"] == yr])
    L += block("all overs", O)
    for b in ("<45", "45-49.5", "50-54.5", "55-59.5", "60-64.5", "65+"):
        L += block(f"unders, band {b}", [r for r in U if band(r["line"])[0] == b])

    # heterogeneity across seasons
    groups = {str(yr): [r for r in U if r["season"] == yr] for yr in sorted({r["season"] for r in U})}
    stat, hp, df = heterogeneity(groups)
    L += ["", "**Seasons consistent with one rate?** Chi-square heterogeneity across "
          + ", ".join(f"{k} ({rec(v)[0]}-{rec(v)[1]})" for k, v in groups.items())
          + f": χ²={stat:.2f}, df={df}, p={hp:.2f}. "
          + ("No evidence the seasons differ; pooling is defensible." if hp > 0.10 else
             "Seasons differ more than one rate explains; pool with caution.")]

    # independence
    runs, mu, rp = runs_test([r["win"] for r in U])
    iid, cl, g = clustered_se(U)
    p_all = rec(U)[0] / len(U)
    L += ["", f"**Independence.** Runs test on the pooled under sequence: {runs} runs vs {mu:.0f} expected, p={rp:.2f} "
          f"({'no streakiness beyond chance' if rp > 0.10 else 'streakier than chance'}). "
          f"Win-rate SE clustered by game day ({g} days) is {cl * 100:.2f} points vs {iid * 100:.2f} iid; "
          f"the day-clustered 95% interval on {p_all * 100:.1f}% is {(p_all - 1.96 * cl) * 100:.1f}–{(p_all + 1.96 * cl) * 100:.1f}%. "
          + ("Same-day dependence is negligible here." if cl <= iid * 1.15 else "Same-day dependence widens the interval; use the clustered one.")]

    # drawdowns
    L += ["", "**Drawdowns.** Max drawdown, longest losing streak, and what the point estimate predicts for the streak:", "",
          "| series | bets | max drawdown | longest losing run | expected longest run |", "|---|---:|---:|---:|---:|"]
    for lab, rs in (("personal 2023", [r for r in P if r["season"] == 2023]), ("personal 2024", [r for r in P if r["season"] == 2024]),
                    ("personal 2025", [r for r in P if r["season"] == 2025]), ("PFF 2026 flags", F), ("all unders", U)):
        if len(rs) >= 5:
            mdd, longest, n = drawdown(rs)
            L.append(f"| {lab} | {n} | {mdd:+.1f}u | {longest} | {expected_longest_streak(1 - rec(rs)[0] / n, n):.1f} |")

    # price
    prices = [r["price"] for r in U]
    be_actual = st.mean(1 / decimal(p) for p in prices)
    L += ["", f"**Price paid.** Mean price on unders {st.mean(prices):.0f} (range {min(prices):.0f} to {max(prices):.0f}); "
          f"the break-even at the prices actually taken is {be_actual * 100:.1f}%, vs 52.4% at a flat -110."]

    # multiplicity + power
    n_u = len(U)
    L += ["", f"**Multiplicity.** About {SPLITS_EXAMINED} splits have been examined across this document. "
          f"Under a Bonferroni correction the per-split threshold is p<{0.05 / SPLITS_EXAMINED:.4f}; only the pooled rows "
          "above were specified in advance, and only the pooled all-unders row and the 55-59.5 band come near even the "
          "uncorrected 0.05. A true 56% rate needs about 720 bets before its 95% floor clears break-even; "
          f"there are {n_u}.", ""]
    return "\n".join(L)


def self_check() -> None:
    assert abs(binom_p(62, 98) - 0.0189) < 0.01, binom_p(62, 98)
    post, med, p5 = beta_post(62, 98)
    assert post > 0.95 and 0.60 < med < 0.66 and 0.53 < p5 < 0.57, (post, med, p5)
    rows = [dict(net=0.909, win=True, date=f"d{i % 7}") for i in range(60)] + [dict(net=-1.0, win=False, date=f"d{i % 7}") for i in range(40)]
    lo, hi, rlo, rhi = bootstrap(rows)
    assert lo < 60 * 0.909 - 40 < hi and rlo < rhi
    stat, p, df = heterogeneity({"a": rows[:50], "b": rows[50:]})
    assert df == 1 and p < 0.05                          # first half all wins, second half mixed: heterogeneous
    runs, mu, rp = runs_test([True] * 30 + [False] * 30)
    assert runs == 2 and rp < 0.001                      # maximally streaky
    iid, cl, g = clustered_se(rows)
    assert g == 7 and iid > 0 and cl > 0
    mdd, longest, n = drawdown([dict(net=-1.0, win=False)] * 3 + [dict(net=0.909, win=True)] * 5)
    assert mdd == -3.0 and longest == 3 and n == 8
    assert 3 < expected_longest_streak(0.45, 100) < 8
    assert 0.17 < hetero_mde([130, 88, 106]) < 0.23         # matches the pooled doc's ~0.20 spread
    assert hetero_mde([1000, 1000, 1000]) < hetero_mde([50, 50, 50])  # more n, finer resolution
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    md = report(load(args.season))
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
