"""Does any of PT's ~150 individual model columns beat the closing line against the spread?

EXPLORATORY. Not registered in `prereg-line-movement.md`. Fourth of the PT-column studies.

DIFFERENT ESTIMAND FROM THE ARCHIVE. Amendments A2 and A6 tested these same columns against the
MOVEMENT target -- do they anticipate where the line goes from the opener. This asks the
separate question the last three studies asked of PT's summary columns: bet the side a model
disagrees with the CLOSING line on, does it clear the -110 break-even. Neither answers the
other; this does not re-litigate A2/A6.

Unlike phcover / phwin / linestd, the model columns are NOT rescalings of the market -- R^2 of
each model on `line` has a median of 0.82 and a minimum of 0.31, so they carry real independent
variation. That is why this sweep is worth running and those were not.

SCREEN, DECLARED BEFORE SCORING: a model is tested only with >= MIN_GAMES graded predictions and
>= MIN_SEASONS seasons. Coverage in this panel is not missing-at-random -- some models publish on
a handful of games (`linemaxy` has 50) and a self-selected slate produces a cover rate not
comparable to a model that prices everything. The floor is set here, not after seeing results.

TWO READS, in the order that decides it:

  WALK-FORWARD  The only one a bettor could have acted on. For each season, rank models by
                `base.prior_skill` over STRICTLY PRIOR seasons, take the best, bet its side all
                season. One number, no multiplicity. NOTE: selection is by prior MARGIN skill
                (what prior_skill measures); grading is ATS against the close. Stated because a
                reader would otherwise assume they match.

  LEADERBOARD   Every model's in-sample ATS with season-cluster inference and Benjamini-Hochberg
                q-values across the whole family. Context for the walk-forward, not a result:
                with ~120 models the best in-sample number is high by construction.

Side convention: a model's column is a spread in the archive's negated sign, so the model
favours HOME iff `model < line`. Pushes (`y + line == 0`) are dropped.

    python research/spread/scripts/eval_model_columns_ats.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "model_columns_ats.json"
BREAKEVEN = 110 / 210
MIN_GAMES = 1000          # declared screen, not tuned
MIN_SEASONS = base.MIN_CLUSTERS


def season_cluster_test(won, seasons):
    """Per-season cover rates, then a one-sample t-test of those means against break-even.
    Seasons are the cluster; this is the same unit the rest of the tree clusters on."""
    per = pd.Series(won).groupby(seasons).mean()
    if len(per) < MIN_SEASONS:
        return None
    t, p = stats.ttest_1samp(per.to_numpy(), BREAKEVEN)
    se = per.std(ddof=1) / np.sqrt(len(per))
    crit = stats.t.ppf(0.975, len(per) - 1)
    return {"ats": float(np.mean(won)), "ats_season_mean": float(per.mean()),
            "lo": float(per.mean() - crit * se), "hi": float(per.mean() + crit * se),
            "seasons": int(len(per)), "t": float(t), "p": float(p)}


def sides(model_col, line):
    """True where the model favours the home side (model spread below the market's)."""
    return model_col < line


def main() -> int:
    df, models = base.load()
    testable = [c for c in models if c not in base.MARKET_LINES]
    d = df[df.line.notna()].copy()
    d = d[(d.y + d.line) != 0].copy()                      # drop pushes
    d["cover"] = (d.y + d.line > 0).astype(int)            # 1 = HOME covers
    line = d.line.to_numpy(float)
    cover = d.cover.to_numpy(int)
    seasons = d.season.to_numpy(int)

    print(f"{len(d)} graded games, {int(d.season.min())}-{int(d.season.max())}, pushes dropped")
    print(f"{len(testable)} model columns after excluding MARKET_LINES {sorted(base.MARKET_LINES)}")
    print(f"screen: >= {MIN_GAMES} graded predictions and >= {MIN_SEASONS} seasons")

    rows = []
    for c in testable:
        v = d[c].to_numpy(float)
        ok = np.isfinite(v)
        if ok.sum() < MIN_GAMES:
            continue
        won = np.where(sides(v[ok], line[ok]), cover[ok], 1 - cover[ok]).astype(float)
        r = season_cluster_test(won, seasons[ok])
        if r is None:
            continue
        r["model"] = c
        r["n"] = int(ok.sum())
        rows.append(r)

    lb = pd.DataFrame(rows)
    lb["q"] = base.bh_qvalues(lb.p.to_numpy())
    lb = lb.sort_values("ats_season_mean", ascending=False).reset_index(drop=True)
    print(f"{len(lb)} models pass the screen")

    print("")
    print("WALK-FORWARD -- pick the best model on prior seasons, bet it the next season")
    screened = set(lb.model)
    picks, wf_won, wf_seasons = [], [], []
    for s in sorted(d.season.unique()):
        prior = d[d.season < s]
        if prior.season.nunique() < MIN_SEASONS:
            continue
        skill = base.prior_skill(prior, testable, "line", upto=s - 1)
        eligible = {m: v for m, v in skill.items() if m in screened}
        if not eligible:
            continue
        best = min(eligible, key=eligible.get)               # lower dMSE is better
        cur = d[d.season == s]
        v = cur[best].to_numpy(float)
        ok = np.isfinite(v)
        if ok.sum() < 50:
            continue
        w = np.where(sides(v[ok], cur.line.to_numpy(float)[ok]),
                     cur.cover.to_numpy(int)[ok], 1 - cur.cover.to_numpy(int)[ok]).astype(float)
        picks.append({"season": int(s), "model": best, "n": int(ok.sum()), "ats": float(w.mean())})
        wf_won.append(w)
        wf_seasons.append(np.full(int(ok.sum()), s))
        print(f"  {int(s)}  picked {best:16s} n {int(ok.sum()):4d}  ATS {w.mean():.4f}")

    out = {"n_graded": len(d), "seasons": [int(d.season.min()), int(d.season.max())],
           "n_models_screened": len(lb), "min_games": MIN_GAMES, "breakeven": BREAKEVEN,
           "walk_forward_picks": picks}
    if wf_won:
        w_all = np.concatenate(wf_won)
        r = season_cluster_test(w_all, np.concatenate(wf_seasons))
        out["walk_forward"] = r
        above = sum(1 for p_ in picks if p_["ats"] > BREAKEVEN)
        out["walk_forward_seasons_above_breakeven"] = above
        print(f"  pooled: {len(w_all)} bets, ATS {r['ats']:.4f}, season-mean "
              f"{r['ats_season_mean']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}] "
              f"over {r['seasons']} seasons, p {r['p']:.3f} vs {BREAKEVEN:.4f}")
        print(f"  seasons above break-even: {above} of {len(picks)}")

    print("")
    print("LEADERBOARD (in-sample; context, not a result) -- top 10 by season-mean ATS")
    print(f"  {'model':17s} {'n':>6s} {'ATS':>7s} {'season mean':>12s} {'95% CI':>18s} {'p':>7s} {'q':>7s}")
    for _, r in lb.head(10).iterrows():
        print(f"  {r.model:17s} {int(r.n):6d} {r.ats:7.4f} {r.ats_season_mean:12.4f} "
              f"  [{r.lo:.4f},{r.hi:.4f}] {r.p:7.3f} {r.q:7.3f}")
    print(f"  models with q < 0.10: {int((lb.q < 0.10).sum())} of {len(lb)}")
    print(f"  models whose CI lower bound clears {BREAKEVEN:.4f}: {int((lb.lo > BREAKEVEN).sum())}")
    out["leaderboard"] = lb.to_dict("records")
    out["n_q_below_10pct"] = int((lb.q < 0.10).sum())
    out["n_ci_clears_breakeven"] = int((lb.lo > BREAKEVEN).sum())

    # POWER. "Zero models clear break-even" is only half the picture: the other half is how
    # many had enough precision for a real edge to have shown up. A model whose interval spans
    # break-even has not been cleared OR convicted.
    print("")
    print("POWER -- what could these tests have detected?")
    se = (lb.hi - lb.lo) / 3.92
    mde = 2.8 * se
    cant_exclude = int((lb.hi > BREAKEVEN).sum())
    excluded = int((lb.hi <= BREAKEVEN).sum())
    print(f"  per model: median SE {se.median():.4f}, median MDE at 80% power {mde.median():.4f}")
    print(f"  CI lower bound above break-even (a proven winner): {int((lb.lo > BREAKEVEN).sum())}")
    print(f"  CI upper bound above break-even (an edge NOT excluded): {cant_exclude} of {len(lb)}")
    print(f"  CI entirely below break-even (an edge excluded): {excluded} of {len(lb)}")
    print("  So the sweep convicts two thirds of the family and leaves the rest unresolved --")
    print("  it does not prove every model is worthless, only that none is demonstrably good.")
    pw = {"median_se": float(se.median()), "median_mde_80": float(mde.median()),
          "n_proven_winner": int((lb.lo > BREAKEVEN).sum()),
          "n_edge_not_excluded": cant_exclude, "n_edge_excluded": excluded}
    if wf_won:
        se_wf = (out["walk_forward"]["hi"] - out["walk_forward"]["lo"]) / 3.92
        gap = BREAKEVEN - out["walk_forward"]["ats_season_mean"]
        pw["se_walk_forward"] = float(se_wf)
        pw["mde_walk_forward_80"] = float(2.8 * se_wf)
        pw["gap_to_breakeven_in_mde"] = float(gap / (2.8 * se_wf))
        print(f"  walk-forward: SE {se_wf:.5f}, MDE {2.8 * se_wf:.4f}; the gap to break-even is "
              f"{gap:+.4f}, {gap / (2.8 * se_wf):.1f}x the MDE -- well powered.")
    out["power"] = pw

    OUT.write_text(json.dumps(out, indent=2))
    print("")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
