"""Team-level offensive/defensive scheme tendencies from PFF split data.

PFF carries no scheme *labels* (no "Air Raid", no "3-4"). What it carries is a
`split` dimension on six staging tables plus alignment snap counts, from which
team scheme rates are derivable. This script rolls the player-week rows up to
one row per team-season and writes a CSV.

Usage:
    python scripts/pff_scheme_profile.py                 # 2025, default out path
    python scripts/pff_scheme_profile.py --season 2024
    python scripts/pff_scheme_profile.py --inventory     # print split inventory only

See docs/pff-scheme-inventory-2026-09-16.md for what each column means and what
it does not support.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402

INVENTORY_TABLES = (
    "pff_defense_coverage",
    "pff_defense_pass_rush",
    "pff_run_blocking",
    "pff_pass_blocking",
    "pff_passing",
    "pff_receiving",
)


def _share(num: str, den: str) -> str:
    """Rate guarded on a positive denominator.

    Gate on `> 0`, never `is not null`: the flattener emits NaN (not NULL) for
    absent numerics, and it emits a row per split whether or not the player had
    plays there.
    """
    return f"case when {den} > 0 then {num} / ({den})::double end"


SQL_TEMPLATE = """
with cov as (  -- man/zone: coverage-defender snaps, not plays. 'all' excluded:
               -- its row population differs from man/zone and would skew the denominator.
    select franchise_id,
           sum(snap_counts_coverage) filter (where split = 'man')  as man_snaps,
           sum(snap_counts_coverage) filter (where split = 'zone') as zone_snaps
    from stg.pff_defense_coverage where season = ? group by 1
),
dsum as (  -- defensive alignment: where the 11 line up
    select franchise_id,
           sum(snap_counts_defense)       as def_snaps,
           sum(snap_counts_dl)            as dl_snaps,
           sum(snap_counts_box)           as box_snaps,
           sum(snap_counts_corner)        as corner_snaps,
           sum(snap_counts_fs)            as fs_snaps,
           sum(snap_counts_slot)          as slot_snaps,
           sum(snap_counts_dl_a_gap)      as dl_a_gap,
           sum(snap_counts_dl_b_gap)      as dl_b_gap,
           sum(snap_counts_dl_over_t)     as dl_over_t,
           sum(snap_counts_dl_outside_t)  as dl_outside_t
    from stg.pff_defense_summary where season = ? group by 1
),
rb as (  -- run-block scheme. The equivalent from pff_rushing gap/zone_attempts
         -- is r = 0.9997 with this, so only one of the two is carried.
    select franchise_id,
           sum(snap_counts_run_block) filter (where split = 'gap')  as gap_rb,
           sum(snap_counts_run_block) filter (where split = 'zone') as zone_rb
    from stg.pff_run_blocking where season = ? group by 1
),
osum as (
    select franchise_id,
           sum(snap_counts_total_pass) as off_pass_snaps,
           sum(snap_counts_total_run)  as off_run_snaps
    from stg.pff_offense_summary where season = ? group by 1
),
pass as (  -- QB-view splits. blitz/pressure here are what the offense FACED.
    select franchise_id,
           sum(dropbacks) filter (where split = 'all')            as db_all,
           sum(dropbacks) filter (where split = 'pa')             as db_pa,
           sum(dropbacks) filter (where split = 'npa')            as db_npa,
           sum(dropbacks) filter (where split = 'screen')         as db_screen,
           sum(dropbacks) filter (where split = 'no_screen')      as db_no_screen,
           sum(dropbacks) filter (where split = 'blitz')          as db_blitz,
           sum(dropbacks) filter (where split = 'no_blitz')       as db_no_blitz,
           sum(dropbacks) filter (where split = 'pressure')       as db_pressure,
           sum(dropbacks) filter (where split = 'no_pressure')    as db_no_pressure,
           sum(dropbacks) filter (where split = 'ttt_under_2_5')  as db_ttt_fast,
           sum(dropbacks) filter (where split = 'ttt_over_2_5')   as db_ttt_slow,
           sum(attempts)  filter (where split = 'behind_los')     as att_behind_los,
           sum(attempts)  filter (where split = 'short')          as att_short,
           sum(attempts)  filter (where split = 'medium')         as att_medium,
           sum(attempts)  filter (where split = 'deep')           as att_deep
    from stg.pff_passing where season = ? group by 1
),
recv as (  -- receiver deployment; split='all' carries the alignment snaps
    select franchise_id,
           sum(slot_snaps)   as wr_slot_snaps,
           sum(wide_snaps)   as wr_wide_snaps,
           sum(inline_snaps) as wr_inline_snaps
    from stg.pff_receiving where season = ? and split = 'all' group by 1
),
dir as (  -- run direction. The QB* direction codes are kneels/sneaks/scrambles,
          -- NOT designed QB runs -- a designed keep is coded to its gap.
    select franchise_id,
           sum(attempts) filter (where direction in ('LG','ML','MR','RG')) as run_interior,
           sum(attempts) filter (where direction in ('LT','RT'))           as run_tackle,
           sum(attempts) filter (where direction in ('LE','RE'))           as run_edge
    from stg.pff_rushing_direction where season = ? group by 1
),
qbrun as (  -- designed QB runs = QB carries less scrambles, via the position join
    select r.franchise_id,
           sum(r.attempts - coalesce(r.scrambles, 0))
               filter (where ps.position = 'QB')                           as qb_designed,
           sum(r.attempts - coalesce(r.scrambles, 0))                      as all_designed
    from stg.pff_rushing r
    join stg.pff_player_season ps
      on ps.season = r.season and ps.player_id = r.player_id
    where r.season = ? group by 1
)
select
    f.team_name,
    f.cfbd_team_id,
    cov.franchise_id,
    -- defense: coverage shell and front
    {man_rate}        as def_man_rate,
    {dl_rate}         as def_dl_snap_share,
    {box_rate}        as def_box_snap_share,
    {corner_rate}     as def_corner_snap_share,
    {slot_d_rate}     as def_slot_db_share,
    {fs_rate}         as def_fs_snap_share,
    {a_gap_rate}      as def_dl_a_gap_share,
    {edge_rate}       as def_dl_outside_t_share,
    -- offense: own play-calling tendencies
    {pass_rate}       as off_pass_snap_rate,
    {gap_rb_rate}     as off_gap_run_rate,
    {pa_rate}         as off_play_action_rate,
    {screen_rate}     as off_screen_rate,
    {ttt_fast_rate}   as off_quick_game_rate,
    {deep_rate}       as off_deep_attempt_rate,
    {behind_rate}     as off_behind_los_rate,
    {slot_rate}       as off_wr_slot_rate,
    {inline_rate}     as off_te_inline_rate,
    {qb_run_rate}     as off_qb_designed_run_rate,
    {interior_rate}   as off_run_interior_rate,
    -- offense: what opponents did to it (not this team's own call)
    {blitz_faced}     as off_blitz_faced_rate,
    {pressure_faced}  as off_pressure_faced_rate,
    -- volume, for filtering
    cov.man_snaps + cov.zone_snaps as cov_snaps,
    dsum.def_snaps,
    pass.db_all as dropbacks
from cov
join dsum  using (franchise_id)
join rb    using (franchise_id)
join osum  using (franchise_id)
join pass  using (franchise_id)
join recv  using (franchise_id)
join dir   using (franchise_id)
join qbrun using (franchise_id)
join stg.pff_franchise f using (franchise_id)
order by f.team_name
"""

DL_DEN = "dsum.dl_a_gap + dsum.dl_b_gap + dsum.dl_over_t + dsum.dl_outside_t"
DEPTH_DEN = "pass.att_behind_los + pass.att_short + pass.att_medium + pass.att_deep"
ALIGN_DEN = "recv.wr_slot_snaps + recv.wr_wide_snaps + recv.wr_inline_snaps"

SQL = SQL_TEMPLATE.format(
    man_rate=_share("cov.man_snaps", "cov.man_snaps + cov.zone_snaps"),
    dl_rate=_share("dsum.dl_snaps", "dsum.def_snaps"),
    box_rate=_share("dsum.box_snaps", "dsum.def_snaps"),
    corner_rate=_share("dsum.corner_snaps", "dsum.def_snaps"),
    slot_d_rate=_share("dsum.slot_snaps", "dsum.def_snaps"),
    fs_rate=_share("dsum.fs_snaps", "dsum.def_snaps"),
    a_gap_rate=_share("dsum.dl_a_gap", DL_DEN),
    edge_rate=_share("dsum.dl_outside_t", DL_DEN),
    pass_rate=_share("osum.off_pass_snaps", "osum.off_pass_snaps + osum.off_run_snaps"),
    gap_rb_rate=_share("rb.gap_rb", "rb.gap_rb + rb.zone_rb"),
    pa_rate=_share("pass.db_pa", "pass.db_pa + pass.db_npa"),
    screen_rate=_share("pass.db_screen", "pass.db_screen + pass.db_no_screen"),
    ttt_fast_rate=_share("pass.db_ttt_fast", "pass.db_ttt_fast + pass.db_ttt_slow"),
    deep_rate=_share("pass.att_deep", DEPTH_DEN),
    behind_rate=_share("pass.att_behind_los", DEPTH_DEN),
    slot_rate=_share("recv.wr_slot_snaps", ALIGN_DEN),
    inline_rate=_share("recv.wr_inline_snaps", ALIGN_DEN),
    qb_run_rate=_share("qbrun.qb_designed", "qbrun.all_designed"),
    interior_rate=_share("dir.run_interior", "dir.run_interior + dir.run_tackle + dir.run_edge"),
    blitz_faced=_share("pass.db_blitz", "pass.db_blitz + pass.db_no_blitz"),
    pressure_faced=_share("pass.db_pressure", "pass.db_pressure + pass.db_no_pressure"),
)

N_SEASON_PARAMS = 8


def inventory(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    frames = [
        con.execute(
            f"select '{table}' as tbl, split, count(*) as n_rows "
            f"from stg.{table} where season = ? group by 1, 2 order by 2",
            [season],
        ).df()
        for table in INVENTORY_TABLES
    ]
    return pd.concat(frames, ignore_index=True)


def profile(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    return con.execute(SQL, [season] * N_SEASON_PARAMS).df()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--db", default=None, help="path to cfb.duckdb")
    ap.add_argument("--out", default=None, help="output CSV path")
    ap.add_argument("--inventory", action="store_true", help="print split inventory and exit")
    args = ap.parse_args()

    con = duckdb.connect(args.db or str(DB_PATH), read_only=True)

    if args.inventory:
        print(inventory(con, args.season).to_string(index=False))
        return

    df = profile(con, args.season)
    out = Path(args.out or PROCESSED / f"pff_scheme_profile_{args.season}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} teams -> {out}")

    rate_cols = [c for c in df.columns if c.endswith(("_rate", "_share"))]
    print(df[rate_cols].describe().T[["count", "mean", "std", "min", "max"]].round(3).to_string())


def _selftest() -> None:
    """Smallest check that fails if the rate logic breaks: option academies must
    lead designed QB runs, and every rate must land in [0, 1] with no nulls."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = profile(con, 2025)
    assert len(df) == 136, f"expected 136 FBS teams, got {len(df)}"
    rate_cols = [c for c in df.columns if c.endswith(("_rate", "_share"))]
    assert not df[rate_cols].isna().any().any(), "null rate column"
    assert df[rate_cols].min().min() >= 0 and df[rate_cols].max().max() <= 1, "rate out of [0,1]"
    top3 = set(df.nlargest(3, "off_qb_designed_run_rate")["team_name"])
    assert top3 == {"Army Black Knights", "Navy Midshipmen", "Air Force Falcons"}, top3
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
