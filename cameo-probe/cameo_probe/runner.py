"""Runs probes against an Executor and turns observations into evidence reports."""
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .executors import Executor
from .model import (LEVEL_INCONCLUSIVE, LEVEL_LIVE, LEVEL_LIVE_DRAFT, LEVEL_SCRIPTED, LEVEL_SKIPPED,
                    OUTCOME_COMPLETED, OUTCOME_LEFT_STATE, OUTCOME_PROBE_FAILURE, OUTCOME_SKIPPED, ExecResult, Probe,
                    ProbeReport, RunRecord, Step, StepRecord)
from .normalize import Normalizer
from .probes.env import ENV_FINGERPRINT

# Prepended to every snippet. Snippets must use fully qualified names (no imports).
PRELUDE = "def __json = { Object o -> groovy.json.JsonOutput.toJson(o) }\n"


def _parse_value(result: ExecResult) -> Any:
    if not result.ok or result.value is None:
        return None
    try:
        return json.loads(result.value)
    except (TypeError, ValueError):
        return result.value


def _reported_failure(rec: StepRecord) -> bool:
    """A snippet that returns a JSON object with "ok": false is reporting that it could not do its
    job (session threw, setup missing, no project). Behaviour under test goes in other fields."""
    return isinstance(rec.value, dict) and rec.value.get("ok") is False


def _snapshot(executor: Executor, step: Optional[Step]) -> Any:
    if step is None:
        return None
    result = executor.execute(PRELUDE + step.code)
    return _parse_value(result) if result.ok else ("SNAPSHOT_FAILED", result.error_type)


def run_probe_once(probe: Probe, executor: Executor, *, state_check: Optional[Step] = None) -> RunRecord:
    record = RunRecord()

    def do(phase: str, step: Step) -> StepRecord:
        result = executor.execute(PRELUDE + step.code)
        rec = StepRecord(phase=phase, name=step.name, ok=result.ok, value=_parse_value(result),
                         error_type=result.error_type, error_message=result.error_message,
                         duration_ms=result.duration_ms)
        record.steps.append(rec)
        return rec

    def failed(rec: StepRecord) -> bool:
        return (not rec.ok) or _reported_failure(rec)

    if probe.precondition is not None:
        rec = do("precondition", probe.precondition)
        if not rec.ok:
            record.outcome = OUTCOME_PROBE_FAILURE
            return record
        if not (isinstance(rec.value, dict) and rec.value.get("ok") is True):
            reason = rec.value.get("reason") if isinstance(rec.value, dict) else None
            record.outcome = OUTCOME_SKIPPED
            record.skipped_reason = str(reason) if reason else "precondition not satisfied"
            return record

    before = _snapshot(executor, state_check)
    try:
        for step in probe.setup:
            if failed(do("setup", step)):
                record.outcome = OUTCOME_PROBE_FAILURE
                return record
        if failed(do("action", probe.action)):
            record.outcome = OUTCOME_PROBE_FAILURE
            return record
        for step in probe.observe:
            if failed(do("observe", step)):
                record.outcome = OUTCOME_PROBE_FAILURE
                return record
    finally:
        for step in probe.teardown:
            if failed(do("teardown", step)):
                record.outcome = OUTCOME_PROBE_FAILURE
        if state_check is not None and _snapshot(executor, state_check) != before:
            record.left_state = True
            if record.outcome == OUTCOME_COMPLETED:
                record.outcome = OUTCOME_LEFT_STATE
    return record


def _signature(step: StepRecord) -> Tuple[Any, ...]:
    return (step.phase, step.name, step.ok, step.value, step.error_type, step.error_message)


def _compare(runs: Sequence[RunRecord]) -> Tuple[bool, List[str]]:
    base, stable, differing = runs[0], True, []
    for other in runs[1:]:
        if other.outcome != base.outcome or other.skipped_reason != base.skipped_reason:
            stable = False
            if "outcome" not in differing:
                differing.append("outcome")
        for i in range(max(len(base.steps), len(other.steps))):
            a = base.steps[i] if i < len(base.steps) else None
            b = other.steps[i] if i < len(other.steps) else None
            if (a and _signature(a)) != (b and _signature(b)):
                stable = False
                label = f"{(a or b).phase}:{(a or b).name}"
                if label not in differing:
                    differing.append(label)
    return stable, differing


def _digest(run: RunRecord) -> str:
    blob = json.dumps(
        {"outcome": run.outcome, "skipped_reason": run.skipped_reason,
         "steps": [list(_signature(s)) for s in run.steps]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _timings(runs: Sequence[RunRecord]) -> Dict[str, List[float]]:
    buckets: Dict[str, List[float]] = {}
    for run in runs:
        for s in run.steps:
            buckets.setdefault(f"{s.phase}:{s.name}", []).append(s.duration_ms)
    return {k: [round(min(v), 1), round(statistics.median(v), 1), round(max(v), 1)]
            for k, v in buckets.items()}


def _evidence_level(probe: Probe, executor: Executor, runs: Sequence[RunRecord], stable: bool) -> str:
    if all(r.outcome == OUTCOME_SKIPPED for r in runs):
        return LEVEL_SKIPPED
    if not executor.is_live:
        return LEVEL_SCRIPTED
    if any(r.outcome != OUTCOME_COMPLETED for r in runs):
        return LEVEL_INCONCLUSIVE
    if probe.status != "reviewed":
        return LEVEL_LIVE_DRAFT
    return LEVEL_LIVE if stable else LEVEL_INCONCLUSIVE


def run_probe(probe: Probe, executor: Executor, *, repeat: int = 3,
              environment: Optional[Dict[str, Any]] = None,
              normalizer: Optional[Normalizer] = None,
              state_check: Optional[Step] = None) -> ProbeReport:
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    normalizer = normalizer or Normalizer()
    runs = [run_probe_once(probe, executor, state_check=state_check) for _ in range(repeat)]
    for run in runs:  # fresh ID map per run, so real IDs never leak into evidence
        payload = [{"value": s.value, "error_message": s.error_message} for s in run.steps]
        normalized = normalizer.normalize_run(payload + [run.skipped_reason])
        for step, norm in zip(run.steps, normalized):
            step.value, step.error_message = norm["value"], norm["error_message"]
        run.skipped_reason = normalized[-1]

    all_skipped = all(r.outcome == OUTCOME_SKIPPED for r in runs)
    stable, differing = _compare(runs)
    return ProbeReport(
        probe_id=probe.id, family=probe.family, hypothesis=probe.hypothesis,
        clauses=list(probe.clauses), probe_status=probe.status,
        evidence_level=_evidence_level(probe, executor, runs, stable),
        stability="n/a" if all_skipped else ("stable" if stable else "flaky"),
        differing_steps=differing, repeat=repeat, digest=_digest(runs[0]),
        environment=dict(environment or {}), timings_ms=_timings(runs), runs=runs)


def run_probes(probes: Sequence[Probe], executor: Executor, *, repeat: int = 3,
               environment: Optional[Dict[str, Any]] = None,
               state_check: Optional[Step] = None) -> List[ProbeReport]:
    return [run_probe(p, executor, repeat=repeat, environment=environment, state_check=state_check)
            for p in probes]


def capture_environment(executor: Executor) -> Dict[str, Any]:
    result = executor.execute(PRELUDE + ENV_FINGERPRINT.code)
    value = _parse_value(result)
    if result.ok and isinstance(value, dict):
        return value
    return {"error": result.error_type or "UnparseableFingerprint", "message": result.error_message}


def write_reports(reports: Sequence[ProbeReport], out_dir: Any) -> List[Path]:
    """SCRIPTED reports go to _scratch/ so test-double output can never pass as evidence."""
    root, paths = Path(out_dir), []
    for report in reports:
        sub = "_scratch" if report.evidence_level == LEVEL_SCRIPTED else report.family
        path = root / sub / f"{report.probe_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        paths.append(path)
    return paths
