from pathlib import Path

text = Path(r"c:\Users\mckel\dev\cfb\docs\feature-evaluation-framework.md").read_text(
    encoding="utf-8"
)
raw = Path(r"c:\Users\mckel\dev\cfb\docs\feature-evaluation-framework.md").read_bytes()

print("backslash-begin", raw.count(b"\\begin"))
print("backslash-text", raw.count(b"\\text"))
print("backslash-neq", raw.count(b"\\neq"))
print("backslash-beta", raw.count(b"\\beta"))
print("backslash-quad", raw.count(b"\\quad"))
print(
    "CRLF",
    raw.count(b"\r\n"),
    "LF-only newlines",
    raw.count(b"\n") - raw.count(b"\r\n"),
)

# strip fenced code
import re

stripped = re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.S | re.M)
stripped = re.sub(r"`[^`\n]*`", "", stripped)

# display blocks
display = list(re.finditer(r"\$\$(.+?)\$\$", stripped, flags=re.S))
print("display $$ blocks", len(display))

# remove display before counting inline
no_display = re.sub(r"\$\$.+?\$\$", "", stripped, flags=re.S)
# inline $...$
inline = list(
    re.finditer(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", no_display, flags=re.S)
)
print("inline $ pairs", len(inline))

# leftover single $
leftover = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", "", no_display, flags=re.S)
orphans = [i for i, ch in enumerate(leftover) if ch == "$"]
print("orphan $ after pairing", len(orphans))
if orphans:
    for i in orphans[:10]:
        print("orphan context:", repr(leftover[max(0, i - 40) : i + 40]))

# line-by-line $ parity outside $$
in_display = False
odd_lines = []
for n, line in enumerate(text.splitlines(), 1):
    if line.strip() == "$$":
        in_display = not in_display
        continue
    if in_display:
        continue
    # ignore code fences roughly
    if line.strip().startswith("```"):
        continue
    count = 0
    i = 0
    while i < len(line):
        if line[i] == "$":
            count += 1
        i += 1
    if count % 2:
        odd_lines.append((n, count, line[:120]))
print("odd-$ lines outside $$", len(odd_lines))
for item in odd_lines[:20]:
    print(item)

print("first display head:")
print(display[0].group(0)[:200] if display else "NONE")
