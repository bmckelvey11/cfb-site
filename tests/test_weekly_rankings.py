"""Weekly O/D/P rankings. In-memory: no CFB_DATA_ROOT, no network."""
import itertools

import pandas as pd

from scripts.weekly_rankings import page_data, rank_week, season_rankings

TRUE_O = {"A": 0.6, "B": 0.3, "C": 0.1, "D": -0.2, "E": -0.3, "F": -0.5}
TRUE_D = {"A": -0.4, "B": 0.2, "C": -0.1, "D": 0.5, "E": 0.0, "F": -0.2}
TRUE_P = {"A": 1.0, "B": -0.5, "C": 0.2, "D": 0.3, "E": -0.6, "F": -0.4}
TINY = {"lam_ppp": 1e-4, "lam_pace": 1e-7}


def _game(gid, home, away, week, home_bonus=0.0):
    n = 12.0 + TRUE_P[home] + TRUE_P[away]
    y_home = 2.1 + TRUE_O[home] + TRUE_D[away] + home_bonus
    y_away = 2.1 + TRUE_O[away] + TRUE_D[home]
    return {"game_id": gid, "season": 2024, "week": week, "home": home, "away": away,
            "neutral": True, "home_reg": y_home * n, "away_reg": y_away * n,
            "home_poss": n, "away_poss": n, "N": n, "ot": 0.0,
            "total": (y_home + y_away) * n, "gated": False}


def _round_robin(week=1):
    return pd.DataFrame([_game(i, h, a, week) for i, (h, a) in enumerate(itertools.permutations(TRUE_O, 2))])


def test_rank_one_is_best_offense_best_defense_and_fastest():
    _, t = rank_week(_round_robin(), **TINY)
    assert t["O_rank"].idxmin() == "A" and t["O_rank"].idxmax() == "F"
    assert t["D_rank"].idxmin() == "A" and t["D_rank"].idxmax() == "D"  # most negative D is 1
    assert t["P_rank"].idxmin() == "A" and t["P_rank"].idxmax() == "E"
    assert sorted(t["O_rank"]) == list(range(1, len(TRUE_O) + 1))


def test_prior_rates_idle_team_at_its_prior_and_pulls_played_teams_toward_theirs():
    prior = pd.DataFrame({"O0": [0.0] * 6 + [0.4], "D0": [0.0] * 7, "P0": [0.0] * 6 + [-0.9]},
                         index=list(TRUE_O) + ["Z"])
    _, t = rank_week(_round_robin(), lam_ppp=40, lam_pace=8, prior=prior)
    assert t.at["Z", "O"] == 0.4 and t.at["Z", "P"] == -0.9 and t.at["Z", "n_games"] == 0
    assert t.at["Z", "P_rank"] == 7  # ranked with everyone else, on prior alone
    _, base = rank_week(_round_robin(), lam_ppp=40, lam_pace=8)
    lifted = prior.assign(O0=[0.5] + [0.0] * 6)  # A's own last season says it is good
    _, t2 = rank_week(_round_robin(), lam_ppp=40, lam_pace=8, prior=lifted)
    assert t2.at["A", "O"] > base.at["A", "O"]


def test_each_week_sees_only_games_through_that_week():
    week1 = _round_robin(week=1)
    blowout = pd.DataFrame([_game(900, "F", "A", week=3, home_bonus=5.0)])
    weeks = season_rankings(pd.concat([week1, blowout], ignore_index=True), 2024, **TINY)
    assert [w for w, _, _ in weeks] == [1, 3]
    pd.testing.assert_frame_equal(weeks[0][2], rank_week(week1, **TINY)[1])
    assert weeks[1][2].at["F", "O"] > weeks[0][2].at["F", "O"]


def test_page_data_keeps_every_week_with_rows_in_offense_order(tmp_path):
    frames = []
    for week in (1, 2):
        _, t = rank_week(_round_robin(week), **TINY)
        frames.append(t.reset_index(names="team").assign(
            through_week=week, mu=2.1, nu=12.0, games_fit=30, games_scheduled=31))
    pd.concat(frames).to_csv(tmp_path / "2024.csv", index=False)
    (tmp_path / "notes.csv").write_text("ignored\n", encoding="utf-8")

    data = page_data(tmp_path)
    assert list(data) == ["2024"] and list(data["2024"]) == [1, 2]
    rows = data["2024"][2]["rows"]
    assert [r[3] for r in rows] == list(range(1, 7))  # O_rank ascending
    assert rows[0][0] == "A" and data["2024"][2]["scheduled"] == 31
