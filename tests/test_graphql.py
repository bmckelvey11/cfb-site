import json
import re

from cfb_system_maker.graphql_client import (
    GQL_DEFAULT_TABLES,
    GQL_ENTITY_TO_RAW,
    GQL_ENTITY_TO_STG,
    GQL_RAW_TO_ENTITY,
    graphql_scrape,
    pull_game_player_stats,
)


def test_gql_entity_to_stg_is_total_and_injective():
    # Every GraphQL entity we pull must have an explicit destination — no fallback,
    # no clash detection. That totality is what removes the load-order dependence.
    assert set(GQL_ENTITY_TO_STG) == set(GQL_DEFAULT_TABLES)
    assert len(set(GQL_ENTITY_TO_STG.values())) == len(GQL_ENTITY_TO_STG)


def test_gql_destinations_are_bare_snake_case():
    # stg_gql destinations carry no gql_ prefix — the schema is the disambiguator now.
    for entity, dest in GQL_ENTITY_TO_STG.items():
        assert not dest.startswith("gql_"), f"{entity} -> {dest} still carries gql_ prefix"
        assert re.fullmatch(r"[a-z0-9_]+", dest), f"{entity} -> {dest} is not snake_case"


def test_gql_destinations_match_spec_examples():
    assert GQL_ENTITY_TO_STG["game"] == "game"
    assert GQL_ENTITY_TO_STG["gameLines"] == "game_lines"
    assert GQL_ENTITY_TO_STG["adjustedPlayerMetrics"] == "adjusted_player_metrics"
    assert GQL_ENTITY_TO_STG["playerStatCategory"] == "player_stat_category"
    assert GQL_ENTITY_TO_STG["calendar"] == "calendar"


def test_gql_entity_to_raw_is_total_injective_and_prefixed():
    # raw naming must stay decoupled from the stg_gql scheme: same shape the old
    # (prefixed) GQL_ENTITY_TO_STG had, so raw tables keep colliding with nothing.
    assert set(GQL_ENTITY_TO_RAW) == set(GQL_DEFAULT_TABLES)
    assert len(set(GQL_ENTITY_TO_RAW.values())) == len(GQL_ENTITY_TO_RAW)
    for entity, raw_name in GQL_ENTITY_TO_RAW.items():
        assert raw_name.startswith("gql_"), f"{entity} -> {raw_name} lacks gql_ prefix"


def test_gql_entity_to_raw_matches_shipped_prefix_scheme():
    # These are the exact values the (unapplied) gql_ prefix build shipped for `stg`.
    # raw keeps them verbatim even though stg_gql no longer does.
    assert GQL_ENTITY_TO_RAW["game"] == "gql_game"
    assert GQL_ENTITY_TO_RAW["gameLines"] == "gql_game_lines"
    assert GQL_ENTITY_TO_RAW["draftPicks"] == "gql_draft_picks"
    assert GQL_ENTITY_TO_RAW["calendar"] == "gql_calendar"


def test_gql_raw_to_entity_is_exact_inverse_of_gql_entity_to_raw():
    assert GQL_RAW_TO_ENTITY == {raw: entity for entity, raw in GQL_ENTITY_TO_RAW.items()}
    assert len(GQL_RAW_TO_ENTITY) == len(GQL_ENTITY_TO_RAW)


def test_gql_raw_names_never_collide_with_rest_raw_names():
    # The bug this whole scheme exists to prevent, one layer up: raw dumps for REST
    # endpoints that snake-case to the same bare name as a GraphQL entity.
    rest_raw_stems = {"games", "coaches", "conferences", "draft_picks", "recruits",
                       "recruiting_teams", "coach_seasons", "predicted_points", "talent",
                       "lines", "calendar", "draft_positions", "draft_teams"}
    assert not (set(GQL_ENTITY_TO_RAW.values()) & rest_raw_stems)


def _scalar(name="String"):
    return {"kind": "SCALAR", "name": name, "ofType": None}


def _obj(name):
    return {"kind": "OBJECT", "name": name, "ofType": None}


def _list_of(name):
    return {"kind": "LIST", "name": None, "ofType": {"kind": "OBJECT", "name": name, "ofType": None}}


def _args(*names):
    return [{"name": n} for n in names]


SCHEMA = {
    "__schema": {
        "queryType": {
            "fields": [
                {"name": "game", "args": _args("limit", "offset", "orderBy", "where"), "type": _list_of("game")},
                {"name": "conference", "args": [], "type": _list_of("conference")},  # non-paginated view
                {"name": "gameTeam", "args": _args("limit", "offset", "orderBy"), "type": _list_of("gameTeam")},  # no `id`
                {"name": "gameAggregate", "args": [], "type": _obj("gameAggregate")},  # no scalars -> ignored
            ]
        },
        "types": [
            {"name": "game", "fields": [
                {"name": "id", "type": _scalar("Int")},
                {"name": "season", "type": _scalar("Int")},
                {"name": "homeTeam", "type": _scalar()},
                {"name": "weather", "type": _obj("weather")},  # relation -> must be skipped
            ]},
            {"name": "gameTeam", "fields": [
                {"name": "endElo", "type": _scalar("Int")},
                {"name": "gameId", "type": _scalar("Int")},
                {"name": "homeAway", "type": _scalar()},
            ]},
            {"name": "conference", "fields": [
                {"name": "name", "type": _scalar()},
                {"name": "abbreviation", "type": _scalar()},
            ]},
            {"name": "gameAggregate", "fields": None},
        ],
    }
}


def make_post(dataset, captured=None):
    def post(query, variables):
        if "__schema" in query:
            return SCHEMA
        for root in dataset:
            if f"{root}(" in query or f"{root} {{" in query:
                if captured is not None:
                    captured[root] = query
                lo = variables.get("offset", 0)
                limit = variables.get("limit")
                hi = lo + limit if limit is not None else None
                return {root: dataset[root][lo:hi]}
        raise AssertionError(f"no known root in query: {query}")
    return post


def test_writes_table_files_and_counts(tmp_path):
    data = {"game": [{"id": i, "season": 2023} for i in range(5)],
            "conference": [{"name": "SEC"}, {"name": "Big Ten"}]}
    reports = graphql_scrape(data_dir=tmp_path, post_fn=make_post(data))

    by_name = {r.name: r for r in reports}
    assert (tmp_path / "graphql" / "game.json").exists()
    assert json.loads((tmp_path / "graphql" / "game.json").read_text()) == data["game"]
    assert by_name["game"].rows == 5 and by_name["game"].error is None
    assert by_name["conference"].rows == 2


def test_pagination_walks_all_pages(tmp_path):
    data = {"game": [{"id": i, "season": 2023} for i in range(2500)]}
    reports = graphql_scrape(data_dir=tmp_path, only={"game"}, page_size=1000, post_fn=make_post(data))

    rows = json.loads((tmp_path / "graphql" / "game.json").read_text())
    assert len(rows) == 2500
    assert reports[0].pages == 3  # 1000 + 1000 + 500


def test_only_scalar_columns_selected(tmp_path):
    captured = {}
    data = {"game": [{"id": 1, "season": 2023}]}
    graphql_scrape(data_dir=tmp_path, only={"game"}, post_fn=make_post(data, captured))

    q = captured["game"]
    assert "id" in q and "season" in q and "homeTeam" in q
    assert "weather" not in q  # relation skipped
    assert "orderBy: [{id: ASC}]" in q  # unique id is already a total order


def test_season_filter_only_when_column_exists(tmp_path):
    captured = {}
    data = {"game": [{"id": 1, "season": 2023}], "conference": [{"name": "SEC"}]}
    graphql_scrape(data_dir=tmp_path, seasons=[2022, 2023], post_fn=make_post(data, captured))

    assert "where: {season: {_in: [2022, 2023]}}" in captured["game"]
    assert "where" not in captured["conference"]  # no season column -> no filter


def test_unknown_table_reported_not_raised(tmp_path):
    data = {"game": [{"id": 1, "season": 2023}]}
    reports = graphql_scrape(data_dir=tmp_path, tables=["nope"], post_fn=make_post(data))

    assert reports[0].name == "nope"
    assert reports[0].error is not None


def make_player_stat_post(rows_per_season, captured=None):
    def post(query, variables):
        if captured is not None:
            captured.append(query)
        season = next(s for s in rows_per_season if f"_eq: {s}" in query)
        lo = variables["offset"]
        hi = lo + variables["limit"]
        return {"gamePlayerStat": rows_per_season[season][lo:hi]}
    return post


def test_player_stats_per_season_files_and_season_filter(tmp_path):
    captured = []
    data = {2022: [{"id": i} for i in range(1500)], 2023: [{"id": i} for i in range(3)]}
    reports = pull_game_player_stats(
        [2022, 2023], data_dir=tmp_path, page_size=1000, post_fn=make_player_stat_post(data, captured)
    )

    assert json.loads((tmp_path / "graphql" / "gamePlayerStat_2022.json").read_text()) == data[2022]
    assert len(json.loads((tmp_path / "graphql" / "gamePlayerStat_2023.json").read_text())) == 3
    by = {r.name: r for r in reports}
    assert by["gamePlayerStat_2022"].rows == 1500 and by["gamePlayerStat_2022"].pages == 2
    assert any("_eq: 2022" in q for q in captured)  # season scoped into query


def test_player_stats_resume_skips_existing(tmp_path):
    data = {2023: [{"id": 1}]}
    pull_game_player_stats([2023], data_dir=tmp_path, post_fn=make_player_stat_post(data))
    reports = pull_game_player_stats([2023], data_dir=tmp_path, post_fn=make_player_stat_post(data))

    assert reports[0].skipped is True


def test_paginated_query_sorts_by_the_sort_key(tmp_path):
    """Unsorted limit/offset has no stable row order — pages can skip or repeat rows."""
    captured = {}
    data = {"game": [{"id": 1, "season": 2023}], "conference": [{"name": "SEC"}]}
    graphql_scrape(data_dir=tmp_path, post_fn=make_post(data, captured))

    # Hasura's arg is `orderBy` and its enum is uppercase; `order_by: {id: asc}` is rejected.
    assert "orderBy: [{id: ASC}]" in captured["game"]
    assert "orderBy" not in captured["conference"]  # root doesn't advertise the arg


def test_tables_without_an_id_sort_on_every_scalar_column(tmp_path):
    """A single non-unique sort key is worse than useless: ties break differently per
    request, so rows fall between page boundaries. Ordering on every scalar leaves ties
    only between byte-identical rows, which are interchangeable."""
    captured = {}
    data = {"gameTeam": [{"endElo": 1500, "gameId": 1, "homeAway": "home"}]}
    graphql_scrape(data_dir=tmp_path, tables=["gameTeam"], post_fn=make_post(data, captured))

    assert "orderBy: [{endElo: ASC}, {gameId: ASC}, {homeAway: ASC}]" in captured["gameTeam"]


def test_relation_keys_are_selected_and_sorted_through(tmp_path, monkeypatch):
    """A table whose own scalars don't identify a row needs its relation key in BOTH the
    selection (or the dump can't be joined) and the sort (or ties break per request)."""
    from cfb_system_maker import graphql_client

    monkeypatch.setitem(
        graphql_client.GQL_RELATION_KEYS, "gameTeam",
        {"game": ["season", "pollType.name"]},
    )
    captured = {}
    data = {"gameTeam": [{"endElo": 1, "gameId": 1, "homeAway": "home"}]}
    graphql_scrape(data_dir=tmp_path, tables=["gameTeam"], post_fn=make_post(data, captured))
    q = captured["gameTeam"]

    assert "game { season pollType { name } }" in q          # dotted path nests
    assert "{game: {season: ASC}}" in q                       # relation key orders first
    assert "{game: {pollType: {name: ASC}}}" in q             # and does so through two hops
    assert q.index("{game: {season: ASC}}") < q.index("{endElo: ASC}")


def test_selection_and_order_clause_render_nested_paths():
    from cfb_system_maker.graphql_client import _order_clause, _selection

    assert _selection(["season", "pollType.name"]) == "season pollType { name }"
    assert _order_clause("poll.pollType.name") == "{poll: {pollType: {name: ASC}}}"
    assert _order_clause("rank") == "{rank: ASC}"
