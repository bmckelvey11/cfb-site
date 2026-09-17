"""Render one reveal.js HTML deck per SQL-course module."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from learning.sql_course.course_parse import Module, parse_course  # noqa: E402

CDN = "https://cdn.jsdelivr.net/npm/reveal.js@5"
HLJS_CSS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css"
FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400"
    "&family=JetBrains+Mono:wght@400;600&display=swap"
)
PART_HEAD = re.compile(r"^# Part ([A-D])(?: — (.+))?$")

# Shared tokens: paper page, navy ink, penalty-flag yellow for module tags only,
# turf green for the betting callout. One serif for reading, one mono for SQL.
TOKENS = """
:root {
  --paper: #F7F6F2;
  --ink: #1B2A41;
  --ink-soft: #4A5568;
  --rule: #D7D9D3;
  --flag: #F2C230;
  --turf: #2F6B3B;
  --turf-wash: #E9F0E6;
  --code-bg: #EEF0EC;
  --serif: "Source Serif 4", Georgia, "Times New Roman", serif;
  --mono: "JetBrains Mono", Consolas, "Courier New", monospace;
}
"""

DECK_CSS = TOKENS + """
.reveal-viewport { background: var(--paper); }
.reveal { font-family: var(--serif); font-size: 26px; color: var(--ink); }
.reveal .slides { text-align: left; }
.reveal .slides > section { padding: 0; }
.reveal .slides > section > * { max-width: 40em; }
.reveal .slides > section > pre { max-width: none; }
.reveal h1, .reveal h2, .reveal h3 {
  font-family: var(--serif); color: var(--ink); text-transform: none;
  letter-spacing: -0.01em; line-height: 1.15; margin: 0 0 0.7em;
}
.reveal h1 { font-size: 2.2em; font-weight: 700; }
.reveal h2 { font-size: 1.45em; font-weight: 700;
  padding-bottom: 0.35em; border-bottom: 2px solid var(--ink); }
.reveal h2 code { font-size: 0.85em; }
.reveal p { line-height: 1.55; margin: 0 0 0.8em; }
.reveal ul, .reveal ol { display: block; margin: 0 0 0 1.1em; }
.reveal li { line-height: 1.5; margin-bottom: 0.45em; }
.reveal strong { font-weight: 600; }
.reveal a { color: var(--turf); text-decoration: underline; text-underline-offset: 0.15em; }
.reveal a:hover { color: var(--ink); }

/* inline and block code */
.reveal code { font-family: var(--mono); font-size: 0.82em;
  background: var(--code-bg); padding: 0.05em 0.3em; border-radius: 3px; }
.reveal pre { width: 100%; max-width: none; margin: 0; font-size: 0.66em;
  box-shadow: none; }
.reveal pre code { display: block; padding: 0.9em 1.1em; max-height: 560px;
  overflow: auto; background: var(--code-bg); border-left: 4px solid var(--ink);
  line-height: 1.5; border-radius: 0; }
.reveal .hljs { background: var(--code-bg); color: var(--ink); }
.reveal .hljs-keyword, .reveal .hljs-built_in { color: #8A3B12; }
.reveal .hljs-string { color: var(--turf); }
.reveal .hljs-number { color: #1F4E9E; }
.reveal .hljs-comment { color: var(--ink-soft); font-style: italic; }

/* tables (Standard vs DuckDB dialect) */
.reveal table { font-size: 0.85em; border-collapse: collapse; margin: 0; }
.reveal th, .reveal td { text-align: left; padding: 0.4em 0.8em; vertical-align: top;
  border-bottom: 1px solid var(--rule); }
.reveal th { font-weight: 600; border-bottom: 2px solid var(--ink); }
.reveal tr:last-child td { border-bottom: none; }

/* betting callout */
.reveal blockquote { width: 100%; margin: 0; padding: 0.9em 1.2em; font-style: normal;
  background: var(--turf-wash); border-left: 5px solid var(--turf); box-shadow: none;
  font-size: 1em; }
.reveal blockquote p { margin: 0; }
.reveal blockquote strong { color: var(--turf); }

/* title slide */
.reveal section.title .code {
  display: inline-block; background: var(--flag); color: var(--ink);
  font-weight: 700; font-size: 1.1em; padding: 0.1em 0.5em; margin-bottom: 0.9em; }
.reveal section.title h1 { border: none; margin-bottom: 0.5em; }
.reveal section.title p { font-size: 1.05em; color: var(--ink-soft); max-width: 30em; }
.reveal section.title p.dialect { font-style: italic; }

/* persistent footer */
.deck-footer { position: absolute; left: 0; right: 0; bottom: 0; z-index: 20;
  display: flex; align-items: center; gap: 1.2em; padding: 0.55em 1.6em;
  font-family: var(--serif); font-size: 15px; color: var(--ink-soft);
  border-top: 1px solid var(--rule); background: var(--paper); }
.deck-footer .tag { background: var(--flag); color: var(--ink); font-weight: 700;
  padding: 0 0.45em; }
.deck-footer .module { color: var(--ink); font-weight: 600; }
.deck-footer a { color: var(--ink-soft); text-decoration: none; }
.deck-footer a:hover { color: var(--ink); text-decoration: underline; }
.deck-footer .spacer { flex: 1; }
.reveal .slide-number { position: static; background: none; color: var(--ink-soft);
  font-family: var(--serif); font-size: 15px; padding: 0; }
.reveal .controls { color: var(--ink); bottom: 48px; }
.reveal .progress { color: var(--turf); height: 3px; }
@media (prefers-reduced-motion: reduce) {
  .reveal .slides section { transition: none !important; }
}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="{fonts}">
<link rel="stylesheet" href="{cdn}/dist/reveal.css">
<link rel="stylesheet" href="{cdn}/dist/theme/white.css">
<link rel="stylesheet" href="{hljs}">
<style>{css}</style>
</head>
<body>
<div class="reveal">
<div class="slides">
{slides}
</div>
<footer class="deck-footer">
<span class="tag">{code}</span>
<span class="module">{module_title}</span>
<a href="index.html">Course index</a>
{next_link}
<span class="spacer"></span>
</footer>
</div>
<script src="{cdn}/dist/reveal.js"></script>
<script src="{cdn}/plugin/markdown/markdown.js"></script>
<script src="{cdn}/plugin/highlight/highlight.js"></script>
<script>
Reveal.initialize({{
  hash: true, center: false, width: 1280, height: 800, margin: 0.07,
  slideNumber: 'c/t', transition: 'fade', transitionSpeed: 'fast',
  plugins: [RevealMarkdown, RevealHighlight]
}}).then(function () {{
  var n = document.querySelector('.reveal .slide-number');
  if (n) document.querySelector('.deck-footer').appendChild(n);
}});
</script>
</body>
</html>
"""

INDEX_CSS = TOKENS + """
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--serif); font-size: 18px; line-height: 1.55; }
main { max-width: 44em; margin: 0 auto; padding: 4rem 1.5rem 5rem; }
header h1 { font-size: 2.6rem; font-weight: 700; line-height: 1.1; letter-spacing: -0.01em;
  margin: 0 0 1rem; max-width: 12em; }
header p { font-size: 1.1rem; color: var(--ink-soft); max-width: 34em; margin: 0; }
header code { font-family: var(--mono); font-size: 0.85em; }
header .start { display: inline-block; margin-top: 1.6rem; padding: 0.55em 1.1em;
  background: var(--ink); color: var(--paper); text-decoration: none; font-weight: 600; }
header .start:hover, header .start:focus-visible { background: var(--turf); }
section.part { margin-top: 3.2rem; padding-top: 1.4rem; border-top: 2px solid var(--ink); }
section.part h2 { font-size: 1.5rem; margin: 0 0 0.3rem; }
section.part .focus { margin: 0; color: var(--ink-soft); }
section.part .dialect { margin: 0.2rem 0 1.2rem; font-style: italic; color: var(--ink-soft); }
ul.modules { list-style: none; margin: 0; padding: 0; }
ul.modules li { display: flex; align-items: baseline; gap: 1rem;
  padding: 0.55rem 0; border-bottom: 1px solid var(--rule); }
ul.modules li:last-child { border-bottom: none; }
ul.modules .tag { flex: 0 0 3.2em; text-align: center; background: var(--flag);
  font-weight: 700; padding: 0.05em 0; }
ul.modules a { color: var(--ink); text-decoration: none; }
ul.modules a:hover, ul.modules a:focus-visible { color: var(--turf); text-decoration: underline;
  text-underline-offset: 0.15em; }
@media (max-width: 600px) {
  body { font-size: 17px; }
  main { padding: 2.5rem 1rem 4rem; }
  header h1 { font-size: 2.1rem; }
}
"""

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The CFB Warehouse SQL Course</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="{fonts}">
<style>{css}</style>
</head>
<body>
<main>
<header>
<h1>The CFB Warehouse SQL Course</h1>
<p>Work top to bottom; each module assumes the ones before it. Read the concepts,
run the worked solution against <code>md:cfb</code>, confirm the row count, then
attempt the exercises from the hints alone.</p>
<a class="start" href="{first}.html">Start with {first}</a>
</header>
{parts}
</main>
</body>
</html>
"""

PART = """<section class="part">
<h2>Part {letter}{name}</h2>
<p class="focus">{focus}</p>
<p class="dialect">{dialect}</p>
<ul class="modules">
{links}
</ul>
</section>"""


def _escape_textarea(text: str) -> str:
    return text.replace("</textarea>", "&lt;/textarea&gt;")


def _section(markdown: str, cls: str = "") -> str:
    body = markdown.strip()
    if body.endswith("\n---"):  # stray horizontal rule at the end of Part D
        body = body[:-3].rstrip()
    body = _escape_textarea(body)
    attrs = f'<!-- .slide: class="{cls}" -->\n' if cls else ""
    return (
        '<section data-markdown>\n'
        '<textarea data-template>\n'
        f"{attrs}{body}\n"
        "</textarea>\n"
        "</section>"
    )


def _title_slide(m: Module) -> str:
    md = f'<p class="code">{m.code}</p>\n\n# {m.title}'
    if m.part_focus:
        md += f"\n\n{m.part_focus}"
    if m.part_dialect:
        md += f'\n\n<p class="dialect">{m.part_dialect}</p>'
    return _section(md, cls="title")


def _deck(m: Module, parts: list[str], next_module: Module | None) -> str:
    next_link = (
        f'<a href="{next_module.code}.html">Next: {next_module.code} {next_module.title}</a>'
        if next_module
        else ""
    )
    return TEMPLATE.format(
        title=f"{m.code} — {m.title}",
        cdn=CDN,
        hljs=HLJS_CSS,
        fonts=FONTS,
        css=DECK_CSS,
        code=m.code,
        module_title=m.title,
        next_link=next_link,
        slides="\n".join(parts),
    )


def render_module(m: Module, next_module: Module | None = None) -> str:
    parts: list[str] = [_title_slide(m)]

    if m.code == "D":
        for heading, body in m.reference_sections:
            parts.append(_section(f"## {heading}\n\n{body}"))
        return _deck(m, parts, next_module)

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
    return _deck(m, parts, next_module)


def parse_part_names(course_text: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in course_text.splitlines():
        pm = PART_HEAD.match(line)
        if pm:
            names[pm.group(1)] = (pm.group(2) or "").strip()
    return names


def render_index(modules: list[Module], part_names: dict[str, str] | None = None) -> str:
    part_names = part_names or {}
    blocks: list[str] = []
    for letter in sorted({m.part for m in modules}):
        mods = [m for m in modules if m.part == letter]
        links = "\n".join(
            f'<li><span class="tag">{m.code}</span><a href="{m.code}.html">{m.title}</a></li>'
            for m in mods
        )
        name = part_names.get(letter, "")
        blocks.append(
            PART.format(
                letter=letter,
                name=f" — {name}" if name else "",
                focus=mods[0].part_focus,
                dialect=mods[0].part_dialect,
                links=links,
            )
        )
    return INDEX.format(
        fonts=FONTS, css=INDEX_CSS, first=modules[0].code, parts="\n".join(blocks)
    )


def build_all(course_path: Path, out_dir: Path) -> list[Path]:
    text = course_path.read_text(encoding="utf-8")
    modules = parse_course(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, m in enumerate(modules):
        nxt = modules[i + 1] if i + 1 < len(modules) else None
        dest = out_dir / f"{m.code}.html"
        dest.write_text(render_module(m, nxt), encoding="utf-8")
        paths.append(dest)
    index = out_dir / "index.html"
    index.write_text(render_index(modules, parse_part_names(text)), encoding="utf-8")
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
