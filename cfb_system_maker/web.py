from __future__ import annotations

import json
import logging
import math
import time as _time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from cfb_system_maker.backtest import (
    _side_spread,
    grade_bet,
    matches_system,
    run_backtest,
    run_backtest_summary,
    sign_consistency,
    split_holdout,
)
from cfb_system_maker.describe import describe, group_is_renderable
from cfb_system_maker.enrich import (
    load_features,
    load_features_from,
    load_features_meta,
    upcoming_features_path,
)
from cfb_system_maker.features import (
    FEATURE_BY_KEY,
    FEATURE_REGISTRY,
    FeatureDef,
    effective_perspective,
    registry_version,
    resolve_feature_value,
)
from cfb_system_maker.models import BacktestResult, BetDetail, FeatureFilter, GameRecord, SavedSystem, SystemFilter
from cfb_system_maker.narration import NarrationError, narrate_run
from cfb_system_maker.storage import (
    EXAMPLES_DIR,
    list_examples,
    list_systems,
    load_example_system,
    load_processed_games,
    load_saved_system,
    load_search_run,
    load_system,
    load_upcoming_games,
    load_upcoming_meta,
    save_system,
)

_REMOVE_PARAM_MAP: dict[str, tuple[str, ...]] = {
    "favorite": ("favorite",),
    "underdog": ("underdog",),
    "home": ("home",),
    "away": ("away",),
    "spread_range": ("min_spread", "max_spread"),
    "total_range": ("min_total", "max_total"),
    "seasons": ("filter_seasons",),
    "weeks": ("filter_weeks",),
    "teams": ("filter_teams",),
    "conferences": ("filter_conferences",),
    "providers": ("filter_providers",),
}

_ALLOWED_PERSPECTIVES = frozenset({"single", "home", "away", "bet_side", "opponent", "either"})

_NARRATE_COOLDOWN_S = 30.0
_NARRATE_LAST: dict[str, float] = {"t": 0.0}
_ALLOWED_OPS = frozenset({"eq", "in", "gte", "lte"})
_MAX_IN_LIST = 256
_CHART_POINTS_CAP = 60
_CORE_CANDIDATE_CLEAR: dict[str, dict[str, object]] = {
    "core:season": {"seasons": frozenset()},
    "core:week": {"weeks": frozenset()},
    "core:team": {"teams": frozenset()},
    "core:conference": {"conferences": frozenset()},
    "core:provider": {"providers": frozenset()},
    "core:spread_range": {"min_spread": None, "max_spread": None},
    "core:total_range": {"min_total": None, "max_total": None},
}

CORE_FILTER_META: dict[str, dict[str, str]] = {
    "core:season": {
        "label": "Season",
        "control": "categorical",
        "description": (
            "Restrict bets to one or more seasons (calendar year of the CFB season). "
            "Leave empty for all seasons in the dataset."
        ),
        "param": "filter_seasons",
    },
    "core:week": {
        "label": "Week",
        "control": "categorical",
        "description": "Restrict bets to specific weeks within a season. Leave empty for all weeks.",
        "param": "filter_weeks",
    },
    "core:team": {
        "label": "Team",
        "control": "categorical",
        "description": (
            "Restrict bets to games with the selected team on the bet side. "
            "Over/under systems have no bet side, so there the filter matches games "
            "involving the team on either side."
        ),
        "param": "filter_teams",
    },
    "core:conference": {
        "label": "Conference",
        "control": "categorical",
        "description": (
            "Restrict bets to the selected conference on the bet side. "
            "Over/under systems have no bet side, so there the filter matches games "
            "involving the conference on either side."
        ),
        "param": "filter_conferences",
    },
    "core:provider": {
        "label": "Provider",
        "control": "categorical",
        "description": "Restrict bets to lines from the selected odds provider.",
        "param": "filter_providers",
    },
    "core:spread_range": {
        "label": "Spread Range",
        "control": "numeric",
        "description": (
            "Restrict bets to a spread range (min/max) on the side you're betting. "
            "Negative means that side is favored. For an away bet this is the home "
            "spread negated, not the raw home-spread number."
        ),
        "param": "min_spread,max_spread",
    },
    "core:total_range": {
        "label": "Total Range",
        "control": "numeric",
        "description": "Restrict bets to an over/under total range (min/max points).",
        "param": "min_total,max_total",
    },
}


logger = logging.getLogger(__name__)


class StrictParseError(Exception):
    def __init__(self, error: str, message: str):
        super().__init__(message)
        self.error = error
        self.message = message


def filter_descriptor(candidate_id: str) -> dict[str, object] | None:
    if candidate_id.startswith("core:"):
        meta = CORE_FILTER_META.get(candidate_id)
        if meta is None:
            return None
        return {
            "id": candidate_id,
            "key": candidate_id.split(":", 1)[1],
            "team_scoped": False,
            "group": "core",
            "lookahead_warning": False,
            **meta,
        }
    key = candidate_id
    if candidate_id.startswith("feature:"):
        key = candidate_id.split(":", 1)[1]
    feature = FEATURE_BY_KEY.get(key)
    if feature is None:
        return None
    lookahead = feature.group == "result_lookahead"
    return {
        "id": f"feature:{feature.key}",
        "key": feature.key,
        "label": feature.label,
        "control": feature.control,
        "description": feature.description,
        "param": feature.key,
        "group": feature.group,
        "team_scoped": feature.team_scoped,
        "lookahead_warning": "lookahead — analysis only" if lookahead else False,
    }


def remove_candidate_filters(system: SystemFilter, candidate_id: str) -> SystemFilter:
    """Clear every committed representation of the candidate; keep Fade and other filters."""
    if candidate_id in _CORE_CANDIDATE_CLEAR:
        updates = dict(_CORE_CANDIDATE_CLEAR[candidate_id])
        # dataclasses.replace needs mutable sets where the model uses set
        for field, value in list(updates.items()):
            if isinstance(value, frozenset):
                updates[field] = set(value)
        return replace(system, **updates)
    if candidate_id.startswith("feature:"):
        key = candidate_id.split(":", 1)[1]
        remaining = tuple(filt for filt in system.feature_filters if filt.key != key)
        return replace(system, feature_filters=remaining)
    raise StrictParseError("unknown_candidate", f"Unknown candidate_id: {candidate_id}")


def resolve_candidate_value(
    game: GameRecord,
    system: SystemFilter,
    descriptor: dict[str, object],
    perspective: str,
    *,
    feature_map: dict[int, dict] | None = None,
) -> object | tuple[object, ...] | None:
    candidate_id = str(descriptor["id"])
    if candidate_id == "core:season":
        return game.season
    if candidate_id == "core:week":
        return game.week
    if candidate_id == "core:provider":
        return game.provider
    if candidate_id == "core:team":
        if system.bet_type == "total":
            return (game.home_team, game.away_team)
        return game.home_team if system.side.lower() == "home" else game.away_team
    if candidate_id == "core:conference":
        if system.bet_type == "total":
            return (game.home_conference, game.away_conference)
        return game.home_conference if system.side.lower() == "home" else game.away_conference
    if candidate_id == "core:spread_range":
        if game.spread is None:
            return None
        return _side_spread(game.spread, system.side)
    if candidate_id == "core:total_range":
        return game.total
    if candidate_id.startswith("feature:"):
        key = str(descriptor["key"])
        feature = FEATURE_BY_KEY.get(key)
        if feature is None:
            return None
        filt = FeatureFilter(key=key, op="eq", value=True, perspective=perspective)
        return resolve_feature_value(
            (feature_map or {}).get(game.game_id, {}),
            feature,
            filt,
            system,
        )
    return None


def aggregate_filter_value_rows(
    games: list[GameRecord],
    base_system: SystemFilter,
    descriptor: dict[str, object],
    *,
    feature_map: dict[int, dict] | None,
    perspective: str,
    stake: float = 1.0,
    american_odds: int = -110,
    matched_game_ids: set[int] | None = None,
) -> list[dict[str, object]]:
    """One-pass per-value Record/ROI/Money with the candidate already removed from base_system."""
    feature_map = feature_map or {}
    control = str(descriptor.get("control", ""))
    buckets: dict[object, list] = {}

    if control == "bool":
        # Fixed domain Yes/No even before observing values
        buckets[False] = []
        buckets[True] = []

    for game in games:
        if not matches_system(game, base_system, feature_map):
            continue
        raw = resolve_candidate_value(
            game, base_system, descriptor, perspective, feature_map=feature_map
        )
        if raw is None:
            continue
        if matched_game_ids is not None:
            matched_game_ids.add(game.game_id)
        if isinstance(raw, tuple):
            values = []
            for item in raw:
                if item is not None and item not in values:
                    values.append(item)
        else:
            values = [raw]
        detail = grade_bet(game, base_system, stake=stake, american_odds=american_odds)
        for value in values:
            buckets.setdefault(value, []).append(detail)

    rows: list[dict[str, object]] = []
    for value, details in buckets.items():
        wins = sum(1 for bet in details if bet.result == "win")
        losses = sum(1 for bet in details if bet.result == "loss")
        pushes = sum(1 for bet in details if bet.result == "push")
        bets = len(details)
        decided = wins + losses
        profit = round(sum(bet.profit for bet in details), 4)
        risked = bets * stake
        roi = round(profit / risked, 4) if risked else 0.0
        description = _value_description(value, control)
        rows.append(
            {
                "value": value,
                "description": description,
                "wins": wins,
                "losses": losses,
                "pushes": pushes,
                "record": f"{wins}-{losses}-{pushes}",
                "roi": roi,
                "money": profit * 100,
            }
        )

    if control == "bool":
        order = {"No": 0, "Yes": 1}
        rows.sort(key=lambda row: order.get(str(row["description"]), 99))
    elif control == "numeric":
        rows.sort(key=lambda row: float(row["value"]))  # type: ignore[arg-type]
    else:
        rows.sort(key=lambda row: _categorical_sort_key(row["value"]))
    return rows


def _categorical_sort_key(value: object) -> tuple:
    try:
        return (0, float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return (1, str(value))


def _value_description(value: object, control: str) -> str:
    if control == "bool":
        return "Yes" if value is True else "No"
    return str(value)


def downsample_chart_points(
    rows: list[dict[str, object]],
    *,
    cap: int = _CHART_POINTS_CAP,
) -> list[dict[str, object]]:
    """Deterministic visual downsample of exact numeric rows (D-09). Domain bounds stay on rows.

    Scatter of value (x) vs ROI (y) so a value-ROI correlation is visible at a glance.
    """
    if not rows:
        return []
    items = [
        (float(row["value"]), float(row["roi"]), float(row["money"]))  # type: ignore[arg-type]
        for row in rows
    ]
    if len(items) > cap:
        step = max(1, len(items) // cap)
        items = items[::step]
        if len(items) > cap:
            items = items[:cap]
        # Always keep the last observed extreme when stride skips it
        last = (
            float(rows[-1]["value"]),  # type: ignore[arg-type]
            float(rows[-1]["roi"]),  # type: ignore[arg-type]
            float(rows[-1]["money"]),  # type: ignore[arg-type]
        )
        if items[-1][0] != last[0]:
            if len(items) >= cap:
                items[-1] = last
            else:
                items.append(last)

    width = 520
    height = 150
    pad_x = 28
    pad_y = 18
    values = [value for value, _, _ in items]
    min_value = min(values)
    max_value = max(values)
    value_span = max_value - min_value or 1.0
    rois = [roi for _, roi, _ in items] + [0.0]
    min_roi = min(rois)
    max_roi = max(rois)
    roi_span = max_roi - min_roi or 1.0

    points: list[dict[str, object]] = []
    for value, roi, money in items:
        x = pad_x + (width - pad_x * 2) * (value - min_value) / value_span
        y = height - pad_y - ((roi - min_roi) / roi_span) * (height - pad_y * 2)
        points.append(
            {
                "value": value,
                "roi": roi,
                "money": money,
                "x": round(x, 2),
                "y": round(y, 2),
            }
        )
    return points


def serialize_numeric_draft(
    candidate_id: str,
    minimum: float,
    maximum: float,
    *,
    perspective: str = "single",
) -> dict[str, object]:
    """Canonical form updates for a validated numeric Save draft (D-06 / D-07)."""
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        raise StrictParseError("invalid_bounds", "Bounds must be finite numbers.")
    if minimum > maximum:
        raise StrictParseError("reversed_bounds", "Max must be greater than or equal to min.")

    if candidate_id == "core:spread_range":
        return {"min_spread": float(minimum), "max_spread": float(maximum)}
    if candidate_id == "core:total_range":
        return {"min_total": float(minimum), "max_total": float(maximum)}
    if candidate_id.startswith("feature:"):
        key = candidate_id.split(":", 1)[1]
        if key not in FEATURE_BY_KEY:
            raise StrictParseError("unknown_candidate", f"Unknown candidate_id: {candidate_id}")
        if FEATURE_BY_KEY[key].control != "numeric":
            raise StrictParseError("invalid_candidate", f"Candidate is not numeric: {candidate_id}")
        return {
            "feature_filters": [
                {"key": key, "op": "gte", "value": float(minimum), "perspective": perspective},
                {"key": key, "op": "lte", "value": float(maximum), "perspective": perspective},
            ]
        }
    raise StrictParseError("unknown_candidate", f"Unknown candidate_id: {candidate_id}")


def parse_system_strict(args: MultiDict | None = None) -> SystemFilter:
    """Allowlist-parse query args for JSON APIs; raise StrictParseError on bad input."""
    source = args if args is not None else request.args
    _validate_feature_filters_strict(source)
    _validate_numeric_fields_strict(source)
    _validate_int_list_fields_strict(source)
    form = _form_values_from_args(source)
    return _system_from_form(form)


def create_app(data_dir: str | Path = "data") -> Flask:
    app = Flask(__name__)
    app.config["DATA_DIR"] = Path(data_dir)
    app.jinja_env.globals["query_href"] = _query_href

    @app.before_request
    def _reject_cross_origin_posts():
        if request.method != "POST":
            return None
        origin = request.headers.get("Origin")
        if not origin:
            return None
        if urlparse(origin).netloc != request.host:
            abort(403)
        return None

    @app.before_request
    def _start_timer():
        g.request_start = _time.perf_counter()

    @app.after_request
    def _access_log(response):
        start = g.get("request_start")
        elapsed_ms = (_time.perf_counter() - start) * 1000 if start is not None else 0.0
        logger.info("%s %s %s %.0fms", request.method, request.full_path.rstrip("?"), response.status_code, elapsed_ms)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/")
    def dashboard():
        if _wants_editor(request.args):
            query = request.query_string.decode()
            return redirect(f"/system?{query}" if query else "/system")

        tab = "examples" if request.args.get("tab") == "examples" else "mine"
        try:
            games, feature_map = _load_data_cached(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "dashboard.html",
                error="missing_data",
                tab=tab,
                timeframe="all",
                seasons=[],
                systems=[],
            )

        seasons = sorted({game.season for game in games}, reverse=True)
        timeframe = _normalize_timeframe(request.args.get("timeframe", ""), seasons)

        saved_systems = _saved_systems_newest_first(app.config["DATA_DIR"])
        if tab == "examples":
            systems = _example_rows(games, feature_map, timeframe, app.config["DATA_DIR"])
        else:
            systems = [
                _dashboard_row(saved, games, feature_map, timeframe, app.config["DATA_DIR"])
                for saved in saved_systems
            ]
        panel = _current_matches_panel(saved_systems, app.config["DATA_DIR"])
        return render_template(
            "dashboard.html",
            error=None,
            tab=tab,
            timeframe=timeframe,
            seasons=seasons,
            systems=systems,
            panel=panel,
        )

    @app.post("/copy-example")
    def copy_example():
        """Copy a read-only bundled example into the user's data directory (D-14).

        The bundled file is only ever read; the write lands in DATA_DIR/systems
        and is name-gated on both the read and the write side (T-05-18).
        """
        name = str(request.form.get("name", "")).strip()
        try:
            example = load_example_system(name, EXAMPLES_DIR)
            save_system(name, example.system, app.config["DATA_DIR"], theory=example.theory)
        except (ValueError, OSError, json.JSONDecodeError):
            logger.exception("copy_example failed for %r", name)
            return redirect("/?tab=examples&copy_error=1")
        return redirect("/?tab=examples")

    @app.get("/system")
    def index():
        try:
            games, feature_map = _load_data_cached(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "index.html",
                error="missing_data",
                form=_empty_form(),
                options=_empty_options(),
                feature_options=[],
                features_enabled=False,
                saved_systems=[],
                load_error=None,
                parse_warning=False,
                loaded_system="",
                stale_registry=False,
                core_filters=CORE_FILTER_META,
            )

        meta = load_features_meta(app.config["DATA_DIR"]) if feature_map is not None else None
        stale_registry = bool(meta and meta.get("registry_version") != registry_version())
        loaded_name = request.args.get("load_system", "")
        load_error = None
        parse_warning = False
        if loaded_name:
            try:
                saved = load_saved_system(loaded_name, app.config["DATA_DIR"])
                system = saved.system
                form = _form_from_system(system, loaded_name, saved.theory)
            except (FileNotFoundError, ValueError):
                load_error = f"System '{loaded_name}' not found."
                form = _form_values()
                system = _system_from_form(form)
                loaded_name = ""
        else:
            parse_warning = _has_unparseable_input(request.args)
            form = _form_values()
            system = _system_from_form(form)

        result = _cached_backtest(system, games, feature_map, app.config["DATA_DIR"])
        coverage = _feature_coverage(games, system, feature_map)
        tab = "matches" if request.args.get("tab") == "matches" else "graph"
        base_query = _query_args_from_form(form) if loaded_name else MultiDict(request.args.items(multi=True))
        sentences = describe(system)
        for row in sentences:
            row["remove_href"] = _query_href_removing(str(row["key"]), base_query)
            row["edit"] = edit_metadata_for_sentence(system, row)
        return render_template(
            "index.html",
            error=None,
            load_error=load_error,
            parse_warning=parse_warning,
            loaded_system=loaded_name,
            form=form,
            enabled_feature_keys=_enabled_feature_keys(form.get("feature_filters", [])),
            options=_options_from_games(games),
            feature_options=_feature_options_cached(feature_map, app.config["DATA_DIR"]),
            features_enabled=feature_map is not None,
            stale_registry=stale_registry,
            saved_systems=list_systems(app.config["DATA_DIR"]),
            result=result,
            bets=result.bet_details[:250],
            chart=_range_chart(result),
            cumulative_chart=_cumulative_chart(result),
            coverage=coverage,
            season_sign_consistency=sign_consistency(result.season_breakdown),
            tab=tab,
            sentences=sentences,
            core_filters=CORE_FILTER_META,
        )

    @app.post("/save")
    def save():
        form = _form_values_from_post()
        name = str(form.get("save_name", "")).strip()
        args = _query_args_from_form(form)
        if not name:
            args.setlist("save_error", ["missing_name"])
            return redirect("/system?" + urlencode(list(args.items(multi=True))))
        try:
            save_system(name, _system_from_form(form), app.config["DATA_DIR"], theory=form.get("theory", ""))
        except ValueError:
            args.setlist("save_error", ["invalid_name"])
            return redirect("/system?" + urlencode(list(args.items(multi=True))))
        return redirect(url_for("index", **{"load_system": name}))

    @app.get("/compare")
    def compare():
        try:
            games, feature_map = _load_data_cached(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "compare.html",
                error="missing_data",
                rows=[],
                selected=[],
                saved_systems=[],
                saved_system_meta={},
                options=_empty_options(),
                holdout_seasons=set(),
            )

        selected = request.args.getlist("system")
        holdout_seasons = _int_set(",".join(request.args.getlist("holdout_season")))
        available_seasons = {game.season for game in games}
        rows = []
        for name in selected:
            try:
                system = load_system(name, app.config["DATA_DIR"])
            except (FileNotFoundError, ValueError):
                continue
            if holdout_seasons:
                in_sample, holdout = split_holdout(system, holdout_seasons, available_seasons)
                in_result = _cached_backtest(in_sample, games, feature_map, app.config["DATA_DIR"])
                holdout_result = _cached_backtest(holdout, games, feature_map, app.config["DATA_DIR"])
                rows.append({
                    "name": f"{name} (in-sample)",
                    "system": in_sample,
                    "result": in_result,
                    "sign_consistency": sign_consistency(in_result.season_breakdown),
                })
                rows.append({
                    "name": f"{name} (holdout)",
                    "system": holdout,
                    "result": holdout_result,
                    "sign_consistency": sign_consistency(holdout_result.season_breakdown),
                })
            else:
                result = _cached_backtest(system, games, feature_map, app.config["DATA_DIR"])
                rows.append({
                    "name": name,
                    "system": system,
                    "result": result,
                    "sign_consistency": sign_consistency(result.season_breakdown),
                })
        system_names = list_systems(app.config["DATA_DIR"])
        saved_system_meta = {}
        for name in system_names:
            try:
                saved = load_saved_system(name, app.config["DATA_DIR"])
            except (FileNotFoundError, ValueError):
                continue
            saved_system_meta[name] = {
                "source": saved.source,
                "search_candidates_tested": saved.search_candidates_tested,
            }
        return render_template(
            "compare.html",
            error=None,
            rows=rows,
            selected=selected,
            saved_systems=system_names,
            saved_system_meta=saved_system_meta,
            options=_options_from_games(games),
            holdout_seasons=holdout_seasons,
        )

    @app.get("/search-runs/<name>")
    def search_run_view(name: str):
        try:
            run = load_search_run(name, app.config["DATA_DIR"])
        except (ValueError, FileNotFoundError):
            abort(404)

        finalist_rows = []
        for i, finalist in enumerate(run.finalists, start=1):
            sentences = describe(finalist.system)
            filters_text = "; ".join(row["text"] for row in sentences) if sentences else "no filters (all games)"
            finalist_rows.append(
                {
                    "index": i,
                    "filters_text": filters_text,
                    "wins": finalist.wins,
                    "losses": finalist.losses,
                    "pushes": finalist.pushes,
                    "roi": finalist.roi,
                    "raw_p": finalist.raw_p,
                    "corrected_p": finalist.corrected_p,
                    "bh_significant": finalist.bh_significant,
                }
            )

        return render_template(
            "search_run.html",
            run=run,
            name=name,
            finalist_rows=finalist_rows,
        )

    @app.post("/search-runs/<name>/narrate")
    def narrate_search_run(name: str):
        try:
            run = load_search_run(name, app.config["DATA_DIR"])
        except (ValueError, FileNotFoundError):
            abort(404)

        now = _time.monotonic()
        if now - _NARRATE_LAST["t"] < _NARRATE_COOLDOWN_S:
            return jsonify({"error": "rate_limited"}), 429
        _NARRATE_LAST["t"] = now

        try:
            text = narrate_run(run)
        except NarrationError:
            return jsonify({"error": "narration_unavailable"}), 502

        return jsonify({"text": text})

    @app.get("/api/backtest")
    def api_backtest():
        try:
            system = parse_system_strict(request.args)
        except StrictParseError as exc:
            return {"error": exc.error, "message": exc.message}, 400
        try:
            games, feature_map = _load_data_cached(app.config["DATA_DIR"])
        except FileNotFoundError:
            return {"error": "missing_data", "message": "Processed games file not found."}, 503
        return run_backtest_summary(games, system, feature_map=feature_map)

    @app.get("/filter-detail")
    def filter_detail():
        candidate_id = (request.args.get("candidate_id") or "").strip()
        if not candidate_id:
            return {"error": "missing_candidate", "message": "candidate_id is required."}, 400
        descriptor = filter_descriptor(candidate_id)
        if descriptor is None:
            return {"error": "unknown_candidate", "message": f"Unknown candidate_id: {candidate_id}"}, 400
        try:
            system = parse_system_strict(request.args)
        except StrictParseError as exc:
            return {"error": exc.error, "message": exc.message}, 400
        try:
            games, feature_map = _load_data_cached(app.config["DATA_DIR"])
        except FileNotFoundError:
            return {"error": "missing_data", "message": "Processed games file not found."}, 503

        team_scoped = bool(descriptor.get("team_scoped"))
        if team_scoped:
            allowed = _allowed_perspectives_for_system(system)
            perspective = (request.args.get("perspective") or "").strip() or _default_perspective(system)
            if perspective not in allowed:
                return {
                    "error": "invalid_perspective",
                    "message": f"Illegal perspective for candidate: {perspective}",
                }, 400
        else:
            allowed = ["single"]
            perspective = "single"

        base_system = remove_candidate_filters(system, candidate_id)
        matched_game_ids: set[int] = set()
        rows = aggregate_filter_value_rows(
            games,
            base_system,
            descriptor,
            feature_map=feature_map,
            perspective=perspective,
            matched_game_ids=matched_game_ids,
        )
        domain_values = [row["value"] for row in rows]
        is_numeric = descriptor["control"] == "numeric"
        chart_points = downsample_chart_points(rows) if is_numeric else []
        # A game with two distinct values (either-perspective home != away, or
        # a total system's team/conference filter on a cross-{team,conference}
        # game) contributes its outcome to more than one row. Each row is a
        # correct standalone Record/ROI, but a window SUM across rows (Max ROI)
        # would double-count that game -- overlapping_rows tells the client to
        # fall back to a single best bucket instead of a summed window.
        overlapping_rows = perspective == "either" or (
            candidate_id in ("core:team", "core:conference") and system.bet_type == "total"
        )
        return {
            "candidate_id": candidate_id,
            "label": descriptor["label"],
            "control": descriptor["control"],
            "description": descriptor["description"],
            "lookahead_warning": descriptor.get("lookahead_warning", False),
            "team_scoped": team_scoped,
            "perspective": perspective,
            "allowed_perspectives": allowed,
            "overlapping_rows": overlapping_rows,
            "matched_games": len(matched_game_ids),
            "domain": {
                "values": domain_values,
                "min": min(domain_values) if domain_values and is_numeric else None,
                "max": max(domain_values) if domain_values and is_numeric else None,
            },
            "rows": rows,
            "chart_points": chart_points,
        }

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.errorhandler(404)
    def _not_found(err):
        return render_template("error.html", title="Page not found",
                               message="That page does not exist."), 404

    @app.errorhandler(500)
    def _server_error(err):
        logger.exception("unhandled error on %s %s", request.method, request.path)
        return render_template("error.html", title="Something went wrong",
                               message="An internal error occurred. Details are in the server log."), 500

    return app


def default_perspective(system: SystemFilter) -> str:
    """New team-scoped filters: spread → bet_side, total → either (D-14)."""
    return "bet_side" if system.bet_type == "spread" else "either"


# Back-compat alias for call sites that still use the private name.
_default_perspective = default_perspective

_SENTENCE_TO_CANDIDATE: dict[str, str] = {
    "seasons": "core:season",
    "weeks": "core:week",
    "teams": "core:team",
    "conferences": "core:conference",
    "providers": "core:provider",
    "spread_range": "core:spread_range",
    "total_range": "core:total_range",
}


def edit_metadata_for_sentence(
    system: SystemFilter, row: dict[str, object]
) -> dict[str, object] | None:
    """Build Edit-launcher metadata for D-01 modal candidates; None for global toggles."""
    key = str(row.get("key", ""))
    if key in ("favorite", "underdog", "home", "away"):
        return None

    candidate_id: str | None = None
    if key in _SENTENCE_TO_CANDIDATE:
        candidate_id = _SENTENCE_TO_CANDIDATE[key]
    elif key.startswith("ff:"):
        candidate_id = f"feature:{key[len('ff:'):]}"
    if candidate_id is None:
        return None

    descriptor = filter_descriptor(candidate_id)
    if descriptor is None:
        return None

    meta: dict[str, object] = {
        "candidate_id": candidate_id,
        "control": descriptor["control"],
        "description": descriptor["description"],
        "label": descriptor["label"],
        "team_scoped": bool(descriptor.get("team_scoped")),
        "lookahead_warning": descriptor.get("lookahead_warning") or "",
        "param": descriptor.get("param") or "",
    }

    if candidate_id == "core:season":
        meta["values"] = sorted(system.seasons)
    elif candidate_id == "core:week":
        meta["values"] = sorted(system.weeks)
    elif candidate_id == "core:team":
        meta["values"] = sorted(system.teams)
    elif candidate_id == "core:conference":
        meta["values"] = sorted(system.conferences)
    elif candidate_id == "core:provider":
        meta["values"] = sorted(system.providers)
    elif candidate_id == "core:spread_range":
        meta["min"] = system.min_spread
        meta["max"] = system.max_spread
    elif candidate_id == "core:total_range":
        meta["min"] = system.min_total
        meta["max"] = system.max_total
    elif candidate_id.startswith("feature:"):
        feature_key = candidate_id.split(":", 1)[1]
        # Deliberately scoped by key only, not (key, perspective): the sentence
        # this Edit button is attached to (row["key"] == f"ff:{feature_key}")
        # is itself per-key, not per-perspective (describe.py groups by
        # (key, perspective) but emits one sentence per group under the same
        # "ff:{key}" sentence key). So if ANY perspective-group for this key is
        # unrenderable, suppress Edit here too — fail closed rather than open
        # a modal that can't represent every filter the sentence covers.
        filts = [filt for filt in system.feature_filters if filt.key == feature_key]
        if not filts:
            return None
        control = str(descriptor["control"])
        groups: dict[str, list[FeatureFilter]] = {}
        for filt in filts:
            groups.setdefault(filt.perspective, []).append(filt)
        renderable = all(group_is_renderable(group, control) for group in groups.values())
        if not renderable:
            # Same shape describe()'s fallback branch renders — no modal
            # representation exists that can edit every filter without
            # silently dropping one.
            return None
        perspective = filts[0].perspective
        meta["perspective"] = perspective
        if control == "numeric":
            meta["min"] = next((float(filt.value) for filt in filts if filt.op == "gte"), None)
            meta["max"] = next((float(filt.value) for filt in filts if filt.op == "lte"), None)
        elif control == "bool":
            eq = next((filt for filt in filts if filt.op == "eq"), None)
            meta["values"] = [bool(eq.value)] if eq is not None else []
        else:
            values: list[object] = []
            for filt in filts:
                if filt.op == "in" and isinstance(filt.value, (list, tuple)):
                    values.extend(filt.value)
                elif filt.op == "eq":
                    values.append(filt.value)
            meta["values"] = values
    return meta


def _allowed_perspectives_for_system(system: SystemFilter) -> list[str]:
    # Modal primary set is Bet-side / Opponent / Either (D-14 / UI-SPEC).
    # home/away remain valid for committed edits and progressive-enhancement fallbacks.
    # bet_side/opponent resolve via system.side, which only means something for a
    # spread bet; either checks both teams regardless of bet_type, so it's always valid.
    if system.bet_type == "spread":
        return ["bet_side", "opponent", "either", "home", "away"]
    return ["either", "home", "away"]


def _feature_coverage(
    games: list[GameRecord],
    system: SystemFilter,
    feature_map: dict[int, dict] | None,
) -> list[dict[str, object]]:
    if not system.feature_filters or feature_map is None:
        return []
    core = replace(system, feature_filters=())
    matched = [game for game in games if matches_system(game, core, feature_map)]
    if not matched:
        return []
    output: list[dict[str, object]] = []
    for filt in system.feature_filters:
        feature = FEATURE_BY_KEY.get(filt.key)
        if feature is None:
            continue
        non_null = 0
        for game in matched:
            value = resolve_feature_value(feature_map.get(game.game_id, {}), feature, filt, core)
            if filt.perspective == "either" and isinstance(value, tuple):
                value = value[0] if value[0] is not None else value[1]
            if value is not None:
                non_null += 1
        output.append({"key": filt.key, "label": feature.label, "pct": round(100 * non_null / len(matched), 1)})
    return output


def _query_href(**overrides: str) -> str:
    copy = MultiDict(request.args.items(multi=True))
    for key, value in overrides.items():
        copy.setlist(key, [value])
    return "?" + urlencode(list(copy.items(multi=True)))


def _query_args_from_form(form: dict[str, object]) -> MultiDict:
    args: list[tuple[str, str]] = [
        ("bet_type", str(form.get("bet_type", "spread"))),
        ("side", str(form.get("side", "home"))),
        ("total_side", str(form.get("total_side", "over"))),
    ]
    for key in ("favorite", "underdog", "home", "away", "fade"):
        if form.get(key):
            args.append((key, "on"))
    for form_key, query_key in (
        ("season", "filter_seasons"),
        ("week", "filter_weeks"),
        ("team", "filter_teams"),
        ("conference", "filter_conferences"),
        ("provider", "filter_providers"),
    ):
        value = str(form.get(form_key, "")).strip()
        if value:
            args.append((query_key, value))
    for key in ("min_spread", "max_spread", "min_total", "max_total"):
        value = str(form.get(key, "")).strip()
        if value:
            args.append((key, value))
    save_name = str(form.get("save_name", "")).strip()
    if save_name:
        args.append(("save_name", save_name))
    for row in form.get("feature_filters", []):
        key = str(row.get("key", ""))
        if not key:
            continue
        value = row.get("value")
        if isinstance(value, list):
            value_text = ",".join(str(item) for item in value)
        elif isinstance(value, bool):
            value_text = "true" if value else "false"
        else:
            value_text = str(value)
        args.append(("ff_enable", key))
        args.append(("ff_key", key))
        args.append(("ff_op", str(row.get("op", "eq"))))
        args.append(("ff_value", value_text))
        args.append(("ff_perspective", str(row.get("perspective", "single"))))
    theory = form.get("theory")
    if theory:
        args.append(("theory", str(theory)))
    return MultiDict(args)


def _query_href_removing(key: str, base: MultiDict) -> str:
    copy = MultiDict(base.items(multi=True))
    if request.args.get("tab") == "matches":
        copy.setlist("tab", ["matches"])
    if key.startswith("ff:"):
        feature_key = key[len("ff:"):]
        keys = copy.getlist("ff_key")
        ops = copy.getlist("ff_op")
        values = copy.getlist("ff_value")
        perspectives = copy.getlist("ff_perspective")
        keep = [index for index, item in enumerate(keys) if item != feature_key]
        copy.setlist("ff_key", [keys[index] for index in keep])
        copy.setlist("ff_op", [ops[index] for index in keep if index < len(ops)])
        copy.setlist("ff_value", [values[index] for index in keep if index < len(values)])
        copy.setlist("ff_perspective", [perspectives[index] for index in keep if index < len(perspectives)])
        copy.setlist("ff_enable", [value for value in copy.getlist("ff_enable") if value != feature_key])
    else:
        for param in _REMOVE_PARAM_MAP.get(key, ()):
            copy.poplist(param)
    copy.poplist("load_system")
    return "?" + urlencode(list(copy.items(multi=True)))


def _try_load_features(data_dir: Path) -> dict[int, dict] | None:
    try:
        return load_features(data_dir)
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _empty_form() -> dict[str, object]:
    return {
        "side": "home",
        "bet_type": "spread",
        "total_side": "over",
        "favorite": False,
        "underdog": False,
        "home": False,
        "away": False,
        "fade": False,
        "season": "",
        "week": "",
        "team": "",
        "conference": "",
        "provider": "",
        "min_spread": "",
        "max_spread": "",
        "min_total": "",
        "max_total": "",
        "save_name": "",
        "feature_filters": [],
    }


def _valid_choice(value: str, allowed: tuple[str, ...], default: str) -> str:
    return value if value in allowed else default


def _has_unparseable_input(args: MultiDict) -> bool:
    """True if any raw query value would be silently dropped by the lenient
    HTML-path parsers (_optional_float / _int_set), e.g. a typo'd min_spread.

    The /system page never 400s on bad input (it must stay usable without
    JS/strict validation), so this only powers a visible "some values were
    ignored" notice -- it never blocks parsing. This intentionally duplicates
    the shape of _validate_int_list_fields_strict's per-part int() parsing
    (different failure mode: warn here, 400 there for /api/backtest) -- do not
    unify them into one function, or /system would start 400ing on bad input.
    """
    for field in ("min_spread", "max_spread", "min_total", "max_total"):
        raw = str(args.get(field, "")).strip()
        if raw and _optional_float(raw) is None:
            return True
    for field, legacy in (("filter_seasons", "season"), ("filter_weeks", "week")):
        raw = str(args.get(field, args.get(legacy, ""))).strip()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                int(part)
            except ValueError:
                return True
    return False


def _form_values() -> dict[str, object]:
    return _form_values_from_args(request.args)


def _form_values_from_args(args: MultiDict) -> dict[str, object]:
    filters = _feature_filters_from_values(args)
    return {
        "side": _valid_choice(args.get("side", "home"), ("home", "away"), "home"),
        "bet_type": _valid_choice(args.get("bet_type", "spread"), ("spread", "total"), "spread"),
        "total_side": _valid_choice(args.get("total_side", "over"), ("over", "under"), "over"),
        "favorite": args.get("favorite") == "on",
        "underdog": args.get("underdog") == "on",
        "home": args.get("home") == "on",
        "away": args.get("away") == "on",
        "fade": args.get("fade") == "on",
        "season": args.get("filter_seasons", args.get("season", "")),
        "week": args.get("filter_weeks", args.get("week", "")),
        "team": args.get("filter_teams", args.get("team", "")),
        "conference": args.get("filter_conferences", args.get("conference", "")),
        "provider": args.get("filter_providers", args.get("provider", "")),
        "min_spread": args.get("min_spread", ""),
        "max_spread": args.get("max_spread", ""),
        "min_total": args.get("min_total", ""),
        "max_total": args.get("max_total", ""),
        "save_name": args.get("save_name", ""),
        "theory": args.get("theory", ""),
        "feature_filters": filters,
    }


def _validate_feature_filters_strict(values: MultiDict) -> None:
    enabled = set(values.getlist("ff_enable"))
    keys = values.getlist("ff_key")
    ops = values.getlist("ff_op")
    raw_values = values.getlist("ff_value")
    perspectives = values.getlist("ff_perspective")
    bet_type = values.get("bet_type", "spread")
    for index, key in enumerate(keys):
        if not key or key not in enabled:
            continue
        if key not in FEATURE_BY_KEY:
            raise StrictParseError("unknown_feature", f"Unknown feature key: {key}")
        if ":" in key:
            raise StrictParseError("invalid_feature", f"Illegal feature key: {key}")
        op = ops[index] if index < len(ops) else "eq"
        if op not in _ALLOWED_OPS:
            raise StrictParseError("invalid_op", f"Unsupported operator: {op}")
        perspective = perspectives[index] if index < len(perspectives) else "single"
        if perspective not in _ALLOWED_PERSPECTIVES:
            raise StrictParseError("invalid_perspective", f"Illegal perspective: {perspective}")
        if bet_type == "total" and perspective in {"bet_side", "opponent"}:
            # Same rule /filter-detail enforces (a1e6e19): a total bet has no
            # team side for these perspectives to resolve against.
            raise StrictParseError(
                "invalid_perspective",
                f"Perspective {perspective} is not valid for total systems",
            )
        raw_value = raw_values[index] if index < len(raw_values) else ""
        if op in {"gte", "lte"}:
            _parse_finite_float(raw_value, field=f"ff_value[{key}]")
        if op == "in":
            parts = [part.strip() for part in str(raw_value).split(",") if part.strip()]
            if len(parts) > _MAX_IN_LIST:
                raise StrictParseError(
                    "list_too_large",
                    f"In-list for {key} exceeds {_MAX_IN_LIST} values",
                )


def _validate_numeric_fields_strict(values: MultiDict) -> None:
    for field in ("min_spread", "max_spread", "min_total", "max_total"):
        raw = values.get(field, "")
        if raw and str(raw).strip():
            _parse_finite_float(str(raw), field=field)


def _validate_int_list_fields_strict(values: MultiDict) -> None:
    for field, legacy in (("filter_seasons", "season"), ("filter_weeks", "week")):
        raw = values.get(field, values.get(legacy, ""))
        if not raw or not str(raw).strip():
            continue
        parts = [part.strip() for part in str(raw).split(",") if part.strip()]
        if len(parts) > _MAX_IN_LIST:
            raise StrictParseError("list_too_large", f"{field} exceeds {_MAX_IN_LIST} values")
        for part in parts:
            try:
                int(part)
            except ValueError as exc:
                raise StrictParseError("invalid_integer", f"Invalid integer in {field}: {part}") from exc
    for field, legacy in (
        ("filter_teams", "team"),
        ("filter_conferences", "conference"),
        ("filter_providers", "provider"),
    ):
        raw = values.get(field, values.get(legacy, ""))
        if not raw or not str(raw).strip():
            continue
        parts = [part.strip() for part in str(raw).split(",") if part.strip()]
        if len(parts) > _MAX_IN_LIST:
            raise StrictParseError("list_too_large", f"{field} exceeds {_MAX_IN_LIST} values")


def _parse_finite_float(raw_value: str, *, field: str) -> float:
    try:
        number = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise StrictParseError("invalid_number", f"Invalid number for {field}") from exc
    if not math.isfinite(number):
        raise StrictParseError("invalid_number", f"Non-finite number for {field}")
    return number


def _form_values_from_post() -> dict[str, object]:
    return _form_values_from_args(request.form)


def _enabled_feature_keys(feature_filters: list[dict[str, object]]) -> set[str]:
    return {str(row["key"]) for row in feature_filters if row.get("key")}


def _form_from_system(system: SystemFilter, loaded_name: str, theory: str = "") -> dict[str, object]:
    return {
        "side": system.side,
        "bet_type": system.bet_type,
        "total_side": system.total_side,
        "favorite": system.favorite,
        "underdog": system.underdog,
        "home": system.home,
        "away": system.away,
        "fade": system.fade,
        "season": ",".join(str(s) for s in sorted(system.seasons)),
        "week": ",".join(str(w) for w in sorted(system.weeks)),
        "team": ",".join(sorted(system.teams)),
        "conference": ",".join(sorted(system.conferences)),
        "provider": ",".join(sorted(system.providers)),
        "min_spread": system.min_spread if system.min_spread is not None else "",
        "max_spread": system.max_spread if system.max_spread is not None else "",
        "min_total": system.min_total if system.min_total is not None else "",
        "max_total": system.max_total if system.max_total is not None else "",
        "save_name": loaded_name,
        "theory": theory,
        "feature_filters": [
            {
                "key": filt.key,
                "op": filt.op,
                "value": filt.value,
                "perspective": filt.perspective,
            }
            for filt in system.feature_filters
        ],
    }


def _feature_filters_from_values(values: MultiDict) -> list[dict[str, object]]:
    enabled = set(values.getlist("ff_enable"))
    keys = values.getlist("ff_key")
    ops = values.getlist("ff_op")
    raw_values = values.getlist("ff_value")
    perspectives = values.getlist("ff_perspective")
    filters: list[dict[str, object]] = []
    for index, key in enumerate(keys):
        if not key or key not in enabled:
            continue
        op = ops[index] if index < len(ops) else "eq"
        raw_value = raw_values[index] if index < len(raw_values) else ""
        perspective = perspectives[index] if index < len(perspectives) else "single"
        parsed = _parse_filter_value(op, raw_value)
        if parsed is None:
            continue
        filters.append(
            {
                "key": key,
                "op": op,
                "value": parsed,
                "perspective": perspective,
            }
        )
    return filters


def _parse_filter_value(op: str, raw_value: str) -> object | None:
    if op == "in":
        parts = [part.strip() for part in raw_value.split(",") if part.strip()]
        return parts if parts else None
    if op == "eq":
        if raw_value in {"true", "false"}:
            return raw_value == "true"
        return raw_value if raw_value.strip() else None
    if op in {"gte", "lte"}:
        if not raw_value.strip():
            return None
        try:
            number = float(raw_value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return raw_value if str(raw_value).strip() else None


def _system_from_form(form: dict[str, object]) -> SystemFilter:
    bet_type = str(form["bet_type"])
    feature_filters = tuple(
        FeatureFilter(
            key=str(row["key"]),
            op=str(row["op"]),
            value=row["value"],
            perspective=effective_perspective(bet_type, str(row.get("perspective", "single"))),
        )
        for row in form.get("feature_filters", [])
        if row.get("key")
    )
    return SystemFilter(
        bet_type=str(form["bet_type"]),
        side=str(form["side"]),
        total_side=str(form["total_side"]),
        seasons=_int_set(str(form["season"])),
        weeks=_int_set(str(form["week"])),
        teams=_str_set(str(form["team"])),
        conferences=_str_set(str(form["conference"])),
        favorite=bool(form["favorite"]),
        underdog=bool(form["underdog"]),
        home=bool(form["home"]),
        away=bool(form["away"]),
        fade=bool(form["fade"]),
        providers=_str_set(str(form["provider"])),
        min_spread=_optional_float(str(form["min_spread"])),
        max_spread=_optional_float(str(form["max_spread"])),
        min_total=_optional_float(str(form["min_total"])),
        max_total=_optional_float(str(form["max_total"])),
        feature_filters=feature_filters,
    )


def _int_set(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result


def _str_set(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def _optional_float(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _options_from_games(games: list[GameRecord]) -> dict[str, list[str | int]]:
    seasons = sorted({game.season for game in games})
    weeks = sorted({game.week for game in games})
    teams = sorted({game.home_team for game in games} | {game.away_team for game in games})
    conferences = sorted(
        {game.home_conference for game in games if game.home_conference}
        | {game.away_conference for game in games if game.away_conference}
    )
    providers = sorted({game.provider for game in games if game.provider})
    return {"seasons": seasons, "weeks": weeks, "teams": teams, "conferences": conferences, "providers": providers}


def _empty_options() -> dict[str, list[str | int]]:
    return {"seasons": [], "weeks": [], "teams": [], "conferences": [], "providers": []}


def _feature_options(feature_map: dict[int, dict] | None) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for feature in FEATURE_REGISTRY:
        grouped.setdefault(feature.group, []).append(_feature_option(feature, feature_map))
    output: list[dict[str, object]] = []
    for group in (
        "matchup",
        "ratings",
        "betting_lines",
        "weather",
        "season_to_date",
        "team_preseason",
        "metadata",
        "result_lookahead",
    ):
        if group in grouped:
            output.append({"group": group, "features": grouped[group]})
    return output


def _feature_option(feature: FeatureDef, feature_map: dict[int, dict] | None) -> dict[str, object]:
    values = _scan_values(feature, feature_map or {})
    lookahead = feature.group == "result_lookahead"
    return {
        "key": feature.key,
        "candidate_id": f"feature:{feature.key}",
        "label": feature.label,
        "control": feature.control,
        "team_scoped": feature.team_scoped,
        "description": feature.description,
        "lookahead_warning": "lookahead — analysis only" if lookahead else "",
        "values": values,
        "min_value": min(values) if values and feature.control == "numeric" else None,
        "max_value": max(values) if values and feature.control == "numeric" else None,
    }


def _scan_values(feature: FeatureDef, feature_map: dict[int, dict]) -> list[object]:
    seen: set[object] = set()
    for row in feature_map.values():
        if feature.team_scoped:
            keys = (f"home_{feature.key}", f"away_{feature.key}")
        else:
            keys = (feature.key,)
        for key in keys:
            value = row.get(key)
            if value is not None:
                seen.add(value)
    if feature.control == "bool":
        return [True, False]
    if feature.control == "numeric":
        return sorted(seen, key=lambda item: float(item))  # type: ignore[arg-type]
    return sorted(seen, key=lambda item: str(item))


def _range_chart(result: BacktestResult) -> dict[str, object]:
    if not result.bet_details:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}

    buckets: dict[float, float] = {}
    for bet in result.bet_details:
        line = round(bet.line * 2) / 2
        buckets[line] = round(buckets.get(line, 0.0) + bet.profit, 4)

    items = sorted(buckets.items())
    if len(items) > 18:
        step = max(1, len(items) // 18)
        sampled = items[::step]
        if sampled[-1] != items[-1]:
            sampled.append(items[-1])
        items = sampled

    width = 520
    height = 150
    pad_x = 28
    pad_y = 18
    values = [profit for _, profit in items] + [0]
    min_profit = min(values)
    max_profit = max(values)
    span = max_profit - min_profit or 1

    points = []
    for index, (line, profit) in enumerate(items):
        x = pad_x if len(items) == 1 else pad_x + (width - pad_x * 2) * index / (len(items) - 1)
        y = height - pad_y - ((profit - min_profit) / span) * (height - pad_y * 2)
        points.append({"x": round(x, 2), "y": round(y, 2), "line": line, "profit": profit})

    zero_y = height - pad_y - ((0 - min_profit) / span) * (height - pad_y * 2)
    return {
        "points": points,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
        "zero_y": round(zero_y, 2),
        "min_x": items[0][0],
        "max_x": items[-1][0],
    }


def _cumulative_chart(result: BacktestResult) -> dict[str, object]:
    if not result.bet_details:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}

    ordered = sorted(result.bet_details, key=lambda bet: (bet.season, bet.week, bet.game_id))

    width = 520
    height = 150
    pad_x = 28
    pad_y = 18

    running = 0.0
    running_values = []
    for bet in ordered:
        running = round(running + bet.profit, 4)
        running_values.append(running)

    values = running_values + [0]
    min_profit = min(values)
    max_profit = max(values)
    span = max_profit - min_profit or 1

    points = []
    for index, profit in enumerate(running_values):
        x = pad_x if len(ordered) == 1 else pad_x + (width - pad_x * 2) * index / (len(ordered) - 1)
        y = height - pad_y - ((profit - min_profit) / span) * (height - pad_y * 2)
        points.append({"x": round(x, 2), "y": round(y, 2), "order": index, "profit": profit})

    zero_y = height - pad_y - ((0 - min_profit) / span) * (height - pad_y * 2)
    return {
        "points": points,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
        "zero_y": round(zero_y, 2),
        "min_x": 0,
        "max_x": len(ordered) - 1,
    }


# --- Dashboard support --------------------------------------------------------

_EDITOR_PARAMS = frozenset({
    "side", "bet_type", "total_side",
    "favorite", "underdog", "home", "away", "fade",
    "min_spread", "max_spread", "min_total", "max_total",
    "filter_seasons", "filter_weeks", "filter_teams",
    "filter_conferences", "filter_providers",
    "season", "week", "team", "conference", "provider",
    "save_name", "theory", "load_system",
})

_FIGURE_CACHE: dict[tuple, BacktestResult] = {}
_DATA_CACHE: dict[tuple, tuple[list[GameRecord], dict[int, dict] | None]] = {}
_FEATURE_OPTIONS_CACHE: dict[tuple, list] = {}


def _load_data_cached(data_dir: Path) -> tuple[list[GameRecord], dict[int, dict] | None]:
    """Games + feature sidecar, memoized on file identity. FileNotFoundError
    still propagates so the missing_data branches keep working."""
    key = _data_fingerprint(data_dir)
    hit = _DATA_CACHE.get(key)
    if hit is None:
        games = load_processed_games(data_dir)
        features = _try_load_features(data_dir)
        _DATA_CACHE.clear()
        _FEATURE_OPTIONS_CACHE.clear()
        _DATA_CACHE[key] = (games, features)
        return games, features
    return hit


def _feature_options_cached(feature_map: dict[int, dict] | None, data_dir: Path) -> list:
    if feature_map is None:
        return []
    key = _data_fingerprint(data_dir)
    hit = _FEATURE_OPTIONS_CACHE.get(key)
    if hit is None:
        hit = _feature_options(feature_map)
        _FEATURE_OPTIONS_CACHE[key] = hit
    return hit


def _wants_editor(args: MultiDict) -> bool:
    """True when a request to / carries editor state and belongs at /system (D-09)."""
    return any(key in _EDITOR_PARAMS or key.startswith("ff_") for key in args.keys())


def _normalize_timeframe(raw: str, seasons: list[int]) -> str:
    """Normalize ?timeframe to the literal 'all' or a season present in the data."""
    if raw and raw != "all":
        try:
            candidate = int(raw)
        except ValueError:
            return "all"
        if candidate in seasons:
            return str(candidate)
    return "all"


def _saved_systems_newest_first(data_dir: Path) -> list[SavedSystem]:
    saved = []
    for name in list_systems(data_dir):
        try:
            saved.append(load_saved_system(name, data_dir))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
    return sorted(saved, key=lambda item: item.saved_at, reverse=True)


def _data_fingerprint(data_dir: Path) -> tuple:
    """Size+mtime of the files the figures derive from, so a rebuild invalidates."""
    parts = []
    for name in ("games.csv", "features.json"):
        path = Path(data_dir) / "processed" / name
        try:
            stat = path.stat()
            parts.append((name, stat.st_size, stat.st_mtime))
        except OSError:
            parts.append((name, None, None))
    return tuple(parts)


def _system_key(system: SystemFilter) -> str:
    """Deterministic identity for a SystemFilter (sets have unstable iteration order)."""
    def normalize(value: object) -> object:
        if isinstance(value, (set, frozenset)):
            return sorted(value, key=str)
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(val) for key, val in value.items()}
        return value

    return json.dumps(normalize(asdict(system)), sort_keys=True, default=str)


def _cached_backtest(
    system: SystemFilter,
    games: list[GameRecord],
    feature_map: dict[int, dict] | None,
    data_dir: Path,
) -> BacktestResult:
    """One all-time run_backtest per system, memoized on system + data identity (D-11)."""
    key = (_system_key(system), _data_fingerprint(data_dir))
    cached = _FIGURE_CACHE.get(key)
    if cached is None:
        stale = [k for k in _FIGURE_CACHE if k[1] != key[1]]
        for k in stale:
            del _FIGURE_CACHE[k]
        cached = run_backtest(games, system, feature_map=feature_map)
        _FIGURE_CACHE[key] = cached
    return cached


def _timeframe_figures(result: BacktestResult, timeframe: str) -> dict[str, object]:
    """Per-season figures derived from the single all-time result, never a second backtest."""
    if timeframe == "all":
        return {
            "bets": result.bets,
            "wins": result.wins,
            "losses": result.losses,
            "pushes": result.pushes,
            "hit_rate": result.hit_rate,
            "profit": result.profit,
            "roi": result.roi,
            "bet_details": result.bet_details,
        }

    season = int(timeframe)
    record = next((row for row in result.season_breakdown if row.season == season), None)
    details = [bet for bet in result.bet_details if bet.season == season]
    if record is None:
        return {
            "bets": 0, "wins": 0, "losses": 0, "pushes": 0,
            "hit_rate": 0.0, "profit": 0.0, "roi": 0.0, "bet_details": [],
        }
    decided = record.wins + record.losses
    return {
        "bets": record.bets,
        "wins": record.wins,
        "losses": record.losses,
        "pushes": record.pushes,
        "hit_rate": round(record.wins / decided, 4) if decided else 0.0,
        "profit": record.profit,
        "roi": record.roi,
        "bet_details": details,
    }


_SPARK_WIDTH = 96
_SPARK_HEIGHT = 24
_SPARK_INSET = 3
_SPARK_MAX_POINTS = 48


def _sparkline(bet_details: list[BetDetail]) -> dict[str, object]:
    """Cumulative-profit shape for one systems-table row.

    Sibling of _cumulative_chart, not a parameterization of it: no axes, no zero
    line, no points, y-scaled to the series' own min/max so a flat run centers.
    """
    if not bet_details:
        return {"empty": True, "polyline": "", "sign_class": "", "label": ""}

    ordered = sorted(bet_details, key=lambda bet: (bet.season, bet.week, bet.game_id))
    running = 0.0
    values = []
    for bet in ordered:
        running = round(running + bet.profit, 4)
        values.append(running)

    final = values[-1]
    sign_class = "positive" if final >= 0 else "negative"
    label = "Cumulative profit trend: {}".format(_money_text(final))

    if len(values) > _SPARK_MAX_POINTS:
        step = (len(values) - 1) / (_SPARK_MAX_POINTS - 1)
        values = [values[min(len(values) - 1, round(index * step))] for index in range(_SPARK_MAX_POINTS)]

    low = min(values)
    high = max(values)
    span = high - low
    usable = _SPARK_HEIGHT - _SPARK_INSET * 2

    def y_for(value: float) -> float:
        if span == 0:
            return _SPARK_HEIGHT / 2
        return _SPARK_HEIGHT - _SPARK_INSET - ((value - low) / span) * usable

    if len(values) == 1:
        coords = [(0.0, _SPARK_HEIGHT / 2), (float(_SPARK_WIDTH), _SPARK_HEIGHT / 2)]
    else:
        coords = [
            (_SPARK_WIDTH * index / (len(values) - 1), y_for(value))
            for index, value in enumerate(values)
        ]

    return {
        "empty": False,
        "polyline": " ".join(f"{round(x, 2)},{round(y, 2)}" for x, y in coords),
        "sign_class": sign_class,
        "label": label,
    }


def _money_text(profit: float) -> str:
    if profit > 0:
        return "+${:,.0f}".format(profit * 100)
    if profit < 0:
        return "-${:,.0f}".format(-profit * 100)
    return "$0"


def _system_type_label(system: SystemFilter) -> str:
    label = "Over/Under" if system.bet_type == "total" else "Spread"
    return f"{label} · Fade" if system.fade else label


def _dashboard_row(
    saved: SavedSystem,
    games: list[GameRecord],
    feature_map: dict[int, dict] | None,
    timeframe: str,
    data_dir: Path,
) -> dict[str, object]:
    result = _cached_backtest(saved.system, games, feature_map, data_dir)
    figures = _timeframe_figures(result, timeframe)
    return {
        "name": saved.name,
        "theory": saved.theory.strip(),
        "theory_line": saved.theory.strip().splitlines()[0] if saved.theory.strip() else "",
        "type_label": _system_type_label(saved.system),
        "figures": figures,
        "sparkline": _sparkline(figures["bet_details"]),
        "source": saved.source,
        "search_candidates_tested": saved.search_candidates_tested,
    }


def _example_rows(
    games: list[GameRecord],
    feature_map: dict[int, dict] | None,
    timeframe: str,
    data_dir: Path,
) -> list[dict[str, object]]:
    """Rows for the Example Systems tab — same backtest path as My Systems (D-11)."""
    rows = []
    for name in list_examples(EXAMPLES_DIR):
        try:
            saved = load_example_system(name, EXAMPLES_DIR)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        row = _dashboard_row(saved, games, feature_map, timeframe, data_dir)
        # The file stem, not the display name, is what the copy action writes.
        row["example_name"] = name
        rows.append(row)
    return rows


# --- Current Matches panel (DASH-03) -----------------------------------------

_KICKOFF_SORT_SENTINEL = datetime.max.replace(tzinfo=timezone.utc)


def _fmt_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _fmt_signed_spread(line: float) -> str:
    return ("-" if line < 0 else "+") + _fmt_number(abs(line))


def _play_text(system: SystemFilter, game: GameRecord) -> str:
    """Play text derived from the SAME normalization grade_bet applies (D-08).

    A fade inverts the graded side, so the displayed play must invert too — the
    declared ``side`` / ``total_side`` alone is not sufficient input.
    """
    if system.bet_type == "total":
        side = system.total_side
        if system.fade:
            side = "under" if side == "over" else "over"
        return f"Play {side.title()} {_fmt_number(game.total)}"

    normalized_side = system.side.lower()
    if system.fade:
        normalized_side = "away" if normalized_side == "home" else "home"
    team = game.home_team if normalized_side == "home" else game.away_team
    line = _side_spread(game.spread, normalized_side)  # spread is always the home spread
    return f"Play {team} {_fmt_signed_spread(line)}"


def _parse_kickoff(raw: object) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_kickoff_local(dt: datetime, *, date_only: bool = False) -> str:
    local = dt.astimezone()
    date_part = f"{local.strftime('%a')} {local.strftime('%b')} {local.day}"
    if date_only:
        return date_part
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{date_part}, {hour}:{local.minute:02d} {meridiem}"


def _kickoff_label(kickoff: dict) -> str:
    dt = _parse_kickoff(kickoff.get("start_date"))
    if dt is None:
        return "TBD"
    # A to-be-determined kickoff has no real clock time — show the date alone
    # rather than fabricating one on a page that tells the user what to bet.
    return _format_kickoff_local(dt, date_only=bool(kickoff.get("start_time_tbd")))


def _try_load_upcoming_features(data_dir: Path) -> dict[int, dict]:
    try:
        return load_features_from(upcoming_features_path(data_dir))
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return {}


def _current_matches_panel(saved_systems: list[SavedSystem], data_dir: Path) -> dict[str, object]:
    """Every saved system's currently matched upcoming games, in one panel (D-12).

    Reads only pre-built local files (D-02). Matching is the single authoritative
    path with the played requirement relaxed (D-18); grading is never called here
    because an upcoming game has no result to grade.
    """
    if not saved_systems:
        return {"state": "no_systems"}

    try:
        games, kickoffs = load_upcoming_games(data_dir)
        meta = load_upcoming_meta(data_dir)
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"state": "missing"}

    feature_map = _try_load_upcoming_features(data_dir)

    rows: list[dict[str, object]] = []
    for record in games:
        kickoff = kickoffs.get(record.game_id, {})
        dt = _parse_kickoff(kickoff.get("start_date"))
        label = _kickoff_label(kickoff)
        matchup = f"{record.away_team} @ {record.home_team}"
        for saved in saved_systems:
            if not matches_system(record, saved.system, feature_map, require_played=False):
                continue
            rows.append(
                {
                    "_sort": (dt or _KICKOFF_SORT_SENTINEL, saved.name.lower()),
                    "kickoff": label,
                    "matchup": matchup,
                    "play": _play_text(saved.system, record),
                    "system_name": saved.name,
                    "type_label": _system_type_label(saved.system),
                    "details": [str(row["text"]) for row in describe(saved.system)],
                }
            )

    rows.sort(key=lambda row: row["_sort"])
    for row in rows:
        del row["_sort"]

    is_fallback = bool(meta.get("is_fallback"))
    fallback_label = ""
    if is_fallback:
        season_type = str(meta.get("season_type") or "").strip()
        week_word = f"{season_type.title()} Week" if season_type and season_type != "regular" else "Week"
        fallback_label = (
            f"Most recent week with data: {week_word} {meta.get('week')}, {meta.get('season')}"
        )

    dt = _parse_kickoff(meta.get("fetched_at"))
    return {
        "state": "populated",
        "fetched_at": _format_kickoff_local(dt) if dt is not None else "",
        "is_fallback": is_fallback,
        "fallback_label": fallback_label,
        "rows": rows,
    }
