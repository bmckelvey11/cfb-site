"""Generate docs/pff-endpoint-reference.md from the PFF OpenAPI document.

    python scripts/gen_pff_endpoint_reference.py                 # fetch the live spec
    python scripts/gen_pff_endpoint_reference.py --spec api.json # or use a local copy

The spec is public-read -- no credential -- at https://api.pff.com/openapi.json,
so this needs no PFF subscription. Regenerate after `restish api sync pff`
reports new commands.

Structure only: operation ids, aliases, paths, parameters, types and enums. PFF
authors long prose descriptions in the spec; those are not copied here. Read
them with `restish pff <command> --help`.
"""

import argparse
import json
import re
import urllib.request
from pathlib import Path

SPEC_URL = "https://api.pff.com/openapi.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "docs" / "pff-endpoint-reference.md"

# The order PFF groups them in `restish pff --help`.
TAG_ORDER = ["ref", "team", "player", "facet", "signature", "auth", "meta"]
TAG_BLURB = {
    "ref": "Reference data — leagues, games, the player directory. Start here: these are where team and player ids come from.",
    "team": "Team lists and reports. `team-*` other than `teams`/`team-overview`/`team-summary` are PFF's own `/v2` contract — camelCase, `{columns, rows}` tables, CSV via `--format csv`.",
    "player": "One player's reports. Takes a player id from `ref-players`.",
    "facet": "League-wide leaderboards, one row per player. CSV via `--export true`.",
    "signature": "PFF signature stats. CSV via `--export true`.",
    "auth": "Session and credential.",
    "meta": "The API contract itself.",
}


def load_spec(path: Path | None) -> dict:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    with urllib.request.urlopen(SPEC_URL, timeout=30) as fh:
        return json.load(fh)


def resolve(spec: dict, node: dict) -> dict:
    """Follow a single $ref into components. The spec nests no deeper than one."""
    ref = node.get("$ref")
    if not ref:
        return node
    out = spec
    for part in ref.lstrip("#/").split("/"):
        out = out[part]
    return out


def kebab(name: str) -> str:
    """Restish flag spelling: snake_case and camelCase both become kebab-case."""
    return re.sub(r"(?<=[a-z0-9])([A-Z])", lambda m: "-" + m.group(1), name).replace("_", "-").lower()


def type_of(schema: dict) -> str:
    if not schema:
        return ""
    if "enum" in schema:
        return " \\| ".join(str(v) for v in schema["enum"])
    base = schema.get("type", "")
    bits = [base]
    if "pattern" in schema:
        bits.append(f"`{schema['pattern']}`")
    if "minimum" in schema:
        bits.append(f"min {schema['minimum']}")
    if "default" in schema:
        bits.append(f"default {schema['default']}")
    return ", ".join(b for b in bits if b)


def operations(spec: dict) -> list[dict]:
    ops = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            ops.append({"path": path, "method": method.upper(), **op})
    return ops


def render_op(spec: dict, op: dict) -> list[str]:
    name = op.get("operationId", "?")
    aliases = op.get("x-cli-aliases") or []
    heading = f"### `{name}`"
    if aliases:
        heading += "  ·  alias " + ", ".join(f"`{a}`" for a in aliases)
    lines = [heading, ""]
    lines.append(f"`{op['method']} {op['path']}`")
    if op.get("summary"):
        lines += ["", op["summary"]]

    req = op.get("x-requires-one-of")
    if req:
        alts = " or ".join(
            "(" + " + ".join(f"`{p}`" for p in alt) + ")" for alt in req.get("alternatives", [])
        )
        lines += ["", f"**Requires** {alts} — otherwise `400 invalid_parameter`."]

    params = [resolve(spec, p) for p in op.get("parameters", [])]
    if params:
        lines += ["", "| Flag | Wire name | In | Type / values | Required |", "| --- | --- | --- | --- | --- |"]
        for p in params:
            wire = p["name"]
            flag = p.get("x-cli-name", wire)
            # Restish makes every required parameter a positional argument, in
            # spec order, and renders the rest as kebab-case flags.
            if p.get("in") == "path" or p.get("required"):
                shown = f"`<{flag}>`"
            else:
                shown = f"`--{kebab(flag)}`"
            same = "—" if flag == wire else f"`{wire}`"
            lines.append(
                f"| {shown} | {same} | {p.get('in','')} | {type_of(p.get('schema', {}))} "
                f"| {'yes' if p.get('required') else ''} |"
            )

    content = op.get("responses", {}).get("200", {}).get("content", {})
    if "text/csv" in content:
        flag = "--format csv" if op["path"].startswith("/v2") else "--export true"
        lines += ["", f"CSV: `{flag}` (pair with `--rsh-print b`)."]
    schema = content.get("application/json", {}).get("schema", {})
    if schema.get("$ref"):
        lines += ["", f"Response schema: `{schema['$ref'].rsplit('/', 1)[-1]}`"]
    return lines + [""]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, help="local OpenAPI json (default: fetch the live one)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    spec = load_spec(args.spec)
    ops = operations(spec)
    version = spec["info"]["version"]

    out = [
        "# PFF API endpoint reference",
        "",
        f"Auto-generated from the PFF OpenAPI document (**spec version {version}**, "
        f"{len(ops)} operations) by "
        "[`scripts/gen_pff_endpoint_reference.py`](../scripts/gen_pff_endpoint_reference.py). "
        "The spec is public-read at <https://api.pff.com/openapi.json> — no credential — so this "
        "regenerates without a subscription. Re-run it after `restish api sync pff` reports new "
        "commands.",
        "",
        "Structure only. PFF authors long per-parameter prose in the spec; it is not copied here. "
        "Read it with `restish pff <command> --help`. Setup, auth and export mechanics are in "
        "[`docs/pff-cli.md`](pff-cli.md).",
        "",
        "Required parameters are **positional** in Restish, in the order below, and shown as "
        "`<name>`; optional ones are `--flags`. Flag names are not always wire names — "
        "`--franchise` is `franchise_id`, `--game` is `game_id`. The **Wire name** column is what "
        "a raw HTTP client must send; `—` means the two match.",
        "",
    ]

    by_tag: dict[str, list[dict]] = {}
    for op in ops:
        for tag in op.get("tags", ["untagged"]):
            by_tag.setdefault(tag, []).append(op)

    out += ["## Contents", ""]
    for tag in TAG_ORDER + sorted(set(by_tag) - set(TAG_ORDER)):
        if tag in by_tag:
            out.append(f"- [`{tag}`](#{tag}) — {len(by_tag[tag])} operations")
    out.append("")

    for tag in TAG_ORDER + sorted(set(by_tag) - set(TAG_ORDER)):
        if tag not in by_tag:
            continue
        out += [f"## {tag}", ""]
        if TAG_BLURB.get(tag):
            out += [TAG_BLURB[tag], ""]
        for op in sorted(by_tag[tag], key=lambda o: o.get("operationId", "")):
            out += render_op(spec, op)

    args.out.write_text("\n".join(out), encoding="utf-8")
    print(f"{args.out}  {len(ops)} operations, spec {version}")


if __name__ == "__main__":
    main()
