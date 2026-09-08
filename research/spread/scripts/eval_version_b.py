"""Version B of research/spread/docs/prereg-line-movement.md: grade the forward log.

Written 2026-09-08 (amendment B1), BEFORE any in-season close existed, so the join and the
estimator are fixed ahead of the data. Reads only files the collector already writes.

  anchor   the earliest snapshot per game captured on or after Monday 00:00 ET of the
           game's kick week -- "Monday's line" in the pre-registration
  close    Action Network consensus (book 15), last full-game spread tick before kickoff,
           from raw/actionnetwork/history_event_<id>.json (pulled Mondays by CFB-AN-History)
  scores   CFBD, stg_gql.game, through the same name matching the archive build uses

Everything in PT sign: POSITIVE = home favoured. y = close - line_Monday; x = pred - line_Monday.

  B4  slope of y on x, season-week cluster SE, for E4 (registered), E6 and the model median
  B5  CLV and ATS of a Monday bet on the E4 side at |x| >= 1 and >= 2

Prints the observed sigmas, the MDE at the current n and the n at which the MDE reaches 0.2.
No verdict is printed before that n (amendment B1); the numbers are reported either way.

    python research/spread/scripts/eval_version_b.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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


def monday_anchor(log: pd.DataFrame) -> pd.DataFrame:
    """One row per game: the earliest snapshot on or after Monday 00:00 ET of its kick week."""
    log = log[log.event_id.notna() & log.kick.notna()].copy()
    cap = pd.to_datetime(log.captured_utc, format="%Y%m%dT%H%M%SZ", utc=True)
    kick_et = pd.to_datetime(log.kick, utc=True).dt.tz_convert(ET)
    monday = (kick_et - pd.to_timedelta(kick_et.dt.weekday, unit="D")).dt.normalize()
    log["captured"], log["week"] = cap, monday.dt.strftime("%Y-%m-%d")
    log = log[cap.dt.tz_convert(ET) >= monday].sort_values("captured")
    return log.groupby("event_id", as_index=False).first()


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


def margins(games: pd.DataFrame) -> pd.Series:
    """Home margin from CFBD via the archive build's name matching; NaN when unplayed/unmatched."""
    seasons = sorted(set(pd.to_datetime(games.kick, utc=True).dt.year))
    by_season = bpt.load_cfbd(base.cfb_paths.DB_PATH, seasons)
    out = []
    for r in games.itertuples():
        season = pd.Timestamp(r.kick).year
        pairs, _ = by_season.get(season, ({}, set()))
        hit = None
        for h in bpt.candidates(r.home):
            for a in bpt.candidates(r.road):
                hits = pairs.get(frozenset((h, a)))
                if hits:
                    g, flipped, _ = bpt.pick_game(hits, h, None, None, None)
                    if g is not None and g["home_points"] is not None:
                        m = float(g["home_points"]) - float(g["away_points"])
                        hit = -m if flipped else m
                    break
            if hit is not None:
                break
        out.append(np.nan if hit is None else hit)
    return pd.Series(out, index=games.index, dtype=float)


def cluster_ols(y, x, cl):
    """Slope of y on x with a cluster-robust SE and a t(G-1) interval."""
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
            "hi": float(b[1] + crit * se), "clusters": int(G), "n": int(n), "se_kind": kind}


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


def main() -> int:
    log = pd.read_csv(LOG)
    g = monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    g["margin"] = margins(g)
    now = datetime.now(timezone.utc)
    graded = g[g.close.notna() & (g.kick_utc < now)].copy()
    print(f"forward log: {log.snapshot.nunique()} snapshots, {len(g)} games with a Monday anchor, "
          f"{len(graded)} graded against a close, {int(graded.margin.notna().sum())} with a score")
    out = {"n_anchor": int(len(g)), "n_graded": int(len(graded)),
           "weeks": sorted(graded.week.unique().tolist())}
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
        out["slope"][p] = r
        print(f"  {p:10s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  se {r['se']:.3f} ({r['se_kind']})  "
              f"sd(x) {r['sd_x']:.2f}  n {r['n']}  weeks {r['clusters']}  MDE {r['mde_80']:.2f}  "
              f"n for MDE {TARGET_MDE}: {r['n_for_mde_0.2']}")

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
        row = {"thr": thr, "bets": int(m.sum()), "clv": clv, "beat_close": float((side * y[m] > 0).mean())}
        res = side * (graded.margin.to_numpy(float)[m] - graded.line_pt.to_numpy(float)[m])
        keep = np.isfinite(res) & (res != 0)
        if keep.sum() >= 10:
            row["ats"] = cluster_mean((res[keep] > 0).astype(float), cl[m][keep])
        out["bets"].append(row)
        ats = row.get("ats")
        print(f"  |x| >= {thr:.0f}: {row['bets']} bets  CLV {clv['mean']:+.2f} [{clv['lo']:+.2f}, {clv['hi']:+.2f}]  "
              f"beat close {row['beat_close']:.1%}"
              + (f"  ATS {ats['mean']:.3f} [{ats['lo']:.3f}, {ats['hi']:.3f}] vs {BREAKEVEN}" if ats else "  ATS: no scores yet"))

    print("\nper week: games graded / mean |close - Monday| / mean |E4 - Monday|")
    wk = graded.assign(ay=np.abs(y), ax=np.abs(x4)).groupby("week").agg(n=("event_id", "size"),
                                                                       move=("ay", "mean"), gap=("ax", "mean"))
    print(wk.round(2).to_string())
    out["per_week"] = json.loads(wk.reset_index().to_json(orient="records"))
    need = out["slope"]["E4"]["n_for_mde_0.2"]
    print(f"\nAmendment B1: no verdict until n >= {need} (MDE {TARGET_MDE}) or season end. Reported, not decided.")
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
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
