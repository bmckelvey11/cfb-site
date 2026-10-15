"""Which team-level PFF stats, if any, separate winning Greenline unders from losing ones?

    python research/totals/scripts/pff_under_screen.py
    python research/totals/scripts/pff_under_screen.py --csv data/exports/pff_under_screen.csv

An exploratory screen, not the registered test. `pff_under_filters.py` holds the registered
five-feature family (2026 only, 2025 full-season profiles, median splits) and stays closed
at five. This script asks the wider question on a wider sample, and is built so that its
own search cannot fool it:

  * **Sample.** Every graded Greenline under in all three eras (`under_filters.greenline_unders`):
    2020 PFF_hist, 2022-23 exports, 2026 flags. `stg.pff_*` now reaches back to 2014, so
    the archive eras can join PFF -- `pff_under_filters.py` predates that load.
  * **Outcome.** Cover margin = capture line - actual total, in points (positive = the under
    won by that much). A continuous outcome has far more power than win/loss; the win/loss
    split is reported beside it as the betting read.
  * **Features.** Nineteen team stats, declared in FEATURES below before any result was seen.
    Each game's value is the mean of the two teams (two offenses or two defenses).
  * **No lookahead.** A team's profile pools the prior season's regular season (weeks 0-14)
    with the current season strictly before the game's CFBD week (capped at 14). The prior
    season is the shrinkage: in week 2 the profile is almost all last year, by week 10
    mostly this year. PFF and CFBD week numbers are checked to agree (`week_alignment`).
  * **Discovery / holdout.** The screen runs on the archive eras (2020 + 2022-23, n=179).
    Benjamini-Hochberg q and Holm p are computed across all nineteen. Only a feature with
    discovery q < 0.10 is a candidate, and a candidate is then scored once on the 2026 flags
    (n=230), which the screen never saw. Caveat: five related features (pass rush, pass
    rate, deep rate, QB grade, coverage) were tested on 2026 weeks 2-4 in the registered
    run, so 2026 is untouched by this screen but not by every look.
  * **Errors.** OLS with era fixed effects, standard errors clustered by slate date (games
    on one day share weather, news and market moves). p-values use a t with G-1 df.

Trial count for this screen: 19 features x 1 outcome specification = 19 trials.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

from cfb_paths import DB_PATH  # noqa: E402
from under_filters import greenline_unders  # noqa: E402

LAST_REGULAR_WEEK = 14
DISCOVERY = ("2020 PFF_hist", "2022-23 exports")
HOLDOUT = "2026 flags"
Q_CANDIDATE = 0.10
MIN_DROPBACKS = 60  # about two games of pass volume across the pooled window

# name, unit (off/def), numerator column, denominator column, under-side direction, description
# Each is a ratio of window sums from TEAM_WEEK_SQL. Direction is the prior: which way
# should the value point for an under? It is recorded, not tested one-sided.
FEATURES = [
    ("off_pass_grade", "off", "pass_grade_w", "dropbacks", "low", "QB passing grade, dropback-weighted"),
    ("off_ypa", "off", "pass_yards", "attempts", "low", "yards per pass attempt"),
    ("off_adot", "off", "adot_w", "attempts", "low", "average depth of target"),
    ("off_btt_rate", "off", "btt", "dropbacks", "low", "big-time throws per dropback"),
    ("off_twp_rate", "off", "twp", "dropbacks", "high", "turnover-worthy plays per dropback"),
    ("off_sack_rate", "off", "sacks", "dropbacks", "high", "sacks per dropback"),
    ("off_pass_rate", "off", "dropbacks", "plays", "low", "dropbacks / (dropbacks + designed runs)"),
    ("off_plays_pg", "off", "plays", "games", "low", "offensive plays per game (tempo)"),
    ("off_run_grade", "off", "run_grade_w", "rush_att", "low", "ball-carrier run grade, carry-weighted"),
    ("off_explosive_run", "off", "explosive", "rush_att", "low", "explosive runs per carry"),
    ("off_yco", "off", "yco", "rush_att", "low", "yards after contact per carry"),
    ("off_pass_block", "off", "pblk_grade_w", "pblk_snaps", "low", "pass-block grade, snap-weighted"),
    ("off_run_block", "off", "rblk_grade_w", "rblk_snaps", "low", "run-block grade, snap-weighted"),
    ("def_pressure_rate", "def", "pressures", "rush_opp", "high", "pressures per pass-rush opportunity"),
    ("def_pass_rush_grade", "def", "prush_grade_w", "prush_snaps", "high", "pass-rush grade, snap-weighted"),
    ("def_coverage_grade", "def", "cov_grade_w", "cov_snaps", "high", "coverage grade, snap-weighted"),
    ("def_run_def_grade", "def", "rdef_grade_w", "rdef_snaps", "high", "run-defense grade, snap-weighted"),
    ("def_stop_rate", "def", "stops", "run_stop_opp", "high", "run stops per run-stop opportunity"),
    ("def_missed_tackle_rate", "def", "missed", "tackle_att", "low", "missed tackles / (tackles + missed)"),
]

# NaN, not NULL, is how an absent PFF numeric arrives (docs/pff-scheme-inventory-2026-09-16.md).
def _f(c: str) -> str:
    return f"case when {c} is null or isnan({c}) then 0 else {c} end"


def _w(grade: str, weight: str) -> tuple[str, str]:
    """Grade x weight, and the weight that actually carried a grade."""
    return (f"sum({_f(grade)} * {_f(weight)})",
            f"sum(case when {grade} is null or isnan({grade}) then 0 else {_f(weight)} end)")


_pg, _pgw = _w("grades_pass", "dropbacks")
_rg, _rgw = _w("grades_run", "attempts")
_pb, _pbw = _w("grades_pass_block", "snap_counts_pass_block")
_rb, _rbw = _w("grades_run_block", "snap_counts_run_block")
_pr, _prw = _w("grades_pass_rush_defense", "snap_counts_pass_rush")
_cv, _cvw = _w("grades_coverage_defense", "snap_counts_coverage")
_rd, _rdw = _w("grades_run_defense", "snap_counts_run_defense")

# One row per franchise x season x week, every column a plain sum so windows can be added.
TEAM_WEEK_SQL = f"""
with pass as (
    select season, week, franchise_id,
           {_pg} as pass_grade_w, {_pgw} as dropbacks,
           sum({_f('attempts')}) as attempts, sum({_f('yards')}) as pass_yards,
           sum({_f('avg_depth_of_target')} * {_f('attempts')}) as adot_w,
           sum({_f('big_time_throws')}) as btt, sum({_f('turnover_worthy_plays')}) as twp,
           sum({_f('sacks')}) as sacks, sum({_f('scrambles')}) as scrambles
    from stg.pff_passing where split = 'all' and season in (select unnest(?)) group by all
), rush as (
    select season, week, franchise_id,
           {_rg} as run_grade_w, {_rgw} as rush_att_graded,
           sum({_f('attempts')}) as rush_att, sum({_f('explosive')}) as explosive,
           sum({_f('yards_after_contact')}) as yco
    from stg.pff_rushing where season in (select unnest(?)) group by all
), blk as (
    select season, week, franchise_id,
           {_pb} as pblk_grade_w, {_pbw} as pblk_snaps, {_rb} as rblk_grade_w, {_rbw} as rblk_snaps
    from stg.pff_offense_summary where season in (select unnest(?)) group by all
), dsum as (
    select season, week, franchise_id,
           {_pr} as prush_grade_w, {_prw} as prush_snaps, {_cv} as cov_grade_w, {_cvw} as cov_snaps,
           {_rd} as rdef_grade_w, {_rdw} as rdef_snaps,
           sum({_f('missed_tackles')}) as missed,
           sum({_f('tackles')}) + sum({_f('missed_tackles')}) as tackle_att
    from stg.pff_defense_summary where season in (select unnest(?)) group by all
), prush as (
    select season, week, franchise_id,
           sum({_f('total_pressures')}) as pressures, sum({_f('pass_rush_opp')}) as rush_opp
    from stg.pff_defense_pass_rush where split = 'all' and season in (select unnest(?)) group by all
), drun as (
    select season, week, franchise_id,
           sum({_f('stops')}) as stops, sum({_f('run_stop_opp')}) as run_stop_opp
    from stg.pff_defense_run where season in (select unnest(?)) group by all
)
select f.cfbd_team_id, p.*, r.* exclude (season, week, franchise_id),
       b.* exclude (season, week, franchise_id), d.* exclude (season, week, franchise_id),
       pr.* exclude (season, week, franchise_id), dr.* exclude (season, week, franchise_id)
from pass p
left join rush r using (season, week, franchise_id)
left join blk b using (season, week, franchise_id)
left join dsum d using (season, week, franchise_id)
left join prush pr using (season, week, franchise_id)
left join drun dr using (season, week, franchise_id)
join stg.pff_franchise f using (franchise_id)
where f.cfbd_team_id is not null and p.week <= {LAST_REGULAR_WEEK}
"""


def team_weeks(con, seasons: list[int]) -> pd.DataFrame:
    tw = con.execute(TEAM_WEEK_SQL, [seasons] * 6).df()
    tw = tw.fillna(0.0)
    tw["games"] = (tw["dropbacks"] > 0).astype(float)
    # Designed runs: carries minus QB scrambles, which PFF books as rushing attempts.
    tw["plays"] = tw["dropbacks"] + (tw["rush_att"] - tw["scrambles"]).clip(lower=0)
    return tw


def profile(tw: pd.DataFrame, team: int, season: int, week: int) -> dict | None:
    """One team's feature values for a game in (season, CFBD week): last season's regular
    season plus this season strictly before `week`. None below the volume floor."""
    t = tw[tw["cfbd_team_id"] == team]
    win = t[((t["season"] == season - 1) & (t["week"] <= LAST_REGULAR_WEEK))
            | ((t["season"] == season) & (t["week"] < min(week, LAST_REGULAR_WEEK + 1)))]
    s = win.drop(columns=["cfbd_team_id", "season", "week", "franchise_id"]).sum()
    if s["dropbacks"] < MIN_DROPBACKS:
        return None
    out = {}
    for name, _, num, den, _, _ in FEATURES:
        out[name] = s[num] / s[den] if s[den] > 0 else np.nan
    return out


def week_alignment(con, tw: pd.DataFrame, seasons: list[int]) -> float:
    """Share of team-weeks where PFF shows a game and CFBD has one in the same week number.

    If PFF ran one week ahead of CFBD the strict `< week` window would still exclude the
    game itself; if it ran one week behind, it would include it. So this must be ~1."""
    cf = con.execute(
        "select season, week, home_team_id as t from core.fact_game where season in (select unnest(?)) "
        f"and week <= {LAST_REGULAR_WEEK} and season_type = 'regular' union all "
        "select season, week, away_team_id from core.fact_game where season in (select unnest(?)) "
        f"and week <= {LAST_REGULAR_WEEK} and season_type = 'regular'", [seasons, seasons]).df()
    cf_keys = set(zip(cf["season"], cf["week"], cf["t"]))
    played = tw[tw["dropbacks"] > 0]
    keys = list(zip(played["season"], played["week"], played["cfbd_team_id"]))
    return sum(k in cf_keys for k in keys) / len(keys)


def build(rows: list[dict]) -> tuple[pd.DataFrame, float]:
    import duckdb

    df = pd.DataFrame(rows)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    games = con.execute(
        "select game_id, season, week, home_team_id, away_team_id, home_points + away_points as actual "
        "from core.fact_game where game_id in (select unnest(?))", [df["game_id"].tolist()]).df()
    df = df.merge(games, on="game_id", how="left")
    seasons = sorted({int(s) for s in df["season"].dropna()} | {int(s) - 1 for s in df["season"].dropna()})
    tw = team_weeks(con, seasons)
    align = week_alignment(con, tw, seasons)
    con.close()

    feats = []
    for r in df.itertuples():
        if pd.isna(r.season):
            feats.append({})
            continue
        h = profile(tw, int(r.home_team_id), int(r.season), int(r.week))
        a = profile(tw, int(r.away_team_id), int(r.season), int(r.week))
        feats.append({n: (h[n] + a[n]) / 2 for n, *_ in FEATURES} if h and a else {})
    df = pd.concat([df, pd.DataFrame(feats, index=df.index)], axis=1)
    df["margin"] = df["line"].astype(float) - df["actual"]
    df["win"] = (df["result"] == "win").astype(float)
    return df, align


# ---------------------------------------------------------------- statistics

def cluster_ols(y: np.ndarray, X: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """OLS coefficients and CR1 cluster-robust standard errors."""
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    uniq = np.unique(groups)
    for g in uniq:
        m = groups == g
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    G, n, k = len(uniq), len(y), X.shape[1]
    adj = G / (G - 1) * (n - 1) / (n - k)
    V = adj * XtX_inv @ meat @ XtX_inv
    return beta, np.sqrt(np.diag(V)), G


def slope(sub: pd.DataFrame, feat: str, outcome: str) -> dict:
    """Slope of outcome on the feature z-scored within era, era fixed effects, date clusters."""
    d = sub[[feat, outcome, "era", "date"]].dropna()
    z = d.groupby("era")[feat].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
    eras = sorted(d["era"].unique())
    X = np.column_stack([z.to_numpy()] + [(d["era"] == e).to_numpy(float) for e in eras])
    beta, se, G = cluster_ols(d[outcome].to_numpy(float), X, d["date"].to_numpy())
    t = beta[0] / se[0]
    p = 2 * stats.t.sf(abs(t), G - 1)
    return {"n": len(d), "dates": G, "b": beta[0], "se": se[0], "p": p}


def bh(p: list[float]) -> list[float]:
    p = np.asarray(p)
    order = np.argsort(p)
    m = len(p)
    q = np.empty(m)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[i] * m / rank)
        q[i] = prev
    return q.tolist()


def holm(p: list[float]) -> list[float]:
    p = np.asarray(p)
    order = np.argsort(p)
    m = len(p)
    out = np.empty(m)
    running = 0.0
    for k, i in enumerate(order):
        running = max(running, min(1.0, (m - k) * p[i]))
        out[i] = running
    return out.tolist()


def halves(sub: pd.DataFrame, feat: str) -> tuple[str, str]:
    """W-L on the under-side half and the other half, split at each era's median."""
    d = sub[[feat, "win", "era"]].dropna()
    med = d.groupby("era")[feat].transform("median")
    direction = next(dr for n, *_, dr, _ in FEATURES if n == feat)
    on = d[feat] <= med if direction == "low" else d[feat] >= med
    fmt = lambda m: f"{int(d.loc[m, 'win'].sum())}-{int((1 - d.loc[m, 'win']).sum())}"  # noqa: E731
    return fmt(on), fmt(~on)


def screen(df: pd.DataFrame) -> pd.DataFrame:
    disc = df[df["era"].isin(DISCOVERY)]
    hold = df[df["era"] == HOLDOUT]
    out = []
    for name, unit, *_, direction, desc in FEATURES:
        d_m, d_w = slope(disc, name, "margin"), slope(disc, name, "win")
        h_m, h_w = slope(hold, name, "margin"), slope(hold, name, "win")
        a_m = slope(df, name, "margin")
        on, off = halves(df, name)
        out.append({"feature": name, "under_side": direction, "desc": desc,
                    "disc_n": d_m["n"], "disc_b_pts": d_m["b"], "disc_se": d_m["se"], "disc_p": d_m["p"],
                    "disc_b_win": d_w["b"], "disc_p_win": d_w["p"],
                    "hold_n": h_m["n"], "hold_b_pts": h_m["b"], "hold_se": h_m["se"], "hold_p": h_m["p"],
                    "hold_b_win": h_w["b"], "hold_p_win": h_w["p"],
                    "all_n": a_m["n"], "all_b_pts": a_m["b"], "all_se": a_m["se"], "all_p": a_m["p"],
                    "under_half": on, "other_half": off})
    res = pd.DataFrame(out)
    res["disc_q"] = bh(res["disc_p"].tolist())
    res["disc_holm"] = holm(res["disc_p"].tolist())
    res["all_q"] = bh(res["all_p"].tolist())
    res["all_holm"] = holm(res["all_p"].tolist())
    res["candidate"] = res["disc_q"] < Q_CANDIDATE
    res["sign_agrees"] = np.sign(res["disc_b_pts"]) == np.sign(res["hold_b_pts"])
    return res


# ---------------------------------------------------------------- market-wide follow-up

MARKET_SQL = f"""
select g.game_id, g.season, g.week, g.start_date::date::varchar as date,
       g.home_team_id, g.away_team_id, g.home_points + g.away_points as actual,
       median(l.total_close) as close
from core.fact_game g
join core.fact_game_line l using (game_id)
where g.season in (select unnest(?)) and g.week between 2 and {LAST_REGULAR_WEEK}
  and g.season_type = 'regular' and g.completed and g.home_points is not null
  and l._source <> 'gql' and l.total_close is not null
group by all
"""


def market(feat: str, seasons: list[int]) -> None:
    """One follow-up trial: does the feature move the close-minus-actual residual on EVERY
    FBS game with a REST-backed close, not just Greenline's unders? If the market misprices
    it everywhere it should show up here on ~10x the rows; if it lives only inside the
    flags, this reads ~0. REST-backed rows only (`_source <> 'gql'`, findings row 14)."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    g = con.execute(MARKET_SQL, [seasons]).df()
    tw = team_weeks(con, sorted(set(seasons) | {s - 1 for s in seasons}))
    con.close()
    vals = []
    for r in g.itertuples():
        h = profile(tw, int(r.home_team_id), int(r.season), int(r.week))
        a = profile(tw, int(r.away_team_id), int(r.season), int(r.week))
        vals.append((h[feat] + a[feat]) / 2 if h and a else np.nan)
    g[feat] = vals
    g["margin"] = g["close"] - g["actual"]
    g["era"] = g["season"].astype(str)  # season fixed effects, z within season
    g = g.dropna(subset=[feat, "margin"])
    s = slope(g, feat, "margin")
    print(f"Market-wide: {feat} on close - actual, seasons {seasons[0]}-{seasons[-1]}, weeks 2-{LAST_REGULAR_WEEK}")
    print(f"  n={s['n']} games, {s['dates']} dates: {s['b']:+.3f} pts per SD (SE {s['se']:.3f}, p {s['p']:.4f})")
    for season, sub in g.groupby("season"):
        ss = slope(sub, feat, "margin")
        print(f"  {season}: n={ss['n']:>4} {ss['b']:+.2f} (SE {ss['se']:.2f})")
    g["tercile"] = g.groupby("season")[feat].transform(lambda x: pd.qcut(x, 3, labels=["low", "mid", "high"]))
    g["under_won"] = (g["actual"] < g["close"]).astype(float)
    print(g[g["actual"] != g["close"]].groupby("tercile", observed=True)
          .agg(n=("margin", "size"), under_win=("under_won", "mean"), margin=("margin", "mean")).round(3))


# ---------------------------------------------------------------- entry

def self_check() -> None:
    rng = np.random.default_rng(0)
    n = 400
    x = rng.normal(size=n)
    g = np.repeat(np.arange(40), 10)
    y = 2.0 * x + rng.normal(size=n)
    X = np.column_stack([x, np.ones(n)])
    b, se, G = cluster_ols(y, X, g)
    assert abs(b[0] - 2.0) < 0.15 and G == 40 and se[0] > 0, (b, se)
    q = bh([0.01, 0.04, 0.03, 0.5])
    assert abs(q[0] - 0.04) < 1e-12 and abs(q[3] - 0.5) < 1e-12, q
    h = holm([0.01, 0.04, 0.03, 0.5])
    assert abs(h[0] - 0.04) < 1e-12 and abs(h[1] - 0.09) < 1e-12, h  # step-down stays monotone
    tw = pd.DataFrame({"cfbd_team_id": [1] * 4, "season": [2025, 2026, 2026, 2026],
                       "week": [5, 1, 2, 3], "franchise_id": [9] * 4})
    for _, _, num, den, _, _ in FEATURES:
        tw[num] = 1.0
        tw[den] = 40.0
    p = profile(tw, 1, 2026, 3)  # 2025 w5 + 2026 w1-2: the week-3 row must not enter
    tw.loc[3, "pass_grade_w"] = 1e6
    assert profile(tw, 1, 2026, 3) == p, "a game's own week leaked into its profile"
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, help="write the per-feature table here")
    ap.add_argument("--rows", type=Path, help="write the per-bet feature rows here")
    ap.add_argument("--market", metavar="FEATURE",
                    help="instead of the screen, test one feature on every FBS game's close residual")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    if a.market:
        market(a.market, list(range(2015, 2027)))
        return

    df, align = build(greenline_unders())
    have = df.dropna(subset=["actual", FEATURES[0][0]])
    print(f"Greenline unders: {len(df)}; with a final and both PFF profiles: {len(have)}")
    print(have.groupby("era").agg(n=("win", "size"), wins=("win", "sum"), margin=("margin", "mean")).round(2))
    print(f"PFF/CFBD week alignment: {align:.3f} of PFF team-weeks fall on a CFBD game week\n")

    res = screen(have)
    pd.set_option("display.width", 200)
    cols = ["feature", "under_side", "disc_b_pts", "disc_se", "disc_p", "disc_q", "disc_holm",
            "hold_b_pts", "hold_se", "hold_p", "all_b_pts", "all_p", "all_q", "under_half", "other_half"]
    print(res.sort_values("disc_p")[cols].round(3).to_string(index=False))
    print("\nslope = points of cover margin (line - actual; + favours the under) per 1 SD of the feature")
    cands = res[res["candidate"]]
    if cands.empty:
        print(f"No feature reaches discovery q < {Q_CANDIDATE}. Nothing goes to the 2026 holdout.")
    else:
        print("Candidates scored on the 2026 holdout:")
        print(cands[["feature", "disc_b_pts", "disc_q", "hold_b_pts", "hold_p", "sign_agrees"]].round(3).to_string(index=False))
    if a.csv:
        a.csv.parent.mkdir(parents=True, exist_ok=True)
        res.to_csv(a.csv, index=False)
        print(f"\nwrote {a.csv}")
    if a.rows:
        a.rows.parent.mkdir(parents=True, exist_ok=True)
        have.to_csv(a.rows, index=False)
        print(f"wrote {a.rows}")


if __name__ == "__main__":
    main()
