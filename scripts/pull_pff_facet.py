"""Pull PFF leaderboards (facet and signature commands) to CSV via the Restish CLI.

    python scripts/pull_pff_facet.py passing --league ncaa --season 2025 --division fbs
    python scripts/pull_pff_facet.py all --league ncaa --season 2026 --division fbs
    python scripts/pull_pff_facet.py all --league ncaa --season 2026 --week 1 --dry-run

`all` expands to every exportable leaderboard in the OpenAPI document whose
required parameters the flags you gave can satisfy -- so without `--week` that
is the 28 season-level `facet-*` commands, and with `--week` it also picks up
the four `signature-*` commands, which require one. Nothing is hardcoded: the
list comes from the spec, so a command PFF adds appears here on the next run.

Auth is the `ci` API-key profile from docs/pff-cli.md. Always pin `--division`
on NCAA -- unpinned, an NCAA export sweeps to D3 and does not come back.

PFF meters exports at 20/minute per account, so a bulk run is paced.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import DATA_ROOT  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_URL = "https://api.pff.com/openapi.json"
EXPORT_PACING_SECONDS = 3.5  # 20 exports/minute, with headroom


def api_key() -> str:
    key = os.environ.get("PFF_API")
    if key:
        return key
    env_file = REPO_ROOT / "env.env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("PFF_API="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"PFF_API not in the environment and not in {env_file}")


def restish_bin() -> str:
    found = shutil.which("restish")
    if found:
        return found
    # ponytail: one fallback for the install documented in docs/pff-cli.md
    fallback = Path.home() / "restish" / "restish.exe"
    if fallback.exists():
        return str(fallback)
    raise SystemExit("restish not on PATH; see docs/pff-cli.md")


def load_spec(path: Path | None) -> dict:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    with urllib.request.urlopen(SPEC_URL, timeout=30) as fh:
        return json.load(fh)


def resolve(spec: dict, node: dict) -> dict:
    ref = node.get("$ref")
    if not ref:
        return node
    out = spec
    for part in ref.lstrip("#/").split("/"):
        out = out[part]
    return out


def exportable_ops(spec: dict) -> dict[str, dict]:
    """Every GET that takes `export`, keyed by operationId and by each alias."""
    found = {}
    for methods in spec["paths"].values():
        op = methods.get("get")
        if not op:
            continue
        params = [resolve(spec, p) for p in op.get("parameters", [])]
        if not any(p["name"] == "export" for p in params):
            continue
        entry = {
            "id": op["operationId"],
            "required": [p["name"] for p in params if p.get("required")],
            "optional": {p.get("x-cli-name", p["name"]) for p in params if not p.get("required")},
        }
        found[entry["id"]] = entry
        for alias in op.get("x-cli-aliases") or []:
            found[alias] = entry
    return found


def out_name(op_id: str, values: dict[str, str], optional: set[str] | None = None) -> str:
    """The file name carries division only when the operation takes one: the
    signature commands don't, so an NCAA signature file is all-division and
    must not be labelled `fbs`."""
    parts = [op_id.replace("-", "_"), values["league"], values["season"].replace(",", "-")]
    if values.get("division") and (optional is None or "division" in optional):
        parts.append(values["division"].replace(",", "-"))
    if values.get("week"):
        parts.append("wk" + values["week"].replace(",", "-"))
    return "_".join(parts) + ".csv"


def build_cmd(binary: str, entry: dict, values: dict[str, str], profile: str) -> list[str]:
    """Required parameters are positional, in spec order; the rest are flags."""
    cmd = [binary, "pff", entry["id"]]
    cmd += [values[name] for name in entry["required"]]
    for name in ("league", "season", "week", "division"):
        if name in entry["required"] or not values.get(name):
            continue
        if name in entry["optional"]:
            cmd += [f"--{name}", values[name]]
    return cmd + ["--export", "true", "--rsh-print", "b", "-p", profile]


def run_to_file(cmd: list[str], dest: Path, env: dict, timeout: float) -> str | None:
    """Run cmd with its body redirected to dest. Returns an error string, or None."""
    with dest.open("wb") as fh:
        try:
            # stdin closed: with a terminal attached, restish waits on it forever
            # when run from a non-interactive shell (an agent, a scheduler).
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                  env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            # Some reports hang server-side rather than answering; one slow
            # command must not block the rest of a bulk run.
            proc = None
    if proc is None:
        # unlink after the `with` closes our handle -- Windows refuses while it is open
        dest.unlink(missing_ok=True)
        return f"timed out after {timeout:.0f}s"
    if proc.returncode != 0:
        # PFF's error envelope goes to stdout (the file); stderr only carries
        # restish's retry chatter, so prefer the body when it says something.
        body = dest.read_text(encoding="utf-8", errors="replace")
        dest.unlink(missing_ok=True)
        return error_code(body) or proc.stderr.decode(errors="replace").strip()[:200]
    return None


def error_code(text: str) -> str | None:
    """PFF errors come back as JSON with exit status 0, so look inside the body."""
    body = text.strip()
    if not body.startswith("{"):
        return None
    try:
        err = json.loads(body).get("error")
    except json.JSONDecodeError:
        return None
    if not err:
        return None
    detail = err.get("details", {}).get("upstream_status")
    return f"{err.get('code')}" + (f" (upstream {detail})" if detail else "")


def pull_one(binary: str, entry: dict, values: dict, out_dir: Path, profile: str, env: dict,
             timeout: float) -> str:
    dest = out_dir / out_name(entry["id"], values, entry["optional"])
    cmd = build_cmd(binary, entry, values, profile)
    err = run_to_file(cmd, dest, env, timeout)
    if err:
        return f"FAIL {entry['id']}: {err}"

    text = dest.read_text(encoding="utf-8", errors="replace")
    code = error_code(text)
    if code:
        dest.unlink(missing_ok=True)
        return f"FAIL {entry['id']}: {code}"

    rows = [ln for ln in text.splitlines() if ln.strip()]
    if rows and "," in rows[0]:
        return f"ok   {dest.name}  {len(rows) - 1} rows, {len(rows[0].split(','))} cols"

    # Some reports answer --export true with the right number of lines and no
    # content in any of them -- blank CSV, working JSON. Not an entitlement
    # problem (an unentitled export is empty too, but so is its JSON). Fall back
    # to JSON so the report is still captured; see docs/pff-cli.md.
    dest.unlink(missing_ok=True)
    json_dest = dest.with_suffix(".json")
    json_cmd = [a for a in cmd if a not in ("--export", "true")] + ["-o", "json"]
    err = run_to_file(json_cmd, json_dest, env, timeout)
    if err:
        return f"FAIL {entry['id']}: blank CSV, and JSON failed: {err}"
    body = json_dest.read_text(encoding="utf-8", errors="replace")
    code = error_code(body)
    if code:
        json_dest.unlink(missing_ok=True)
        return f"FAIL {entry['id']}: {code}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        json_dest.unlink(missing_ok=True)
        return f"FAIL {entry['id']}: blank CSV, and JSON was unparseable"
    listed = [(k, v) for k, v in payload.items() if isinstance(v, list)]
    if not any(v for _, v in listed):
        # Blank CSV *and* an empty JSON body: the report genuinely has no data
        # for this query (a week that was never played, say). Keep no file.
        json_dest.unlink(missing_ok=True)
        return f"SKIP {entry['id']}: no data"
    shape = ", ".join(f"{len(v)} {k}" for k, v in listed)
    return f"JSON {json_dest.name}  {shape}  (CSV export came back blank)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("facets", nargs="+", help="command names or aliases, or the single word `all`")
    ap.add_argument("--league", required=True, help="nfl, ncaa, hs, aaf or ufl")
    ap.add_argument("--season", required=True, help="a year, or a comma-separated list")
    ap.add_argument("--week", help="week id; required by the signature commands")
    ap.add_argument("--division", help="ncaa only: fbs, fcs, lower — always pin this on ncaa")
    ap.add_argument("--out-dir", type=Path, default=DATA_ROOT / "raw" / "pff")
    ap.add_argument("--profile", default="ci")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="seconds to wait per request before giving up (default: 180)")
    ap.add_argument("--spec", type=Path, help="local OpenAPI json (default: fetch the live one)")
    ap.add_argument("--dry-run", action="store_true", help="print what would run, call nothing")
    args = ap.parse_args()

    values = {"league": args.league, "season": args.season, "week": args.week,
              "division": args.division}
    available = {k for k, v in values.items() if v}
    ops = exportable_ops(load_spec(args.spec))

    if args.facets == ["all"]:
        chosen, skipped = [], []
        for entry in {e["id"]: e for e in ops.values()}.values():
            missing = [r for r in entry["required"] if r not in available]
            (skipped if missing else chosen).append((entry, missing))
        chosen = [e for e, _ in sorted(chosen, key=lambda x: x[0]["id"])]
        for entry, missing in sorted(skipped, key=lambda x: x[0]["id"]):
            print(f"skip {entry['id']}: needs --{', --'.join(missing)}")
    else:
        chosen = []
        for name in args.facets:
            if name not in ops:
                raise SystemExit(f"unknown command: {name}")
            missing = [r for r in ops[name]["required"] if r not in available]
            if missing:
                raise SystemExit(f"{name} needs --{', --'.join(missing)}")
            chosen.append(ops[name])

    binary = restish_bin()
    if args.dry_run:
        for entry in chosen:
            print(" ".join(build_cmd(binary, entry, values, args.profile)))
            print(f"  -> {args.out_dir / out_name(entry['id'], values, entry['optional'])}")
        print(f"\n{len(chosen)} exports, ~{len(chosen) * EXPORT_PACING_SECONDS / 60:.1f} min paced")
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PFF_API": api_key()}
    results = []
    for i, entry in enumerate(chosen):
        if i:
            time.sleep(EXPORT_PACING_SECONDS)
        line = pull_one(binary, entry, values, args.out_dir, args.profile, env, args.timeout)
        print(line, flush=True)
        results.append(line)
    bad = [r for r in results if not r.startswith(("ok", "JSON"))]
    print(f"\n{len(results) - len(bad)}/{len(results)} exported to {args.out_dir}")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
