"""Generate a single-file HTML summary of cfb.duckdb: schemas, tables, columns, 3 sample rows."""
import html
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parents[1] / "data" / "cfb.duckdb"
OUT = Path(__file__).resolve().parents[1] / "docs" / "db-summary.html"
CELL = 160  # ponytail: hard truncate; raw.payload holds whole JSON API responses

LAYERS = {
    "raw": "JSON landing zone. 119 of 120 tables share one signature "
           "(payload, season, season_type, source_file, week); payload is the undecoded API response.",
    "stg": "Typed shred of raw. One table per endpoint plus exploded child tables for nested lists.",
    "core": "Conformed dimensions and facts built from stg.",
    "meta": "Warehouse bookkeeping: load reports and version.",
}


def trunc(s):
    s = "NULL" if s is None else str(s)
    return s[:CELL] + " …" if len(s) > CELL else s


def main():
    con = duckdb.connect(str(DB), read_only=True)

    cols = {}
    for sch, tbl, col, typ in con.sql(
        "select table_schema, table_name, column_name, data_type from information_schema.columns "
        "order by table_schema, table_name, ordinal_position"
    ).fetchall():
        cols.setdefault((sch, tbl), []).append((col, typ))

    sizes = {
        (s, t): (n, c)
        for s, t, n, c in con.sql(
            "select schema_name, table_name, estimated_size, column_count from duckdb_tables()"
        ).fetchall()
    }

    parts = []
    rendered = 0
    for sch in ("core", "stg", "raw", "meta"):
        tables = sorted(t for (s, t) in cols if s == sch)
        if not tables:
            continue
        parts.append(f'<section><h2>{html.escape(sch)} <span class="cnt">{len(tables)} tables</span></h2>')
        parts.append(f'<p class="layer">{html.escape(LAYERS.get(sch, ""))}</p>')
        for tbl in tables:
            rendered += 1
            nrows, ncols = sizes.get((sch, tbl), ("?", len(cols[(sch, tbl)])))
            parts.append(
                f'<details data-name="{html.escape(sch + "." + tbl)}"><summary>'
                f'<code>{html.escape(sch)}.{html.escape(tbl)}</code>'
                f'<span class="cnt">{ncols} cols · ~{nrows:,} rows</span></summary>'
                if isinstance(nrows, int)
                else f'<details data-name="{html.escape(sch + "." + tbl)}"><summary>'
                     f'<code>{html.escape(sch)}.{html.escape(tbl)}</code>'
                     f'<span class="cnt">{ncols} cols</span></summary>'
            )
            parts.append('<table class="cols"><thead><tr><th>column</th><th>type</th></tr></thead><tbody>')
            for col, typ in cols[(sch, tbl)]:
                parts.append(f"<tr><td><code>{html.escape(col)}</code></td><td>{html.escape(trunc(typ))}</td></tr>")
            parts.append("</tbody></table>")

            try:
                try:
                    rel = con.sql(f'select * from "{sch}"."{tbl}" limit 3')
                    head = [d[0] for d in rel.description]
                    rows = rel.fetchall()
                except duckdb.OutOfMemoryException:
                    # ponytail: raw.payload can be a multi-MB JSON blob; truncate in SQL instead
                    proj = ", ".join(
                        f'substr(CAST("{c}" AS VARCHAR), 1, {CELL + 1}) AS "{c}"' for c, _ in cols[(sch, tbl)]
                    )
                    rel = con.sql(f'select {proj} from "{sch}"."{tbl}" limit 3')
                    head = [d[0] for d in rel.description]
                    rows = rel.fetchall()
                if rows:
                    parts.append('<div class="scroll"><table class="sample"><thead><tr>')
                    parts.extend(f"<th>{html.escape(h)}</th>" for h in head)
                    parts.append("</tr></thead><tbody>")
                    for r in rows:
                        parts.append("<tr>" + "".join(f"<td>{html.escape(trunc(v))}</td>" for v in r) + "</tr>")
                    parts.append("</tbody></table></div>")
                else:
                    parts.append('<p class="empty">no rows</p>')
            except Exception as exc:  # noqa: BLE001 - surface it in the doc, never swallow
                parts.append(f'<p class="err">sample failed: {html.escape(str(exc))}</p>')
            parts.append("</details>")
        parts.append("</section>")

    assert rendered == len(cols), f"rendered {rendered} tables, expected {len(cols)}"

    doc = TEMPLATE.format(
        ntab=len(cols),
        ncol=sum(len(v) for v in cols.values()),
        db=html.escape(str(DB)),
        body="\n".join(parts),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, {rendered} tables)")


TEMPLATE = """<!doctype html>
<meta charset="utf-8"><title>cfb.duckdb summary</title>
<style>
:root {{ color-scheme: light dark; --fg:#111; --bg:#fff; --mut:#666; --line:#ddd; --acc:#0b5; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg:#e6e6e6; --bg:#141414; --mut:#999; --line:#333; }} }}
body {{ font:14px/1.5 ui-sans-serif,system-ui,sans-serif; color:var(--fg); background:var(--bg);
        margin:0 auto; padding:2rem 1.5rem; max-width:1100px; }}
h1 {{ margin:0 0 .25rem; }} h2 {{ margin:2.5rem 0 .25rem; }}
.sub, .layer {{ color:var(--mut); margin:.25rem 0 1rem; }}
.cnt {{ color:var(--mut); font-weight:400; font-size:.85em; margin-left:.6rem; }}
#q {{ width:100%; padding:.6rem .8rem; font:inherit; border:1px solid var(--line);
      border-radius:6px; background:var(--bg); color:var(--fg); margin:1rem 0; }}
details {{ border-bottom:1px solid var(--line); padding:.4rem 0; }}
summary {{ cursor:pointer; }} summary code {{ font-weight:600; }}
table {{ border-collapse:collapse; font-size:12px; margin:.6rem 0; }}
th,td {{ border:1px solid var(--line); padding:.25rem .5rem; text-align:left;
         vertical-align:top; white-space:pre-wrap; }}
th {{ background:color-mix(in srgb, var(--fg) 7%, transparent); }}
.cols {{ min-width:420px; }}
.scroll {{ overflow-x:auto; max-width:100%; }}
.sample td {{ max-width:360px; }}
.empty {{ color:var(--mut); }} .err {{ color:#c33; }}
</style>
<h1>cfb.duckdb</h1>
<p class="sub">{ntab} tables · {ncol} columns · source <code>{db}</code>. Each table shows its
columns and up to 3 sample rows (cell values truncated).</p>
<input id="q" type="search" placeholder="filter tables… (e.g. games, stg.lines)">
{body}
<script>
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const v = q.value.toLowerCase();
  for (const d of document.querySelectorAll('details'))
    d.hidden = v && !d.dataset.name.toLowerCase().includes(v);
  for (const s of document.querySelectorAll('section'))
    s.hidden = ![...s.querySelectorAll('details')].some(d => !d.hidden);
}});
</script>
"""

if __name__ == "__main__":
    sys.exit(main())
