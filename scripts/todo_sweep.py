"""TODO-system sweeper/linter — capture, check, verify for the root TODO.md queue.

Contract: docs/methodology/todo-system.md. Ported 2026-09-10 from golf-master's
scripts/infra/todo_sweep.py (design there: docs/analysis/todo-system-redesign-2026-07-25.md).

    python scripts/todo_sweep.py sweep            # dry-run: what would land in section 0
    python scripts/todo_sweep.py sweep --apply    # append new todo-block ids under section 0
    python scripts/todo_sweep.py check            # lint ids/links/graduation; exit 1 on violation
    python scripts/todo_sweep.py verify           # run items' verify: commands, report likely-done
    python scripts/todo_sweep.py refs             # list `#sec-*` sections + open `#id` items
    python scripts/todo_sweep.py label            # dry-run: mint missing ids + visible `#id` / `#sec-*` refs
    python scripts/todo_sweep.py label --apply    # write those labels into TODO.md

Pure filesystem + regex + yaml. Never auto-closes an item; verify only reports.

Pointing convention:
- Items: visible backtick `#id` after the checkbox (same slug as `<!-- id: -->`).
- Sections: visible `#sec-*` on the `##` heading (same slug as `<!-- section: -->`).
  Prefer `#sec-totals` over `§3` — section numbers can renumber; slugs stay put.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# Sources scanned for ```yaml todo: blocks (docs/_private is off-limits, never scanned).
SOURCE_GLOBS = (
    "docs/*.md",
    "docs/superpowers/plans/*.md",
    "docs/superpowers/specs/*.md",
)

YAML_FENCE_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)
ID_COMMENT_RE = re.compile(r"<!--\s*id:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")
SECTION_COMMENT_RE = re.compile(r"<!--\s*section:\s*(sec-[A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")
VERIFY_COMMENT_RE = re.compile(r"<!--\s*verify:\s*(.+?)\s*-->")
POINTER_RE = re.compile(r"`#([A-Za-z0-9][A-Za-z0-9_-]*)`")
# Visible ref immediately after the checkbox: `- [ ] `#slug` **Title**`
VISIBLE_REF_RE = re.compile(r"^- \[([ x])\] `#([A-Za-z0-9][A-Za-z0-9_-]*)`")
TITLE_RE = re.compile(r"\*\*(.+?)\*\*|~~(.+?)~~")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)\)")
SLUG_STOPWORDS = frozenset(
    "a an the and or of to for in on at by with from vs via".split()
)

# Stable section slugs (survive renumbering). Matched against heading text after "## ".
SECTION_SLUG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^0\.\s*NOW", re.I), "sec-now"),
    (re.compile(r"^1\.\s*System maker", re.I), "sec-system-maker"),
    (re.compile(r"^2\.\s*Data", re.I), "sec-data"),
    (re.compile(r"^3\.\s*Totals", re.I), "sec-totals"),
    (re.compile(r"^4\.\s*Over-zero", re.I), "sec-over-zero"),
    (re.compile(r"^5\.\s*Spread", re.I), "sec-spread"),
    (re.compile(r"^6\.\s*Ops", re.I), "sec-ops"),
    (re.compile(r"^7\.\s*Housekeeping", re.I), "sec-housekeeping"),
    (re.compile(r"^Recently completed", re.I), "sec-recent"),
)

# Soft WIP for `#sec-now` / §0 (warn-only in check; see todo-system.md).
SECTION0_WIP_SOFT_CAP = 8


@dataclass
class DocTodo:
    id: str
    text: str
    status: str
    priority: str
    source: Path  # relative to root


@dataclass
class TodoItem:
    line_no: int  # 0-based index into TODO.md lines
    line: str
    closed: bool
    section: str
    id: str | None = None
    verify: str | None = None


@dataclass
class TodoSection:
    line_no: int
    line: str
    title: str  # heading text with labels stripped
    id: str | None = None  # sec-* slug


@dataclass
class TodoFile:
    lines: list[str]
    items: list[TodoItem] = field(default_factory=list)
    sections: list[TodoSection] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def find_source_docs(root: Path) -> list[Path]:
    out: list[Path] = []
    for pattern in SOURCE_GLOBS:
        out.extend(root.glob(pattern))
    return sorted(p for p in set(out) if "_private" not in p.parts)


def parse_doc_todos(path: Path, root: Path) -> list[DocTodo]:
    """Extract todo: block entries from one markdown file."""
    text = path.read_text(encoding="utf-8")
    todos: list[DocTodo] = []
    for match in YAML_FENCE_RE.finditer(text):
        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or "todo" not in data:
            continue
        for entry in data["todo"] or []:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            todos.append(
                DocTodo(
                    id=str(entry["id"]),
                    text=str(entry.get("text", "")).strip(),
                    status=str(entry.get("status", "open")),
                    priority=str(entry.get("priority", "")),
                    source=path.relative_to(root),
                )
            )
    return todos


def collect_doc_todos(root: Path) -> list[DocTodo]:
    todos: list[DocTodo] = []
    for doc in find_source_docs(root):
        todos.extend(parse_doc_todos(doc, root))
    return todos


def heading_title(line: str) -> str:
    """Strip labels/comments from a ## heading for display / matching."""
    text = line[3:].strip() if line.startswith("## ") else line.strip()
    text = SECTION_COMMENT_RE.sub("", text)
    text = re.sub(r"`#sec-[A-Za-z0-9_-]+`", "", text)
    return re.sub(r"\s+", " ", text).strip()


def default_section_slug(heading_text: str) -> str | None:
    title = heading_title(f"## {heading_text}" if not heading_text.startswith("## ") else heading_text)
    for pattern, slug in SECTION_SLUG_RULES:
        if pattern.search(title):
            return slug
    return None


def parse_todo_md(root: Path) -> TodoFile:
    lines = (root / "TODO.md").read_text(encoding="utf-8").splitlines()
    tf = TodoFile(lines=lines)
    section = ""
    current: TodoItem | None = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            title = heading_title(line)
            sec_id = None
            sec_m = SECTION_COMMENT_RE.search(line)
            if sec_m:
                sec_id = sec_m.group(1)
            tf.sections.append(TodoSection(line_no=i, line=line, title=title, id=sec_id))
            section = title
            current = None
            continue
        stripped = line.lstrip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            current = TodoItem(
                line_no=i, line=line, closed=stripped.startswith("- [x]"), section=section
            )
            tf.items.append(current)
        elif stripped.startswith("- ") or stripped.startswith("#"):
            current = None
        if current is not None:
            id_m = ID_COMMENT_RE.search(line)
            if id_m and current.id is None:
                current.id = id_m.group(1)
            v_m = VERIFY_COMMENT_RE.search(line)
            if v_m and current.verify is None:
                current.verify = v_m.group(1)
    return tf


def item_title(line: str) -> str:
    m = TITLE_RE.search(line)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def visible_ref_id(line: str) -> str | None:
    m = VISIBLE_REF_RE.match(line.lstrip())
    return m.group(2) if m else None


def visible_section_id(line: str) -> str | None:
    m = re.search(r"`#(sec-[A-Za-z0-9][A-Za-z0-9_-]*)`", line)
    return m.group(1) if m else None


def slugify(title: str, taken: set[str], fallback_line: str = "") -> str:
    """Mint a stable kebab slug from a title; never reuse a taken id."""
    source = title or fallback_line
    # Strip markdown noise so stub lines without **Title** still slugify.
    source = re.sub(r"`[^`]+`", " ", source)
    source = re.sub(r"<!--.*?-->", " ", source)
    source = re.sub(r"^-\s*\[[ x]\]\s*", "", source)
    words: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9]+", source.lower()):
        if raw in SLUG_STOPWORDS and words:
            continue
        words.append(raw)
        if len(words) >= 6:
            break
    base = "-".join(words) if words else "item"
    base = base[:48].rstrip("-")
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def format_open_item(text: str, item_id: str, priority: str = "", source: Path | None = None) -> str:
    """Canonical open-item line: visible `#id` + bold title + HTML id comment."""
    line = f"- [ ] `#{item_id}` **{text}** <!-- id: {item_id} -->"
    if priority:
        line += f" ({priority})"
    if source is not None:
        posix = source.as_posix()
        line += f" — from [{posix}]({posix})"
    return line


def ensure_visible_label(line: str, item_id: str) -> str:
    """Insert or correct the visible `#id` after the checkbox; leave the rest alone."""
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    if stripped.startswith("- [ ]"):
        prefix, rest = "- [ ]", stripped[5:].lstrip()
    elif stripped.startswith("- [x]"):
        prefix, rest = "- [x]", stripped[5:].lstrip()
    else:
        return line
    # Drop a wrong/old visible ref if present.
    if rest.startswith("`#"):
        close = rest.find("`", 2)
        if close != -1:
            rest = rest[close + 1 :].lstrip()
    if f"<!-- id: {item_id} -->" not in line and "<!-- id:" not in line:
        # Insert id comment after title if missing entirely.
        title_m = TITLE_RE.search(rest)
        if title_m:
            end = title_m.end()
            rest = rest[:end] + f" <!-- id: {item_id} -->" + rest[end:]
        else:
            rest = f"<!-- id: {item_id} --> " + rest
    return f"{indent}{prefix} `#{item_id}` {rest}"


def ensure_section_label(line: str, section_id: str) -> str:
    """Append/correct visible `#sec-*` + `<!-- section: -->` on a ## heading."""
    if not line.startswith("## "):
        return line
    body = line[3:]
    body = SECTION_COMMENT_RE.sub("", body)
    body = re.sub(r"\s*`#sec-[A-Za-z0-9_-]+`\s*", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return f"## {body} `#{section_id}` <!-- section: {section_id} -->"


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------

def sweep(root: Path, apply: bool) -> int:
    todo_text = (root / "TODO.md").read_text(encoding="utf-8")
    new = [
        t
        for t in collect_doc_todos(root)
        if t.status == "open" and not re.search(rf"\b{re.escape(t.id)}\b", todo_text)
    ]
    if not new:
        print("sweep: nothing new to promote")
        return 0
    for t in new:
        print(f"sweep: {'appending' if apply else 'would append'} {t.id} (from {t.source})")
    if not apply:
        print("sweep: dry-run — pass --apply to write")
        return 0

    lines = todo_text.splitlines()
    # End of section 0 = line before the next "## " heading after it (skip trailing --- / blanks).
    start = next(i for i, l in enumerate(lines) if l.startswith("## 0."))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
    )
    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() in ("", "---"):
        insert_at -= 1
    additions = [
        format_open_item(t.text, t.id, priority=t.priority, source=t.source) for t in new
    ]
    lines[insert_at:insert_at] = additions
    (root / "TODO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sweep: appended {len(new)} item(s) to TODO.md section 0")
    return 0


# ---------------------------------------------------------------------------
# label — mint missing ids + visible `#id` refs on open items
# ---------------------------------------------------------------------------

def label(root: Path, apply: bool) -> int:
    tf = parse_todo_md(root)
    taken = {i.id for i in tf.items if i.id} | {s.id for s in tf.sections if s.id}
    changes: list[tuple[int, str, str]] = []  # line_no, old, new

    for sec in tf.sections:
        line = tf.lines[sec.line_no]
        section_id = sec.id or default_section_slug(sec.title)
        if not section_id:
            print(f"label: skip heading (no slug rule) line {sec.line_no + 1}: {sec.title[:60]}")
            continue
        if section_id in taken and sec.id != section_id:
            # Collision with an item id — refuse rather than overwrite.
            print(f"label: refuse section `{section_id}` — already taken (line {sec.line_no + 1})")
            continue
        taken.add(section_id)
        new_line = ensure_section_label(line, section_id)
        if new_line != line:
            changes.append((sec.line_no, line, new_line))
            action = "mint+section" if sec.id is None else "section"
            print(f"label: {action} `#{section_id}` (line {sec.line_no + 1})")

    for item in tf.items:
        if item.closed:
            continue
        line = tf.lines[item.line_no]
        item_id = item.id
        if not item_id:
            item_id = slugify(item_title(line), taken, fallback_line=line)
            taken.add(item_id)
        new_line = ensure_visible_label(line, item_id)
        # If we minted a new id, ensure_visible_label already inserted the comment when missing.
        if new_line != line:
            changes.append((item.line_no, line, new_line))
            action = "mint+label" if item.id is None else "label"
            print(f"label: {action} `#{item_id}` (line {item.line_no + 1})")
    if not changes:
        print("label: nothing to do")
        return 0
    if not apply:
        print(f"label: dry-run — {len(changes)} change(s); pass --apply to write")
        return 0
    for line_no, _old, new in changes:
        tf.lines[line_no] = new
    (root / "TODO.md").write_text("\n".join(tf.lines) + "\n", encoding="utf-8")
    print(f"label: wrote {len(changes)} change(s)")
    return 0


# ---------------------------------------------------------------------------
# refs — printable section + open-item index for pointing
# ---------------------------------------------------------------------------

def refs(root: Path) -> int:
    tf = parse_todo_md(root)
    print("## sections")
    if not tf.sections:
        print("(none)")
    else:
        for sec in tf.sections:
            mark = f"#{sec.id}" if sec.id else "#???"
            print(f"{mark:<22}  {sec.title}")
    print()
    open_items = [i for i in tf.items if not i.closed]
    print("## open items")
    if not open_items:
        print("(none)")
        print("refs: 0 open item(s)")
        return 0
    rows: list[tuple[str, str, str]] = []
    for item in open_items:
        sec = item.section
        # Prefer section slug if we can map the title.
        sec_slug = default_section_slug(sec) or ""
        sec_short = f"#{sec_slug}" if sec_slug else sec.split("—")[0].split("–")[0].strip()[:24]
        title = item_title(item.line) or "(no title)"
        if len(title) > 60:
            title = title[:57] + "..."
        rows.append((item.id or "???", sec_short, title))
    id_w = max(len(r[0]) for r in rows) + 1
    sec_w = max(len(r[1]) for r in rows)
    for item_id, sec, title in rows:
        mark = f"#{item_id}"
        print(f"{mark:<{id_w + 1}}  {sec:<{sec_w}}  {title}")
    print(f"refs: {len(tf.sections)} section(s), {len(rows)} open item(s) — point with `#sec-*` / `#id`")
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def check(root: Path) -> int:
    problems: list[str] = []
    tf = parse_todo_md(root)
    doc_todos = collect_doc_todos(root)

    # 1. Duplicate ids: twice in TODO.md, or the same id declared in two different docs.
    seen: dict[str, int] = {}
    for item in tf.items:
        if item.id:
            if item.id in seen:
                problems.append(
                    f"duplicate id in TODO.md: {item.id} (lines {seen[item.id] + 1} and {item.line_no + 1})"
                )
            else:
                seen[item.id] = item.line_no
    doc_seen: dict[str, Path] = {}
    for t in doc_todos:
        if t.id in doc_seen and doc_seen[t.id] != t.source:
            problems.append(f"id {t.id} declared in two docs: {doc_seen[t.id]} and {t.source}")
        doc_seen.setdefault(t.id, t.source)

    # 1b. Section ids — required, unique, sec-* prefix, no collision with item ids.
    sec_seen: dict[str, int] = {}
    for sec in tf.sections:
        if not sec.id:
            problems.append(
                f"section heading missing `<!-- section: sec-* -->` (TODO.md line {sec.line_no + 1}) — run `todo_sweep.py label --apply`"
            )
            continue
        if not sec.id.startswith("sec-"):
            problems.append(
                f"section id `{sec.id}` must start with `sec-` (TODO.md line {sec.line_no + 1})"
            )
        if sec.id in sec_seen:
            problems.append(
                f"duplicate section id `{sec.id}` (lines {sec_seen[sec.id] + 1} and {sec.line_no + 1})"
            )
        else:
            sec_seen[sec.id] = sec.line_no
        if sec.id in seen:
            problems.append(
                f"section id `{sec.id}` collides with item id (TODO.md line {sec.line_no + 1})"
            )
        vis = visible_section_id(sec.line)
        if vis is None:
            problems.append(
                f"section `#{sec.id}` missing visible label (TODO.md line {sec.line_no + 1}) — run `todo_sweep.py label --apply`"
            )
        elif vis != sec.id:
            problems.append(
                f"visible `#{vis}` != section comment `{sec.id}` (TODO.md line {sec.line_no + 1})"
            )

    # 2. Dangling relative links in TODO.md (resolved from repo root).
    for i, line in enumerate(tf.lines):
        for target in MD_LINK_RE.findall(line):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (root / target).exists():
                problems.append(f"dangling link in TODO.md line {i + 1}: {target}")

    # 3. Graduation: closed items still sitting in section 0 / sec-now.
    for item in tf.items:
        in_now = item.section.startswith("0.") or "NOW" in item.section[:20]
        if item.closed and in_now:
            problems.append(
                f"closed item still in section 0 (TODO.md line {item.line_no + 1}) — graduate it"
            )

    # 3b. Soft WIP warn for §0 / #sec-now (warn-only — does not fail check).
    now_open = sum(
        1
        for item in tf.items
        if not item.closed
        and (item.section.startswith("0.") or "NOW" in item.section[:20])
    )
    if now_open > SECTION0_WIP_SOFT_CAP:
        print(
            f"check: WARN §0 / #sec-now has {now_open} open items "
            f"(soft cap {SECTION0_WIP_SOFT_CAP}) — triage before adding more"
        )

    # 4. Pointer lines referencing an id that exists nowhere (items + sections + doc todos).
    known_ids = set(seen) | set(sec_seen) | {t.id for t in doc_todos}
    for i, line in enumerate(tf.lines):
        for ref in POINTER_RE.findall(line):
            if ref not in known_ids:
                problems.append(f"pointer to unknown id `#{ref}` (TODO.md line {i + 1})")

    # 5. Open items must carry an id + a matching visible `#id` label (pointing contract).
    for item in tf.items:
        if item.closed:
            continue
        if not item.id:
            problems.append(
                f"open item missing id (TODO.md line {item.line_no + 1}) — run `todo_sweep.py label --apply`"
            )
            continue
        vis = visible_ref_id(item.line)
        if vis is None:
            problems.append(
                f"open item `#{item.id}` missing visible `#id` label (TODO.md line {item.line_no + 1}) — run `todo_sweep.py label --apply`"
            )
        elif vis != item.id:
            problems.append(
                f"visible `#{vis}` != id comment `{item.id}` (TODO.md line {item.line_no + 1})"
            )

    for p in problems:
        print(f"check: {p}")
    print(f"check: {len(problems)} problem(s)")
    return 1 if problems else 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def verify(root: Path) -> int:
    tf = parse_todo_md(root)
    checkable = [i for i in tf.items if not i.closed and i.verify]
    if not checkable:
        print("verify: no open items carry a verify: command")
        return 0
    likely_done = 0
    for item in checkable:
        result = subprocess.run(
            item.verify, shell=True, cwd=root, capture_output=True, text=True
        )
        label = item.id or f"line {item.line_no + 1}"
        if result.returncode == 0:
            likely_done += 1
            print(f"verify: LIKELY DONE  {label}  ({item.verify})")
        else:
            print(f"verify: still open   {label}")
    print(f"verify: {likely_done}/{len(checkable)} likely done — strike through by hand with a resolution note")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_sweep = sub.add_parser("sweep", help="promote open todo: block ids into TODO.md section 0")
    p_sweep.add_argument("--apply", action="store_true", help="write (default is dry-run)")
    sub.add_parser("check", help="lint ids, links, graduation, pointers, visible labels; exit 1 on violation")
    sub.add_parser("verify", help="run items' verify: commands; report likely-done")
    sub.add_parser("refs", help="list `#sec-*` sections + open `#id` items (for pointing in chat)")
    p_label = sub.add_parser(
        "label", help="mint missing ids + insert visible `#id` / `#sec-*` refs"
    )
    p_label.add_argument("--apply", action="store_true", help="write (default is dry-run)")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sweep":
        return sweep(args.root, apply=args.apply)
    if args.command == "check":
        return check(args.root)
    if args.command == "refs":
        return refs(args.root)
    if args.command == "label":
        return label(args.root, apply=args.apply)
    return verify(args.root)


if __name__ == "__main__":
    sys.exit(main())
