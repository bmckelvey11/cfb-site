"""Load the floor-bias model's inputs from the DuckDB warehouse.

The model only ever needs four arrays per season -- favourite-side spread,
total, favourite points, underdog points -- so this module returns exactly the
contract `models_v2.load_raw_seasons` returns:

    {season: (spread_est, totals_est, fav_pts, dog_pts)}

Anything downstream (`run_walkforward.fit_train`, `monitor.walk_forward_bets`,
`bias_bins`, `roi_report`) therefore works unchanged with either source.

Why a second source at all: `load_raw_seasons` reads `data/raw/lines_*.json`,
which is a replay log of CFBD pulls and gets backfilled in place -- the files'
mtimes do not track their content (see
`docs/roi-refresh-backfill-2026-09-22.md`). `data/cfb.duckdb` is the warehouse
and the repo's stated source of truth.

`core.fact_game.selected_spread` / `selected_total` is the faithful analogue of
`models_v2.pick_line`: it prefers the `consensus` provider and falls back to a
book carrying both numbers. Sign convention matches CFBD -- negative means the
home team is favoured.

    from warehouse_source import load_warehouse_seasons
    data = load_warehouse_seasons(range(2013, 2027))

Run it directly for a self-check against the live warehouse:

    python v2/warehouse_source.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "cfb_paths.py").is_file():
            return parent
    raise RuntimeError("Cannot locate repository root containing cfb_paths.py")


sys.path.insert(0, str(_repo_root()))
from cfb_paths import DATA_ROOT  # noqa: E402

WAREHOUSE = DATA_ROOT / "cfb.duckdb"

# Deterministic order matters: callers that build a parallel per-game identity
# list pair by position, so an unordered result set would silently misalign it.
_QUERY = """
select game_id, season, week, start_date, home_team, away_team,
       selected_spread    as spread,
       selected_total     as total,
       selected_spread_provider_key as spread_provider,
       selected_total_provider_key  as total_provider,
       home_points, away_points
from core.fact_game
where season = any(?)
  and home_points is not null
  and away_points is not null
  and spread is not null
  and total is not null
  and spread <> 0          -- pick'em dropped, as load_raw_seasons does
  and total > 0            -- guards the -1.0 sentinel seen in the line tables
order by season, start_date, game_id
"""


# SENSITIVITY PROBE -- NOT A SHIPPING PATH. Its ROI is not usable.
#
# `selected_spread` / `selected_total` are chosen independently, so a game can
# carry a consensus spread beside a teamrankings total. models_v2.pick_line
# instead requires ONE provider to supply both, which is why the two sources
# disagree on ~20% of spreads -- a selection rule difference, not bad data
# (both sources are internally consistent with their own formatted_spread).
#
# implied_team_points does dog = (total - spread)/2, so in principle the pair
# should come from one market. In practice that argument does not survive
# measurement: this query's fallback `order by provider_key` is arbitrary, and
# requiring one provider to carry both fields drops 3,073 of 13,397 games --
# it scores a richer-coverage subsample, not the same games. Its ROI also moved
# 2.6 points when core.fact_game_line was rebuilt mid-analysis, while the
# shipped path reproduced exactly. Keep it to measure that sensitivity; do not
# report it. See docs/warehouse-as-model-source-2026-09-22.md.
_QUERY_PAIR = """
with pick as (
    select game_id, spread_close as spread, total_close as total, provider_key,
           row_number() over (
               partition by game_id
               order by case when lower(provider_key) = 'consensus' then 0 else 1 end,
                        provider_key
           ) as rn
    from core.fact_game_line
    where spread_close is not null and total_close is not null
      and spread_close <> 0 and total_close > 0
)
select g.game_id, g.season, g.week, g.start_date, g.home_team, g.away_team,
       p.spread, p.total,
       p.provider_key as spread_provider,
       p.provider_key as total_provider,
       g.home_points, g.away_points
from core.fact_game g
join pick p on p.game_id = g.game_id and p.rn = 1
where g.season = any(?)
  and g.home_points is not null
  and g.away_points is not null
order by g.season, g.start_date, g.game_id
"""


# Lines straight from stg.game_lines, which is what core.fact_game's
# selected_* columns are derived from. Used because that derivation regressed:
# on 2026-09-22 selected_total was NULL for every 2013-2016 game while the
# staging rows were intact, which silently removed four seasons.
#
# Selection rule, fixed on principle BEFORE it was scored, because the rule is
# worth several ROI points and must not be picked on the outcome:
#   tier 0  consensus          -- the market aggregate pick_line was reaching for
#   tier 1  a real sportsbook  -- a price that could actually have been taken
#   tier 2  a projection site  -- numberfire / teamrankings, never tradeable
# ...then by provider name, purely to make ties deterministic. Spread and total
# are chosen per field, as core.fact_game does, so a consensus spread is kept
# even when that provider published no total.
#
# period = 'game' is required: the table also carries firsthalf and
# firstquarter rows, which are a different market.
_QUERY_STG = """
with lines as (
    select l.gameId as game_id, p.name as provider, lower(p.name) as pkey,
           l.spread, l.overUnder as total,
           case when lower(p.name) = 'consensus' then 0
                when lower(p.name) in ('teamrankings', 'numberfire') then 2
                else 1 end as tier
    from stg.game_lines l
    join stg.lines_provider p on p.linesProviderId = l.linesProviderId
    where l.period = 'game'
),
sp as (
    select game_id, spread, provider,
           row_number() over (partition by game_id order by tier, pkey) rn
    from lines where spread is not null and spread <> 0
),
tt as (
    select game_id, total, provider,
           row_number() over (partition by game_id order by tier, pkey) rn
    from lines where total is not null and total > 0
)
select g.game_id, g.season, g.week, g.start_date, g.home_team, g.away_team,
       sp.spread, tt.total,
       sp.provider as spread_provider, tt.provider as total_provider,
       g.home_points, g.away_points
from core.fact_game g
join sp on sp.game_id = g.game_id and sp.rn = 1
join tt on tt.game_id = g.game_id and tt.rn = 1
where g.season = any(?)
  and g.home_points is not null
  and g.away_points is not null
order by g.season, g.start_date, g.game_id
"""


def load_warehouse_frame(seasons, db=WAREHOUSE, lines="fact_game"):
    """Every gradeable game for `seasons`, one row each, deterministically
    ordered. Carries identity columns the 4-tuple contract drops, which is what
    a reconciliation against the raw JSON needs.

    coherent_pair=False (default, and the shipping path) takes
    core.fact_game's selected_spread and selected_total.

    coherent_pair=True requires one provider to supply both, consensus first.
    It exists to measure how much the line-selection rule moves the result,
    which is a lot -- its own ROI is inflated by an arbitrary tiebreak and is
    not a reportable number.

    The fallback when no provider carries both is ordered by provider_key,
    where pick_line takes whichever book the CFBD JSON array happened to list
    first. Those two orders are not the same, so a game with no consensus pair
    can still differ between the sources.
    """
    import duckdb

    # Read-only: the warehouse is ~5GB and a scheduled slate run may hold it.
    con = duckdb.connect(str(db), read_only=True)
    try:
        query = {"game_lines": _QUERY_STG, "fact_game": _QUERY,
                 "fact_game_line": _QUERY_PAIR}[lines]
        return con.execute(query, [[int(s) for s in seasons]]).df()
    finally:
        con.close()


def _split_fav_dog(spread, home_pts, away_pts):
    """Favourite is the negative-spread side, matching load_raw_seasons."""
    home_fav = spread < 0
    fav = np.where(home_fav, home_pts, away_pts).astype(float)
    dog = np.where(home_fav, away_pts, home_pts).astype(float)
    return np.abs(spread).astype(float), fav, dog


def _assert_no_silent_gap(seasons, df, db):
    """Fail loudly when a season has played games but no usable lines.

    A season that returns zero rows does not raise on its own -- it simply
    disappears from the returned dict, and the walk-forward then starts
    `min_train` seasons later than intended and reports a smaller record that
    looks entirely plausible. That happened on 2026-09-22: a core rebuild left
    core.fact_game.selected_total NULL for 2013-2016 while the spreads and the
    upstream stg.game_lines totals were intact, which would have moved the
    first bet season from 2016 to 2020 without any error.
    """
    import duckdb

    present = set(df["season"].unique().tolist()) if len(df) else set()
    wanted = {int(s) for s in seasons}
    missing = sorted(wanted - present)
    if not missing:
        return

    con = duckdb.connect(str(db), read_only=True)
    try:
        played = dict(con.execute(
            "select season, count(*) from core.fact_game"
            " where season = any(?) and home_points is not null"
            " group by 1", [missing]).fetchall())
    finally:
        con.close()

    broken = {s: n for s, n in played.items() if n}
    if broken:
        detail = ", ".join(f"{s} ({n:,} played games)" for s, n in sorted(broken.items()))
        raise RuntimeError(
            "warehouse has played games but no usable spread+total for: "
            f"{detail}. The season would vanish from the walk-forward silently. "
            "Check core.fact_game.selected_total against stg.game_lines.overUnder "
            "-- a partial stg->core build can null it out.")


def load_warehouse_seasons(seasons, db=WAREHOUSE, lines="fact_game"):
    """dict season -> (spread_est, totals_est, fav_pts, dog_pts).

    Same contract, ordering rule and favourite convention as
    `models_v2.load_raw_seasons`, so the two are drop-in interchangeable.
    """
    df = load_warehouse_frame(seasons, db, lines)
    _assert_no_silent_gap(seasons, df, db)
    out = {}
    for season, g in df.groupby("season", sort=True):
        se, fp, dp = _split_fav_dog(
            g["spread"].to_numpy(), g["home_points"].to_numpy(),
            g["away_points"].to_numpy())
        out[int(season)] = (se, g["total"].to_numpy(float), fp, dp)
    return out


def _self_check():
    """Cheapest checks that fail if the favourite split or the contract breaks."""
    # Home favoured by 7 (spread -7): favourite scored 30, underdog 20.
    se, fp, dp = _split_fav_dog(
        np.array([-7.0, 7.0]), np.array([30, 20]), np.array([20, 30]))
    assert list(se) == [7.0, 7.0], se
    assert list(fp) == [30.0, 30.0], fp          # away side when spread > 0
    assert list(dp) == [20.0, 20.0], dp
    print("split self-check OK")

    data = load_warehouse_seasons(range(2013, 2027))
    assert data, "warehouse returned no seasons"
    for yr, arrays in sorted(data.items()):
        n = {len(a) for a in arrays}
        assert len(n) == 1, f"{yr}: ragged arrays {n}"
        se, te, fp, dp = arrays
        assert (se > 0).all(), f"{yr}: non-positive spread survived"
        assert (te > 0).all(), f"{yr}: non-positive total survived"
        assert np.isfinite(se).all() and np.isfinite(te).all(), f"{yr}: NaN line"
        print(f"  {yr}  n={len(se):5}  mean total {te.mean():5.2f}  "
              f"mean combined {(fp + dp).mean():5.2f}")
    print("warehouse self-check OK")


if __name__ == "__main__":
    _self_check()
