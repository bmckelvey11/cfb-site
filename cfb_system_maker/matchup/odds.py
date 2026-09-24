"""The newest Odds API snapshot, read straight from `data/ingest/oddsapi/`.

The warehouse loads these files only at the 05:00 rebuild; `CFB-Odds-Snapshot` writes a new one
every 6 h. Reading the newest file here takes the page's DraftKings/FanDuel numbers from up to a
day stale to up to 6 h. It is the page's one read outside the warehouse: stdlib JSON, no API
call, no key.

Names resolve with the loader's own head rule (`oddsapi_schema.candidates`) against
`core.dim_team.school`, not a new matcher. Games join on the unordered team pair
(`docs/oddsapi-game-join-2026-09-10.md`): the vendor's home/away can disagree with CFBD's at
neutral sites, so every number is keyed by school, never by side.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cfb_system_maker.oddsapi_schema import candidates, norm

PATTERN = "odds_americanfootball_ncaaf_*.json"


def newest_snapshot(odds_dir: Path) -> Path | None:
    # The stamp in the name is UTC ISO basic format, so name order is time order.
    files = sorted(Path(odds_dir).glob(PATTERN))
    return files[-1] if files else None


def school_index(schools: list[str]) -> dict[str, str]:
    return {norm(s): s for s in schools}


def resolve(name: str, index: dict[str, str]) -> str | None:
    for head in candidates(name):
        if head in index:
            return index[head]
    return None


def read_lines(path: Path | None, index: dict[str, str]) -> dict:
    """{"pulled_at", "file", "games": {frozenset({school_a, school_b}): game}}.

    game = {"commence_time", "books": {book: {"spread": {school: [point, price]},
    "total": {"over": [point, price], "under": [point, price]}, "ml": {school: price}}}}.
    Events whose teams do not both resolve are counted in "unresolved", not guessed.
    """
    if path is None:
        return {"pulled_at": None, "file": None, "games": {}, "unresolved": 0}
    snap = json.loads(Path(path).read_text(encoding="utf-8"))
    games: dict[frozenset, dict] = {}
    unresolved = 0
    for ev in snap.get("events", []):
        side = {ev["home_team"]: resolve(ev["home_team"], index),
                ev["away_team"]: resolve(ev["away_team"], index)}
        if None in side.values():
            unresolved += 1
            continue
        books = {}
        for bk in ev.get("bookmakers", []):
            book = {"spread": {}, "total": {}, "ml": {}, "last_update": bk.get("last_update")}
            for mk in bk.get("markets", []):
                for o in mk.get("outcomes", []):
                    if mk["key"] == "spreads" and o["name"] in side:
                        book["spread"][side[o["name"]]] = [o.get("point"), o.get("price")]
                    elif mk["key"] == "h2h" and o["name"] in side:
                        book["ml"][side[o["name"]]] = o.get("price")
                    elif mk["key"] == "totals":
                        book["total"][o["name"].lower()] = [o.get("point"), o.get("price")]
            books[bk["key"]] = book
        games[frozenset(side.values())] = {"commence_time": ev.get("commence_time"), "books": books}
    return {"pulled_at": snap.get("pulled_at"), "file": Path(path).name, "games": games,
            "unresolved": unresolved}


def pulled_at(lines: dict) -> datetime | None:
    raw = lines.get("pulled_at")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
