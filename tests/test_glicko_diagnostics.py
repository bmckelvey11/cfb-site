"""glicko_diagnostics: conference-switch detection and the diagnose() report shape. In-memory."""
import numpy as np
import pandas as pd

from scripts.glicko_diagnostics import diagnose, switchers


def _frame():
    rng = np.random.default_rng(0)
    rows = []
    for season in (2021, 2022):
        for wk in range(1, 9):
            for i in range(6):
                fcs = i == 5
                conf_a = "SEC" if (season == 2022 and i == 0) else "B12"
                rows.append({"game_id": season * 1000 + wk * 10 + i, "season": season, "week": wk,
                             "season_type": "regular", "home": f"T{i}", "away": f"U{i}",
                             "home_div": "fbs", "away_div": "fcs" if fcs else "fbs",
                             "home_conf": conf_a, "away_conf": "MWC", "neutral": i == 4,
                             "mhat": rng.normal(0, 10), "margin": 0})
    d = pd.DataFrame(rows)
    d["e"] = rng.normal(0, 14, len(d))
    d["z"] = d["e"] / 15
    d["cluster"] = d["season"].astype(str) + "-" + d["week"].astype(str)
    return d


def test_switchers_flags_a_team_whose_conference_changed():
    assert switchers(_frame()) == {(2022, "T0")}


def test_diagnose_reports_every_check():
    d = _frame()
    out = diagnose(d, {d["game_id"].iloc[0]}, {(2022, "T0")})
    assert set(out) == {"D1_scale", "D2_fcs_gap", "D3_coverage", "D4_home_edge", "D5_switchers", "D6_overtime"}
    assert out["D3_coverage"]["overtime"]["n"] == 1
    assert out["D5_switchers"]["team_seasons"] == 1
    assert set(out["D4_home_edge"]) == {2021, 2022}
