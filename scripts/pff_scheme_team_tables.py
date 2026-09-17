"""One CSV per side of the ball: PFF scheme rates + cluster label + warehouse context stats.

Splits the scheme work into an offense table and a defense table, each one row
per FBS team, carrying every column that went into the clustering plus the
team-season stats the warehouse already holds (tempo, efficiency, explosiveness,
line yards, havoc, opponent-adjusted EPA, SP+/FPI/Elo).

Team key is `stg.pff_franchise.cfbd_team_id` -> `core.dim_team` -> the CFBD
feeds, which joins all 136 FBS teams for 2025 with no misses.

Usage:
    python scripts/pff_scheme_team_tables.py                 # 2025, both files
    python scripts/pff_scheme_team_tables.py --season 2025 --out-dir some/dir

Writes <processed>/pff_scheme_offense_<season>.csv and ..._defense_<season>.csv.
See docs/pff-scheme-inventory-2026-09-16.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402
from scripts.pff_scheme_clusters import (  # noqa: E402
    DEFENSE_FEATS,
    OFFENSE_FEATS,
    QUALITY_R_THRESHOLD,
    SEED,
    load_sp_overall,
    quality_correlations,
    _match_school,
)
from scripts.pff_scheme_profile import profile  # noqa: E402

# Opponent behaviour faced -- context for the offense table, not a scheme feature.
OFFENSE_CONTEXT_RATES = ["off_blitz_faced_rate", "off_pressure_faced_rate"]

# Computed by the profile but excluded from the clustering as near-constant
# across FBS (sd .005 and .009). Carried here so the file is the complete record.
DEFENSE_CONTEXT_RATES = ["def_corner_snap_share", "def_slot_db_share"]

# Warehouse columns per side: {output_name: source_expression}. Tempo is
# plays/game and drives/game -- CFBD carries no seconds-per-play.
OFFENSE_STATS = {
    "off_plays": "a.offense_plays",
    "off_plays_per_game": "a.offense_plays / g.games::double",
    "off_drives_per_game": "a.offense_drives / g.games::double",
    "off_points_per_game": "g.points_for / g.games::double",
    "off_ppa": "a.offense_ppa",
    "off_success_rate": "a.offense_successRate",
    "off_explosiveness": "a.offense_explosiveness",
    "off_points_per_opportunity": "a.offense_pointsPerOpportunity",
    "off_line_yards": "a.offense_lineYards",
    "off_second_level_yards": "a.offense_secondLevelYards",
    "off_open_field_yards": "a.offense_openFieldYards",
    "off_power_success": "a.offense_powerSuccess",
    "off_stuff_rate_allowed": "a.offense_stuffRate",
    "off_havoc_allowed": "a.offense_havoc_total",
    "off_passing_downs_rate": "a.offense_passingDowns_rate",
    "off_passing_downs_success": "a.offense_passingDowns_successRate",
    "off_standard_downs_success": "a.offense_standardDowns_successRate",
    "off_rushing_ppa": "a.offense_rushingPlays_ppa",
    "off_passing_ppa": "a.offense_passingPlays_ppa",
    "off_adj_epa_total": "j.epa_total",
    "off_adj_epa_passing": "j.epa_passing",
    "off_adj_epa_rushing": "j.epa_rushing",
    "off_adj_success_rate": "j.successRate_total",
    "off_adj_explosiveness": "j.explosiveness",
    "sp_offense": "c.offense",
    "fpi_offense": "f.efficiencies_offense",
}

DEFENSE_STATS = {
    "def_plays": "a.defense_plays",
    "def_plays_per_game": "a.defense_plays / g.games::double",
    "def_drives_per_game": "a.defense_drives / g.games::double",
    "def_points_allowed_per_game": "g.points_against / g.games::double",
    "def_ppa": "a.defense_ppa",
    "def_success_rate_allowed": "a.defense_successRate",
    "def_explosiveness_allowed": "a.defense_explosiveness",
    "def_points_per_opportunity_allowed": "a.defense_pointsPerOpportunity",
    "def_line_yards_allowed": "a.defense_lineYards",
    "def_second_level_yards_allowed": "a.defense_secondLevelYards",
    "def_open_field_yards_allowed": "a.defense_openFieldYards",
    "def_power_success_allowed": "a.defense_powerSuccess",
    "def_stuff_rate": "a.defense_stuffRate",
    "def_havoc_total": "a.defense_havoc_total",
    "def_havoc_front_seven": "a.defense_havoc_frontSeven",
    "def_havoc_db": "a.defense_havoc_db",
    "def_passing_downs_rate": "a.defense_passingDowns_rate",
    "def_passing_downs_success_allowed": "a.defense_passingDowns_successRate",
    "def_standard_downs_success_allowed": "a.defense_standardDowns_successRate",
    "def_rushing_ppa_allowed": "a.defense_rushingPlays_ppa",
    "def_passing_ppa_allowed": "a.defense_passingPlays_ppa",
    "def_adj_epa_allowed_total": "j.epaAllowed_total",
    "def_adj_epa_allowed_passing": "j.epaAllowed_passing",
    "def_adj_epa_allowed_rushing": "j.epaAllowed_rushing",
    "def_adj_success_rate_allowed": "j.successRateAllowed_total",
    "def_adj_explosiveness_allowed": "j.explosivenessAllowed",
    "sp_defense": "c.defense",
    "fpi_defense": "f.efficiencies_defense",
}

# Carried on both files so either stands alone.
SHARED_STATS = {
    "conference": "a.conference",
    "games": "g.games",
    "wins": "g.wins",
    "sp_overall": "c.overall",
    "fpi": "f.fpi",
    "elo": "e.elo",
}

STATS_SQL = """
with g as (  -- games, record and points from the completed schedule
    select team_id, count(*) as games,
           sum(points_for) as points_for, sum(points_against) as points_against,
           sum(case when points_for > points_against then 1 else 0 end) as wins
    from (
        select home_team_id as team_id, home_points as points_for, away_points as points_against
        from core.fact_game where season = ? and completed
        union all
        select away_team_id, away_points, home_points
        from core.fact_game where season = ? and completed
    ) t
    where team_id is not null
    group by 1
)
select
    p.franchise_id,
    d.school,
    d.team_id as cfbd_team_id,
    {cols}
from stg.pff_franchise p
join core.dim_team d on d.team_id = p.cfbd_team_id
left join g on g.team_id = d.team_id
left join stg.advanced_season_stats a on a.team = d.school and a.season = ?
left join stg.adjusted_team_season  j on j.team = d.school and j.season = ?
left join stg.core_ratings          c on c.team = d.school and c.season = ?
left join stg.fpi                   f on f.team = d.school and f.season = ?
left join stg.elo                   e on e.team = d.school and e.season = ?
"""


def warehouse_stats(con: duckdb.DuckDBPyConnection, season: int,
                    stats: dict[str, str]) -> pd.DataFrame:
    cols = ",\n    ".join(f"{expr} as {name}" for name, expr in
                          {**SHARED_STATS, **stats}.items())
    return con.execute(STATS_SQL.format(cols=cols), [season] * 7).df()


def cluster_labels(prof: pd.DataFrame, feats: list[str], k: int = 2) -> pd.Series:
    x = StandardScaler().fit_transform(prof[feats].to_numpy())
    return pd.Series(KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(x),
                     index=prof.index)


def build(con: duckdb.DuckDBPyConnection, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    prof = profile(con, season)
    sp = load_sp_overall(season)
    prof["team_short"] = [_match_school(n, sp.index) for n in prof.team_name]

    # the defensive clustering that holds up drops the SP+-loaded features;
    # see docs/pff-scheme-inventory-2026-09-16.md
    corr = quality_correlations(prof, DEFENSE_FEATS, sp)
    clean_def = [f for f in DEFENSE_FEATS if abs(corr[f]) <= QUALITY_R_THRESHOLD]

    prof["offense_cluster"] = cluster_labels(prof, OFFENSE_FEATS)
    prof["defense_cluster"] = cluster_labels(prof, clean_def)

    frames = {}
    for side, feats, extra, stats, vol in (
        ("offense", OFFENSE_FEATS, OFFENSE_CONTEXT_RATES, OFFENSE_STATS, ["dropbacks"]),
        ("defense", DEFENSE_FEATS, DEFENSE_CONTEXT_RATES, DEFENSE_STATS,
         ["def_snaps", "cov_snaps"]),
    ):
        keep = ["team_name", "franchise_id", f"{side}_cluster"] + feats + extra + vol
        df = prof[keep].merge(warehouse_stats(con, season, stats),
                              on="franchise_id", how="left")
        # school/cfbd_team_id come from the join; put identity columns first
        ident = ["team_name", "school", "cfbd_team_id", "franchise_id", "conference"]
        df = df[ident + [c for c in df.columns if c not in ident]]
        frames[side] = df.sort_values("team_name").reset_index(drop=True)
    return frames["offense"], frames["defense"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    con = duckdb.connect(args.db or str(DB_PATH), read_only=True)
    off, dfn = build(con, args.season)

    out_dir = Path(args.out_dir or PROCESSED)
    out_dir.mkdir(parents=True, exist_ok=True)
    for side, df in (("offense", off), ("defense", dfn)):
        path = out_dir / f"pff_scheme_{side}_{args.season}.csv"
        df.to_csv(path, index=False)
        missing = df.isna().sum()
        missing = missing[missing > 0]
        print(f"{side}: {len(df)} teams x {len(df.columns)} cols -> {path}")
        if len(missing):
            print(f"  columns with nulls: {missing.to_dict()}")


def _selftest() -> None:
    """Guards the join: a silent key mismatch would show up as nulls, and the
    cluster labels must still reproduce the academies grouping."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    off, dfn = build(con, 2025)
    for side, df in (("offense", off), ("defense", dfn)):
        assert len(df) == 136, f"{side}: {len(df)} teams"
        nulls = df.isna().sum()
        assert not nulls.any(), f"{side} nulls: {nulls[nulls > 0].to_dict()}"
    academies = off[off.team_name.isin(
        ["Army Black Knights", "Navy Midshipmen", "Air Force Falcons"])]
    assert academies.offense_cluster.nunique() == 1, "academies split across clusters"
    assert off.off_plays_per_game.between(50, 90).all(), "implausible tempo"
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
