"""Client over Polymarket's public Gamma API -- college football game prices.

Read-only. Gamma is Polymarket's public market-data API: no key, no wallet, no
account. Nothing here places or signs an order; trading goes through a different
API (CLOB) this repo never calls.

One run is one SNAPSHOT, like the-odds-api: every open CFB game's moneyline,
spread and total markets as priced right now. Prices are probabilities (0-1), not
American odds -- `0.235` means the market charges 23.5 cents for a share that pays
$1 if that side wins.

Shape, measured live 2026-10-17 (docs/polymarket-ingest.md has the detail):

- `/sports` lists one entry per league; CFB is `sport == "cfb"`, and its `series`
  field is the id of this season's game series (`12756` = `cfb-2026`). It is read
  every run rather than pinned, because the series id changes each season.
- `/events/keyset?series_id=...` pages through that series' events. The list is
  under `events`; the next page is `after_cursor=<next_cursor>`, and the last page
  has no `next_cursor`.
- `closed=false` still returns finished games, and each game has an
  `<slug>-exact-margin` companion event, so both are filtered here.
- Each game carries ~220 markets: a full ladder of alternate spreads and totals
  plus quarter/half lines and player-ish props. Only full-game moneyline, spreads
  and totals are kept, with a trimmed field set -- the untrimmed event is ~800KB.

``fetch_fn`` is injectable so tests run network-free.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BASE_URL = "https://gamma-api.polymarket.com"
SPORT = "cfb"

# Full-game markets only. `exact_margin`, `team_totals`, quarter/half lines and the
# stat props exist too; add a type here to start keeping it.
MARKET_TYPES: frozenset[str] = frozenset({"moneyline", "spreads", "totals"})

PAGE_LIMIT = 100
MAX_PAGES = 50        # ~360 events was 4 pages; a runaway cursor stops here

EVENT_FIELDS = ("id", "slug", "title", "startTime", "gameId", "eventWeek")
TEAM_FIELDS = ("name", "alias", "abbreviation", "ordering", "providerId")
MARKET_FIELDS = (
    "id", "slug", "question", "sportsMarketType", "line", "outcomes", "outcomePrices",
    "bestBid", "bestAsk", "lastTradePrice", "volumeNum", "liquidityNum",
    "acceptingOrders", "updatedAt",
)

HEADERS = {"User-Agent": "cfb-research/1.0", "Accept": "application/json"}

Fetcher = Callable[[str, dict[str, Any]], Any]


def find_series_id(fetch: Fetcher, sport: str = SPORT) -> str:
    """This season's game series for `sport`, from `/sports`."""
    for entry in fetch(f"{BASE_URL}/sports", {}):
        if entry.get("sport") == sport and entry.get("series"):
            return str(entry["series"])
    raise RuntimeError(f"no series for sport {sport!r} in /sports")


def fetch_markets(
    *,
    sport: str = SPORT,
    market_types: frozenset[str] = MARKET_TYPES,
    fetch_fn: Fetcher | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One snapshot of every upcoming CFB game's prices, wrapped in a dated envelope."""
    fetch = fetch_fn or _fetch
    pulled = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    series_id = find_series_id(fetch, sport)

    raw_events, pages = list_events(fetch, series_id)
    events = [trim_event(e, market_types) for e in raw_events if is_upcoming_game(e, pulled)]
    return {
        "pulled_at": pulled.isoformat().replace("+00:00", "Z"),
        "sport": sport,
        "series_id": series_id,
        "market_types": sorted(market_types),
        "pages": pages,
        "events_seen": len(raw_events),
        "events": events,
    }


def list_events(fetch: Fetcher, series_id: str) -> tuple[list[dict], int]:
    """Every open event in the series, untrimmed, following `next_cursor`. (events, pages)"""
    events: list[dict] = []
    cursor = None
    pages = 0
    while pages < MAX_PAGES:
        params: dict[str, Any] = {"series_id": series_id, "closed": "false", "limit": PAGE_LIMIT}
        if cursor:
            params["after_cursor"] = cursor
        body = fetch(f"{BASE_URL}/events/keyset", params)
        pages += 1
        events.extend(body.get("events") or [])
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return events, pages


def is_upcoming_game(event: dict, pulled: datetime) -> bool:
    """A real game that has not kicked off yet.

    Pre-kickoff only, so every stored price is a pre-game price: an in-play quote
    would be lookahead to anything that joins it as a "line". Drops the
    `-exact-margin` companions, finished games, and series entries with no
    `startTime` (AP-poll futures).
    """
    if str(event.get("slug", "")).endswith("-exact-margin") or event.get("ended"):
        return False
    start = parse_time(event.get("startTime"))
    return start is not None and start > pulled


def trim_event(event: dict, market_types: frozenset[str] = MARKET_TYPES) -> dict:
    out = {k: event.get(k) for k in EVENT_FIELDS}
    out["teams"] = [{k: t.get(k) for k in TEAM_FIELDS} for t in event.get("teams") or []]
    out["markets"] = [
        {k: m.get(k) for k in MARKET_FIELDS}
        for m in event.get("markets") or []
        if m.get("sportsMarketType") in market_types
    ]
    return out


def write_snapshot(payload: dict[str, Any], out_dir: str | Path) -> Path:
    """Write one snapshot. Lands in `ingest/`, which the warehouse does not glob."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = payload["pulled_at"].replace(":", "").replace("-", "")
    path = folder / f"pm_{payload['sport']}_{stamp}.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def parse_time(value: Any) -> datetime | None:
    """ISO `2026-10-17T16:00:00Z`, or None. (`gameStartTime` uses a space form; not read.)"""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fetch(url: str, params: dict[str, Any]) -> Any:
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    request = urllib.request.Request(full, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from None
