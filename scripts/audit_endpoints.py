"""Endpoint completeness: live CFBD spec vs vendored client vs `ENDPOINTS` registry.

`audit_coverage.py` answers "did we scrape every file the registry expects" — its
universe is the registry. This one answers "does the registry cover every endpoint
CFBD publishes", so its universe is the live OpenAPI spec.

    python scripts/audit_endpoints.py                  # fetch the live spec
    python scripts/audit_endpoints.py --spec spec.json # offline, from a saved copy

Exits 1 if any spec path is unclassified or any registry entry has drifted.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as `python scripts/...`
from cfb_system_maker.scrapers import ENDPOINTS  # noqa: E402

SPEC_URL = "https://api.collegefootballdata.com/api-docs.json"
CLIENT_API_DIR = Path(__file__).resolve().parent.parent / "cfbd-python" / "cfbd" / "api"
# Endpoints CFBD publishes that we deliberately do not register; see docs/data-coverage.md.
DELIBERATE = {"/info/usage": "account metering, not football data"}


def load_spec(src: str) -> dict:
    if src.startswith(("http://", "https://")):
        # Non-default User-Agent: Cloudflare 403s urllib's own.
        req = urllib.request.Request(src, headers={"User-Agent": "cfb-system-maker/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    return json.loads(Path(src).read_text(encoding="utf-8"))


def client_methods() -> dict[tuple[str, str], str]:
    """Map (ApiClass, method) -> REST path, read from the generated client's source.

    The path literal only exists at the `self.api_client.call_api('/x', 'GET', ...)`
    site inside each `*_with_http_info` variant, so the source is parsed rather than
    the module imported. Paths are never inferred from the class name: TeamsApi
    serves /roster and /talent too.
    """
    found: dict[tuple[str, str], str] = {}
    for py in sorted(CLIENT_API_DIR.glob("*_api.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
                path = _called_path(fn)
                if path:
                    name = fn.name.removesuffix("_with_http_info")
                    found[(cls.name, name)] = path
    return found


def _called_path(fn: ast.FunctionDef) -> str | None:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "call_api" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=SPEC_URL, help="spec URL or local api-docs.json")
    ap.add_argument("--quiet", action="store_true", help="only print the summary")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    paths: dict[str, dict] = spec.get("paths", {})
    client = client_methods()
    by_path: dict[str, list[tuple[str, str]]] = {}
    for key, path in client.items():
        by_path.setdefault(path, []).append(key)
    registry = {(e.api, e.method): e for e in ENDPOINTS}

    registered, client_only, no_client = [], [], []
    for path in sorted(paths):
        keys = by_path.get(path, [])
        hits = [registry[k] for k in keys if k in registry]
        if hits:
            registered.append((path, hits))
        elif keys:
            client_only.append((path, keys))
        else:
            no_client.append(path)
    # Registry entries that no longer resolve — a typo, or an endpoint CFBD retired.
    drift = []
    for key, ep in sorted(registry.items()):
        path = client.get(key)
        if path is None:
            drift.append((ep.name, f"no client method {key[0]}.{key[1]}"))
        elif path not in paths:
            drift.append((ep.name, f"path {path} not in spec"))

    verbs = {v.upper() for ops in paths.values() for v in ops if v.lower() != "parameters"}
    dupes = {p: k for p, k in by_path.items() if len(k) > 1}
    orphan_client = sorted(p for p in by_path if p not in paths)

    if not args.quiet:
        print(f"spec: {args.spec}")
        print(f"spec paths: {len(paths)} | verbs: {', '.join(sorted(verbs))}"
              f" | client methods: {len(client)} | registry: {len(ENDPOINTS)}")
        print("\nREGISTERED (%d)" % len(registered))
        for path, hits in registered:
            names = ", ".join(sorted(h.name for h in hits))
            print(f"  {path:42} {names}")
        print("\nIN CLIENT, NOT REGISTERED (%d)" % len(client_only))
        for path, keys in client_only:
            why = DELIBERATE.get(path, "registerable now")
            print(f"  {path:42} {keys[0][0]}.{keys[0][1]}  — {why}")
        print("\nNO CLIENT METHOD — blocked on a cfbd-python bump (%d)" % len(no_client))
        for path in no_client:
            print(f"  {path}")

    if dupes:
        print("\nWARNING — one path, several client methods:")
        for path, keys in sorted(dupes.items()):
            print(f"  {path}: {keys}")
    if orphan_client:
        print("\nWARNING — client method paths absent from the spec:")
        for path in orphan_client:
            print(f"  {path}: {by_path[path]}")
    if drift:
        print("\nREGISTRY DRIFT — entries that no longer resolve:")
        for name, why in drift:
            print(f"  {name}: {why}")

    total = len(registered) + len(client_only) + len(no_client)
    print(f"\n{len(registered)} registered + {len(client_only)} client-only"
          f" + {len(no_client)} no-client = {total} of {len(paths)} spec paths")
    if total != len(paths):
        print(f"UNCLASSIFIED: {len(paths) - total} path(s) fell through — fix the mapping.")
    if drift:
        print(f"DRIFT: {len(drift)} registry entr(y/ies) no longer resolve.")
    return 1 if drift or total != len(paths) else 0


if __name__ == "__main__":
    sys.exit(main())
