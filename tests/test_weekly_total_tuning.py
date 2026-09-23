"""Joint lambda tuning on total-forecast loss. In-memory: no CFB_DATA_ROOT, no network."""
import pandas as pd

from scripts.weekly_total_tuning import tune_total
from test_weekly_ratings import _round_robin

GRID = dict(grid_ppp=(10, 40, 160), grid_pace=(2, 8, 32))


def _season(season: int) -> pd.DataFrame:
    g = _round_robin().assign(season=season)
    g["week"] = 1 + g.index // 8  # four-plus weeks, kickoffs already increasing
    g["kickoff"] = g["kickoff"] + pd.Timedelta(days=365 * (season - 2024))
    # Noise so the grid points differ.
    g["total"] = g["total"] + [(-1) ** i * (i % 5) for i in range(len(g))]
    return g


def test_tuner_returns_the_minimum_of_its_own_grid():
    out = tune_total(_season(2024), [2024], **GRID)
    losses = {tuple(map(float, k.split("/"))): v for k, v in out["mae_by_lambda"].items()}
    assert len(losses) == 9
    best = min(losses, key=losses.get)
    assert (out["lambda_ppp"], out["lambda_pace"]) == best
    assert out["n_games"] > 0


def test_tuner_ignores_games_outside_its_seasons():
    base = _season(2024)
    later = _season(2025)
    later["total"] = later["total"] + 500.0
    later["home_reg"] = later["home_reg"] * 9
    alone = tune_total(base, [2024], **GRID)
    mixed = tune_total(pd.concat([base, later], ignore_index=True), [2024], **GRID)
    assert alone == mixed
