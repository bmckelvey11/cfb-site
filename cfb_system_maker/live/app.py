"""The live odds page: a standalone local Flask app, like `matchup`.

Run: `python -m cfb_system_maker live --port 5070` (bound to 127.0.0.1). The page asks
`/api/live` every 30 seconds. The game list comes from `/events/keyset`, which Polymarket serves
from a cache a few minutes behind, so it is re-read only every `LIST_SECONDS`; the games in play
are then re-read every `CACHE_SECONDS` through `/events?slug=`, which is current. Several open
tabs cost one pull. Polymarket answers 403 from the cloud, so this runs on the Mac. Needs no
warehouse and no API key.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory

from cfb_system_maker import polymarket_client as pm
from cfb_system_maker.live import board as board_mod

log = logging.getLogger(__name__)
TOKENS = Path(__file__).resolve().parents[1] / "static" / "tokens"
CACHE_SECONDS = 20
LIST_SECONDS = 120
SLUG_BATCH = 20


def create_app(fetch_fn: pm.Fetcher | None = None,
               clock=lambda: datetime.now(timezone.utc),
               cache_seconds: float = CACHE_SECONDS,
               list_seconds: float = LIST_SECONDS) -> Flask:
    app = Flask(__name__)
    fetch = fetch_fn or pm._fetch
    lock = threading.Lock()
    cache: dict = {"series": None, "list": None, "list_mono": None, "events": None, "at": None, "mono": None}

    def stale(key: str, seconds: float) -> bool:
        return cache[key] is None or time.monotonic() - cache[key] >= seconds

    def events() -> tuple[list[dict], datetime]:
        with lock:
            if stale("list_mono", list_seconds):
                cache["series"] = cache["series"] or pm.find_series_id(fetch)
                cache["list"], _ = pm.list_events(fetch, cache["series"])
                cache["list_mono"] = time.monotonic()
            if stale("mono", cache_seconds):
                now = clock().replace(microsecond=0)
                cache["events"] = refresh_in_play(fetch, cache["list"], now)
                cache["at"], cache["mono"] = now, time.monotonic()
            return cache["events"], cache["at"]

    @app.get("/")
    def page():
        return render_template("live.html")

    @app.get("/tokens/<name>.css")
    def tokens(name: str):
        return send_from_directory(TOKENS, f"{name}.css")

    @app.get("/api/live")
    def api_live():
        try:
            evs, pulled = events()
        except Exception as exc:  # network, 403, bad JSON: the page shows it and keeps polling
            log.warning("polymarket pull failed: %s", exc)
            return jsonify(error="polymarket_unavailable",
                           message="Couldn't reach Polymarket. Retrying shortly."), 503
        out = board_mod.board(evs, clock())
        return jsonify(pulled_at=pulled.isoformat().replace("+00:00", "Z"), **out)

    return app


def refresh_in_play(fetch: pm.Fetcher, events: list[dict], now: datetime) -> list[dict]:
    """`events` with each live or just-started game swapped for its current `/events?slug=` copy.

    A failed batch keeps the list's older copies; the page still shows a price, just a later one.
    """
    slugs = [e["slug"] for e in events if board_mod.in_play(e, now)]
    fresh: dict[str, dict] = {}
    for i in range(0, len(slugs), SLUG_BATCH):
        try:
            batch = fetch(f"{pm.BASE_URL}/events", {"slug": slugs[i:i + SLUG_BATCH]})
        except Exception as exc:
            log.warning("polymarket slug refresh failed: %s", exc)
            continue
        fresh.update({e.get("slug"): e for e in batch or [] if isinstance(e, dict)})
    return [fresh.get(e.get("slug"), e) for e in events]
