"""Export an isolated, dated football research snapshot; never mutate the warehouse."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile
import duckdb

TABLES = [
    'core.fact_game', 'core.fact_game_line', 'core.fact_game_team',
    'core.dim_team', 'core.dim_conference', 'core.dim_lines_provider',
    'core.fact_coach_season', 'core.dim_coach', 'core.fact_team_talent',
    'stg.advanced_game_stats', 'stg.advanced_season_stats', 'stg.ppa_games',
    'stg.returning_production', 'stg.team_stats', 'stg.ratings',
]

def export(source: Path, output: Path, repo: Path, site: Path | None = None):
    output.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = output / f'football-{stamp}.sqlite'
    manifest = {'exported_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'tables': [], 'missing_tables': [], 'source': 'local cfb.duckdb',
                'limitations': [
                    'Snapshot, not a live database. No guaranteed current injury feed.',
                    'Closing lines lack capture times; do not treat them as available earlier.',
                    'Game results and season aggregates include postgame information.',
                    'Pregame analysis must restrict source games to strictly earlier kickoffs.',
                    'Missing betting prices cannot be replaced with assumed -110 without explicit labeling.',
                    'Qualified-pick history contains repeated observations, not one bet per row.',
                    'Selected tables only; raw plays, PFF and some vendor sources are not included.',
                ]}
    with duckdb.connect(str(source), read_only=True) as src, sqlite3.connect(target) as dst:
        src.execute('BEGIN TRANSACTION')
        available = {f'{a}.{b}' for a,b in src.execute('select table_schema,table_name from information_schema.tables').fetchall()}
        for table in TABLES:
            if table not in available:
                manifest['missing_tables'].append(table)
                continue
            name = table.replace('.', '__')
            cols = src.execute(f'DESCRIBE {table}').fetchall()
            definitions = ','.join('"'+c[0].replace('"','""')+'" '+ ('REAL' if any(t in c[1] for t in ['DOUBLE','FLOAT','DECIMAL']) else 'INTEGER' if c[1] in ['INTEGER','BIGINT','BOOLEAN','SMALLINT'] else 'TEXT') for c in cols)
            dst.execute(f'CREATE TABLE "{name}" ({definitions})')
            cursor = src.execute(f'SELECT * FROM {table}')
            count = 0
            while rows := cursor.fetchmany(2000):
                clean = [tuple(v if v is None or isinstance(v,(int,float,str,bytes)) else json.dumps(v,default=str) if isinstance(v,(list,dict)) else str(v) for v in row) for row in rows]
                dst.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" for _ in cols)})',clean)
                count += len(rows)
            manifest['tables'].append({'table': name, 'source': table, 'rows': count, 'columns': [{'name':c[0],'type':c[1]} for c in cols]})
        manifest['game_seasons'] = list(src.execute('select min(season),max(season) from core.fact_game').fetchone())
        src.execute('COMMIT')
    archive = output / f'football-{stamp}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_LZMA) as z:
        z.write(target,'football.sqlite')
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        for rel in ['models/over_zero/docs/MODEL_GUIDE.md','models/over_zero/docs/ROI_HITRATE.md']:
            p=repo/rel
            if p.exists(): z.write(p,p.name)
        for name in ['board.json','weekly-results.json']:
            p=(site or repo/'models/over_zero/site')/'lib'/name
            if p.exists(): z.write(p,name)
        history=source.parent/'processed/over_zero/qualified_picks_history.csv'
        if history.exists(): z.write(history,history.name)
    manifest['archive'] = str(archive)
    manifest['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest['bytes'] = archive.stat().st_size
    (output/'latest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'archive':str(archive),'bytes':manifest['bytes'],'tables':len(manifest['tables']),'rows':sum(t['rows'] for t in manifest['tables']),'game_seasons':manifest['game_seasons']}))
    return manifest

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--site',type=Path,help='Checkout matching the published board')
    args=p.parse_args()
    export(args.source,args.output,Path(__file__).resolve().parents[3],args.site)
