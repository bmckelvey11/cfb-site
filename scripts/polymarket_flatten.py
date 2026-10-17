"""Polymarket snapshots -> `data/processed/polymarket/*.csv`, ready for the loader.

Two tables, the same split as the-odds-api's:

**`pm_market_tick`** -- one row per outcome per market per snapshot: `(pulled_at, market_id,
side)`. A game has a whole ladder of spread and total markets (31 spreads and 21 totals on
one game, 2026-10-17), and every rung is kept: no market is flagged as the main line, so
picking one (price nearest 0.5, or most liquidity) is a query, not a flatten decision.

**`pm_snapshot`** -- one row per pull.

Three conversions the raw markets need, all done here so nothing downstream repeats them:

- `outcomes` and `outcomePrices` arrive as JSON-encoded *strings*, not lists.
- A spread market's `line` belongs to its FIRST outcome ("Spread: James Madison (-12.5)",
  outcomes `["James Madison", "Georgia State"]`, line -12.5). The second outcome gets the
  negated line, so `line` is always that row's own team's handicap -- the same convention
  as `oa_odds_tick`. Totals carry the same line on Over and Under.
- `bestBid`/`bestAsk`/`lastTradePrice` quote the first outcome. A share of the second is
  the complement, so its bid is `1 - ask` and its ask is `1 - bid`.

Like `oddsapi_flatten`, no `game_id` is resolved here; `home_school`/`away_school` carry
CFBD's spelling for a later join.

    python scripts/polymarket_flatten.py
    python scripts/polymarket_flatten.py --list-unresolved

Exits 1 if a team name fails to resolve (the row is still written with Polymarket's name).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.polymarket_schema import PM_TABLES, school_key  # noqa: E402
from oddsapi_flatten import cfbd_schools  # noqa: E402

IN_DIR = DATA_ROOT / "ingest" / "polymarket"
OUT_DIR = DATA_ROOT / "processed" / "polymarket"

TICK_COLUMNS = ["pulled_at", "event_id", "event_slug", "pm_game_id", "start_time",
                "home_team", "away_team", "home_school", "away_school",
                "market_id", "market_slug", "market", "side", "outcome_name", "line",
                "price", "best_bid", "best_ask", "last_trade_price", "liquidity", "volume",
                "accepting_orders", "updated_at", "_source_file"]
SNAPSHOT_COLUMNS = ["pulled_at", "sport", "series_id", "market_types", "pages",
                    "events_seen", "event_count", "market_count", "_source_file"]

# Polymarket's own term is `moneyline`; `oa_odds_tick` says `h2h`. Kept as the vendor's.
_TOTALS_SIDES = {"over": "over", "under": "under"}


def home_away(event: dict) -> tuple[str, str]:
    """(home, away) school names as Polymarket spells them.

    From `teams[].ordering` when present; else from the title, which lists away first for
    CFB ("Georgia State vs. James Madison", `/sports` ordering = "away").
    """
    by_order = {t.get("ordering"): t.get("alias") or t.get("name") for t in event.get("teams") or []}
    if by_order.get("home") and by_order.get("away"):
        return by_order["home"], by_order["away"]
    away, sep, home = str(event.get("title", "")).partition(" vs. ")
    if not sep:
        raise ValueError(f"cannot tell home from away in event {event.get('slug')!r}")
    return home.strip(), away.strip()


def side_of(outcome_name: str, home: str, away: str) -> str:
    """`home` / `away` / `over` / `under`, or raise -- a default would flip a spread's sign."""
    key = str(outcome_name).strip().lower()
    if key in _TOTALS_SIDES:
        return _TOTALS_SIDES[key]
    if outcome_name == home:
        return "home"
    if outcome_name == away:
        return "away"
    raise ValueError(f"outcome {outcome_name!r} is neither Over/Under nor {away!r} / {home!r}")


def _as_list(value) -> list:
    if value is None:
        return []
    return json.loads(value) if isinstance(value, str) else list(value)


def _num(value):
    if value is None or value == "":
        return ""
    return round(float(value), 6)


def _complement(value):
    return "" if value in (None, "") else round(1 - float(value), 6)


def market_rows(market: dict, home: str, away: str) -> list[dict]:
    names = _as_list(market.get("outcomes"))
    prices = _as_list(market.get("outcomePrices"))
    kind = market.get("sportsMarketType", "")
    line = market.get("line")
    rows = []
    for i, name in enumerate(names):
        first = i == 0
        if line is None or kind == "moneyline":
            row_line = ""
        elif kind == "spreads":
            row_line = float(line) if first else -float(line)
        else:
            row_line = float(line)
        rows.append({
            "market_id": str(market.get("id", "")),
            "market_slug": market.get("slug", ""),
            "market": kind,
            "side": side_of(name, home, away),
            "outcome_name": name,
            "line": row_line,
            "price": _num(prices[i]) if i < len(prices) else "",
            "best_bid": _num(market.get("bestBid")) if first else _complement(market.get("bestAsk")),
            "best_ask": _num(market.get("bestAsk")) if first else _complement(market.get("bestBid")),
            "last_trade_price": (_num(market.get("lastTradePrice")) if first
                                 else _complement(market.get("lastTradePrice"))),
            "liquidity": _num(market.get("liquidityNum")),
            "volume": _num(market.get("volumeNum")),
            "accepting_orders": "" if market.get("acceptingOrders") is None
                                else str(bool(market["acceptingOrders"])).lower(),
            "updated_at": market.get("updatedAt") or "",
        })
    return rows


def flatten(paths: list[Path], schools: dict[str, str]
             ) -> tuple[list[dict], list[dict], dict[str, str]]:
    ticks: list[dict] = []
    snapshots: list[dict] = []
    names: dict[str, str] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pulled_at = payload.get("pulled_at", "")
        events = payload.get("events", [])
        market_count = 0
        for event in events:
            home, away = home_away(event)
            home_school = schools.get(school_key(home), "")
            away_school = schools.get(school_key(away), "")
            names[home] = home_school
            names[away] = away_school
            base = {
                "pulled_at": pulled_at,
                "event_id": str(event.get("id", "")),
                "event_slug": event.get("slug", ""),
                "pm_game_id": "" if event.get("gameId") is None else str(event["gameId"]),
                "start_time": event.get("startTime") or "",
                "home_team": home,
                "away_team": away,
                "home_school": home_school,
                "away_school": away_school,
            }
            for market in event.get("markets", []):
                market_count += 1
                for row in market_rows(market, home, away):
                    ticks.append({**base, **row, "_source_file": path.name})
        snapshots.append({
            "pulled_at": pulled_at,
            "sport": payload.get("sport", ""),
            "series_id": payload.get("series_id", ""),
            "market_types": ",".join(payload.get("market_types") or []),
            "pages": payload.get("pages", ""),
            "events_seen": payload.get("events_seen", ""),
            "event_count": len(events),
            "market_count": market_count,
            "_source_file": path.name,
        })
    return ticks, snapshots, names


def write(ticks: list[dict], snapshots: list[dict], out_dir: Path = OUT_DIR
          ) -> list[tuple[str, int]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows, columns in (("pm_market_tick", ticks, TICK_COLUMNS),
                                ("pm_snapshot", snapshots, SNAPSHOT_COLUMNS)):
        with (out_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        written.append((name, len(rows)))
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in-dir", type=Path, default=IN_DIR)
    ap.add_argument("--list-unresolved", action="store_true")
    args = ap.parse_args(argv)

    paths = sorted(args.in_dir.glob("pm_*.json"))
    if not paths:
        print(f"no snapshots in {args.in_dir}")
        return 0

    schools = cfbd_schools()
    if not schools:
        print("  ERROR no data/raw/teams_<season>.json on disk; names cannot be resolved")
        return 1

    ticks, snapshots, names = flatten(paths, schools)
    written = write(ticks, snapshots)
    assert {name for name, _ in written} == set(PM_TABLES), "write() drifted from PM_TABLES"
    for name, rows in written:
        print(f"  {name:16s} {rows:,} rows")

    bad = sorted(vendor for vendor, cfbd in names.items() if not cfbd)
    print(f"  {len(paths)} snapshots, {len(names)} distinct team names, {len(bad)} unresolved")
    if bad:
        print("  UNRESOLVED -- add to cfb_system_maker/polymarket_schema.ALIASES:")
        for name in (bad if args.list_unresolved else bad[:5]):
            print(f"    {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
