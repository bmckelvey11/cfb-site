"""Turn Polymarket's open CFB events into a live board: score, clock, and each game's main lines.

Read-only and display-only. Nothing here is stored, so these in-play prices never reach the
warehouse (they would be lookahead to anything that joins them as a "line").

Game state comes from the event itself (measured live 2026-10-17):

- Not started: no `live`/`ended`/`score`/`period`/`elapsed` keys at all; `startTime` is kickoff.
- Live: `live` true, `score` "away-home" (e.g. "0-37"), `period` "Q1".."Q4", "End Q2", "End Q3",
  `elapsed` the mm:ss game clock ("" at a break).
- Finished: `ended` true, `period` "VFT". `closed=false` still returns these. `period` "CAN" is
  a cancelled game with `ended` false.
- Starting: kicked off by `startTime` but not yet flagged `live`. `/events/keyset` is cached
  a few minutes behind (18:58Z data served at 19:02Z), so for a while after kickoff a game has
  neither flag; it is listed with the live games rather than dropped. `/events?slug=` is
  fresher, which is why `app.py` re-reads live and starting games through it.

Main line: Polymarket flags none, and a rung nobody quotes shows a 0.495/0.505 placeholder with a
0.01/0.99 book, so "price nearest 50%" alone picks dead rungs. A rung counts only with both a bid
and an ask no more than `MAX_SPREAD` apart and at least `MIN_LIQUIDITY`, priced between `LOPSIDED` and
1 - `LOPSIDED`; of those, the one whose midpoint is nearest 50% is the main line. A game with no
such rung shows no line rather than a stale or decided one -- blowouts often have no live spread
at all. The moneyline is shown even from a wider book, flagged `wide`, since a team's win chance
is the number wanted however lopsided it is.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from pathlib import Path

from cfb_system_maker.polymarket_client import parse_time
from cfb_system_maker.polymarket_schema import school_key

MAX_SPREAD = 0.10      # wider than 10 cents and `outcomePrices` no longer matches the book
MIN_LIQUIDITY = 100.0  # placeholder rungs carry $5
LOPSIDED = 0.15        # a rung priced outside 15-85% is decided, not a line (Army -2.5 at 98.6%, up 49-24)
SOON = timedelta(hours=3)
STARTING = timedelta(hours=4)   # past kickoff with no live flag for longer than this: unknown
FINAL_PERIODS = {"VFT", "FT", "F"}


def state(event: dict, now: datetime) -> str:
    """One of live, starting, upcoming, final, other."""
    if event.get("ended") or event.get("period") in FINAL_PERIODS:
        return "final"
    if event.get("period") == "CAN":
        return "other"
    if event.get("live"):
        return "live"
    start = parse_time(event.get("startTime"))
    if start is None:
        return "other"
    if start > now:
        return "upcoming"
    return "starting" if now - start <= STARTING else "other"


def in_play(event: dict, now: datetime) -> bool:
    """Live or just kicked off: the games worth re-reading through the fresher `/events?slug=`."""
    return (not str(event.get("slug", "")).endswith("-exact-margin")
            and state(event, now) in ("live", "starting"))


def load_fbs(raw_dir: Path, season: int) -> frozenset[str]:
    """`school_key`s of this season's FBS teams from CFBD's `fbs_teams_{season}.json`.

    Falls back to last season's file before this season's is scraped; empty when neither
    exists, and the page then hides its FBS filter.
    """
    for year in (season, season - 1):
        path = Path(raw_dir) / f"fbs_teams_{year}.json"
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            return frozenset(school_key(r["school"]) for r in rows if r.get("school"))
    return frozenset()


def board(events: list[dict], now: datetime, soon: timedelta = SOON,
          fbs: frozenset[str] = frozenset()) -> dict[str, list[dict]]:
    """Live games, then games kicking off within `soon`. Exact-margin companions are skipped."""
    live, upcoming = [], []
    for event in events:
        if str(event.get("slug", "")).endswith("-exact-margin"):
            continue
        kind = state(event, now)
        if kind in ("live", "starting"):
            live.append(game(event, kind, fbs))
        elif kind == "upcoming" and parse_time(event["startTime"]) <= now + soon:
            upcoming.append(game(event, kind, fbs))
    live.sort(key=lambda g: (g["kickoff"] or "", g["title"]))
    upcoming.sort(key=lambda g: (g["kickoff"] or "", g["title"]))
    return {"live": live, "upcoming": upcoming}


def game(event: dict, kind: str, fbs: frozenset[str] = frozenset()) -> dict:
    away, home = teams(event)
    away_score, home_score = score(event.get("score"))
    markets = event.get("markets") or []
    return {
        "id": event.get("id"),
        "slug": event.get("slug"),
        "title": event.get("title"),
        "url": f"https://polymarket.com/event/{event.get('slug')}",
        "state": kind,
        "kickoff": event.get("startTime"),
        "updated_at": event.get("updatedAt"),
        "away": away, "home": home,
        "away_fbs": bool(away) and school_key(away) in fbs,
        "home_fbs": bool(home) and school_key(home) in fbs,
        "away_score": away_score, "home_score": home_score,
        "period": event.get("period") or None,
        "clock": event.get("elapsed") or None,
        "moneyline": moneyline(markets, away, home),
        "spread": main_line(markets, "spreads"),
        "total": main_line(markets, "totals"),
    }


def teams(event: dict) -> tuple[str | None, str | None]:
    """(away, home) school names. Falls back to the "Away vs. Home" title."""
    names = {t.get("ordering"): t.get("alias") or t.get("name") for t in event.get("teams") or []}
    if names.get("away") and names.get("home"):
        return names["away"], names["home"]
    parts = str(event.get("title") or "").split(" vs. ")
    return (parts[0], parts[1]) if len(parts) == 2 else (None, None)


def score(raw: Any) -> tuple[int | None, int | None]:
    """ "0-37" is away 0, home 37."""
    try:
        away, home = str(raw).split("-")
        return int(away), int(home)
    except (TypeError, ValueError):
        return None, None


def quote(market: dict) -> dict | None:
    """The first outcome's book, or None when it is too thin or too wide to trust."""
    bid, ask = market.get("bestBid"), market.get("bestAsk")
    if bid is None or ask is None or ask - bid > MAX_SPREAD or bid <= 0 or ask >= 1:
        return None
    if (market.get("liquidityNum") or 0) < MIN_LIQUIDITY:
        return None
    outcomes = _list(market.get("outcomes"))
    return {
        "mid": round((bid + ask) / 2, 4), "bid": bid, "ask": ask,
        "line": market.get("line"),
        "first": outcomes[0] if outcomes else None,
        "second": outcomes[1] if len(outcomes) > 1 else None,
        "liquidity": round(market.get("liquidityNum") or 0),
        "volume": round(market.get("volumeNum") or 0),
        "updated_at": market.get("updatedAt"),
        "slug": market.get("slug"),
    }


def main_line(markets: list[dict], kind: str) -> dict | None:
    """The tradable rung of `kind` whose midpoint is nearest 50%; ties go to more liquidity."""
    quotes = [q for m in markets if m.get("sportsMarketType") == kind and (q := quote(m))
              and LOPSIDED <= q["mid"] <= 1 - LOPSIDED]
    if not quotes:
        return None
    return min(quotes, key=lambda q: (abs(q["mid"] - 0.5), -q["liquidity"]))


def moneyline(markets: list[dict], away: str | None, home: str | None) -> dict | None:
    """Home win chance from the moneyline book, oriented to home whichever outcome is first."""
    for market in markets:
        if market.get("sportsMarketType") != "moneyline":
            continue
        bid, ask = market.get("bestBid"), market.get("bestAsk")
        if ask is None or (market.get("liquidityNum") or 0) < MIN_LIQUIDITY:
            return None
        if bid is None:           # no bid at all: fine on a near-certain loser, else a dead book
            if ask > MAX_SPREAD:
                return None
            bid = 0.0
        mid = (bid + ask) / 2
        outcomes = _list(market.get("outcomes"))
        if outcomes and home and outcomes[0] != home:
            mid = 1 - mid
        return {"home": round(mid, 4), "away": round(1 - mid, 4), "wide": ask - bid > MAX_SPREAD,
                "liquidity": round(market.get("liquidityNum") or 0),
                "updated_at": market.get("updatedAt")}
    return None


def _list(raw: Any) -> list:
    """`outcomes` arrives as a JSON-encoded string."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
