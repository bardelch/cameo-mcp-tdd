import unittest

from conformance.base import non_loopback_ip
from contract_constants import SCENARIOS

from .helpers import discover, flatten, run_suite


def describe(result):
    return "\n".join(f"{t.id()}\n{tb}" for t, tb in result.failures + result.errors)


class FakePassesConformance(unittest.TestCase):
    def test_every_scenario_passes(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                result = run_suite(scenario)
                self.assertTrue(result.wasSuccessful(), describe(result))
                self.assertGreaterEqual(len(result.passed), 8)

    def test_every_conformance_test_runs_in_at_least_one_scenario(self):
        everything = {t.id() for t in flatten(discover())}
        ran = set()
        for scenario in SCENARIOS:
            ran |= set(run_suite(scenario).passed)
        missing = everything - ran
        if non_loopback_ip() is None:  # that test needs a second network interface
            missing = {m for m in missing if "t_hsk_001_05" not in m}
        self.assertEqual(missing, set(), "tests that never ran in any scenario")


if __name__ == "__main__":
    unittest.main()
