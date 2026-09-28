"""Build one master Greenline history table from every source we hold.

    python research/totals/scripts/build_greenline_history.py
    python research/totals/scripts/build_greenline_history.py --self-check

Writes $CFB_DATA_ROOT/processed/greenline/greenline_history.csv (data, not committed).
Rebuild after each week is graded; every column is recomputed from its source.

GRAIN. Greenline rows: one per (era, game, market) that PFF priced, whether or not PFF took a
side -- `is_pick` marks the ones it did. The 2020 and 2022-23 archive stores every game twice
(once per side) and three times over (snapshots); it is collapsed to one row here, so pooling
the file never double-counts. Personal rows (`source=personal`): one per book bet, 2023-25
full-game NCAAF totals, never merged into a Greenline row.

ERAS. `2020 PFF_hist` (open-Greenline snapshot; close values in their own columns), `2022-23
exports` (three slates, public split, no projection), `2026 capture` (weekly captures, weeks
2 on; ungraded weeks have a blank result), `personal 2023-25`.

COLUMNS -- convention; coverage; what a blank means
  source, era, season, week        greenline | personal. week blank on personal rows
  kickoff_utc, date_et, kickoff_tbd  ISO UTC kickoff; its US/Eastern date; 2026 `00:00` ET is
                                   PFF's "time TBD" (kickoff_tbd=1, time unreliable)
  pff_game_id, cfbd_game_id        2026 / archive ids; cfbd id blank where no join exists
  away, home, game                 team labels as each source writes them; game = "away @ home"
  market                           total | spread | moneyline (personal: total)
  is_pick, pick_side               1 if PFF took a side (over/under/home/away); blank side if not
  market_line_home                 the market number from HOME's view: the total, the home
                                   spread (negative = home favored), or the home moneyline
  market_line_away                 moneyline only: the away price
  pick_line                        the market number as the picked side takes it (total; the
                                   side's own spread; the side's moneyline price)
  pff_projection_home / _away      PFF's number in the same convention (projected total, PFF's
                                   home spread, PFF's fair moneyline); blank for 2022-23 exports
  pff_win_prob                     PFF's stated probability for the picked side
  pff_value                        PFF's stated edge: its probability minus the price's break-even.
                                   For non-picks, the better side's (<= 0) value
  breakeven_prob                   2020 only: PFF's published break-even for the pick
  price, price_source              American price the result is graded at: 2020 from PFF's
                                   break-even, 2026 totals/spreads an ASSUMED -110, moneylines the
                                   market price, personal the price paid; exports none (no return)
  pff_close_line_home / pff_close_projection_home / pff_clv
                                   2020 only, from the close snapshot -- NOT decision-time values
  home_points, away_points, actual_total   final score. 2026 from PFF's schedule; blank where PFF
                                   posted none even though `result` is graded (warehouse final)
  result, units                    win | loss | push for the pick at pick_line and price; units
                                   per 1 staked. Blank = no pick, no final yet, or no price
  on_under_list                    2026 totals: 1 if on that week's published under list
  cash_pct, tickets_pct            2022-23 exports: public split on the picked side
  close_rest, clv_rest             2026 totals: median REST-backed book close (span gate) and CLV
                                   signed toward the pick, points. The GraphQL-contaminated close
                                   is never used (greenline-findings row 14)
  clv_pff_board                    2026: CLV against PFF's own displayed close (weaker)
  best_book, book_line, book_odds, price_snapshot, pinnacle_fair, proj_gap, proj_edge,
  rule_c, rule_e, book_result, book_units
                                   2026 weeks 2-4 positive-edge UNDERS only, rebuilt at decision
                                   time by greenline_price_filter.build(): best DK/FD under, the
                                   odds snapshot, Pinnacle fair total, book total minus PFF
                                   projection, projection edge, the two price rules, and the pick
                                   graded at the book number. Blank for overs, spreads,
                                   moneylines, and weeks without a capture snapshot mapped
  bet, line_taken, price_taken, stake_units
                                   2026 totals, from the bet ledger. bet is y | n | blank, and
                                   blank means NOT YET MARKED, never "not bet"

CAVEATS FOR ANALYSIS
  * Open question C (greenline-findings) is embargoed: win rate by pff_value >= 0.04 for 2026
    week 4 onward is not to be read until 56 prospective picks have graded (~week 6).
  * Personal rows are prior evidence on the same signal, not an independent sample: on the
    only checkable days, 3 of 12 personal unders took the side PFF flagged AGAINST.
  * 2026 CLV may reflect PFF's followers moving lines, not forecasting skill (row 13).
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import DATA_ROOT, INGEST  # noqa: E402

GL_DIR = INGEST / "pff_scoreboard"
OUT = DATA_ROOT / "processed" / "greenline" / "greenline_history.csv"
ET = ZoneInfo("America/New_York")
COLUMNS = [
    "source", "era", "season", "week", "kickoff_utc", "date_et", "kickoff_tbd", "pff_game_id", "cfbd_game_id",
    "away", "home", "game", "market", "is_pick", "pick_side", "market_line_home", "market_line_away", "pick_line",
    "pff_projection_home", "pff_projection_away", "pff_win_prob", "pff_value", "breakeven_prob", "price",
    "price_source", "pff_close_line_home", "pff_close_projection_home", "pff_clv", "home_points", "away_points",
    "actual_total", "result", "units", "on_under_list", "cash_pct", "tickets_pct", "close_rest", "clv_rest",
    "clv_pff_board", "best_book", "book_line", "book_odds", "price_snapshot", "pinnacle_fair", "proj_gap",
    "proj_edge", "rule_c", "rule_e", "book_result", "book_units", "bet", "line_taken", "price_taken", "stake_units"]
RESULT = {"W": "win", "L": "loss", "P": "push"}


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def units(result: str | None, price: float | None) -> float | None:
    if result is None or price is None:
        return None
    if result == "push":
        return 0.0
    if result == "loss":
        return -1.0
    return 100 / -price if price < 0 else price / 100


def american(breakeven: float | None) -> float | None:
    if not breakeven:
        return None
    dec = 1 / breakeven
    return round(100 * (dec - 1)) if dec >= 2 else round(-100 / (dec - 1))


def side_line(market: str, side: str, home_number: float | None, away_price: float | None = None):
    if home_number is None and market != "moneyline":
        return None
    if market == "spread":
        return home_number if side == "home" else -home_number
    if market == "moneyline":
        return home_number if side == "home" else away_price
    return home_number


def grade(market: str, side: str, line: float | None, hp: float | None, ap: float | None) -> str | None:
    if hp is None or ap is None or (line is None and market != "moneyline"):
        return None   # a moneyline grades on the winner alone; it needs a price only for units
    if market == "total":
        t = hp + ap
        return "push" if t == line else ("win" if (t > line) == (side == "over") else "loss")
    if market == "spread":
        edge = (hp - ap if side == "home" else ap - hp) + line
        return "push" if edge == 0 else ("win" if edge > 0 else "loss")
    mine, theirs = (hp, ap) if side == "home" else (ap, hp)
    return "push" if mine == theirs else ("win" if mine > theirs else "loss")


def et_date(utc_iso: str | None) -> str | None:
    if not utc_iso:
        return None
    return datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(ET).date().isoformat()


# ---------------------------------------------------------------- archive (2020, 2022-23)

def archive_rows() -> list[dict]:
    a = pd.read_csv(GL_DIR / "greenline_history_archive.csv", dtype={"is_greenline_pick": "object"})
    out = []
    for era, src_mask, snap in (("2020 PFF_hist", a.source_file == "PFF_hist.xlsx", "open_greenline"),
                                ("2022-23 exports", a.source_file != "PFF_hist.xlsx", "export")):
        part = a[src_mask & (a.snapshot == snap)].copy()
        close = a[src_mask & (a.snapshot == "close")]
        def gkey(d: pd.DataFrame) -> pd.Series:
            # a missing game_id must stay a real key: groupby silently drops NA keys (3 games in 2020)
            return pd.Series([f"{'' if pd.isna(g) else int(g)}|{s}|{w}|{h}|{a}" for g, s, w, h, a in
                              zip(d.game_id, d.season, d.week, d.home_team.fillna(""), d.away_team.fillna(""))],
                             index=d.index, dtype=object)
        part["key"] = gkey(part)
        close = close.assign(key=gkey(close))
        cidx = {(k, m, s): r for k, m, s, r in zip(close.key, close.market, close.side, close.itertuples())}
        for (key, market), g in part.groupby(["key", "market"], sort=False):
            if era.startswith("2022") and g.source_file.nunique() > 1:
                g = g[g.source_file == sorted(g.source_file.unique())[0]]   # one slate copy per game
            sides = {r.side: r for r in g.itertuples()}
            any_r = next(iter(sides.values()))
            picks = [r for r in sides.values() if str(r.is_greenline_pick) == "True"]
            pick = picks[0] if picks else None
            home_r, away_r = sides.get("home"), sides.get("away")
            if market == "total":
                mlh, mla = num(any_r.market_line), None
                ph, pa = num(any_r.greenline_line), None
            elif market == "spread" and era.startswith("2020"):   # 2020: the HOME spread on both rows
                mlh, mla, ph, pa = num(any_r.market_line), None, num(any_r.greenline_line), None
            elif market == "spread":                                # exports: each row is its side's own number
                mlh = num(home_r.market_line) if home_r else (-num(away_r.market_line) if away_r and num(away_r.market_line) is not None else None)
                mla, ph, pa = None, None, None
            else:
                mlh = num(home_r.market_line) if home_r else None
                mla = num(away_r.market_line) if away_r else None
                ph = num(home_r.greenline_line) if home_r else None
                pa = num(away_r.greenline_line) if away_r else None
            hp, ap = num(any_r.home_points), num(any_r.away_points)
            row = {"source": "greenline", "era": era,
                   "season": int(any_r.season) if num(any_r.season) is not None else None,
                   "week": int(any_r.week) if num(any_r.week) is not None else None,
                   "kickoff_utc": any_r.kickoff_utc if isinstance(any_r.kickoff_utc, str) else None,
                   "cfbd_game_id": str(int(any_r.game_id)) if num(any_r.game_id) is not None else None,
                   "away": any_r.away_team, "home": any_r.home_team, "game": f"{any_r.away_team} @ {any_r.home_team}",
                   "market": market, "is_pick": int(pick is not None), "market_line_home": mlh,
                   "market_line_away": mla, "pff_projection_home": ph, "pff_projection_away": pa,
                   "home_points": hp, "away_points": ap,
                   "actual_total": hp + ap if hp is not None and ap is not None else None}
            row["date_et"] = et_date(row["kickoff_utc"])
            vals = [num(r.difference) for r in sides.values() if num(r.difference) is not None]
            if pick is None:
                row["pff_value"] = max(vals) if vals else None
            else:
                side = pick.side
                pl = side_line(market, side, mlh, mla)
                be = num(pick.breakeven_prob)
                price = american(be) if era.startswith("2020") else None
                res = grade(market, side, pl, hp, ap)
                if era.startswith("2020") and isinstance(pick.bet_result, str):
                    res = RESULT.get(pick.bet_result, res)          # PFF's own grading, checked in self_check
                c = cidx.get((key, market, side))
                row.update({"pick_side": side, "pick_line": pl, "pff_win_prob": num(pick.cover_prob),
                            "pff_value": num(pick.difference), "breakeven_prob": be, "price": price,
                            "price_source": "PFF break-even" if price is not None else None, "result": res,
                            "units": units(res, price), "cash_pct": num(pick.cash_pct),
                            "tickets_pct": num(pick.tickets_pct)})
                if c is not None:
                    row.update({"pff_close_line_home": num(c.market_line) if market != "moneyline" else None,
                                "pff_close_projection_home": num(c.greenline_line) if market != "moneyline" else None,
                                "pff_clv": num(c.clv)})
            out.append(row)
    return out


# ---------------------------------------------------------------- 2026 captures

def rows_2026() -> list[dict]:
    from greenline_clv import load_flags
    from greenline_clv_all_eras import CAPTURE_SNAPSHOTS, book_closes, consensus
    from greenline_price_filter import build
    from greenline_season_review import load as review_load

    graded, _ = review_load(2026)
    res = {(r["week"], r["pff_game_id"], r["market"]): r for r in graded}
    teams = {(f["week"], f["pff_game_id"]): f["teams"] for f in load_flags()}
    _, by_teams = book_closes((2026,))
    pf = {(r["week"], r["game_id"]): r for r in build()[0]}
    ledger = {(r["week"], r["pff_game_id"]): r for r in
              csv.DictReader((GL_DIR / "greenline_bet_log.csv").open(encoding="utf-8")) if r["season"] == "2026"}
    import duckdb
    from cfb_paths import DB_PATH
    con = duckdb.connect(str(DB_PATH), read_only=True)
    cfbd = {frozenset((str(h), str(a))): str(g) for g, h, a in con.execute(
        "select game_id, home_team_id, away_team_id from core.fact_game where season = 2026").fetchall()}
    con.close()
    sched = {s["pff_game_id"]: s for s in csv.DictReader((GL_DIR / "pff_schedule_2026.csv").open(encoding="utf-8"))}

    out = []
    for p in sorted(GL_DIR.glob("pff_greenline_2026_w*.csv"), key=lambda p: p.stem):
        wk = p.stem.rsplit("_w", 1)[1]
        if not wk.isdigit():
            continue
        listed = set()
        lp = GL_DIR / f"greenline_unders_2026_w{wk}.csv"
        if lp.exists():
            listed = {r["game_id"] for r in csv.DictReader(lp.open(encoding="utf-8"))}
        for f in csv.DictReader(p.open(encoding="utf-8")):
            gid, k = f["pff_game_id"], (f.get("kickoff_raw") or "")[:16]
            tbd = int(k.endswith("00:00")) if k else None
            kutc = (datetime.fromisoformat(k).replace(tzinfo=ET).astimezone(ZoneInfo("UTC")).isoformat()
                    if k else None)
            g = sched.get(gid, {})
            hp, ap = num(g.get("home_score")), num(g.get("away_score"))
            tm = teams.get((wk, gid))
            base = {"source": "greenline", "era": "2026 capture", "season": 2026, "week": int(wk),
                    "kickoff_utc": kutc, "date_et": k[:10] or None, "kickoff_tbd": tbd, "pff_game_id": gid,
                    "cfbd_game_id": cfbd.get(tm) if tm else None, "away": f["away_abbreviation"],
                    "home": f["home_abbreviation"], "game": f"{f['away_abbreviation']} @ {f['home_abbreviation']}"}
            specs = (("total", f.get("total_best_side"), num(f.get("market_over_under")), None,
                      num(f.get("greenline_total_projection")), None, f.get("total_best_value")),
                     ("spread", f.get("spread_best_side"), num(f.get("market_spread")), None,
                      num(f.get("greenline_spread")), None, f.get("spread_best_value")),
                     ("moneyline", f.get("money_line_best_side"), num(f.get("market_money_line_home")),
                      num(f.get("market_money_line_away")), num(f.get("greenline_money_line_home")),
                      num(f.get("greenline_money_line_away")), f.get("money_line_best_value")))
            for market, side, mlh, mla, ph, pa, val in specs:
                gr = res.get((wk, gid, market))
                if mlh is None and market == "total" and gr:
                    mlh = gr["line"]      # capture had no total; the grader took it from the under list
                if mlh is None and market != "moneyline":
                    continue
                row = dict(base, market=market, is_pick=int(bool(side)), pick_side=side or None,
                           market_line_home=mlh, market_line_away=mla, pff_projection_home=ph,
                           pff_projection_away=pa, pff_value=num(val))
                if gr:   # graded: the season review's final (PFF, else warehouse) and its line
                    row.update(result=gr["result"], price=gr["price"],
                               clv_pff_board=gr["clv"], pff_win_prob=gr["p"])
                if side:
                    pl = side_line(market, side, mlh, mla) if not gr else (
                        gr["line"] if market != "spread" else side_line(market, side, gr["line"]))
                    row["pick_line"] = pl
                    price = row.get("price", -110 if market != "moneyline" else pl)
                    row["price"] = price
                    row["price_source"] = "market price" if market == "moneyline" else "assumed -110"
                    row["units"] = units(row.get("result"), price)
                    if row.get("pff_win_prob") is None:
                        row["pff_win_prob"] = num(f.get(f"{side}_cover_probability" if market == "total" else
                                                        f"{'spread' if market == 'spread' else 'money_line'}_{side}_cover_probability"))
                row.update(home_points=hp, away_points=ap,
                           actual_total=hp + ap if hp is not None and ap is not None else None)
                if market == "total":
                    row["on_under_list"] = int(gid in listed)
                    close, _ = consensus(by_teams.get((2026, tm))) if tm else (None, "")
                    row["close_rest"] = close
                    if close is not None and side and row.get("pick_line") is not None:
                        row["clv_rest"] = (row["pick_line"] - close) if side == "under" else (close - row["pick_line"])
                    b = pf.get((wk, gid))
                    if b:
                        row.update(best_book=b["book"], book_line=b["book_line"], book_odds=b["odds"],
                                   price_snapshot=CAPTURE_SNAPSHOTS.get(wk), pinnacle_fair=b["pin_fair"],
                                   proj_gap=b["proj_gap"], proj_edge=b["proj_edge"], rule_c=int(b["C"]),
                                   rule_e=int(b["E"]), book_result=b["result"], book_units=b["net"])
                    led = ledger.get((wk, gid))
                    if led:
                        row.update(bet=led["bet"] or None, line_taken=led["line_taken"] or None,
                                   price_taken=led["price_taken"] or None, stake_units=led["stake_units"] or None)
                out.append(row)
    return out


def personal_rows() -> list[dict]:
    from greenline_season_review import personal_totals
    out = []
    for yr in (2023, 2024, 2025):
        for r in personal_totals(yr):
            out.append({"source": "personal", "era": "personal 2023-25", "season": yr, "date_et": r["date"],
                        "game": r["game"], "market": "total", "is_pick": 1, "pick_side": r["side"],
                        "pick_line": r["line"], "price": r["price"], "price_source": "price paid",
                        "result": r["result"], "units": units(r["result"], r["price"])})
    return out


# ---------------------------------------------------------------- checks

def record(rows, era, market, source="greenline"):
    s = [r for r in rows if r["source"] == source and r["era"] == era and r["market"] == market and r.get("is_pick")]
    return tuple(sum(r.get("result") == x for r in s) for x in ("win", "loss", "push"))


def verify(rows: list[dict]) -> None:
    """Reproduce the records on file; a sign or convention bug cannot survive these."""
    keys = [(r["era"], r.get("pff_game_id") or r.get("cfbd_game_id") or r["game"], r.get("week"), r["market"])
            for r in rows if r["source"] == "greenline"]
    assert len(keys) == len(set(keys)), "greenline rows must be unique per (era, game, week, market)"
    assert record(rows, "2020 PFF_hist", "total") == (71, 59, 1), record(rows, "2020 PFF_hist", "total")
    assert record(rows, "2022-23 exports", "total") == (46, 42, 2), record(rows, "2022-23 exports", "total")
    assert record(rows, "2026 capture", "total")[:2] == (85, 79), record(rows, "2026 capture", "total")
    assert record(rows, "2026 capture", "spread") == (79, 82, 3), record(rows, "2026 capture", "spread")
    assert record(rows, "2026 capture", "moneyline")[:2] == (69, 87), record(rows, "2026 capture", "moneyline")
    # 2020 spreads: our grade at the side's own number must equal PFF's published result
    s20 = [r for r in rows if r["era"] == "2020 PFF_hist" and r["market"] == "spread" and r.get("is_pick")
           and r.get("result")]
    mine = [grade("spread", r["pick_side"], r["pick_line"], r["home_points"], r["away_points"]) for r in s20]
    assert all(m == r["result"] for m, r in zip(mine, s20)), "2020 spread sign convention"
    assert sum(1 for r in rows if r["source"] == "personal") >= 200


def self_check() -> None:
    assert side_line("spread", "away", -7.0) == 7.0 and side_line("spread", "home", -7.0) == -7.0
    assert side_line("moneyline", "away", -300, 250) == 250
    assert grade("spread", "away", 7.0, 24, 20) == "win"     # away +7 loses by 4
    assert grade("total", "under", 49.5, 20, 21) == "win" and grade("total", "over", 41.0, 20, 21) == "push"
    assert units("win", -110) == 100 / 110 and units("loss", -110) == -1 and units("push", 150) == 0
    assert american(0.5238095) == -110 and american(0.4) == 150
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    rows = archive_rows() + rows_2026() + personal_rows()
    verify(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    df = pd.DataFrame(rows)
    print(df.groupby(["source", "era", "market"]).agg(rows=("market", "size"), picks=("is_pick", "sum"),
                                                      graded=("result", "count")).to_string())
    print(f"\nwrote {len(rows)} rows x {len(COLUMNS)} columns -> {OUT}")


if __name__ == "__main__":
    main()
