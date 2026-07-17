from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from cfb_system_maker.backtest import matches_system, run_backtest, sign_consistency, split_holdout
from cfb_system_maker.enrich import load_features, load_features_meta
from cfb_system_maker.features import (
    FEATURE_BY_KEY,
    FEATURE_REGISTRY,
    FeatureDef,
    registry_version,
    resolve_feature_value,
)
from cfb_system_maker.models import BacktestResult, FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.storage import list_systems, load_processed_games, load_system, save_system


def create_app(data_dir: str | Path = "data") -> Flask:
    app = Flask(__name__)
    app.config["DATA_DIR"] = Path(data_dir)
    app.jinja_env.globals["query_href"] = _query_href

    @app.get("/")
    def index():
        try:
            games = load_processed_games(app.config["DATA_DIR"])
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
                loaded_system="",
                stale_registry=False,
            )

        feature_map = _try_load_features(app.config["DATA_DIR"])
        meta = load_features_meta(app.config["DATA_DIR"]) if feature_map is not None else None
        stale_registry = bool(meta and meta.get("registry_version") != registry_version())
        loaded_name = request.args.get("load_system", "")
        load_error = None
        if loaded_name:
            try:
                system = load_system(loaded_name, app.config["DATA_DIR"])
                form = _form_from_system(system, loaded_name)
            except FileNotFoundError:
                load_error = f"System '{loaded_name}' not found."
                form = _form_values()
                system = _system_from_form(form)
                loaded_name = ""
        else:
            form = _form_values()
            system = _system_from_form(form)

        result = run_backtest(games, system, feature_map=feature_map)
        coverage = _feature_coverage(games, system, feature_map)
        tab = "matches" if request.args.get("tab") == "matches" else "graph"
        return render_template(
            "index.html",
            error=None,
            load_error=load_error,
            loaded_system=loaded_name,
            form=form,
            enabled_feature_keys=_enabled_feature_keys(form.get("feature_filters", [])),
            options=_options_from_games(games),
            feature_options=_feature_options(feature_map),
            features_enabled=feature_map is not None,
            stale_registry=stale_registry,
            saved_systems=list_systems(app.config["DATA_DIR"]),
            result=result,
            result_dict=asdict(result),
            bets=result.bet_details[:250],
            chart=_range_chart(result),
            cumulative_chart=_cumulative_chart(result),
            coverage=coverage,
            season_sign_consistency=sign_consistency(result.season_breakdown),
            tab=tab,
        )

    @app.post("/save")
    def save():
        form = _form_values_from_post()
        name = str(form.get("save_name", "")).strip()
        if not name:
            return redirect(url_for("index"))
        save_system(name, _system_from_form(form), app.config["DATA_DIR"])
        return redirect(url_for("index", **{"load_system": name}))

    @app.get("/compare")
    def compare():
        try:
            games = load_processed_games(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "compare.html",
                error="missing_data",
                rows=[],
                selected=[],
                saved_systems=[],
                options=_empty_options(),
                holdout_seasons=set(),
            )

        feature_map = _try_load_features(app.config["DATA_DIR"])
        selected = request.args.getlist("system")
        holdout_seasons = {int(value) for value in request.args.getlist("holdout_season") if value.strip()}
        available_seasons = {game.season for game in games}
        rows = []
        for name in selected:
            try:
                system = load_system(name, app.config["DATA_DIR"])
            except FileNotFoundError:
                continue
            if holdout_seasons:
                in_sample, holdout = split_holdout(system, holdout_seasons, available_seasons)
                in_result = run_backtest(games, in_sample, feature_map=feature_map)
                holdout_result = run_backtest(games, holdout, feature_map=feature_map)
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
                result = run_backtest(games, system, feature_map=feature_map)
                rows.append({
                    "name": name,
                    "system": system,
                    "result": result,
                    "sign_consistency": sign_consistency(result.season_breakdown),
                })
        return render_template(
            "compare.html",
            error=None,
            rows=rows,
            selected=selected,
            saved_systems=list_systems(app.config["DATA_DIR"]),
            options=_options_from_games(games),
            holdout_seasons=holdout_seasons,
        )

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    return app


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


def _try_load_features(data_dir: Path) -> dict[int, dict] | None:
    try:
        return load_features(data_dir)
    except FileNotFoundError:
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


def _form_values() -> dict[str, object]:
    filters = _feature_filters_from_request()
    return {
        "side": request.args.get("side", "home"),
        "bet_type": request.args.get("bet_type", "spread"),
        "total_side": request.args.get("total_side", "over"),
        "favorite": request.args.get("favorite") == "on",
        "underdog": request.args.get("underdog") == "on",
        "home": request.args.get("home") == "on",
        "away": request.args.get("away") == "on",
        "season": request.args.get("filter_seasons", request.args.get("season", "")),
        "week": request.args.get("filter_weeks", request.args.get("week", "")),
        "team": request.args.get("filter_teams", request.args.get("team", "")),
        "conference": request.args.get("filter_conferences", request.args.get("conference", "")),
        "provider": request.args.get("filter_providers", request.args.get("provider", "")),
        "min_spread": request.args.get("min_spread", ""),
        "max_spread": request.args.get("max_spread", ""),
        "min_total": request.args.get("min_total", ""),
        "max_total": request.args.get("max_total", ""),
        "save_name": "",
        "feature_filters": filters,
    }


def _form_values_from_post() -> dict[str, object]:
    filters = _feature_filters_from_request()
    return {
        "side": request.form.get("side", "home"),
        "bet_type": request.form.get("bet_type", "spread"),
        "total_side": request.form.get("total_side", "over"),
        "favorite": request.form.get("favorite") == "on",
        "underdog": request.form.get("underdog") == "on",
        "home": request.form.get("home") == "on",
        "away": request.form.get("away") == "on",
        "season": request.form.get("filter_seasons", ""),
        "week": request.form.get("filter_weeks", ""),
        "team": request.form.get("filter_teams", ""),
        "conference": request.form.get("filter_conferences", ""),
        "provider": request.form.get("filter_providers", ""),
        "min_spread": request.form.get("min_spread", ""),
        "max_spread": request.form.get("max_spread", ""),
        "min_total": request.form.get("min_total", ""),
        "max_total": request.form.get("max_total", ""),
        "save_name": request.form.get("save_name", ""),
        "feature_filters": filters,
    }


def _enabled_feature_keys(feature_filters: list[dict[str, object]]) -> set[str]:
    return {str(row["key"]) for row in feature_filters if row.get("key")}


def _active_filter(feature_filters: list[dict[str, object]], key: str) -> dict[str, object] | None:
    for row in feature_filters:
        if row.get("key") == key:
            return row
    return None


def _form_from_system(system: SystemFilter, loaded_name: str) -> dict[str, object]:
    return {
        "side": system.side,
        "bet_type": system.bet_type,
        "total_side": system.total_side,
        "favorite": system.favorite,
        "underdog": system.underdog,
        "home": system.home,
        "away": system.away,
        "season": next(iter(system.seasons), "") if len(system.seasons) == 1 else "",
        "week": next(iter(system.weeks), "") if len(system.weeks) == 1 else "",
        "team": next(iter(system.teams), "") if len(system.teams) == 1 else "",
        "conference": next(iter(system.conferences), "") if len(system.conferences) == 1 else "",
        "provider": next(iter(system.providers), "") if len(system.providers) == 1 else "",
        "min_spread": system.min_spread if system.min_spread is not None else "",
        "max_spread": system.max_spread if system.max_spread is not None else "",
        "min_total": system.min_total if system.min_total is not None else "",
        "max_total": system.max_total if system.max_total is not None else "",
        "save_name": loaded_name,
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


def _feature_filters_from_request() -> list[dict[str, object]]:
    enabled = set(request.values.getlist("ff_enable"))
    keys = request.values.getlist("ff_key")
    ops = request.values.getlist("ff_op")
    values = request.values.getlist("ff_value")
    perspectives = request.values.getlist("ff_perspective")
    filters: list[dict[str, object]] = []
    for index, key in enumerate(keys):
        if not key or key not in enabled:
            continue
        op = ops[index] if index < len(ops) else "eq"
        raw_value = values[index] if index < len(values) else ""
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
        return float(raw_value) if raw_value.strip() else None
    return raw_value if str(raw_value).strip() else None


def _system_from_form(form: dict[str, object]) -> SystemFilter:
    feature_filters = tuple(
        FeatureFilter(
            key=str(row["key"]),
            op=str(row["op"]),
            value=row["value"],
            perspective=str(row.get("perspective", "single")),
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
        providers=_str_set(str(form["provider"])),
        min_spread=_optional_float(str(form["min_spread"])),
        max_spread=_optional_float(str(form["max_spread"])),
        min_total=_optional_float(str(form["min_total"])),
        max_total=_optional_float(str(form["max_total"])),
        feature_filters=feature_filters,
    )


def _int_set(value: str) -> set[int]:
    return {int(part.strip()) for part in value.split(",") if part.strip()}


def _str_set(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def _optional_float(value: str) -> float | None:
    return float(value) if value.strip() else None


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
    for group in ("pregame", "season_to_date", "team_preseason", "metadata", "result_lookahead"):
        if group in grouped:
            output.append({"group": group, "features": grouped[group]})
    return output


def _feature_option(feature: FeatureDef, feature_map: dict[int, dict] | None) -> dict[str, object]:
    values = _scan_values(feature, feature_map or {})
    return {
        "key": feature.key,
        "label": feature.label,
        "control": feature.control,
        "team_scoped": feature.team_scoped,
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
        items = items[::step]

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
