import json

from cfb_system_maker.graphql_client import graphql_scrape, pull_game_player_stats


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
    assert "orderBy: {id: ASC}" in q  # id used as sort key


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
    assert "orderBy: {id: ASC}" in captured["game"]
    assert "orderBy" not in captured["conference"]  # root doesn't advertise the arg
