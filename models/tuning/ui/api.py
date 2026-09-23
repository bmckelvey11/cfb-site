"""What the GUI asks the lab, run in the main `.venv` so the spec logic is the worker's own.

    python -m models.tuning.ui.api catalog  [--root DIR]
    python -m models.tuning.ui.api validate --spec FILE [--root DIR]

Both print one JSON document. Imports stay light (spec, catalog, fingerprint: no optuna,
no sklearn) so a Validate click answers in about a second. `validate` is where the GUI's
guardrails live, so the UI cannot route around them:

- red (blocking): the spec does not parse or breaks a RunSpec rule; a sealed season; a
  feature the catalog refuses or declares differently;
- amber: the outer seasons were already evaluated, with the prior runs and their trials
  read from `jobs.sqlite3` (synthetic runs never count);
- the run it would launch: the next replicate whose job is absent, or a completed job on
  this exact code (returned as is). A job still in flight blocks the launch.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from pydantic import ValidationError

from models.tuning.catalog import CATALOG, ELIGIBLE, REFUSED
from models.tuning.fingerprint import code_fingerprint
from models.tuning.spec import SEARCH_PROFILES, RunSpec, canonical_json

# 2026 belongs to prior_v3's one confirmatory look (after the regular season) and to the
# Release E shadow period. Lift only after both are recorded in models/tuning/hypotheses.json.
SEALED = frozenset({2026})
# Evaluated outside the lab's job store (Release B, the priors work, D, F1): see the
# Hypotheses page. Any run scored on them is descriptive.
USED_OUTSIDE_LAB = frozenset(range(2021, 2026))
IN_FLIGHT = ("queued", "claimed", "running", "retry_wait", "cancellation_requested")
SNAPSHOTS = ("release_b_ridge_v1_2026-09-23",)
SEASONS = tuple(range(2014, 2026))


def catalog() -> dict:
    return {"features": [{"id": k, "version": e.version, "availability_class": e.availability_class,
                          "description": e.description, "eligible": e.availability_class == ELIGIBLE,
                          "refused_because": REFUSED.get(e.availability_class)}
                         for k, e in CATALOG.items()],
            "baselines": ["market_open", "past_mean", "ridge_v1_total"],
            "profiles": {k: {fam: {p: list(v) for p, v in ps.items()} for fam, ps in prof.items()}
                         for k, prof in SEARCH_PROFILES.items()},
            "snapshots": list(SNAPSHOTS), "seasons": list(SEASONS), "sealed": sorted(SEALED),
            "code_sha256": code_fingerprint()}


def _jobs(root: Path) -> list[dict]:
    path = root / "jobs.sqlite3"
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(
            "SELECT run_id, config_hash, attempt, state, code_sha256, spec_json FROM jobs ORDER BY job_id")]
    finally:
        con.close()


def validate(text: str, root: Path) -> dict:
    out = {"ok": False, "errors": [], "warnings": [], "config_hash": None, "run_id": None,
           "canonical": None, "holdout": None, "launch": None}
    try:
        spec = RunSpec.model_validate_json(text)
    except ValidationError as e:
        out["errors"] = [f"{'.'.join(str(p) for p in err['loc']) or 'spec'}: {err['msg']}"
                         for err in e.errors()]
        return out
    ds, f = spec.dataset, spec.folds
    sealed = sorted(SEALED & set(ds.seasons + f.inner_test_seasons + f.outer_test_seasons))
    if sealed:
        out["errors"].append(f"seasons {sealed} are sealed: prior_v3's confirmation and the "
                             "shadow period own them")
    for ref in spec.feature_set.features:
        entry = CATALOG.get(ref.id)
        if entry is None:
            out["errors"].append(f"feature {ref.id}: not in the catalog")
        elif (entry.version, entry.availability_class) != (ref.version, ref.availability_class):
            out["errors"].append(f"feature {ref.id}: declared v{ref.version} {ref.availability_class}, "
                                 f"catalog says v{entry.version} {entry.availability_class}")
        elif entry.availability_class != ELIGIBLE:
            out["errors"].append(f"feature {ref.id}: {REFUSED[entry.availability_class]}")

    outer = set(f.outer_test_seasons)
    jobs = _jobs(root)
    prior = []
    for j in jobs:
        other = json.loads(j["spec_json"])
        if j["config_hash"] == spec.config_hash or other["dataset"]["source"] != "cfb_release_b":
            continue
        overlap = sorted(outer & set(other["folds"]["outer_test_seasons"]))
        if overlap:
            prior.append({"run_id": j["run_id"], "state": j["state"], "overlap": overlap,
                          "n_trials": other["search"]["n_trials"]})
    out["holdout"] = {"outer": sorted(outer), "prior_runs": prior,
                      "prior_trials": sum(p["n_trials"] for p in prior),
                      "used_outside_lab": sorted(outer & USED_OUTSIDE_LAB)}
    if ds.source == "cfb_release_b" and (prior or outer & USED_OUTSIDE_LAB):
        by = ([f"{len(prior)} lab run(s) ({out['holdout']['prior_trials']} trials requested)"]
              if prior else [])
        if outer & USED_OUTSIDE_LAB:
            by.append(f"Releases B and D, the priors work, and F1 on {sorted(outer & USED_OUTSIDE_LAB)} "
                      "(Hypotheses page)")
        out["warnings"].append(f"Outer seasons {sorted(outer)} were already evaluated by "
                               f"{' and by '.join(by)}. The result is descriptive, not new "
                               "holdout evidence.")

    code = code_fingerprint()
    mine = {j["attempt"]: j for j in jobs if j["config_hash"] == spec.config_hash}
    r = 0
    while r in mine and not (mine[r]["state"] == "completed" and mine[r]["code_sha256"] == code):
        if mine[r]["state"] in IN_FLIGHT:
            out["errors"].append(f"{mine[r]['run_id']} is {mine[r]['state']}: wait for it or cancel it")
            break
        r += 1
    existing = mine.get(r)
    out["launch"] = {"replicate": r, "run_id": spec.run_id(r),
                     "existing_state": existing["state"] if existing else None,
                     "skipped": [{"run_id": mine[a]["run_id"], "state": mine[a]["state"],
                                  "same_code": mine[a]["code_sha256"] == code} for a in sorted(mine) if a < r],
                     "code_sha256": code}
    if existing and existing["state"] == "completed":
        out["warnings"].append(f"{existing['run_id']} already completed on this code: launching "
                               "returns it; nothing is refit")
    out.update(ok=not out["errors"], config_hash=spec.config_hash, run_id=spec.run_id(),
               canonical=json.dumps(json.loads(canonical_json(spec)), indent=1, sort_keys=True))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog")
    c.add_argument("--root")
    v = sub.add_parser("validate")
    v.add_argument("--spec", required=True)
    v.add_argument("--root")
    args = ap.parse_args(argv)
    if args.root:
        root = Path(args.root)
    else:
        from cfb_paths import PROCESSED
        root = PROCESSED / "tuning"
    out = catalog() if args.cmd == "catalog" else validate(
        Path(args.spec).read_text(encoding="utf-8"), root)
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
