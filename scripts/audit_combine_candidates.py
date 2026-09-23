"""Measure the `stg` table groups that hold one concept under *different* names.

The 13 REST/GraphQL pairs in `docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md`
section 3 were paired by name (`coach_season` / `coach_seasons`). This covers the pairs that
name matching cannot find -- `poll_rank` / `rankings`, `transfer` / `transfer_portal`,
`adjusted_player_metrics` / three REST tables -- plus the line-score explode siblings and
the `_ngt` twins. Findings: docs/warehouse-combine-candidates-2026-09-22.md.

    python scripts/audit_combine_candidates.py

Read-only. Like `audit_pair_columns.py` it reports evidence and does not build anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cfb_paths  # noqa: E402

# REST rounds adjusted metrics to 2 decimals; GraphQL carries full precision.
ROUNDING_TOL = 0.005

# Every REST adjusted_team_season metric, and the GraphQL adjusted_team_metrics column
# that holds it under another name.
ADJ_TEAM_COLUMNS = {
    "epa_total": "epa", "epa_passing": "passingEpa", "epa_rushing": "rushingEpa",
    "epaAllowed_total": "epaAllowed", "epaAllowed_passing": "passingEpaAllowed",
    "epaAllowed_rushing": "rushingEpaAllowed", "explosiveness": "explosiveness",
    "explosivenessAllowed": "explosivenessAllowed",
    "rushing_highlightYards": "highlightYards", "rushing_lineYards": "lineYards",
    "rushing_openFieldYards": "openFieldYards", "rushing_secondLevelYards": "secondLevelYards",
    "rushingAllowed_highlightYards": "highlightYardsAllowed",
    "rushingAllowed_lineYards": "lineYardsAllowed",
    "rushingAllowed_openFieldYards": "openFieldYardsAllowed",
    "rushingAllowed_secondLevelYards": "secondLevelYardsAllowed",
    "successRate_total": "success", "successRate_standardDowns": "standardDownsSuccess",
    "successRate_passingDowns": "passingDownsSuccess",
    "successRateAllowed_total": "successAllowed",
    "successRateAllowed_standardDowns": "standardDownsSuccessAllowed",
    "successRateAllowed_passingDowns": "passingDownsSuccessAllowed",
}

NGT_KEYS = {
    "ppa_games": '"gameId", team',
    "advanced_game_stats": '"gameId", team',
    "ppa_teams": "season, team",
    "advanced_season_stats": "season, team",
    "player_usage": 'season, "athleteId"',
    "ppa_players_season": 'season, "athleteId"',
    "ppa_players_games": 'season, week, "seasonType", "athleteId"',
    "player_success_game": '"gameId", "athleteId"',
    "player_success_season": 'season, "athleteId"',
}


def main() -> None:
    con = duckdb.connect(str(cfb_paths.DATA_ROOT / "cfb.duckdb"), read_only=True)

    def show(label: str, sql: str) -> None:
        rows = con.execute(sql).fetchall()
        print(f"  {label}: {rows[0] if len(rows) == 1 else rows}")

    print("polls: GraphQL poll_rank vs REST rankings__polls__polls_ranks")
    show("gql span (min, max, rows)", "SELECT min(poll_season), max(poll_season), count(*) FROM stg.poll_rank")
    show("rest span (min, max, rows)", "SELECT min(season), max(season), count(*) FROM stg.rankings__polls__polls_ranks")
    show("2026 max week (gql, rest)", """SELECT
        (SELECT max(poll_week) FROM stg.poll_rank WHERE poll_season = 2026),
        (SELECT max(week) FROM stg.rankings__polls__polls_ranks WHERE season = 2026)""")
    show("AP 2012-25 on (season, week, seasonType, school): gql, rest, matched, rank differs", """
        WITH g AS (SELECT poll_season s, poll_week w, poll_seasonType st, team_school t, rank r
                   FROM stg.poll_rank WHERE poll_pollType_name = 'AP Top 25'
                   AND poll_season BETWEEN 2012 AND 2025),
             r AS (SELECT season s, week w, "seasonType" st, polls_ranks_school t, polls_ranks_rank r
                   FROM stg.rankings__polls__polls_ranks WHERE polls_poll = 'AP Top 25'
                   AND season BETWEEN 2012 AND 2025)
        SELECT (SELECT count(*) FROM g), (SELECT count(*) FROM r),
               count(*), count(*) FILTER (WHERE g.r <> r.r)
        FROM g JOIN r USING (s, w, st, t)""")
    show("rest rows with NULL teamId", "SELECT count(*) FROM stg.rankings__polls__polls_ranks WHERE \"polls_ranks_teamId\" IS NULL")

    print("line scores: GraphQL game__*_line_scores vs REST games__*_line_scores")
    for side, col, rest, gql in (
            ("home", "homeLineScores", "stg.games__home_line_scores", "stg.game__home_line_scores"),
            ("away", "awayLineScores", "stg.games__away_line_scores", "stg.game__away_line_scores")):
        show(f"{side}: matched periods, value differs", f"""
            SELECT count(*), count(*) FILTER (WHERE r."{col}" IS DISTINCT FROM g."{col}")
            FROM {rest} r JOIN {gql} g
              ON r."gameId" = g."gameId" AND r."{col}_idx" = g."{col}_idx" """)
    show("games with line scores (gql, rest, rest not in gql, gql not in rest)", """
        WITH g AS (SELECT DISTINCT "gameId" FROM stg.game__home_line_scores),
             r AS (SELECT DISTINCT "gameId" FROM stg.games__home_line_scores)
        SELECT (SELECT count(*) FROM g), (SELECT count(*) FROM r),
               (SELECT count(*) FROM r ANTI JOIN g USING ("gameId")),
               (SELECT count(*) FROM g ANTI JOIN r USING ("gameId"))""")

    print(f"adjusted player: GraphQL long form vs REST wide (tolerance {ROUNDING_TOL})")
    for metric, table, value in (("passing", "adjusted_player_passing", "wepa"),
                                 ("rushing", "adjusted_player_rushing", "wepa"),
                                 ("field_goals", "kicker_paar", "paar")):
        show(f"{metric}: rest, gql, matched, value off, rest-only, gql-only", f"""
            WITH r AS (SELECT "athleteId"::VARCHAR a, year y, {value} v FROM stg.{table}),
                 g AS (SELECT "athleteId"::VARCHAR a, year y, "metricValue" v
                       FROM stg.adjusted_player_metrics WHERE "metricType" = '{metric}')
            SELECT (SELECT count(*) FROM r), (SELECT count(*) FROM g),
                   (SELECT count(*) FROM r JOIN g USING (a, y)),
                   (SELECT count(*) FROM r JOIN g USING (a, y) WHERE abs(r.v - g.v) > {ROUNDING_TOL}),
                   (SELECT count(*) FROM r ANTI JOIN g USING (a, y)),
                   (SELECT count(*) FROM g ANTI JOIN r USING (a, y))""")

    print("adjusted team: GraphQL adjusted_team_metrics vs REST adjusted_team_season")
    show("spans (gql, rest)", """SELECT
        (SELECT min(year) || '-' || max(year) || ' / ' || count(*) FROM stg.adjusted_team_metrics),
        (SELECT min(season) || '-' || max(season) || ' / ' || count(*) FROM stg.adjusted_team_season)""")
    show("rest keys absent from gql", """SELECT count(*) FROM (
        SELECT season, "teamId" FROM stg.adjusted_team_season
        EXCEPT SELECT year, "teamId" FROM stg.adjusted_team_metrics)""")
    off = " + ".join(
        f'(abs(s."{r}" - m."{g}") > {ROUNDING_TOL})::INT' for r, g in ADJ_TEAM_COLUMNS.items()
    )
    show(f"{len(ADJ_TEAM_COLUMNS)} mapped metrics: matched rows, cells off", f"""
        SELECT count(*), sum({off}) FROM stg.adjusted_team_season s
        JOIN stg.adjusted_team_metrics m ON m.year = s.season AND m."teamId" = s."teamId" """)

    print("transfers: GraphQL transfer vs REST transfer_portal")
    key = """t.season = p.season AND t."firstName" IS NOT DISTINCT FROM p."firstName"
             AND t."lastName" IS NOT DISTINCT FROM p."lastName"
             AND t."transferDate" IS NOT DISTINCT FROM p."transferDate" """
    show("gql rows, matched in rest", f"SELECT count(*), count(p.season) FROM stg.transfer t LEFT JOIN stg.transfer_portal p ON {key}")
    show("rest rows, matched in gql", f"SELECT count(*), count(t.season) FROM stg.transfer_portal p LEFT JOIN stg.transfer t ON {key}")

    print("_ngt twins: base rows, base distinct keys, ngt rows, keys in both")
    for base, k in NGT_KEYS.items():
        show(base, f"""SELECT (SELECT count(*) FROM stg.{base}),
            (SELECT count(DISTINCT ({k})) FROM stg.{base}), (SELECT count(*) FROM stg.{base}_ngt),
            (SELECT count(*) FROM (SELECT {k} FROM stg.{base} INTERSECT SELECT {k} FROM stg.{base}_ngt))""")

    print("non-candidate: pregame_win_prob vs game_team.winProb (home)")
    show("matched, differ by > 0.001", """
        SELECT count(*), count(*) FILTER (WHERE abs(p."homeWinProbability" - gt."winProb") > 0.001)
        FROM stg.pregame_win_prob p JOIN stg.game_team gt
          ON gt."gameId" = p."gameId" AND gt."homeAway" = 'home'""")


if __name__ == "__main__":
    main()
