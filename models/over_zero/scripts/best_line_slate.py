"""Floor-bias over model across every real sportsbook, with the total shopped.

The v1 model qualifies a game from ONE spread/total pair. Books disagree, so this
script splits that into two jobs:

  qualify on the fair number -- median spread and median total across the four
    regulated books in the the-odds-api snapshot (FAIR_BOOKS, outlier-guarded), the
    closest live stand-in for the one-line-per-game distribution the 1.75 threshold
    was calibrated against (v1 fits on games.csv)
  execute at the best number -- among books pricing the over at -120 or better,
    the lowest posted total, tie-broken on price

Qualifying on the best number instead would manufacture picks: the min of N noisy
totals sits below the market, which inflates the bias straight through the gate.
The printed run reports both counts so that gap is visible.

`--qualify shopped` does exactly that on purpose, for answering "what would the
shopped gate have picked". It is not the calibrated rule and the default stays
`fair`. Because bias_best >= bias_fair on every row, it can only add picks, never
drop one, and the extra picks clear on whichever book posted the lowest number.
Its rows key into the pick history under `model='slate-shopped'`, so the two rules
accumulate side by side rather than overwriting each other. It is refused with
`--book`, where fair and best are the same number and the gate cannot differ.

    python models/over_zero/scripts/best_line_slate.py
    python models/over_zero/scripts/best_line_slate.py --days 3 --threshold 1.75
    python models/over_zero/scripts/best_line_slate.py --qualify shopped

Caveat: shopping was never backtested for this model. The 64.5% headline is a
single-line-source number; taking a better total can only help at an unchanged
signal, but it is an execution improvement, not a re-validated edge.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "models" / "over_zero" / "v1"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from oddsapi_flatten import cfbd_schools, school_of  # noqa: E402
from censoring_bias import censoring_bias, fit_pipeline, implied_team_points  # noqa: E402
from run_on_project_data import DEFAULT_CSV, load  # noqa: E402
from pick_history import record_views  # noqa: E402

OUT_DIR = Path(os.environ["CFB_DATA_ROOT"]) / "processed" / "over_zero"
# the-odds-api book keys -> display names. Since 2026-09-11 this snapshot is the only feed:
# the Action Network scoreboard is no longer read (docs/odds-sources-an-vs-apis-2026-09-11.md).
OA_BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betrivers": "BetRivers",
            "betmgm": "BetMGM", "betonlineag": "BetOnline.ag", "bovada": "Bovada",
            "lowvig": "LowVig.ag", "betus": "BetUS", "mybookieag": "MyBookie.ag"}
OA_SNAP_DIR = Path(os.environ["CFB_DATA_ROOT"]) / "ingest" / "oddsapi"
# Only the regulated books vote in the fair spread and fair total. The 1.75 gate was
# calibrated on games.csv -- one CFBD line per game -- and the regulated median is the closest
# live stand-in for that number; until 2026-09-11 it was these four plus Caesars, read live
# from Action Network. The offshore books get their own single-book views, where the number
# is openly one book's number. To let them vote, add them here -- and recalibrate.
FAIR_BOOKS = ("DraftKings", "FanDuel", "BetRivers", "BetMGM")
BOOKS = FAIR_BOOKS + tuple(n for n in OA_BOOKS.values() if n not in FAIR_BOOKS)
OUTLIER_PTS = 2.5        # a book this far off the median of all books is ignored (n >= 3)
MIN_ODDS = -120          # the model's own price gate (MODEL_GUIDE: over at -120 or better)
ET = ZoneInfo("America/New_York")
COLUMNS = ["run_at", "kick", "home", "away", "n_books", "spread_fair", "total_fair",
           "total_range", "dog_implied", "bias_fair", "p_over_fair", "pick", "best_total",
           "best_book", "best_odds", "bias_best", "playable", "bet_to", "qualify"]


def oa_games(now: datetime, days: int) -> tuple[pd.DataFrame, str | None]:
    """Per-book spread and total for games kicking off in the next `days` days.

    Read from the latest the-odds-api snapshot on disk, never fetched: `CFB-Odds-Snapshot`
    pulls every 6 hours plus Saturdays (see `docs/oddsapi-ingest.md`) and the free plan is 500
    credits a month, so a slate run costs no credits. Every number is therefore AS OF
    `pulled_at`, which the board prints beside every view.
    """
    snaps = sorted(OA_SNAP_DIR.glob("odds_americanfootball_ncaaf_*.json"))
    if not snaps:
        print(f"  no the-odds-api snapshot in {OA_SNAP_DIR}; nothing to score", file=sys.stderr)
        return pd.DataFrame(), None
    payload = json.loads(snaps[-1].read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(payload["pulled_at"].replace("Z", "+00:00"))
    age_h = (now - as_of).total_seconds() / 3600
    print(f"  the-odds-api snapshot {snaps[-1].name}: {len(payload['events'])} events, "
          f"{age_h:.1f}h old")
    if age_h > 12:
        print(f"  WARNING: snapshot is {age_h:.0f}h old -- is CFB-Odds-Snapshot still "
              f"running?", file=sys.stderr)

    schools = cfbd_schools()
    lo, hi = now, now + timedelta(days=days)
    rows = []
    for e in payload["events"]:
        ko = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if not (lo <= ko <= hi):
            continue
        spreads, totals = {}, {}
        for b in e.get("bookmakers", []):
            name = OA_BOOKS.get(b.get("key"))
            if name is None:          # a new book must be named before it reaches the board
                print(f"  the-odds-api: unmapped book {b.get('key')!r}, not counted",
                      file=sys.stderr)
                continue
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    if o.get("point") is None or o.get("price") is None:
                        continue
                    # The home team's own outcome carries the home spread in betting sign
                    # (negative = home favored), the convention the model was fit on.
                    if m.get("key") == "spreads" and o.get("name") == e["home_team"]:
                        spreads[name] = float(o["point"])
                    elif m.get("key") == "totals" and o.get("name") == "Over":
                        totals[name] = (float(o["point"]), int(o["price"]))
        rows.append({"kick": ko,
                     # CFBD's spelling of the school, so the board reads as it always has; a
                     # name the strip cannot resolve keeps the vendor's rather than vanishing.
                     "home": school_of(e["home_team"], schools) or e["home_team"],
                     "away": school_of(e["away_team"], schools) or e["away_team"],
                     "spreads": spreads, "totals": totals})
    return pd.DataFrame(rows), payload["pulled_at"]


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
        out.update({"best_total": total, "best_book": book,
                    "best_odds": -neg_odds, "playable": True})
    else:
        best = v.idxmin()
        out.update({"best_total": float(v[best]), "best_book": best,
                    "best_odds": totals[best][1], "playable": False})
    return out


def bias_of(spread: np.ndarray, total: np.ndarray, fit) -> np.ndarray:
    dog, fav = implied_team_points(np.abs(spread), total)
    _, bias = censoring_bias(dog, fav, fit.tobit_dog.sigma, fit.tobit_fav.sigma)
    return bias


def bet_to_total(spread: np.ndarray, fit, threshold: float) -> np.ndarray:
    """Highest nonnegative half-point total with bias strictly above threshold.

    Hold each view's spread and fitted sigmas fixed. Bias decreases with total,
    so integer bisection finds the final qualifying half-point without rounding
    an equality up into a playable line. NaN means no nonnegative total qualifies.
    """
    spread = np.asarray(spread, dtype=float)
    if not np.isfinite(threshold) or threshold <= 0 or not np.isfinite(spread).all():
        raise ValueError('Finite spreads and a positive finite threshold are required')
    low = np.full(spread.shape, -1, dtype=np.int64)
    high = np.ceil(2 * (np.abs(spread) + 20 * max(fit.tobit_dog.sigma, fit.tobit_fav.sigma))).astype(np.int64)
    high = np.maximum(high, 1)
    while np.any(bias_of(spread, high / 2, fit) > threshold):
        high *= 2
    while np.any(high - low > 1):
        mid = (low + high) // 2
        qualifies = bias_of(spread, mid / 2, fit) > threshold
        active = high - low > 1
        low = np.where(active & qualifies, mid, low)
        high = np.where(active & ~qualifies, mid, high)
    return np.where(low >= 0, low / 2, np.nan)


def fit_model(fit_csv: Path, fit_seasons):
    """The Arscott pipeline, plus the fit sample's underdog-implied support."""
    spread_est, totals_est, fav_pts, dog_pts = load(fit_csv, fit_seasons)
    print(f"Fit on {spread_est.size:,} games from seasons "
          f"{min(fit_seasons)}-{max(fit_seasons)}")
    return (fit_pipeline(spread_est, totals_est, fav_pts, dog_pts),
            (totals_est - spread_est) / 2)


def score(games: pd.DataFrame, fit, fit_dog: np.ndarray, run_at: str, threshold: float,
          book: str | None = None, quiet: bool = False,
          max_spread: float = np.inf, qualify: str = "fair") -> pd.DataFrame:
    """One view of an already-fetched slate: shopped across books, or one book alone.

    `qualify` picks which total the 1.75 gate reads. "fair" is the calibrated rule.
    "shopped" gates on the best total instead, which can only add picks -- see the
    module docstring for why that is selection on book noise, not a better signal.
    Either way `bias_fair`/`p_over_fair` carry the number that gated, so every
    consumer of those columns stays honest without knowing the mode.
    """
    # One book means no shopping and no cross-book fair: that book IS both numbers.
    need = 1 if book else 2

    rows = []
    for g in games.itertuples():
        totals, spreads = g.totals, g.spreads
        if book:
            totals = {book: totals[book]} if book in totals else {}
            spreads = {book: spreads[book]} if book in spreads else {}
        else:
            # Only FAIR_BOOKS set the number the 1.75 gate reads; the offshore books reach
            # the board through their own views.
            totals = {b: q for b, q in totals.items() if b in FAIR_BOOKS}
            spreads = {b: q for b, q in spreads.items() if b in FAIR_BOOKS}
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
    t["qualify"] = qualify
    if qualify == "shopped":
        # The gate reads the shopped total. bias_best >= bias_fair on every row, so this
        # is a superset of the calibrated picks, never a different set.
        t["bias_fair"] = t.bias_best
        t["p_over_fair"] = fit.probit.win_prob(t.bias_best.to_numpy())
    # Past max_spread the game is scored but never picked: the fit has 42 games in 13k
    # with |spread| > 50, so the bias out there is an extrapolation.
    t["pick"] = np.where((t.bias_fair > threshold) & (t.spread_fair.abs() <= max_spread),
                         "OVER", "")
    t["bet_to"] = bet_to_total(t.spread_fair.to_numpy(), fit, threshold)
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
                threshold: float, fit, oa_as_of: str | None = None) -> None:
    """Every view in one payload, for a static site that switches between them.

    The board is a build-time import, not a fetch, so all six views ship together. Kickoffs
    are pre-formatted in Eastern -- the reader's frame, and the one the board has always
    used; leaving them in UTC would move every Saturday night game to Sunday.
    """
    payload = {"run_at": run_at, "threshold": threshold, "min_odds": MIN_ODDS,
               # The books that vote in the fair number, not every book with a view.
               "books": list(FAIR_BOOKS), "views": {},
               "betToBySpread": [float(x) if np.isfinite(x) else None
                                 for x in bet_to_total(np.arange(201) / 2, fit, threshold)]}
    market = views.get("Best lines", pd.DataFrame())
    market_spreads = {(r.away, r.home, r.kick): float(r.spread_fair)
                      for r in market.itertuples()}
    for name, t in views.items():
        # The board reads chronologically; bias order is the terminal report's job.
        picks = t[t.pick == "OVER"].sort_values("kick") if not t.empty else t
        # `scored` is how many games the view could price at all. A book that posts a total
        # but no spread scores nothing -- the model needs both -- and an empty board should
        # say that rather than imply the book had no qualifying games.
        # Every price on the board is as of the snapshot, not this run.
        payload["views"][name] = {
            "scored": len(t),
            "asOf": oa_as_of or run_at,
            "picks": [
            {"date": r.kick.astimezone(ET).strftime("%b %d"),
             "time": et_clock(r.kick),
             "away": r.away, "home": r.home, "total": r.total_fair, "spread": r.spread_fair,
             "marketSpread": market_spreads.get((r.away, r.home, r.kick)),
             "bias": round(r.bias_fair, 3), "probability": round(r.p_over_fair * 100, 2),
             "dogImplied": r.dog_implied, "bestTotal": r.best_total, "bestBook": r.best_book,
             "betTo": float(r.bet_to) if np.isfinite(r.bet_to) else None,
             "bestOdds": int(r.best_odds), "books": int(r.n_books), "playable": bool(r.playable)}
                for r in picks.itertuples()]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    counts = ", ".join(f"{k} {len(v['picks'])}/{v['scored']}" for k, v in payload["views"].items())
    print(f"Wrote {path} ({counts})")


def report(t: pd.DataFrame, threshold: float, book: str | None = None,
           max_spread: float = np.inf, qualify: str = "fair") -> None:
    if t.empty:
        print(f"No games with {book or 'two or more books'} quoting both markets.")
        return
    print(f"\n{'home':<22} {'away':<22} {'gate':>6} {'bias':>6} {'P(over)':>8} "
          f"{'best':>6} {'book':<11} {'odds':>6} pick")
    for r in t.itertuples():
        flag = "" if r.playable else "  (no price at -120 or better)"
        # The gate column shows the total the bias beside it was computed from.
        gate = r.best_total if qualify == "shopped" else r.total_fair
        print(f"{r.home:<22} {r.away:<22} {gate:>6.1f} {r.bias_fair:>6.2f} "
              f"{r.p_over_fair * 100:>7.2f}% {r.best_total:>6.1f} {r.best_book:<11} "
              f"{r.best_odds:>+6d} {r.pick}{flag if r.pick else ''}")
    in_cap = t.spread_fair.abs() <= max_spread
    on_fair = int((t.pick == "OVER").sum())
    on_best = int(((t.bias_best > threshold) & in_cap).sum())
    playable = int(((t.pick == "OVER") & t.playable).sum())
    capped = int(((t.bias_fair > threshold) & ~in_cap).sum())
    label = (f"{book}'s total" if book else
             "the shopped total" if qualify == "shopped" else "the fair total")
    cap = f" ({capped} more clear it but sit past the {max_spread:g} spread cap)" if capped else ""
    print(f"\n{on_fair}/{len(t)} games clear bias > {threshold} on {label}{cap}; "
          f"{playable} of those have a price at {MIN_ODDS} or better.")
    if book:
        print(f"Single-book run: no shopping, and {book}'s own number is the gate rather "
              f"than the market's -- one book's noise passes straight through it.")
    elif qualify == "shopped":
        # bias_best >= bias_fair rowwise, so these picks are a superset of the fair rule's.
        print(f"NOT THE CALIBRATED RULE: the gate read the shopped total, so the min of N "
              f"noisy totals sets it, and that min sits below the market. These picks are a "
              f"superset of the fair-total rule's, and the extra ones cleared on book noise "
              f"rather than signal. Nothing here is comparable to the backtested 64.5%, "
              f"which is a fair-total figure. Run without --qualify to see the gap.")
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
    ap.add_argument("--max-spread", type=float, default=np.inf,
                    help="no pick when |spread| exceeds this; the fit thins out past 50")
    ap.add_argument("--book", choices=sorted(BOOKS),
                    help="score one book's own number instead of shopping across all of "
                         "them; the fair and best columns collapse onto that book")
    ap.add_argument("--qualify", choices=("fair", "shopped"), default="fair",
                    help="which total the bias gate reads. 'fair' is the calibrated rule. "
                         "'shopped' gates on the best total instead: it only ever adds "
                         "picks, because the min of N noisy totals sits below the market, "
                         "and its record is not comparable to the backtested 64.5%%")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="'' to skip writing")
    ap.add_argument("--json", help="also write every view -- shopped plus each book on its "
                                   "own -- to this path, for the signal board to import")
    args = ap.parse_args()
    if args.qualify == "shopped" and args.book:
        ap.error("--qualify shopped needs a market to shop: with --book the fair and best "
                 "totals are the same number, so the gate is unchanged")

    seasons = list(range(args.fit_from, args.season))
    fit, fit_dog = fit_model(Path(args.fit_csv), seasons)
    now = datetime.now(timezone.utc)
    run_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    games, oa_as_of = oa_games(now, args.days)
    print(f"{len(games)} games kicking off in the next {args.days} days, priced as of {oa_as_of}")

    cap = args.max_spread
    t = score(games, fit, fit_dog, run_at, args.threshold, args.book, max_spread=cap,
              qualify=args.qualify)
    report(t, args.threshold, args.book, cap, args.qualify)

    # Preserve all book qualifications on every run, including terminal-only runs.
    # Only the shopped view has two totals to choose between, so --qualify applies there
    # alone; a single-book view collapses fair and best onto that book's number.
    views = {"Best lines": t if not args.book else
             score(games, fit, fit_dog, run_at, args.threshold, quiet=True, max_spread=cap)}
    for name in BOOKS:
        views[name] = t if args.book == name else \
            score(games, fit, fit_dog, run_at, args.threshold, name, quiet=True, max_spread=cap)
    # Only the shopped view's gate actually moved, so only its rows carry the other model
    # name. KEY already carries `model`, so the two rules accumulate side by side instead
    # of overwriting. The single-book views are fair-gated in either mode -- one book's
    # fair and best totals are the same number -- so they stay `slate` and would lie if
    # this tagged them otherwise.
    if args.qualify == "shopped":
        shopped = {"Best lines": views["Best lines"]}
        record_views(shopped, run_at, args.threshold, oa_as_of, model="slate-shopped")
        record_views({k: v for k, v in views.items() if k != "Best lines"},
                     run_at, args.threshold, oa_as_of)
    else:
        record_views(views, run_at, args.threshold, oa_as_of)
    if args.json:
        export_json(views, Path(args.json), run_at, args.threshold, fit, oa_as_of)

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
    tot = {"DraftKings": (44.5, -110), "FanDuel": (43.5, -115),
           "BetRivers": (43.5, -108), "BetMGM": (52.0, -110)}
    s = shop_total(tot)
    # 52.0 is 8 from the median -> guarded out; best playable is the 43.5 at -108.
    assert s["n_books"] == 3 and s["total_fair"] == 43.5, s
    assert (s["best_total"], s["best_book"], s["best_odds"]) == (43.5, "BetRivers", -108), s
    assert s["playable"] is True, s
    # Nothing at -120 or better -> still reported, flagged unplayable.
    s2 = shop_total({"DraftKings": (44.5, -135), "FanDuel": (45.0, -130)})
    assert s2["playable"] is False and s2["best_total"] == 44.5, s2
    assert not shop_total({"DraftKings": (44.5, -110)}), "one book is not a market"
    # ...unless the run asked for that one book, where fair and best are the same number.
    s1 = shop_total({"DraftKings": (44.5, -110)}, 1)
    assert s1["total_fair"] == s1["best_total"] == 44.5 and s1["n_books"] == 1, s1
    # Two books straddling: the fair total is the posted 56.5, not the synthetic 56.0.
    s3 = shop_total({"DraftKings": (55.5, -110), "FanDuel": (56.5, -110)})
    assert s3["total_fair"] == 56.5 and s3["best_total"] == 55.5, s3
    # --qualify wiring: a lower total raises the bias, so the shopped gate can only ever
    # be a superset. Pick a threshold between the two biases -- the fair rule must leave
    # this row unpicked and the shopped rule must pick it, or the flag is wired backwards.
    stub = SimpleNamespace(tobit_dog=SimpleNamespace(sigma=10.0),
                           tobit_fav=SimpleNamespace(sigma=10.0))
    spread, fair_total, best_total = np.array([-40.5]), np.array([56.5]), np.array([55.5])
    b_fair = bias_of(spread, fair_total, stub)[0]
    b_shop = bias_of(spread, best_total, stub)[0]
    assert b_shop > b_fair, (b_fair, b_shop)
    mid = (b_fair + b_shop) / 2
    assert not b_fair > mid and b_shop > mid, "gate must follow --qualify"
    # Spreads break the other way -- the smaller magnitude, which also lowers the bias.
    sp = pd.Series({"DraftKings": -45.5, "FanDuel": -44.5})
    assert conservative_median(sp.abs(), high=False) == 44.5

    # oa_games: one row per event in the window, schools in CFBD's spelling, the home side's
    # spread and the over's total per book, and the snapshot's own timestamp.
    import tempfile
    global OA_SNAP_DIR
    saved = OA_SNAP_DIR
    with tempfile.TemporaryDirectory() as tmp:
        OA_SNAP_DIR = Path(tmp)
        (OA_SNAP_DIR / "odds_americanfootball_ncaaf_20260911T060004Z.json").write_text(json.dumps({
            "pulled_at": "2026-09-11T06:00:04Z", "events": [{
                "commence_time": "2026-09-12T23:30:00Z", "home_team": "Miami Hurricanes",
                "away_team": "Florida A&M Rattlers", "bookmakers": [{"key": "draftkings", "markets": [
                    {"key": "spreads", "outcomes": [
                        {"name": "Miami Hurricanes", "point": -57.5, "price": -110},
                        {"name": "Florida A&M Rattlers", "point": 57.5, "price": -110}]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 62.5, "price": -108},
                        {"name": "Under", "point": 62.5, "price": -112}]}]}]}]}), encoding="utf-8")
        games, as_of = oa_games(datetime(2026, 9, 11, 12, tzinfo=timezone.utc), 8)
    OA_SNAP_DIR = saved
    assert as_of == "2026-09-11T06:00:04Z" and len(games) == 1, games
    g = games.iloc[0]
    assert g.spreads == {"DraftKings": -57.5} and g.totals == {"DraftKings": (62.5, -108)}, (g.spreads, g.totals)
    assert (g.home, g.away) == ("Miami", "Florida A&M"), (g.home, g.away)
    print("checks pass")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _check()
    else:
        raise SystemExit(main())
