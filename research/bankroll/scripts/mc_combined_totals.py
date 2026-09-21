"""Monte Carlo projection for the rest of the 2026 season: over-zero OVERs + Greenline totals.

    python research/bankroll/scripts/mc_combined_totals.py
    python research/bankroll/scripts/mc_combined_totals.py --paths 100000
    python research/bankroll/scripts/mc_combined_totals.py --self-check

Two legs, very different shapes. Over-zero (floor bias, bias > 1.75) fires ~11
times across weeks 4-15 -- its volume is front-loaded into the FCS-cupcake weeks
that have already played. Greenline totals flags every FBS-vs-FBS game, ~49-57 a
week, and is ~85% unders; the plan bets 6-12 of those unders. So Greenline's
assumed win rate IS the answer; over-zero barely moves the terminal bankroll
either way.

Which is why neither win rate is a point estimate here. Both are drawn per path
from the Beta posterior of their own graded record, so the output is a mixture
over parameter uncertainty, not a curve conditioned on a number the source data
does not establish. The Greenline record is the published under list graded by
research/totals/scripts/grade_unders_list.py: n=58, CI 42.5-67.3%, break-even
52.38% sits inside it.

Bets inside a week are correlated through one shared scoring environment: a high-
scoring Saturday helps every OVER and hurts every UNDER. Because over-zero is all
overs and Greenline is mostly unders, that shared factor correlates the two legs
NEGATIVELY. Modelled with a Gaussian copula on a per-week shock.

Pushes are not modelled: all 234 graded over-zero bets and all 58 graded Greenline
under picks sat on half-point lines, so the realised push rate is 0.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.special import erfinv, ndtr

# --- Priors, all from graded records in this repo -------------------------------
# over-zero: 151-83 walk-forward, 2016-2025 (models/over_zero/docs/ROI_HITRATE.md)
OZ_WINS, OZ_LOSSES = 151, 83
# Greenline totals. Three defensible priors, selected with --gl-prior.
#  n58         32-26, the published 2026 under list, weeks 2-3 (36 + 22 picks),
#              graded at PFF's number and at DraftKings' -- identical both ways
#              (research/totals/docs/greenline-w3-grade-2026-09-21.md;
#              research/totals/scripts/grade_unders_list.py --week 2 --week 3).
#              This is the bet population: the plan bets unders off that list,
#              never the over flags. The all-flags reading is 58-48 and the
#              unders-only-flags reading is 46-42; both are in the bracket table
#              of the proposal, neither is what gets staked.
#  pooled      + the 201 full-game unders in the personal book export, 2023-08
#              to 2025-12, 114-87 at a mean price of -110.1
#              (docs/bet-history-analysis-2023-2025.md,
#              data/ingest/bet_history/history.csv). Pooled as PRIOR EVIDENCE:
#              those unders were mostly PFF Greenline flags, so this is the
#              same signal in earlier seasons, never independent confirmation.
#  pff-window  the same pooling restricted to 2024-25 (72-50), the slice most
#              strongly identified as PFF-driven. Sensitivity only.
GL_PRIORS = {"n58": (32, 26), "pooled": (146, 113), "pff-window": (104, 76)}

# MODEL_GUIDE.md: the 1.75 threshold was chosen on this data, so the 64.5% point
# estimate is selection-inflated. The guide says plan on the 58.2% lower bound.
OZ_SELECTION_HAIRCUT = (OZ_WINS / (OZ_WINS + OZ_LOSSES)) - 0.582  # ~0.063

# Volume, weeks 4-15. over-zero week-4+ counts by season: 2021..2025 = 8,11,9,11,14.
OZ_WEEK4PLUS_HISTORY = (8, 11, 9, 11, 14)
# Greenline: 49 gradeable totals flags in week 2, 57 flagged in week 3. 49 is the
# graded count and the conservative floor of the two; it is the `constant` volume.
GL_FLAGS_PER_WEEK = 49.0
# But Greenline flags EVERY FBS-vs-FBS game: week 2 had 49 such games and 49 flags,
# week 3 had 57 and 57. So the weekly count is the slate, and the slate is known.
# core.fact_game, 2026 regular season, both teams is_fbs, weeks 4-13; weeks 14-15
# are not scheduled in the warehouse yet, so they take 2025's counts (67, 9).
# Queried 2026-09-17. This is the `slate` volume and the default.
GL_FLAGS_BY_WEEK = (58, 56, 58, 59, 56, 56, 62, 67, 66, 65, 67, 9)
# `range` volume: a stated number of unders a week, drawn uniformly from this
# closed interval and capped at that week's slate. 6-12 is the operator's plan;
# its mean of 9 is ~16% of a typical slate, a little above the 13% historical rate.
GL_BETS_RANGE = (6, 12)
# A full later season (2027+): the 2025 FBS-vs-FBS slate, weeks 1-15, from
# core.fact_game (the 1-game week 16 dropped). Bowls and the playoff excluded.
GL_FLAGS_FULL_SEASON = (48, 51, 47, 50, 51, 50, 56, 59, 53, 52, 51, 58, 60, 67, 9)
# over-zero full-season counts, 2022-2025 (ROI_HITRATE.md), and their weekly
# shape: ~68% of a season's bets land in weeks 1-3 (2024: 19 of 30; 2025: 37 of 51).
OZ_SEASON_HISTORY = (37, 40, 30, 51)
OZ_EARLY_SHARE, OZ_EARLY_WEEKS = 0.68, 3

# What fraction of the flags actually gets bet. The 201-bet personal record came
# from roughly 92 unders in 2025 against ~690 flags at this rate -- about 13%.
# Betting all 49 a week is a DIFFERENT population from the one that record
# measures: the other 87% are the flags he passed on, and they have no record.
GL_COVERAGE_HISTORICAL = 0.13

WEEKS_REMAINING = 12  # weeks 4-15 of the 2026 regular season

PCTS = [5, 25, 50, 75, 95]  # the fan chart's bands

# Prices. over-zero's operational rule is -120 or better; Greenline is graded -110.
OZ_PRICE, GL_PRICE = -120, -110


def payout(american: int) -> float:
    """Net return on a 1-unit stake for a win."""
    return 100.0 / abs(american) if american < 0 else american / 100.0


def breakeven(american: int) -> float:
    return 1.0 / (1.0 + payout(american))


def kelly_unit(p: float, american: int, fraction: float = 0.25, n_simul: float = 9.0,
               rho_outcome: float = 0.063) -> float:
    """Fractional Kelly for one bet, then shrunk for n_simul simultaneous bets that
    share outcome correlation rho_outcome: f / (1 + (n-1) rho). Small-edge approx."""
    b = payout(american)
    f = max((p * b - (1 - p)) / b, 0.0)
    return fraction * f / (1 + (n_simul - 1) * rho_outcome)


def planning_p_gl(kappa: float = 0.5) -> float:
    """Posterior mean of the planning prior."""
    w = GL_PRIORS["n58"][0] + kappa * 114 + 0.5
    l = GL_PRIORS["n58"][1] + kappa * 87 + 0.5
    return w / (w + l)


@dataclass
class Config:
    bankroll: float = 20_000.0
    paths: int = 50_000
    rho: float = 0.10           # intra-week correlation through the scoring environment
    oz_unit: float = 0.01       # fraction of STARTING bankroll per over-zero bet
    gl_unit: float = 0.0025     # fraction of STARTING bankroll per Greenline bet
    oz_haircut: bool = True     # apply the guide's selection haircut to over-zero p
    gl_prior: str = "pooled"    # key into GL_PRIORS, used only when gl_kappa is None
    gl_coverage: float = 1.0    # fraction of weekly Greenline flags actually bet
    gl_volume: str = "range"    # "range": GL_BETS_RANGE unders/wk; "slate": coverage x schedule; "constant": coverage x 49
    gl_range: tuple = GL_BETS_RANGE
    resize_weekly: bool = True  # units off the bankroll at the start of each week
    seed: int = 20260921
    # --- stress knobs (bankroll_stress.py); defaults reproduce the base model ---
    oz_center: float | None = None   # override the post-haircut over-zero mean (e.g. 0.565)
    oz_extra_sd: float = 0.0         # add N(0, sd) to each path's over-zero haircut
    gl_kappa: float | None = 0.5     # PLANNING PRIOR: Beta(27.5 + k*114, 22.5 + k*87); None -> gl_prior
    seasons: int = 1                 # 1 = rest of 2026; each extra season is a full 15-week 2027-style season
    gl_marginal_penalty: float = 0.0 # Greenline bets beyond GL_MARGINAL_BASE a week win at p - d
    gl_marginal_base: int = 6        # the first N bets a week keep the full p


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
        # The haircut is a point correction by default. oz_extra_sd makes the
        # selection correction itself uncertain (review item 1); oz_center moves it.
        haircut = OZ_SELECTION_HAIRCUT + (rng.normal(0.0, cfg.oz_extra_sd, n) if cfg.oz_extra_sd else 0.0)
        if cfg.oz_center is not None:
            haircut += (OZ_WINS / (OZ_WINS + OZ_LOSSES) - OZ_SELECTION_HAIRCUT) - cfg.oz_center
        p_oz = np.clip(p_oz - haircut, 0.01, 0.99)
    if cfg.gl_kappa is None:
        gl_w, gl_l = GL_PRIORS[cfg.gl_prior]
        p_gl = rng.beta(gl_w + 0.5, gl_l + 0.5, n)
    else:
        # Partial pooling: the 201 personal unders (114-87) count kappa-fold.
        # kappa=0 is n58, kappa=1 is pooled.
        gl_w = GL_PRIORS["n58"][0] + cfg.gl_kappa * 114
        gl_l = GL_PRIORS["n58"][1] + cfg.gl_kappa * 87
        p_gl = rng.beta(gl_w + 0.5, gl_l + 0.5, n)
    p_gl_marg = np.clip(p_gl - cfg.gl_marginal_penalty, 0.01, 0.99)

    oz_b, gl_b = payout(OZ_PRICE), payout(GL_PRICE)
    oz_stake = cfg.bankroll * cfg.oz_unit
    gl_stake = cfg.bankroll * cfg.gl_unit

    # thresholds on the latent scoring variable (see module docstring)
    z_oz = np.sqrt(2) * erfinv(2 * (1 - p_oz) - 1)   # OVER wins when S >  z_oz
    z_gl = -np.sqrt(2) * erfinv(2 * (1 - p_gl) - 1)  # UNDER wins when S <  z_gl
    z_gl_marg = -np.sqrt(2) * erfinv(2 * (1 - p_gl_marg) - 1)

    a, c = np.sqrt(cfg.rho), np.sqrt(1.0 - cfg.rho)
    # One entry per simulated week: (Greenline slate, over-zero thinning weight,
    # season index). Season 0 is the rest of 2026; later seasons are full.
    schedule = [(f, 1.0, 0) for f in GL_FLAGS_BY_WEEK]
    for s_ix in range(1, cfg.seasons):
        nw = len(GL_FLAGS_FULL_SEASON)
        early = OZ_EARLY_SHARE / OZ_EARLY_WEEKS
        late = (1 - OZ_EARLY_SHARE) / (nw - OZ_EARLY_WEEKS)
        schedule += [(f, early if i < OZ_EARLY_WEEKS else late, s_ix)
                     for i, f in enumerate(GL_FLAGS_FULL_SEASON)]
    n_weeks = len(schedule)
    oz_by_season = [rng.poisson(rng.choice(OZ_WEEK4PLUS_HISTORY, n)).astype(np.int64)]
    oz_by_season += [rng.poisson(rng.choice(OZ_SEASON_HISTORY, n)).astype(np.int64)
                     for _ in range(1, cfg.seasons)]

    pnl = np.zeros(n)
    turnover = np.zeros(n)
    worst_week = np.zeros(n)
    running_min = np.zeros(n)  # deepest drawdown, for the mid-season bust check
    peak = np.zeros(n)         # running peak of cumulative pnl, for max drawdown
    max_dd = np.zeros(n)       # largest peak-to-trough fall, in dollars
    weeks_under = np.zeros(n)  # weeks ending below the starting bankroll
    oz_remaining = oz_by_season[0].copy()
    cur_season = 0
    # Percentiles of the bankroll after each week. Keeping the quantiles rather than
    # the paths is what makes a fan chart affordable at 100k paths.
    fan = [np.percentile(np.full(n, cfg.bankroll), PCTS)]

    for w, (flags_w, oz_wt, s_ix) in enumerate(schedule):
        if s_ix != cur_season:
            cur_season = s_ix
            oz_remaining = oz_by_season[s_ix].copy()
        # this week's share of the season's remaining over-zero bets
        wts_left = [wt for f, wt, s in schedule[w:] if s == s_ix]
        oz_p = oz_wt / sum(wts_left)
        shock = rng.standard_normal(n)
        if cfg.resize_weekly:
            # Weekly compounding: units re-sized off the bankroll as it stands before
            # the week's slate. Within a week stakes are still flat -- Saturday
            # kickoffs are simultaneous. A path at or below zero stops betting.
            live = np.maximum(cfg.bankroll + pnl, 0.0)
            oz_stake = live * cfg.oz_unit
            gl_stake = live * cfg.gl_unit

        if cfg.gl_volume == "range":
            lo, hi = cfg.gl_range
            gl_n = np.minimum(rng.integers(lo, hi + 1, n), flags_w)
        else:
            flags = flags_w if cfg.gl_volume == "slate" else GL_FLAGS_PER_WEEK
            gl_n = rng.poisson(flags * cfg.gl_coverage, n)
        if cfg.gl_marginal_penalty > 0:
            base_n = np.minimum(gl_n, cfg.gl_marginal_base)
            gl_wins = (_copula_wins(rng, base_n, shock, z_gl, a, c, upper=False)
                       + _copula_wins(rng, gl_n - base_n, shock, z_gl_marg, a, c, upper=False))
        else:
            gl_wins = _copula_wins(rng, gl_n, shock, z_gl, a, c, upper=False)
        week_pnl = gl_wins * gl_stake * gl_b - (gl_n - gl_wins) * gl_stake

        # over-zero's few bets thinned uniformly across the weeks that remain
        oz_n = rng.binomial(oz_remaining, oz_p)
        oz_remaining -= oz_n
        oz_wins = _copula_wins(rng, oz_n, shock, z_oz, a, c, upper=True)
        week_pnl += oz_wins * oz_stake * oz_b - (oz_n - oz_wins) * oz_stake

        pnl += week_pnl
        turnover += gl_n * gl_stake + oz_n * oz_stake
        worst_week = np.minimum(worst_week, week_pnl)
        running_min = np.minimum(running_min, pnl)
        peak = np.maximum(peak, pnl)
        max_dd = np.maximum(max_dd, peak - pnl)
        weeks_under += pnl < 0
        fan.append(np.percentile(cfg.bankroll + pnl, PCTS))

    return {
        "config": dict(cfg.__dict__, weeks=n_weeks),
        "n_weeks": n_weeks,
        "p_oz_mean": float(p_oz.mean()),
        "p_gl_mean": float(p_gl.mean()),
        "gl_prior": ("kappa %.2f: " % cfg.gl_kappa if cfg.gl_kappa is not None else "") + "%.1f-%.1f" % (gl_w, gl_l),
        "p_gl_below_breakeven": float((p_gl < breakeven(GL_PRICE)).mean()),
        "p_oz_below_breakeven": float((p_oz < breakeven(OZ_PRICE)).mean()),
        "mean_turnover": float(turnover.mean()),
        "final": cfg.bankroll + pnl,
        "worst_week": worst_week,
        # Stakes are flat off the STARTING bankroll with no stop-loss, so a path
        # can go through zero and keep betting. Percentiles on such a path are
        # unreachable in reality -- report the rate rather than hiding it.
        "p_bust": float((cfg.bankroll + running_min <= 0).mean()),
        "n_bust": int((cfg.bankroll + running_min <= 0).sum()),
        "max_dd": max_dd,            # dollars, per path
        "weeks_under": weeks_under,  # per path
        "fan": np.array(fan),  # (weeks + 1, len(PCTS))
    }


# ------------------------------------------------------------------ figures ---
# Palette and axis treatment copied from models/over_zero/monitor/roi_report.py so
# the two sets of figures read as one system.
INK, MUTED, GRID = "#1a1d24", "#6b7280", "#d8dce3"
BLUE, GREEN, RED, GOLD = "#2b5d8a", "#3e7d5a", "#a9384a", "#b7822a"


def _style(ax):
    ax.set_facecolor("white")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5, length=3, color=GRID)
    ax.grid(alpha=0.5, color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def _short(label: str) -> str:
    """Scenario labels are written for the table; the dot plot needs them narrow."""
    lab = label.split(" -- ")[0]
    for a, b in (("Pooled prior", "pooled"), ("n=58 prior (published under list)", "n=58"),
                 ("n=58 prior", "n=58"), ("2024-25 window prior (72-50)", "2024-25 window"),
                 (", bet at the historical rate (~6/wk),", ", ~6/wk,"),
                 (", historical rate,", ", ~6/wk,"), (", historical rate", ", ~6/wk"),
                 (", bet EVERY flag (~49/wk),", ", all 49/wk,"),
                 (", bet EVERY flag,", ", all 49/wk,"), (", every flag at", ", all 49/wk at"),
                 (" units", ""), ("Over-zero only (Greenline stood down)", "over-zero only"),
                 ("Headline at rho=0.25", "headline, rho=0.25")):
        lab = lab.replace(a, b)
    return lab


def _fan(ax, res, label, b0):
    weeks = np.arange(WEEKS_REMAINING + 1) + 3  # week 3 is the last one played
    f = res["fan"]
    ax.fill_between(weeks, f[:, 0], f[:, 4], color=BLUE, alpha=0.14, lw=0,
                    label="5-95%")
    ax.fill_between(weeks, f[:, 1], f[:, 3], color=BLUE, alpha=0.28, lw=0,
                    label="25-75%")
    ax.plot(weeks, f[:, 2], color=BLUE, lw=2, label="median", zorder=3)
    ax.axhline(b0, color=RED, lw=1.1, ls="--", zorder=2, label="start")
    ax.set_title(label)
    ax.set_xlabel("week")
    ax.set_ylabel("bankroll ($)")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1000:.0f}k")
    _style(ax)


def make_figures(base: Config, scenarios: list[tuple[str, Config]], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 10.5,
                         "axes.titleweight": "bold", "axes.labelsize": 9,
                         "figure.facecolor": "white"})

    def variant(**kw):
        return Config(**dict(base.__dict__, **kw))

    cov = GL_COVERAGE_HISTORICAL
    pooled = simulate(variant(gl_coverage=cov, gl_unit=0.01, gl_prior="pooled", gl_kappa=None))
    thin = simulate(variant(gl_coverage=cov, gl_unit=0.01, gl_prior="n58", gl_kappa=None))
    b0 = base.bankroll

    fig = plt.figure(figsize=(15.5, 10.2))
    gs = GridSpec(2, 2, figure=fig, hspace=0.34, wspace=0.2,
                  left=0.07, right=0.97, top=0.88, bottom=0.08)

    # 1-2. the bracket, as two fan charts on a shared scale
    ax1, ax2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    _fan(ax1, pooled, "Pooled prior (146-113)", b0)
    _fan(ax2, thin, "Published under list only (32-26)", b0)
    lo = min(pooled["fan"][:, 0].min(), thin["fan"][:, 0].min())
    hi = max(pooled["fan"][:, 4].max(), thin["fan"][:, 4].max())
    for ax in (ax1, ax2):
        ax.set_ylim(lo - 500, hi + 500)
    ax1.legend(frameon=False, fontsize=8, labelcolor=MUTED, loc="upper left")

    # 3. terminal distributions, overlaid
    ax3 = fig.add_subplot(gs[1, 0])
    bins = np.linspace(min(pooled["final"].min(), thin["final"].min()),
                       max(np.percentile(pooled["final"], 99.5),
                           np.percentile(thin["final"], 99.5)), 70)
    for res, c, lab in ((thin, GOLD, "graded flags only"), (pooled, BLUE, "pooled")):
        ax3.hist(res["final"], bins=bins, color=c, alpha=0.45, lw=0,
                 label=f"{lab} (median ${np.median(res['final']):,.0f})")
    ax3.axvline(b0, color=RED, lw=1.2, ls="--", label="start $20,000")
    ax3.set_title("Ending bankroll, 100k paths")
    ax3.set_xlabel("ending bankroll ($)")
    ax3.set_ylabel("paths")
    ax3.xaxis.set_major_formatter(lambda v, _: f"${v / 1000:.0f}k")
    ax3.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    _style(ax3)

    # 4. every scenario, median with a 5-95 whisker
    ax4 = fig.add_subplot(gs[1, 1])
    rows = [(lab, simulate(cfg)) for lab, cfg in scenarios]
    ys = np.arange(len(rows))[::-1]
    for y, (lab, res) in zip(ys, rows):
        f = res["final"]
        p5, p50, p95 = np.percentile(f, [5, 50, 95])
        c = GREEN if p50 >= b0 else RED
        ax4.plot([p5, p95], [y, y], color=GRID, lw=3, solid_capstyle="round", zorder=2)
        ax4.plot([p50], [y], "o", color=c, ms=7, zorder=3)
    ax4.axvline(b0, color=RED, lw=1.1, ls="--", zorder=1)
    ax4.set_yticks(ys)
    ax4.set_yticklabels([_short(lab) for lab, _ in rows], fontsize=8)
    ax4.set_title("Every scenario: median, 5th-95th")
    ax4.set_xlabel("ending bankroll ($)")
    ax4.xaxis.set_major_formatter(lambda v, _: f"${v / 1000:.0f}k")
    _style(ax4)

    fig.text(0.07, 0.955, "$20,000 across over-zero OVERs and Greenline totals, "
             "weeks 4-15 of 2026", fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.07, 0.915,
             "Win rates drawn per path from each leg's Beta posterior. The two fan "
             "charts are the same bet at the two defensible Greenline priors -- the "
             "spread between them is unresolved evidence, not risk.",
             fontsize=9, color=MUTED, va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"wrote {path}")


def report(res: dict, label: str) -> str:
    f = res["final"]
    b0 = res["config"]["bankroll"]
    qs = np.percentile(f, [1, 5, 10, 25, 50, 75, 90, 95, 99])
    return "\n".join([
        f"### {label}",
        "",
        f"- drawn win rates: over-zero mean {res['p_oz_mean']:.1%} "
        f"(P below break-even {res['p_oz_below_breakeven']:.0%}), "
        f"Greenline mean {res['p_gl_mean']:.1%} from a {res['gl_prior']} prior "
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
        f"- **paths that pass through $0 mid-season: {res['p_bust']:.1%}** "
        f"(flat stakes off the starting bankroll, no stop-loss -- every "
        f"percentile above assumes betting continues past zero)",
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

    # the n=58 posterior must keep real mass below break-even, or the sim has
    # smuggled in an edge that two graded weeks do not establish
    thin = simulate(Config(paths=5_000, seed=2, gl_prior="n58", gl_kappa=None))
    assert 0.25 < thin["p_gl_below_breakeven"] < 0.50, thin["p_gl_below_breakeven"]

    # pooling the 201 personal unders must actually tighten it, not just relabel
    fat = simulate(Config(paths=5_000, seed=2, gl_prior="pooled", gl_kappa=None))
    assert fat["p_gl_below_breakeven"] < 0.20, fat["p_gl_below_breakeven"]

    # slate volume must carry ~15% more flags than 49/wk and be week-shaped
    assert len(GL_FLAGS_BY_WEEK) == WEEKS_REMAINING
    assert 1.1 < sum(GL_FLAGS_BY_WEEK) / (GL_FLAGS_PER_WEEK * WEEKS_REMAINING) < 1.2
    sl = simulate(Config(paths=5_000, seed=5, gl_volume="slate"))
    ct = simulate(Config(paths=5_000, seed=5, gl_volume="constant"))
    assert sl["mean_turnover"] > ct["mean_turnover"] * 1.1
    # range volume: mean 9 a week capped by the slate, so ~9*11 + 9 bets; the
    # stake is re-sized weekly so turnover is not exactly linear -- check bounds
    rg = simulate(Config(paths=5_000, seed=5, gl_volume="range", resize_weekly=False))
    per_bet = Config().bankroll * Config().gl_unit
    oz_share = 11 * Config().bankroll * Config().oz_unit
    gl_bets = (rg["mean_turnover"] - oz_share) / per_bet
    assert 100 < gl_bets < 116, gl_bets
    # coverage must scale volume, not the win rate
    lo = simulate(Config(paths=5_000, seed=3, gl_volume="slate", gl_coverage=GL_COVERAGE_HISTORICAL))
    hi = simulate(Config(paths=5_000, seed=3, gl_volume="slate", gl_coverage=1.0))
    assert lo["mean_turnover"] < hi["mean_turnover"] / 3
    assert abs(lo["p_gl_mean"] - hi["p_gl_mean"]) < 0.005
    # the fan must start at the starting bankroll and carry one row per week
    f = fat["fan"]
    assert f.shape == (WEEKS_REMAINING + 1, len(PCTS)), f.shape
    # two seasons: 12 + 15 weeks, more turnover, over-zero front-loaded in season 2
    two = simulate(Config(paths=5_000, seed=8, seasons=2))
    assert two["fan"].shape == (WEEKS_REMAINING + 15 + 1, len(PCTS))
    assert two["mean_turnover"] > fat["mean_turnover"] * 1.8
    # planning prior default is kappa 0.5
    assert Config().gl_kappa == 0.5 and abs(planning_p_gl(0.5) - 0.5614) < 0.002
    assert 0.010 < kelly_unit(planning_p_gl(0.5), -110) < 0.014
    assert np.allclose(f[0], Config().bankroll), f[0]
    assert (np.diff(f, axis=1) >= 0).all(), "percentiles must be non-decreasing"
    # weekly resizing must lift the upper tail, and at a unit where one week's
    # slate cannot exceed the bankroll (0.25% x ~49 flags = 12%) it cannot bust.
    # Within a week stakes are still flat, so a 2% unit CAN bust on one Saturday.
    flat = simulate(Config(paths=5_000, seed=4, gl_unit=0.0025, resize_weekly=False))
    grow = simulate(Config(paths=5_000, seed=4, gl_unit=0.0025, resize_weekly=True))
    assert grow["p_bust"] == 0.0, grow["p_bust"]
    assert grow["final"].min() > 0
    assert np.percentile(grow["final"], 95) > np.percentile(flat["final"], 95)
    # stress knobs: kappa endpoints must reproduce the named priors; a marginal
    # penalty must lower the median; extra haircut sd must widen over-zero p
    k0 = simulate(Config(paths=5_000, seed=6, gl_kappa=0.0))
    k1 = simulate(Config(paths=5_000, seed=6, gl_kappa=1.0))
    assert abs(k0["p_gl_mean"] - 0.55) < 0.01 and abs(k1["p_gl_mean"] - 0.564) < 0.01
    base = simulate(Config(paths=5_000, seed=7))
    pen = simulate(Config(paths=5_000, seed=7, gl_marginal_penalty=0.03))
    assert np.median(pen["final"]) < np.median(base["final"])
    wide = simulate(Config(paths=5_000, seed=7, oz_extra_sd=0.03))
    assert wide["p_oz_below_breakeven"] > base["p_oz_below_breakeven"]
    assert base["max_dd"].min() >= 0 and base["weeks_under"].max() <= base["n_weeks"]
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
    ap.add_argument("--gl-kappa", type=float, default=0.5,
                    help="planning prior weight on the 2023-25 unders (0=n58, 1=pooled); default 0.5")
    ap.add_argument("--seasons", type=int, default=1,
                    help="1 = rest of 2026; 2 adds a full 2027-style season, and so on")
    ap.add_argument("--gl-prior", choices=sorted(GL_PRIORS), default=None,
                    help="which Greenline record to draw the win rate from")
    ap.add_argument("--gl-volume", choices=("range", "slate", "constant"), default="range",
                    help="range: GL_BETS_RANGE unders a week (default); slate: coverage x "
                         "FBS-vs-FBS schedule; constant: coverage x 49")
    ap.add_argument("--gl-range", type=int, nargs=2, default=list(GL_BETS_RANGE),
                    metavar=("LO", "HI"), help="unders per week for --gl-volume range")
    ap.add_argument("--flat-stakes", action="store_true",
                    help="flat units off the starting bankroll instead of weekly re-sizing")
    ap.add_argument("--gl-coverage", type=float, default=1.0,
                    help="fraction of the weekly Greenline flags actually bet")
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--json", help="write the scenario table here")
    ap.add_argument("--figs", help="write the four-panel figure here (.png)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    base = Config(bankroll=args.bankroll, paths=args.paths, rho=args.rho,
                  oz_unit=args.oz_unit, gl_unit=args.gl_unit,
                  oz_haircut=not args.no_haircut,
                  gl_prior=args.gl_prior or "pooled",
                  gl_kappa=None if args.gl_prior else args.gl_kappa, seasons=args.seasons,
                  gl_coverage=args.gl_coverage, resize_weekly=not args.flat_stakes,
                  gl_volume=args.gl_volume, gl_range=tuple(args.gl_range), seed=args.seed)

    def variant(**kw):
        return Config(**dict(base.__dict__, **kw))

    cov = GL_COVERAGE_HISTORICAL
    scenarios = [
        ("Pooled prior, bet at the historical rate (~6/wk), 1% units -- headline",
         variant(gl_coverage=cov, gl_unit=0.01)),
        ("Pooled prior, historical rate, 2% units",
         variant(gl_coverage=cov, gl_unit=0.02)),
        ("Pooled prior, bet EVERY flag (~49/wk), 0.25% units",
         variant(gl_coverage=1.0, gl_unit=0.0025)),
        ("Pooled prior, bet EVERY flag, 1% units",
         variant(gl_coverage=1.0, gl_unit=0.01)),
        ("n=58 prior (published under list), every flag at 0.25% -- the previous headline",
         variant(gl_prior="n58", gl_coverage=1.0, gl_unit=0.0025)),
        ("n=58 prior, historical rate at 1%",
         variant(gl_prior="n58", gl_coverage=cov, gl_unit=0.01)),
        ("2024-25 window prior (72-50), historical rate at 1% -- sensitivity",
         variant(gl_prior="pff-window", gl_coverage=cov, gl_unit=0.01)),
        ("Over-zero only (Greenline stood down)", variant(gl_unit=0.0)),
        ("Headline at rho=0.25 -- correlation sensitivity",
         variant(gl_coverage=cov, gl_unit=0.01, rho=0.25)),
    ]

    if args.figs:
        make_figures(base, scenarios, Path(args.figs))

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
            "p_bust": res["p_bust"],
        }
    print("\n".join(out))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(blob, fh, indent=2)


if __name__ == "__main__":
    main()
