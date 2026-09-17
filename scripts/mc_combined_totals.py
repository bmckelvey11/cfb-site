"""Monte Carlo projection for the rest of the 2026 season: over-zero OVERs + Greenline totals.

    python scripts/mc_combined_totals.py
    python scripts/mc_combined_totals.py --paths 100000 --rho 0.15
    python scripts/mc_combined_totals.py --self-check

Two legs, very different shapes. Over-zero (floor bias, bias > 1.75) fires ~11
times across weeks 4-15 -- its volume is front-loaded into the FCS-cupcake weeks
that have already played. Greenline totals fires ~49 times a week, ~590 bets over
the same span, and is ~85% unders. So Greenline's assumed win rate IS the answer;
over-zero barely moves the terminal bankroll either way.

Which is why neither win rate is a point estimate here. Both are drawn per path
from the Beta posterior of their own graded record, so the output is a mixture
over parameter uncertainty, not a curve conditioned on a number the source data
does not establish. research/totals/docs/greenline-season-review-2026-09-16.md
says so explicitly: n=49, CI 41-68%, break-even 52.38% sits inside it.

Bets inside a week are correlated through one shared scoring environment: a high-
scoring Saturday helps every OVER and hurts every UNDER. Because over-zero is all
overs and Greenline is mostly unders, that shared factor correlates the two legs
NEGATIVELY. Modelled with a Gaussian copula on a per-week shock.

Pushes are not modelled: all 234 graded over-zero bets and all 49 graded Greenline
totals sat on half-point lines, so the realised push rate is 0.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np
from scipy.special import erfinv, ndtr

# --- Priors, all from graded records in this repo -------------------------------
# over-zero: 151-83 walk-forward, 2016-2025 (models/over_zero/docs/ROI_HITRATE.md)
OZ_WINS, OZ_LOSSES = 151, 83
# Greenline totals: 27-22, 2026 week 2
# (research/totals/docs/greenline-season-review-2026-09-16.md)
GL_WINS, GL_LOSSES = 27, 22

# MODEL_GUIDE.md: the 1.75 threshold was chosen on this data, so the 64.5% point
# estimate is selection-inflated. The guide says plan on the 58.2% lower bound.
OZ_SELECTION_HAIRCUT = (OZ_WINS / (OZ_WINS + OZ_LOSSES)) - 0.582  # ~0.063

# Volume, weeks 4-15. over-zero week-4+ counts by season: 2021..2025 = 8,11,9,11,14.
OZ_WEEK4PLUS_HISTORY = (8, 11, 9, 11, 14)
# Greenline: 49 gradeable totals flags in week 2, 57 flags in week 3.
GL_FLAGS_PER_WEEK = 49.0

WEEKS_REMAINING = 12  # weeks 4-15 of the 2026 regular season

# Prices. over-zero's operational rule is -120 or better; Greenline is graded -110.
OZ_PRICE, GL_PRICE = -120, -110


def payout(american: int) -> float:
    """Net return on a 1-unit stake for a win."""
    return 100.0 / abs(american) if american < 0 else american / 100.0


def breakeven(american: int) -> float:
    return 1.0 / (1.0 + payout(american))


@dataclass
class Config:
    bankroll: float = 20_000.0
    paths: int = 50_000
    rho: float = 0.10           # intra-week correlation through the scoring environment
    oz_unit: float = 0.01       # fraction of STARTING bankroll per over-zero bet
    gl_unit: float = 0.0025     # fraction of STARTING bankroll per Greenline bet
    oz_haircut: bool = True     # apply the guide's selection haircut to over-zero p
    seed: int = 20260917


def _copula_wins(rng, counts, shock, thresh, a, c, upper: bool) -> np.ndarray:
    """Wins per path when `counts` correlated bets share a per-week `shock`.

    Each bet's latent S = a*shock + c*eps. Conditional on the shock, bets are
    independent with probability q, so the count is Binomial(n, q) -- no need to
    draw every bet. That is what keeps ~590 bets x 50k paths cheap.
    """
    cond = (thresh - a * shock) / c
    q = ndtr(-cond) if upper else ndtr(cond)
    return rng.binomial(counts, np.clip(q, 0.0, 1.0))


def simulate(cfg: Config) -> dict:
    rng = np.random.default_rng(cfg.seed)
    n = cfg.paths

    # --- parameter draws, one per path -----------------------------------------
    # Jeffreys posterior: Beta(w + 1/2, l + 1/2).
    p_oz = rng.beta(OZ_WINS + 0.5, OZ_LOSSES + 0.5, n)
    if cfg.oz_haircut:
        p_oz = np.clip(p_oz - OZ_SELECTION_HAIRCUT, 0.01, 0.99)
    p_gl = rng.beta(GL_WINS + 0.5, GL_LOSSES + 0.5, n)

    oz_b, gl_b = payout(OZ_PRICE), payout(GL_PRICE)
    oz_stake = cfg.bankroll * cfg.oz_unit
    gl_stake = cfg.bankroll * cfg.gl_unit

    # thresholds on the latent scoring variable (see module docstring)
    z_oz = np.sqrt(2) * erfinv(2 * (1 - p_oz) - 1)   # OVER wins when S >  z_oz
    z_gl = -np.sqrt(2) * erfinv(2 * (1 - p_gl) - 1)  # UNDER wins when S <  z_gl

    oz_season = rng.poisson(rng.choice(OZ_WEEK4PLUS_HISTORY, n)).astype(np.int64)
    a, c = np.sqrt(cfg.rho), np.sqrt(1.0 - cfg.rho)

    pnl = np.zeros(n)
    turnover = np.zeros(n)
    worst_week = np.zeros(n)
    oz_remaining = oz_season.copy()

    for w in range(WEEKS_REMAINING):
        shock = rng.standard_normal(n)

        gl_n = rng.poisson(GL_FLAGS_PER_WEEK, n)
        gl_wins = _copula_wins(rng, gl_n, shock, z_gl, a, c, upper=False)
        week_pnl = gl_wins * gl_stake * gl_b - (gl_n - gl_wins) * gl_stake

        # over-zero's few bets thinned uniformly across the weeks that remain
        oz_n = rng.binomial(oz_remaining, 1.0 / (WEEKS_REMAINING - w))
        oz_remaining -= oz_n
        oz_wins = _copula_wins(rng, oz_n, shock, z_oz, a, c, upper=True)
        week_pnl += oz_wins * oz_stake * oz_b - (oz_n - oz_wins) * oz_stake

        pnl += week_pnl
        turnover += gl_n * gl_stake + oz_n * oz_stake
        worst_week = np.minimum(worst_week, week_pnl)

    return {
        "config": dict(cfg.__dict__, weeks=WEEKS_REMAINING),
        "p_oz_mean": float(p_oz.mean()),
        "p_gl_mean": float(p_gl.mean()),
        "p_gl_below_breakeven": float((p_gl < breakeven(GL_PRICE)).mean()),
        "p_oz_below_breakeven": float((p_oz < breakeven(OZ_PRICE)).mean()),
        "mean_turnover": float(turnover.mean()),
        "final": cfg.bankroll + pnl,
        "worst_week": worst_week,
    }


def report(res: dict, label: str) -> str:
    f = res["final"]
    b0 = res["config"]["bankroll"]
    qs = np.percentile(f, [1, 5, 10, 25, 50, 75, 90, 95, 99])
    return "\n".join([
        f"### {label}",
        "",
        f"- drawn win rates: over-zero mean {res['p_oz_mean']:.1%} "
        f"(P below break-even {res['p_oz_below_breakeven']:.0%}), "
        f"Greenline mean {res['p_gl_mean']:.1%} "
        f"(P below break-even {res['p_gl_below_breakeven']:.0%})",
        f"- total staked over the 12 weeks: ${res['mean_turnover']:,.0f} "
        f"({res['mean_turnover'] / b0:.1f}x the starting bankroll)",
        f"- **median ending bankroll ${np.median(f):,.0f}** "
        f"({np.median(f) / b0 - 1:+.1%})",
        f"- mean ${f.mean():,.0f} ({f.mean() / b0 - 1:+.1%})",
        "",
        "| pct | 1% | 5% | 10% | 25% | 50% | 75% | 90% | 95% | 99% |",
        "|---|" + "---:|" * 9,
        "| ending bankroll |" + "".join(f" ${q:,.0f} |" for q in qs),
        "",
        f"- P(end below ${b0:,.0f}): **{(f < b0).mean():.1%}**",
        f"- P(end below ${b0 * 0.75:,.0f}, -25%): {(f < b0 * 0.75).mean():.1%}",
        f"- P(end below ${b0 * 0.5:,.0f}, -50%): {(f < b0 * 0.5).mean():.1%}",
        f"- P(end above ${b0 * 1.25:,.0f}, +25%): {(f > b0 * 1.25).mean():.1%}",
        f"- worst single week: median ${np.median(res['worst_week']):,.0f}, "
        f"5th pct ${np.percentile(res['worst_week'], 5):,.0f}",
        "",
    ])


def self_check() -> None:
    """Smallest checks that fail if the copula or the payout maths break."""
    assert abs(breakeven(-110) - 0.5238) < 1e-3
    assert abs(breakeven(-120) - 0.5455) < 1e-3

    rng = np.random.default_rng(0)
    thresh = np.full(20_000, -np.sqrt(2) * erfinv(2 * (1 - 0.55) - 1))

    # near-zero rho with a fixed win rate must reproduce that win rate
    wins = _copula_wins(rng, np.full(20_000, 200), rng.standard_normal(20_000),
                        thresh, np.sqrt(1e-9), np.sqrt(1 - 1e-9), upper=False)
    assert abs(wins.mean() / 200 - 0.55) < 0.01, wins.mean() / 200

    # rho > 0 must inflate the variance of the win count, not its mean
    lo = _copula_wins(rng, np.full(20_000, 50), rng.standard_normal(20_000),
                      thresh, np.sqrt(0.01), np.sqrt(0.99), upper=False)
    hi = _copula_wins(rng, np.full(20_000, 50), rng.standard_normal(20_000),
                      thresh, np.sqrt(0.30), np.sqrt(0.70), upper=False)
    assert hi.std() > lo.std() * 1.5, (lo.std(), hi.std())
    assert abs(hi.mean() - lo.mean()) < 1.0, (lo.mean(), hi.mean())

    # an OVER and an UNDER at the same win rate must move opposite ways on a shock
    shock = rng.standard_normal(20_000)
    up = _copula_wins(rng, np.full(20_000, 50), shock, thresh,
                      np.sqrt(0.3), np.sqrt(0.7), upper=True)
    dn = _copula_wins(rng, np.full(20_000, 50), shock, thresh,
                      np.sqrt(0.3), np.sqrt(0.7), upper=False)
    assert np.corrcoef(up, dn)[0, 1] < -0.3, np.corrcoef(up, dn)[0, 1]

    # the Greenline posterior must keep real mass below break-even, or the sim
    # has smuggled in an edge the source data disclaims
    res = simulate(Config(paths=5_000, seed=2))
    assert 0.25 < res["p_gl_below_breakeven"] < 0.50, res["p_gl_below_breakeven"]
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bankroll", type=float, default=20_000.0)
    ap.add_argument("--paths", type=int, default=50_000)
    ap.add_argument("--rho", type=float, default=0.10)
    ap.add_argument("--oz-unit", type=float, default=0.01)
    ap.add_argument("--gl-unit", type=float, default=0.0025)
    ap.add_argument("--no-haircut", action="store_true",
                    help="skip the MODEL_GUIDE selection haircut on over-zero p")
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--json", help="write the scenario table here")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    base = Config(bankroll=args.bankroll, paths=args.paths, rho=args.rho,
                  oz_unit=args.oz_unit, gl_unit=args.gl_unit,
                  oz_haircut=not args.no_haircut, seed=args.seed)

    def variant(**kw):
        return Config(**dict(base.__dict__, **kw))

    scenarios = [
        ("Combined -- Greenline 0.25%, over-zero 1.0% (headline)", base),
        ("Combined -- Greenline 0.50%, over-zero 1.0%", variant(gl_unit=0.005)),
        ("Combined -- Greenline 1.0%, over-zero 1.0%", variant(gl_unit=0.01)),
        ("Over-zero only (Greenline stood down)", variant(gl_unit=0.0)),
        ("Greenline only, 0.25%", variant(oz_unit=0.0)),
        ("Headline, uncorrelated (rho=0) -- variance check", variant(rho=1e-9)),
        ("Headline, no selection haircut on over-zero", variant(oz_haircut=False)),
    ]

    out, blob = [], {}
    for label, cfg in scenarios:
        res = simulate(cfg)
        out.append(report(res, label))
        f = res["final"]
        blob[label] = {
            "median": float(np.median(f)), "mean": float(f.mean()),
            "p05": float(np.percentile(f, 5)), "p95": float(np.percentile(f, 95)),
            "p_loss": float((f < cfg.bankroll).mean()),
            "turnover": res["mean_turnover"],
            "p_gl_below_breakeven": res["p_gl_below_breakeven"],
        }
    print("\n".join(out))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(blob, fh, indent=2)


if __name__ == "__main__":
    main()
