"""Verify the current board against its model CSV and report a completed game.

Run from the repository root with CFB_DATA_ROOT set.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'research/spread/scripts'))
import collect_line_timing as clt
from best_line_slate import bet_to_total, bias_of, fit_model, DEFAULT_CSV


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "cfb_paths.py").is_file():
            return parent
    raise RuntimeError("Cannot locate repository root containing cfb_paths.py")


sys.path.insert(0, str(_repo_root()))
from cfb_paths import DATA_ROOT  # noqa: E402

board = json.loads((ROOT / 'models/over_zero/site/lib/board.json').read_text())
rows = pd.read_csv(DATA_ROOT / 'processed/over_zero/best_line_slate_latest.csv')
assert set(rows.run_at) == {board['run_at']}
market = board['views']['Best lines']
assert market['scored'] == len(rows)
assert len(market['picks']) == int((rows.pick == 'OVER').sum())
for pick in market['picks']:
    row = rows[(rows.home == pick['home']) & (rows.away == pick['away'])].iloc[0]
    assert pick['total'] == row.total_fair
    assert pick['bias'] == round(row.bias_fair, 3)
    assert pick['bestTotal'] == row.best_total
    assert pick['bestOdds'] == row.best_odds
    assert pick['probability'] == round(row.p_over_fair * 100, 2)
now = datetime.fromisoformat(board['run_at'].replace('Z', '+00:00'))
for view in board['views'].values():
    for pick in view['picks']:
        kick = datetime.strptime(f"{now.year} {pick['date']} {pick['time'].removesuffix(' ET')}", '%Y %b %d %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York'))
        assert kick >= now, pick
print(f"PASS: {len(rows)} market games; {len(market['picks'])} signals; all views contain future games only.")
fit, _ = fit_model(Path(DEFAULT_CSV), range(2013, 2026))
lookup = np.array(board['betToBySpread'])
spreads_lookup = np.arange(len(lookup)) / 2
assert len(lookup) == 201
assert np.all(bias_of(spreads_lookup, lookup, fit) > board['threshold'])
assert np.all(bias_of(spreads_lookup, lookup + .5, fit) <= board['threshold'])
for view in board['views'].values():
    for pick in view['picks']:
        match = rows[(rows.home == pick['home']) & (rows.away == pick['away'])]
        assert pick['marketSpread'] == (None if match.empty else float(match.iloc[0].spread_fair))
print('PASS: all 201 editable spread cutoffs and market-spread references.')
count = 0
for name, view in board['views'].items():
    for pick in view['picks']:
        cutoff = pick['betTo']
        assert cutoff is not None and cutoff * 2 == int(cutoff * 2)
        assert bias_of(pick['spread'], cutoff, fit) > board['threshold'], (name, pick)
        assert bias_of(pick['spread'], cutoff + .5, fit) <= board['threshold'], (name, pick)
        count += 1
print(f'PASS: {count} Bet to values across all book views clear threshold; next half-point fails.')
spreads = np.array([-60., -45., 0., 45., 60.])
grid = np.arange(0, 150.5, .5)
for threshold in [.5, 1.75, 5., 100.]:
    actual = bet_to_total(spreads, fit, threshold)
    for spread, cutoff in zip(spreads, actual):
        valid = grid[bias_of(spread, grid, fit) > threshold]
        assert cutoff == valid[-1] if len(valid) else np.isnan(cutoff)
boundary = float(bias_of(45., 55., fit))
assert bet_to_total(np.array([45.]), fit, boundary)[0] == 54.5
assert bet_to_total(np.array([]), fit, 1.75).size == 0
print('PASS: brute-force grid, spread signs, no qualifying total, exact equality, and empty inputs.')
for pick in market['picks']:
    print(f"{pick['away']} at {pick['home']}: total {pick['total']}, Bet to {pick['betTo']}")
payload = json.loads(clt._get(clt.AN_SCOREBOARD, {'season': 2026, 'week': 2, 'seasonType': 'reg'}))
game = next(g for g in payload['games'] if g['id'] == 288898)
assert game['status'] == 'complete'
box = game['boxscore']
total = box['total_home_points'] + box['total_away_points']
assert total > 65.5
print(f"Miami vs Florida A&M final: {box['total_home_points']}-{box['total_away_points']}; OVER 65.5 won. Prior published record 10-4 becomes 11-4, 15 settled, 73.3%.")
