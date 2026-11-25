from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .doctor import TOKEN_HEADER, run_doctor
from .executors import HttpExecutor
from .model import OUTCOME_LEFT_STATE, OUTCOME_PROBE_FAILURE
from .probes.common import STATE_SNAPSHOT
from .registry import builtin
from .runner import capture_environment, run_probes, write_reports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cameo-probe", description="Probe a live Cameo to produce evidence for the TDD contract.")
    sub = parser.add_subparsers(dest="command", required=True)

    ls = sub.add_parser("list", help="list built-in probes")
    ls.add_argument("--family")

    run = sub.add_parser("run", help="run probes against a live probe shim")
    run.add_argument("--url", required=True, help="probe shim endpoint (protocol v0)")
    run.add_argument("--family")
    run.add_argument("--probe", action="append", dest="probes", metavar="ID", help="repeatable")
    run.add_argument("--repeat", type=int, default=3)
    run.add_argument("--out", default="evidence")
    run.add_argument("--timeout", type=float, default=30.0)
    run.add_argument("--thread", choices=("edt", "http"), default="edt")
    run.add_argument("--token", help="shim token (or set CAMEO_PROBE_TOKEN)")
    run.add_argument("--no-state-check", action="store_true",
                     help="skip the before/after model snapshot that detects leftover state")

    doc = sub.add_parser("doctor", help="check that a probe shim behaves as protocol v0 says")
    doc.add_argument("--url", required=True)
    doc.add_argument("--token", help="shim token (or set CAMEO_PROBE_TOKEN)")
    doc.add_argument("--timeout", type=float, default=30.0)
    doc.add_argument("--expect-project", choices=("any", "yes", "no"), default="any",
                     help="whether a project should be open in Cameo right now")
    return parser


def _doctor(args, token) -> int:
    checks = run_doctor(args.url, token=token, timeout_s=args.timeout, expect_project=args.expect_project)
    for check in checks:
        print(f"{check.status.upper():<5} {check.name:<36} {check.detail}")
    failed = sum(c.status == "fail" for c in checks)
    print(f"{sum(c.status == 'pass' for c in checks)} passed, {failed} failed, "
          f"{sum(c.status == 'skip' for c in checks)} skipped")
    return 1 if failed else 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    token = getattr(args, "token", None) or os.environ.get("CAMEO_PROBE_TOKEN")
    if args.command == "doctor":
        return _doctor(args, token)
    try:
        selected = builtin().select(family=args.family, ids=getattr(args, "probes", None))
    except KeyError as exc:
        print(f"error: unknown probe {exc.args[0]}", file=sys.stderr)
        return 2

    if args.command == "list":
        for p in selected:
            clauses = ",".join(p.clauses) or "-"
            print(f"{p.id:<10} {p.family:<9} {p.status:<8} {clauses:<12} {p.hypothesis}")
        return 0

    if not selected:
        print("error: no probes selected", file=sys.stderr)
        return 2
    executor = HttpExecutor(args.url, timeout_s=args.timeout, thread=args.thread,
                            headers={TOKEN_HEADER: token} if token else None)
    fingerprint = capture_environment(executor)
    if "error" in fingerprint:
        print(f"error: cannot fingerprint the shim ({fingerprint['error']}: {fingerprint.get('message')}); "
              "run doctor first", file=sys.stderr)
        return 1
    if fingerprint.get("hasProject") is False:
        blocked = [p.id for p in selected if p.needs_project]
        if blocked:
            print(f"error: no project is open in Cameo, and these probes need one: {', '.join(blocked)}",
                  file=sys.stderr)
            return 2
    environment = {"executor": executor.describe(), "fingerprint": fingerprint}
    reports = run_probes(selected, executor, repeat=args.repeat, environment=environment,
                         state_check=None if args.no_state_check else STATE_SNAPSHOT)
    for report, path in zip(reports, write_reports(reports, args.out)):
        print(f"{report.probe_id:<10} {report.evidence_level:<12} {report.stability:<7} {path}")
    failed = any(run.outcome in (OUTCOME_PROBE_FAILURE, OUTCOME_LEFT_STATE) for r in reports for run in r.runs)
    return 1 if failed else 0
