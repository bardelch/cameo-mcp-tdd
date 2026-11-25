"""Regression tests for review findings: false evidence from in-snippet failures, leftover state,
unnormalized skip reasons, probes run with no project, and the cleanup convention."""
import itertools
import json
import re
import tempfile
import unittest

from cameo_probe.executors import ScriptedExecutor
from cameo_probe.model import Step
from cameo_probe.probes.common import STATE_SNAPSHOT
from cameo_probe.registry import builtin
from cameo_probe.runner import run_probe, run_probe_once
from tests.stub_shim import StubShim
from tests.test_cli import run_cli
from tests.test_runner import make_probe, router

REPORTED_FAILURE = json.dumps({"ok": False, "error": {"type": "java.lang.NullPointerException"}})


class InSnippetFailureTests(unittest.TestCase):
    def test_setup_reporting_ok_false_stops_before_the_action(self):
        run = run_probe_once(make_probe(), ScriptedExecutor(router(setup=REPORTED_FAILURE)))
        self.assertEqual(run.outcome, "probe_failure")
        self.assertEqual([s.phase for s in run.steps], ["precondition", "setup", "teardown"])

    def test_action_observe_and_teardown_reporting_ok_false_fail_the_run(self):
        for phase in ("action", "observe", "teardown"):
            with self.subTest(phase=phase):
                run = run_probe_once(make_probe(), ScriptedExecutor(router(**{phase: REPORTED_FAILURE})))
                self.assertEqual(run.outcome, "probe_failure")
                self.assertEqual(run.steps[-1].phase, "teardown")

    def test_behaviour_under_test_in_a_sub_field_is_still_an_observation(self):
        caught = json.dumps({"ok": True, "applyNull": {"threw": True, "type": "IllegalArgumentException"}})
        run = run_probe_once(make_probe(), ScriptedExecutor(router(action=caught)))
        self.assertEqual(run.outcome, "completed")

    def test_live_reported_failure_is_never_live_draft(self):
        # The original harness wrote this as LIVE_DRAFT/stable: P-SES-001 then "proved" cancel works.
        ex = ScriptedExecutor(router(action=REPORTED_FAILURE), pretend_live=True)
        report = run_probe(make_probe(), ex, repeat=2)
        self.assertEqual(report.evidence_level, "INCONCLUSIVE")


class LeftStateTests(unittest.TestCase):
    SNAP = Step("snap", "// step:snap")

    def test_unchanged_model_completes(self):
        ex = ScriptedExecutor(router(snap=json.dumps({"total": 3})), pretend_live=True)
        report = run_probe(make_probe(status="reviewed"), ex, repeat=2, state_check=self.SNAP)
        self.assertEqual([r.outcome for r in report.runs], ["completed", "completed"])
        self.assertEqual(report.evidence_level, "LIVE")

    def test_changed_model_is_left_state_and_inconclusive(self):
        totals = itertools.count(3)
        ex = ScriptedExecutor(router(snap=lambda: json.dumps({"total": next(totals)})), pretend_live=True)
        report = run_probe(make_probe(status="reviewed"), ex, repeat=1, state_check=self.SNAP)
        self.assertEqual(report.runs[0].outcome, "left_state")
        self.assertTrue(report.runs[0].left_state)
        self.assertEqual(report.evidence_level, "INCONCLUSIVE")

    def test_snapshot_steps_are_not_recorded_as_probe_steps(self):
        ex = ScriptedExecutor(router(snap=json.dumps({"total": 1})))
        run = run_probe_once(make_probe(), ex, state_check=self.SNAP)
        self.assertNotIn("snap", [s.name for s in run.steps])

    def test_builtin_snapshot_is_read_only(self):
        for verb in ("createSession", "addElement", "removeElement", "setName"):
            self.assertNotIn(verb, STATE_SNAPSHOT.code)


class SkipReasonNormalizationTests(unittest.TestCase):
    def test_ids_in_a_skip_reason_are_normalized(self):
        uid = "0f8fad5b-d9cb-469f-a165-70867728950e"
        ex = ScriptedExecutor(router(pre=json.dumps({"ok": False, "reason": f"element {uid} missing"})))
        report = run_probe(make_probe(), ex, repeat=1)
        self.assertEqual(report.runs[0].skipped_reason, "element <ID:1> missing")


class NoProjectCliTests(unittest.TestCase):
    def setUp(self):
        self.shim = StubShim().start()
        self.addCleanup(self.shim.stop)
        self.shim.handler = lambda body: (200, {"ok": True, "result": json.dumps({"ok": True, "hasProject": False})})

    def test_probes_that_need_a_project_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli("run", "--url", self.shim.url, "--probe", "P-ELM-001",
                                   "--repeat", "1", "--out", tmp)
        self.assertEqual(code, 2)
        self.assertIn("P-ELM-001", err)

    def test_the_environment_probe_still_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = run_cli("run", "--url", self.shim.url, "--probe", "P-ENV-001",
                                 "--repeat", "1", "--out", tmp)
        self.assertEqual(code, 0)


class CleanupConventionTests(unittest.TestCase):
    """CLEANUP only removes "__probe_*" elements owned directly by the root model."""

    ADD_TO_ROOT = re.compile(r"addElement\(\s*(\w+)\s*,\s*primaryModel\s*\)")

    def test_everything_added_to_the_root_is_named_for_cleanup(self):
        for p in builtin().all():
            for step in [*p.setup, p.action]:
                for var in self.ADD_TO_ROOT.findall(step.code):
                    with self.subTest(probe=p.id, step=step.name, var=var):
                        self.assertRegex(step.code, rf'{var}\.setName\("__probe_')

    def test_only_the_environment_probe_runs_without_a_project(self):
        self.assertEqual([p.id for p in builtin().all() if not p.needs_project], ["P-ENV-001"])


if __name__ == "__main__":
    unittest.main()
