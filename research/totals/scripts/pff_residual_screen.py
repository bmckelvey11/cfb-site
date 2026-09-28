"""Do entering PFF offense and defense grades still move the totals residual?

Screen, not a bet. The fit is regular-season games in 2019-2025. 2026 is drawn
on the same axes and is not in the slope. Association only: a grade can line up
with the residual because the market ignored it, or because both track something
else. This script does not separate those.

Residual. y is home points plus away points, overtime included.
r_open = y - median_total_open. r_close = y - median_total_close.
Both lines are core.v_game_book_median (book median, consensus only when no book
posted that number).

Feature. For each team, the snap-weighted mean of weekly PFF grades in weeks
strictly before the game. Week 0 is the season-aggregate grain and is excluded.
A team with no earlier week this season gets the previous season's snap-weighted
mean. The game feature is home plus away. Grades are averaged, never summed
across weeks except through the snap weights.

The seven grades were named before the fit. Nothing is added after seeing a slope.

Uncertainty. Seasons are the cluster, and there are fewer than ten of them, so
the 95% interval is a wild cluster bootstrap (Rademacher weights on season
residuals, 9999 draws), not an iid or analytic cluster SE. The leave-one-season
range is the min and max slope with each season held out. A interval that covers
0 is not evidence of no relationship. The practical size used for that reading
is 0.1 points of total per grade point of the home+away sum, which is 1 point
of total per 10 grade points.

Significance. H0 is a slope of 0. The p-value is a wild cluster bootstrap-t
(Cameron, Gelbach, Miller), null imposed, Webb six-point weights because there
are fewer than ten seasons. With five seasons the 7,776 weight patterns are
enumerated exactly. With seven seasons the test uses 9,999 Monte Carlo draws.
p_holm is Holm across the fourteen tests. A large p-value is not evidence of
no association, and five seasons cannot resolve a small tail.

Run from the repo root:
    python research/totals/scripts/pff_residual_screen.py
    python research/totals/scripts/pff_residual_screen.py --self-check
"""

from __future__ import annotations

import argparse
import itertools
import sys
from bisect import bisect_left
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from cfb_paths import DB_PATH  # noqa: E402

# (feature, grade column, snap weight, table). Named before any fit.
STATS = [
    (
        "grades_offense",
        "grades_offense",
        "snap_counts_total",
        "stg.pff_offense_summary",
    ),
    ("grades_pass", "grades_pass", "snap_counts_pass", "stg.pff_offense_summary"),
    ("grades_run", "grades_run", "snap_counts_run", "stg.pff_offense_summary"),
    (
        "grades_defense",
        "grades_defense",
        "snap_counts_defense",
        "stg.pff_defense_summary",
    ),
    (
        "grades_coverage_defense",
        "grades_coverage_defense",
        "snap_counts_coverage",
        "stg.pff_defense_summary",
    ),
    (
        "grades_pass_rush_defense",
        "grades_pass_rush_defense",
        "snap_counts_pass_rush",
        "stg.pff_defense_summary",
    ),
    (
        "grades_run_defense",
        "grades_run_defense",
        "snap_counts_run_defense",
        "stg.pff_defense_summary",
    ),
]

FIT_MAX_SEASON = 2025
HOLDOUT_SEASON = 2026
PRACTICAL_SLOPE = 0.1  # 1 total point per 10 grade points on the home+away sum
BOOT_DRAWS = 9999
BOOT_SEED = 20260922

OUT_PNG = ROOT / "data" / "exports" / "pff_residual_screen.png"
OUT_CSV = ROOT / "data" / "exports" / "pff_residual_screen.csv"

IDENTIFICATION = "association of the pre-game PFF grade with the market residual, clustered by season"


def _mass_sql(table: str, cols: list[tuple[str, str, str]]) -> str:
    pieces = []
    for name, grade, snap in cols:
        ok = (
            f"{grade} is not null and not isnan({grade}) "
            f"and {snap} is not null and {snap} > 0"
        )
        pieces.append(
            f"sum(case when {ok} then {grade} * {snap} else 0 end) as {name}_g"
        )
        pieces.append(f"sum(case when {ok} then {snap} else 0 end) as {name}_w")
    body = ", ".join(pieces)
    return f"""
        select f.cfbd_team_id, p.season, p.week, {body}
        from {table} p
        join stg.pff_franchise f using (franchise_id)
        where p.week > 0 and f.cfbd_team_id is not null
        group by 1, 2, 3
    """


def load_team_weeks(
    con,
) -> dict[str, dict[tuple[int, int], tuple[list[int], list[float]]]]:
    """Snap-weighted grade through each week, keyed by stat then (team, season)."""
    by_table: dict[str, list[tuple[str, str, str]]] = {}
    for name, grade, snap, table in STATS:
        by_table.setdefault(table, []).append((name, grade, snap))

    frames = [
        con.execute(_mass_sql(table, cols)).fetchdf()
        for table, cols in by_table.items()
    ]
    mass = frames[0]
    for frame in frames[1:]:
        mass = mass.merge(frame, on=["cfbd_team_id", "season", "week"], how="outer")
    mass = mass.fillna(0.0)

    out: dict[str, dict[tuple[int, int], tuple[list[int], list[float]]]] = {}
    for name, _, _, _ in STATS:
        gcol, wcol = f"{name}_g", f"{name}_w"
        part = mass[["cfbd_team_id", "season", "week", gcol, wcol]].copy()
        part = part.sort_values(["cfbd_team_id", "season", "week"])
        part["cg"] = part.groupby(["cfbd_team_id", "season"], sort=False)[gcol].cumsum()
        part["cw"] = part.groupby(["cfbd_team_id", "season"], sort=False)[wcol].cumsum()
        part = part[part["cw"] > 0]
        lookup: dict[tuple[int, int], tuple[list[int], list[float]]] = {}
        for (tid, season), grp in part.groupby(["cfbd_team_id", "season"], sort=False):
            lookup[(int(tid), int(season))] = (
                grp["week"].astype(int).tolist(),
                (grp["cg"] / grp["cw"]).tolist(),
            )
        out[name] = lookup
    return out


def entering(
    lookup: dict[tuple[int, int], tuple[list[int], list[float]]],
    team: int,
    season: int,
    week: int,
):
    """Grade known before this week. Previous season if this season has no earlier week."""
    row = lookup.get((team, season))
    if row is not None:
        weeks, values = row
        i = bisect_left(weeks, week) - 1
        if i >= 0:
            return values[i]
    prev = lookup.get((team, season - 1))
    if prev is not None and prev[1]:
        return prev[1][-1]
    return None


def load_games(con) -> pd.DataFrame:
    return con.execute(
        """
        select game_id, season, week, home_team_id, away_team_id,
               home_points + away_points as y,
               median_total_open, median_total_close
        from core.v_game_book_median
        where season_type = 'regular'
          and home_points is not null
          and away_points is not null
          and season between 2019 and 2026
        """
    ).fetchdf()


def attach(games: pd.DataFrame, lookups: dict) -> pd.DataFrame:
    df = games.copy()
    for name, _, _, _ in STATS:
        lookup = lookups[name]
        home, away = [], []
        for season, week, hid, aid in zip(
            df["season"], df["week"], df["home_team_id"], df["away_team_id"]
        ):
            h = entering(lookup, int(hid), int(season), int(week))
            a = entering(lookup, int(aid), int(season), int(week))
            home.append(h)
            away.append(a)
        hser = pd.Series(home, index=df.index, dtype="float64")
        aser = pd.Series(away, index=df.index, dtype="float64")
        df[name] = hser + aser
        df[f"{name}_ok"] = hser.notna() & aser.notna()
    return df


def ols_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    x_c = x - x.mean()
    y_c = y - y.mean()
    var = float(np.dot(x_c, x_c))
    if var == 0.0:
        return float("nan"), float("nan")
    b = float(np.dot(x_c, y_c) / var)
    a = float(y.mean() - b * x.mean())
    return a, b


def wild_ci(
    x: np.ndarray, y: np.ndarray, seasons: np.ndarray, seed: int
) -> tuple[float, float]:
    a, b = ols_slope(x, y)
    fitted = a + b * x
    resid = y - fitted
    uniq = np.unique(seasons)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(BOOT_DRAWS, len(uniq)))
    sign_of = {s: i for i, s in enumerate(uniq)}
    idx = np.array([sign_of[s] for s in seasons])
    boots = np.empty(BOOT_DRAWS)
    for i in range(BOOT_DRAWS):
        y_star = fitted + signs[i, idx] * resid
        boots[i] = ols_slope(x, y_star)[1]
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return float(lo), float(hi)


# Webb (2014) six-point weights: mean 0, second moment 1. Rademacher's 2^G
# patterns are too coarse to resolve a tail when G is under 10.
_WEBB_WEIGHTS = np.array(
    [-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)]
)


def _cluster_ols(x: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """Intercept-plus-slope OLS with a CR1 cluster-robust SE on the slope."""
    n = len(y)
    X = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ (X.T @ y)
    resid = y - X @ beta
    uniq = np.unique(groups)
    g_count = len(uniq)
    meat = np.zeros((2, 2))
    for g in uniq:
        m = groups == g
        score = X[m].T @ resid[m]
        meat += np.outer(score, score)
    scale = (g_count / (g_count - 1)) * ((n - 1) / (n - 2))
    var = scale * (xtx_inv @ meat @ xtx_inv)
    se = float(np.sqrt(var[1, 1]))
    return float(beta[1]), se


def wild_p(
    x: np.ndarray, y: np.ndarray, seasons: np.ndarray, seed: int
) -> tuple[float, int, str]:
    """Bootstrap-t p-value for slope = 0. Returns p, draw count, weight name."""
    uniq = np.unique(seasons)
    g_count = len(uniq)
    weights = _WEBB_WEIGHTS if g_count < 10 else np.array([-1.0, 1.0])
    beta, se = _cluster_ols(x, y, seasons)
    t_obs = beta / se
    # Restricted fit imposes slope 0, so the null residual is the demeaned outcome.
    fitted_r = np.full(len(y), y.mean())
    resid_r = y - fitted_r
    sign_of = {s: i for i, s in enumerate(uniq)}
    idx = np.array([sign_of[s] for s in seasons])

    def t_for(w_by_cluster: np.ndarray) -> float:
        y_star = fitted_r + resid_r * w_by_cluster[idx]
        b_star, se_star = _cluster_ols(x, y_star, seasons)
        return b_star / se_star

    n_patterns = len(weights) ** g_count
    if n_patterns <= 65536:
        t_boot = np.array(
            [t_for(np.array(combo)) for combo in itertools.product(weights, repeat=g_count)]
        )
        n_used = len(t_boot)
    else:
        rng = np.random.default_rng(seed)
        t_boot = np.empty(BOOT_DRAWS)
        for i in range(BOOT_DRAWS):
            t_boot[i] = t_for(rng.choice(weights, size=g_count))
        n_used = BOOT_DRAWS
    p_value = float(np.mean(np.abs(t_boot) >= abs(t_obs)))
    kind = "webb" if len(weights) == 6 else "rademacher"
    return p_value, n_used, kind


def holm(p_values: np.ndarray) -> np.ndarray:
    """Holm adjusted p-values, same order as the input."""
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def leave_one_season(
    x: np.ndarray, y: np.ndarray, seasons: np.ndarray
) -> tuple[float, float]:
    slopes = []
    for season in np.unique(seasons):
        keep = seasons != season
        if keep.sum() < 2:
            continue
        slopes.append(ols_slope(x[keep], y[keep])[1])
    return float(np.min(slopes)), float(np.max(slopes))


def screen(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fit = df[df["season"] <= FIT_MAX_SEASON]
    for i, (name, _, _, _) in enumerate(STATS):
        usable = fit[fit[f"{name}_ok"]]
        for residual, line in (
            ("open", "median_total_open"),
            ("close", "median_total_close"),
        ):
            sub = usable[usable[line].notna()]
            x = sub[name].to_numpy(dtype=float)
            y = (sub["y"] - sub[line]).to_numpy(dtype=float)
            seasons = sub["season"].to_numpy()
            _, b = ols_slope(x, y)
            los_min, los_max = leave_one_season(x, y, seasons)
            ci_lo, ci_hi = wild_ci(
                x, y, seasons, BOOT_SEED + i * 2 + (residual == "close")
            )
            p_wild, n_draws, weight = wild_p(
                x, y, seasons, BOOT_SEED + 100 + i * 2 + (residual == "close")
            )
            rows.append(
                {
                    "stat": name,
                    "residual": residual,
                    "n": int(len(sub)),
                    "n_seasons": int(pd.Series(seasons).nunique()),
                    "slope": b,
                    "leave_one_season_min": los_min,
                    "leave_one_season_max": los_max,
                    "ci_low": ci_lo,
                    "ci_high": ci_hi,
                    "covers_0": bool(ci_lo <= 0.0 <= ci_hi),
                    "covers_one_point_per_10": bool(ci_lo <= PRACTICAL_SLOPE <= ci_hi),
                    "p_wild": p_wild,
                    "p_draws": n_draws,
                    "weight": weight,
                }
            )
    table = pd.DataFrame(rows)
    table["p_holm"] = holm(table["p_wild"].to_numpy(dtype=float))
    return table


def plot(df: pd.DataFrame, table: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(len(STATS), 2, figsize=(10, 18), sharey=True)
    for row, (name, _, _, _) in enumerate(STATS):
        for col, (residual, line) in enumerate(
            (("open", "median_total_open"), ("close", "median_total_close"))
        ):
            ax = axes[row, col]
            usable = df[df[f"{name}_ok"] & df[line].notna()]
            fit = usable[usable["season"] <= FIT_MAX_SEASON]
            hold = usable[usable["season"] == HOLDOUT_SEASON]
            x = fit[name].to_numpy(dtype=float)
            y = (fit["y"] - fit[line]).to_numpy(dtype=float)
            ax.scatter(
                x, y, s=6, alpha=0.25, c="#4c78a8", linewidths=0, label="2019-2025"
            )
            if len(hold):
                ax.scatter(
                    hold[name],
                    hold["y"] - hold[line],
                    s=10,
                    alpha=0.7,
                    c="#e45756",
                    linewidths=0,
                    label="2026, not in fit",
                )
            a, b = ols_slope(x, y)
            xs = np.linspace(np.nanmin(x), np.nanmax(x), 40)
            ax.plot(xs, a + b * xs, color="#222222", lw=1.2)
            rec = table[(table["stat"] == name) & (table["residual"] == residual)].iloc[
                0
            ]
            ax.set_title(
                f"{name}  {residual}\nslope {rec.slope:.3f}  "
                f"95% [{rec.ci_low:.3f}, {rec.ci_high:.3f}]",
                fontsize=8,
            )
            if row == len(STATS) - 1:
                ax.set_xlabel("home + away entering grade")
            if col == 0:
                ax.set_ylabel("residual (points)")
            if row == 0 and col == 1:
                ax.legend(fontsize=7, frameon=False)
    fig.suptitle("Totals residual vs entering PFF grade", fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def report(games: pd.DataFrame, df: pd.DataFrame, table: pd.DataFrame) -> str:
    scored = games
    lines = [
        IDENTIFICATION,
        f"scored regular-season games 2019-2026: {len(scored)}",
        f"missing median_total_open: {int(scored['median_total_open'].isna().sum())}",
        f"missing median_total_close: {int(scored['median_total_close'].isna().sum())}",
    ]
    fit = df[df["season"] <= FIT_MAX_SEASON]
    both = fit[fit["grades_offense_ok"]]
    lines.append(
        f"2019-2025 scored games: {len(fit)}; both teams have an entering grade: {len(both)}. "
        "The games without a grade are outside the PFF franchise map."
    )
    for residual, line in (
        ("open", "median_total_open"),
        ("close", "median_total_close"),
    ):
        sub = both[both[line].notna()]
        seasons = sorted(int(s) for s in sub["season"].unique())
        lines.append(f"{residual} fit seasons ({len(sub)} games): {seasons}")
    hold = df[(df["season"] == HOLDOUT_SEASON) & df["grades_offense_ok"]]
    lines.append(
        f"2026 games with both grades, plotted and excluded from the fit: {len(hold)}"
    )
    lines.append(
        "A 95% interval that covers 0 is not evidence of no association. "
        "covers_one_point_per_10 means the interval also covers 0.1 "
        "(1 total point per 10 grade points on the home+away sum); "
        "if it does, the screen cannot see an effect of that size. "
        "p_wild tests slope = 0 with a Webb wild cluster bootstrap-t. "
        "p_holm is Holm across the 14 tests. A large p-value is not evidence of no association."
    )
    lines.append(table.to_string(index=False))
    return "\n".join(lines)


def self_check() -> None:
    lookup = {
        (1, 2024): ([1, 3], [50.0, 60.0]),
        (1, 2025): ([2], [70.0]),
    }
    assert entering(lookup, 1, 2025, 2) == 60.0  # no 2025 week before 2; prior season
    assert entering(lookup, 1, 2025, 3) == 70.0  # 2025 week 2 is before week 3
    assert entering(lookup, 1, 2025, 1) == 60.0
    assert entering(lookup, 9, 2025, 4) is None

    rng = np.random.default_rng(0)
    seasons = np.repeat(np.arange(2019, 2026), 80)
    x = rng.normal(size=len(seasons))
    y = 0.2 * x + rng.normal(scale=0.5, size=len(seasons))
    _, b = ols_slope(x, y)
    lo, hi = wild_ci(x, y, seasons, seed=1)
    assert lo < b < hi
    los_min, los_max = leave_one_season(x, y, seasons)
    assert los_min < b < los_max
    p_signal, _, _ = wild_p(x, y, seasons, seed=2)
    y_null = rng.normal(scale=0.5, size=len(seasons))
    p_null, _, _ = wild_p(x, y_null, seasons, seed=3)
    assert p_signal < 0.05
    assert p_null > 0.05
    adjusted = holm(np.array([0.01, 0.04, 0.20]))
    assert adjusted[0] == 0.03
    assert abs(adjusted[1] - 0.08) < 1e-12
    assert adjusted[2] == 0.20
    print("self-check ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return

    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        lookups = load_team_weeks(con)
        games = load_games(con)
    finally:
        con.close()
    df = attach(games, lookups)
    table = screen(df)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    plot(df, table, OUT_PNG)
    print(report(games, df, table))
    print(f"wrote {OUT_PNG}")
    print(f"wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
