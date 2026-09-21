"""Endpoint completeness: live CFBD spec vs vendored client vs `ENDPOINTS` registry.

`audit_coverage.py` answers "did we scrape every file the registry expects" — its
universe is the registry. This one answers "does the registry cover every endpoint
CFBD publishes", so its universe is the live OpenAPI spec.

    python scripts/audit_endpoints.py                    # REST spec + GraphQL schema
    python scripts/audit_endpoints.py --spec spec.json   # offline REST audit only
    python scripts/audit_endpoints.py --no-graphql       # skip the Tier 3 schema pull

The GraphQL half needs a Patreon Tier 3 token. Not having one is a printed note, never a
failure — otherwise the REST partition, which runs offline from a saved spec, would be held
hostage to a paid tier.

Exits 1 if a spec path is unclassified, a registry entry has drifted, or an introspected
GraphQL table is neither in the default pull nor a documented exclusion.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as `python scripts/...`
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.cfbd_client import find_cfbd_token  # noqa: E402
from cfb_system_maker.scrapers import ENDPOINTS  # noqa: E402
from cfb_system_maker.graphql_client import (  # noqa: E402
    GQL_DEFAULT_TABLES,
    GQL_EXCLUDED,
    _introspect,
    _make_poster,
)

SPEC_URL = "https://api.collegefootballdata.com/api-docs.json"
CLIENT_API_DIR = Path(__file__).resolve().parent.parent / "cfbd-python" / "cfbd" / "api"
# Endpoints CFBD publishes that we deliberately do not register; see docs/data-coverage.md.
DELIBERATE = {
    "/info/usage": "account metering, not football data",
    # Dropped 2026-09-10, not pending: GraphQL supersedes both under R6 and the REST
    # pulls were duplicates (docs/warehouse-drop-superseded-2026-09-10.md).
    "/draft/positions": "superseded by GraphQL draftPosition",
    "/draft/teams": "superseded by GraphQL draftTeam",
}


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
    ap.add_argument("--no-graphql", action="store_true", help="skip the GraphQL schema audit")
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

    gql_unaccounted: list[str] = []
    if not args.no_graphql:
        gql_unaccounted = _audit_graphql(DATA_ROOT / "graphql", quiet=args.quiet)

    total = len(registered) + len(client_only) + len(no_client)
    print(f"\n{len(registered)} registered + {len(client_only)} client-only"
          f" + {len(no_client)} no-client = {total} of {len(paths)} spec paths")
    if total != len(paths):
        print(f"UNCLASSIFIED: {len(paths) - total} path(s) fell through — fix the mapping.")
    if drift:
        print(f"DRIFT: {len(drift)} registry entr(y/ies) no longer resolve.")
    return 1 if drift or total != len(paths) or gql_unaccounted else 0


def _audit_graphql(gql_dir: Path, *, quiet: bool) -> list[str]:
    """Partition the introspected GraphQL tables. Returns the unaccounted-for ones.

    Universe is the live schema, not `GQL_DEFAULT_TABLES` — the same reason this script
    exists for REST. A table is accounted for if it is in the default pull or carries a
    documented reason in GQL_EXCLUDED.
    """
    try:
        post = _make_poster(find_cfbd_token())
        schema = _introspect(post)
    except Exception as exc:  # no Tier 3, no token, offline — a note, not a failure
        print(f"\nGRAPHQL: schema not reached ({type(exc).__name__}); section skipped")
        return []

    roots = sorted(schema)
    # Hasura exposes per-key wrappers alongside the table roots. Print what was filtered:
    # a schema shape change then shows up as a diff, not a silently different denominator.
    wrappers = [r for r in roots if r.endswith(("Aggregate", "ByPk", "_aggregate", "_by_pk"))]
    tables = [r for r in roots if r not in set(wrappers)]

    on_disk = _graphql_files(gql_dir)
    in_defaults = [t for t in tables if t in GQL_DEFAULT_TABLES]
    excluded = [t for t in tables if t not in GQL_DEFAULT_TABLES and t in GQL_EXCLUDED]
    unaccounted = [t for t in tables if t not in GQL_DEFAULT_TABLES and t not in GQL_EXCLUDED]
    missing = [t for t in in_defaults if t not in on_disk]
    orphans = sorted(set(on_disk) - set(tables))

    print(f"\nGRAPHQL: {len(roots)} root field(s) with scalars"
          f" - {len(wrappers)} wrapper(s) {wrappers} = {len(tables)} table(s)")
    if not quiet:
        print("  IN DEFAULT PULL (%d)" % len(in_defaults))
        for table in in_defaults:
            files = on_disk.get(table, 0)
            mark = f"{files} file(s)" if files else "NOT ON DISK"
            print(f"    {table:24} {mark}")
        print("  DOCUMENTED EXCLUSION (%d)" % len(excluded))
        for table in excluded:
            files = on_disk.get(table, 0)
            seen = f"{files} file(s) on disk" if files else "not pulled"
            print(f"    {table:24} {seen} — {GQL_EXCLUDED[table]}")

    print(f"  {len(in_defaults)} in defaults + {len(excluded)} excluded"
          f" = {len(in_defaults) + len(excluded)} of {len(tables)} introspected tables")

    # `roots` holds only tables with scalar columns; `*Aggregate` roots return
    # {aggregate, nodes} and are filtered out upstream, so ask the schema for every root.
    _report_row_counts(post, _all_root_names(post), in_defaults, gql_dir, quiet=quiet)
    if missing:
        print(f"  MISSING FROM DISK: {', '.join(missing)} — in the default pull, never scraped.")
    if orphans:
        print(f"  ON DISK, NOT IN SCHEMA: {', '.join(orphans)}")
    if unaccounted:
        print(f"  UNACCOUNTED: {', '.join(unaccounted)}"
              " — add to GQL_DEFAULT_TABLES or give a reason in GQL_EXCLUDED.")
    return unaccounted


def _all_root_names(post) -> set[str]:
    query = "{ __schema { queryType { fields { name } } } }"
    try:
        data = post(query, {})
    except Exception:
        return set()
    return {f["name"] for f in data["__schema"]["queryType"]["fields"]}


def _report_row_counts(post, roots: set[str], tables: list[str], gql_dir: Path, *, quiet: bool) -> None:
    """Compare on-disk row counts to `{table}Aggregate.count` — the source's own total.

    Only some tables expose an aggregate variant; the rest can only be checked for file
    existence, and this says so rather than implying they were verified. Drift is a REFRESH
    decision, not a wiring bug, so it never changes the exit code.
    """
    checkable = [t for t in tables if f"{t}Aggregate" in roots]
    drift: list[tuple[str, int, int]] = []
    for table in checkable:
        path = gql_dir / f"{table}.json"
        if not path.exists():
            continue
        try:
            remote = post("{ %sAggregate { aggregate { count } } }" % table, {})
            remote_n = remote[f"{table}Aggregate"]["aggregate"]["count"]
        except Exception:
            continue
        local_n = _count_rows(path)
        if local_n != remote_n:
            drift.append((table, local_n, remote_n))

    print(f"  ROW COUNTS: {len(checkable)}/{len(tables)} table(s) expose an aggregate variant"
          f" — the other {len(tables) - len(checkable)} are file-existence only")
    if drift:
        print("  BEHIND THE SOURCE (re-pull to close; not a failure):")
        for table, local_n, remote_n in drift:
            print(f"    {table:24} disk {local_n:>8}  source {remote_n:>8}  ({local_n - remote_n:+})")
    elif not quiet:
        print("    every checkable table matches its source count")


def _count_rows(path: Path) -> int:
    """Row count without parsing the file — `game.json` alone is 103 MB.

    `graphql_client._write` dumps `json.dumps(rows, indent=2)`, so every top-level row
    begins on a line that is exactly two spaces and an opening brace.
    """
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.rstrip("\n") == "  {":
                count += 1
    return count


def _graphql_files(gql_dir: Path) -> dict[str, int]:
    """Map table -> file count, folding `{table}_{season}.json` shards into their base."""
    counts: dict[str, int] = {}
    for path in gql_dir.glob("*.json"):
        stem = path.stem
        base, sep, tail = stem.rpartition("_")
        table = base if sep and tail.isdigit() and len(tail) == 4 else stem
        counts[table] = counts.get(table, 0) + 1
    return counts


if __name__ == "__main__":
    sys.exit(main())
