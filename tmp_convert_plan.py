import re
from pathlib import Path

src = Path(r"c:\Users\mckel\Downloads\cfb_model_tuning_lab_plan_v2.md")
text = src.read_text(encoding="utf-8")
parts = re.split(r"(^```.*?^```)", text, flags=re.S | re.M)
out = []
for i, part in enumerate(parts):
    if i % 2 == 1:
        out.append(part)
        continue
    part = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1) + "$", part, flags=re.S)
    part = re.sub(r"^[ \t]*\\\[[ \t]*$", "$$", part, flags=re.M)
    part = re.sub(r"^[ \t]*\\\][ \t]*$", "$$", part, flags=re.M)
    out.append(part)
converted = "".join(out)

fence = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
inline = re.compile(r"`[^`\n]*`")
bad = re.compile(r"(?<!\\)\\\(.+?(?<!\\)\\\)|^[ \t]*\\\[[ \t]*$", re.M)
stripped = inline.sub("", fence.sub("", converted))
hits = bad.findall(stripped)
print("bad", len(hits))
if hits[:5]:
    print(hits[:5])
dest = Path(r"c:\Users\mckel\dev\cfb\docs\model-tuning-lab-plan.md")
dest.write_text(converted, encoding="utf-8")
print("wrote", dest, "chars", len(converted))
