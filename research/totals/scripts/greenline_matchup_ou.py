"""Two follow-ups to `pff_under_screen.py`, asked 2026-10-15, on the same 402 Greenline unders.

    python research/totals/scripts/greenline_matchup_ou.py
    python research/totals/scripts/greenline_matchup_ou.py --rows data/exports/greenline_matchup_ou.csv

1. **Good/bad offense x good/bad defense.** Each team's PFF offense grade (snap-weighted
   `grades_offense`) and defense grade (snap-weighted `grades_defense`), on the same
   no-lookahead window as the screen: last regular season plus this season strictly before
   the game's week. "Good" is at or above the median of the bet rows' teams in that era.
   A game falls in one of nine cells: how many of its two offenses are good (0-2) by how
   many of its two defenses are good (0-2). One omnibus test across the nine cells (one-way F
   on era-demeaned margins, within-era permutation p), then the cells as a description.

2. **Over/under record to date.** Does a team's history against the total, this season
   before the game, say anything? The idea: when teams have been going over, the market has
   already raised their totals, and PFF's projection might lag that adjustment. Two features,
   both the mean over the two teams, each team needing two prior games with a REST-backed
   close (`_source <> 'gql'`, findings row 14):
       ou_resid  mean (actual - close) in the team's prior games this season, in points
       ou_over   share of those games that went over, pushes dropped
   Each is tested on the unders (two-sided) and then, as a control, on every FBS game's
   close residual, to tell "PFF lags the market" from "the market itself lags".

Trials added to the ledger by this script: 1 omnibus + 2 O/U features = 3 (running total
for this question, with the screen's 20: 23). Holm is applied across the two O/U features.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

from cfb_paths import DB_PATH  # noqa: E402
from pff_under_screen import LAST_REGULAR_WEEK, _f, holm, slope  # noqa: E402
from under_filters import greenline_unders  # noqa: E402

MIN_SNAPS = 300       # about five games of offensive or defensive snaps across the window
MIN_OU_GAMES = 2

GRADE_SQL = f"""
with o as (
    select season, week, franchise_id,
           sum({_f('grades_offense')} * {_f('snap_counts_total')}) as off_w,
           sum(case when grades_offense is null or isnan(grades_offense) then 0
                    else {_f('snap_counts_total')} end) as off_snaps
    from stg.pff_offense_summary where season in (select unnest(?)) group by all
), d as (
    select season, week, franchise_id,
           sum({_f('grades_defense')} * {_f('snap_counts_defense')}) as def_w,
           sum(case when grades_defense is null or isnan(grades_defense) then 0
                    else {_f('snap_counts_defense')} end) as def_snaps
    from stg.pff_defense_summary where season in (select unnest(?)) group by all
)
select f.cfbd_team_id, o.season, o.week, o.off_w, o.off_snaps, d.def_w, d.def_snaps
from o join d using (season, week, franchise_id)
join stg.pff_franchise f using (franchise_id)
where f.cfbd_team_id is not null and o.week <= {LAST_REGULAR_WEEK}
"""

# Every completed regular-season FBS game with a REST-backed close, both team ids.
CLOSE_SQL = """
select g.game_id, g.season, g.week, g.start_date::date::varchar as date,
       g.home_team_id, g.away_team_id, g.home_points + g.away_points as actual,
       median(l.total_close) as close
from core.fact_game g
join core.fact_game_line l using (game_id)
where g.season in (select unnest(?)) and g.season_type = 'regular' and g.completed
  and g.home_points is not null and l._source <> 'gql' and l.total_close is not null
group by all
"""


def grade_profile(gw: pd.DataFrame, team: int, season: int, week: int) -> tuple[float, float] | None:
    t = gw[gw["cfbd_team_id"] == team]
    win = t[((t["season"] == season - 1) & (t["week"] <= LAST_REGULAR_WEEK))
            | ((t["season"] == season) & (t["week"] < min(week, LAST_REGULAR_WEEK + 1)))]
    s = win[["off_w", "off_snaps", "def_w", "def_snaps"]].sum()
    if s["off_snaps"] < MIN_SNAPS or s["def_snaps"] < MIN_SNAPS:
        return None
    return s["off_w"] / s["off_snaps"], s["def_w"] / s["def_snaps"]


def ou_to_date(closes: pd.DataFrame, team: int, season: int, week: int) -> tuple[float, float] | None:
    """Mean (actual - close) and over share in the team's games this season before `week`."""
    c = closes[(closes["season"] == season) & (closes["week"] < week)
               & ((closes["home_team_id"] == team) | (closes["away_team_id"] == team))]
    if len(c) < MIN_OU_GAMES:
        return None
    resid = c["actual"] - c["close"]
    decided = resid[resid != 0]
    return resid.mean(), (decided > 0).mean() if len(decided) else np.nan


def build(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    import duckdb

    df = pd.DataFrame(rows)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    games = con.execute(
        "select game_id, season, week, home_team_id, away_team_id, home_points + away_points as actual "
        "from core.fact_game where game_id in (select unnest(?))", [df["game_id"].tolist()]).df()
    df = df.merge(games, on="game_id", how="left").dropna(subset=["actual"])
    seasons = sorted({int(s) for s in df["season"]})
    gw = con.execute(GRADE_SQL, [sorted(set(seasons) | {s - 1 for s in seasons})] * 2).df().fillna(0.0)
    market_seasons = list(range(2015, 2027))
    closes = con.execute(CLOSE_SQL, [market_seasons]).df()
    con.close()

    feats = []
    for r in df.itertuples():
        s, w = int(r.season), int(r.week)
        h, a = grade_profile(gw, int(r.home_team_id), s, w), grade_profile(gw, int(r.away_team_id), s, w)
        oh, oa = ou_to_date(closes, int(r.home_team_id), s, w), ou_to_date(closes, int(r.away_team_id), s, w)
        feats.append({
            "home_off": h[0] if h else np.nan, "home_def": h[1] if h else np.nan,
            "away_off": a[0] if a else np.nan, "away_def": a[1] if a else np.nan,
            "ou_resid": (oh[0] + oa[0]) / 2 if oh and oa else np.nan,
            "ou_over": (oh[1] + oa[1]) / 2 if oh and oa else np.nan,
        })
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    df["margin"] = df["line"].astype(float) - df["actual"]
    df["win"] = (df["result"] == "win").astype(float)

    # Good = at or above the era median of all team-values on the bet rows.
    for side in ("off", "def"):
        vals = pd.concat([df[["era", f"home_{side}"]].rename(columns={f"home_{side}": "v"}),
                          df[["era", f"away_{side}"]].rename(columns={f"away_{side}": "v"})])
        med = vals.groupby("era")["v"].median()
        m = df["era"].map(med)
        df[f"good_{side}"] = (df[f"home_{side}"] >= m).astype(float) + (df[f"away_{side}"] >= m).astype(float)
        df.loc[df[f"home_{side}"].isna() | df[f"away_{side}"].isna(), f"good_{side}"] = np.nan

    closes["margin"] = closes["close"] - closes["actual"]
    return df, closes


def cell_test(d: pd.DataFrame, n_perm: int = 5000, seed: int = 1) -> tuple[float, float]:
    """Do the nine cells share one mean margin? One-way F on era-demeaned margins, with a
    within-era permutation p-value.

    Not a cluster-robust Wald test: 2026 has only 16 slate dates, and a cluster Wald on
    eight restrictions with 16 clusters over-rejects badly (it read F 15.8 on data whose
    permutation p is 0.16). Permutation ignores the date clustering, which makes it, if
    anything, slightly generous."""
    d = d.dropna(subset=["good_off", "good_def"]).reset_index(drop=True)
    cell = (d["good_off"].astype(int) * 3 + d["good_def"].astype(int)).to_numpy()
    era = d["era"].to_numpy()
    y = d["margin"].to_numpy(float)

    def f_stat(v: np.ndarray) -> float:
        r = v - pd.Series(v).groupby(era).transform("mean").to_numpy()
        means = pd.Series(r).groupby(cell).agg(["mean", "size"])
        fitted = pd.Series(cell).map(means["mean"]).to_numpy()
        k = len(means) - 1
        ssb = (means["size"] * (means["mean"] - r.mean()) ** 2).sum()
        ssw = ((r - fitted) ** 2).sum()
        return (ssb / k) / (ssw / (len(r) - k - 1))

    f0 = f_stat(y)
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_perm):
        yy = y.copy()
        for e in np.unique(era):
            m = era == e
            yy[m] = rng.permutation(yy[m])
        hits += f_stat(yy) >= f0
    return f0, hits / n_perm


def grid(d: pd.DataFrame) -> pd.DataFrame:
    d = d.dropna(subset=["good_off", "good_def"])
    t = d.groupby(["good_off", "good_def"]).agg(
        n=("win", "size"), wins=("win", "sum"), margin=("margin", "mean")).reset_index()
    t["record"] = t["wins"].astype(int).astype(str) + "-" + (t["n"] - t["wins"]).astype(int).astype(str)
    t["win_pct"] = (t["wins"] / t["n"] * 100).round(1)
    t["margin"] = t["margin"].round(2)
    return t[["good_off", "good_def", "n", "record", "win_pct", "margin"]]


def market_ou(closes: pd.DataFrame, feat: str) -> dict:
    """The same O/U feature against every FBS game's close residual, weeks 3-14."""
    g = closes[(closes["week"] >= 3) & (closes["week"] <= LAST_REGULAR_WEEK) & (closes["season"] >= 2015)].copy()
    vals = []
    by_season = {s: c for s, c in closes.groupby("season")}
    for r in g.itertuples():
        c = by_season[r.season]
        oh = ou_to_date(c, int(r.home_team_id), int(r.season), int(r.week))
        oa = ou_to_date(c, int(r.away_team_id), int(r.season), int(r.week))
        idx = 0 if feat == "ou_resid" else 1
        vals.append((oh[idx] + oa[idx]) / 2 if oh and oa else np.nan)
    g[feat] = vals
    g["era"] = g["season"].astype(str)
    return slope(g.dropna(subset=[feat]), feat, "margin")


def market_build() -> pd.DataFrame:
    """Every FBS regular-season game, weeks 2-14 of 2015-2026, with a REST-backed close:
    the same matchup cell and O/U features as the unders, against close - actual."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    seasons = list(range(2015, 2027))
    closes = con.execute(CLOSE_SQL, [seasons]).df()
    gw = con.execute(GRADE_SQL, [[s - 1 for s in seasons] + seasons] * 2).df().fillna(0.0)
    con.close()
    g = closes[(closes["week"] >= 2) & (closes["week"] <= LAST_REGULAR_WEEK)].copy()
    by_season = {s: c for s, c in closes.groupby("season")}
    feats = []
    for r in g.itertuples():
        s, w = int(r.season), int(r.week)
        h, a = grade_profile(gw, int(r.home_team_id), s, w), grade_profile(gw, int(r.away_team_id), s, w)
        oh = ou_to_date(by_season[s], int(r.home_team_id), s, w)
        oa = ou_to_date(by_season[s], int(r.away_team_id), s, w)
        feats.append({
            "home_off": h[0] if h else np.nan, "home_def": h[1] if h else np.nan,
            "away_off": a[0] if a else np.nan, "away_def": a[1] if a else np.nan,
            "ou_resid": (oh[0] + oa[0]) / 2 if oh and oa else np.nan,
            "ou_over": (oh[1] + oa[1]) / 2 if oh and oa else np.nan,
        })
    g = pd.concat([g.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    g["margin"] = g["close"] - g["actual"]
    g["era"] = g["season"].astype(str)
    g = g[g["actual"] != g["close"]].copy()         # pushes carry no under/over result
    g["win"] = (g["actual"] < g["close"]).astype(float)   # "win" = the under won
    # Good = at or above that season's median over every team-game value in the sample.
    for side in ("off", "def"):
        vals = pd.concat([g[["era", f"home_{side}"]].rename(columns={f"home_{side}": "v"}),
                          g[["era", f"away_{side}"]].rename(columns={f"away_{side}": "v"})])
        m = g["era"].map(vals.groupby("era")["v"].median())
        g[f"good_{side}"] = (g[f"home_{side}"] >= m).astype(float) + (g[f"away_{side}"] >= m).astype(float)
        g.loc[g[f"home_{side}"].isna() | g[f"away_{side}"].isna(), f"good_{side}"] = np.nan
    return g


def market_main() -> None:
    g = market_build()
    print(f"FBS games 2015-26, weeks 2-14, REST-backed close, no push: {len(g)}; "
          f"with both grade profiles: {g['good_off'].notna().sum()}; with both O/U histories: {g['ou_over'].notna().sum()}")
    print("win = the UNDER won; margin = close - actual (+ favours under)\n")
    early, late = g[g["season"] <= 2020], g[g["season"] >= 2021]
    print("=== 1. good offenses x good defenses, every game ===")
    for label, sub in [("2015-26", g), ("2015-20", early), ("2021-26", late)]:
        F, p = cell_test(sub, n_perm=1000)
        print(f"\n{label}: omnibus F = {F:.2f}, permutation p {p:.3f}")
        print(grid(sub).to_string(index=False))
    print("\n=== 2. over/under record to date, every game (weeks 3-14) ===")
    for feat in ("ou_resid", "ou_over"):
        sub = g.dropna(subset=[feat])
        s_all, s_e, s_l = slope(sub, feat, "margin"), slope(sub[sub["season"] <= 2020], feat, "margin"), \
            slope(sub[sub["season"] >= 2021], feat, "margin")
        print(f"\n{feat}: n={s_all['n']} {s_all['b']:+.3f} pts/SD (SE {s_all['se']:.3f}, p {s_all['p']:.3f}); "
              f"2015-20 {s_e['b']:+.3f} (SE {s_e['se']:.3f}, p {s_e['p']:.3f}); 2021-26 {s_l['b']:+.3f} (SE {s_l['se']:.3f}, p {s_l['p']:.3f})")
        sub = sub.copy()
        sub["fifth"] = sub.groupby("era")[feat].transform(
            lambda x: pd.qcut(x.rank(method="first"), 5, labels=["1 low", "2", "3", "4", "5 high"]))
        for label, part in [("all", sub), ("2015-20", sub[sub["season"] <= 2020]), ("2021-26", sub[sub["season"] >= 2021])]:
            t = part.groupby("fifth", observed=True).agg(n=("win", "size"), under=("win", "mean"), margin=("margin", "mean"))
            print(f"  {label}: " + "  ".join(f"{i}: {r.under * 100:.1f}% ({r.n})" for i, r in t.iterrows()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, help="write the per-bet rows here")
    ap.add_argument("--market", action="store_true",
                    help="run both questions on every FBS game instead of the Greenline unders")
    a = ap.parse_args()
    if a.market:
        market_main()
        return

    df, closes = build(greenline_unders())
    print(f"unders with a final: {len(df)}; with both grade profiles: {df['good_off'].notna().sum()}; "
          f"with both O/U histories: {df['ou_resid'].notna().sum()}\n")

    print("=== 1. good offenses x good defenses (count of the two teams at/above the era median) ===")
    for label, sub in [("all eras", df), ("2026 only", df[df["era"] == "2026 flags"]),
                       ("2020 + 2022-23", df[df["era"] != "2026 flags"])]:
        F, p = cell_test(sub)
        print(f"\n{label}: omnibus F = {F:.2f}, permutation p {p:.3f}, {sub['date'].nunique()} dates"
              "  (margin = line - actual, + favours under)")
        print(grid(sub).to_string(index=False))
    # Interpretable one-number versions of the grid, as descriptions (not extra trials).
    for col in ("good_off", "good_def"):
        s = slope(df.dropna(subset=[col]), col, "margin")
        print(f"\n  margin per extra good {col[5:]}ense: {s['b'] / df[col].std():+.2f} pts (p {s['p']:.3f})")

    print("\n=== 2. over/under record to date (mean of the two teams, this season before the game) ===")
    res = []
    for feat in ("ou_resid", "ou_over"):
        sub = df.dropna(subset=[feat])
        s_all = slope(sub, feat, "margin")
        s26 = slope(sub[sub["era"] == "2026 flags"], feat, "margin")
        s_old = slope(sub[sub["era"] != "2026 flags"], feat, "margin")
        mk = market_ou(closes, feat)
        res.append((feat, s_all, s_old, s26, mk))
    hp = holm([r[1]["p"] for r in res])
    for (feat, s_all, s_old, s26, mk), h in zip(res, hp):
        print(f"\n{feat}: unders n={s_all['n']}  {s_all['b']:+.2f} pts/SD (SE {s_all['se']:.2f}, p {s_all['p']:.3f}, Holm {h:.3f})")
        print(f"  2020+2022-23 {s_old['b']:+.2f} (SE {s_old['se']:.2f}, n={s_old['n']});"
              f"  2026 {s26['b']:+.2f} (SE {s26['se']:.2f}, n={s26['n']})")
        print(f"  market-wide control, all FBS 2015-26 wk 3-14: {mk['b']:+.3f} pts/SD (SE {mk['se']:.3f}, n={mk['n']}, p {mk['p']:.3f})")
        sub = df.dropna(subset=[feat]).copy()
        sub["third"] = sub.groupby("era")[feat].transform(lambda x: pd.qcut(x, 3, labels=["low", "mid", "high"]))
        t = sub.groupby("third", observed=True).agg(n=("win", "size"), wins=("win", "sum"), margin=("margin", "mean"))
        t["record"] = t["wins"].astype(int).astype(str) + "-" + (t["n"] - t["wins"]).astype(int).astype(str)
        t["win_pct"] = (t["wins"] / t["n"] * 100).round(1)
        print(t[["n", "record", "win_pct", "margin"]].round(2).to_string())

    if a.rows:
        a.rows.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.rows, index=False)
        print(f"\nwrote {a.rows}")


if __name__ == "__main__":
    main()
