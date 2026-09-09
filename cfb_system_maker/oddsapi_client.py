"""Client over the-odds-api.com v4 — college football odds snapshots.

One call per run: ``/v4/sports/{sport}/odds`` returns every upcoming NCAAF game
with each book's current prices. There is no history on this endpoint -- the
payload is a live SNAPSHOT -- so a run writes a new timestamped file rather than
resuming an old one, and ``pulled_at`` travels inside the envelope instead of
being implied by the filename. Line movement is the difference between two
snapshots, which only works if every snapshot says when it was taken.

The historical endpoint (``/v4/historical/...``) is paid-only; on the free plan
it returns 401 ``HISTORICAL_UNAVAILABLE_ON_FREE_USAGE_PLAN``. Nothing here calls
it. See `docs/oddsapi-ingest.md` for the quota math and the join-key problem.

CAVEAT: this API authenticates by **query parameter**, not a header like every
other client in this repo. The key must never reach stdout, a log, or an
exception message -- `_redact` exists for exactly that and every raise goes
through it.

``fetch_fn`` is injectable so tests run network-free.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_ncaaf"

# Cost is one credit per region per market, so this default costs 3. The free
# plan is 500/month: a daily pull is 90, every 6h is 360, hourly blows the cap.
DEFAULT_REGIONS: tuple[str, ...] = ("us",)
DEFAULT_MARKETS: tuple[str, ...] = ("h2h", "spreads", "totals")

# (payload, response headers) -- the quota headers are the only way to see what a
# call cost, so they have to come back with the body.
Fetcher = Callable[[str, dict[str, Any]], tuple[Any, dict[str, str]]]


def find_odds_token(env_path: str | Path = "env.env") -> str:
    for key in ("ODDS_API_KEY", "ODDS_API"):
        if os.environ.get(key):
            return os.environ[key]

    path = Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"ODDS_API_KEY", "ODDS_API"}:
                return value.strip()

    raise RuntimeError("Odds API token not found in env or env.env")


def fetch_odds(
    *,
    token: str,
    sport: str = SPORT,
    regions: tuple[str, ...] = DEFAULT_REGIONS,
    markets: tuple[str, ...] = DEFAULT_MARKETS,
    odds_format: str = "american",
    fetch_fn: Fetcher | None = None,
) -> dict[str, Any]:
    """One snapshot of every upcoming game's odds, wrapped in a dated envelope."""
    fetch = fetch_fn or _fetch
    url = f"{BASE_URL}/sports/{sport}/odds"
    params = {
        "apiKey": token,
        "regions": ",".join(regions),
        "markets": ",".join(markets),
        "oddsFormat": odds_format,
    }
    events, headers = fetch(url, params)
    return {
        "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sport": sport,
        "regions": list(regions),
        "markets": list(markets),
        "odds_format": odds_format,
        "requests_last": _int_header(headers, "x-requests-last"),
        "requests_used": _int_header(headers, "x-requests-used"),
        "requests_remaining": _int_header(headers, "x-requests-remaining"),
        "events": events,
    }


def write_snapshot(payload: dict[str, Any], out_dir: str | Path) -> Path:
    """Write one snapshot. Lands in `ingest/`, which the warehouse does not glob."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = payload["pulled_at"].replace(":", "").replace("-", "")
    path = folder / f"odds_{payload['sport']}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _fetch(url: str, params: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
            headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers
    except urllib.error.HTTPError as exc:
        # exc carries the full URL on `.url` and often in the body; both hold the key.
        detail = _redact(exc.read().decode("utf-8", "replace")[:400], params.get("apiKey"))
        raise RuntimeError(f"HTTP {exc.code} from {_redact(url, params.get('apiKey'))}: {detail}") from None


def _redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def _int_header(headers: dict[str, str], name: str) -> int | None:
    value = headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
