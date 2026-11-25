import itertools
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from cameo_probe.executors import ScriptedExecutor
from cameo_probe.model import ExecResult, Probe, Step
from cameo_probe.runner import (PRELUDE, capture_environment, run_probe,
                                run_probe_once, write_reports)

OK = json.dumps({"ok": True})
PHASES = ("pre", "setup", "action", "observe", "teardown")


def make_probe(**over):
    base = dict(
        id="P-TST-001", family="tests", hypothesis="h", clauses=("CL-TST-001",),
        precondition=Step("pre", "// step:pre"),
        setup=(Step("s1", "// step:setup"),),
        action=Step("act", "// step:action"),
        observe=(Step("obs", "// step:observe"),),
        teardown=(Step("td", "// step:teardown"),),
    )
    base.update(over)
    return Probe(**base)


def router(**table):
    """Scripted handler choosing a response by the '// step:<name>' marker in the code."""
    full = {name: OK for name in PHASES}
    full.update(table)

    def handler(code):
        for marker, response in full.items():
            if f"// step:{marker}" in code:
                return response() if callable(response) else response
        raise AssertionError(f"no route for {code!r}")

    return handler


class RunOnceTests(unittest.TestCase):
    def test_prelude_is_prepended_to_every_snippet(self):
        ex = ScriptedExecutor(router())
        run_probe_once(make_probe(), ex)
        self.assertTrue(ex.calls)
        self.assertTrue(all(call.startswith(PRELUDE) for call in ex.calls))

    def test_phases_run_in_order_and_are_recorded(self):
        run = run_probe_once(make_probe(), ScriptedExecutor(router()))
        self.assertEqual(run.outcome, "completed")
        self.assertEqual([s.phase for s in run.steps],
                         ["precondition", "setup", "action", "observe", "teardown"])

    def test_unsatisfied_precondition_skips_everything_else(self):
        ex = ScriptedExecutor(router(pre=json.dumps({"ok": False, "reason": "SysML present"})))
        run = run_probe_once(make_probe(), ex)
        self.assertEqual(run.outcome, "skipped")
        self.assertEqual(run.skipped_reason, "SysML present")
        self.assertEqual(len(ex.calls), 1)

    def test_action_failure_is_a_probe_failure_but_teardown_still_runs(self):
        failing = ExecResult(ok=False, error_type="MissingMethodException", error_message="nope")
        run = run_probe_once(make_probe(), ScriptedExecutor(router(action=failing)))
        self.assertEqual(run.outcome, "probe_failure")
        self.assertEqual(run.steps[-1].phase, "teardown")
        self.assertNotIn("observe", [s.phase for s in run.steps])

    def test_setup_failure_stops_before_the_action_and_runs_teardown(self):
        failing = ExecResult(ok=False, error_type="Boom")
        run = run_probe_once(make_probe(), ScriptedExecutor(router(setup=failing)))
        self.assertEqual(run.outcome, "probe_failure")
        self.assertEqual([s.phase for s in run.steps], ["precondition", "setup", "teardown"])

    def test_teardown_failure_downgrades_the_run(self):
        failing = ExecResult(ok=False, error_type="Boom")
        run = run_probe_once(make_probe(), ScriptedExecutor(router(teardown=failing)))
        self.assertEqual(run.outcome, "probe_failure")

    def test_non_json_values_are_kept_as_raw_strings(self):
        run = run_probe_once(make_probe(), ScriptedExecutor(router(action="plain text")))
        action = [s for s in run.steps if s.phase == "action"][0]
        self.assertEqual(action.value, "plain text")


class ReportTests(unittest.TestCase):
    def test_stable_after_normalization_even_though_real_ids_differ(self):
        ex = ScriptedExecutor(router(action=lambda: json.dumps({"ok": True, "id": str(uuid.uuid4())})))
        report = run_probe(make_probe(), ex, repeat=3)
        self.assertEqual(report.stability, "stable")
        self.assertEqual(report.differing_steps, [])

    def test_flaky_when_behaviour_differs_between_runs(self):
        counter = itertools.count()
        ex = ScriptedExecutor(router(action=lambda: json.dumps({"ok": True, "n": next(counter)})))
        report = run_probe(make_probe(), ex, repeat=3)
        self.assertEqual(report.stability, "flaky")
        self.assertEqual(report.differing_steps, ["action:act"])

    def test_evidence_levels(self):
        cases = [
            (False, "reviewed", False, "SCRIPTED"),
            (True, "draft", False, "LIVE_DRAFT"),
            (True, "reviewed", False, "LIVE"),
            (True, "reviewed", True, "INCONCLUSIVE"),
        ]
        for pretend_live, status, flaky, expected in cases:
            with self.subTest(live=pretend_live, status=status, flaky=flaky):
                counter = itertools.count()
                action = (lambda: json.dumps({"n": next(counter)})) if flaky else OK
                ex = ScriptedExecutor(router(action=action), pretend_live=pretend_live)
                report = run_probe(make_probe(status=status), ex, repeat=2)
                self.assertEqual(report.evidence_level, expected)

    def test_live_probe_failure_is_inconclusive(self):
        failing = ExecResult(ok=False, error_type="Boom")
        ex = ScriptedExecutor(router(action=failing), pretend_live=True)
        report = run_probe(make_probe(status="reviewed"), ex, repeat=2)
        self.assertEqual(report.evidence_level, "INCONCLUSIVE")

    def test_all_skipped_reports_skipped(self):
        ex = ScriptedExecutor(router(pre=json.dumps({"ok": False, "reason": "no"})), pretend_live=True)
        report = run_probe(make_probe(), ex, repeat=2)
        self.assertEqual(report.evidence_level, "SKIPPED")
        self.assertEqual(report.stability, "n/a")

    def test_digest_ignores_real_ids(self):
        def build():
            ex = ScriptedExecutor(router(action=lambda: json.dumps({"id": str(uuid.uuid4())})))
            return run_probe(make_probe(), ex, repeat=2)

        self.assertEqual(build().digest, build().digest)

    def test_timings_are_summarised_per_step_across_runs(self):
        durations = iter([10.0, 20.0, 30.0])

        def handler(code):
            if "// step:action" in code:
                return ExecResult(ok=True, value=OK, duration_ms=next(durations))
            return OK

        probe = make_probe(precondition=None, setup=(), observe=(), teardown=())
        report = run_probe(probe, ScriptedExecutor(handler), repeat=3)
        self.assertEqual(report.timings_ms["action:act"], [10.0, 20.0, 30.0])

    def test_repeat_must_be_positive(self):
        with self.assertRaises(ValueError):
            run_probe(make_probe(), ScriptedExecutor(router()), repeat=0)


class WriteTests(unittest.TestCase):
    def test_scripted_reports_never_land_in_the_evidence_tree(self):
        report = run_probe(make_probe(), ScriptedExecutor(router()), repeat=1)
        with tempfile.TemporaryDirectory() as tmp:
            (path,) = write_reports([report], tmp)
            self.assertEqual(path, Path(tmp) / "_scratch" / "P-TST-001.json")

    def test_live_reports_land_under_their_family_and_are_deterministic(self):
        def build(root):
            ex = ScriptedExecutor(router(), pretend_live=True)
            return write_reports([run_probe(make_probe(), ex, repeat=2)], root)[0]

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = build(a), build(b)
            self.assertEqual(first.relative_to(a), Path("tests/P-TST-001.json"))
            self.assertEqual(first.read_text(), second.read_text())
            data = json.loads(first.read_text())
            self.assertNotIn("duration_ms", data["runs"][0]["steps"][0])
            self.assertEqual(data["evidence_level"], "LIVE_DRAFT")


class EnvironmentTests(unittest.TestCase):
    def test_capture_environment_parses_the_fingerprint(self):
        ex = ScriptedExecutor(lambda code: json.dumps({"java": "17", "hasProject": True}))
        self.assertEqual(capture_environment(ex)["java"], "17")

    def test_capture_environment_reports_failure(self):
        ex = ScriptedExecutor(lambda code: ExecResult(ok=False, error_type="ConnectionError",
                                                      error_message="refused"))
        self.assertEqual(capture_environment(ex)["error"], "ConnectionError")


if __name__ == "__main__":
    unittest.main()
