"""Tuning lab CLI (Release C).

    python -m models.tuning run --spec models/tuning/specs/total_ratings_v1.json [--root DIR] [--replicate K]
    python -m models.tuning status [--root DIR]
    python -m models.tuning cancel --run-id RUN_ID [--root DIR]
    python -m models.tuning dist --spec models/tuning/specs/dist_total_v1.json [--root DIR]
    python -m models.tuning shadow {freeze,tick,alias} --spec models/tuning/specs/shadow_2026_w05_08.json
    python -m models.tuning replay --spec models/tuning/specs/replay_2026_w05_08.json [--rehearsal]

`run` submits the spec and works that job until it is completed, failed, or cancelled.
Resubmitting a completed spec returns the existing run when the code fingerprint and
source hashes still match; otherwise it refuses and asks for --replicate.
Default root: data/processed/tuning under CFB_DATA_ROOT.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

from models.tuning.features import source_paths
from models.tuning.spec import load_run_spec
from models.tuning.worker import LabStore, _sources_digest, code_fingerprint, work

TERMINAL = ("completed", "failed", "cancelled")


def _default_root() -> Path:
    from cfb_paths import PROCESSED

    return PROCESSED / "tuning"


def _run(args) -> int:
    spec = load_run_spec(args.spec)
    root = Path(args.root) if args.root else _default_root()
    store = LabStore(root, retry_backoff_s=args.retry_backoff)
    code = code_fingerprint()
    job = store.submit(spec, code, replicate=args.replicate)
    if job.state == "completed":
        sources = None
        if spec.dataset.source == "cfb_release_b":
            from cfb_paths import DATA_ROOT
            sources = _sources_digest(source_paths(spec.dataset, DATA_ROOT), DATA_ROOT)
        else:
            sources = _sources_digest([], None)
        if job.code_sha256 != code or job.sources_sha256 != sources:
            print(f"{job.run_id} is completed with different code or data; rerun with "
                  f"--replicate {args.replicate + 1}", file=sys.stderr)
            return 2
        print(f"{job.run_id} already completed (existing run returned)")
    worker_id = args.worker_id or f"{socket.gethostname()}-{time.time_ns()}"
    while job.state not in TERMINAL:
        if job.state == "retry_wait" and job.retry_at:
            time.sleep(max(0.0, job.retry_at - time.time()))
        elif job.state in ("claimed", "running", "cancellation_requested"):
            time.sleep(1.0)  # another worker holds it, or its lease is still running out
        work(root, worker_id, run_id=job.run_id, lease_s=args.lease_s,
             heartbeat_interval=args.heartbeat, grace_period=args.grace,
             retry_backoff_s=args.retry_backoff)
        job = store.get(job.run_id)
    run_dir = root / "runs" / job.run_id
    print(json.dumps({"run_id": job.run_id, "state": job.state, "error_kind": job.error_kind,
                      "error": job.error, "retries": job.retries,
                      "card": str(run_dir / "card.md") if job.state == "completed" else None},
                     indent=1))
    return 0 if job.state == "completed" else 1


def _dist(args) -> int:
    from models.tuning.dist_run import DistRefused, run_dist
    from models.tuning.dist_spec import DistRunSpec

    spec = DistRunSpec.model_validate_json(Path(args.spec).read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else _default_root()
    try:
        run_dir = run_dist(spec, root)
    except DistRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    print(json.dumps({"run_id": spec.run_id(), "selected": scores["selected"],
                      "gate_pass": scores["gate"]["pass"], "card": str(run_dir / "card.md")},
                     indent=1))
    return 0


def _shadow(args) -> int:
    from cfb_paths import DATA_ROOT

    from models.tuning.shadow import ShadowRefused, freeze, set_alias, tick
    from models.tuning.shadow_spec import ShadowSpec

    spec = ShadowSpec.model_validate_json(Path(args.spec).read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else _default_root()
    try:
        if args.action == "freeze":
            doc = freeze(spec, root, DATA_ROOT)
            print(json.dumps({k: doc[k] for k in ("shadow_id", "artifacts", "pools")}, indent=1))
            print("written: commit the freeze file before the first snapshot")
            return 0
        if args.action == "alias":
            if not (args.alias and args.model and args.reason):
                print("alias needs --alias, --model and --reason", file=sys.stderr)
                return 2
            set_alias(spec, root, args.alias, args.model, args.reason)
            return 0
        return tick(spec, root, DATA_ROOT)
    except ShadowRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


def _replay(args) -> int:
    from cfb_paths import DATA_ROOT

    from models.tuning.replay import ReplaySpec, replay
    from models.tuning.shadow import ShadowRefused

    spec = ReplaySpec.model_validate_json(Path(args.spec).read_text(encoding="utf-8"))
    try:
        out = replay(spec, Path(args.root) if args.root else _default_root(), DATA_ROOT,
                     rehearsal=args.rehearsal)
    except ShadowRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(out["framing"])
    print(json.dumps({k: out[k] for k in ("replay_id", "weeks", "games_priced", "views",
                                          "actionable", "p_over_vs_market")}, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m models.tuning", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--spec", required=True)
    r.add_argument("--root")
    r.add_argument("--replicate", type=int, default=0)
    r.add_argument("--worker-id")
    r.add_argument("--lease-s", type=float, default=60.0)
    r.add_argument("--heartbeat", type=int, default=10, help="Optuna heartbeat interval, seconds")
    r.add_argument("--grace", type=int, default=None, help="stale-trial grace, seconds")
    r.add_argument("--retry-backoff", type=float, default=5.0)
    s = sub.add_parser("status")
    s.add_argument("--root")
    c = sub.add_parser("cancel")
    c.add_argument("--run-id", required=True)
    c.add_argument("--root")
    d = sub.add_parser("dist", help="predictive distributions on a completed run (Release D)")
    d.add_argument("--spec", required=True)
    d.add_argument("--root")
    sh = sub.add_parser("shadow", help="live shadow ledger (Release E)")
    sh.add_argument("action", choices=["freeze", "tick", "alias"])
    sh.add_argument("--spec", required=True)
    sh.add_argument("--root")
    sh.add_argument("--alias", choices=["champion", "challenger"])
    sh.add_argument("--model")
    sh.add_argument("--reason")
    rp = sub.add_parser("replay", help="priced replay of a finished shadow period")
    rp.add_argument("--spec", required=True)
    rp.add_argument("--root")
    rp.add_argument("--rehearsal", action="store_true", help="rehearsal weeks only; not a result")
    args = ap.parse_args(argv)

    if args.cmd == "run":
        return _run(args)
    if args.cmd == "dist":
        return _dist(args)
    if args.cmd == "shadow":
        return _shadow(args)
    if args.cmd == "replay":
        return _replay(args)
    store = LabStore(Path(args.root) if args.root else _default_root())
    if args.cmd == "cancel":
        job = store.request_cancel(args.run_id)
        print(f"{args.run_id}: {job.state if job else 'no such run'}")
        return 0 if job else 1
    for job in store.jobs():
        print(f"{job.run_id}  {job.state:<22} retries {job.retries}  {job.error_kind or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
