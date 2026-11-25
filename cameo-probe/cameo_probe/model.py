"""Data model for the probe harness (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

PROBE_ID_RE = re.compile(r"^P-[A-Z]{3}-\d{3}$")
CLAUSE_ID_RE = re.compile(r"^CL-[A-Z]{3}-\d{3}$")
PROBE_STATUSES = ("draft", "reviewed")

# Outcome of a single run of a probe.
OUTCOME_COMPLETED = "completed"
OUTCOME_SKIPPED = "skipped"
OUTCOME_PROBE_FAILURE = "probe_failure"
OUTCOME_LEFT_STATE = "left_state"  # completed, but the model differs after teardown

# Evidence levels written into reports (contract section 2.1 maps LIVE to the LIVE tag).
LEVEL_SCRIPTED = "SCRIPTED"          # produced by a test double; never evidence
LEVEL_LIVE_DRAFT = "LIVE_DRAFT"      # live run of a probe a human has not reviewed yet
LEVEL_LIVE = "LIVE"                  # live, reviewed probe, stable across repeats
LEVEL_INCONCLUSIVE = "INCONCLUSIVE"  # live but failed, flaky, or left state behind
LEVEL_SKIPPED = "SKIPPED"            # precondition not met on every run


@dataclass(frozen=True)
class ExecResult:
    """Outcome of running one snippet through an Executor.

    ok=False means the snippet did not complete: transport failure, compile
    error, or an exception that escaped the snippet. Behaviour under test must
    be caught inside the snippet and returned in its JSON payload instead.
    """

    ok: bool
    value: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0


@dataclass(frozen=True)
class Step:
    """One Groovy snippet. It must `return` a JSON string (use __json([...]))."""

    name: str
    code: str


@dataclass(frozen=True)
class Probe:
    id: str
    family: str
    hypothesis: str
    action: Step
    clauses: Tuple[str, ...] = ()
    precondition: Optional[Step] = None
    setup: Tuple[Step, ...] = ()
    observe: Tuple[Step, ...] = ()
    teardown: Tuple[Step, ...] = ()
    status: str = "draft"
    needs_project: bool = True  # the CLI refuses to run it when the shim reports no open project

    def __post_init__(self) -> None:
        if not PROBE_ID_RE.match(self.id):
            raise ValueError(f"bad probe id {self.id!r}; expected P-XXX-000")
        if self.status not in PROBE_STATUSES:
            raise ValueError(f"bad probe status {self.status!r}; expected one of {PROBE_STATUSES}")
        if not self.hypothesis.strip():
            raise ValueError(f"{self.id}: a hypothesis is required")
        for clause in self.clauses:
            if not CLAUSE_ID_RE.match(clause):
                raise ValueError(f"{self.id}: bad clause id {clause!r}; expected CL-XXX-000")


@dataclass
class StepRecord:
    phase: str
    name: str
    ok: bool
    value: Any = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class RunRecord:
    outcome: str = OUTCOME_COMPLETED
    steps: List[StepRecord] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    left_state: bool = False


@dataclass
class ProbeReport:
    probe_id: str
    family: str
    hypothesis: str
    clauses: List[str]
    probe_status: str
    evidence_level: str
    stability: str  # "stable" | "flaky" | "n/a"
    differing_steps: List[str]
    repeat: int
    digest: str
    environment: Dict[str, Any]
    timings_ms: Dict[str, List[float]]
    runs: List[RunRecord]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Per-step durations are summarised in timings_ms; dropping them keeps re-runs diffable.
        for run in data["runs"]:
            for step in run["steps"]:
                step.pop("duration_ms", None)
        return data
