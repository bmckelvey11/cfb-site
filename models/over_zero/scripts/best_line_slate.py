"""Floor-bias over model across every real sportsbook, with the total shopped.

The v1 model qualifies a game from ONE spread/total pair. Books disagree, so this
script splits that into two jobs:

  qualify on the fair number -- median spread and median total across the real
    Action Network books (outlier-guarded), which is the distribution the 1.75
    threshold was calibrated against (v1 fits on games.csv, one line per game)
  execute at the best number -- among books pricing the over at -120 or better,
    the lowest posted total, tie-broken on price

Qualifying on the best number instead would manufacture picks: the min of N noisy
totals sits below the market, which inflates the bias straight through the gate.
The printed run reports both counts so that gap is visible.

    python models/over_zero/scripts/best_line_slate.py
    python models/over_zero/scripts/best_line_slate.py --days 3 --threshold 1.75

Caveat: shopping was never backtested for this model. The 64.5% headline is a
single-line-source number; taking a better total can only help at an unchanged
signal, but it is an execution improvement, not a re-validated edge.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "models" / "over_zero" / "v1"))
sys.path.insert(0, str(REPO / "research" / "spread" / "scripts"))

import collect_line_timing as clt  # noqa: E402
from censoring_bias import censoring_bias, fit_pipeline, implied_team_points  # noqa: E402
from run_on_project_data import DEFAULT_CSV, load  # noqa: E402

OUT_DIR = Path(os.environ["CFB_DATA_ROOT"]) / "processed" / "over_zero"
# Action Network book ids, names from AN's own /web/v1/books (2026-09-08). 15 and 30 are
# consensus and opener -- not bettable, so not shoppable.
REAL_BOOKS = {"49": "Caesars", "68": "DraftKings", "69": "FanDuel",
              "71": "BetRivers", "75": "BetMGM"}
OUTLIER_PTS = 2.5        # a book this far off the median of all books is ignored (n >= 3)
MIN_ODDS = -120          # the model's own price gate (MODEL_GUIDE: over at -120 or better)
ET = ZoneInfo("America/New_York")
COLUMNS = ["run_at", "kick", "home", "away", "n_books", "spread_fair", "total_fair",
           "total_range", "dog_implied", "bias_fair", "p_over_fair", "pick", "best_total",
           "best_book", "best_odds", "bias_best", "playable"]


def _usable(m: dict) -> bool:
    """A real, currently postable main-market quote -- not in-play, not an alt line."""
    return (not m.get("is_live") and not m.get("is_alt_market")
            and m.get("value") is not None and m.get("odds") is not None)


def live_markets(now: datetime, days: int) -> pd.DataFrame:
    """Per-book event spread and total for games kicking off in the next `days` days."""
    lo, hi = now - timedelta(days=1), now + timedelta(days=days)
    wk_guess = max(1, int((now - datetime(now.year, 8, 25, tzinfo=timezone.utc)).days // 7) + 1)
    rows = []
    for week in range(max(1, wk_guess - 1), wk_guess + 3):
        try:
            payload = json.loads(clt._get(
                clt.AN_SCOREBOARD, {"season": now.year, "week": week, "seasonType": "reg"}))
        except Exception as exc:
            print(f"  AN week {week}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        for g in payload.get("games", []):
            ko = datetime.fromisoformat(g["start_time"].replace("Z", "+00:00"))
            if not (lo <= ko <= hi):
                continue
            teams = {t["id"]: t for t in g.get("teams", [])}
            spreads, totals = {}, {}
            for book, b in (g.get("markets") or {}).items():
                if book not in REAL_BOOKS:
                    continue
                event = b.get("event") or {}
                for s in event.get("spread") or []:
                    if _usable(s) and s.get("side") == "home":
                        spreads[book] = float(s["value"])
                for t in event.get("total") or []:
                    if _usable(t) and t.get("side") == "over":
                        totals[book] = (float(t["value"]), int(t["odds"]))
            rows.append({
                "event_id": g["id"], "kick": ko,
                "home": teams.get(g["home_team_id"], {}).get("display_name"),
                "away": teams.get(g["away_team_id"], {}).get("display_name"),
                "spreads": spreads, "totals": totals})
        time.sleep(0.5)
    return pd.DataFrame(rows).drop_duplicates("event_id")


def guarded(values: pd.Series) -> pd.Series:
    """Drop books more than OUTLIER_PTS from the median of all books (n >= 3).

    The median of ALL books, not of the others: with three books the outlier drags the
    other two's median toward itself.
    """
    if len(values) >= 3:
        kept = values[(values - values.median()).abs() <= OUTLIER_PTS]
        if len(kept) >= 2:
            return kept
    return values


def conservative_median(values: pd.Series, *, high: bool) -> float:
    """Median snapped to a number a book actually posts, on the side that lowers the bias.

    An even count interpolates to a total no book offers -- two books at 55.5 and 56.5
    give a "fair" 56.0, and gating on the bias at a synthetic half-point is the same
    selection-on-noise the fair number exists to avoid. Break the tie toward the higher
    total and the smaller spread, both of which raise the underdog's implied score and so
    make the 1.75 gate harder, never easier.
    """
    return float(values.quantile(0.5, interpolation="higher" if high else "lower"))


def shop_total(totals: dict, min_books: int = 2) -> dict:
    """Fair total and the best playable over, from {book: (total, odds)}.

    Two books are the minimum for a "fair" number worth the name. `min_books=1` is the
    single-book read (--book): fair and best collapse onto that book's own line.
    """
    if len(totals) < min_books:
        return {}
    v = guarded(pd.Series({b: t for b, (t, _) in totals.items()}))
    out = {"n_books": len(v), "total_fair": conservative_median(v, high=True),
           "total_range": float(v.max() - v.min())}
    # Lowest total among books pricing the over at MIN_ODDS or better; ties go to the price.
    playable = [(t, -totals[b][1], b) for b, t in v.items() if totals[b][1] >= MIN_ODDS]
    if playable:
        total, neg_odds, book = min(playable)
        out.update({"best_total": total, "best_book": REAL_BOOKS[book],
                    "best_odds": -neg_odds, "playable": True})
    else:
        best = v.idxmin()
        out.update({"best_total": float(v[best]), "best_book": REAL_BOOKS[best],
                    "best_odds": totals[best][1], "playable": False})
    return out


def bias_of(spread: np.ndarray, total: np.ndarray, fit) -> np.ndarray:
    dog, fav = implied_team_points(np.abs(spread), total)
    _, bias = censoring_bias(dog, fav, fit.tobit_dog.sigma, fit.tobit_fav.sigma)
    return bias


def fit_model(fit_csv: Path, fit_seasons):
    """The Arscott pipeline, plus the fit sample's underdog-implied support."""
    spread_est, totals_est, fav_pts, dog_pts = load(fit_csv, fit_seasons)
    print(f"Fit on {spread_est.size:,} games from seasons "
          f"{min(fit_seasons)}-{max(fit_seasons)}")
    return (fit_pipeline(spread_est, totals_est, fav_pts, dog_pts),
            (totals_est - spread_est) / 2)


def score(games: pd.DataFrame, fit, fit_dog: np.ndarray, run_at: str, threshold: float,
          book: str | None = None, quiet: bool = False) -> pd.DataFrame:
    """One view of an already-fetched slate: shopped across books, or one book alone."""
    # One book means no shopping and no cross-book fair: that book IS both numbers.
    only = next((k for k, v in REAL_BOOKS.items() if v == book), None) if book else None
    need = 1 if only else 2

    rows = []
    for g in games.itertuples():
        totals, spreads = g.totals, g.spreads
        if only:
            totals = {only: totals[only]} if only in totals else {}
            spreads = {only: spreads[only]} if only in spreads else {}
        shopped = shop_total(totals, need)
        if not shopped or len(spreads) < need:
            continue
        kept = guarded(pd.Series(spreads))
        # Only the magnitude feeds the model; carry the sign back for the reader.
        mag = conservative_median(kept.abs(), high=False)
        if mag == 0:                               # pick'em -- no favorite, per the paper
            continue
        spread_fair = float(kept[kept.abs() == mag].iloc[0])
        rows.append({"kick": g.kick, "home": g.home, "away": g.away,
                     "spread_fair": spread_fair, **shopped})
    t = pd.DataFrame(rows)
    if t.empty:
        return t

    t["bias_fair"] = bias_of(t.spread_fair.to_numpy(), t.total_fair.to_numpy(), fit)
    t["p_over_fair"] = fit.probit.win_prob(t.bias_fair.to_numpy())
    # Same spread, best total: isolates what shopping the total alone does to the bias.
    t["bias_best"] = bias_of(t.spread_fair.to_numpy(), t.best_total.to_numpy(), fit)
    t["pick"] = np.where(t.bias_fair > threshold, "OVER", "")
    t["run_at"] = run_at
    t["dog_implied"] = (t.total_fair - t.spread_fair.abs()) / 2
    # The picks live where the underdog is implied for a handful of points, and the fit
    # sample thins out fast down there. Print the support so p_over is read for what it
    # is: a parametric read at the edge of the calibrated region, not a local rate.
    floor = t.loc[t.pick == "OVER", "dog_implied"].min() if (t.pick == "OVER").any() else None
    if floor is not None and not quiet:
        print(f"Picks sit at dog_implied {floor:.1f}-"
              f"{t.loc[t.pick == 'OVER', 'dog_implied'].max():.1f}; the fit sample has "
              f"{int((fit_dog < 5).sum()):,} games under 5 and {int((fit_dog < 4).sum()):,} "
              f"under 4 -- thin support, so treat p_over as extrapolated there.")
    return t.sort_values("bias_fair", ascending=False)[COLUMNS]


def et_clock(kick: datetime) -> str:
    """Kickoff as the board has always shown it: 12-hour Eastern, no leading zero.

    strftime's no-pad hour is %-I on POSIX and %#I on Windows, so neither is portable.
    """
    d = kick.astimezone(ET)
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'} ET"


def export_json(views: dict[str, pd.DataFrame], path: Path, run_at: str,
                threshold: float) -> None:
    """Every view in one payload, for a static site that switches between them.

    The board is a build-time import, not a fetch, so all six views ship together. Kickoffs
    are pre-formatted in Eastern -- the reader's frame, and the one the board has always
    used; leaving them in UTC would move every Saturday night game to Sunday.
    """
    payload = {"run_at": run_at, "threshold": threshold, "min_odds": MIN_ODDS,
               "books": list(REAL_BOOKS.values()), "views": {}}
    for name, t in views.items():
        picks = t[t.pick == "OVER"] if not t.empty else t
        # `scored` is how many games the view could price at all. A book that posts a total
        # but no spread scores nothing -- the model needs both -- and an empty board should
        # say that rather than imply the book had no qualifying games.
        payload["views"][name] = {"scored": len(t), "picks": [
            {"date": r.kick.astimezone(ET).strftime("%b %d"),
             "time": et_clock(r.kick),
             "away": r.away, "home": r.home, "total": r.total_fair, "spread": r.spread_fair,
             "bias": round(r.bias_fair, 3), "probability": round(r.p_over_fair * 100, 2),
             "dogImplied": r.dog_implied, "bestTotal": r.best_total, "bestBook": r.best_book,
             "bestOdds": int(r.best_odds), "books": int(r.n_books), "playable": bool(r.playable)}
            for r in picks.itertuples()]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    counts = ", ".join(f"{k} {len(v['picks'])}/{v['scored']}" for k, v in payload["views"].items())
    print(f"Wrote {path} ({counts})")


def report(t: pd.DataFrame, threshold: float, book: str | None = None) -> None:
    if t.empty:
        print(f"No games with {book or 'two or more books'} quoting both markets.")
        return
    print(f"\n{'home':<22} {'away':<22} {'fair':>6} {'bias':>6} {'P(over)':>8} "
          f"{'best':>6} {'book':<11} {'odds':>6} pick")
    for r in t.itertuples():
        flag = "" if r.playable else "  (no price at -120 or better)"
        print(f"{r.home:<22} {r.away:<22} {r.total_fair:>6.1f} {r.bias_fair:>6.2f} "
              f"{r.p_over_fair * 100:>7.2f}% {r.best_total:>6.1f} {r.best_book:<11} "
              f"{r.best_odds:>+6d} {r.pick}{flag if r.pick else ''}")
    on_fair = int((t.bias_fair > threshold).sum())
    on_best = int((t.bias_best > threshold).sum())
    playable = int(((t.bias_fair > threshold) & t.playable).sum())
    label = f"{book}'s total" if book else "the fair total"
    print(f"\n{on_fair}/{len(t)} games clear bias > {threshold} on {label}; "
          f"{playable} of those have a price at {MIN_ODDS} or better.")
    if book:
        print(f"Single-book run: no shopping, and {book}'s own number is the gate rather "
              f"than the market's -- one book's noise passes straight through it.")
    else:
        print(f"{on_best} would clear if qualified on the shopped total instead -- that "
              f"gap is selection on book noise, which is why the gate is the fair number.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fit-csv", default=str(DEFAULT_CSV))
    ap.add_argument("--season", type=int, default=datetime.now(timezone.utc).year,
                    help="current season; the fit uses every season before it")
    ap.add_argument("--fit-from", type=int, default=2013, help="first season to fit on")
    ap.add_argument("--days", type=int, default=8, help="kickoff window from now")
    ap.add_argument("--threshold", type=float, default=1.75,
                    help="bet rule: over when expected censoring bias exceeds this")
    ap.add_argument("--book", choices=sorted(REAL_BOOKS.values()),
                    help="score one book's own number instead of shopping across all of "
                         "them; the fair and best columns collapse onto that book")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="'' to skip writing")
    ap.add_argument("--json", help="also write every view -- shopped plus each book on its "
                                   "own -- to this path, for the signal board to import")
    args = ap.parse_args()

    seasons = list(range(args.fit_from, args.season))
    fit, fit_dog = fit_model(Path(args.fit_csv), seasons)
    now = datetime.now(timezone.utc)
    run_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    games = live_markets(now, args.days)
    print(f"Fetched {len(games)} games kicking off in the next {args.days} days")

    t = score(games, fit, fit_dog, run_at, args.threshold, args.book)
    report(t, args.threshold, args.book)

    if args.json:
        # Every view off the one fetch: six scorings of the same games, not six AN pulls.
        views = {"Best lines": score(games, fit, fit_dog, run_at, args.threshold, quiet=True)}
        for name in REAL_BOOKS.values():
            views[name] = score(games, fit, fit_dog, run_at, args.threshold, name, quiet=True)
        export_json(views, Path(args.json), run_at, args.threshold)

    if args.out_dir and not t.empty:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = t.run_at.iloc[0].replace(":", "").replace("-", "")
        tag = f"_{args.book.lower()}" if args.book else ""
        for path in (out / f"best_line_slate_{stamp}{tag}.csv",
                     out / f"best_line_slate_latest{tag}.csv"):
            t.to_csv(path, index=False)
            print(f"Wrote {len(t)} rows to {path}")
    return 0


def _check() -> None:
    tot = {"68": (44.5, -110), "69": (43.5, -115), "71": (43.5, -108), "75": (52.0, -110)}
    s = shop_total(tot)
    # 52.0 is 8 from the median -> guarded out; best playable is the 43.5 at -108.
    assert s["n_books"] == 3 and s["total_fair"] == 43.5, s
    assert (s["best_total"], s["best_book"], s["best_odds"]) == (43.5, "BetRivers", -108), s
    assert s["playable"] is True, s
    # Nothing at -120 or better -> still reported, flagged unplayable.
    s2 = shop_total({"68": (44.5, -135), "69": (45.0, -130)})
    assert s2["playable"] is False and s2["best_total"] == 44.5, s2
    assert not shop_total({"68": (44.5, -110)}), "one book is not a market"
    # ...unless the run asked for that one book, where fair and best are the same number.
    s1 = shop_total({"68": (44.5, -110)}, 1)
    assert s1["total_fair"] == s1["best_total"] == 44.5 and s1["n_books"] == 1, s1
    assert not _usable({"value": 30.5, "odds": -110, "is_alt_market": True}), "alt lines are not quotes"
    # Two books straddling: the fair total is the posted 56.5, not the synthetic 56.0.
    s3 = shop_total({"68": (55.5, -110), "69": (56.5, -110)})
    assert s3["total_fair"] == 56.5 and s3["best_total"] == 55.5, s3
    # Spreads break the other way -- the smaller magnitude, which also lowers the bias.
    sp = pd.Series({"68": -45.5, "69": -44.5})
    assert conservative_median(sp.abs(), high=False) == 44.5
    print("checks pass")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _check()
    else:
        raise SystemExit(main())
