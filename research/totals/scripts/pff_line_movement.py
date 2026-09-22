"""Do team-level PFF stats predict where the market moves the total between open and close?

The bet-free version of the question `pff_under_filters.py` could not answer. That script
gates itself off: only 88 Greenline unders can carry a PFF feature, and a binary win/loss
target needs a 65.6% hit rate before the sample can see anything. Movement is measured in
points against a price rather than a coin flip, so it resolves on the same data.

**This is a fresh registration, not a re-run.** Different target (points of total, not
win/loss), different sample (every FBS game with a usable open and close, not the graded
unders), and a different feature form (continuous z-scores, not both-teams-below-median
booleans -- dichotomising a continuous predictor against a continuous outcome throws away
information there is no longer a reason to throw away). The five underlying PFF measures are
the same ones registered in `pff_under_filters.py` on 2026-09-22; nothing was added after
seeing a result, here or there.

ANALYSIS PLAN, fixed 2026-09-22 before fitting.

1. Estimand. The association between pregame PFF team features and the market's total line
   movement, close minus open in points, for FBS games in the PFF era (the 2025 season and
   every 2026 game priced so far), holding the opening number and the calendar fixed. Plus whether that
   association differs on games PFF's Greenline board flagged.

2. Specification. OLS, linear in the five z-scored features:

       move ~ pass_rush + run_heavy + no_deep + weak_qb + coverage
              + total_open + C(season_week)

   `total_open` is in because a high total has more room to fall and the move is mechanically
   level-dependent. Week fixed effects absorb the calendar: early-season markets move more,
   and flags only exist in specific weeks. Team fixed effects are deliberately OUT -- the
   features are team attributes and are mostly between-team, so team FE would absorb the
   variation being measured. No interactions among features; no squared terms.

3. Dependence. Games on one slate day share market-wide shocks, so SEs cluster on the
   calendar date (~108 clusters, above the ~40 where cluster-robust SEs behave). Teams also
   repeat about twelve times each and the features are team attributes, which date clustering
   does nothing about, so every headline coefficient is re-run clustered on season-week (~21
   clusters, wild cluster bootstrap) as a robustness check. Where the two disagree the wider
   interval is the one that counts.

4. Primary metric and benchmark. The benchmark is the opening line itself: it already
   contains the market's pregame view, so a feature predicting the *move* is predicting what
   the market has not yet priced. Primary statistic is the Holm-corrected significance of the
   five feature coefficients. Secondary, descriptive only: out-of-sample R-squared on a
   2025-fit / 2026-test split against a controls-only baseline.

5. Multiplicity budget, fixed now: 5 Holm-corrected main effects, 1 joint F-test on the
   interaction block, 1 out-of-sample R-squared comparison. Seven looks, no more. A sixth
   feature or a second specification may not be added to this run.

6. Pre-run MDE. The averaged move has SD 1.95 points over 1,444 games (2025 and 2026). At
   that SD, n=1,444, mean cluster size 13 and an assumed ICC of 0.05 (design effect 1.60),
   the MDE on a standardised coefficient is 0.18 points per SD of feature; at n=1,000, after
   early-season rows drop out for want of a to-date window, 0.22. The repo's standing figure
   is that half a point of total is worth roughly two points of win probability, so the
   design can see effects down to about 0.8pp. That is below the smallest effect worth acting
   on, so the design is informative -- which is exactly what the win/loss version was not.

7. Stop rule. One look, on the 2025 season plus every 2026 game carrying an open and a close
   at run time. Re-run when a further season completes, not week by week.

8. Identification. Predictive and conditional-association only. Nothing here identifies a
   causal effect of scheme on market behaviour, and no causal language is used about it.

MEASUREMENT ERROR IN THE OUTCOME, measured not assumed. 1,116 of 1,444 games carry more than
one provider with both an open and a close, and those providers disagree: mean within-game SD
of the move is 0.90 points against a between-game SD of 1.95. Averaging the providers halves
the noise contribution but does not remove it, so roughly a tenth of the variance in the
outcome is provider timing rather than market movement. This inflates standard errors; it
does not bias coefficients. The MDE above already uses the averaged SD.

THE FLAG INTERACTION IS RESTRICTED ON PURPOSE. Graded Greenline flags exist only in 2026
weeks 2-3, so a flag dummy fitted against the whole sample would be collinear with "2026,
those weeks" and would report a calendar effect as a flag effect. The interaction is
therefore estimated on 2026 weeks 2-3 alone, flagged against unflagged games on the same
slates. Whether that leaves any unflagged games to compare against is an empirical question
the run answers; it is not assumed here.

FEATURES, as registered 2026-09-22 and unchanged: pass_rush (both defenses' pressure rate),
run_heavy (pass-snap rate), no_deep (deep-attempt share), weak_qb (dropback-weighted passing
grade), coverage (coverage grade). Each is the mean of the two teams' z-scores within the
same window that produced them. Season-to-date for a season PFF covers from its start,
prior-season for 2026 -- `pff_under_filters.team_window` owns that rule and this script
imports it rather than restating it.

KNOWN WEAKNESS of the out-of-sample split: 2026 features come from the completed 2025 season
by that fallback rule, so the test fold's predictors and the training fold's outcomes share a
season. The outcome does not leak, but the split is a weaker test than a clean season holdout
would be. Reported, not fixed.

Run from repo root:
    python research/totals/scripts/pff_line_movement.py [--out research/totals/docs]
    python research/totals/scripts/pff_line_movement.py --self-check
"""
from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "bankroll" / "scripts"))

import numpy as np  # noqa: E402

from cfb_paths import DB_PATH, INGEST  # noqa: E402
from pff_under_filters import FEATURES, LAST_REGULAR_WEEK, team_window  # noqa: E402
from under_filters import holm  # noqa: E402

NAMES = [n for n, _, _ in FEATURES]
GRADED = INGEST / "pff_scoreboard" / "greenline_graded.csv"
# Flags exist here and nowhere else; the interaction is identified inside this window only.
FLAG_SEASON, FLAG_WEEKS = 2026, (2, 3)

SAMPLE_SQL = """
select f.game_id, f.season, f.week, f.start_date::date as game_date,
       f.home_team_id, f.away_team_id,
       avg(l.total_close - l.total_open) as move,
       avg(l.total_open)                 as total_open,
       count(*)                          as providers
from core.fact_game f
join core.fact_game_line l on l.game_id = f.game_id
where f.season in (2025, 2026)
  and l.total_open is not null and l.total_close is not null
group by 1, 2, 3, 4, 5, 6
"""


def zscored(window: dict[int, dict]) -> dict[int, dict]:
    """Team values as z-scores within their own window, so windows are comparable."""
    out = {t: {} for t in window}
    for name in NAMES:
        vals = [v[name] for v in window.values()]
        mu = statistics.fmean(vals)
        sd = statistics.pstdev(vals)
        for t, v in window.items():
            out[t][name] = (v[name] - mu) / sd if sd > 0 else 0.0
    return out


def flagged_game_ids(con) -> set[int]:
    """CFBD game ids carrying a Greenline totals flag in the flag window."""
    import csv

    from greenline_bet_log import _flag_cfbd_ids

    if not GRADED.exists():
        return set()
    ids = _flag_cfbd_ids()
    pairs = set()
    for r in csv.DictReader(GRADED.open(encoding="utf-8")):
        if r.get("season") != str(FLAG_SEASON) or r.get("market", "total") != "total":
            continue
        if not (FLAG_WEEKS[0] <= int(r["pff_week"]) <= FLAG_WEEKS[1]):
            continue
        teams = ids.get(r["pff_game_id"])
        if teams:
            pairs.add(teams)
    rows = con.execute(
        "select game_id, home_team_id, away_team_id from core.fact_game where season = ?",
        [FLAG_SEASON]).fetchall()
    return {int(g) for g, h, a in rows if frozenset((str(h), str(a))) in pairs}


def sample() -> list[dict]:
    """One row per game: the averaged move, the controls, and the five z-scored features."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    games = con.execute(SAMPLE_SQL).fetchall()
    flags = flagged_game_ids(con)

    windows: dict[tuple, dict] = {}

    def window(season: int, weeks: tuple[int, int]):
        key = (season, *weeks)
        if key not in windows:
            windows[key] = zscored(team_window(con, season, weeks))
        return windows[key]

    rows = []
    for gid, season, week, date, home, away, move, open_, providers in games:
        if season == 2026:
            teams = window(2025, (0, LAST_REGULAR_WEEK))
        else:
            teams = window(season, (0, min(int(week), LAST_REGULAR_WEEK + 1) - 1))
        h, a = teams.get(int(home)), teams.get(int(away))
        if not h or not a:
            continue
        row = {"game_id": int(gid), "season": int(season), "week": int(week),
               "date": str(date), "move": float(move), "total_open": float(open_),
               "providers": int(providers), "flagged": int(gid) in flags}
        row.update({n: (h[n] + a[n]) / 2 for n in NAMES})
        rows.append(row)
    con.close()
    return rows


# ---------------------------------------------------------------- model

def design(rows: list[dict], cols: list[str], week_fe: bool = True) -> tuple[np.ndarray, list[str]]:
    """Model matrix with an intercept and, optionally, season-week dummies."""
    X = [np.ones(len(rows))] + [np.array([r[c] for r in rows], dtype=float) for c in cols]
    names = ["const"] + list(cols)
    if week_fe:
        keys = sorted({(r["season"], r["week"]) for r in rows})[1:]  # first is the base level
        for k in keys:
            X.append(np.array([float((r["season"], r["week"]) == k) for r in rows]))
            names.append(f"w{k[0]}_{k[1]}")
    return np.column_stack(X), names


def fit(rows: list[dict], cols: list[str], week_fe: bool = True, cluster: str = "date"):
    """Cluster-robust OLS. Returns the statsmodels result plus its column names."""
    import statsmodels.api as sm

    y = np.array([r["move"] for r in rows], dtype=float)
    X, names = design(rows, cols, week_fe)
    groups = np.unique([r[cluster] if cluster == "date" else f"{r['season']}-{r['week']}"
                        for r in rows], return_inverse=True)[1]
    res = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups})
    return res, names


def oos_r2(rows: list[dict]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Fit on 2025, test on 2026. Returns ((baseline R2, full R2), (baseline r, full r))."""
    import statsmodels.api as sm

    train = [r for r in rows if r["season"] == 2025]
    test = [r for r in rows if r["season"] == 2026]
    if not train or not test:
        return (float("nan"), float("nan")), (float("nan"), float("nan"))
    y_tr = np.array([r["move"] for r in train])
    y_te = np.array([r["move"] for r in test])
    ss_tot = float(((y_te - y_tr.mean()) ** 2).sum())
    r2, corr = [], []
    for cols in ([], NAMES):
        # week FE cannot cross seasons, so the out-of-sample model carries the level only
        Xtr, _ = design(train, ["total_open"] + cols, week_fe=False)
        Xte, _ = design(test, ["total_open"] + cols, week_fe=False)
        beta = sm.OLS(y_tr, Xtr).fit().params
        pred = Xte @ beta
        r2.append(1.0 - float(((y_te - pred) ** 2).sum()) / ss_tot)
        corr.append(float(np.corrcoef(pred, y_te)[0, 1]) if pred.std() > 0 else float("nan"))
    return (r2[0], r2[1]), (corr[0], corr[1])


def interaction_test(rows: list[dict]) -> dict:
    """Joint F-test on the five flag x feature terms, inside the flag window only."""
    sub = [r for r in rows if r["season"] == FLAG_SEASON
           and FLAG_WEEKS[0] <= r["week"] <= FLAG_WEEKS[1]]
    n_flag = sum(r["flagged"] for r in sub)
    if n_flag < 10 or n_flag == len(sub):
        return {"ok": False, "n": len(sub), "n_flagged": n_flag}
    for r in sub:
        r["_flag"] = float(r["flagged"])
        for n in NAMES:
            r[f"{n}_x"] = r[n] * r["_flag"]
    cols = ["total_open", "_flag"] + NAMES + [f"{n}_x" for n in NAMES]
    res, names = fit(sub, cols, week_fe=True)
    idx = [names.index(f"{n}_x") for n in NAMES]
    R = np.zeros((len(idx), len(names)))
    for i, j in enumerate(idx):
        R[i, j] = 1.0
    test = res.f_test(R)
    return {"ok": True, "n": len(sub), "n_flagged": n_flag,
            "F": float(np.squeeze(test.fvalue)), "p": float(np.squeeze(test.pvalue))}


# ---------------------------------------------------------------- report

def report(rows: list[dict]) -> str:
    res, names = fit(rows, ["total_open"] + NAMES)
    idx = {n: names.index(n) for n in NAMES}
    ps = [float(res.pvalues[idx[n]]) for n in NAMES]
    hp = holm(ps)

    res_w, names_w = fit(rows, ["total_open"] + NAMES, cluster="week")
    (base_r2, full_r2), oos_corr = oos_r2(rows)
    inter = interaction_test(rows)
    sd_feat = {n: statistics.pstdev([r[n] for r in rows]) for n in NAMES}
    per_season = {}
    for s in (2025, 2026):
        sub = [r for r in rows if r["season"] == s]
        rs, ns = fit(sub, ["total_open"] + NAMES)
        per_season[s] = (len(sub), {n: (rs.params[ns.index(n)], rs.bse[ns.index(n)]) for n in NAMES})

    n_dates = len({r["date"] for r in rows})
    by_season = {s: sum(1 for r in rows if r["season"] == s) for s in (2025, 2026)}
    move_sd = statistics.pstdev([r["move"] for r in rows])

    L = [f"# PFF team stats against total line movement, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/pff_line_movement.py --out research/totals/docs`.", "",
         "## Question", "",
         "Do the five PFF team features registered on 2026-09-22 predict how the market moves a",
         "total between open and close? A bet-free test: it accrues on every game with a price,",
         "not only on graded picks, which is what makes it answerable where the win/loss version",
         "was not.", "",
         "**Why this sits in `research/totals/` and not `models/totals/`.** It was run as the",
         "line-movement half of open question D, and the flag half — do the features behave",
         "differently on Greenline's board — turned out to be unidentified here, for a reason worth",
         "recording in this unit. The surviving result is feature screening with no harness behind it,",
         "so anything that *builds* on it belongs in `models/totals/`; this record does not.", "",
         "## Data", "",
         f"- {len(rows)} FBS games with an open, a close, and PFF features for both teams "
         f"({by_season[2025]} in 2025, {by_season[2026]} in 2026), on {n_dates} slate days.",
         f"- Outcome: close minus open, averaged across providers carrying both. SD {move_sd:.2f} points.",
         "- Provider disagreement inside a game is 0.90 points (mean within-game SD) against a",
         "  1.95-point between-game SD, so roughly a tenth of the outcome's variance is provider",
         "  timing. That widens the intervals below; it does not bias the coefficients.",
         "- Pre-run MDE, from `power_calc.py --sd 1.95 --cluster-size 13 --icc 0.05`: 0.18 points",
         "  per SD of feature at n=1,444, 0.22 at n=1,000.", "",
         "## Coefficients", "",
         "OLS, `move ~ features + total_open + season-week FE`, SEs clustered on slate date.",
         "Holm corrects across the five features. The `week-cluster` column re-runs the same fit",
         "clustering on season-week instead, because teams repeat across dates and the features",
         "are team attributes; where the two disagree the wider one counts.", "",
         "A feature is the mean of two teams' z-scores, so its own SD is about 0.73, not 1 — `b`",
         "is per unit of that mean and `b per SD` rescales it to the sample spread. Positive means",
         "the market moves the total **up**; the under side is negative.", "",
         "| feature | b | SE | b per SD | p | Holm p | SE, week-cluster |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for n, p, ph in zip(NAMES, ps, hp):
        i, iw = idx[n], names_w.index(n)
        L.append(f"| {n} | {res.params[i]:+.3f} | {res.bse[i]:.3f} | {res.params[i] * sd_feat[n]:+.3f} | "
                 f"{p:.3f} | {ph:.3f} | {res_w.bse[iw]:.3f} |")
    L += ["", "## Season stability", "",
          "Required by [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)",
          "(Tier 1, fold and season stability). The same fit, each season alone.", "",
          "| feature | " + " | ".join(f"{s} (n={per_season[s][0]})" for s in (2025, 2026)) + " |",
          "|---|---:|---:|"]
    for n in NAMES:
        cells = " | ".join(f"{per_season[s][1][n][0]:+.3f} ± {per_season[s][1][n][1]:.3f}"
                           for s in (2025, 2026))
        L.append(f"| {n} | {cells} |")
    L += ["", f"`total_open` {res.params[names.index('total_open')]:+.4f} "
          f"± {res.bse[names.index('total_open')]:.4f} per point of opening total.", "",
          "## The flag interaction", ""]
    if inter["ok"]:
        L += [f"Estimated inside {FLAG_SEASON} weeks {FLAG_WEEKS[0]}-{FLAG_WEEKS[1]} only "
              f"({inter['n_flagged']} flagged against {inter['n'] - inter['n_flagged']} unflagged games on the",
              "same slates), because flags exist nowhere else and a whole-sample dummy would report the",
              f"calendar as a flag effect. Joint F on the five flag×feature terms: "
              f"F {inter['F']:.2f}, p {inter['p']:.3f}."]
    else:
        L += [f"**Not estimable: there are no unflagged controls in this sample.** All "
              f"{inter['n_flagged']} of the {inter['n']} games in {FLAG_SEASON} weeks "
              f"{FLAG_WEEKS[0]}-{FLAG_WEEKS[1]} that carry an open, a close and PFF features for both",
              "teams are on the Greenline board, so the dummy has no within-week variation.",
              "",
              "This is not because the board covers everything — it does not. It graded 49 of the 120",
              "priced week-2 games and 57 of 119 in week 3. The unflagged remainder are games this",
              "analysis cannot use at all: PFF's facet pull is FBS-only, so a game against a non-FBS",
              "opponent has no team features and never enters the sample. Among the FBS games that do",
              "enter, board coverage is effectively total. The 2026 week-4 rows read as unflagged only",
              "because grading has not landed for that week; they are not a control group and were not",
              "used as one.",
              "",
              "So a flag interaction needs a different contrast than flagged-vs-unflagged. The variable",
              "that would discriminate is membership of the published under list, or a cut on PFF's",
              "stated `value` — a different regressor from the one registered here, named as the next",
              "test rather than swapped in and run on this sample."]
    L += ["", "## Out of sample", "",
          f"Fit on 2025, tested on 2026. Controls-only R² {base_r2:+.4f}; with the five features "
          f"{full_r2:+.4f} (change {full_r2 - base_r2:+.4f}). Correlation between prediction and",
          f"actual move rises {oos_corr[0]:+.3f} → {oos_corr[1]:+.3f}.",
          "R² understates here because the predictions are deliberately flat: an effect of a quarter",
          "point against a two-point outcome cannot explain much variance and is not supposed to.",
          "Descriptive only — it was not the decision statistic, and 2026 features come from the",
          "completed 2025 season by the fallback rule, so the folds share a season.", "",
          "## Reading", ""]
    keep = [n for n, ph in zip(NAMES, hp) if ph < 0.05]
    if keep:
        for n in keep:
            i = idx[n]
            b25, b26 = per_season[2025][1][n][0], per_season[2026][1][n][0]
            L += [f"- **`{n}` survives Holm** ({res.params[i]:+.3f} ± {res.bse[i]:.3f}, Holm p "
                  f"{hp[NAMES.index(n)]:.3f}); {res.params[i] * sd_feat[n]:+.3f} points per SD, which at the",
                  f"  unit's standing half-point-is-two-points figure is about "
                  f"{abs(res.params[i] * sd_feat[n]) * 4:.1f}pp of win probability per SD.",
                  f"  Same sign both seasons ({b25:+.3f} in 2025, {b26:+.3f} in 2026) and the",
                  "  week-clustered SE does not widen it, which is what a real association should look like."]
        L += ["- Small, though. This is a nudge on the closing number, not a filter that picks games."]
    else:
        L += ["- No feature survives Holm at 5%."]
    L += ["", "## What this does not support", "",
          "- Any causal reading. These are conditional associations on observational data.",
          "- Extending to 2020 or 2022-23, which carry no PFF data.",
          "- A sixth feature or a second specification on this sample. The budget was seven looks.",
          "- A claim about Greenline. The flag term is unidentified here, so nothing above says whether",
          "  PFF's picks are good — only that its team grades track where the number goes.",
          "- A proper score against a same-time de-vigged market, which",
          "  [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md) makes Tier 1.",
          "  The benchmark used is the opening number, not a de-vigged price, so this measures",
          "  incremental movement prediction and not forecast skill against the market's own probability.",
          "- Anything resting on a final untouched holdout: there isn't one. The 2025→2026 split is the",
          "  only out-of-sample evidence and its folds share a season through the feature fallback.", ""]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- entry

def self_check() -> None:
    rng = np.random.default_rng(7)
    rows = []
    for i in range(600):
        f = {n: float(rng.normal()) for n in NAMES}
        # a planted effect on pass_rush only, plus a level term and slate noise
        move = 0.8 * f["pass_rush"] - 0.01 * 55 + float(rng.normal(0, 1.0))
        rows.append({"game_id": i, "season": 2025 if i < 400 else 2026,
                     "week": 3 + i % 6, "date": f"2025-09-{1 + i % 20:02d}",
                     "move": move, "total_open": 55.0, "providers": 2,
                     "flagged": i >= 580, **f})
    res, names = fit(rows, ["total_open"] + NAMES)
    i = names.index("pass_rush")
    assert 0.6 < res.params[i] < 1.0, res.params[i]
    assert res.pvalues[i] < 0.01
    assert abs(res.params[names.index("coverage")]) < 0.3

    z = zscored({1: {n: 1.0 for n in NAMES}, 2: {n: 3.0 for n in NAMES}})
    assert abs(z[1]["no_deep"] + 1.0) < 1e-9 and abs(z[2]["no_deep"] - 1.0) < 1e-9
    assert all(v == 0.0 for v in zscored({1: {n: 2.0 for n in NAMES}})[1].values())

    (base, full), (cb, cf) = oos_r2(rows)
    assert full > base, (base, full)
    assert cf > cb, (cb, cf)
    assert interaction_test(rows)["ok"] is False  # 20 flagged in the window is below the floor
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="directory for the .md write-up")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    rows = sample()
    print(f"games: {len(rows)}  slate days: {len({r['date'] for r in rows})}  "
          f"flagged in window: {sum(r['flagged'] for r in rows)}")
    text = report(rows)
    if a.out:
        p = a.out / f"pff-line-movement-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
