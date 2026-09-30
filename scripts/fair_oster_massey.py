"""Fair & Oster (2005), "College Football Rankings and Market Efficiency", on Massey data.

The paper regresses the actual margin on a home-field dummy and each computer system's
rank difference (Fair-Shiller 1990: no constant), finds several systems carry independent
information, then adds the closing spread and finds none of them survive it.

This script rebuilds every table from the Massey composite archive (stg.massey_*):

  era "paper"   1998-2001, the paper's window. No lines exist for it here, so no Table 5.
                Massey's Colley series starts 2000-10-09, so COL only enters Table 4.
  era "modern"  2013-2025, closing line = per-game median spread_close across books.

Deviations from the paper, all deliberate:
  - Q is 100 * (R_away - R_home) / N, rank difference as percent of the N ranked teams, so
    one scale spans 112-136 teams. Multiply a paper coefficient by N/100 (~1.15) to compare.
  - Games are oriented home = i, then flipped by game-id parity (paper: "arbitrary"). OLS
    coefficients and SEs are invariant to the flip; it only centres R^2 and Table 1.
  - Edition = latest Massey edition dated strictly before the game's US/Eastern date.
  - t-stats are reported twice: OLS (the paper's) and clustered by edition (week).
  - Walk-forward by season (fit on earlier seasons only) is added, per
    docs/model-evaluation-standard.md; the paper's weights are fit in-sample.

Usage:  python scripts/fair_oster_massey.py [--era paper|modern|all] [--boot 2000]
Writes: $CFB_DATA_ROOT/processed/fair_oster_massey.json; prints markdown tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f as fdist

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

PAPER_SYSTEMS = ["MAT", "SAG", "BIL", "AND", "COL", "MAS", "RTH", "WOL", "DUN"]  # SEA=AND
ERAS = {"paper": (1998, 2001), "modern": (2013, 2025)}
CORE_COVERAGE = 0.90  # a system joins the Table 2 core if it ranks >= 90% of era games
TRIALS: list[str] = []  # every regression fit, for the trial count


def load(con, lo: int, hi: int, systems: list[str] | None = None
         ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Games (one row per FBS-vs-FBS regular-season game, week >= 6, both teams ranked)
    and the per-edition team table they were joined from.

    `systems` defaults to the paper's nine; pass a list to load others. "CMP" is the Massey
    composite rank itself. Column `flip` is the +-1 applied to every signed column, for
    callers that add their own home-oriented columns.
    """
    systems = PAPER_SYSTEMS if systems is None else systems
    games = con.execute(
        """
        with g as (
          select gameId as game_id, season, week,
                 cast(timezone('America/New_York', startDate) as date) as gdate,
                 homeTeam as home, awayTeam as away,
                 cast(homePoints as int) - cast(awayPoints as int) as y,
                 case when neutralSite then 0 else 1 end as h
          from stg.games
          where seasonType = 'regular' and week >= 6 and completed
            and homeClassification = 'fbs' and awayClassification = 'fbs'
            and season between ? and ?
        ), ed as (select distinct season, date as edition from stg.massey_editions)
        select g.*, ed.edition from g
        asof join ed on g.season = ed.season and g.gdate > ed.edition
        """,
        [lo, hi],
    ).df()
    ranks = con.execute(
        "select date as edition, cfbd_team as team, system, rank from stg.massey_ranks "
        "where season between ? and ? and list_contains(?, system)",
        [lo, hi, systems],
    ).df().pivot_table(index=["edition", "team"], columns="system", values="rank")
    eds = con.execute(
        "select date as edition, cfbd_team as team, wins, losses, cmp_rank as CMP, "
        "count(*) over (partition by date) as n_teams from stg.massey_editions "
        "where season between ? and ?",
        [lo, hi],
    ).df().set_index(["edition", "team"])
    eds["wpct"] = eds.wins / (eds.wins + eds.losses).replace(0, np.nan)
    side = eds.join(ranks, how="left")
    d = games.join(side.add_prefix("h_"), on=["edition", "home"]).join(
        side.add_prefix("a_"), on=["edition", "away"])
    d = d[d.h_n_teams.notna() & d.a_n_teams.notna()].copy()
    n = d.h_n_teams
    for s in systems:
        d[s] = 100 * (d["a_" + s] - d["h_" + s]) / n if "h_" + s in d else np.nan
    d["REC"] = 100 * (d.h_wpct - d.a_wpct)
    lines = con.execute(
        "select game_id, median(spread_close) as close from core.fact_game_line "
        "where spread_close is not null group by 1").df()
    d = d.merge(lines, on="game_id", how="left")
    d["LV"] = -d.close  # spread_close < 0 means home favoured
    d["flip"] = np.where(d.game_id % 2 == 0, 1.0, -1.0)
    for c in ["y", "h", "LV", "REC", *systems]:
        d[c] = d[c] * d.flip
    return d.reset_index(drop=True), side


def check_no_lookahead(con, d: pd.DataFrame) -> dict:
    """Edition W-L must count games before the edition date and never the game itself."""
    played = con.execute(
        """
        with t as (
          select season, homeTeam as team, cast(timezone('America/New_York', startDate) as date) as gd
          from stg.games where completed and seasonType = 'regular'
          union all
          select season, awayTeam, cast(timezone('America/New_York', startDate) as date)
          from stg.games where completed and seasonType = 'regular')
        select * from t""").df()
    rows = d[["season", "edition", "home", "gdate", "h_wins", "h_losses"]].rename(
        columns={"home": "team"})
    m = rows.merge(played, on=["season", "team"])
    m["by_edition"] = m.gd <= m.edition
    m["by_game"] = m.gd < m.gdate
    agg = m.groupby(["season", "edition", "team", "gdate", "h_wins", "h_losses"])[
        ["by_edition", "by_game"]].sum().reset_index()
    gp = agg.h_wins + agg.h_losses
    return {"wl_matches_edition_date": float((gp == agg.by_edition).mean()),
            "wl_includes_later_games": float((gp > agg.by_game).mean())}


def fit(d: pd.DataFrame, cols: list[str], label: str) -> dict:
    X, y = d[cols].to_numpy(float), d.y.to_numpy(float)
    TRIALS.append(label)
    ols = sm.OLS(y, X).fit()
    cl = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": d.edition.astype(str)})
    tss = ((y - y.mean()) ** 2).sum()
    nz = y != 0
    return {
        "label": label, "n": int(len(y)), "cols": cols,
        "coef": dict(zip(cols, ols.params.round(4))),
        "t": dict(zip(cols, ols.tvalues.round(2))),
        "t_cl": dict(zip(cols, cl.tvalues.round(2))),
        "se_reg": round(float(np.sqrt(ols.ssr / ols.df_resid)), 2),
        "r2": round(float(1 - ols.ssr / tss), 3),
        "right": round(float((np.sign(ols.fittedvalues[nz]) == np.sign(y[nz])).mean()), 3),
        "_ols": ols, "_cl": cl,
    }


def select_systems(res: dict, systems: list[str]) -> list[str]:
    """Paper's regression 9: which systems survive from the all-in regression 8.

    Clustered t, not the paper's OLS t: games in one week share a ranking snapshot.
    """
    return [s for s in systems if abs(res["t_cl"][s]) >= 1.96]


def chow(d: pd.DataFrame, cols: list[str]) -> dict:
    """F test that coefficients are equal in the first and second half of the seasons."""
    seasons = sorted(d.season.unique())
    first = d.season.isin(seasons[: len(seasons) // 2])
    ssr = lambda x: sm.OLS(x.y.to_numpy(float), x[cols].to_numpy(float)).fit().ssr  # noqa: E731
    k, n = len(cols), len(d)
    s1, s2 = ssr(d[first]), ssr(d[~first])
    F = ((ssr(d) - s1 - s2) / k) / ((s1 + s2) / (n - 2 * k))
    return {"F": round(float(F), 2), "df": [k, n - 2 * k], "p": round(float(fdist.sf(F, k, n - 2 * k)), 3),
            "split": f"{seasons[0]}-{seasons[len(seasons) // 2 - 1]} vs "
                     f"{seasons[len(seasons) // 2]}-{seasons[-1]}"}


def market_test(d: pd.DataFrame, cols: list[str], label: str) -> dict:
    """Table 5: add LV; F test that everything but LV is zero; t test that LV = 1."""
    r = fit(d, ["LV", *cols], label)
    others = np.eye(len(cols) + 1)[1:]
    b, se = r["_ols"].params[0], r["_ols"].bse[0]
    return {**r, "F_others": round(float(r["_ols"].f_test(others).fvalue), 2),
            "F_others_p": round(float(r["_ols"].f_test(others).pvalue), 3),
            "F_others_cl_p": round(float(r["_cl"].f_test(others).pvalue), 3),
            "df": [len(cols), r["n"] - len(cols) - 1],
            "t_LV_eq_1": round(float((b - 1) / se), 2)}


def walk_forward(d: pd.DataFrame, core: list[str], min_train: int, boot: int) -> dict:
    """Fit on seasons < s, score s. Best single system is chosen on the training window."""
    seasons = sorted(d.season.unique())
    rows = []
    for s in seasons[min_train:]:
        tr, te = d[d.season < s], d[d.season == s].copy()
        solo = {k: sm.OLS(tr.y, tr[["h", k]]).fit() for k in core}
        best = min(solo, key=lambda k: solo[k].ssr)
        te["best_single"] = solo[best].predict(te[["h", best]])
        te["best_name"] = best
        te["combo"] = sm.OLS(tr.y, tr[["h", *core]]).fit().predict(te[["h", *core]])
        rows.append(te)
    o = pd.concat(rows)
    preds = ["best_single", "combo"] + (["LV"] if o.LV.notna().all() else [])
    rmse = lambda x, p: float(np.sqrt(((x.y - x[p]) ** 2).mean()))  # noqa: E731
    out = {"test_seasons": [int(x) for x in o.season.unique()], "n": int(len(o)),
           "rmse": {p: round(rmse(o, p), 3) for p in preds},
           "best_single_by_season": o.groupby("season").best_name.first().to_dict()}
    rng = np.random.default_rng(0)
    blocks = [g for _, g in o.groupby("edition")]
    diffs = {f"combo-{p}": [] for p in preds if p != "combo"}
    for _ in range(boot):
        b = pd.concat([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        for p in preds:
            if p != "combo":
                diffs[f"combo-{p}"].append(rmse(b, "combo") - rmse(b, p))
    out["rmse_diff"] = {k: {"point": round(rmse(o, "combo") - rmse(o, k.split("-")[1]), 3),
                            "ci95": [round(float(np.percentile(v, q)), 3) for q in (2.5, 97.5)]}
                        for k, v in diffs.items()}
    if "LV" in preds:
        TRIALS.append("WF encompassing y ~ LV + combo_oos")
        enc = sm.OLS(o.y, o[["LV", "combo"]]).fit(
            cov_type="cluster", cov_kwds={"groups": o.edition.astype(str)})
        out["oos_encompassing"] = {"coef": enc.params.round(3).to_dict(),
                                   "t_cl": enc.tvalues.round(2).to_dict()}
    return out


def table(results: list[dict], cols: list[str]) -> str:
    head = "| # | n | " + " | ".join(cols) + " | SE | R² | %right |"
    lines = [head, "|" + "---|" * (len(cols) + 5)]
    for i, r in enumerate(results, 1):
        cells = [f"{r['coef'][c]:.3f} ({r['t'][c]:.2f}; {r['t_cl'][c]:.2f})" if c in r["coef"]
                 else "" for c in cols]
        lines.append(f"| {i} | {r['n']} | " + " | ".join(cells)
                     + f" | {r['se_reg']} | {r['r2']} | {r['right']} |")
    return "\n".join(lines)


def ranking(con, side: pd.DataFrame, season: int, res: dict, top: int = 25) -> pd.DataFrame:
    """Table A: rank every team on the last pre-bowl edition by regression-9 weights (no H)."""
    # stg.games has no bowls before ~2002, so fall back to the last edition of the calendar year
    last = con.execute(
        "select max(date) from stg.massey_editions where season = ? and year(date) = ? and "
        "date < coalesce((select min(cast(timezone('America/New_York', startDate) as date)) "
        "from stg.games where season = ? and seasonType = 'postseason' "
        "and homeClassification = 'fbs'), date '9999-01-01')",
        [season, season, season]).fetchone()[0]
    t = side.xs(pd.Timestamp(last), level="edition").copy()
    w = {k: v for k, v in res["coef"].items() if k != "h"}
    t["V"] = sum(v * (100 * t.wpct if k == "REC" else -100 * t[k] / t.n_teams)
                 for k, v in w.items())
    t = t.sort_values("V", ascending=False).head(top)
    return t[["wins", "losses", *[k for k in w if k != "REC"]]].astype("Int64").assign(
        edition=str(last))


def run_era(con, era: str, boot: int) -> dict:
    lo, hi = ERAS[era]
    d, side = load(con, lo, hi)
    cover = {s: round(float(d[s].notna().mean()), 3) for s in PAPER_SYSTEMS}
    core = [s for s in PAPER_SYSTEMS if cover[s] >= CORE_COVERAGE] + ["REC"]
    extra3 = [s for s in ("AND",) if s not in core and cover[s] > 0]
    extra4 = [s for s in PAPER_SYSTEMS if s not in core + extra3 and cover[s] > 0]
    out = {"era": era, "seasons": [lo, hi], "games_with_editions": len(d), "coverage": cover,
           "core": core, "no_lookahead": check_no_lookahead(con, d)}

    t2 = d.dropna(subset=core)
    out["table1_corr"] = t2[core].corr().round(3).to_dict()
    singles = [fit(t2, ["h", k], f"{era} T2 {k}") for k in core]
    reg8 = fit(t2, ["h", *core], f"{era} T2 all")
    keep = select_systems(reg8, core)
    reg9 = fit(t2, ["h", *keep], f"{era} T2 reg9")
    out["table2"] = singles + [reg8, reg9]
    out["reg9_systems"] = keep
    out["stability"] = chow(t2, ["h", *keep])
    for name, add in (("table3", extra3), ("table4", extra3 + extra4)):
        if add:
            cols = core + add
            sub = d.dropna(subset=cols)
            full = fit(sub, ["h", *cols], f"{era} {name} all")
            out[name] = [full, fit(sub, ["h", *select_systems(full, cols)], f"{era} {name} drop")]
    lv = t2.dropna(subset=["LV"])
    if len(lv) > 0.9 * len(t2):
        out["lv_coverage"] = round(len(lv) / len(t2), 3)
        out["table5"] = market_test(lv, ["h", *keep], f"{era} T5 reg9+LV")
        out["lv_alone"] = fit(lv, ["LV", "h"], f"{era} LV+H")
        out["lv_each_single"] = {k: market_test(lv, ["h", k], f"{era} T5 {k}+LV") for k in core}
    out["walk_forward"] = walk_forward(lv if "table5" in out else t2, core,
                                       min_train=3 if era == "modern" else 1, boot=boot)
    out["tableA"] = ranking(con, side, hi, reg9).reset_index().to_dict("records")
    return out


def clean(x):
    """Drop the private statsmodels handles (keys starting '_') before writing JSON."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def report(o: dict) -> None:
    print(f"\n## Era {o['era']} {o['seasons'][0]}-{o['seasons'][1]}  "
          f"({o['games_with_editions']} games with an edition)")
    print("coverage:", o["coverage"])
    print("no-lookahead:", o["no_lookahead"])
    print("\n### Table 1 (correlations)\n")
    print(pd.DataFrame(o["table1_corr"]).to_string())
    print("\n### Table 2  coef (t OLS; t clustered by edition)\n")
    print(table(o["table2"], ["h", *o["core"]]))
    print("\nstability:", o["stability"])
    for name in ("table3", "table4"):
        if name in o:
            print(f"\n### {name}\n")
            print(table(o[name], ["h", *o[name][0]["cols"][1:]]))
    if "table5" in o:
        t5 = o["table5"]
        print(f"\n### Table 5 (LV coverage {o['lv_coverage']})\n")
        print(table([o["lv_alone"], t5], ["LV", "h", *o["reg9_systems"]]))
        print(f"\nF(others=0) = {t5['F_others']} df {t5['df']} p={t5['F_others_p']} "
              f"(clustered p={t5['F_others_cl_p']}); t(LV=1) = {t5['t_LV_eq_1']}")
        print("single + LV:", {k: (v["coef"]["LV"], v["coef"][k], v["t_cl"][k])
                                for k, v in o["lv_each_single"].items()})
    print("\n### Walk-forward\n")
    print(json.dumps(o["walk_forward"], indent=1, default=str))
    print("\n### Table A (top 25)\n")
    print(pd.DataFrame(o["tableA"]).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--era", choices=[*ERAS, "all"], default="all")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    con = duckdb.connect(str(DATA_ROOT / "cfb.duckdb"), read_only=True)
    res = [run_era(con, e, a.boot) for e in (ERAS if a.era == "all" else [a.era])]
    for o in res:
        report(o)
    print(f"\ntrial count: {len(TRIALS)} regressions")
    path = DATA_ROOT / "processed" / "fair_oster_massey.json"
    path.write_text(json.dumps({"eras": clean(res), "trials": TRIALS}, indent=1, default=str))
    print("wrote", path)


if __name__ == "__main__":
    main()
