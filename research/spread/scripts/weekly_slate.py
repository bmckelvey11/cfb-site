"""This week's slate: every line-movement model on the latest Prediction Tracker snapshot,
next to the live book fair and the best number at each sportsbook.

What each column is (all spreads in Prediction Tracker's sign: POSITIVE = home favored):

  open_pt      PT's recorded opener (often a months-old look-ahead number for early weeks)
  line_pt      the market line at the moment PT compiled the snapshot
  book_fair    median home spread across real books RIGHT NOW, after the outlier guard: the
               five Action Network books (Caesars, DraftKings, FanDuel, BetRivers, BetMGM)
               plus the five offshore books only the-odds-api carries (BetOnline.ag, Bovada,
               LowVig.ag, BetUS, MyBookie.ag) plus Pinnacle from oddspapi. One vote per book --
               AN wins every overlap because its quote is live. Amendments S2 and S3 of
               prereg-line-shopping.md; tagged `book_set_version` 3 on every forward-log row
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
  Pinnacle_home / Pinnacle_odds / pin_limit   Pinnacle's full-game main line from the latest
               oddspapi snapshot (scripts/pull_oddspapi.py, daily), PT sign. Votes in book_fair
               as one book of up to eleven since amendment S3 (`book_set_version` 3).
               pin_vs_fair = Pinnacle_home - book_fair.

  oa_*         the same arithmetic over the-odds-api's nine books ALONE, AS OF `oa_as_of`
               (the 6-hourly snapshot, so up to six hours stale). Kept beside book_fair as the
               agreement check: `oa_vs_book_fair` should sit within about a point, and a
               systematic gap means a sign error or a bad join, not a better consensus.

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
import cfb_paths  # noqa: E402  (clt put the repo root on sys.path)

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

# the-odds-api book keys -> the same display names, so quotes from both feeds land in one
# Series keyed by BOOK IDENTITY. Without that, DraftKings/FanDuel/BetRivers/BetMGM arrive twice
# and vote twice in the median -- a consensus weighted by which books happen to be on two
# feeds. Action Network wins every overlap: it is fetched live at slate time where the
# the-odds-api snapshot is up to six hours old, and `book_fair` claims to be the number RIGHT NOW.
OA_BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betrivers": "BetRivers",
            "betmgm": "BetMGM", "betonlineag": "BetOnline.ag", "bovada": "Bovada",
            "lowvig": "LowVig.ag", "betus": "BetUS", "mybookieag": "MyBookie.ag"}
# What promotion actually added: the five the-odds-api books Action Network does not carry.
# All five are offshore. They are real venues and OUTLIER_PTS still guards the median, but
# regulated-only is a one-line change here if that turns out to be the wrong call.
OA_ONLY_BOOKS = tuple(n for n in OA_BOOKS.values() if n not in REAL_BOOKS.values())
# Amendment S3 (2026-09-09): Pinnacle, from the oddspapi snapshot (pinnacle_lines), votes too.
# One book, one vote, same as the rest; it is the sharpest book but the median does not know
# that. Its quote is up to 24h old (daily pull); the outlier guard is what stops a stale number
# on a moved line from dragging the fair.
BOOKS = tuple(REAL_BOOKS.values()) + OA_ONLY_BOOKS + ("Pinnacle",)

# Which book set produced book_fair, tagged on every forward-log row for the same reason
# MODEL_SET_VERSION is: a graded quantity that changes mid-test has to say so.
#   1 = Action Network alone (rows through 2026-09-09)
#   2 = Action Network + the five the-odds-api books above (2026-09-09, same day)
#   3 = version 2 + Pinnacle via oddspapi (2026-09-09 on; amendment S3)
# Earlier rows cannot be recomputed under a later version -- no snapshot from the added feed
# exists for those moments -- so each break is permanent and version B must either restrict to
# one era or model the shift.
BOOK_SET_VERSION = 3
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
                        quotes[REAL_BOOKS[book]] = (float(s["value"]), int(s["odds"]))
            rows.append({"event_id": g["id"], "kick": ko, "an_home": home.get("display_name"),
                         "an_road": road.get("display_name"),
                         "key": norm(home.get("display_name", "")),
                         "rkey": norm(road.get("display_name", "")), "quotes": quotes})
        time.sleep(0.5)
    return pd.DataFrame(rows).drop_duplicates("event_id")


def shop(quotes: dict) -> dict:
    """Book fair and best number per side, in AN sign (negative = home favored).

    `quotes` is keyed by display name, not by any one feed's book id, so both sources can be
    deduped into it before the median is taken -- see `OA_BOOKS`.
    """
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
            "best_home_an": v.max(), "best_home_book": v.idxmax(),
            "best_home_odds": quotes[v.idxmax()][1],
            "best_away_an": v.min(), "best_away_book": v.idxmin(),
            "best_away_odds": quotes[v.idxmin()][1]}


# ---------------------------------------------------------------- the-odds-api (observation)

OA_SNAP_DIR = cfb_paths.INGEST / "oddsapi"
# Books the-odds-api returns for `regions=us`. The four that overlap Action Network's set
# (DraftKings, FanDuel, BetRivers, BetMGM) plus five offshore books AN does not carry; it has
# no Caesars, which AN does. So `oa_fair` is a DIFFERENT book set from `book_fair`, not a
# second opinion on the same one -- that is the point of keeping it beside rather than inside.
OA_MIN_BOOKS = 2


def oddsapi_books(now: datetime) -> pd.DataFrame:
    """Per-book home spreads from the latest the-odds-api snapshot. OBSERVATION ONLY.

    These columns never feed `book_fair`, `move_vs_fair`, `side`, or `edge`. `book_fair` is the
    quantity version B grades, and the forward log is its dataset; widening the book set mid-test
    would silently redefine what was graded, exactly as `MODEL_SET_VERSION` guards against on the
    predictor side. Promoting this source into `book_fair` is a deliberate, version-tagged
    decision, not a side effect of having the data.

    Read from disk, not live: `CFB-Odds-Snapshot` pulls every 6 hours (see
    `docs/oddsapi-ingest.md`) and a slate run costs no credits this way. That makes every number
    here AS OF `oa_as_of`, up to six hours stale -- which is why the best-number columns are
    named `oa_*` and not merged into the shoppable ones.
    """
    snaps = sorted(OA_SNAP_DIR.glob("odds_americanfootball_ncaaf_*.json"))
    if not snaps:
        print(f"  no the-odds-api snapshot in {OA_SNAP_DIR}; oa_* columns unavailable",
              file=sys.stderr)
        return pd.DataFrame()
    payload = json.loads(snaps[-1].read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(payload["pulled_at"].replace("Z", "+00:00"))
    age_h = (now - as_of).total_seconds() / 3600
    print(f"  the-odds-api snapshot {snaps[-1].name}: {len(payload['events'])} events, "
          f"{age_h:.1f}h old")
    if age_h > 12:
        print(f"  WARNING: snapshot is {age_h:.0f}h old -- is CFB-Odds-Snapshot still running?",
              file=sys.stderr)

    lo, hi = now - timedelta(days=1), now + timedelta(days=8)
    rows = []
    for e in payload["events"]:
        ko = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if not (lo <= ko <= hi):
            continue
        quotes = {}
        for b in e.get("bookmakers", []):
            if b.get("key") not in OA_BOOKS:      # a new book must be named before it votes
                print(f"  the-odds-api: unmapped book {b.get('key')!r}, not counted",
                      file=sys.stderr)
                continue
            for m in b.get("markets", []):
                if m.get("key") != "spreads":
                    continue
                for o in m.get("outcomes", []):
                    # the home team's own outcome carries the home spread in betting sign
                    # (negative = home favored), the same convention AN uses.
                    if (o.get("name") == e["home_team"] and o.get("point") is not None
                            and o.get("price") is not None
                            and ODDS_WINDOW[0] <= o["price"] <= ODDS_WINDOW[1]):
                        quotes[OA_BOOKS[b["key"]]] = (float(o["point"]), int(o["price"]))
        rows.append({"oa_home_raw": e["home_team"], "oa_road_raw": e["away_team"],
                     "oa_quotes": quotes, "oa_as_of": payload["pulled_at"]})
    return pd.DataFrame(rows)


# the-odds-api school spellings that do not normalize onto Prediction Tracker's, checked
# after the mascot is stripped. Grows the way ALIASES did -- add a line when a game shows up
# in the unpriced list with books actually posted for it in the snapshot.
OA_ALIASES = {"florida international": "florida intl", "middle tennessee": "middle tenn",
              # oddspapi spellings (Pinnacle feed)
              "middle tennessee state": "middle tenn", "ut san antonio": "texas-san antonio"}

# Mascots are one or two trailing tokens ("Hurricanes", "Thundering Herd"), so the strip never
# needs to drop more than two. The cap does NOT make a single name unambiguous -- "Alabama
# Crimson Tide" and "Florida International Panthers" are both three tokens, and dropping two
# gives the right school for one and the Gators for the other. What actually prevents a wrong
# price is that the merge keys on BOTH teams: a misresolved home name has to be paired with a
# road name that misresolves onto the same PT row, which is why a bad strip lands in the
# unpriced list instead of pricing a game against another game's number.
OA_MAX_MASCOT_TOKENS = 2


def oa_resolve(name: str, keys: set[str]) -> str:
    """Odds API names carry the mascot ("Miami Hurricanes"); PT carries the school ("Miami").

    Drop trailing tokens longest-match-first, at most `OA_MAX_MASCOT_TOKENS` of them, until the
    head normalizes onto a name the slate actually has. Longest-first is what keeps
    "Miami (OH) RedHawks" off "miami". An over-eager strip is caught by the both-teams merge,
    not here -- see `OA_MAX_MASCOT_TOKENS`.
    """
    parts = str(name).split()
    for cut in range(len(parts), max(0, len(parts) - OA_MAX_MASCOT_TOKENS) - 1, -1):
        candidate = norm(" ".join(parts[:cut]))
        candidate = OA_ALIASES.get(candidate, candidate)
        if candidate in keys:
            return candidate
    return norm(name)


def oa_shop(quotes: dict) -> dict:
    """`shop()`'s arithmetic over the-odds-api books, on `oa_`-prefixed names."""
    if len(quotes) < OA_MIN_BOOKS:
        return {}
    v = pd.Series({b: q[0] for b, q in quotes.items()})
    if len(v) >= 3:
        kept = v[(v - v.median()).abs() <= OUTLIER_PTS]
        if len(kept) >= 2:
            v = kept
    return {"oa_fair_an": v.median(), "oa_n_books": len(v), "oa_range": v.max() - v.min(),
            "oa_best_home_an": v.max(), "oa_best_home_book": v.idxmax(),
            "oa_best_home_odds": quotes[v.idxmax()][1],
            "oa_best_away_an": v.min(), "oa_best_away_book": v.idxmin(),
            "oa_best_away_odds": quotes[v.idxmin()][1]}


# ---------------------------------------------------------------- Pinnacle via oddspapi (observation)

PIN_SNAP_DIR = cfb_paths.INGEST / "oddspapi"


def is_full_game_spread(market: dict) -> bool:
    """Pinnacle's market path is `line/<...>/<period>/spreads`; period 0 is the full game.
    `altLine/...` entries are alternate numbers, periods 1+ are halves and quarters -- the
    first-half line at half the number is what a period-blind parse picks up."""
    parts = (market.get("bookmakerMarketId") or "").split("/")
    return parts[0] == "line" and parts[-1] == "spreads" and parts[-2] == "0"


def pinnacle_lines(now: datetime) -> pd.DataFrame:
    """Pinnacle's full-game main-line home spread from the latest oddspapi snapshot
    (`scripts/pull_oddspapi.py`, one request per pull, daily). Votes in `book_fair` as one book
    among up to eleven under amendment S3 of prereg-line-shopping.md (BOOK_SET_VERSION 3).

    The file carries betting sign from the home side (`-3.5/home` = home favored by 3.5);
    stored here in PT sign like every other `<Book>_home` column. participant1 is the home
    team: 46 of 46 games joined that way and 0 the other way on 2026-09-09.
    """
    snaps = sorted(PIN_SNAP_DIR.glob("oddspapi_ncaa_*.json"))
    if not snaps:
        print(f"  no oddspapi snapshot in {PIN_SNAP_DIR}; Pinnacle columns unavailable", file=sys.stderr)
        return pd.DataFrame()
    payload = json.loads(snaps[-1].read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(payload["pulled_at"].replace("Z", "+00:00"))
    print(f"  oddspapi snapshot {snaps[-1].name}: {len(payload['fixtures'])} fixtures, "
          f"{(now - as_of).total_seconds() / 3600:.1f}h old")
    lo, hi = now - timedelta(days=1), now + timedelta(days=8)
    rows = []
    for f in payload["fixtures"]:
        ko = datetime.fromisoformat(f["startTime"].replace("Z", "+00:00"))
        if not (lo <= ko <= hi):
            continue
        book = (f.get("bookmakerOdds") or {}).get("pinnacle") or {}
        for m in (book.get("markets") or {}).values():
            if not is_full_game_spread(m):
                continue
            for o in m["outcomes"].values():
                for pl in o["players"].values():
                    if pl.get("mainLine") and pl["bookmakerOutcomeId"].endswith("/home"):
                        rows.append({"pin_home_raw": f["participant1Name"], "pin_road_raw": f["participant2Name"],
                                     "Pinnacle_home": -float(pl["bookmakerOutcomeId"].split("/")[0]),
                                     "Pinnacle_odds": int(pl["priceAmerican"]), "pin_limit": pl.get("limit"),
                                     "pin_active": bool(pl.get("active")), "pin_as_of": payload["pulled_at"]})
    return pd.DataFrame(rows)


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

        # the-odds-api joins here so its books can vote in book_fair (BOOK_SET_VERSION 2).
        oa = oddsapi_books(now)
        if not oa.empty:
            oa["key"] = [oa_resolve(n, set(t.key)) for n in oa.oa_home_raw]
            oa["rkey"] = [oa_resolve(n, set(t.rkey)) for n in oa.oa_road_raw]
            oa = oa.drop_duplicates(["key", "rkey"])
            t = t.merge(oa.drop(columns=["oa_home_raw", "oa_road_raw"]),
                        on=["key", "rkey"], how="left")
        else:
            t["oa_quotes"], t["oa_as_of"] = [{} for _ in range(len(t))], np.nan

        # Pinnacle joins here too (BOOK_SET_VERSION 3); it is on neither other feed, so no overlap.
        pin = pinnacle_lines(now)
        if not pin.empty:
            pin["key"] = [oa_resolve(n, set(t.key)) for n in pin.pin_home_raw]
            pin["rkey"] = [oa_resolve(n, set(t.rkey)) for n in pin.pin_road_raw]
            t = t.merge(pin.drop(columns=["pin_home_raw", "pin_road_raw"]).drop_duplicates(["key", "rkey"]),
                        on=["key", "rkey"], how="left")
        for c in ("Pinnacle_home", "Pinnacle_odds", "pin_limit", "pin_active", "pin_as_of"):
            if c not in t:
                t[c] = np.nan
        # AN sign for the vote (negative = home favored), like every other quote in qs
        pin_qs = [{"Pinnacle": (-h, int(o))} if np.isfinite(h) else {}
                  for h, o in zip(t.Pinnacle_home, t.Pinnacle_odds.fillna(0))]

        an_qs = [q if isinstance(q, dict) else {} for q in t.quotes]
        oa_qs = [q if isinstance(q, dict) else {} for q in t.oa_quotes]
        # Action Network wins every overlapping book: its quote is live, the snapshot's is up
        # to six hours old. Promotion therefore ADDS the five offshore books AN does not carry
        # rather than reshuffling the four it already had.
        qs = [{**o, **p, **a} for o, p, a in zip(oa_qs, pin_qs, an_qs)]
        s = pd.DataFrame([shop(q) for q in qs])
        # the-odds-api on its own, kept beside the promoted number as the agreement check
        s_oa = pd.DataFrame([oa_shop(q) for q in oa_qs])
        t = pd.concat([t.drop(columns=["quotes", "oa_quotes"]), s, s_oa], axis=1)
        for name in BOOKS:                             # every book's own number, PT sign
            t[f"{name}_home"] = [-q[name][0] if name in q else np.nan for q in qs]
            t[f"{name}_odds"] = [q[name][1] if name in q else np.nan for q in qs]
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
        # Pinnacle against the fair it now votes in -- one of up to eleven, so a gap here is
        # Pinnacle disagreeing with the rest, not a join problem
        t["pin_vs_fair"] = (t.Pinnacle_home - t.book_fair).round(2)
        n_pin = int(t.Pinnacle_home.notna().sum())
        print(f"  Pinnacle (oddspapi): {n_pin}/{len(t)} games priced"
              + (f", median |Pinnacle - book_fair| {t.pin_vs_fair.abs().median():.2f} pts, "
                 f"max {t.pin_vs_fair.abs().max():.1f}" if n_pin else ""))
        t["kick_et"] = pd.to_datetime(t.kick, utc=True).dt.tz_convert(ET).dt.strftime("%a %m-%d %I:%M%p")
        unmatched = t[t.event_id.isna()][["road", "home"]].values.tolist()
        if unmatched:
            print(f"  no Action Network match for {len(unmatched)}/{len(t)} games: "
                  f"{unmatched[:8]}{' ...' if len(unmatched) > 8 else ''}")
        if len(unmatched) == len(t):
            print("  ALL games unmatched -- the snapshot is almost certainly a different week "
                  "than the books. book_fair/move_vs_fair are unavailable, not zero.")
        for c in ("oa_fair_an", "oa_best_home_an", "oa_best_away_an"):
            t[c.replace("_an", "_pt")] = -t[c] if c in t else np.nan
        # the-odds-api's own median against the promoted one. They should sit within about a
        # point; a systematic gap is a sign error or a bad join, not a better consensus.
        t["oa_vs_book_fair"] = (t.oa_fair_pt - t.book_fair).round(1)
        priced = int(t.oa_fair_pt.notna().sum())
        gap = t.oa_vs_book_fair.abs()
        print(f"  the-odds-api: {priced}/{len(t)} games priced"
              + (f", median |oa_fair - book_fair| {gap.median():.1f} pts, "
                 f"max {gap.max():.1f}" if gap.notna().any() else ""))
        if priced < len(t):
            unpriced = t[t.oa_fair_pt.isna()][["road", "home"]].values.tolist()
            print(f"    unpriced: {unpriced[:8]}{' ...' if len(unpriced) > 8 else ''}")

    t = add_side(t, book)
    t.insert(0, "snapshot", snapshot.name)
    t.insert(1, "captured_utc", snapshot.stem.split("_")[-1])
    # Which PARAMS/MODEL_COLS definition produced pred_close -- bumped whenever either changes
    # (amendment A4, 2026-09-08: E6 moved from lambda=1e4 to its A4 modal 5e4). A predictor that
    # changes mid-forward-test silently redefines the graded quantity, so every row is tagged.
    t["model_set_version"] = MODEL_SET_VERSION
    # Which book set produced book_fair, and therefore side/side_line/edge and the bet set.
    t["book_set_version"] = BOOK_SET_VERSION if with_books else np.nan
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
    for b in BOOKS:
        slate[b] = bet(f"{b}_home")
        slate[f"{b} odds"] = t.get(f"{b}_odds", np.nan)
    slate["Pinnacle vs Fair"] = -t.get("pin_vs_fair", np.nan)     # betting sign, home side
    slate = slate.sort_values("Edge", ascending=False)
    models = t[["road", "home", "open_pt", "line_pt"] + (["book_fair"] if "book_fair" in t else [])
               + ["consensus"] + REPORTED_COLS + ["pred_close"]]
    shop = None
    if "home_gain" in t:      # the SHOP printout: best number vs book fair, one row per side
        sides = []
        for _, r in t.iterrows():
            # every book's number from the side's perspective; only home-side odds are captured
            per_book = {b: r.get(f"{b}_home", np.nan) for b in BOOKS}
            sides.append({"Kick (ET)": r.get("kick_et", ""), "Team": r.home, "Opponent": r.road,
                          "Best Line": -r.best_home_pt, "Book": r.best_home_book, "Odds": r.best_home_odds,
                          "Fair": -r.fair_pt, "Gain": r.home_gain, "Key": bool(r.home_key),
                          **{b: -v for b, v in per_book.items()}})
            sides.append({"Kick (ET)": r.get("kick_et", ""), "Team": r.road, "Opponent": r.home,
                          "Best Line": r.best_away_pt, "Book": r.best_away_book, "Odds": r.best_away_odds,
                          "Fair": r.fair_pt, "Gain": r.away_gain, "Key": bool(r.away_key), **per_book})
        shop = pd.DataFrame(sides).dropna(subset=["Gain"]).query("Gain >= 0.5") \
                 .sort_values(["Key", "Gain"], ascending=False)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        slate.to_excel(xw, sheet_name="Slate", index=False)
        if shop is not None:
            shop.to_excel(xw, sheet_name="Shop", index=False)
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
                    help="show the side's number and price at this one book: " + ", ".join(BOOKS))
    ap.add_argument("--recompute-forward-log", action="store_true",
                    help="refit every existing forward-log row under the current PARAMS/"
                         "MODEL_COLS and MODEL_SET_VERSION, then exit -- no new slate built")
    args = ap.parse_args()
    if args.recompute_forward_log:
        recompute_forward_log()
        return 0
    book = None
    if args.book:
        book = next((n for n in BOOKS if n.lower() == args.book.lower()), None)
        if book is None or args.no_books:
            raise SystemExit(f"--book must be one of {', '.join(BOOKS)}, with the live fetch on")
    snap = args.snapshot or pu.latest_snapshot()
    t = build(snap, with_books=not args.no_books, book=book)
    report(t, with_books=not args.no_books)
    suffix = f"_{book.lower()}" if book else ""
    stamp = snap.stem.split("_")[-1]
    path = OUT / f"weekly_slate_{stamp}{suffix}.csv"
    out = t.drop(columns=[c for c in ("quotes", "key", "rkey") if c in t])
    out.to_csv(path, index=False)
    out.to_csv(OUT / f"weekly_slate_latest{suffix}.csv", index=False)
    try:
        write_xlsx(t, OUT / f"weekly_slate_latest{suffix}.xlsx")
    except PermissionError:      # the workbook is open in Excel; the CSV and forward log still land
        print(f"  weekly_slate_latest{suffix}.xlsx is open elsewhere -- workbook not refreshed",
              file=sys.stderr)
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
    # Pinnacle: only the full-game main line (period 0); halves and alt lines are skipped
    assert is_full_game_spread({"bookmakerMarketId": "line/15/880/1/2/0/spreads"})
    assert not is_full_game_spread({"bookmakerMarketId": "line/15/880/1/2/1/spreads"})
    assert not is_full_game_spread({"bookmakerMarketId": "altLine/15/880/1/2/3/0/spreads"})
    assert not is_full_game_spread({"bookmakerMarketId": "line/15/880/1/2/0/totals"})
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
