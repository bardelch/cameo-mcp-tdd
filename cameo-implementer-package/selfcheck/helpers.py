import io
import os
import unittest
from unittest import mock

from contract_constants import SCENARIOS  # noqa: F401  (re-exported for the selfchecks)
from fake_plugin.server import FakePlugin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Recorder(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


def discover():
    return unittest.defaultTestLoader.discover(
        os.path.join(ROOT, "conformance"), pattern="test_*.py", top_level_dir=ROOT)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run_suite(scenario, faults=()):
    """Run the whole conformance suite against a fresh fake plugin."""
    fake = FakePlugin(scenario, faults=faults).start()
    env = {"CAMEO_CONFORMANCE_URL": fake.url, "CAMEO_CONFORMANCE_SCENARIO": scenario,
           "CAMEO_CONFORMANCE_DISPOSABLE": "yes"}
    try:
        with mock.patch.dict(os.environ, env):
            runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=Recorder, verbosity=0)
            return runner.run(discover())
    finally:
        fake.stop()
