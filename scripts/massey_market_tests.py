"""Massey rankings against the opener, and every Massey system against the market.

EXPLORATORY follow-up to docs/fair-oster-massey-replication-2026-09-30.md. Two questions:
does ranking information beyond the paper's closing-line test survive against the **opener**,
and does **any** Massey system (not just the paper's nine) carry information the market lacks?

Pre-specified 2026-09-30, before the first run of this script:

  Sample   FBS-vs-FBS regular season, week >= 6, from fair_oster_massey.load (same
           orientation flip, same edition rule).
  Lines    Per-book spread_open / spread_close from core.fact_game_line. Opens exist only for
           2021-2025. Primary book: bovada, the only one with opens in all five seasons.
           Secondary: draftkings and espn bet (2023-2025).
  Timing   2026 Action Network ticks show CFBD's DraftKings open was posted Wed-Fri, before the
           previous weekend's games, for 49% of games (the rest: that Sunday). Older opens carry
           no timestamp. Every opener result is therefore an UPPER BOUND, and no ATS or ROI at
           the opener is computed: a price that cannot be placed at decision time is a hard
           gate under docs/model-evaluation-standard.md.
  Core     SAG BIL COL MAS DUN REC, the replication's modern core.
  A        Timing diagnostic: move M = LVc - LVo on last-week surprise S, per book; and on
           2026 DraftKings split by look-ahead vs Sunday open (the calibration).
  O1       Y ~ LVo + H + Q_core; F(others = 0), clustered by edition. Same on LVc, same games.
  O2       Walk-forward movement. rank_pred from Y ~ H + Q_core fit on 2013..s-1 (no opener
           needed); gap = rank_pred - LVo; M = gamma * gap with gamma fit on opener seasons < s;
           scored s = 2022-2025. R^2 of the move = 1 - sum (M - gamma*gap)^2 / sum M^2, the
           research/spread metric (a line that never moves scores 0).
  O3       M ~ gap + S, all opener seasons, clustered: does gap survive last week's surprise?
  Scan     Every system with median >= 100 teams ranked per edition, plus CMP (the composite).
           S1 Y ~ LVc + H + Q_k, 2013-2025, n >= 500.  S2 Y ~ LVo + H + Q_k, primary book, n >= 300.
           Benjamini-Hochberg q = .10 within each family on clustered p. A survivor must also
           beat the line out of sample (season walk-forward, delta-MSE CI below 0) and keep its
           sign in most seasons. Systems whose title or URL suggests a betting source are flagged.
  Power    MDE of a coefficient = 2.8 x its SE (two-sided .05, power .8).

Added after run 2 had been read (POST-HOC, exploratory, counted as extra trials):
  O4       DraftKings only: M ~ gap plus controls for DK converging to another book's open,
           for news since the previous edition, and for home field. See dk_controls().

Runs: 1 aborted before any output (slow bootstrap), 2 read, 3 adds O4.

Usage:  python scripts/massey_market_tests.py [--boot 2000]
Writes: $CFB_DATA_ROOT/processed/massey_market_tests.json; prints the tables.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fair_oster_massey as fo  # noqa: E402

CORE = ["SAG", "BIL", "COL", "MAS", "DUN", "REC"]
BOOKS = {"bovada": "bov", "draftkings": "dk", "espn bet": "espn"}
PRIMARY = "bov"
MARKET_WORDS = re.compile(r"wager|bookie|sharp|vegas|odds|spread|\bline\b|\bbet", re.I)

LINES_SQL = """
select game_id, provider_key, spread_open, spread_close from core.fact_game_line
where provider_key in ('bovada', 'draftkings', 'espn bet')
"""

# Last-week surprise: each team's most recent earlier game (same season, any opponent) that
# has a closing line; surprise = its margin minus the close's expected margin, team view.
SURPRISE_SQL = """
with cl as (select game_id, median(spread_close) as close from core.fact_game_line
            where spread_close is not null group by 1),
tg as (
  select g.gameId as game_id, g.season, g.startDate as t, g.homeTeam as team,
         cast(g.homePoints as int) - cast(g.awayPoints as int) + cl.close as surprise
  from stg.games g join cl on cl.game_id = g.gameId where g.completed
  union all
  select g.gameId, g.season, g.startDate, g.awayTeam,
         cast(g.awayPoints as int) - cast(g.homePoints as int) - cl.close
  from stg.games g join cl on cl.game_id = g.gameId where g.completed),
gm as (select gameId as game_id, season, startDate as t, homeTeam, awayTeam from stg.games
       where season >= ? and homeClassification = 'fbs' and awayClassification = 'fbs')
select gm.game_id, h.surprise - a.surprise as S from gm
asof join tg h on h.team = gm.homeTeam and h.season = gm.season and gm.t > h.t
asof join tg a on a.team = gm.awayTeam and a.season = gm.season and gm.t > a.t
"""

# 2026 DraftKings: was CFBD's open the Wed-Fri look-ahead or the Sunday line? AN ticks decide.
LOOKAHEAD_SQL = """
with ev as (
  select s.event_id, s.start_time,
         max(case when t.team_id = s.home_team_id then t.location end) as hloc,
         max(case when t.team_id = s.away_team_id then t.location end) as aloc
  from stg.an_scoreboard s join stg.an_team t using (event_id) where s.season = 2026
  group by all),
tk as (
  select g.gameId as game_id, cast(timezone('America/New_York', g.startDate) as date) as gd,
         timezone('America/New_York', t.updated_at) as ts, t.line
  from ev join stg.games g on g.season = 2026 and g.homeTeam = ev.hloc and g.awayTeam = ev.aloc
   and cast(timezone('America/New_York', g.startDate) as date)
     = cast(timezone('America/New_York', ev.start_time) as date)
  join stg.an_history_tick t using (event_id)
  where t.book_id = 15 and t.market_type = 'spread' and not t.is_live and t.period = 'event'
    and t.side = 'home'),
o as (select game_id, spread_open from core.fact_game_line where provider_key = 'draftkings')
select tk.game_id,
       min(tk.ts) < cast(any_value(tk.gd) - dayofweek(any_value(tk.gd)) * interval 1 day
                         as timestamp) as lookahead
from tk join o on o.game_id = tk.game_id and tk.line = o.spread_open group by 1
"""


def books(con) -> pd.DataFrame:
    """One row per game: LVo_/LVc_ per book, home orientation (LV = -spread)."""
    raw = con.execute(LINES_SQL).df()
    raw["b"] = raw.provider_key.map(BOOKS)
    w = raw.pivot_table(index="game_id", columns="b", values=["spread_open", "spread_close"])
    out = pd.DataFrame(index=w.index)
    for b in BOOKS.values():
        out["LVo_" + b] = -w[("spread_open", b)] if ("spread_open", b) in w else np.nan
        out["LVc_" + b] = -w[("spread_close", b)] if ("spread_close", b) in w else np.nan
    return out.reset_index()


def mde(se: float) -> float:
    return round(2.8 * float(se), 4)


def r2_move(m: np.ndarray, pred: np.ndarray) -> float:
    return float(1 - ((m - pred) ** 2).sum() / (m ** 2).sum())


def block_boot(o: pd.DataFrame, cols: list[str], stat, rng, boot: int) -> list[float]:
    """95% interval of stat(column sums) over bootstrap draws of whole weekly editions.

    Sums per edition once, then resamples rows of that small matrix: every statistic here
    is a ratio of sums, so this equals concatenating the drawn blocks, without the copies.
    """
    g = o.groupby("edition")[cols].sum().to_numpy()
    s = g[rng.integers(0, len(g), (boot, len(g)))].sum(axis=1)
    return [round(float(np.percentile(stat(s), q)), 3) for q in (2.5, 97.5)]


def timing(con, d: pd.DataFrame, sur: pd.DataFrame) -> dict:
    """A: does each book's open->close move load on last week's surprise?"""
    out = {}
    for b in BOOKS.values():
        x = d.dropna(subset=["LVo_" + b, "LVc_" + b, "S"]).assign(y=lambda t: t["M_" + b])
        if len(x) > 200:
            r = fo.fit(x, ["S"], f"A move_{b} ~ S")
            out[b] = {"n": r["n"], "coef_S": r["coef"]["S"], "t_cl": r["t_cl"]["S"],
                      "r2_move": round(r2_move(x.y.values, r["_ols"].fittedvalues), 3),
                      "seasons": [int(x.season.min()), int(x.season.max())]}
    # 2026 calibration: home orientation is fine here, the model has no constant.
    la = con.execute(LOOKAHEAD_SQL).df()
    g26 = la.merge(books(con), on="game_id").merge(sur, on="game_id").dropna(
        subset=["LVo_dk", "LVc_dk", "S"])
    g26["y"], g26["edition"] = g26.LVc_dk - g26.LVo_dk, g26.game_id  # iid SEs: no editions
    cal = {"share_lookahead": round(float(la.lookahead.mean()), 3), "n_matched": len(la)}
    for flag, grp in g26.groupby("lookahead"):
        r = fo.fit(grp, ["S"], f"A 2026 dk lookahead={flag}")
        cal["lookahead" if flag else "sunday"] = {
            "n": r["n"], "coef_S": r["coef"]["S"], "t": r["t"]["S"],
            "r2_move": round(r2_move(grp.y.values, r["_ols"].fittedvalues), 3)}
    out["calibration_2026_dk"] = cal
    return out


def opener_tests(d: pd.DataFrame, allmod: pd.DataFrame, boot: int) -> dict:
    """O1-O3 for each book."""
    rng = np.random.default_rng(0)
    out = {}
    for b in BOOKS.values():
        x = d.dropna(subset=["LVo_" + b, "LVc_" + b, *CORE]).copy()
        if len(x) < 300:
            continue
        res = {"n": len(x), "seasons": sorted(int(s) for s in x.season.unique())}
        for anchor in ("LVo_", "LVc_"):
            r = fo.fit(x, [anchor + b, "h", *CORE], f"O1 {anchor}{b}+core")
            R = np.eye(len(CORE) + 2)[1:]
            res["O1_" + anchor.rstrip("_")] = {
                "coef": r["coef"], "t_cl": r["t_cl"],
                "F_others_p": round(float(r["_ols"].f_test(R).pvalue), 3),
                "F_others_cl_p": round(float(r["_cl"].f_test(R).pvalue), 3)}
        # O2: rank_pred from 2013..s-1, gamma from opener seasons < s.
        x["M"] = x["M_" + b]
        for s in res["seasons"]:
            tr = allmod[allmod.season < s].dropna(subset=CORE)
            fitr = sm.OLS(tr.y, tr[["h", *CORE]]).fit()
            idx = x.season == s
            x.loc[idx, "rank_pred"] = fitr.predict(x.loc[idx, ["h", *CORE]])
        x["gap"] = x.rank_pred - x["LVo_" + b]
        wf = []
        for s in res["seasons"][1:]:
            tr, te = x[x.season < s], x[x.season == s].copy()
            g = float((tr.gap * tr.M).sum() / (tr.gap ** 2).sum())
            wf.append(te.assign(pred=g * te.gap, gamma=g))
        o = pd.concat(wf)
        o["e2"], o["m2"] = (o.M - o.pred) ** 2, o.M ** 2
        moved = (o.M != 0) & (o.gap != 0)
        res["O2_walk_forward"] = {
            "test_seasons": sorted(int(s) for s in o.season.unique()), "n": len(o),
            "gamma_by_season": o.groupby("season").gamma.first().round(3).to_dict(),
            "r2_move": round(r2_move(o.M.values, o.pred.values), 3),
            "r2_ci95": block_boot(o, ["e2", "m2"], lambda s: 1 - s[:, 0] / s[:, 1], rng, boot),
            "direction_right": round(float((np.sign(o.gap[moved]) == np.sign(o.M[moved])).mean()), 3),
            "n_direction": int(moved.sum()), "sd_move": round(float(o.M.std()), 2)}
        # O3: in-sample, all opener seasons, with and without last week's surprise.
        xs = x.dropna(subset=["S"]).assign(y=lambda t: t.M)
        r0 = fo.fit(xs, ["gap"], f"O3 {b} M~gap")
        r1 = fo.fit(xs, ["gap", "S"], f"O3 {b} M~gap+S")
        res["O3"] = {"n": r1["n"],
                     "gap_alone": {"coef": r0["coef"]["gap"], "t_cl": r0["t_cl"]["gap"],
                                   "mde": mde(r0["_cl"].bse[0]),
                                   "r2_move": round(r2_move(xs.y.values, r0["_ols"].fittedvalues), 3)},
                     "gap_with_S": {"coef": r1["coef"], "t_cl": r1["t_cl"],
                                    "r2_move": round(r2_move(xs.y.values, r1["_ols"].fittedvalues), 3)}}
        if b == "dk":
            res["O4_posthoc"] = dk_controls(xs)
        out[b] = res
    return out


def dk_controls(xs: pd.DataFrame) -> dict:
    """O4, POST-HOC (added after run 2 showed DK moving toward the rank gap): what is DK's gap
    standing in for? book_gap = Bovada's open minus DK's (DK converging to the market); dQ =
    change in the composite rank gap since the previous edition (news a look-ahead open
    missed); h = home field (DK's open prices it at 1.47 against 0.93 at its close)."""
    z = xs.dropna(subset=["LVo_bov", "dQ"]).assign(book_gap=lambda t: t.LVo_bov - t.LVo_dk)
    specs = {"gap": ["gap"], "+book_gap": ["gap", "book_gap"], "+dQ": ["gap", "dQ"],
             "+h": ["gap", "h"], "all": ["gap", "book_gap", "dQ", "h"]}
    out = {"n": len(z)}
    for name, cols in specs.items():
        r = fo.fit(z, cols, f"O4 posthoc dk M~{name}")
        out[name] = {"coef": r["coef"], "t_cl": r["t_cl"],
                     "r2_move": round(r2_move(z.y.values, r["_ols"].fittedvalues), 3)}
    return out


def scan(d: pd.DataFrame, systems: list[str], titles: dict, boot: int) -> dict:
    """S1 (vs close) and S2 (vs primary opener) for every eligible system."""
    rng = np.random.default_rng(1)
    fams = {"S1_close": ("LV", 500, d.season >= 2013),
            "S2_open": ("LVo_" + PRIMARY, 300, d["LVo_" + PRIMARY].notna())}
    out = {}
    for fam, (anchor, min_n, keep) in fams.items():
        rows = []
        for k in systems:
            x = d[keep].dropna(subset=[anchor, k])
            if len(x) < min_n:
                continue
            r = fo.fit(x, [anchor, "h", k], f"{fam} {k}")
            solo = sm.OLS(x.y, x[["h", k]]).fit()
            rows.append({
                "system": k, "title": titles.get(k, "Massey composite"), "n": r["n"],
                "seasons": f"{int(x.season.min())}-{int(x.season.max())}",
                "coef": r["coef"][k], "t_cl": r["t_cl"][k], "p_cl": float(r["_cl"].pvalues[2]),
                "mde": mde(r["_cl"].bse[2]), "anchor_coef": r["coef"][anchor],
                "rmse_solo_minus_line": round(float(np.sqrt(solo.ssr / len(x))
                                                    - np.sqrt(((x.y - x[anchor]) ** 2).mean())), 3),
                "paper_nine": k in fo.PAPER_SYSTEMS,
                "market_flag": bool(MARKET_WORDS.search(titles.get(k, "") or ""))})
        t = pd.DataFrame(rows)
        t["bh_reject"] = multipletests(t.p_cl, alpha=0.10, method="fdr_bh")[0]
        t["q_bh"] = multipletests(t.p_cl, method="fdr_bh")[1].round(3)
        t["holm_p"] = multipletests(t.p_cl, method="holm")[1].round(3)
        surv = {}
        for k in t.loc[t.bh_reject, "system"]:
            surv[k] = survivor_check(d[keep].dropna(subset=[anchor, k]), anchor, k, rng, boot)
        out[fam] = {"anchor": anchor, "n_systems": len(t), "n_bh_reject": int(t.bh_reject.sum()),
                    "table": t.sort_values("p_cl").round(4).to_dict("records"),
                    "survivors": surv}
    return out


def survivor_check(x: pd.DataFrame, anchor: str, k: str, rng, boot: int) -> dict:
    """Walk-forward: fit anchor + H + Q_k on earlier seasons; does it beat the raw line?"""
    TRIALS_TAG = f"WF {anchor} {k}"
    seasons = sorted(x.season.unique())
    parts = []
    for s in seasons[2:]:
        tr, te = x[x.season < s], x[x.season == s]
        b = sm.OLS(tr.y, tr[[anchor, "h", k]]).fit()
        parts.append(te.assign(pred=b.predict(te[[anchor, "h", k]])))
    fo.TRIALS.append(TRIALS_TAG)
    if not parts:
        return {"note": "fewer than three seasons"}
    o = pd.concat(parts)
    o["em"], o["el"], o["one"] = (o.y - o.pred) ** 2, (o.y - o[anchor]) ** 2, 1.0
    signs = [np.sign(sm.OLS(g.y, g[[anchor, "h", k]]).fit().params[k]) for _, g in x.groupby("season")]
    return {"test_seasons": f"{int(o.season.min())}-{int(o.season.max())}", "n": len(o),
            "delta_mse_vs_line": round(float(o.em.mean() - o.el.mean()), 3),
            "ci95": block_boot(o, ["em", "el", "one"], lambda s: (s[:, 0] - s[:, 1]) / s[:, 2],
                               rng, boot),
            "seasons_positive": int(sum(s > 0 for s in signs)), "seasons": len(signs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    con = duckdb.connect(str(fo.DATA_ROOT / "cfb.duckdb"), read_only=True)
    elig = con.execute(
        "select system from (select system, date, count(*) n from stg.massey_ranks "
        "where season between 2013 and 2025 group by all) group by 1 "
        "having median(n) >= 100 order by 1").df().system.tolist()
    titles = dict(con.execute("select system, fulltitle || ' ' || coalesce(url, '') "
                              "from stg.massey_systems").fetchall())
    systems = sorted(set(elig) | set(CORE[:-1])) + ["CMP"]
    d, side = fo.load(con, 2013, 2025, systems)
    # dQ: change in the composite rank gap since the previous edition (flip applied below).
    eds = sorted(side.index.get_level_values("edition").unique())
    d["prev_ed"] = d.edition.map(dict(zip(eds[1:], eds[:-1])))
    prev = side[["CMP", "n_teams"]].reset_index()
    for s, team in (("hp_", "home"), ("ap_", "away")):
        d = d.merge(prev.add_prefix(s), left_on=["prev_ed", team],
                    right_on=[s + "edition", s + "team"], how="left")
    d["dQ"] = d.CMP - d.flip * 100 * (d.ap_CMP - d.hp_CMP) / d.hp_n_teams
    sur = con.execute(SURPRISE_SQL, [2013]).df()
    d = d.merge(books(con), on="game_id", how="left").merge(sur, on="game_id", how="left")
    for c in [c for c in d if c.startswith(("LVo_", "LVc_"))] + ["S"]:
        d[c] = d[c] * d.flip
    for b in BOOKS.values():
        d["M_" + b] = d["LVc_" + b] - d["LVo_" + b]
    # Sanity: the flip reached every added column iff the opener's slope on Y is near +1.
    chk = d.dropna(subset=["LVo_" + PRIMARY])
    slope = float(sm.OLS(chk.y, chk[["LVo_" + PRIMARY]]).fit().params.iloc[0])
    assert 0.8 < slope < 1.2, f"opener slope {slope:.2f}: a column missed the flip"

    res = {"eligible_systems": len(systems), "opener_slope_check": round(slope, 3),
           "A_timing": timing(con, d, sur),
           "opener": opener_tests(d[d.season >= 2021], d, a.boot),
           "scan": scan(d, systems + ["REC"], titles, a.boot)}
    res["trials"] = len(fo.TRIALS)
    report(res)
    path = fo.DATA_ROOT / "processed" / "massey_market_tests.json"
    path.write_text(json.dumps(fo.clean(res), indent=1, default=str))
    print("wrote", path)


def report(r: dict) -> None:
    print(f"eligible systems: {r['eligible_systems']}; opener slope check {r['opener_slope_check']}")
    print("\n## A timing\n" + json.dumps(fo.clean(r["A_timing"]), indent=1, default=str))
    print("\n## Opener tests")
    for b, v in r["opener"].items():
        print(f"\n### {b}  n={v['n']} seasons={v['seasons']}")
        for k in ("O1_LVo", "O1_LVc"):
            print(k, {"coef": v[k]["coef"], "t_cl": v[k]["t_cl"]},
                  "F p", v[k]["F_others_p"], "cl p", v[k]["F_others_cl_p"])
        print("O2", v["O2_walk_forward"])
        print("O3", fo.clean(v["O3"]))
        if "O4_posthoc" in v:
            print("O4 (post-hoc)", json.dumps(fo.clean(v["O4_posthoc"]), default=str))
    for fam, v in r["scan"].items():
        print(f"\n## {fam}: {v['n_systems']} systems, BH q=.10 rejects {v['n_bh_reject']}")
        t = pd.DataFrame(v["table"])
        print(t[["system", "title", "n", "seasons", "coef", "t_cl", "q_bh", "holm_p", "mde",
                 "rmse_solo_minus_line", "paper_nine", "market_flag"]].head(15).to_string(index=False))
        print("paper nine:\n" + t[t.paper_nine][["system", "n", "coef", "t_cl", "q_bh"]].to_string(index=False))
        print("best solo (rmse gap to line):\n" + t.sort_values("rmse_solo_minus_line")[
            ["system", "title", "n", "rmse_solo_minus_line"]].head(10).to_string(index=False))
        print("survivors:", json.dumps(v["survivors"], indent=1))
    print("\ntrial count:", r["trials"], "regressions")


if __name__ == "__main__":
    main()
