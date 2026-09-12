"""Ledger integrity across repeat imports, book views, and incomplete history."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('pick_history', Path(__file__).resolve().parents[1] /
                                            'models/over_zero/scripts/pick_history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def observation(**changes):
    return dict(model='slate', run_at='2026-09-12T13:45:02Z', view='Best lines',
                away='Howard', home='Indiana', pick='OVER', **changes)


def test_repeated_import_preserves_first_observation(tmp_path):
    path = tmp_path / 'history.csv'
    row = observation(total=66.5)
    assert history.append_history([row], path) == (1, 1)
    original = path.read_bytes()
    assert history.append_history([dict(row, total=70)], path) == (0, 1)
    assert path.read_bytes() == original


def test_separate_books_and_runs_and_unplayable_signal(tmp_path):
    path = tmp_path / 'history.csv'
    row = observation(playable=False)
    assert history.append_history([row, dict(row, view='FanDuel'),
                                   dict(row, run_at='2026-09-12T14:00:00Z'),
                                   dict(row, home='Other', pick='')], path) == (3, 3)
    assert len(history.read_csv(path)) == 3


def test_invalid_row_does_not_damage_existing_file(tmp_path):
    path = tmp_path / 'history.csv'
    history.append_history([observation()], path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='Missing history identity'):
        history.append_history([dict(observation(), home='')], path)
    assert path.read_bytes() == before
    assert not path.with_suffix('.csv.lock').exists()


def test_board_conversion_keeps_missing_fields_unknown():
    board = {'run_at': '2026-09-12T13:45:02Z', 'threshold': 1.75,
             'views': {'Bovada': {'picks': [{'date': 'Sep 12', 'time': '8:00 PM ET',
                       'away': 'A', 'home': 'B', 'total': 55.5, 'spread': -43.5,
                       'bias': 2.036, 'probability': 60.82}]}}}
    row, = history.board_rows(board, 'test')
    assert row['kickoff_utc'] == '2026-09-13T00:00:00+00:00'
    assert row['p_over'] == pytest.approx(.6082)
    assert row['playable'] is None
    assert row['best_odds'] is None
    assert row['lines_as_of'] is None


def test_empty_history_has_headers_and_nonfinite_is_blank(tmp_path):
    path = tmp_path / 'history.csv'
    assert history.append_history([], path) == (0, 0)
    history.append_history([observation(bet_to=float('nan'))], path)
    row, = history.read_csv(path)
    assert row['bet_to'] == ''
