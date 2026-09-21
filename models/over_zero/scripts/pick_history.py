"""Persistent qualified-pick ledger. Run directly to backfill saved outputs."""
from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "cfb_paths.py").is_file():
            return parent
    raise RuntimeError("Cannot locate repository root containing cfb_paths.py")


sys.path.insert(0, str(_repo_root()))
from cfb_paths import DATA_ROOT  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIELDS = ['model', 'run_at', 'lines_as_of', 'view', 'game_id', 'game_date',
          'kickoff_utc', 'away', 'home', 'spread', 'total', 'bias', 'p_over',
          'threshold', 'pick', 'best_total', 'best_book', 'best_odds',
          'playable', 'bet_to', 'source']
KEY = ['model', 'run_at', 'view', 'away', 'home']


def default_path():
    return DATA_ROOT / 'processed/over_zero/qualified_picks_history.csv'


def clean(value):
    if value is None or isinstance(value, float) and not math.isfinite(value):
        return ''
    return str(value)


@contextmanager
def locked(path):
    lock = path.with_suffix('.csv.lock')
    deadline = time.monotonic() + 30
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f'History is locked: {lock}')
            time.sleep(.1)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def append_history(rows, path=None):
    """Merge once per run/view/game, preserving existing observations atomically."""
    path = Path(path) if path is not None else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        existing = []
        if path.exists():
            with path.open(newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != FIELDS:
                    raise ValueError(f'Unexpected history columns: {path}')
                existing = list(reader)
        keyed = {tuple(r[k] for k in KEY): r for r in existing}
        added = 0
        for row in rows:
            record = {k: clean(row.get(k)) for k in FIELDS}
            if record['pick'] != 'OVER':
                continue
            key = tuple(record[k] for k in KEY)
            if any(not part for part in key):
                raise ValueError(f'Missing history identity: {key}')
            if key not in keyed:
                keyed[key] = record
                added += 1
        if added or not path.exists():
            fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(sorted(keyed.values(), key=lambda r: tuple(r[k] for k in KEY)))
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)
    return added, len(keyed)


def slate_rows(records, view, source, threshold=None, as_of=None, model='slate'):
    for r in records:
        if r.get('pick') != 'OVER':
            continue
        kick = datetime.fromisoformat(str(r['kick']).replace('Z', '+00:00')).astimezone(timezone.utc)
        yield dict(model=model, run_at=r['run_at'], lines_as_of=as_of, view=view,
                   game_date=kick.astimezone(ZoneInfo('America/New_York')).date(),
                   kickoff_utc=kick.isoformat(), home=r['home'], away=r['away'],
                   spread=r['spread_fair'], total=r['total_fair'], bias=r['bias_fair'],
                   p_over=r['p_over_fair'], threshold=threshold, pick='OVER',
                   best_total=r['best_total'], best_book=r['best_book'],
                   best_odds=r['best_odds'], playable=r['playable'],
                   bet_to=r.get('bet_to'), source=source)


def record_views(views, run_at, threshold, as_of, model='slate'):
    rows = [r for view, frame in views.items()
            for r in slate_rows(frame.to_dict('records'), view, f'live:{run_at}', threshold,
                                as_of, model)]
    added, total = append_history(rows)
    print(f'Pick history: added {added}; {total} qualified observations -> {default_path()}')


def board_rows(board, source):
    for view, data in board['views'].items():
        for p in data['picks']:
            local = datetime.strptime(f"{board['run_at'][:4]} {p['date']} {p['time'].removesuffix(' ET')}",
                                      '%Y %b %d %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York'))
            yield dict(model='slate', run_at=board['run_at'], lines_as_of=data.get('asOf'),
                       view=view, game_date=local.date(), kickoff_utc=local.astimezone(timezone.utc).isoformat(),
                       home=p['home'], away=p['away'], spread=p['spread'], total=p['total'],
                       bias=p['bias'], p_over=p['probability'] / 100,
                       threshold=board['threshold'], pick='OVER', best_total=p.get('bestTotal'),
                       best_book=p.get('bestBook'), best_odds=p.get('bestOdds'),
                       playable=p.get('playable'), bet_to=p.get('betTo'), source=source)


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def backfill():
    base = default_path().parent
    rows = []
    for path in sorted(base.glob('best_line_slate_*.csv')):
        view = 'DraftKings' if 'draftkings' in path.stem else 'Best lines'
        rows.extend(slate_rows(read_csv(path), view, path.name))
    legacy = sorted((base / 'predictions').glob('*.csv'))
    if (base / 'predictions.csv').exists():
        legacy.append(base / 'predictions.csv')
    for path in legacy:
        for r in read_csv(path):
            rows.append(dict(model='v1', run_at=r['run_at'], view=r['book'], game_id=r['game_id'],
                             game_date=r['game_date'], away=r['away_team'], home=r['home_team'],
                             spread=r['spread'], total=r['total'], bias=r['bias'], p_over=r['p_over'],
                             threshold=r['threshold'], pick=r['pick'], best_book=r['book'], source=path.name))
    site = ROOT / 'models/over_zero/site'
    revisions = subprocess.check_output(['git', '-C', str(site), 'log', '--reverse', '--format=%H',
                                         '--', 'lib/board.json'], text=True).splitlines()
    for revision in revisions:
        raw = subprocess.check_output(['git', '-C', str(site), 'show', f'{revision}:lib/board.json'])
        rows.extend(board_rows(json.loads(raw), f'site:{revision}'))
    board = site / 'lib/board.json'
    if board.exists():
        rows.extend(board_rows(json.loads(board.read_text(encoding='utf-8')), 'site:working-board'))
    # CSV observations retain full precision; fill only missing metadata from published boards.
    merged = {}
    for row in rows:
        key = tuple(clean(row.get(k)) for k in KEY)
        if key not in merged:
            merged[key] = row
        else:
            for field, value in row.items():
                if not clean(merged[key].get(field)):
                    merged[key][field] = value
    added, total = append_history(merged.values())
    print(f'Backfill: added {added}; {total} qualified observations -> {default_path()}')


if __name__ == '__main__':
    backfill()
