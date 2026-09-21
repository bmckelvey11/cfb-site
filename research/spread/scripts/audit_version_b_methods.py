"""Methods audit of the pred-tracker-model's version B forward test.

Reproduces every number in `research/spread/docs/methods-review-2026-09-21.md` that
`eval_version_b.py` does not itself print. Read-only: it grades nothing, writes nothing to
the forward log, and issues no verdict. The confirmatory hypothesis remains B4's registered
E4 slope under amendment B3's stopping rule.

Six checks, in the order the review reports them:

  1  anchor realization -- how many graded games are anchored on a capture that actually
     falls on Monday ET, by week (the prereg calls this quantity "Monday's line")
  2  regressor composition -- how much of x = E4 - line_anchor is the market's own move
     since the opener, reversed
  3  target distribution -- sd(y), the share of games whose line never moved, and what that
     does to B5's `beat_close` statistic
  4  selection -- played games that fail to grade against an Action Network close
  5  B2 coverage -- how many distinct games and weeks survive the fixed game set
  6  training-set leakage -- whether the archive `weekly_slate.py` fits on carries any rows
     from the live season, which would put the graded games inside their own screen

  7  decomposition (exploratory) -- y regressed on the two parts of x separately:
       R = open_pt - line_anchor   the revert-to-opener component
       C = x - R                   the screened consensus's own deviation
     This is a diagnostic, not an amendment. Nothing in the registered grading changes on
     the strength of it -- see the amendment ledger's rule that a data-driven amendment
     cannot carry the confirmatory claim.

    python research/spread/scripts/audit_version_b_methods.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_version_b as vb  # noqa: E402
import weekly_slate as ws  # noqa: E402

RULE = "=" * 72


def graded_games() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(full forward log, all Monday-anchored games, the graded subset) -- vb's own join."""
    log = pd.read_csv(vb.LOG)
    g = vb.monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [vb.close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    now = datetime.now(timezone.utc)
    return log, g, g[g.close.notna() & (g.kick_utc < now)].copy()


def anchor_offsets(graded: pd.DataFrame) -> pd.Series:
    """Hours between each graded game's week's Monday 00:00 ET and its anchoring capture."""
    cap = pd.to_datetime(graded.captured_utc, format="%Y%m%dT%H%M%SZ", utc=True).dt.tz_convert(vb.ET)
    kick_et = graded.kick_utc.dt.tz_convert(vb.ET)
    monday = (kick_et - pd.to_timedelta(kick_et.dt.weekday, unit="D")).dt.normalize()
    return (cap - monday).dt.total_seconds() / 3600


def cluster_ols_multi(y, regressors, cl, names, min_weeks=vb.MIN_WEEKS):
    """Cluster-robust OLS with k regressors; same estimator and fallback as vb.cluster_ols.

    Returns {name: {coef, lo, hi, se}} and prints a row per term. Below `min_weeks` clusters
    the cluster meat is degenerate, so this falls back to HC1 and says so -- those intervals
    are optimistic and are not cluster evidence.
    """
    X = np.column_stack([np.ones(len(y))] + list(regressors))
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    codes = np.unique(cl)
    G, n, k = len(codes), len(y), X.shape[1]
    if G >= min_weeks:
        meat = sum(np.outer(X[cl == g].T @ e[cl == g], X[cl == g].T @ e[cl == g]) for g in codes)
        V = bread @ meat @ bread * (G / (G - 1)) * ((n - 1) / max(n - k, 1))
        df, kind = G - 1, "cluster"
    else:
        V = bread @ (X * (e ** 2)[:, None]).T @ X @ bread * (n / max(n - k, 1))
        df, kind = n - k, "hc1"
    crit = float(tdist.ppf(0.975, max(df, 1)))
    out = {}
    for i, nm in enumerate(["const"] + names):
        se = float(np.sqrt(V[i, i]))
        out[nm] = {"coef": float(b[i]), "se": se,
                   "lo": float(b[i] - crit * se), "hi": float(b[i] + crit * se), "se_kind": kind}
        print(f"    {nm:28s} {b[i]:+.3f} [{b[i] - crit * se:+.3f}, {b[i] + crit * se:+.3f}]  "
              f"se {se:.3f} ({kind})")
    return out


def main() -> int:
    log, g, graded = graded_games()
    y = (graded.close - graded.line_pt).to_numpy(float)
    x = (graded.E4 - graded.line_pt).to_numpy(float)
    cl = graded.week.to_numpy()

    print(f"{RULE}\n1. ANCHOR -- is the graded 'Monday line' a Monday capture?")
    hours = anchor_offsets(graded)
    print(f"  capture weekday: "
          f"{pd.to_datetime(graded.captured_utc, format='%Y%m%dT%H%M%SZ', utc=True)
             .dt.tz_convert(vb.ET).dt.day_name().value_counts().to_dict()}")
    print(f"  hours after Monday 00:00 ET: median {hours.median():.1f}   "
          f"share < 24h (a true Monday capture) {(hours < 24).mean():.1%}")
    by_week = (graded.assign(h=hours.values, mon=(hours < 24).values)
               .groupby("week").agg(n=("event_id", "size"), median_h=("h", "median"),
                                    share_monday=("mon", "mean")).round(2))
    print(by_week.to_string())

    print(f"\n{RULE}\n2. REGRESSOR -- how much of x is the market's move since the opener?")
    since_open = (graded.line_pt - graded.open_pt).to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(since_open)
    r = float(np.corrcoef(x[ok], -since_open[ok])[0, 1])
    print(f"  corr(x, -(line_anchor - open_pt)) = {r:+.3f}   R^2 = {r ** 2:.3f}")
    print(f"  sd(x) {x[ok].std():.2f}   sd(line_anchor - open_pt) {since_open[ok].std():.2f}")
    print(f"  prereg B1 assumed sd(x) ~ 0.45; realized is {x[ok].std() / 0.45:.1f}x that")

    print(f"\n{RULE}\n3. TARGET -- y = close - line_anchor, and B5's tie handling")
    side = np.sign(x)
    print(f"  n {len(y)}   mean {y.mean():+.3f}   sd {y.std():.3f}")
    print(f"  line never moved (y == 0): {(y == 0).sum()} of {len(y)} = {(y == 0).mean():.1%}")
    print(f"  beat_close as B5 codes it (side*y > 0):  {(side * y > 0).mean():.1%}")
    print(f"  beat_close among games that moved:       {(side * y > 0)[y != 0].mean():.1%}"
          f"  (n {(y != 0).sum()})")
    print(f"  lost to the close (side*y < 0):          {(side * y < 0).mean():.1%}")

    print(f"\n{RULE}\n4. SELECTION -- played games that fail to grade")
    played = g[g.kick_utc < datetime.now(timezone.utc)]
    miss = played[played.close.isna()]
    print(f"  anchored {len(g)}   played {len(played)}   graded {len(graded)}   "
          f"played without an AN close: {len(miss)}")
    if len(miss):
        print(f"  mean |E4 - line| ungraded {np.abs(miss.E4 - miss.line_pt).mean():.2f} "
              f"vs graded {np.abs(x).mean():.2f}")

    print(f"\n{RULE}\n5. B2 COVERAGE -- the fixed game set")
    per_bucket = vb.capture_offsets(log[log.event_id.isin(graded.event_id)])
    per_bucket = per_bucket.merge(graded[["event_id", "close"]], on="event_id")
    fixed, dropped = vb.apply_fixed_game_set(per_bucket)
    print(f"  {fixed.event_id.nunique()} distinct games x {len(vb.BUCKET_LABELS)} buckets "
          f"= {len(fixed)} rows; {dropped} games dropped")
    print(f"  weeks represented: {sorted(fixed.week.unique())}")

    print(f"\n{RULE}\n6. LEAKAGE -- does the fitted archive carry live-season rows?")
    hist, _ = base.load()
    live_seasons = sorted({int(s) for s in pd.to_datetime(graded.kick, utc=True).dt.year})
    bad = int(hist.season.isin(live_seasons).sum())
    print(f"  archive seasons {int(hist.season.min())}-{int(hist.season.max())}, {len(hist)} games")
    print(f"  upto passed to prior_skill: {int(hist.season.max())}")
    print(f"  rows from the graded seasons {live_seasons} inside the archive: {bad}"
          + ("  <-- LEAKAGE" if bad else "  (clean)"))
    print(f"  MODEL_COLS feeding pred_close: {ws.MODEL_COLS}")

    print(f"\n{RULE}\n7. DECOMPOSITION (EXPLORATORY -- grades nothing, amends nothing)")
    R = (graded.open_pt - graded.line_pt).to_numpy(float)
    C = x - R
    print(f"  sd(x) {x.std():.2f}   sd(R) {R.std():.2f}   sd(C) {C.std():.2f}   "
          f"corr(R,C) {np.corrcoef(R, C)[0, 1]:+.3f}")
    print("  y on x alone (B4's registered estimate):")
    cluster_ols_multi(y, [x], cl, ["x: E4 - line_anchor"])
    print("  y on both components:")
    cluster_ols_multi(y, [R, C], cl, ["R: open_pt - line_anchor", "C: consensus deviation"])
    print("  y on the panel component alone:")
    cluster_ols_multi(y, [C], cl, ["C: consensus deviation"])
    print("\n  The registered B4 slope is a variance-weighted blend of these two. Reported as a")
    print("  diagnostic only: the amendment ledger bars a data-driven amendment from carrying")
    print("  the confirmatory claim, and B4's regressor stands as registered.")
    return 0


def _check() -> None:
    # anchor_offsets: a Tuesday 14:00 ET capture for a Saturday game is 38 hours after Monday
    df = pd.DataFrame({"captured_utc": ["20260908T180000Z"],
                       "kick_utc": pd.to_datetime(["2026-09-12T19:30:00+00:00"], utc=True)})
    assert abs(float(anchor_offsets(df).iloc[0]) - 38.0) < 0.01, anchor_offsets(df)
    # cluster_ols_multi recovers a known two-regressor slope pair
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 600), rng.normal(0, 1, 600)
    yv = 0.4 * a - 0.2 * b + rng.normal(0, 1, 600)
    out = cluster_ols_multi(yv, [a, b], np.repeat(np.arange(12), 50), ["a", "b"])
    assert out["a"]["lo"] < 0.4 < out["a"]["hi"] and out["b"]["lo"] < -0.2 < out["b"]["hi"], out
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
