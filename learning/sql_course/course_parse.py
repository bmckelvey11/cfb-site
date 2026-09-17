"""Parse the CFB SQL course markdown into Module / Exercise / Block records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MODULE_HEAD = re.compile(r"^## ([A-C]\d) — (.+)$")
PART_D_HEAD = re.compile(r"^# Part D(?: — (.+))?$")
APPENDIX_HEAD = re.compile(r"^# Appendix")
SECTION_HEAD = re.compile(r"^### (.+)$")
REF_HEAD = re.compile(r"^## (.+)$")
EXERCISE = re.compile(r"^(\d+)\. (.+?) \*Hint: (.+)\*$")
SYLLABUS_ROW = re.compile(r"^\| ([A-D]) \| [^|]+ \| ([^|]+) \| ([^|]+) \|$")
ROWS = re.compile(r"^-- rows:\s*(\d[\d,]*)\s*$")
MODULE_FOR_BLOCKS = re.compile(r"^## ([A-D]\d) — ")
CONCEPTS_HEADINGS = {"Concepts", "The idea, then the SQL, then the reading"}


@dataclass
class Block:
    block_id: str
    module: str
    line: int
    dialect: str
    claimed: int | None
    sql: str
    tables: set[str] = field(default_factory=set)
    columns: set[str] = field(default_factory=set)
    missing: list[str] = field(default_factory=list)
    local_rows: int | None = None
    status: str = ""


@dataclass
class Exercise:
    module: str
    number: int
    text: str
    hint: str


@dataclass
class Module:
    code: str
    title: str
    part: str
    goals: list[str]
    dialect_table: str
    concepts: list[str]
    worked: Block | None
    exercises: list[Exercise]
    check_yourself: str
    mistakes: list[str]
    why_betting: str = ""
    part_focus: str = ""
    part_dialect: str = ""
    reference_sections: list[tuple[str, str]] = field(default_factory=list)
    start_line: int = 0


def parse_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    module = "intro"
    per_module: dict[str, int] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = MODULE_FOR_BLOCKS.match(lines[i])
        if m:
            module = m.group(1)
        if lines[i].strip() == "```sql":
            start = i + 1
            j = start
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            body = lines[start:j]
            dialect = body[0].replace("--", "").strip() if body else ""
            rm = ROWS.match(body[1]) if len(body) > 1 else None
            claimed = int(rm.group(1).replace(",", "")) if rm else None
            per_module[module] = per_module.get(module, 0) + 1
            blocks.append(
                Block(
                    f"{module}-{per_module[module]}",
                    module,
                    start + 1,
                    dialect,
                    claimed,
                    "\n".join(body),
                )
            )
            i = j
        i += 1
    for b in blocks:
        if per_module[b.module] == 1:
            b.block_id = b.module
    return blocks


def _parse_syllabus(lines: list[str]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    in_table = False
    for line in lines:
        if line.startswith("### Syllabus at a glance"):
            in_table = True
            continue
        if in_table:
            if line.startswith("#") or (line.startswith("### ") and "Syllabus" not in line):
                break
            m = SYLLABUS_ROW.match(line)
            if m:
                out[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    return out


def _paragraphs(buf: list[str]) -> list[str]:
    paras: list[str] = []
    cur: list[str] = []
    for line in buf:
        if not line.strip():
            if cur:
                paras.append("\n".join(cur).strip())
                cur = []
            continue
        cur.append(line)
    if cur:
        paras.append("\n".join(cur).strip())
    return paras


def parse_course(text: str) -> list[Module]:
    lines = text.splitlines()
    syllabus = _parse_syllabus(lines)
    blocks = parse_blocks(text)
    modules: list[Module] = []
    current: Module | None = None
    section = ""
    concept_buf: list[str] = []
    dialect_lines: list[str] = []
    check_lines: list[str] = []
    ref_heading: str | None = None
    ref_buf: list[str] = []
    in_fence = False

    def flush_concepts() -> None:
        if current is None:
            return
        current.concepts.extend(_paragraphs(concept_buf))
        concept_buf.clear()

    def flush_ref() -> None:
        if current is None or ref_heading is None:
            return
        current.reference_sections.append((ref_heading, "\n".join(ref_buf).strip()))
        ref_buf.clear()

    def finish_section() -> None:
        if current is None:
            return
        if section in CONCEPTS_HEADINGS:
            flush_concepts()
        elif section == "Standard → DuckDB":
            current.dialect_table = "\n".join(dialect_lines).strip()
            dialect_lines.clear()
        elif section == "Check yourself":
            current.check_yourself = "\n".join(check_lines).strip()
            check_lines.clear()

    def flush_module() -> None:
        nonlocal current, section, ref_heading
        if current is None:
            return
        finish_section()
        flush_ref()
        modules.append(current)
        current = None
        section = ""
        ref_heading = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if APPENDIX_HEAD.match(line):
            flush_module()
            break

        mh = MODULE_HEAD.match(line)
        if mh:
            flush_module()
            code, title = mh.group(1), mh.group(2)
            part = code[0]
            focus, dialect = syllabus.get(part, ("", ""))
            current = Module(
                code=code,
                title=title,
                part=part,
                goals=[],
                dialect_table="",
                concepts=[],
                worked=None,
                exercises=[],
                check_yourself="",
                mistakes=[],
                why_betting="",
                part_focus=focus,
                part_dialect=dialect,
                start_line=i + 1,
            )
            section = ""
            continue

        pd = PART_D_HEAD.match(line)
        if pd:
            flush_module()
            title = (pd.group(1) or "SQL best practices").strip()
            focus, dialect = syllabus.get("D", ("", ""))
            current = Module(
                code="D",
                title=title,
                part="D",
                goals=[],
                dialect_table="",
                concepts=[],
                worked=None,
                exercises=[],
                check_yourself="",
                mistakes=[],
                why_betting="",
                part_focus=focus,
                part_dialect=dialect,
                start_line=i + 1,
            )
            section = ""
            continue

        if current is None:
            continue

        if current.code == "D":
            rh = REF_HEAD.match(line)
            if rh and not MODULE_HEAD.match(line):
                flush_ref()
                ref_heading = rh.group(1)
                continue
            if ref_heading is not None:
                ref_buf.append(line)
            continue

        sh = SECTION_HEAD.match(line)
        if sh:
            finish_section()
            section = sh.group(1)
            continue

        if line.startswith("> **Why it matters"):
            current.why_betting = line.strip()
            continue

        if section == "Learning goals" and stripped.startswith("- "):
            current.goals.append(stripped[2:])
        elif section == "Standard → DuckDB":
            dialect_lines.append(line)
        elif section in CONCEPTS_HEADINGS:
            concept_buf.append(line)
        elif section == "Exercises":
            em = EXERCISE.match(line)
            if em:
                current.exercises.append(
                    Exercise(current.code, int(em.group(1)), em.group(2), em.group(3))
                )
        elif section == "Check yourself":
            check_lines.append(line)
        elif section == "Common mistakes" and stripped.startswith("- "):
            current.mistakes.append(stripped[2:])

    flush_module()

    for idx, mod in enumerate(modules):
        end = modules[idx + 1].start_line if idx + 1 < len(modules) else 10**9
        for b in blocks:
            if mod.start_line <= b.line < end:
                mod.worked = b
                break
    return modules
