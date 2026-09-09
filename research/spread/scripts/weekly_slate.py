"""This week's slate: every line-movement model on the latest Prediction Tracker snapshot,
next to the live book fair and the best number at each sportsbook.

What each column is (all spreads in Prediction Tracker's sign: POSITIVE = home favored):

  open_pt      PT's recorded opener (often a months-old look-ahead number for early weeks)
  line_pt      the market line at the moment PT compiled the snapshot
  book_fair    median home spread across real books RIGHT NOW (DraftKings, FanDuel, BetMGM,
               BetRivers, Caesars), after the outlier guard
  <Book>_home / <Book>_odds   each book's posted home spread (PT sign) and its odds
  consensus    the model consensus: mean of the top-20 models by prior MOVEMENT skill
  E4 .. E14    each movement model's predicted CLOSE, fit on the whole archive with the
               opener as anchor (research/spread/docs/line-movement-results.md)
  pred_close   median of the model columns -- a summary, not another model
  move_vs_fair pred_close - book_fair: where the models say the line still has to go.
               Positive = toward the home side being favored by more.
  best_home / best_away   the most favorable posted number for each side, and its book
  side         which team E4 (the registered predictor, the one version B grades) says to
               take: home when E4 sits above the book fair, road when below
  side_line    the number to take for that side, from that side's perspective (+3.5 = getting
               3.5), at the best book; PT's line when no book matched
  side_book    where that number is posted
  side_odds    the price at that book
  our_line     E4's predicted close as a home spread in BETTING sign (negative = home favored),
               i.e. -E4; the one number to compare against a posted home line
  edge         |E4 - book fair| in points; the forward test grades bets at edge >= 1

Every run writes weekly_slate_<stamp>.csv and overwrites weekly_slate_latest.csv. With
`--book DraftKings` the side columns use that one book's number and price instead of the best
across books, the files get a `_draftkings` suffix, and the forward log is left alone.

    python research/spread/scripts/weekly_slate.py --book DraftKings

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
# Modal hyperparameter choice across the 20 walk-forward seasons of the movement runs:
# `chosen_params` in {CFB_DATA_ROOT}/processed/pt_movement.json (version A) and
# pt_movement_a2.json (the rest).
#
# Amendment A7 (2026-09-09) retired E6 from the served slate. Given a grid wide enough for the
# 1-SE rule to express itself (to 1e9), the rule modally picks lambda ~3e6 and E6 scores 0.0655
# -- below E4's 0.1537 on the same support. Its previously reported 0.2009 depended on the grid
# stopping near the R^2 peak; the estimator's own selection rule does not find that peak. A7's
# pre-registered "flat" branch (the curve sits within 1 SE across a median 3.0 decades of lambda)
# therefore fired: E6 leaves the slate rather than being served at a value the rule would not
# have chosen. E13 (Hedge) is omitted: weakest method and it needs sequential state that a
# one-shot live fit lacks.
PARAMS = {"E6": 3e6, "E7": "all", "E8": 0.3, "E9": 1, "E10": 1.0, "E11": 0.4,
          "E12": (10.0, 0.1), "E14": 1}
MODEL_COLS = ["E4", "E7", "E8", "E9", "E10", "E11", "E12", "E14"]   # feeds pred_close
# E6 is still COMPUTED and REPORTED -- prereg B1 requires it beside E4 in every version B read,
# and A7 retired it from serving, not from existence. It is out of MODEL_COLS so it no longer
# enters pred_close, and it is fitted at A7's modal 1-SE lambda (3e6), which is what the
# registered estimator actually chooses once the grid is wide enough to let the rule express
# itself -- not A4's 5e4, which A7 showed the rule would never have picked.
REPORTED_COLS = MODEL_COLS + ["E6"]
MODEL_SET_VERSION = 3   # 2026-09-09: E6 retired from the slate (amendment A7, flat branch)

# Action Network book ids, names from AN's own /web/v1/books (2026-09-08). Until then this map
# said Pinnacle/FanDuel/BetMGM/Caesars/Bet365 -- every label was wrong; the ids were right.
REAL_BOOKS = {"49": "Caesars", "68": "DraftKings", "69": "FanDuel", "71": "BetRivers", "75": "BetMGM"}
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
           "sam houston": "sam houston state",
           # 2026 week 3: 13 of 49 games unmatched on these AN spellings alone
           "nd state": "north dakota state", "ga southern": "georgia southern",
           "uconn": "connecticut", "app state": "appalachian state",
           "sac state": "sacramento state", "n mexico state": "new mexico state",
           "k state": "kansas state", "jax state": "jacksonville state",
           "ucf": "central florida", "utsa": "texas-san antonio",
           "s alabama": "south alabama", "louisiana": "louisiana-lafayette",
           "va tech": "virginia tech"}


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


def build(snapshot: Path, with_books: bool, book: str | None = None) -> pd.DataFrame:
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
    for m in REPORTED_COLS:
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
        qs = [q if isinstance(q, dict) else {} for q in t.quotes]
        s = pd.DataFrame([shop(q) for q in qs])
        t = pd.concat([t.drop(columns=["quotes"]), s], axis=1)
        for bid, name in REAL_BOOKS.items():           # every book's own number, PT sign
            t[f"{name}_home"] = [-q[bid][0] if bid in q else np.nan for q in qs]
            t[f"{name}_odds"] = [q[bid][1] if bid in q else np.nan for q in qs]
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
    t = add_side(t, book)
    t.insert(0, "snapshot", snapshot.name)
    t.insert(1, "captured_utc", snapshot.stem.split("_")[-1])
    # Which PARAMS/MODEL_COLS definition produced pred_close -- bumped whenever either changes
    # (amendment A4, 2026-09-08: E6 moved from lambda=1e4 to its A4 modal 5e4). A predictor that
    # changes mid-forward-test silently redefines the graded quantity, so every row is tagged.
    t["model_set_version"] = MODEL_SET_VERSION
    return t


def add_side(t: pd.DataFrame, book: str | None = None) -> pd.DataFrame:
    """Which side E4 says to take, the number to take it at, its price, and the edge.

    PT sign: E4 above fair means the models favour the home team by more than the market,
    so take the home side; below, take the road side. The line is expressed from the chosen
    side's perspective (+3.5 = getting 3.5) so it reads like a slip. The side is always decided
    against the book fair; `book` only changes which number and price are shown -- that
    book's own, NaN where it has not posted -- instead of the best across books.
    """
    have_books = "fair_pt" in t and t.fair_pt.notna().any()
    fair = (t.fair_pt if have_books else t.line_pt).fillna(t.line_pt)
    gap = t.E4 - fair
    home = gap > 0
    if book:
        home_num = away_num = t[f"{book}_home"]
        home_odds = away_odds = t[f"{book}_odds"]
        home_book = away_book = pd.Series(book, index=t.index).where(home_num.notna(), "")
    elif have_books:
        home_num = t.best_home_pt.fillna(t.line_pt)
        away_num = t.best_away_pt.fillna(t.line_pt)
        home_odds, away_odds = t.best_home_odds, t.best_away_odds
        home_book = t.best_home_book.where(t.best_home_pt.notna(), "PT")
        away_book = t.best_away_book.where(t.best_away_pt.notna(), "PT")
    else:
        home_num = away_num = t.line_pt
        home_odds = away_odds = pd.Series(np.nan, index=t.index)
        home_book = away_book = pd.Series("PT", index=t.index)
    t["side"] = np.where(gap.isna() | (gap == 0), "", np.where(home, t.home, t.road))
    t["side_line"] = np.where(home, -home_num, away_num).round(1)
    t["side_book"] = np.where(home, home_book, away_book)
    t["side_odds"] = np.where(home, home_odds, away_odds)
    t.loc[t.side == "", ["side_line", "side_book", "side_odds"]] = [np.nan, "", np.nan]
    t["our_line"] = (-t.E4).round(1)
    t["edge"] = gap.abs().round(2)
    return t


def write_xlsx(t: pd.DataFrame, path: Path) -> None:
    """Two-sheet workbook. 'Slate' is the slip view in BETTING sign (negative = home favored):
    market numbers, our line, edge, the side to take and where, then each book's home number
    and price. 'Models' keeps every model column in PT sign, as printed."""
    def bet(col):        # PT sign -> betting sign, NaN-safe
        return -t[col] if col in t else pd.Series(np.nan, index=t.index)
    slate = pd.DataFrame({
        "Kick (ET)": t.get("kick_et", ""), "Road": t.road, "Home": t.home,
        "Open": bet("open_pt"), "Market": bet("line_pt"), "Book Fair": bet("book_fair"),
        "Our Line": t.our_line, "Edge": t.edge, "Side": t.side, "Take": t.side_line,
        "Book": t.side_book, "Odds": t.side_odds,
    })
    for b in REAL_BOOKS.values():
        slate[b] = bet(f"{b}_home")
        slate[f"{b} odds"] = t.get(f"{b}_odds", np.nan)
    slate = slate.sort_values("Edge", ascending=False)
    models = t[["road", "home", "open_pt", "line_pt"] + (["book_fair"] if "book_fair" in t else [])
               + ["consensus"] + REPORTED_COLS + ["pred_close"]]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        slate.to_excel(xw, sheet_name="Slate", index=False)
        models.to_excel(xw, sheet_name="Models (PT sign)", index=False)
        for ws in xw.sheets.values():
            ws.freeze_panes = "D2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    8, min(22, max(len(str(c.value or "")) for c in col) + 2))


def report(t: pd.DataFrame, with_books: bool) -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    sort_col = "move_vs_fair" if with_books and "move_vs_fair" in t else "move_vs_line"
    view = ["road", "home", "open_pt", "line_pt"] + (["book_fair"] if with_books else []) + \
           ["consensus"] + REPORTED_COLS + ["pred_close", sort_col] + \
           (["our_line", "edge"] if "our_line" in t else [])
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
    if "side" in t:
        print("\n=== SIDE: E4's side vs book fair, edge >= 1 (the forward test's bet set) ===")
        s = t[(t.side != "") & (t.edge >= 1)].sort_values("edge", ascending=False)
        for _, r in s.iterrows():
            odds = f" ({r.side_odds:+.0f})" if pd.notna(r.side_odds) else ""
            line = f"{r.side_line:+.1f}" if pd.notna(r.side_line) else "not posted"
            print(f"  {r.side:20s} {line:>11s} @ {r.side_book or '-':10s}{odds:8s} edge {r.edge:.1f}")


def recompute_forward_log() -> int:
    """Refit every model column for every existing forward-log row from its raw PT snapshot,
    under the CURRENT PARAMS/MODEL_COLS, and re-tag every row with MODEL_SET_VERSION.

    Run this whenever PARAMS or MODEL_COLS changes (amendment A4 and any future one) and BEFORE
    any read quotes pred_close -- a predictor that changes mid-forward-test silently redefines
    the graded quantity (plan of record, decision 3). Book-derived columns (book_fair, side,
    side_line, edge, ...) do not depend on the model set and are left as originally captured;
    only the model columns, pred_close, move_vs_line and move_vs_fair are recomputed.
    """
    if not FORWARD_LOG.exists():
        print("no forward log to recompute"); return 0
    log = pd.read_csv(FORWARD_LOG)
    hist, models = base.load()
    hist = hist[hist["line"].notna() & hist[BENCH].notna()].reset_index(drop=True)
    parts = []
    for snap, grp in log.groupby("snapshot", sort=False):
        path = clt.SNAP_DIR / snap
        if not path.exists():
            print(f"  {snap}: raw snapshot missing on disk, {len(grp)} rows left unrecomputed")
            parts.append(grp)
            continue
        live_raw = pd.read_csv(path).drop_duplicates(["road", "home"], keep="last").reset_index(drop=True)
        gap = (live_raw["lineopen"] - live_raw["line"]).abs()
        live_raw["open_suspect"] = gap > 14
        live_raw.loc[live_raw.open_suspect, "lineopen"] = live_raw.loc[live_raw.open_suspect, "line"]
        live = pu.to_archive_convention(live_raw.drop(columns=["open_suspect"]))
        live["season"] = int(hist.season.max()) + 1
        live = live.reset_index(drop=True)
        preds, *_ = fit_movement_models(hist, models, live)
        new = pd.DataFrame({"road": live_raw["road"], "home": live_raw["home"]})
        for m in REPORTED_COLS:
            new[m] = np.round(preds[m], 1)
        new["pred_close"] = new[MODEL_COLS].median(axis=1).round(1)
        grp = grp.drop(columns=[c for c in REPORTED_COLS + ["pred_close"] if c in grp]) \
                 .merge(new, on=["road", "home"], how="left")
        grp["move_vs_line"] = (grp.pred_close - grp.line_pt).round(1)
        if "book_fair" in grp:
            grp["move_vs_fair"] = (grp.pred_close - grp.book_fair).round(1)
        parts.append(grp)
    out = pd.concat(parts, ignore_index=True)
    out["model_set_version"] = MODEL_SET_VERSION
    out.to_csv(FORWARD_LOG, index=False)
    n_snaps = log.snapshot.nunique()
    print(f"recomputed {len(out)} forward-log rows across {n_snaps} snapshots "
          f"under model_set_version {MODEL_SET_VERSION}")
    return len(out)


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
    ap.add_argument("--book", default=None,
                    help="show the side's number and price at this one book: " + ", ".join(REAL_BOOKS.values()))
    ap.add_argument("--recompute-forward-log", action="store_true",
                    help="refit every existing forward-log row under the current PARAMS/"
                         "MODEL_COLS and MODEL_SET_VERSION, then exit -- no new slate built")
    args = ap.parse_args()
    if args.recompute_forward_log:
        recompute_forward_log()
        return 0
    book = None
    if args.book:
        book = next((n for n in REAL_BOOKS.values() if n.lower() == args.book.lower()), None)
        if book is None or args.no_books:
            raise SystemExit(f"--book must be one of {', '.join(REAL_BOOKS.values())}, with the live fetch on")
    snap = args.snapshot or pu.latest_snapshot()
    t = build(snap, with_books=not args.no_books, book=book)
    report(t, with_books=not args.no_books)
    suffix = f"_{book.lower()}" if book else ""
    stamp = snap.stem.split("_")[-1]
    path = OUT / f"weekly_slate_{stamp}{suffix}.csv"
    out = t.drop(columns=[c for c in ("quotes", "key", "rkey") if c in t])
    out.to_csv(path, index=False)
    out.to_csv(OUT / f"weekly_slate_latest{suffix}.csv", index=False)
    write_xlsx(t, OUT / f"weekly_slate_latest{suffix}.xlsx")
    # A snapshot with no book match is a stale slate (PT still serving last week's games after
    # they kicked off); logging it would add ungradable rows to version B's dataset. A --book
    # run is a view, not new data.
    stale = (not args.no_books) and "event_id" in t and t.event_id.isna().all()
    n = 0 if (stale or book) else append_forward_log(t)
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
    for pt_name, an_name in [("North Dakota St.", "ND State"), ("Connecticut", "UConn"),
                             ("New Mexico St.", "N. Mexico St"), ("Kansas St.", "K State"),
                             ("Central Florida", "UCF"), ("Texas-San Antonio", "UTSA"),
                             ("Louisiana-Lafayette", "Louisiana"), ("Virginia Tech", "VA Tech")]:
        assert norm(pt_name) == norm(an_name), (pt_name, an_name, norm(pt_name), norm(an_name))
    # side: E4 above fair -> home at the best home number (shown as a home line);
    # below -> road at the best road number (shown as points received)
    frame = pd.DataFrame({"home": ["Auburn", "LSU"], "road": ["S Miss", "La Tech"], "line_pt": [33.5, 35.5],
                          "E4": [28.5, 36.5], "fair_pt": [33.5, 35.5], "best_home_pt": [32.5, 36.0],
                          "best_away_pt": [34.0, 35.5], "best_home_book": ["FanDuel", "BetRivers"],
                          "best_away_book": ["BetMGM", "Caesars"], "best_home_odds": [-106, -110],
                          "best_away_odds": [100, -112], "DraftKings_home": [33.5, np.nan],
                          "DraftKings_odds": [-115, np.nan]})
    s = add_side(frame.copy())
    assert s.side.tolist() == ["S Miss", "LSU"] and s.side_line.tolist() == [34.0, -36.0], s
    assert s.side_book.tolist() == ["BetMGM", "BetRivers"] and s.edge.tolist() == [5.0, 1.0], s
    assert s.side_odds.tolist() == [100, -110], s
    assert s.our_line.tolist() == [-28.5, -36.5], s
    d = add_side(frame.copy(), book="DraftKings")        # same side; that book's number, NaN if unposted
    assert d.side.tolist() == ["S Miss", "LSU"] and d.side_line.iloc[0] == 33.5 and np.isnan(d.side_line.iloc[1]), d
    assert d.side_book.tolist() == ["DraftKings", ""] and d.side_odds.iloc[0] == -115, d
    q = {"68": (-7.5, -110), "69": (-7.0, -110), "71": (18.0, -110)}
    s = shop(q)
    assert s["n_books"] == 2 and s["fair_an"] == -7.25, s   # BetRivers' 18 was guarded out
    # the cross-game guard: same home team, different opponent must NOT inherit book numbers
    pt = pd.DataFrame({"key": ["ole miss"], "rkey": ["louisville"]})
    an = pd.DataFrame({"key": ["ole miss"], "rkey": ["charlotte"], "event_id": [1]})
    assert pt.merge(an, on=["key", "rkey"], how="left").event_id.isna().all()
    assert pt.merge(an, on="key", how="left").event_id.notna().all()   # the old, silent behaviour
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    raise SystemExit(main())
