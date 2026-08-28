import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_prediction_tracker",
    Path(__file__).resolve().parents[1] / "scripts" / "build_prediction_tracker.py",
)
pt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pt)


def _game(gid, home, away, week, season_type, hp, ap):
    return {
        "game_id": gid,
        "home": home,
        "away": away,
        "week": week,
        "season_type": season_type,
        "home_points": hp,
        "away_points": ap,
    }


def test_candidates_expands_st_and_aliases():
    assert "Fresno State" in pt.candidates("Fresno St.")
    assert "UCF" in pt.candidates("Central Florida")
    assert pt.candidates("Alabama") == ["Alabama"]


def test_rematch_split_by_score_not_week():
    """2011 LSU/Alabama: the BCS title game and the regular-season meeting share a pair."""
    regular = _game(313090333, "Alabama", "LSU", 10, "regular", 6, 9)
    title = _game(320090099, "LSU", "Alabama", 1, "postseason", 0, 21)
    # PT files the title game as home LSU 0, road Alabama 21, at its own week 19
    game, flipped, status = pick = pt.pick_game([regular, title], "LSU", 0, 21, 19)
    assert (game["game_id"], flipped, status) == (320090099, False, "matched")
    assert pick


def test_orientation_flip_on_neutral_site():
    bowl = _game(1, "Navy", "Wake Forest", 1, "postseason", 19, 29)
    game, flipped, status = pt.pick_game([bowl], "Wake Forest", 29, 19, 20)
    assert (game["game_id"], flipped, status) == (1, True, "matched")


def test_sole_candidate_kept_but_flagged_when_scores_disagree():
    only = _game(7, "Duke", "Clemson", 9, "regular", 28, 7)
    game, _, status = pt.pick_game([only], "Duke", 29, 7, 9)
    assert (game["game_id"], status) == (7, "matched_score_mismatch")


def test_unsplittable_rematch_is_ambiguous_not_guessed():
    a = _game(1, "UCF", "Memphis", 5, "regular", 40, 13)
    b = _game(2, "UCF", "Memphis", 14, "regular", 62, 55)
    game, _, status = pt.pick_game([a, b], "UCF", 0, 0, 3)
    assert game is None and status == "ambiguous"


def test_read_season_csv_folds_header_and_drops_ruler_rows(tmp_path):
    path = tmp_path / "ncaa2001.csv"
    path.write_text(
        "HOME,ROAD,WEEK,LINESAG,HSCORE\n"
        "1234567890123456,0123456789012345,1,7890.12,2349.2\n"
        "BYU,Tulane,1,11.56,70\n",
        encoding="utf-8",
    )
    rows, header = pt.read_season_csv(path, 2001)
    # week is the only PT column renamed -- CFBD owns the plain "week" in the output
    assert header == ["home", "road", "pt_week", "linesag", "hscore"]
    assert rows == [
        {
            "home": "BYU",
            "road": "Tulane",
            "pt_week": "1",
            "linesag": "-11.56",
            "hscore": "70",
            "season": "2001",
        }
    ]


def test_clean_cells_blanks_junk_the_source_ships():
    row = pt.clean_cells(
        {
            "hscore": "-18.95",  # 2006 row whose tail is shifted a column
            "vscore": "21",
            "linecoll": "USC",  # a team name in a spread column
            "linesag": "-3.5",
        }
    )
    assert row == {"hscore": "", "vscore": "21", "linecoll": "", "linesag": "3.5"}


def test_spreads_flip_to_the_repo_sign_convention():
    """PT writes spreads positive when home is favored; GameRecord.spread is negative."""
    row = pt.clean_cells({"line": "9.5", "lineopen": "-3", "linesag": "0", "linestd": "6.77"})
    assert row == {
        "line": "-9.5",
        "lineopen": "3",
        "linesag": "0",  # no -0
        "linestd": "6.77",  # a dispersion across the models, not a spread -- never flipped
    }


def test_order_columns_groups_by_block_and_ranks_models_by_coverage():
    rows = [
        {"linesag": "1", "linerare": "", "linegone": ""},
        {"linesag": "2", "linerare": "3", "linegone": ""},
    ]
    fieldnames, models = pt.order_columns(rows, ["linegone", "linerare", "linesag"])
    assert models == ["linesag", "linerare"]  # linegone is empty and drops out
    assert fieldnames[: len(pt.IDENTITY)] == pt.IDENTITY
    assert fieldnames[-2:] == ["linesag", "linerare"]
    assert fieldnames[len(pt.IDENTITY) : len(pt.IDENTITY) + 2] == ["home", "road"]
