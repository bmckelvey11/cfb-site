"""Log a day's spread picks with the price available at pick time, then grade them.

    # log (once, before kickoff): picks JSON -> ledger CSV, prices from one odds snapshot
    python research/spread/scripts/spread_picks_ledger.py log --picks picks.json \
        --odds data/ingest/oddsapi/odds_americanfootball_ncaaf_<stamp>.json \
        --games data/raw/games_2026.json --ledger spread_picks_ledger.csv

    # grade (after the games): fills close, CLV, and result for ungraded rows
    python research/spread/scripts/spread_picks_ledger.py grade --ledger spread_picks_ledger.csv \
        --games data/raw/games_2026.json --odds-dir data/ingest/oddsapi

picks.json is a list of {"date", "away", "home", "side", "tier", "top6", "glicko", "gap", "note"}
where side is the team name exactly as `away` or `home`. `line` is the pick team's spread
(negative = that team favoured). The close is the median home spread across books in the last
odds snapshot pulled before kickoff. `result` grades at the best line logged, `result_consensus` at the
median line. CLV is in points from the pick's side: positive means the
close moved toward the pick (the line you got beat the close).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from daily_spread_breakdown import names_match, norm  # noqa: E402


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _event(odds: dict, away: str, home: str):
    for e in odds["events"]:
        if names_match(home, e["home_team"]) and names_match(away, e["away_team"]):
            return e
    return None


def _book_points(e: dict, team_odds_name: str) -> list[tuple[float, int, str]]:
    out = []
    for b in e["bookmakers"]:
        for m in b["markets"]:
            if m["key"] == "spreads":
                for o in m["outcomes"]:
                    if o["name"] == team_odds_name:
                        out.append((o["point"], o["price"], b["title"]))
    return out


def _snap_time(path: str) -> datetime:
    stamp = os.path.basename(path).rsplit("_", 1)[-1].removesuffix(".json")
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _game(games: list, away: str, home: str, day: str):
    """The game between these teams kicking off within two days of `day` (UTC dates drift)."""
    target = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    for g in games:
        if norm(g["homeTeam"]) == norm(home) and norm(g["awayTeam"]) == norm(away) \
                and abs((_ts(g["startDate"]) - target).days) <= 2:
            return g
    return None


def log(a) -> None:
    picks = json.load(open(a.picks))
    odds = json.load(open(a.odds))
    games = json.load(open(a.games))
    rows = []
    for p in picks:
        g = _game(games, p["away"], p["home"], p["date"])
        e = _event(odds, p["away"], p["home"])
        side_odds = e["home_team"] if p["side"] == p["home"] else e["away_team"]
        pts = _book_points(e, side_odds)
        line, price, book = max(pts, key=lambda t: (t[0], t[1]))  # most points, then best price
        home_med = statistics.median(pt for pt, _, _ in _book_points(e, e["home_team"]))
        rows.append({
            "date": p["date"], "game_id": g["id"] if g else None, "kickoff_utc": g["startDate"] if g else None,
            "away": p["away"], "home": p["home"], "side": p["side"], "tier": p["tier"],
            "line": line, "odds": price, "book": book,
            "consensus_side_line": home_med if p["side"] == p["home"] else -home_med,
            "top6": p.get("top6"), "glicko": p.get("glicko"), "gap": p.get("gap"), "note": p.get("note", ""),
            "priced_from": odds["pulled_at"], "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "close_side_line": None, "clv": None, "margin_side": None, "result": None, "result_consensus": None,
        })
    new = pd.DataFrame(rows)
    if os.path.exists(a.ledger):
        old = pd.read_csv(a.ledger)
        new = pd.concat([old, new[~new.set_index(["date", "away", "home"]).index.isin(
            old.set_index(["date", "away", "home"]).index)]], ignore_index=True)
    new.to_csv(a.ledger, index=False)
    print(f"{len(rows)} picks logged -> {a.ledger}")


def grade(a) -> None:
    led = pd.read_csv(a.ledger, dtype={"result": object, "result_consensus": object})
    games = {g["id"]: g for g in json.load(open(a.games))}
    snaps = sorted(glob.glob(os.path.join(a.odds_dir, "odds_americanfootball_ncaaf_*.json")))
    snap_cache = {}
    for i, r in led[led.result.isna()].iterrows():
        g = games.get(int(r.game_id)) if pd.notna(r.game_id) else None
        if g is None or not g.get("completed") or g.get("homePoints") is None:
            continue
        kick = _ts(g["startDate"])
        before = [s for s in snaps if _snap_time(s) < kick]
        close = None
        for s in reversed(before):
            d = snap_cache.setdefault(s, json.load(open(s)))
            e = _event(d, r.away, r.home)
            if e:
                pts = [p for p, _, _ in _book_points(e, e["home_team"])]
                if pts:
                    close = statistics.median(pts)
                    break
        margin_home = g["homePoints"] - g["awayPoints"]
        is_home = r.side == r.home
        margin_side = margin_home if is_home else -margin_home
        cover = margin_side + r.line
        led.at[i, "margin_side"] = margin_side
        led.at[i, "result"] = "W" if cover > 0 else "L" if cover < 0 else "P"
        cover_c = margin_side + r.consensus_side_line
        led.at[i, "result_consensus"] = "W" if cover_c > 0 else "L" if cover_c < 0 else "P"
        if close is not None:
            close_side = close if is_home else -close
            led.at[i, "close_side_line"] = close_side
            led.at[i, "clv"] = round(r.line - close_side, 2)
    led.to_csv(a.ledger, index=False)
    done = led[led.result.notna()]
    if len(done):
        for tier, t in [("all", done)] + list(done.groupby("tier")):
            w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
            wc, lc = (t.result_consensus == "W").sum(), (t.result_consensus == "L").sum()
            print(f"{tier:>8}: {w}-{l}-{p} at best line, {wc}-{lc} at consensus, "
                  f"mean CLV {pd.to_numeric(t.clv).mean():+.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("log")
    lp.add_argument("--picks", required=True); lp.add_argument("--odds", required=True)
    lp.add_argument("--games", required=True); lp.add_argument("--ledger", required=True)
    gp = sub.add_parser("grade")
    gp.add_argument("--ledger", required=True); gp.add_argument("--games", required=True)
    gp.add_argument("--odds-dir", required=True)
    a = ap.parse_args()
    log(a) if a.cmd == "log" else grade(a)


if __name__ == "__main__":
    main()
