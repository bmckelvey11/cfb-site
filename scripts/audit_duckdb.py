"""Audit the CFB DuckDB warehouse: layer completeness, loader reconciliation,
key-type consistency, grain duplicates, coverage holes, dead columns, orphan keys.

Read-only. Writes a markdown report to stdout (or --out).

    python scripts/audit_duckdb.py --out docs/duckdb-audit-2026-09-02.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import DB_PATH  # noqa: E402

# Schemas the warehouse plan (docs/duckdb-warehouse-plan.md) says should exist.
EXPECTED_SCHEMAS = ["raw", "stg", "stg_gql", "core", "meta"]

# Declared grains. Sources: docs/duckdb-core-ddl.md, docs/graphql-schema-draft.md,
# docs/schema-audit.md.
# Column names reflect the 2026-08-31 naming rationalization (id -> gameId/teamId/...,
# GraphQL staging moved to stg_gql), not the pre-rationalization names in the docs.
DECLARED_GRAINS = [
    ("stg.games", ["gameId"]),
    ("stg_gql.game", ["gameId"]),
    ("stg.teams", ["teamId", "season"]),
    ("stg.venues", ["venueId"]),
    ("stg.conferences", ["conferenceId", "season"]),
    ("stg_gql.calendar", ["season", "week", "seasonType"]),
    # Docs declare (gameId, linesProviderId); actual grain needs `period` too.
    ("stg_gql.game_lines", ["gameId", "linesProviderId"]),
    ("stg_gql.game_lines", ["gameId", "linesProviderId", "period"]),
    ("stg_gql.current_teams", ["teamId"]),
    ("stg.lines", ["gameId"]),
]

# Keys whose physical type must agree everywhere, else joins silently cast or break.
KEY_COLUMNS = [
    "game_id", "gameid", "team_id", "teamid",
    "athlete_id", "athleteid", "season", "week", "year",
]

# Columns the loader derives from the source filename, not from the API payload.
# NULL on datasets scraped as one whole-corpus file - by design, not a defect.
PARTITION_COLUMNS = {"season", "week", "season_type", "_source_file"}


def q(con, sql):
    return con.sql(sql).df()


def section(title):
    return "\n## " + title + "\n"


def check_layers(con, args):
    out = [section("1. Layer completeness")]
    df = q(con, "select schema_name, count(*) n from duckdb_tables() group by 1 order by 2 desc")
    live = dict(zip(df.schema_name, df.n))
    nviews = q(con, "select count(*) n from duckdb_views() where not internal").n[0]
    out.append("| schema | tables | status |")
    out.append("|---|---:|---|")
    for s in EXPECTED_SCHEMAS:
        n = int(live.get(s, 0))
        out.append("| `%s` | %d | %s |" % (s, n, "ok" if n else "**MISSING**"))
    for s in sorted(set(live) - set(EXPECTED_SCHEMAS)):
        out.append("| `%s` | %d | undocumented |" % (s, live[s]))
    out.append("\nViews: %d. Total tables: %d." % (nviews, int(df.n.sum())))
    return out


def check_load_report(con, args):
    out = [section("2. Loader reconciliation (`meta.load_report` vs live tables)")]
    df = q(con, """
        select r.schema, r.name, r.rows as reported_rows, t.estimated_size as live_rows,
               r.files, r.error, r.loaded_at
        from meta.load_report r
        left join duckdb_tables() t
          on t.schema_name = r.schema and t.table_name = r.name
    """)
    missing = df[df.live_rows.isna()]
    mismatch = df[(~df.live_rows.isna()) & (df.reported_rows != df.live_rows)]
    errors = df[df.error.notna()]
    out.append("- Report rows: %d; loaded_at range: %s .. %s" % (len(df), df.loaded_at.min(), df.loaded_at.max()))
    out.append("- Reported tables missing from DB: **%d**" % len(missing))
    out.append("- Row-count mismatches (report vs live): **%d**" % len(mismatch))
    out.append("- Loader-recorded errors: **%d**" % len(errors))
    for d, label in ((missing, "missing"), (mismatch, "mismatch"), (errors, "error")):
        if len(d):
            out.append("\n<details><summary>%s (%d)</summary>\n" % (label, len(d)))
            out.append(d.head(50).to_markdown(index=False))
            out.append("\n</details>")
    return out


def check_parity(con, args):
    out = [section("3. raw to stg parity")]
    raw = q(con, "select table_name, estimated_size from duckdb_tables() where schema_name='raw'")
    stg = q(con, "select table_name, estimated_size from duckdb_tables() where schema_name='stg'")
    rmap = dict(zip(raw.table_name, raw.estimated_size))
    smap = dict(zip(stg.table_name, stg.estimated_size))
    stg_only = sorted(set(smap) - set(rmap))
    raw_only = sorted(set(rmap) - set(smap))
    diff = [(t, rmap[t], smap[t]) for t in sorted(set(rmap) & set(smap)) if rmap[t] != smap[t]]
    out.append("- `raw` tables: %d; `stg` tables: %d" % (len(rmap), len(smap)))
    out.append("- stg with no same-named raw parent: **%d**" % len(stg_only))
    out.append("- raw with no stg child: **%d**" % len(raw_only))
    out.append("- same-named pairs with differing row counts: **%d**" % len(diff))
    if raw_only:
        out.append("\nraw-only: " + ", ".join("`%s`" % t for t in raw_only))
    if stg_only:
        out.append("\n<details><summary>stg-only (%d)</summary>\n" % len(stg_only))
        out.append("\n".join("- `stg.%s` (%s rows)" % (t, format(int(smap[t]), ",")) for t in stg_only))
        out.append("\n</details>")
    if diff:
        out.append("\n| table | raw rows | stg rows |")
        out.append("|---|---:|---:|")
        for t, r, s in diff[:40]:
            out.append("| `%s` | %s | %s |" % (t, format(int(r), ","), format(int(s), ",")))
    return out


def check_key_types(con, args):
    out = [section("4. Key-column type consistency")]
    inlist = ",".join("'%s'" % c for c in KEY_COLUMNS)
    df = q(con, """
        select lower(column_name) col, data_type, count(*) n,
               string_agg(table_schema || '.' || table_name, ', ') as tbl_list
        from information_schema.columns
        where lower(column_name) in (%s)
        group by 1,2
    """ % inlist)
    bad = df.groupby("col").filter(lambda g: len(g) > 1)
    out.append("Keys carrying more than one physical type: **%d**\n" % bad.col.nunique())
    out.append("| key | type | tables |")
    out.append("|---|---|---:|")
    for _, r in bad.sort_values(["col", "n"], ascending=[True, False]).iterrows():
        out.append("| `%s` | `%s` | %d |" % (r.col, r.data_type, r.n))
    for _, r in bad[bad.data_type == "VARCHAR"].iterrows():
        out.append("\n`%s` typed VARCHAR in: %s" % (r.col, r.tbl_list[:800]))
    return out


def check_grains(con, args):
    out = [section("5. Declared grain vs actual (duplicate keys)")]
    out.append("| table | key | rows | distinct keys | dupes |")
    out.append("|---|---|---:|---:|---:|")
    for tbl, keys in DECLARED_GRAINS:
        cols = ", ".join('"%s"' % k for k in keys)
        try:
            n, d = con.sql("select count(*), count(distinct (%s)) from %s" % (cols, tbl)).fetchone()
        except duckdb.Error as e:
            out.append("| `%s` | %s | - | - | error: %s |" % (tbl, ", ".join(keys), str(e).splitlines()[0][:70]))
            continue
        dup = n - d
        flag = "**%s**" % format(dup, ",") if dup else "0"
        out.append("| `%s` | %s | %s | %s | %s |" % (tbl, ", ".join(keys), format(n, ","), format(d, ","), flag))
    return out


def check_season(con, args):
    out = [section("6. Season/week integrity (documented `_post_wk` season-loss bug)")]
    df = q(con, """
        select table_schema sch, table_name tbl, column_name col
        from information_schema.columns
        where lower(column_name) in ('season','year')
          and table_schema in ('raw','stg','stg_gql')
    """)
    rows = []
    for _, r in df.iterrows():
        try:
            n, nulls, lo, hi = con.sql(
                'select count(*), count(*) filter (where "%s" is null), min("%s"), max("%s") from "%s"."%s"'
                % (r.col, r.col, r.col, r.sch, r.tbl)
            ).fetchone()
        except duckdb.Error:
            continue
        if nulls:
            rows.append(("%s.%s" % (r.sch, r.tbl), r.col, n, nulls, lo, hi))
    partial = [r for r in rows if r[3] < r[2]]
    total = [r for r in rows if r[3] == r[2]]
    out.append("Checked %d season/year columns." % len(df))
    out.append("- **Partially** NULL (real data loss - the `_post_wk` signature): **%d**" % len(partial))
    out.append("- 100%% NULL (column present but never populated by the loader): **%d**" % len(total))
    if partial:
        out.append("\n### Partially NULL (investigate)\n")
        out.append("| table | col | rows | nulls | min | max |")
        out.append("|---|---|---:|---:|---:|---:|")
        for t, c, n, nu, lo, hi in sorted(partial, key=lambda x: -x[3]):
            out.append("| `%s` | `%s` | %s | **%s** (%.2f%%) | %s | %s |"
                       % (t, c, format(n, ","), format(nu, ","), 100.0 * nu / n, lo, hi))
    else:
        out.append("\nNo partially-NULL season/year column - the documented postseason bug"
                   " does not reproduce in this build.")
    if total:
        out.append("\n<details><summary>100%% NULL (%d)</summary>\n" % len(total))
        out.append("\n".join("- `%s`.`%s` (%s rows)" % (t, c, format(n, ",")) for t, c, n, _, _, _
                             in sorted(total, key=lambda x: -x[2])))
        out.append("\n</details>")
    return out


def check_coverage(con, args):
    out = [section("7. Season coverage")]
    out.append("| table | season col | seasons | min | max | gaps |")
    out.append("|---|---|---:|---:|---:|---|")
    for t in args.coverage_tables:
        sch, name = t.split(".", 1)
        col = q(con, """select column_name from information_schema.columns
                        where table_schema='%s' and table_name='%s'
                          and lower(column_name) in ('season','year') limit 1""" % (sch, name))
        if col.empty:
            out.append("| `%s` | - | - | - | - | no season column |" % t)
            continue
        c = col.column_name[0]
        df = q(con, 'select "%s" s, count(*) n from "%s"."%s" where "%s" is not null group by 1 order by 1'
               % (c, sch, name, c))
        if df.empty:
            continue
        seasons = [int(x) for x in df.s]
        gaps = [y for y in range(seasons[0], seasons[-1] + 1) if y not in seasons]
        out.append("| `%s` | `%s` | %d | %d | %d | %s |"
                   % (t, c, len(seasons), seasons[0], seasons[-1],
                      ("**" + ", ".join(map(str, gaps)) + "**") if gaps else "-"))
    return out


def check_dead_columns(con, args):
    out = [section("8. Dead columns (100% NULL / single-valued)")]
    tables = q(con, """select schema_name s, table_name t, estimated_size n from duckdb_tables()
                       where estimated_size between 1 and %d order by s, t""" % args.max_rows)
    skipped = int(q(con, "select count(*) n from duckdb_tables() where estimated_size > %d" % args.max_rows).n[0])
    all_null, single = [], []
    for _, r in tables.iterrows():
        try:
            s = con.sql('summarize "%s"."%s"' % (r.s, r.t)).df()
        except duckdb.Error:
            continue
        for _, c in s.iterrows():
            pct = float(c.null_percentage or 0)
            uniq = int(c.approx_unique or 0)
            if pct >= 100:
                all_null.append(("%s.%s" % (r.s, r.t), c.column_name, int(r.n)))
            elif uniq <= 1 and pct == 0:
                single.append(("%s.%s" % (r.s, r.t), c.column_name, int(r.n)))
    out.append("Scanned %d tables (<= %s rows); %d larger tables skipped."
               % (len(tables), format(args.max_rows, ","), skipped))
    out.append("\nLoader-added partition columns (%s) are reported separately: they are NULL "
               "by design on datasets scraped as one whole-corpus file."
               % ", ".join("`%s`" % c for c in sorted(PARTITION_COLUMNS)))
    for data, label in ((all_null, "100% NULL"), (single, "single-valued")):
        payload = [x for x in data if x[1] not in PARTITION_COLUMNS]
        part = [x for x in data if x[1] in PARTITION_COLUMNS]
        out.append("\n- %s: **%d** total = **%d** payload columns + %d partition columns"
                   % (label, len(data), len(payload), len(part)))
        if payload:
            out.append("\n<details><summary>%s, payload columns (%d)</summary>\n" % (label, len(payload)))
            out.append("\n".join("- `%s`.`%s` (%s rows)" % (t, c, format(n, ",")) for t, c, n in payload))
            out.append("\n</details>")
    return out


def check_orphans(con, args):
    out = [section("9. Orphan game ids (vs `stg.games`)")]
    df = q(con, """select table_schema s, table_name t, column_name c
                   from information_schema.columns
                   where lower(column_name) in ('gameid','game_id')
                     and table_schema in ('stg','stg_gql')""")
    out.append("| table | col | rows | orphan game ids | orphan rows |")
    out.append("|---|---|---:|---:|---:|")
    for _, r in df.iterrows():
        sql = ('select count(*), count(distinct case when g."gameId" is null then f."%s" end), '
               'count(*) filter (where g."gameId" is null and f."%s" is not null) '
               'from "%s"."%s" f left join stg.games g '
               'on cast(f."%s" as bigint) = cast(g.gameId as bigint)' % (r.c, r.c, r.s, r.t, r.c))
        try:
            n, oid, orows = con.sql(sql).fetchone()
        except duckdb.Error as e:
            out.append("| `%s.%s` | `%s` | - | - | error: %s |"
                       % (r.s, r.t, r.c, str(e).splitlines()[0][:60]))
            continue
        flag = "**%s**" % format(oid, ",") if oid else "0"
        out.append("| `%s.%s` | `%s` | %s | %s | %s |"
                   % (r.s, r.t, r.c, format(n, ","), flag, format(orows, ",")))
    return out


def check_twin_columns(con, args):
    """Tables carrying BOTH a loader partition column and its payload twin.

    `season`/`week`/`season_type` come from the filename; `year`/`seasonType` come
    from the API payload. Where both exist and the partition one is NULL, anything
    filtering on `season` silently returns nothing.
    """
    out = [section("10. Partition vs payload twin columns (`season`/`year`, `season_type`/`seasonType`)")]
    twins = [("season", "year"), ("season_type", "seasonType")]
    out.append("| table | partition col | non-null | payload twin | non-null | risk |")
    out.append("|---|---|---:|---|---:|---|")
    for part, payload in twins:
        df = q(con, """
            select a.table_schema s, a.table_name t
            from information_schema.columns a
            join information_schema.columns b
              on a.table_schema=b.table_schema and a.table_name=b.table_name
            where lower(a.column_name)=lower('%s') and lower(b.column_name)=lower('%s')
              and a.table_schema in ('stg','stg_gql')
            order by 1,2
        """ % (part, payload))
        for _, r in df.iterrows():
            try:
                n, pn, yn = con.sql(
                    'select count(*), count("%s"), count("%s") from "%s"."%s"'
                    % (part, payload, r.s, r.t)
                ).fetchone()
            except duckdb.Error:
                continue
            if n and pn == 0 and yn > 0:
                risk = "**partition col unusable - filter on payload twin**"
            elif n and pn < n and yn > pn:
                risk = "partition col partially populated"
            else:
                continue
            out.append("| `%s.%s` | `%s` | %s | `%s` | %s | %s |"
                       % (r.s, r.t, part, format(pn, ","), payload, format(yn, ","), risk))
    return out


CHECKS = {
    "layers": check_layers,
    "load_report": check_load_report,
    "parity": check_parity,
    "key_types": check_key_types,
    "grains": check_grains,
    "season": check_season,
    "coverage": check_coverage,
    "dead_columns": check_dead_columns,
    "orphans": check_orphans,
    "twin_columns": check_twin_columns,
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DB_PATH))
    p.add_argument("--out", help="write markdown here instead of stdout")
    p.add_argument("--checks", default="all", help="comma-separated: " + ",".join(CHECKS))
    p.add_argument("--max-rows", type=int, default=200_000,
                   help="dead-column scan skips tables above this row count")
    p.add_argument("--coverage-tables",
                   default="stg.games,stg.game,stg.lines,stg_gql.game_lines,stg.calendar,"
                           "stg.plays,stg.drives,stg.actionnetwork_scoreboard")
    a = p.parse_args()
    a.coverage_tables = [t.strip() for t in a.coverage_tables.split(",") if t.strip()]
    names = list(CHECKS) if a.checks == "all" else [c.strip() for c in a.checks.split(",")]

    con = duckdb.connect(a.db, read_only=True)
    lines = ["# DuckDB warehouse audit - `%s`" % Path(a.db).name, "",
             "Generated by `scripts/audit_duckdb.py` against `%s`." % a.db, ""]
    for n in names:
        print("[audit] " + n, file=sys.stderr)
        lines += CHECKS[n](con, a)
    text = "\n".join(str(x) for x in lines) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print("wrote " + a.out, file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
