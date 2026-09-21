"""Render a markdown document to .docx through the officecli binary.

    python research/bankroll/scripts/md_to_docx.py <input.md> <output.docx>
    python research/bankroll/scripts/md_to_docx.py --self-check

Exists because the proposal has to be editable in Word, and this machine has no
pandoc and no python-docx. officecli is installed and speaks docx directly, so
this walks the markdown and drives it.

Scope is the subset the proposal actually uses: headings, paragraphs with bold
and inline code, pipe tables, images, bullet and numbered lists, fenced code
blocks. Anything else passes through as body text rather than failing -- a
proposal that renders with one paragraph unstyled beats one that does not build.

Paragraph paths are positional (/body/p[N]) and tables live in their own
sequence (/body/tbl[N]), so both counters are tracked here as blocks are
appended. That is what lets a bold span be applied after the fact by text match
without re-querying the document.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

# Matches the PDF's look rather than Word's defaults: the blank document
# officecli creates has no Heading styles, so sizes are set explicitly.
BODY_PT, BODY_FONT = "11pt", "Calibri"
ACCENT = "2B5D8A"
HEADING = {1: ("20pt", None, "0pt", "10pt"),
           2: ("15pt", ACCENT, "16pt", "6pt"),
           3: ("12.5pt", None, "12pt", "4pt")}

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
NUMBER_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")


def inline(text: str) -> tuple[str, list[str], list[str]]:
    """(plain text, phrases to bold, phrases to set in a mono font)."""
    bolds = [m.group(1) for m in BOLD_RE.finditer(text)]
    codes = [m.group(1) for m in CODE_RE.finditer(text)]
    text = LINK_RE.sub(r"\1", text)
    text = BOLD_RE.sub(r"\1", text)
    text = CODE_RE.sub(r"\1", text)
    return text, bolds, codes


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def csv_cell(v: str) -> str:
    """officecli's table `data` prop: ';' separates rows, ',' separates cells."""
    v = v.replace("—", "-")
    if any(ch in v for ch in ',;"'):
        return '"' + v.replace('"', '""') + '"'
    return v


def blocks(md: str) -> list[tuple]:
    """Markdown -> a flat list of ('kind', payload...) blocks, in document order."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(("code", buf))
        elif ln.startswith("#"):
            level = len(ln) - len(ln.lstrip("#"))
            out.append(("heading", min(level, 3), ln.lstrip("#").strip()))
        elif IMG_RE.match(ln):
            out.append(("image", IMG_RE.match(ln).group(2)))
        elif ln.strip().startswith("|") and i + 1 < len(lines) and set(
                lines[i + 1].replace("|", "").replace(":", "").strip()) <= {"-", " "}:
            rows = [split_row(ln)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(("table", rows))
            continue
        elif ln.strip() in ("---", "***", "___"):
            pass  # a horizontal rule is a markdown affordance, not document content
        elif BULLET_RE.match(ln) or NUMBER_RE.match(ln):
            # a list item runs until a blank line or the next item
            m = BULLET_RE.match(ln) or NUMBER_RE.match(ln)
            marker = "•" if BULLET_RE.match(ln) else f"{m.group(2)}."
            body = (m.group(2) if BULLET_RE.match(ln) else m.group(3))
            depth = len(m.group(1)) // 2
            i += 1
            while (i < len(lines) and lines[i].strip()
                   and not lines[i].startswith(("#", "|", "```"))
                   and not BULLET_RE.match(lines[i]) and not NUMBER_RE.match(lines[i])):
                body += " " + lines[i].strip()
                i += 1
            out.append(("list", marker, body, depth))
            continue
        elif ln.strip():
            buf = [ln.strip()]
            i += 1
            while (i < len(lines) and lines[i].strip()
                   and not lines[i].startswith(("#", "|", "```", "!["))
                   and not BULLET_RE.match(lines[i]) and not NUMBER_RE.match(lines[i])):
                buf.append(lines[i].strip())
                i += 1
            out.append(("para", " ".join(buf)))
            continue
        i += 1
    return out


class Doc:
    """Appends to /body and remembers where things landed."""

    def __init__(self, path: Path, base: Path):
        self.path, self.base = path, base
        self.n_p = self.n_tbl = 0
        self.pending: list[list[str]] = []

    def _run(self, *args: str) -> None:
        # officecli's argument order is <verb> <file> <path> [--prop ...]
        r = subprocess.run(["officecli", args[0], str(self.path), *args[1:]],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"officecli {args[0]} failed: {r.stderr.strip() or r.stdout.strip()}")

    def _batch(self, items: list[dict]) -> None:
        """Many sets in one process. Cell formatting is per cell, so a 6x4 table
        is 24 calls run one at a time and a single call run as a batch."""
        if not items:
            return
        r = subprocess.run(["officecli", "batch", str(self.path), "--commands",
                            json.dumps(items)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"officecli batch failed: {r.stderr.strip() or r.stdout.strip()}")

    def para(self, text: str, **props) -> int:
        text, bolds, codes = inline(text)
        args = ["add", "/body", "--type", "paragraph", "--prop", f"text={text}"]
        for k, v in props.items():
            if v is not None:
                args += ["--prop", f"{k}={v}"]
        self._run(*args)
        self.n_p += 1
        here = f"/body/p[{self.n_p}]"
        for b in dict.fromkeys(bolds):
            self._run("set", here, "--find", b, "--prop", "bold=true")
        for c in dict.fromkeys(codes):
            self._run("set", here, "--find", c, "--prop", "font=Consolas", "--prop", "size=9.5pt")
        return self.n_p

    def table(self, rows: list[list[str]]) -> None:
        # Cells carry inline markdown too. `data=` takes plain text only, so the
        # markers are stripped here and re-applied as cell formatting below --
        # otherwise the table renders a literal **$20,000**.
        marks: list[dict] = []
        plain: list[list[str]] = []
        for ri, row in enumerate(rows, start=1):
            out_row = []
            for ci, cell in enumerate(row, start=1):
                text, bolds, codes = inline(cell)
                out_row.append(text)
                path = f"/body/tbl[{self.n_tbl + 1}]/tr[{ri}]/tc[{ci}]"
                if bolds and text.strip() == bolds[0].strip():
                    marks.append({"command": "set", "path": path, "props": {"bold": "true"}})
                else:
                    marks += [{"command": "set", "path": path,
                               "props": {"find": b, "bold": "true"}}
                              for b in dict.fromkeys(bolds)]
                marks += [{"command": "set", "path": path,
                           "props": {"find": c, "font": "Consolas", "size": "9pt"}}
                          for c in dict.fromkeys(codes)]
            plain.append(out_row)
        rows = plain
        data = ";".join(",".join(csv_cell(c) for c in r) for r in rows)
        self._run("add", "/body", "--type", "table", "--prop", f"data={data}",
                  "--prop", "width=100%", "--prop", "layout=autofit",
                  "--prop", "padding=60",
                  "--prop", "border.horizontal=single;0.5pt;D8DCE3",
                  "--prop", "border.vertical=single;0.5pt;D8DCE3")
        self.n_tbl += 1
        here = f"/body/tbl[{self.n_tbl}]"
        # Text formatting in a docx table is a CELL property -- neither the table
        # nor the row accepts size or bold -- so every cell gets set. 9.5pt is a
        # step down from body text, which is what keeps the wide numeric tables
        # inside the margins.
        self._batch([
            {"command": "set", "path": f"{here}/tr[{r}]/tc[{c}]",
             "props": ({"size": "9.5pt", "bold": "true", "fill": "F3F4F6"} if r == 1
                       else {"size": "9.5pt"})}
            for r in range(1, len(rows) + 1) for c in range(1, len(rows[r - 1]) + 1)])
        self._batch(marks)
        self.para("", size="4pt")

    def image(self, src: str, width: str = "6.3in") -> None:
        p = (self.base / src).resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        self.para("", align="center")
        self._run("add", f"/body/p[{self.n_p}]", "--type", "picture",
                  "--prop", f"src={p}", "--prop", f"width={width}",
                  "--prop", "alt=Weekly profit and loss, rest of the 2026 season")


def convert(md_path: Path, out: Path) -> Path:
    md = md_path.read_text(encoding="utf-8")
    out.unlink(missing_ok=True)
    subprocess.run(["officecli", "create", str(out)], capture_output=True, text=True, check=True)
    doc = Doc(out, md_path.parent)
    subprocess.run(["officecli", "open", str(out)], capture_output=True, text=True)
    try:
        doc._run("set", "/", "--prop", f"docDefaults.font={BODY_FONT}",
                 "--prop", f"docDefaults.fontSize={BODY_PT}")
        for blk in blocks(md):
            kind = blk[0]
            if kind == "heading":
                size, color, before, after = HEADING[blk[1]]
                doc.para(blk[2], size=size, bold="true", color=color,
                         spaceBefore=before, spaceAfter=after)
            elif kind == "para":
                doc.para(blk[1], size=BODY_PT, spaceAfter="8pt", lineSpacing="1.15x")
            elif kind == "list":
                doc.para(f"{blk[1]}  {blk[2]}", size=BODY_PT, spaceAfter="4pt",
                         indent=f"{0.25 + 0.25 * blk[3]}in", lineSpacing="1.15x")
            elif kind == "code":
                for line in blk[1]:
                    doc.para(line, font="Consolas", size="8.5pt", spaceAfter="0pt")
                doc.para("", size="6pt")
            elif kind == "table":
                doc.table(blk[1])
            elif kind == "image":
                doc.image(blk[1])
        doc._run("add", "/", "--type", "footer", "--prop", "type=default",
                 "--prop", "size=9pt", "--prop", "text=Page ", "--prop", "field=page")
    finally:
        subprocess.run(["officecli", "save", str(out)], capture_output=True, text=True)
        subprocess.run(["officecli", "close", str(out)], capture_output=True, text=True)
    return out


def self_check() -> None:
    md = ("# Title\n\nA **bold** word and `code`.\n\n"
          "## Section\n\n| a | b |\n|---|---:|\n| 1 | $2,300 |\n\n"
          "- first item\n- second item\n\n```\nrun this\n```\n")
    assert inline("a **b** c `d`") == ("a b c d", ["b"], ["d"])
    assert inline("see [the doc](x.md)") == ("see the doc", [], [])
    assert csv_cell("$2,300") == '"$2,300"' and csv_cell("ok") == "ok"
    assert csv_cell('say "hi"') == '"say ""hi"""'
    b = blocks(md)
    kinds = [x[0] for x in b]
    assert kinds == ["heading", "para", "heading", "table", "list", "list", "code"], kinds
    assert b[3][1] == [["a", "b"], ["1", "$2,300"]], b[3]
    assert blocks(chr(124)+" **x** "+chr(124)+chr(10)+chr(124)+"---"+chr(124)+chr(10)
                  + chr(124)+" y "+chr(124)+chr(10))[0][1] == [["**x**"], ["y"]]
    # a table's separator row must not leak in as a body paragraph
    assert not any(k == "para" and "---" in str(v) for k, *v in b)

    # officecli keeps a resident on the file for a few seconds after close, so the
    # temp dir can still be locked when the check finishes; the build is what is
    # being verified, not the cleanup.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        src = Path(td) / "t.md"
        src.write_text(md, encoding="utf-8")
        out = convert(src, Path(td) / "t.docx")
        assert out.exists() and out.stat().st_size > 5_000, out.stat().st_size
        txt = subprocess.run(["officecli", "view", str(out), "text"],
                             capture_output=True, text=True).stdout
        for probe in ("Title", "A bold word and code.", "Section", "first item", "run this"):
            assert probe in txt, (probe, txt[:400])
        # view text renders a table as a placeholder, so cells are checked directly
        cells = subprocess.run(["officecli", "get", str(out), "/body/tbl[1]", "--depth", "4"],
                               capture_output=True, text=True).stdout
        assert "$2,300" in cells, cells[:400]
        assert "**" not in cells, cells[:400]
        # markdown markers must not survive into the document
        assert "**" not in txt and "|---" not in txt, txt[:400]
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="input .md")
    ap.add_argument("out", nargs="?", help="output .docx")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    if not (args.source and args.out):
        ap.error("source and out are required")
    print(f"wrote {convert(Path(args.source), Path(args.out))}")


if __name__ == "__main__":
    main()
