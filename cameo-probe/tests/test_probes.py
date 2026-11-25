import re
import unittest

from cameo_probe.model import Probe, Step
from cameo_probe.registry import Registry, builtin


def probe(pid="P-ABC-001", **over):
    base = dict(id=pid, family="f", hypothesis="h", action=Step("a", "return 1"))
    base.update(over)
    return Probe(**base)


class ProbeValidationTests(unittest.TestCase):
    def test_rejects_bad_ids_statuses_clauses_and_blank_hypotheses(self):
        for bad in (dict(pid="bad"), dict(status="weird"), dict(clauses=("nope",)), dict(hypothesis=" ")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe(**bad)


class RegistryTests(unittest.TestCase):
    def test_rejects_duplicates_and_filters(self):
        reg = Registry([probe("P-ABC-001", family="x"), probe("P-ABC-002", family="y")])
        with self.assertRaises(ValueError):
            reg.register(probe("P-ABC-001"))
        self.assertEqual([p.id for p in reg.select(family="y")], ["P-ABC-002"])
        self.assertEqual([p.id for p in reg.select(ids=["P-ABC-002", "P-ABC-001"])],
                         ["P-ABC-002", "P-ABC-001"])

    def test_unknown_probe_id_raises_keyerror(self):
        with self.assertRaises(KeyError):
            Registry([probe()]).select(ids=["P-NOP-999"])


class BuiltinProbeLintTests(unittest.TestCase):
    """Quality gates every shipped probe must pass before a human reviews it."""

    def setUp(self):
        self.probes = builtin().all()

    def all_steps(self, p):
        steps = list(p.setup) + [p.action] + list(p.observe) + list(p.teardown)
        if p.precondition:
            steps.append(p.precondition)
        return steps

    def test_there_are_builtin_probes_with_unique_ids(self):
        ids = [p.id for p in self.probes]
        self.assertGreaterEqual(len(ids), 5)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_snippet_returns_a_value(self):
        for p in self.probes:
            for step in self.all_steps(p):
                with self.subTest(probe=p.id, step=step.name):
                    self.assertIn("return ", step.code)

    def test_snippets_use_no_import_statements(self):
        for p in self.probes:
            for step in self.all_steps(p):
                with self.subTest(probe=p.id, step=step.name):
                    self.assertIsNone(re.search(r"^\s*import\s", step.code, re.M))

    def test_mutating_probes_clean_up_after_themselves(self):
        for p in self.probes:
            if any("createSession" in s.code for s in [p.action, *p.setup]):
                with self.subTest(probe=p.id):
                    self.assertTrue(p.teardown, "mutating probe has no teardown")

    def test_probes_name_the_contract_clauses_they_inform(self):
        mutating = [p for p in self.probes if p.family == "elements"]
        self.assertTrue(mutating)
        for p in mutating:
            with self.subTest(probe=p.id):
                self.assertTrue(p.clauses)


if __name__ == "__main__":
    unittest.main()


class PhaseOneProbeCoverageTests(unittest.TestCase):
    """Contract v0.4 section 8: every Phase 1 open item has a draft probe."""

    EXPECTED = {
        "P-ELM-012": "CL-ELM-002", "P-ELM-013": "CL-ELM-002",
        "P-ELM-020": "CL-ELM-003", "P-ELM-021": "CL-ELM-003",
        "P-PRJ-001": "CL-PRJ-001",
    }

    def test_phase_one_probes_exist_and_name_their_clause(self):
        probes = {p.id: p for p in builtin().all()}
        for probe_id, clause in self.EXPECTED.items():
            with self.subTest(probe=probe_id):
                self.assertIn(probe_id, probes)
                self.assertIn(clause, probes[probe_id].clauses)
                self.assertEqual(probes[probe_id].status, "draft")
