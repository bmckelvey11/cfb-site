"""This week's slate: every line-movement model on the latest Prediction Tracker snapshot,
next to the live book fair and the best number at each sportsbook.

What each column is (all spreads in Prediction Tracker's sign: POSITIVE = home favored):

  open_pt      PT's recorded opener (often a months-old look-ahead number for early weeks)
  line_pt      the market line at the moment PT compiled the snapshot
  book_fair    median home spread across real books RIGHT NOW (FanDuel, BetMGM, Caesars,
               Bet365, Pinnacle), after the outlier guard
  consensus    the model consensus: mean of the top-20 models by prior MOVEMENT skill
  E4 .. E14    each movement model's predicted CLOSE, fit on the whole archive with the
               opener as anchor (research/spread/docs/line-movement-results.md)
  pred_close   median of the model columns -- a summary, not another model
  move_vs_fair pred_close - book_fair: where the models say the line still has to go.
               Positive = toward the home side being favored by more.
  best_home / best_away   the most favorable posted number for each side, and its book

Everything here is anchored on the OPENER because that is what the archive could validate.
The archive says the move from the opener is predictable (gamma 0.30, R^2 up to 0.25) and
worth 2-4 points of CLV AT THE OPENER. It says nothing yet about how much of that is left at
the price you can get today; that is version B of the pre-registration, and this script's
forward log is its data. Treat move_vs_fair as the signal to grade, not a bet.

    python research/spread/scripts/weekly_slate.py              # latest snapshot
    python research/spread/scripts/weekly_slate.py --snapshot <path> --no-books
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402
import predict_upcoming as pu  # noqa: E402
import collect_line_timing as clt  # noqa: E402

BENCH = "lineopen"
# Modal hyperparameter choice across the 20 walk-forward seasons of the movement runs
# (version A for E6; amendment A2 for the rest). E13 (Hedge) is omitted: weakest method and
# it needs sequential state that does not apply to a one-shot live fit.
PARAMS = {"E6": 10000.0, "E7": "all", "E8": 0.3, "E9": 1, "E10": 1.0, "E11": 0.4,
          "E12": (10.0, 0.1), "E14": 1}
MODEL_COLS = ["E4", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E14"]

REAL_BOOKS = {"49": "Pinnacle", "68": "FanDuel", "69": "BetMGM", "71": "Caesars", "75": "Bet365"}
OUTLIER_PTS = 2.5          # a book > this far from the median of all books is ignored (n >= 3)
ODDS_WINDOW = (-135, 125)
KEY_NUMBERS = (3, 7)
ET = ZoneInfo("America/New_York")
OUT = base.OUT_DIR
FORWARD_LOG = OUT / "movement_forward_log.csv"

# Prediction Tracker home-team spellings that do not normalize onto Action Network's.
ALIASES = {"ga tech": "georgia tech", "s carolina": "south carolina", "s florida": "south florida",
           "jmu": "james madison", "ole miss": "mississippi", "e michigan": "eastern michigan",
           "west va": "west virginia", "troy": "troy state", "w michigan": "western michigan",
           "c michigan": "central michigan", "n illinois": "northern illinois",
           "boston col": "boston college", "ok state": "oklahoma state", "la tech": "louisiana tech",
           "coastal car": "coastal carolina", "fl atlantic": "florida atlantic",
           "ul monroe": "louisiana-monroe", "la-monroe": "louisiana-monroe",
           # Prediction Tracker's own abbreviations
           "eastern mich": "eastern michigan", "western mich": "western michigan",
           "central mich": "central michigan", "northern ill": "northern illinois",
           "miami (ohio)": "miami (oh)", "southern miss": "southern mississippi",
           # road-side gaps: harmless while only the home name had to resolve, but the
           # both-teams join drops the game outright when the road name does not
           "e carolina": "east carolina", "w kentucky": "western kentucky",
           "umass": "massachusetts", "kent": "kent state", "fiu": "florida intl",
           "sam houston": "sam houston state"}


# ------------------------------------------------------------------------------ models


def fit_movement_models(hist, models, live):
    """Every movement model, fit on the whole archive, predicting the CLOSE for `live` rows.

    `hist` and `live` are in archive sign convention; predictions come back in margin space,
    which equals PT's raw sign (positive = home favored).
    """
    hist = hist.copy()
    hist["y"] = -hist["line"].to_numpy(float)                   # target: the close
    usable = [m for m in models if m not in pu.MARKET_LINES and m in live.columns]
    skill = base.prior_skill(hist, usable, BENCH, int(hist.season.max()))
    active = [m for m in usable if live[m].notna().any()]
    a = sweep.Anchor(hist, live, BENCH)
    if not a.usable:
        raise SystemExit("anchor could not be fitted")
    cols, _ = sweep.regressor_cols(hist, live, usable)

    preds = {"R0": a.r0_te}
    keep = sweep.screened(skill, active, base.SCREEN_K)
    d_tr, _ = sweep.deviations(hist, keep, BENCH)
    d_te, _ = sweep.deviations(live, keep, BENCH)
    preds["E4"], gamma = sweep.gamma_fit(a, np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1))
    consensus = -live[BENCH].to_numpy(float) + np.nanmean(d_te, axis=1)

    notes = {}
    for m, p in PARAMS.items():
        try:
            pred, coef = sweep.FITTERS[m](a, hist, live, cols, active, skill, BENCH, p)
        except Exception as exc:  # a method that cannot fit is reported, not fatal
            pred, coef = None, float("nan")
            notes[m] = f"{type(exc).__name__}: {exc}"
        preds[m] = np.full(len(live), np.nan) if pred is None else np.asarray(pred, float)
        notes.setdefault(m, f"coef {coef:+.3f}")
    return preds, consensus, keep, gamma, len(active), notes


# ------------------------------------------------------------------------------- books


def norm(name: str) -> str:
    s = str(name).lower().replace(".", "").replace("(fla)", "(fl)").strip()
    s = re.sub(r"\bst\b", "state", s)
    s = re.sub(r"\s+", " ", s)
    return ALIASES.get(s, s)


def live_books(now: datetime) -> pd.DataFrame:
    """Per-book home spreads for games kicking off in the next eight days, from Action Network."""
    lo, hi = now - timedelta(days=1), now + timedelta(days=8)
    # AN's week numbering does not match PT's; scan a few weeks and filter by kickoff.
    wk_guess = max(1, int((now - datetime(now.year, 8, 25, tzinfo=timezone.utc)).days // 7) + 1)
    rows = []
    for week in range(max(1, wk_guess - 1), wk_guess + 3):
        try:
            payload = json.loads(clt._get(clt.AN_SCOREBOARD,
                                          {"season": now.year, "week": week, "seasonType": "reg"}))
        except Exception as exc:
            print(f"  AN week {week}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        for g in payload.get("games", []):
            ko = datetime.fromisoformat(g["start_time"].replace("Z", "+00:00"))
            if not (lo <= ko <= hi):
                continue
            teams = {t["id"]: t for t in g.get("teams", [])}
            home = teams.get(g["home_team_id"], {})
            road = teams.get(g["away_team_id"], {})
            quotes = {}
            for book, b in (g.get("markets") or {}).items():
                if book not in REAL_BOOKS:
                    continue
                for s in (b.get("event") or {}).get("spread", []) or []:
                    if (s.get("side") == "home" and not s.get("is_live") and not s.get("is_alt_market")
                            and s.get("value") is not None and s.get("odds") is not None
                            and ODDS_WINDOW[0] <= s["odds"] <= ODDS_WINDOW[1]):
                        quotes[book] = (float(s["value"]), int(s["odds"]))
            rows.append({"event_id": g["id"], "kick": ko, "an_home": home.get("display_name"),
                         "an_road": road.get("display_name"),
                         "key": norm(home.get("display_name", "")),
                         "rkey": norm(road.get("display_name", "")), "quotes": quotes})
        time.sleep(0.5)
    return pd.DataFrame(rows).drop_duplicates("event_id")


def shop(quotes: dict) -> dict:
    """Book fair and best number per side, in AN sign (negative = home favored)."""
    if len(quotes) < 2:
        return {}
    v = pd.Series({b: q[0] for b, q in quotes.items()})
    if len(v) >= 3:
        # the median of ALL books is robust to one mis-post; "median of the others" is not,
        # because with three books the outlier drags the other two's median toward itself
        kept = v[(v - v.median()).abs() <= OUTLIER_PTS]
        if len(kept) >= 2:
            v = kept
    return {"fair_an": v.median(), "n_books": len(v), "range": v.max() - v.min(),
            "best_home_an": v.max(), "best_home_book": REAL_BOOKS[v.idxmax()],
            "best_home_odds": quotes[v.idxmax()][1],
            "best_away_an": v.min(), "best_away_book": REAL_BOOKS[v.idxmin()],
            "best_away_odds": quotes[v.idxmin()][1]}


def crosses_key(a: float, b: float) -> bool:
    lo, hi = min(abs(a), abs(b)), max(abs(a), abs(b))
    return any(lo <= k <= hi and lo != hi for k in KEY_NUMBERS)


# --------------------------------------------------------------------------------- main


def build(snapshot: Path, with_books: bool) -> pd.DataFrame:
    hist, models = base.load()
    hist = hist[hist["line"].notna() & hist[BENCH].notna()].reset_index(drop=True)
    live_raw = pd.read_csv(snapshot).drop_duplicates(["road", "home"], keep="last").reset_index(drop=True)
    # PT occasionally mis-keys an opener (UCLA-Cal 2026 wk2: -55 against a line of -2). Every
    # model anchors on the opener, so a typo there poisons the row. Treat a >14-point gap
    # between opener and current line as a missing opener and anchor on the current line.
    gap = (live_raw["lineopen"] - live_raw["line"]).abs()
    live_raw["open_suspect"] = gap > 14
    live_raw.loc[live_raw.open_suspect, "lineopen"] = live_raw.loc[live_raw.open_suspect, "line"]
    live = pu.to_archive_convention(live_raw.drop(columns=["open_suspect"]))
    live["season"] = int(hist.season.max()) + 1
    live = live.reset_index(drop=True)

    preds, consensus, screened, gamma, n_active, notes = fit_movement_models(hist, models, live)
    print(f"snapshot {snapshot.name}: {len(live)} games, {n_active} live models, "
          f"screened to {len(screened)}; E4 gamma on movement {gamma:+.3f}")
    for m, n in notes.items():
        print(f"  {m}: {n}")

    t = pd.DataFrame({"road": live_raw["road"], "home": live_raw["home"],
                      "open_pt": live_raw[BENCH].astype(float), "line_pt": live_raw["line"].astype(float),
                      "open_suspect": live_raw["open_suspect"], "consensus": np.round(consensus, 1)})
    for m in MODEL_COLS:
        t[m] = np.round(preds[m], 1)
    t["pred_close"] = t[MODEL_COLS].median(axis=1).round(1)
    t["move_vs_line"] = (t.pred_close - t.line_pt).round(1)

    if with_books:
        now = datetime.now(timezone.utc)
        books = live_books(now)
        # Both teams must match. Home alone pairs a PT game with whatever AN game shares its
        # home team -- on an off-week snapshot that silently fills book_fair from a different
        # matchup (2026 wk1 snapshot drew wk2 numbers: Louisville-Ole Miss took Charlotte's -47.5).
        t["key"] = t.home.map(norm)
        t["rkey"] = t.road.map(norm)
        t = t.merge(books, on=["key", "rkey"], how="left")
        s = pd.DataFrame([shop(q) if isinstance(q, dict) else {} for q in t.quotes])
        t = pd.concat([t.drop(columns=["quotes"]), s], axis=1)
        # AN sign -> PT sign. When nothing matched, shop() yields no columns at all, so these
        # must still exist as float NaN or every downstream arithmetic turns object-dtype.
        for c in ("fair_an", "best_home_an", "best_away_an"):
            t[c.replace("_an", "_pt")] = -t[c] if c in t else np.nan
        for c in ("range", "n_books", "event_id"):
            if c not in t:
                t[c] = np.nan
        t["book_fair"] = t["fair_pt"]
        t["move_vs_fair"] = (t.pred_close - t.book_fair).round(1)
        # gain in points for each side vs fair, and key-number crossing
        t["home_gain"] = (t.fair_pt - t.best_home_pt).round(2)
        t["away_gain"] = (t.best_away_pt - t.fair_pt).round(2)
        t["home_key"] = [crosses_key(f, b) if np.isfinite(f) and np.isfinite(b) else False
                         for f, b in zip(t.fair_pt, t.best_home_pt)]
        t["away_key"] = [crosses_key(f, b) if np.isfinite(f) and np.isfinite(b) else False
                         for f, b in zip(t.fair_pt, t.best_away_pt)]
        t["kick_et"] = pd.to_datetime(t.kick, utc=True).dt.tz_convert(ET).dt.strftime("%a %m-%d %I:%M%p")
        unmatched = t[t.event_id.isna()][["road", "home"]].values.tolist()
        if unmatched:
            print(f"  no Action Network match for {len(unmatched)}/{len(t)} games: "
                  f"{unmatched[:8]}{' ...' if len(unmatched) > 8 else ''}")
        if len(unmatched) == len(t):
            print("  ALL games unmatched -- the snapshot is almost certainly a different week "
                  "than the books. book_fair/move_vs_fair are unavailable, not zero.")
    t.insert(0, "snapshot", snapshot.name)
    t.insert(1, "captured_utc", snapshot.stem.split("_")[-1])
    return t


def report(t: pd.DataFrame, with_books: bool) -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    sort_col = "move_vs_fair" if with_books and "move_vs_fair" in t else "move_vs_line"
    view = ["road", "home", "open_pt", "line_pt"] + (["book_fair"] if with_books else []) + \
           ["consensus"] + MODEL_COLS + ["pred_close", sort_col]
    print(f"\n=== LINE: predicted close by model (PT sign, + = home favored), sorted by |{sort_col}| ===")
    print(t.sort_values(sort_col, key=lambda s: s.abs(), ascending=False)[view].to_string(index=False))
    if with_books and "home_gain" in t:
        print("\n=== SHOP: best posted number vs book fair (gain >= 0.5 pts; KEY = crosses 3 or 7) ===")
        for _, r in t.sort_values(["home_gain", "away_gain"], ascending=False).iterrows():
            if pd.notna(r.home_gain) and r.home_gain >= 0.5:
                print(f"  {r.home:18s} {(-r.best_home_pt):+.1f} @ {r.best_home_book} ({r.best_home_odds:+.0f})"
                      f"  fair {(-r.fair_pt):+.1f}  gain {r.home_gain:.2f}{'  KEY' if r.home_key else ''}")
            if pd.notna(r.away_gain) and r.away_gain >= 0.5:
                print(f"  {r.road:18s} {r.best_away_pt:+.1f} @ {r.best_away_book} ({r.best_away_odds:+.0f})"
                      f"  fair {r.fair_pt:+.1f}  gain {r.away_gain:.2f}{'  KEY' if r.away_key else ''}")
        rg = t.range.dropna()
        if len(rg):
            print(f"\n  range across real books: median {rg.median():.2f}; "
                  f"{int((rg >= 1).sum())} of {len(rg)} games with >= 1 point of dispersion")


def append_forward_log(t: pd.DataFrame) -> int:
    """One row per game per snapshot, deduplicated on snapshot; this is version B's dataset."""
    keep = [c for c in t.columns if c not in ("quotes", "key", "rkey")]
    rec = t[keep].copy()
    rec["logged_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if FORWARD_LOG.exists():
        old = pd.read_csv(FORWARD_LOG)
        if (old.snapshot == rec.snapshot.iloc[0]).any():
            return 0
        rec = pd.concat([old, rec], ignore_index=True)
    rec.to_csv(FORWARD_LOG, index=False)
    return len(t)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--no-books", action="store_true", help="skip the live Action Network fetch")
    args = ap.parse_args()
    snap = args.snapshot or pu.latest_snapshot()
    t = build(snap, with_books=not args.no_books)
    report(t, with_books=not args.no_books)
    stamp = snap.stem.split("_")[-1]
    path = OUT / f"weekly_slate_{stamp}.csv"
    t.drop(columns=[c for c in ("quotes", "key", "rkey") if c in t]).to_csv(path, index=False)
    n = append_forward_log(t)
    print(f"\nwrote {path}; appended {n} rows to {FORWARD_LOG.name}")
    return 0


def _check() -> None:
    assert crosses_key(-2.5, -3.5) and crosses_key(6.5, 7.5) and not crosses_key(-10, -12)
    assert norm("Troy St.") == "troy state" and norm("Troy") == "troy state"
    assert norm("Eastern Mich.") == norm("E. Michigan") == "eastern michigan"
    # road-side names, which the both-teams join now depends on (PT spelling == AN spelling)
    assert norm("East Carolina") == norm("E. Carolina")
    assert norm("Western Kentucky") == norm("W. Kentucky")
    assert norm("Massachusetts") == norm("UMass")
    assert norm("Kent") == norm("Kent State")
    assert norm("Florida Intl.") == norm("FIU")
    assert norm("Sam Houston St.") == norm("Sam Houston")
    q = {"68": (-7.5, -110), "69": (-7.0, -110), "71": (18.0, -110)}
    s = shop(q)
    assert s["n_books"] == 2 and s["fair_an"] == -7.25, s   # Caesars' 18 was guarded out
    # the cross-game guard: same home team, different opponent must NOT inherit book numbers
    pt = pd.DataFrame({"key": ["ole miss"], "rkey": ["louisville"]})
    an = pd.DataFrame({"key": ["ole miss"], "rkey": ["charlotte"], "event_id": [1]})
    assert pt.merge(an, on=["key", "rkey"], how="left").event_id.isna().all()
    assert pt.merge(an, on="key", how="left").event_id.notna().all()   # the old, silent behaviour
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
