"""Version B of research/spread/docs/prereg-line-movement.md: grade the forward log.

Written 2026-09-08 (amendment B1), BEFORE any in-season close existed, so the join and the
estimator are fixed ahead of the data. Reads only files the collector already writes.

  anchor   the earliest snapshot per game captured on or after Monday 00:00 ET of the
           game's kick week -- "Monday's line" in the pre-registration
  close    Action Network consensus (book 15), last full-game spread tick before kickoff,
           from raw/actionnetwork/history_event_<id>.json (pulled Mondays by CFB-AN-History)
  scores   CFBD, stg.game, through the same name matching the archive build uses

Everything in PT sign: POSITIVE = home favoured. y = close - line_Monday; x = pred - line_Monday.

  B4  slope of y on x, season-week cluster SE, for E4 (registered), E6 and the model median
  B5  CLV and ATS of a Monday bet on the E4 side at |x| >= 1 and >= 2
  B2  slope by capture offset (mon/tue/wed/thu+ after Monday 00:00 ET), fixed game set

Prints the observed sigmas and the MDE at the current n. The MDE is informational only and
never sets a verdict (amendment B3 replaced B1's MDE gate). The stopping rule, verbatim, and
not to be paraphrased anywhere else in this repo:

    No verdict before season end; at season end, confirmatory inference requires ≥ 8 week
    clusters, and with fewer the read is reported as inconclusive.

    python research/spread/scripts/eval_version_b.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import t as tdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import collect_line_timing as clt  # noqa: E402
import build_prediction_tracker as bpt  # noqa: E402

ET = ZoneInfo("America/New_York")
LOG = base.OUT_DIR / "movement_forward_log.csv"
OUT = base.OUT_DIR / "version_b.json"
PREDS = ["E4", "E6", "pred_close"]     # E4 is the registered one; the others are reported beside it
CONSENSUS_BOOK = "15"
THRESH = (1.0, 2.0)
BREAKEVEN = 0.5238
TARGET_MDE = 0.2                        # the slope B4 must be able to exclude
MIN_WEEKS = 5                           # below this the cluster SE is degenerate; HC1 is printed instead
MIN_CLUSTERS_FOR_VERDICT = 8            # amendment B3: the stopping rule's cluster floor
SEASON_WINDOW = ((8, 25), (12, 15))     # in-season (month, day) window, ET -- matches collector_health.in_season
BUCKETS = [(0, 24, "mon"), (24, 48, "tue"), (48, 72, "wed"), (72, 1e9, "thu+")]   # amendment B2
BUCKET_LABELS = [b[2] for b in BUCKETS]
STOPPING_RULE = ("No verdict before season end; at season end, confirmatory inference requires "
                  "≥ 8 week clusters, and with fewer the read is reported as inconclusive.")


def monday_anchor(log: pd.DataFrame) -> pd.DataFrame:
    """One row per game: the earliest snapshot on or after Monday 00:00 ET of its kick week."""
    log = log[log.event_id.notna() & log.kick.notna()].copy()
    cap = pd.to_datetime(log.captured_utc, format="%Y%m%dT%H%M%SZ", utc=True)
    kick_et = pd.to_datetime(log.kick, utc=True).dt.tz_convert(ET)
    monday = (kick_et - pd.to_timedelta(kick_et.dt.weekday, unit="D")).dt.normalize()
    log["captured"], log["week"] = cap, monday.dt.strftime("%Y-%m-%d")
    log = log[cap.dt.tz_convert(ET) >= monday].sort_values("captured")
    return log.groupby("event_id", as_index=False).first()


def season_has_ended(now: datetime) -> bool:
    """Season-end half of amendment B3's gate: True once the ET date falls outside the
    regular-season window (SEASON_WINDOW). Independent of collector_health.py by design --
    that module is owned by a different agent in this build."""
    d = now.astimezone(ET)
    md = (d.month, d.day)
    return not (SEASON_WINDOW[0] <= md <= SEASON_WINDOW[1])


def apply_stopping_rule(e4_result: dict, season_ended: bool) -> dict | None:
    """Amendment B3, applied literally: null unless season_ended AND clusters >=
    MIN_CLUSTERS_FOR_VERDICT. e4_result's mde_80 is not read here -- a computed MDE must never
    set a verdict, however small it is."""
    if season_ended and e4_result["clusters"] >= MIN_CLUSTERS_FOR_VERDICT:
        return {"gate": "met", "clusters": e4_result["clusters"]}
    return None


def capture_offsets(log: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, bucket): the earliest capture inside that bucket, bucketed by hours
    after the game's week's Monday 00:00 ET into {"mon", "tue", "wed", "thu+"} (amendment B2).

    Does not apply the fixed game set -- see apply_fixed_game_set.
    """
    log = log[log.event_id.notna() & log.kick.notna()].copy()
    cap = pd.to_datetime(log.captured_utc, format="%Y%m%dT%H%M%SZ", utc=True)
    kick_et = pd.to_datetime(log.kick, utc=True).dt.tz_convert(ET)
    monday = (kick_et - pd.to_timedelta(kick_et.dt.weekday, unit="D")).dt.normalize()
    log["hours_after_monday_et"] = (cap.dt.tz_convert(ET) - monday).dt.total_seconds() / 3600
    log["week"] = monday.dt.strftime("%Y-%m-%d")
    log = log[log.hours_after_monday_et >= 0]
    log["offset_bucket"] = pd.cut(log.hours_after_monday_et, [b[0] for b in BUCKETS] + [1e9],
                                   labels=BUCKET_LABELS, right=False)
    log = log.dropna(subset=["offset_bucket"])
    log = log.sort_values("hours_after_monday_et")
    return log.groupby(["event_id", "offset_bucket"], as_index=False, observed=True).first()


def apply_fixed_game_set(per_bucket: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Amendment B2's fixed game set: a game missing from any (populated) bucket is dropped
    from every bucket it does have, so the decay across buckets is not confounded with which
    games happened to get captured when. Grouped by (event_id, week) -- by game and by week --
    though a game's week is a deterministic function of its event_id, so this is equivalent to
    grouping by event_id alone; the explicit pair avoids ever conflating two different games
    that reused an event_id across seasons.

    Returns (kept rows, number of games dropped).
    """
    if per_bucket.empty:
        return per_bucket, 0
    n_buckets = per_bucket.offset_bucket.nunique()
    counts = per_bucket.groupby(["event_id", "week"]).offset_bucket.nunique()
    keep = counts[counts == n_buckets].index
    dropped = int((counts < n_buckets).sum())
    kept = per_bucket[per_bucket.set_index(["event_id", "week"]).index.isin(keep)]
    return kept, dropped


def close_from_history(event_id: float, kick: datetime) -> float:
    path = clt.AN_DIR / f"history_event_{int(event_id)}.json"
    if not path.exists():
        return np.nan
    book = json.loads(path.read_text()).get(CONSENSUS_BOOK) or {}
    ticks = []
    for s in (book.get("event") or {}).get("spread", []) or []:
        if s.get("side") != "home":
            continue
        for h in s.get("history") or []:
            t = datetime.fromisoformat(h["updated_at"].replace("Z", "+00:00"))
            if t < kick and h.get("value") is not None:
                ticks.append((t, float(h["value"])))
    return -max(ticks)[1] if ticks else np.nan          # AN sign -> PT sign


def fetch_scores(con, seasons):
    """{(season, {home, away}): (cfbd_home, home_points, away_points)} from core.fact_game.

    core.fact_game is what CFB-CFBD-Daily rebuilds; stg.game is refreshed only by the
    GraphQL pull and lagged a full week of scores in 2026.
    """
    rows = con.execute(
        "select season, home_team, away_team, home_points, away_points from core.fact_game "
        "where season between ? and ? and home_points is not null",
        [min(seasons), max(seasons)]).fetchall()
    return {(int(s), frozenset((h, a))): (h, float(hp), float(ap)) for s, h, a, hp, ap in rows}


def margins(games: pd.DataFrame, scores: dict) -> pd.Series:
    """Home margin in PT orientation via the archive build's name matching; NaN when unplayed."""
    out = []
    for r in games.itertuples():
        season = pd.Timestamp(r.kick).year
        hit = np.nan
        for h in bpt.candidates(r.home):
            for a in bpt.candidates(r.road):
                rec = scores.get((season, frozenset((h, a))))
                if rec:
                    cfbd_home, hp, ap = rec
                    hit = (hp - ap) if cfbd_home == h else (ap - hp)
                    break
            if not np.isnan(hit):
                break
        out.append(hit)
    return pd.Series(out, index=games.index, dtype=float)


def cluster_ols(y, x, cl, conditional_on_fitted_predictor: bool = False):
    """Slope of y on x with a cluster-robust SE and a t(G-1) interval.

    Set conditional_on_fitted_predictor=True when x is itself a walk-forward prediction from a
    first-stage model (amendment A5) -- this SE does not propagate the first stage's
    uncertainty, and the result is marked so downstream readers can't miss it.
    """
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    codes = np.unique(cl)
    G, n = len(codes), len(y)
    if G >= MIN_WEEKS:
        meat = sum(np.outer(X[cl == g].T @ e[cl == g], X[cl == g].T @ e[cl == g]) for g in codes)
        V = bread @ meat @ bread * (G / (G - 1)) * ((n - 1) / max(n - 2, 1))
        df, kind = G - 1, "cluster"
    else:
        # ponytail: with fewer weeks than MIN_WEEKS a cluster SE is degenerate (one cluster
        # gives exactly zero), so fall back to HC1 and say so; the interval is optimistic.
        V = bread @ (X * (e ** 2)[:, None]).T @ X @ bread * (n / max(n - 2, 1))
        df, kind = n - 2, "hc1"
    se = float(np.sqrt(V[1, 1]))
    crit = float(tdist.ppf(0.975, max(df, 1)))
    return {"slope": float(b[1]), "se": se, "lo": float(b[1] - crit * se),
            "hi": float(b[1] + crit * se), "clusters": int(G), "n": int(n), "se_kind": kind,
            "conditional_on_fitted_predictor": bool(conditional_on_fitted_predictor)}


def cluster_mean(v, cl):
    v, cl = np.asarray(v, float), np.asarray(cl)
    codes = np.unique(cl)
    if len(codes) >= MIN_WEEKS:
        sums = np.array([(v[cl == g] - v.mean()).sum() for g in codes])
        se, df = float(np.sqrt((sums ** 2).sum()) / len(v)), len(codes) - 1
    else:
        se, df = float(v.std(ddof=1) / np.sqrt(len(v))), len(v) - 1     # same fallback as cluster_ols
    crit = float(tdist.ppf(0.975, max(df, 1)))
    return {"mean": float(v.mean()), "lo": float(v.mean() - crit * se),
            "hi": float(v.mean() + crit * se), "n": int(len(v)), "clusters": int(len(codes))}


def close_outcomes(side, y) -> dict:
    """B5's three-way split of a bet's fate against the close, plus the moved-only rate.

    `beat_close` keeps its registered definition -- mean(side * y > 0) -- so the key means the
    same thing it always did. What it does NOT mean is a win rate against 50%: a line that
    never moves (y == 0) lands in the complement, and in 2026 through week 3 that was 35% of
    graded games, which made the printed figure read as an anti-signal it is not. `tied_close`
    and `lost_to_close` name the rest of the mass; `beat_close_moved` is the rate among lines
    that actually moved, which is the one comparable to a coin flip. CLV is unaffected either
    way -- a tie contributes exactly 0 to the mean. See docs/methods-review-2026-09-21.md F3.
    """
    side, y = np.asarray(side, float), np.asarray(y, float)
    moved = y != 0
    return {"beat_close": float((side * y > 0).mean()),
            "tied_close": float((y == 0).mean()),
            "lost_to_close": float((side * y < 0).mean()),
            "n_moved": int(moved.sum()),
            "beat_close_moved": float((side * y > 0)[moved].mean()) if moved.any() else None}


def main() -> int:
    log = pd.read_csv(LOG)
    g = monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    g["margin"] = margins(g, fetch_scores(con, sorted(set(g.kick_utc.dt.year))))
    unmatched = g[g.margin.isna() & (g.kick_utc < datetime.now(timezone.utc))]
    if len(unmatched):
        print(f"no score for {len(unmatched)} played games: "
              f"{unmatched[['road', 'home']].values.tolist()[:8]}")
    now = datetime.now(timezone.utc)
    graded = g[g.close.notna() & (g.kick_utc < now)].copy()
    print(f"forward log: {log.snapshot.nunique()} snapshots, {len(g)} games with a Monday anchor, "
          f"{len(graded)} graded against a close, {int(graded.margin.notna().sum())} with a score")
    # Which model-set definition produced the rows being graded. pred_close is the median of
    # weekly_slate.MODEL_COLS, so a change to that set redefines the graded quantity; more than
    # one version among these rows means pred_close is silently two different things.
    versions = (sorted(int(v) for v in graded.model_set_version.dropna().unique())
                if "model_set_version" in graded else [])
    if len(versions) > 1:
        print(f"WARNING: forward log mixes model_set_version {versions}; pred_close is not one "
              f"quantity across these rows. Recompute with weekly_slate.py --recompute-forward-log.")
    # Same check for the edge/side DEFINITION. Rows written before the stamp existed are all
    # definition 1 by construction -- nothing about edge/side had changed -- so a missing value
    # is filled, not dropped. More than one definition means B5's bet set is two different
    # trades and must not be pooled.
    edge_defs = (sorted(int(v) for v in graded.edge_def_version.fillna(1).unique())
                 if "edge_def_version" in graded else [1])
    if len(edge_defs) > 1:
        print(f"WARNING: forward log mixes edge_def_version {edge_defs}; the B5 bet set is not "
              f"one trade across these rows. Grade the eras separately or recompute the log.")
    out = {"n_anchor": int(len(g)), "n_graded": int(len(graded)),
           "weeks": sorted(graded.week.unique().tolist()),
           "model_set_version": versions, "edge_def_version": edge_defs, "verdict": None}
    if len(graded) < 30:
        print("fewer than 30 graded games -- nothing to estimate yet")
        OUT.write_text(json.dumps(out, indent=2))
        return 0

    y = (graded.close - graded.line_pt).to_numpy(float)
    cl = graded.week.to_numpy()
    print(f"\nsd(close - line_Monday) = {y.std():.3f}   mean {y.mean():+.3f}")
    print("\nB4  slope of (close - line_Monday) on (pred - line_Monday), season-week clusters")
    out["slope"] = {}
    for p in PREDS:
        x = (graded[p] - graded.line_pt).to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        r = cluster_ols(y[ok], x[ok], cl[ok])
        r["sd_x"] = float(x[ok].std())
        r["mde_80"] = 2.8 * r["se"]
        r["n_for_mde_0.2"] = int(np.ceil(r["n"] * (r["mde_80"] / TARGET_MDE) ** 2))
        # amendment B3: the MDE is computed from whichever SE cluster_ols returned (cluster-robust
        # when clusters >= MIN_WEEKS, HC1 below it) -- mark the HC1 case explicit and unmissable,
        # because it is informational only, not cluster evidence, and must never set a verdict.
        r["mde_kind"] = "cluster" if r["se_kind"] == "cluster" else "informational_hc1_fallback"
        out["slope"][p] = r
        flag = "" if r["mde_kind"] == "cluster" else "  [INFORMATIONAL -- HC1 fallback, not cluster evidence]"
        print(f"  {p:10s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  se {r['se']:.3f} ({r['se_kind']})  "
              f"sd(x) {r['sd_x']:.2f}  n {r['n']}  weeks {r['clusters']}  MDE {r['mde_80']:.2f}  "
              f"n for MDE {TARGET_MDE}: {r['n_for_mde_0.2']}{flag}")

    print("\nB5  Monday bet on E4's side vs Monday's line")
    out["bets"] = []
    x4 = (graded.E4 - graded.line_pt).to_numpy(float)
    for thr in THRESH:
        m = np.abs(x4) >= thr
        if m.sum() < 10:
            print(f"  |x| >= {thr:.0f}: {int(m.sum())} bets -- too few")
            continue
        side = np.sign(x4[m])
        clv = cluster_mean(side * y[m], cl[m])
        row = {"thr": thr, "bets": int(m.sum()), "clv": clv, **close_outcomes(side, y[m])}
        res = side * (graded.margin.to_numpy(float)[m] - graded.line_pt.to_numpy(float)[m])
        keep = np.isfinite(res) & (res != 0)
        if keep.sum() >= 10:
            row["ats"] = cluster_mean((res[keep] > 0).astype(float), cl[m][keep])
        out["bets"].append(row)
        ats = row.get("ats")
        moved = (f"{row['beat_close_moved']:.1%} (n {row['n_moved']})"
                 if row["beat_close_moved"] is not None else "n/a")
        print(f"  |x| >= {thr:.0f}: {row['bets']} bets  CLV {clv['mean']:+.2f} [{clv['lo']:+.2f}, {clv['hi']:+.2f}]  "
              f"vs close beat/tie/lost {row['beat_close']:.1%}/{row['tied_close']:.1%}/{row['lost_to_close']:.1%}  "
              f"beat among moved {moved}"
              + (f"  ATS {ats['mean']:.3f} [{ats['lo']:.3f}, {ats['hi']:.3f}] vs {BREAKEVEN}" if ats else "  ATS: no scores yet"))

    print("\nB2  slope by capture offset (fixed game set; season-week clusters)")
    per_bucket = capture_offsets(log[log.event_id.isin(graded.event_id)])
    per_bucket = per_bucket.merge(graded[["event_id", "close"]], on="event_id")
    fixed, dropped = apply_fixed_game_set(per_bucket)
    fixed_universe = sorted(per_bucket.offset_bucket.unique().tolist(), key=BUCKET_LABELS.index)
    before_counts = {b: int((per_bucket.offset_bucket == b).sum()) for b in BUCKET_LABELS}
    out["by_capture"] = {"games_dropped_for_fixed_set": dropped, "buckets_in_fixed_set": fixed_universe,
                          "games_per_bucket_before_fixed_set": before_counts}
    print(f"  fixed game set over {fixed_universe} (before: {before_counts}): "
          f"{dropped} game(s) dropped for missing at least one of those buckets")
    for b in BUCKET_LABELS:
        sub = fixed[fixed.offset_bucket == b]
        if len(sub) < 30:
            print(f"  {b:4s} n {len(sub)} -- too few"); continue
        yy = (sub.close - sub.line_pt).to_numpy(float)
        xx = (sub.E4 - sub.line_pt).to_numpy(float)
        r = cluster_ols(yy, xx, sub.week.to_numpy())
        out["by_capture"][b] = r
        print(f"  {b:4s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  n {r['n']}  weeks {r['clusters']}")

    print("\nper week: games graded / mean |close - Monday| / mean |E4 - Monday|")
    wk = graded.assign(ay=np.abs(y), ax=np.abs(x4)).groupby("week").agg(n=("event_id", "size"),
                                                                       move=("ay", "mean"), gap=("ax", "mean"))
    print(wk.round(2).to_string())
    out["per_week"] = json.loads(wk.reset_index().to_json(orient="records"))

    season_ended = season_has_ended(now)
    out["season_ended"] = season_ended
    out["verdict"] = apply_stopping_rule(out["slope"]["E4"], season_ended)
    status = ("confirmatory_gate_met" if out["verdict"] else
              "inconclusive" if season_ended else "pre_season_end")
    out["read_status"] = status
    print(f"\nAmendment B3 (stopping rule): {STOPPING_RULE}")
    print(f"  season_ended={season_ended}  clusters(E4)={out['slope']['E4']['clusters']}  "
          f"verdict={out['verdict']}  status={status}")
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print(f"wrote {OUT}")
    return 0


def _check() -> None:
    # Monday anchor: a Sunday-night snapshot must lose to Monday's for a Saturday game
    log = pd.DataFrame({"event_id": [1, 1], "kick": ["2026-09-12T19:30:00+00:00"] * 2,
                        "captured_utc": ["20260906T230000Z", "20260907T190500Z"], "line_pt": [7.0, 7.5]})
    a = monday_anchor(log)
    assert len(a) == 1 and a.line_pt.iloc[0] == 7.5 and a.week.iloc[0] == "2026-09-07", a
    # slope recovery with clusters
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.5, 400); yv = 0.3 * x + rng.normal(0, 1, 400)
    r = cluster_ols(yv, x, np.repeat(np.arange(10), 40))
    assert abs(r["slope"] - 0.3) < 0.3 and r["lo"] < 0.3 < r["hi"], r
    # close_outcomes: the three shares partition the sample, and ties are excluded from the
    # moved-only rate rather than counted as losses (the bug docs/methods-review-2026-09-21.md
    # F3 found). 2 beats, 1 loss, 2 ties -> 40% / 40% / 20%, and 2 of 3 among the moved.
    o = close_outcomes([1, 1, 1, -1, -1], [2.0, 1.0, 0.0, 0.0, 1.0])
    assert (o["beat_close"], o["tied_close"], o["lost_to_close"]) == (0.4, 0.4, 0.2), o
    assert abs(o["beat_close"] + o["tied_close"] + o["lost_to_close"] - 1.0) < 1e-12, o
    assert o["n_moved"] == 3 and abs(o["beat_close_moved"] - 2 / 3) < 1e-12, o
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
