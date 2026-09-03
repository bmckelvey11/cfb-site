"""Book fair and line-shopping backtest.

Implements research/spread/docs/prereg-line-shopping.md. Read that first; the thresholds,
book set and cluster definition below are fixed there and are not tuning knobs.

Fair value = median closing home spread across real Action Network books. For each game and
each side, the best available number is compared with fair, and both are graded against the
final margin. Every game contributes both sides, so nothing here selects a bet; the value
measured is what taking the best number is worth mechanically.

    python research/spread/scripts/eval_line_shopping.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

REPO = next(p for p in Path(__file__).resolve().parents if (p / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

TABLE = "stg.an_market"
SEASONS = (2024, 2025)
# 15 is the consensus, 30 the consensus opener; neither is a book. See prereg.
REAL_BOOKS = (49, 68, 69, 71, 75)
CONSENSUS = 15
ODDS_WINDOW = (-135, 125)
GAIN_THRESHOLDS = (0.5, 1.0)
BREAKEVEN = 0.5238
KEY_NUMBERS = (3, 7)
OUT = cfb_paths.PROCESSED


def load() -> pd.DataFrame:
    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    # an_market holds only the offering; the game's score and status stay on
    # the scoreboard row, one per event_id, so the join cannot fan out.
    q = f"""
        select m.event_id, m.season, m.week,
               m.book_id as book,
               m.line as s,
               m.odds,
               m.line_status,
               m.is_live,
               sb.home_points as hp, sb.away_points as ap
        from {TABLE} m
        join stg.an_scoreboard sb using (event_id)
        where m.market_type = 'spread' and m.period = 'event' and m.side = 'home'
          and m.season in {SEASONS} and sb.status = 'complete'
    """
    return con.sql(q).df()


def clean(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    drops = {}
    n0 = len(d)
    d = d[d.s.notna() & d.hp.notna() & d.ap.notna()]
    drops["missing_value_or_score"] = n0 - len(d)
    n0 = len(d)
    d = d[~d.is_live.fillna(False).astype(bool)]
    drops["is_live"] = n0 - len(d)
    n0 = len(d)
    d = d[d.line_status.isna() | (d.line_status == "normal")]
    drops["line_status_not_normal"] = n0 - len(d)
    n0 = len(d)
    d = d[d.odds.isna() | d.odds.between(*ODDS_WINDOW)]
    drops["odds_outside_window"] = n0 - len(d)
    return d, drops


def cluster_mean(x: np.ndarray, g: np.ndarray) -> dict:
    """Mean with season-week cluster-robust SE and a t(G-1) 95% CI."""
    x = np.asarray(x, float)
    n = len(x)
    xbar = x.mean()
    resid = x - xbar
    G = len(np.unique(g))
    sums = pd.Series(resid).groupby(g).sum().to_numpy()
    se = np.sqrt((sums**2).sum()) / n
    tcrit = stats.t.ppf(0.975, G - 1)
    return {"n": int(n), "clusters": int(G), "mean": float(xbar), "se": float(se),
            "lo": float(xbar - tcrit * se), "hi": float(xbar + tcrit * se)}


def with_test(res: dict, null: float) -> dict:
    t = (res["mean"] - null) / res["se"] if res["se"] > 0 else np.nan
    res = dict(res)
    res["null"] = null
    res["p"] = float(2 * stats.t.sf(abs(t), res["clusters"] - 1)) if np.isfinite(t) else np.nan
    return res


def cover(margin: np.ndarray, number: np.ndarray, side: str) -> np.ndarray:
    """1 win, 0 loss, 0.5 push. `number` is the home spread; side is who is backed."""
    z = margin + number
    if side == "away":
        z = -z
    return np.where(z > 0, 1.0, np.where(z < 0, 0.0, 0.5))


def crosses_key(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when |a| and |b| sit on opposite sides of, or one lands on, 3 or 7 and the other does not."""
    lo, hi = np.minimum(np.abs(a), np.abs(b)), np.maximum(np.abs(a), np.abs(b))
    out = np.zeros(len(a), bool)
    for k in KEY_NUMBERS:
        out |= (lo <= k) & (hi >= k) & (lo != hi)
    return out


def build_sides(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    real = d[d.book.isin(REAL_BOOKS)]
    wide = real.pivot_table(index="event_id", columns="book", values="s")
    meta = real.drop_duplicates("event_id").set_index("event_id")[["season", "week", "hp", "ap"]]
    nb = wide.notna().sum(axis=1)
    keep = nb >= 2
    wide, meta = wide[keep], meta.loc[wide[keep].index]
    games = pd.DataFrame({
        "season": meta.season, "week": meta.week, "n_books": nb[keep],
        "fair": wide.median(axis=1), "hi": wide.max(axis=1), "lo": wide.min(axis=1),
        "book_hi": wide.idxmax(axis=1), "book_lo": wide.idxmin(axis=1),
        "margin": (meta.hp - meta.ap).astype(float),
    })
    games["range"] = games.hi - games.lo
    cons = d[d.book == CONSENSUS].drop_duplicates("event_id").set_index("event_id").s
    games["cons15"] = cons.reindex(games.index)

    home = games.assign(side="home", best=games.hi, best_book=games.book_hi)
    home["gain"] = home.best - home.fair
    away = games.assign(side="away", best=games.lo, best_book=games.book_lo)
    away["gain"] = away.fair - away.best
    sides = pd.concat([home, away]).reset_index()
    sides["win_fair"] = 0.0
    sides["win_best"] = 0.0
    for s in ("home", "away"):
        m = sides.side == s
        sides.loc[m, "win_fair"] = cover(sides.margin[m].to_numpy(), sides.fair[m].to_numpy(), s)
        sides.loc[m, "win_best"] = cover(sides.margin[m].to_numpy(), sides.best[m].to_numpy(), s)
    sides["diff"] = sides.win_best - sides.win_fair
    sides["cluster"] = sides.season * 100 + sides.week
    sides["key_cross"] = crosses_key(sides.fair.to_numpy(), sides.best.to_numpy())
    return games, sides


def fmt(r: dict, pct: bool = True) -> str:
    k = 100 if pct else 1
    s = f"{r['mean']*k:+.2f} [{r['lo']*k:+.2f}, {r['hi']*k:+.2f}]"
    if "p" in r:
        s += f"  p={r['p']:.3f} vs {r['null']*k:.2f}"
    return s


def main() -> int:
    raw = load()
    d, drops = clean(raw)
    games, sides = build_sides(d)
    out: dict = {"drops": drops, "n_games": int(len(games)), "n_sides": int(len(sides))}

    print(f"rows {len(raw)} -> {len(d)} after cleaning; drops {drops}")
    print(f"games with >=2 real books: {len(games)}  (books per game: "
          f"{games.n_books.value_counts().sort_index().to_dict()})\n")

    # P1 dispersion
    rg = games["range"]
    p1 = {"median": float(rg.median()), "mean": float(rg.mean()),
          **{f"share_ge_{t}": float((rg >= t).mean()) for t in (0.5, 1, 2, 3)},
          "cons15_within_0.25": float(((games.cons15 - games.fair).abs() <= 0.25).mean())}
    out["P1"] = p1
    print("P1 dispersion (range = max-min home spread across real books)")
    print(f"  median {p1['median']:.2f}  mean {p1['mean']:.2f}  "
          f">=0.5: {p1['share_ge_0.5']:.1%}  >=1: {p1['share_ge_1']:.1%}  "
          f">=2: {p1['share_ge_2']:.1%}  >=3: {p1['share_ge_3']:.1%}")
    print(f"  book 15 within 0.25 of fair: {p1['cons15_within_0.25']:.1%}")
    tail = games[rg >= 3].copy()
    if len(tail):
        real = d[d.book.isin(REAL_BOOKS)]
        tw = real[real.event_id.isin(tail.index)].pivot_table(
            index="event_id", columns="book", values=["s", "odds"])
        print(f"\n  tail: {len(tail)} games with range >= 3")
        print(pd.concat([tail[["season", "week", "fair", "range", "margin"]], tw], axis=1).to_string())
        out["P1_tail"] = json.loads(pd.concat([tail[["season", "week", "fair", "range"]], tw["s"]], axis=1)
                                     .reset_index().to_json(orient="records"))

    # P2 shopping value
    g = sides.cluster.to_numpy()
    p2 = cluster_mean(sides["diff"].to_numpy(), g)
    p2_pts = cluster_mean(sides.gain.to_numpy(), g)
    pos = sides.gain > 0
    per_pt = (sides["diff"][pos].sum() / sides.gain[pos].sum()) if pos.any() else np.nan
    out["P2"] = {"win_gain": p2, "points_gain": p2_pts, "win_per_point": float(per_pt),
                 "share_sides_with_gain": float(pos.mean())}
    print("\nP2 value of taking the best number, all game-sides (pushes = 0.5)")
    print(f"  win(best) - win(fair): {fmt(p2)} win-rate pts   n={p2['n']} clusters={p2['clusters']}")
    print(f"  points gained: {fmt(p2_pts, pct=False)}   sides with any gain: {pos.mean():.1%}   "
          f"win-rate pts per point: {per_pt*100:+.2f}")

    # P3 actionable cells
    out["P3"] = {}
    print("\nP3 game-sides where the best number beats fair by >= threshold")
    for thr in GAIN_THRESHOLDS:
        c = sides[sides.gain >= thr]
        if len(c) == 0:
            continue
        fair_r = with_test(cluster_mean(c.win_fair.to_numpy(), c.cluster.to_numpy()), 0.5)
        nb = c[c.win_best != 0.5]
        best_r = with_test(cluster_mean(nb.win_best.to_numpy(), nb.cluster.to_numpy()), BREAKEVEN)
        best_all = cluster_mean(c.win_best.to_numpy(), c.cluster.to_numpy())
        out["P3"][str(thr)] = {"n_sides": int(len(c)), "share": float(len(c) / len(sides)),
                               "win_fair": fair_r, "win_best_pushes_dropped": best_r,
                               "win_best_pushes_half": best_all,
                               "mean_gain_pts": float(c.gain.mean())}
        print(f"  gain >= {thr}: {len(c)} sides ({len(c)/len(sides):.1%}), mean gain {c.gain.mean():.2f} pts")
        print(f"    at FAIR number: {fmt(fair_r)}")
        print(f"    at BEST number, pushes dropped (n={best_r['n']}): {fmt(best_r)}")

    # Secondary
    print("\nSecondary")
    kc = sides[pos].groupby("key_cross")["diff"].agg(["size", "mean"])
    kc["mean"] = (kc["mean"] * 100).round(2)
    print("  gain>0 sides by key-number crossing (3 or 7):"); print(kc.to_string())
    bb = sides[pos].groupby(["side", "best_book"]).size().unstack(fill_value=0)
    print("  which book supplies the best number (gain>0 sides):"); print(bb.to_string())
    per_season = sides.groupby("season").apply(
        lambda s: pd.Series({"sides": len(s), "win_gain_pts": s["diff"].mean() * 100,
                             "mean_gain_pts": s.gain.mean(),
                             "share_gain_ge_1": (s.gain >= 1).mean()}), include_groups=False)
    print("  per season:"); print(per_season.round(3).to_string())
    out["secondary"] = {"key_cross": json.loads(kc.reset_index().to_json(orient="records")),
                        "best_book": json.loads(bb.reset_index().to_json(orient="records")),
                        "per_season": json.loads(per_season.reset_index().to_json(orient="records"))}

    OUT.mkdir(parents=True, exist_ok=True)
    sides.to_csv(OUT / "line_shopping_sides.csv", index=False)
    (OUT / "line_shopping.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {OUT / 'line_shopping_sides.csv'} and {OUT / 'line_shopping.json'}")
    return 0


def _check() -> None:
    m = np.array([10.0, -3.0, 7.0])
    s = np.array([-7.0, 3.0, -7.0])
    assert cover(m, s, "home").tolist() == [1.0, 0.5, 0.5], "home grading"
    assert cover(m, s, "away").tolist() == [0.0, 0.5, 0.5], "away grading"
    assert crosses_key(np.array([-2.5, -6.5, -10.0]), np.array([-3.5, -6.0, -12.0])).tolist() == [True, False, False]
    r = cluster_mean(np.array([1.0, 0.0, 1.0, 0.0]), np.array([1, 1, 2, 2]))
    assert abs(r["mean"] - 0.5) < 1e-12 and r["se"] == 0.0, "balanced clusters give zero cluster SE"
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
