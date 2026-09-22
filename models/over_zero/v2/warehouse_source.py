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


def load_warehouse_frame(seasons, db=WAREHOUSE):
    """Every gradeable game for `seasons`, one row each, deterministically
    ordered. Carries identity columns the 4-tuple contract drops, which is what
    a reconciliation against the raw JSON needs."""
    import duckdb

    # Read-only: the warehouse is ~5GB and a scheduled slate run may hold it.
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(_QUERY, [[int(s) for s in seasons]]).df()
    finally:
        con.close()


def _split_fav_dog(spread, home_pts, away_pts):
    """Favourite is the negative-spread side, matching load_raw_seasons."""
    home_fav = spread < 0
    fav = np.where(home_fav, home_pts, away_pts).astype(float)
    dog = np.where(home_fav, away_pts, home_pts).astype(float)
    return np.abs(spread).astype(float), fav, dog


def load_warehouse_seasons(seasons, db=WAREHOUSE):
    """dict season -> (spread_est, totals_est, fav_pts, dog_pts).

    Same contract, ordering rule and favourite convention as
    `models_v2.load_raw_seasons`, so the two are drop-in interchangeable.
    """
    df = load_warehouse_frame(seasons, db)
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
