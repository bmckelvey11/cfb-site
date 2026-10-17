"""The live odds page: a standalone local Flask app, like `matchup`.

Run: `python -m cfb_system_maker live --port 5060` (bound to 127.0.0.1). The page asks
`/api/live` every 30 seconds; the server re-reads Polymarket at most every `CACHE_SECONDS`, so
several open tabs cost one pull. Polymarket answers 403 from the cloud, so this runs on the Mac.
Needs no warehouse and no API key.
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


def create_app(fetch_fn: pm.Fetcher | None = None,
               clock=lambda: datetime.now(timezone.utc),
               cache_seconds: float = CACHE_SECONDS) -> Flask:
    app = Flask(__name__)
    fetch = fetch_fn or pm._fetch
    lock = threading.Lock()
    cache: dict = {"at": None, "events": None, "series": None}

    def events() -> tuple[list[dict], datetime]:
        with lock:
            fresh = cache["at"] and time.monotonic() - cache["mono"] < cache_seconds
            if not fresh:
                cache["series"] = cache["series"] or pm.find_series_id(fetch)
                cache["events"], _ = pm.list_events(fetch, cache["series"])
                cache["at"], cache["mono"] = clock().replace(microsecond=0), time.monotonic()
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
