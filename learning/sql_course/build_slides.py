"""Render one reveal.js HTML deck per SQL-course module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from learning.sql_course.course_parse import Module, parse_course  # noqa: E402

CDN = "https://cdn.jsdelivr.net/npm/reveal.js@5"
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="{cdn}/dist/reveal.css">
<link rel="stylesheet" href="{cdn}/dist/theme/white.css">
<link rel="stylesheet" href="{cdn}/plugin/highlight/monokai.css">
</head>
<body>
<div class="reveal">
<div class="slides">
{slides}
</div>
</div>
<script src="{cdn}/dist/reveal.js"></script>
<script src="{cdn}/plugin/markdown/markdown.js"></script>
<script src="{cdn}/plugin/highlight/highlight.js"></script>
<script>
Reveal.initialize({{ hash: true, plugins: [RevealMarkdown, RevealHighlight] }});
</script>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CFB SQL Course</title>
</head>
<body>
<h1>CFB SQL Course</h1>
<ul>
{links}
</ul>
</body>
</html>
"""


def _escape_textarea(text: str) -> str:
    return text.replace("</textarea>", "&lt;/textarea&gt;")


def _section(markdown: str) -> str:
    body = _escape_textarea(markdown.strip())
    return (
        '<section data-markdown>\n'
        '<textarea data-template>\n'
        f"{body}\n"
        "</textarea>\n"
        "</section>"
    )


def render_module(m: Module) -> str:
    parts: list[str] = []
    title_md = f"# {m.code} — {m.title}"
    if m.part_focus:
        title_md += f"\n\n{m.part_focus}"
    if m.part_dialect:
        title_md += f"\n\n*{m.part_dialect}*"
    parts.append(_section(title_md))

    if m.code == "D":
        for heading, body in m.reference_sections:
            parts.append(_section(f"## {heading}\n\n{body}"))
        return TEMPLATE.format(title=f"{m.code} — {m.title}", cdn=CDN, slides="\n".join(parts))

    if m.dialect_table:
        parts.append(_section(f"## Standard → DuckDB\n\n{m.dialect_table}"))
    if m.goals:
        bullets = "\n".join(f"- {g}" for g in m.goals)
        parts.append(_section(f"## Learning goals\n\n{bullets}"))
    for para in m.concepts:
        parts.append(_section(para))
    if m.worked is not None:
        sql = m.worked.sql.rstrip()
        parts.append(_section(f"## Worked solution\n\n```sql\n{sql}\n```"))
    if m.check_yourself:
        parts.append(_section(f"## Check yourself\n\n{m.check_yourself}"))
    if m.mistakes:
        bullets = "\n".join(f"- {x}" for x in m.mistakes)
        parts.append(_section(f"## Common mistakes\n\n{bullets}"))
    if m.why_betting:
        parts.append(_section(m.why_betting))
    return TEMPLATE.format(title=f"{m.code} — {m.title}", cdn=CDN, slides="\n".join(parts))


def render_index(modules: list[Module]) -> str:
    links = "\n".join(
        f'<li><a href="{m.code}.html">{m.code} — {m.title}</a></li>' for m in modules
    )
    return INDEX.format(links=links)


def build_all(course_path: Path, out_dir: Path) -> list[Path]:
    modules = parse_course(course_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for m in modules:
        dest = out_dir / f"{m.code}.html"
        dest.write_text(render_module(m), encoding="utf-8")
        paths.append(dest)
    index = out_dir / "index.html"
    index.write_text(render_index(modules), encoding="utf-8")
    paths.append(index)
    return paths


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--course", type=Path, default=here / "cfb_sql_course.md")
    ap.add_argument("--out", type=Path, default=here / "slides")
    args = ap.parse_args()
    paths = build_all(args.course, args.out)
    print(f"wrote {len(paths)} files to {args.out}")


if __name__ == "__main__":
    main()
