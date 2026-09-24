"""The matchup page: a standalone local Flask app, separate from `web.py`.

Run: `python -m cfb_system_maker matchup --port 5050` (bound to 127.0.0.1). Every API request
opens the warehouse read-only and closes it before responding; see `queries.warehouse`.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from cfb_system_maker.matchup import odds as odds_mod
from cfb_system_maker.matchup import queries as q

log = logging.getLogger(__name__)
TOKENS = Path(__file__).resolve().parents[1] / "static" / "tokens"


def _int(name: str, default: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        abort(400, f"{name} must be an integer")


def _flag(name: str, default: bool) -> bool:
    raw = request.args.get(name)
    return default if raw in (None, "") else raw not in ("0", "false", "off")


def create_app(db_path: Path | None = None, odds_dir: Path | None = None,
               clock=lambda: datetime.now(timezone.utc)) -> Flask:
    if db_path is None or odds_dir is None:
        from cfb_paths import DB_PATH, INGEST
        db_path = db_path or DB_PATH
        odds_dir = odds_dir or INGEST / "oddsapi"
    app = Flask(__name__)

    def lines(con) -> dict:
        return odds_mod.read_lines(odds_mod.newest_snapshot(odds_dir), q.school_index(con))

    @app.errorhandler(q.WarehouseBusy)
    def busy(exc):
        return jsonify(error="warehouse_rebuilding",
                       message="Warehouse rebuilding. Retry in a few minutes."), 503

    @app.get("/")
    def page():
        return render_template("matchup.html")

    @app.get("/tokens/<name>.css")
    def tokens(name: str):
        # The unit's Saturday Signal tokens, shared with web.py rather than copied.
        return send_from_directory(TOKENS, f"{name}.css")

    @app.get("/api/slate")
    def api_slate():
        with q.warehouse(db_path) as con:
            cur = q.current_week(con, clock())
            season = _int("season", cur["season"])
            week = _int("week", cur["week"] if season == cur["season"] else 1)
            season_type = request.args.get("season_type") or "regular"
            snap = lines(con)
            return jsonify(season=season, week=week, season_type=season_type, current=cur,
                           weeks=q.weeks(con, season),
                           snapshot={"file": snap["file"], "pulled_at": snap["pulled_at"]},
                           games=q.slate(con, season, week, season_type, snap))

    @app.get("/api/teams")
    def api_teams():
        with q.warehouse(db_path) as con:
            season = _int("season", q.current_week(con, clock())["season"])
            return jsonify(season=season, teams=q.teams(con, season), weeks=q.weeks(con, season))

    @app.get("/api/matchup")
    def api_matchup():
        started = time.perf_counter()
        a, b = _int("a"), _int("b")
        if a is None or b is None or a == b:
            abort(400, "a and b must be two different team ids")
        full = request.args.get("mode") == "full"
        show_postgame = _flag("postgame", False)
        rollup = request.args.get("rollup") or "pooled"
        if rollup not in ("pooled", "mean", "last3"):
            abort(400, "rollup must be pooled, mean or last3")
        with q.warehouse(db_path) as con:
            cur = q.current_week(con, clock())
            season = _int("season", cur["season"])
            week = _int("week", cur["week"] if season == cur["season"] else 1)
            season_type = "postseason" if request.args.get("season_type") == "postseason" else "regular"
            ta, tb = q.team(con, a, season), q.team(con, b, season)
            if ta is None or tb is None:
                abort(404, "unknown team id")
            window, cutoff = q.asof(con, season, week, season_type, full=full)
            snap = lines(con)
            game_id = _int("game_id") or q.find_game(con, season, a, b, cutoff)
            sections = {
                "game": q.game_card(con, game_id, snap, full=full) if game_id else None,
                "profile": {"a": q.profile(con, a, season, window, cutoff, full=full),
                            "b": q.profile(con, b, season, window, cutoff, full=full),
                            "rows": q.profile_rows(con, season, a, b)},
                "ratings": q.ratings(con, season, cutoff, a, b, full=full, show_postgame=show_postgame),
                "units": q.units(con, season, window, a, b, full=full, rollup=rollup,
                                 fcs=_flag("fcs", True), ngt=_flag("ngt", True)),
            }
            season_weeks = q.weeks(con, season)
        elapsed = round((time.perf_counter() - started) * 1000)
        log.info("matchup a=%s b=%s season=%s week=%s full=%s: %s ms", a, b, season, week, full, elapsed)
        return jsonify(
            meta={"season": season, "week": week, "season_type": season_type, "weeks": season_weeks,
                  "cutoff": q._plain(cutoff), "mode": "full" if full else "asof",
                  "show_postgame": show_postgame, "a": ta, "b": tb, "game_id": game_id,
                  "snapshot": {"file": snap["file"], "pulled_at": snap["pulled_at"]},
                  "elapsed_ms": elapsed},
            sections=sections,
            model_signals=None,  # reserved for a later read-only model panel
        )

    return app
