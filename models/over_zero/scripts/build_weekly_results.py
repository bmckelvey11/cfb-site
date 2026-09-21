"""Rebuild the site's settled weekly record from recorded published picks.

Each game is graded at the line of its first publication. Early publications
kept picks inline in app/page.tsx; later ones ship lib/board.json, whose
"Best lines" signal total is the headline line on the board.
Current prices and editable Bet to scenarios never change a recorded result.
Run from repository root with CFB_DATA_ROOT set.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / 'models/over_zero/site'
sys.path.insert(0, str(ROOT / 'models/over_zero/v1'))
from predict_week import _cfbd_token

# These source revisions contain the exact published boards, not every raw signal.
# (week, site revision) in publication order; a game keeps its first published line.
PUBLICATIONS = [(1, '0802db9'), (2, 'a0e0b4e'), (2, '34a34df'), (3, '4f65acb'), (3, '9838f6a')]


def show(revision, path):
    return subprocess.check_output(['git', '-C', str(SITE), 'show', f'{revision}:{path}'], text=True, encoding='utf-8')


def published_picks(revision):
    """(date, away, home, line, book) for every pick the revision published."""
    source = show(revision, 'app/page.tsx')
    match = re.search(r'const picks = (\[.*?\]) as const;', source, re.S)
    if match:
        return [(date, away, home, total, 'DraftKings') for date, _, away, home, total, *_ in ast.literal_eval(match.group(1))]
    board = json.loads(show(revision, 'lib/board.json'))
    return [(p['date'], p['away'], p['home'], p['total'], 'Market') for p in board['views']['Best lines']['picks']]


def grade(total, home_score, away_score):
    margin = home_score + away_score - total
    return margin, 'Win' if margin > 0 else 'Loss' if margin < 0 else 'Push'


def main():
    req = urllib.request.Request('https://api.collegefootballdata.com/games?year=2026&seasonType=regular',
                                 headers={'Authorization': f'Bearer {_cfbd_token()}'})
    with urllib.request.urlopen(req, timeout=60) as response:
        games = json.load(response)
    raw = Path(os.environ['CFB_DATA_ROOT']) / 'processed/over_zero/results'
    raw.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (raw / f'cfbd_games_{stamp}.json').write_text(json.dumps(games), encoding='utf-8')
    settled = []
    recorded = set()
    for week, revision in PUBLICATIONS:
        for date, away, home, total, book in published_picks(revision):
            matches = [g for g in games if g['week'] == week and g['homeTeam'] == home and g['awayTeam'] == away]
            if len(matches) != 1:
                raise ValueError(f'Cannot uniquely match Week {week}: {away} at {home}')
            game = matches[0]
            if game['id'] in recorded:
                continue
            recorded.add(game['id'])
            if not game.get('completed'):
                continue
            if game.get('homePoints') is None or game.get('awayPoints') is None:
                raise ValueError(f'Completed game missing final scores: {game["id"]}')
            margin, result = grade(total, game['homePoints'], game['awayPoints'])
            settled.append({'id': game['id'], 'week': week, 'date': date,
                            'kickoff': game['startDate'], 'away': away, 'home': home,
                            'line': total, 'awayScore': game['awayPoints'], 'homeScore': game['homePoints'],
                            'finalTotal': game['homePoints'] + game['awayPoints'],
                            'margin': margin, 'result': result, 'publication': revision,
                            'book': book})
    assert len({g['id'] for g in settled}) == len(settled)
    weeks = []
    for week in sorted({g['week'] for g in settled}):
        selected = sorted((g for g in settled if g['week'] == week), key=lambda g: g['kickoff'])
        wins = sum(g['result'] == 'Win' for g in selected)
        losses = sum(g['result'] == 'Loss' for g in selected)
        pushes = sum(g['result'] == 'Push' for g in selected)
        weeks.append({'week': week, 'wins': wins, 'losses': losses, 'pushes': pushes, 'games': selected})
        print(f'Week {week}: {wins}-{losses}-{pushes}, {len(selected)} settled')
        for g in selected:
            print(f"  {g['away']} at {g['home']}: {g['awayScore']}-{g['homeScore']}, OVER {g['line']}, margin {g['margin']:+g}, {g['result']}")
    payload = {'season': 2026, 'updatedAt': datetime.now(timezone.utc).isoformat(),
               'basis': 'Published OVER lines; each game graded at its first published signal total. Settled games only. Pushes excluded from hit rate.',
               'weeks': weeks}
    target = SITE / 'lib/weekly-results.json'
    target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {target}')


if __name__ == '__main__':
    main()
