"""DraftKings Sunday-number forward log. Implements docs/prereg-dk-opener-forward-log.md.

Read the prereg first: decision time, book set, threshold and outcomes are fixed there and
are not tuning knobs.

Every Sunday at 12:00 ET, rebuild each Action Network book's spread as of that moment from
the stored tick paths (CFB-AN-History pulls every 6 h; a Monday pull still carries Sunday's
ticks). Where DraftKings sits >= 1.0 point better than the median of the other real books,
the log records a bet on that side at DraftKings' number. FanDuel is logged the same way as a
secondary. Grading uses CFBD's REST DraftKings close, the only close that agrees with AN's
DraftKings path on games whose path runs through kickoff (90% vs 48% when it stops early).

    python research/spread/scripts/dk_opener_log.py log     # decision-time rows, no outcomes
    python research/spread/scripts/dk_opener_log.py grade   # joins closes and scores

Writes $CFB_DATA_ROOT/processed/dk_opener_log.csv and dk_opener_grade.json. Never touches
movement_forward_log.csv (version B's dataset).
"""

from __future__ import annotations

import argparse
import datetime as dt
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

# AN's own book list: 49 Caesars, 68 DraftKings, 69 FanDuel, 71 BetRivers, 75 BetMGM.
# 15 (consensus) and 30 (consensus opener) are not books. Same set as eval_line_shopping.py.
REAL_BOOKS = {49: "Caesars", 68: "DraftKings", 69: "FanDuel", 71: "BetRivers", 75: "BetMGM"}
BETTABLE = {68: "DraftKings", 69: "FanDuel"}  # 68 primary, 69 secondary (ATS only)
ODDS_WINDOW = (-135, 125)
OUTLIER_PTS = 2.5  # amendment S1, applied to the books that form the fair, never to the bet book
THRESHOLD = 1.0
DECISION_HOUR = 12  # Sunday, US/Eastern
STALE_HOURS = 36  # last tick before Saturday 00:00 ET = priced before the previous weekend
# Games whose decision time is before this instant were visible when the prereg was written.
TEST_START = pd.Timestamp("2026-10-04 12:00")  # first Sunday after the prereg commit
READ_DATE = dt.date(2026, 12, 14)  # the day after the last 2026 regular-season game

TICKS_SQL = """
with ev as (
  select s.event_id, s.start_time,
         max(case when t.team_id = s.home_team_id then t.location end) as hloc,
         max(case when t.team_id = s.away_team_id then t.location end) as aloc
  from stg.an_scoreboard s join stg.an_team t using (event_id) where s.season >= 2026
  group by all)
select g.gameId as game_id, g.season, g.week, g.homeTeam as home, g.awayTeam as away,
       timezone('America/New_York', g.startDate) as kick_et,
       t.book_id, timezone('America/New_York', t.updated_at) as ts, t.line, t.odds,
       t.line_status
from ev
join stg.games g on g.season = year(ev.start_time) and g.homeTeam = ev.hloc and g.awayTeam = ev.aloc
 and cast(timezone('America/New_York', g.startDate) as date)
   = cast(timezone('America/New_York', ev.start_time) as date)
join stg.an_history_tick t using (event_id)
where g.seasonType = 'regular' and g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
  and t.market_type = 'spread' and t.period = 'event' and t.side = 'home'
  and not t.is_live and not coalesce(t.is_alt_market, false)
  and t.book_id in (49, 68, 69, 71, 75)
"""

# CFBD REST payload only: the warehouse's merged "draftkings" also carries AN's consensus.
CLOSE_SQL = """
select gameId as game_id, median(lines_spread) as dk_close from stg.lines__lines
where lines_provider in ('DraftKings', 'Draft Kings') group by 1
"""

SCORES_SQL = """
select gameId as game_id, cast(homePoints as int) - cast(awayPoints as int) as margin
from stg.games where completed
"""

SAG_SQL = """
select r.date as edition, r.cfbd_team as team, r.rank,
       count(*) over (partition by r.date) as n_teams
from stg.massey_ranks r where r.system = 'SAG' and r.season >= 2026
"""


def decision_time(kick: pd.Timestamp) -> pd.Timestamp:
    """12:00 ET on the last Sunday strictly before the kickoff date."""
    d = kick.normalize()
    back = (d.dayofweek + 1) % 7 or 7  # Mon=0 .. Sun=6; a Sunday game looks back a week
    return d - pd.Timedelta(days=back) + pd.Timedelta(hours=DECISION_HOUR)


def lines_at_t(ticks: pd.DataFrame) -> pd.DataFrame:
    """One row per game x book: the book's state at the game's decision time.

    Take the last tick at or before T of ANY status, then require it to be a normal, in-window
    price. Filtering first would let a line the book had since suspended stand as posted.
    """
    t = ticks.copy()
    t["T"] = t.kick_et.map(decision_time)
    # A decision time counts only once the collector has pulled past it; otherwise "as of T"
    # would be whatever the line is today.
    t = t[(t["T"] <= ticks.ts.max()) & (t.ts <= t["T"])].sort_values("ts")
    t = t.groupby(["game_id", "book_id"]).tail(1)
    # 'opener' is AN's status on a book's FIRST posting (100% of DraftKings' first ticks): a
    # live number, and the one this log is about. 'unavailable' means off the board.
    ok = t.line_status.isna() | t.line_status.isin(["normal", "opener"])
    return t[ok & (t.odds.isna() | t.odds.between(*ODDS_WINDOW))]


def fair_ex(row_books: dict[int, float], bet_book: int) -> tuple[float, int]:
    """Median of the other real books, after amendment S1's outlier guard."""
    others = {b: v for b, v in row_books.items() if b != bet_book}
    if len(row_books) >= 3:
        med_all = float(np.median(list(row_books.values())))
        kept = {b: v for b, v in others.items() if abs(v - med_all) <= OUTLIER_PTS}
        if len(kept) >= 2:
            others = kept
    if len(others) < 2:
        return np.nan, len(others)
    return float(np.median(list(others.values()))), len(others)


def side_for(diff: float) -> str:
    """Home spread convention (negative = home favoured). The bet book giving home MORE points
    than the fair (diff > 0) makes home the better side there."""
    if diff >= THRESHOLD:
        return "home"
    if diff <= -THRESHOLD:
        return "away"
    return "none"


def build_log(con) -> pd.DataFrame:
    ticks = con.execute(TICKS_SQL).df()
    at = lines_at_t(ticks)
    games = at.drop_duplicates("game_id").set_index("game_id")
    wide = at.pivot(index="game_id", columns="book_id", values="line")
    odds = at.pivot(index="game_id", columns="book_id", values="odds")
    tick = at.pivot(index="game_id", columns="book_id", values="ts")
    rows = []
    for gid, r in wide.iterrows():
        books = {int(b): float(v) for b, v in r.items() if pd.notna(v)}
        for bb, name in BETTABLE.items():
            if bb not in books:
                continue
            fair, n_other = fair_ex(books, bb)
            if np.isnan(fair):
                continue
            g = games.loc[gid]
            diff = books[bb] - fair
            age = (g["T"] - tick.loc[gid, bb]) / pd.Timedelta(hours=1)
            rows.append({
                "game_id": gid, "season": g.season, "week": g.week, "home": g.home,
                "away": g.away, "kick_et": g.kick_et, "decision_et": g["T"],
                "in_test": g["T"] >= TEST_START, "book": name, "line_T": books[bb],
                "odds_T": odds.loc[gid, bb], "fair_ex": fair, "n_other": n_other,
                "diff": round(diff, 2), "side": side_for(diff),
                # AN records no 'unavailable' ticks for DraftKings, so a pulled line looks
                # posted. A number last touched before the previous weekend began is stale.
                "tick_age_h": round(age, 1), "stale": age > STALE_HOURS})
    log = pd.DataFrame(rows)
    return add_sag(con, log)


def add_sag(con, log: pd.DataFrame) -> pd.DataFrame:
    """Logged, not in the rule: Sagarin's rank gap from the last edition dated before T.
    Home orientation, percent of ranked teams: positive = home ranked better."""
    sag = con.execute(SAG_SQL).df()
    if sag.empty or log.empty:
        return log.assign(q_sag=np.nan)
    sag["edition"] = pd.to_datetime(sag.edition)
    eds = np.sort(sag.edition.unique())
    # Strictly before the decision DAY: a Sunday-dated edition is pulled Tuesday 04:30.
    log["edition"] = [pd.Timestamp(eds[eds < t.normalize()].max())
                      if (eds < t.normalize()).any() else pd.NaT
                      for t in pd.to_datetime(log.decision_et)]
    s = sag.set_index(["edition", "team"])
    get = lambda e, tm: s["rank"].get((e, tm), np.nan)  # noqa: E731
    n = lambda e: s.loc[e].n_teams.iloc[0] if e in s.index.get_level_values(0) else np.nan  # noqa: E731
    log["q_sag"] = [100 * (get(e, a) - get(e, h)) / n(e) if pd.notna(e) else np.nan
                    for e, h, a in zip(log.edition, log.home, log.away)]
    return log


def american_profit(odds: float) -> float:
    """Profit per 1 unit risked at American odds; -110 when the tick carried no price."""
    o = -110.0 if pd.isna(odds) else float(odds)
    return 100 / -o if o < 0 else o / 100


def cluster_ci(x: np.ndarray, g: np.ndarray, boot: int = 2000) -> list[float]:
    """95% interval of the mean, resampling whole decision Sundays."""
    ug = np.unique(g)
    sums = np.array([x[g == k].sum() for k in ug])
    cnts = np.array([(g == k).sum() for k in ug])
    idx = np.random.default_rng(0).integers(0, len(ug), (boot, len(ug)))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    return [round(float(np.percentile(means, q)), 3) for q in (2.5, 97.5)]


def grade(con, log: pd.DataFrame) -> dict:
    """Primary: fresh rows only. Stale rows are graded separately as a sensitivity."""
    out = {"read_date": str(READ_DATE), "registered_read": dt.date.today() >= READ_DATE}
    for label, part in (("primary", log[~log.stale]), ("stale_sensitivity", log[log.stale])):
        out[label] = grade_part(con, part)
    return out


def grade_part(con, log: pd.DataFrame) -> dict:
    bets = log[log.in_test & (log.side != "none")].merge(
        con.execute(SCORES_SQL).df(), on="game_id", how="left").merge(
        con.execute(CLOSE_SQL).df(), on="game_id", how="left")
    bets = bets[bets.margin.notna()].sort_values("kick_et")
    out = {}
    for book, b in bets.groupby("book"):
        home = b.side == "home"
        num = np.where(home, b.margin + b.line_T, -(b.margin + b.line_T))
        win, push = num > 0, num == 0
        pnl = np.where(push, 0.0, np.where(win, b.odds_T.map(american_profit), -1.0))
        g = b.decision_et.astype(str).to_numpy()
        n_dec = int((~push).sum())
        res = {"bets": len(b), "sundays": int(len(np.unique(g))),
               "ats_win_rate": round(float(win.sum() / max(n_dec, 1)), 4),
               "ats_wilson95": [round(float(v), 4) for v in stats.binomtest(
                   int(win.sum()), max(n_dec, 1)).proportion_ci(method="wilson")],
               "pushes": int(push.sum()), "roi": round(float(pnl.mean()), 4),
               "roi_ci95": cluster_ci(pnl, g),
               "max_drawdown_units": round(float((np.maximum.accumulate(np.cumsum(pnl))
                                                  - np.cumsum(pnl)).max()), 2)}
        if book == "DraftKings":  # primary: CLV against DraftKings' REST close
            c = b.dk_close.notna().to_numpy()
            clv = np.where(home, b.line_T - b.dk_close, b.dk_close - b.line_T)[c]
            res.update({"clv_n": int(c.sum()), "clv_mean": round(float(clv.mean()), 3),
                        "clv_ci95": cluster_ci(clv, g[c]),
                        "clv_median": float(np.median(clv)),
                        "clv_positive_rate": round(float((clv > 0).mean()), 3),
                        "clv_zero_rate": round(float((clv == 0).mean()), 3),
                        "clv_by_abs_diff": {
                            k: round(float(clv[m[c]].mean()), 3) if m[c].any() else None
                            for k, m in {"1-1.5": b["diff"].abs().lt(1.5).to_numpy(),
                                         "1.5-2.5": b["diff"].abs().between(1.5, 2.5, "left").to_numpy(),
                                         ">=2.5": b["diff"].abs().ge(2.5).to_numpy()}.items()}})
        out[book] = res
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["log", "grade"])
    a = ap.parse_args()
    con = duckdb.connect(str(cfb_paths.DATA_ROOT / "cfb.duckdb"), read_only=True)
    log = build_log(con)
    out = cfb_paths.DATA_ROOT / "processed"
    log.to_csv(out / "dk_opener_log.csv", index=False)
    trig = log[log.side != "none"]
    print(f"{len(log)} book-game rows, {log.game_id.nunique()} games; "
          f"triggers by week and book (decision-time data only):")
    print(trig.groupby(["week", "book", "stale"]).size().unstack(fill_value=0).to_string()
          if len(trig) else "none")
    if a.cmd == "grade":
        res = grade(con, log)
        if not res["registered_read"]:
            print(f"\nINTERIM - not the registered read (that is {READ_DATE}).")
        print(json.dumps(res, indent=1, default=str))
        (out / "dk_opener_grade.json").write_text(json.dumps(res, indent=1, default=str))
    return 0


def _check() -> None:
    sat = pd.Timestamp("2026-10-10 15:30")
    assert decision_time(sat) == pd.Timestamp("2026-10-04 12:00")
    assert decision_time(pd.Timestamp("2026-10-06 20:00")) == pd.Timestamp("2026-10-04 12:00")
    assert decision_time(pd.Timestamp("2026-10-11 13:00")) == pd.Timestamp("2026-10-04 12:00")
    assert fair_ex({68: 3.0, 69: 1.0, 71: 1.5}, 68) == (1.25, 2)
    assert side_for(3.0 - 1.25) == "home" and side_for(-1.0) == "away" and side_for(0.5) == "none"
    # S1: a far-off other book is dropped when two remain.
    assert fair_ex({68: -3.0, 69: -7.0, 71: -7.5, 75: -14.0}, 68) == (-7.25, 2)
    assert abs(american_profit(-110) - 0.9091) < 1e-3 and american_profit(150) == 1.5


if __name__ == "__main__":
    _check()
    sys.exit(main())
