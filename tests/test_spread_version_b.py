import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import eval_version_b as vb  # noqa: E402


def _con():
    con = duckdb.connect()
    con.execute("create schema core")
    con.execute("""create table core.fact_game(season int, home_team varchar, away_team varchar,
                   home_points int, away_points int)""")
    con.execute("insert into core.fact_game values (2026, 'Alabama', 'East Carolina', 45, 10),"
                "(2026, 'Florida State', 'Georgia Tech', 20, 24)")
    return con


def test_fetch_scores_keys_on_unordered_pair():
    s = vb.fetch_scores(_con(), [2026])
    assert s[(2026, frozenset({"Alabama", "East Carolina"}))] == ("Alabama", 45, 10)


def test_home_margin_matches_pt_spelling_and_orientation():
    s = vb.fetch_scores(_con(), [2026])
    g = pd.DataFrame({"kick": ["2026-09-05T16:00:00+00:00", "2026-09-05T16:00:00+00:00"],
                      "home": ["Alabama", "Georgia Tech"], "road": ["East Carolina", "Florida St."]})
    m = vb.margins(g, s)
    assert m.tolist() == [35.0, 4.0]          # second game: PT home is CFBD away -> flipped sign
