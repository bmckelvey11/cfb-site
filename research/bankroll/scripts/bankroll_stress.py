"""Stress the 0.5% / 1% recommendation against a more skeptical uncertainty model.

    python research/bankroll/scripts/bankroll_stress.py --paths 50000 --out research/bankroll/docs
    python research/bankroll/scripts/bankroll_stress.py --self-check

Answers the outside review of mc-method-2026-09-17.md: does 0.5% still pass the
risk limit (P(-25%) <= 3%, no busts) when
  - the over-zero selection haircut is uncertain (extra sd) or larger (center 56.5%),
  - the Greenline prior is partially pooled (kappa in 0..1) instead of two endpoints,
  - Greenline bets beyond 6 a week win at p - d (marginal-bet degradation),
  - same-slate correlation rho runs 0 to 0.5,
  - all of the skeptical settings are applied together?

Every scenario is run at Greenline units 0.5%, 1.0% and 1.2% (quarter Kelly off the planning prior), over-zero 1%, 6-12 unders a
week, weekly re-sizing. Path-dependent risk (max drawdown, weeks under water,
expected shortfall) is reported alongside the terminal numbers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mc_combined_totals import Config, simulate  # noqa: E402

UNITS = (0.005, 0.01, 0.012)
MAX_P_M25, MAX_BUST = 0.03, 0   # growth frame: 3% per horizon, no busts

# (group, label, config overrides). gl_prior is used when gl_kappa is None.
SCENARIOS = [
    ("base", "planning prior kappa 0.5", dict(gl_kappa=0.5)),
    ("base", "pooled prior", dict(gl_kappa=None, gl_prior="pooled")),
    ("base", "n58 prior", dict(gl_kappa=None, gl_prior="n58")),
    ("over-zero", "center 56.5%, pooled", dict(gl_kappa=None, gl_prior="pooled", oz_center=0.565)),
    ("over-zero", "haircut sd +3pt, pooled", dict(gl_kappa=None, gl_prior="pooled", oz_extra_sd=0.03)),
    ("over-zero", "center 56.5% + sd 4pt, n58", dict(gl_kappa=None, gl_prior="n58", oz_center=0.565, oz_extra_sd=0.04)),
] + [
    ("kappa", f"kappa {k:.2f}", dict(gl_kappa=k)) for k in (0.0, 0.25, 0.75, 1.0)
] + [
    ("marginal", f"bets 7-12 at p-{d}pt, pooled", dict(gl_kappa=None, gl_prior="pooled", gl_marginal_penalty=d / 100))
    for d in (1, 2, 3)
] + [
    ("marginal", f"bets 7-12 at p-{d}pt, n58", dict(gl_kappa=None, gl_prior="n58", gl_marginal_penalty=d / 100))
    for d in (2,)
] + [
    ("rho", f"rho {r:.2f}, pooled", dict(gl_kappa=None, gl_prior="pooled", rho=r)) for r in (0.0, 0.05, 0.2, 0.35, 0.5)
] + [
    ("rho", f"rho {r:.2f}, n58", dict(gl_kappa=None, gl_prior="n58", rho=r)) for r in (0.2, 0.35, 0.5)
] + [
    ("combined", "kappa 0.5, p-2pt, oz 56.5%+sd3, rho 0.2",
     dict(gl_kappa=0.5, gl_marginal_penalty=0.02, oz_center=0.565, oz_extra_sd=0.03, rho=0.2)),
    ("combined", "kappa 0.25, p-3pt, oz 56.5%+sd4, rho 0.35",
     dict(gl_kappa=0.25, gl_marginal_penalty=0.03, oz_center=0.565, oz_extra_sd=0.04, rho=0.35)),
    ("combined", "kappa 0, p-3pt, oz 56.5%+sd4, rho 0.5  (worst)",
     dict(gl_kappa=0.0, gl_marginal_penalty=0.03, oz_center=0.565, oz_extra_sd=0.04, rho=0.5)),
]


def run(paths: int, seed: int, bankroll: float) -> list[dict]:
    rows = []
    for group, label, kw in SCENARIOS:
        for unit in UNITS:
            res = simulate(Config(bankroll=bankroll, paths=paths, gl_unit=unit, seed=seed, **kw))
            f = res["final"]
            q5 = np.percentile(f, 5)
            rows.append(dict(
                group=group, label=label, unit=unit,
                p_gl=res["p_gl_mean"], p_oz=res["p_oz_mean"],
                median=float(np.median(f)), p5=float(q5),
                es5=float(f[f <= q5].mean()),                      # expected shortfall, 5%
                p_down=float((f < bankroll).mean()),
                p_m25=float((f < 0.75 * bankroll).mean()),
                n_m25=int((f < 0.75 * bankroll).sum()),
                n_bust=res["n_bust"],
                dd50=float(np.median(res["max_dd"])), dd95=float(np.percentile(res["max_dd"], 95)),
                p_dd10=float((res["max_dd"] > 0.10 * bankroll).mean()),
                p_dd20=float((res["max_dd"] > 0.20 * bankroll).mean()),
                under50=float(np.median(res["weeks_under"])),
                paths=paths,
            ))
    return rows


def passes(r: dict) -> bool:
    return r["p_m25"] <= MAX_P_M25 and r["n_bust"] <= MAX_BUST


def to_markdown(rows: list[dict], bankroll: float) -> str:
    out = ["| group | scenario | unit | p_GL | p_OZ | median | 5th | ES5 | P(down) | P(-25%) | busts | maxDD med / 95th | P(DD>10%) | P(DD>20%) | wks under | passes |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|:---:|"]
    for r in rows:
        out.append(
            f"| {r['group']} | {r['label']} | {r['unit']:.1%} | {r['p_gl']:.1%} | {r['p_oz']:.1%} | "
            f"${r['median']:,.0f} | ${r['p5']:,.0f} | ${r['es5']:,.0f} | {r['p_down']:.1%} | "
            f"{r['n_m25']}/{r['paths']:,} ({r['p_m25']:.2%}) | {r['n_bust']} | "
            f"${r['dd50']:,.0f} / ${r['dd95']:,.0f} | {r['p_dd10']:.1%} | {r['p_dd20']:.1%} | "
            f"{r['under50']:.0f} | {'yes' if passes(r) else 'no'} |")
    return "\n".join(out)


def verdict(rows: list[dict]) -> str:
    lines = []
    for unit in UNITS:
        rs = [r for r in rows if r["unit"] == unit]
        fails = [r["label"] for r in rs if not passes(r)]
        lines.append(f"{unit:.1%}: passes {len(rs) - len(fails)}/{len(rs)} scenarios"
                     + (f"; fails: {', '.join(fails)}" if fails else ""))
    return "\n".join(lines)


def self_check() -> None:
    rows = run(paths=2_000, seed=1, bankroll=20_000)
    assert len(rows) == len(SCENARIOS) * len(UNITS)
    by = {(r["label"], r["unit"]): r for r in rows}
    # kappa endpoints reproduce the named priors' means
    assert abs(by[("kappa 0.00", 0.005)]["p_gl"] - by[("n58 prior", 0.005)]["p_gl"]) < 0.01
    assert abs(by[("kappa 1.00", 0.005)]["p_gl"] - by[("pooled prior", 0.005)]["p_gl"]) < 0.01
    assert abs(by[("planning prior kappa 0.5", 0.005)]["p_gl"] - 0.561) < 0.01
    # the worst combined case must be worse than base n58 at the same unit
    assert by[("kappa 0, p-3pt, oz 56.5%+sd4, rho 0.5  (worst)", 0.01)]["median"] < by[("n58 prior", 0.01)]["median"]
    assert all(r["es5"] <= r["p5"] for r in rows)
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bankroll", type=float, default=20_000.0)
    ap.add_argument("--paths", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--out", help="docs directory; writes bankroll-stress-2026-09-21.md table")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    rows = run(args.paths, args.seed, args.bankroll)
    md = to_markdown(rows, args.bankroll)
    print(md)
    print()
    print(verdict(rows))
    if args.out:
        out = Path(args.out) / "bankroll-stress-table-2026-09-21.md"
        out.write_text(md + "\n\n" + verdict(rows) + "\n", encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
