"""Sweep Greenline stake and coverage on the combined-totals projection.

    python research/bankroll/scripts/bankroll_config_sweep.py
    python research/bankroll/scripts/bankroll_config_sweep.py --paths 50000 --out research/bankroll/docs
    python research/bankroll/scripts/bankroll_config_sweep.py --self-check

Runs mc_combined_totals.simulate over a grid of Greenline unit size x volume x
prior and scores every cell two ways:

  (a) max median gain subject to P(-25%) <= 1% and mid-season bust = 0%
  (b) ratio = median gain / (median - 5th pct), a Sharpe-like downside ratio

Volume is the operator's plan by default: 6-12 unders a week (GL_BETS_RANGE),
drawn uniformly and capped at the week's slate. --gl-volume slate restores the
coverage grid (13% supported, 25/50/100% conditional on the picked-flag win rate
transferring to flags that were passed on). The recommended row must pass (a)
under BOTH priors; with the slate grid it is also restricted to 13% coverage.

Over-zero stays at 1% throughout: it contributes ~11 bets and cannot move the
answer at any sane stake (see mc-combined-totals-2026-09-17.md).

Stakes are re-sized off the bankroll at the start of each week (the simulator's
default); --flat-stakes keeps them fixed off the starting bankroll.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mc_combined_totals import (  # noqa: E402
    GL_BETS_RANGE, GL_COVERAGE_HISTORICAL, GL_FLAGS_BY_WEEK, GL_FLAGS_FULL_SEASON, WEEKS_REMAINING,
    Config, simulate, kelly_unit, planning_p_gl,
    BLUE, GREEN, RED, GOLD, INK, MUTED, GRID, _style,
)

GL_UNITS = (0.0025, 0.005, 0.01, 0.015, 0.02)
COVERAGES = (GL_COVERAGE_HISTORICAL, 0.25, 0.50, 1.0)
RANGE_KEY = -1.0  # the coverage column's value for a range-volume row
# planning prior first; n58 and pooled are the bracket, reported but not decisive
PRIORS = ("k0.5", "n58", "pooled")
PRIOR_KW = {"k0.5": dict(gl_kappa=0.5), "n58": dict(gl_kappa=None, gl_prior="n58"),
            "pooled": dict(gl_kappa=None, gl_prior="pooled")}
PLANNING = "k0.5"

MAX_P_M25 = 0.03   # constraint (a): at most 3% of paths end a season down 25%+ (growth frame)
MAX_BUST = 0.0     # constraint (a): no path passes through zero


def expected_range_bets(weeks=GL_FLAGS_BY_WEEK) -> float:
    lo, hi = GL_BETS_RANGE
    return sum(sum(min(k, f) for k in range(lo, hi + 1)) / (hi - lo + 1) for f in weeks)


def run_grid(paths: int, seed: int, bankroll: float, volume: str = "range",
             resize: bool = True, seasons: int = 1, max_p_m25: float = MAX_P_M25) -> list[dict]:
    rows = []
    covs = (RANGE_KEY,) if volume == "range" else COVERAGES
    weeks = GL_FLAGS_BY_WEEK + GL_FLAGS_FULL_SEASON * (seasons - 1)
    for prior in PRIORS:
        for cov in covs:
            for unit in GL_UNITS:
                res = simulate(Config(bankroll=bankroll, paths=paths, gl_unit=unit,
                                      gl_volume=volume, resize_weekly=resize,
                                      gl_coverage=(1.0 if cov == RANGE_KEY else cov),
                                      seasons=seasons, seed=seed, **PRIOR_KW[prior]))
                f = res["final"]
                med, p5, p95 = np.percentile(f, [50, 5, 95])
                gain = med - bankroll
                rows.append({
                    "prior": prior,
                    "gl_unit": unit,
                    "coverage": cov,
                    "supported": cov in (GL_COVERAGE_HISTORICAL, RANGE_KEY),
                    "gl_bets": round(expected_range_bets(weeks) if cov == RANGE_KEY
                                     else sum(weeks) * cov),
                    "staked": res["mean_turnover"],
                    "median": med,
                    "median_pct": gain / bankroll,
                    "p5": p5,
                    "p95": p95,
                    "p_down": float((f < bankroll).mean()),
                    "p_m25": float((f < bankroll * 0.75).mean()),
                    "p_bust": res["p_bust"],
                    "worst_week_med": float(np.median(res["worst_week"])),
                    # (b): gain per dollar of downside spread; 0 or negative when the
                    # median itself is a loss
                    "ratio": gain / (med - p5) if med > p5 else 0.0,
                    "passes_a": res["p_bust"] <= MAX_BUST
                                and float((f < bankroll * 0.75).mean()) <= max_p_m25,
                })
    return rows


def recommend(rows: list[dict]) -> tuple[dict | None, dict | None]:
    """(recommended, best_conditional).

    recommended: supported coverage only, constraint (a) under the PLANNING prior,
    ranked by the planning prior's median. n58 and pooled rows ride along as the
    bracket.
    best_conditional: same rule without the coverage restriction -- what the
    grid would pick if the coverage transfer held. Reported, never recommended.
    """
    def best(candidates):
        by_key = {}
        for r in candidates:
            by_key.setdefault((r["gl_unit"], r["coverage"]), []).append(r)
        ok = [(next(r["median"] for r in rs if r["prior"] == PLANNING), rs)
              for rs in by_key.values()
              if len(rs) == len(PRIORS) and all(r["passes_a"] for r in rs if r["prior"] == PLANNING)]
        if not ok:
            return None
        _, rs = max(ok, key=lambda t: t[0])
        r = dict(rs[0])
        r["median_by_prior"] = {x["prior"]: x["median"] for x in rs}
        r["p_down_by_prior"] = {x["prior"]: x["p_down"] for x in rs}
        r["p5_by_prior"] = {x["prior"]: x["p5"] for x in rs}
        r["p95_by_prior"] = {x["prior"]: x["p95"] for x in rs}
        r["ratio_by_prior"] = {x["prior"]: x["ratio"] for x in rs}
        return r
    return best([r for r in rows if r["supported"]]), best(rows)


def to_markdown(rows: list[dict], bankroll: float) -> str:
    out = []
    for prior in PRIORS:
        out.append(f"### `{prior}` prior\n")
        out.append("| GL unit | coverage | GL bets | staked | median | 5th | 95th | "
                   "P(down) | P(-25%) | busts | ratio | passes (a) |")
        out.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")
        for r in rows:
            if r["prior"] != prior:
                continue
            cov = (f"{GL_BETS_RANGE[0]}-{GL_BETS_RANGE[1]}/wk" if r["coverage"] == RANGE_KEY
                   else f"{r['coverage']:.0%}" + ("" if r["supported"] else " *"))
            out.append(
                f"| {r['gl_unit']:.2%} | {cov} | ~{r['gl_bets']} | ${r['staked']/1000:,.1f}k | "
                f"${r['median']:,.0f} ({r['median_pct']:+.1%}) | ${r['p5']:,.0f} | "
                f"${r['p95']:,.0f} | {r['p_down']:.1%} | {r['p_m25']:.1%} | "
                f"{r['p_bust']:.1%} | {r['ratio']:.2f} | {'yes' if r['passes_a'] else 'no'} |")
        out.append("")
    if any(not r["supported"] for r in rows):
        out.append("`*` coverage above the historical 13% is conditional on the picked-flag "
                   "win rate transferring to flags that were passed on. Not supported by the "
                   "record; shown so the tradeoff is visible.\n")
    return "\n".join(out)


def figure(rows: list[dict], bankroll: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = dict(zip(COVERAGES, (BLUE, GREEN, GOLD, RED)))
    colors[RANGE_KEY] = BLUE
    covs = sorted({r["coverage"] for r in rows})
    fig, axes = plt.subplots(2, len(PRIORS), figsize=(5.5 * len(PRIORS), 7.5))
    for j, prior in enumerate(PRIORS):
        top, bot = axes[0, j], axes[1, j]
        for cov in covs:
            rs = [r for r in rows if r["prior"] == prior and r["coverage"] == cov]
            x = [r["gl_unit"] * 100 for r in rs]
            label = (f"{GL_BETS_RANGE[0]}-{GL_BETS_RANGE[1]} unders a week" if cov == RANGE_KEY
                     else f"{cov:.0%} of flags" + ("" if cov == GL_COVERAGE_HISTORICAL else " (conditional)"))
            top.plot(x, [r["median_pct"] * 100 for r in rs], "-o", color=colors[cov],
                     lw=1.8, ms=4, label=label)
            top.fill_between(x, [(r["p5"] / bankroll - 1) * 100 for r in rs],
                             [(r["p95"] / bankroll - 1) * 100 for r in rs],
                             color=colors[cov], alpha=0.08, lw=0)
            bot.plot(x, [r["p_m25"] * 100 for r in rs], "-o", color=colors[cov], lw=1.8, ms=4)
        top.axhline(0, color=MUTED, lw=0.8, ls="--")
        bot.axhline(MAX_P_M25 * 100, color=RED, lw=0.8, ls="--")
        bot.text(GL_UNITS[-1] * 100, MAX_P_M25 * 100 + 0.3, f"{MAX_P_M25:.0%} limit", color=RED,
                 fontsize=8, ha="right")
        for ax in (top, bot):
            _style(ax)
            ax.set_xlabel("Greenline stake, % of bankroll (re-sized weekly)")
        top.set_ylabel("median ending gain, %  (band = 5th-95th)")
        bot.set_ylabel("P(end down 25% or more), %")
        top.set_title(f"`{prior}` prior" + ("  (planning)" if prior == PLANNING else "  (bracket)"), fontsize=11)
        if j == 0:
            top.legend(fontsize=8, frameon=False, loc="upper left")
    what = "Unit sweep" if RANGE_KEY in covs else "Stake x coverage sweep"
    fig.suptitle("%s, $%s, weeks 4-15 of 2026" % (what, f"{bankroll:,.0f}"),
                 fontsize=14, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"wrote {path}")


def self_check() -> None:
    rows = run_grid(paths=3_000, seed=1, bankroll=20_000, volume="slate", resize=False, max_p_m25=0.01)
    assert len(rows) == len(PRIORS) * len(COVERAGES) * len(GL_UNITS)
    # stake scales spread, not sign: 95th-5th must widen with the unit
    for prior in PRIORS:
        rs = [r for r in rows if r["prior"] == prior and r["coverage"] == 1.0]
        widths = [r["p95"] - r["p5"] for r in rs]
        assert all(b > a for a, b in zip(widths, widths[1:])), widths
    # the constraint must actually bite somewhere on the grid
    assert any(not r["passes_a"] for r in rows)
    assert any(r["passes_a"] for r in rows)
    rec, cond = recommend(rows)
    assert rec is not None and rec["supported"]
    assert cond is not None
    assert cond["median"] >= rec["median"]
    # range volume: one coverage key, every row supported, ~107 bets
    rows = run_grid(paths=3_000, seed=1, bankroll=20_000)
    assert len(rows) == len(PRIORS) * len(GL_UNITS)
    assert all(r["supported"] and r["coverage"] == RANGE_KEY for r in rows)
    assert 100 < rows[0]["gl_bets"] < 116, rows[0]["gl_bets"]
    assert recommend(rows)[0] is not None
    # two seasons roughly doubles the bets
    rows2 = run_grid(paths=2_000, seed=1, bankroll=20_000, seasons=2)
    assert 220 < rows2[0]["gl_bets"] < 250, rows2[0]["gl_bets"]
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bankroll", type=float, default=20_000.0)
    ap.add_argument("--paths", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--out", help="directory: writes sweep .csv, .md and figs/ .png")
    ap.add_argument("--gl-volume", choices=("range", "slate"), default="range",
                    help="range: 6-12 unders a week (default); slate: the coverage grid")
    ap.add_argument("--flat-stakes", action="store_true",
                    help="flat units off the starting bankroll instead of weekly re-sizing")
    ap.add_argument("--seasons", type=int, default=1, help="1 = rest of 2026; 2 adds full 2027")
    ap.add_argument("--max-p-m25", type=float, default=MAX_P_M25,
                    help="constraint (a): max share of paths ending down 25%% or more")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return

    rows = run_grid(args.paths, args.seed, args.bankroll, args.gl_volume, not args.flat_stakes,
                    args.seasons, args.max_p_m25)
    p_plan = planning_p_gl(0.5)
    print(f"planning prior kappa 0.5: mean {p_plan:.1%}; quarter Kelly per bet, 9 simultaneous: "
          f"{kelly_unit(p_plan, -110):.2%}  (single-bet quarter Kelly {kelly_unit(p_plan, -110, n_simul=1):.2%})")
    print(f"constraint (a): P(-25%) <= {args.max_p_m25:.0%}, no busts, under the planning prior; "
          f"{args.seasons} season(s)\n")
    rec, cond = recommend(rows)
    print(to_markdown(rows, args.bankroll))
    for label, r in (("RECOMMENDED (supported volume, (a) under both priors)", rec),
                     ("best if coverage transfer held (conditional, not recommended)", cond)):
        if r is None:
            print(f"{label}: no row passes")
            continue
        vol = ("6-12/wk" if r["coverage"] == RANGE_KEY else f"coverage {r['coverage']:.0%}")
        print(f"{label}: GL unit {r['gl_unit']:.2%}, {vol}, ~{r['gl_bets']} bets")
        rs = [x for x in rows if x["gl_unit"] == r["gl_unit"] and x["coverage"] == r["coverage"]]
        r["median_by_prior"] = {x["prior"]: x["median"] for x in rs}
        r["p_down_by_prior"] = {x["prior"]: x["p_down"] for x in rs}
        r["p5_by_prior"] = {x["prior"]: x["p5"] for x in rs}
        r["p95_by_prior"] = {x["prior"]: x["p95"] for x in rs}
        r["ratio_by_prior"] = {x["prior"]: x["ratio"] for x in rs}
        for p in PRIORS:
            print(f"  {p}: median ${r['median_by_prior'][p]:,.0f} "
                  f"({r['median_by_prior'][p] / args.bankroll - 1:+.1%}), "
                  f"5th ${r['p5_by_prior'][p]:,.0f}, 95th ${r['p95_by_prior'][p]:,.0f}, "
                  f"P(down) {r['p_down_by_prior'][p]:.1%}, ratio {r['ratio_by_prior'][p]:.2f}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stem = "bankroll-config-sweep-2026-09-21"
        with open(out / f"{stem}.csv", "w", newline="") as fh:
            keys = [k for k in rows[0] if not k.endswith("_by_prior")]
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows({k: r[k] for k in keys} for r in rows)
        (out / f"{stem}.md").write_text(to_markdown(rows, args.bankroll), encoding="utf-8")
        figure(rows, args.bankroll, out / "figs" / f"{stem}.png")
        print(f"wrote {out / (stem + '.csv')} and .md")


if __name__ == "__main__":
    main()
