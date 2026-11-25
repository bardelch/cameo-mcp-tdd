import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cameo_probe.cli import main
from tests.stub_shim import StubShim


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_list_shows_builtin_probes(self):
        code, out, _ = run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("P-ENV-001", out)
        self.assertIn("P-ELM-001", out)

    def test_list_filters_by_family(self):
        _, out, _ = run_cli("list", "--family", "elements")
        self.assertIn("P-ELM-001", out)
        self.assertNotIn("P-ENV-001", out)

    def test_unknown_probe_id_is_a_usage_error(self):
        code, _, err = run_cli("run", "--url", "http://127.0.0.1:1/x", "--probe", "P-NOP-999")
        self.assertEqual(code, 2)
        self.assertIn("P-NOP-999", err)

    def test_run_against_a_shim_writes_evidence(self):
        shim = StubShim().start()
        self.addCleanup(shim.stop)
        shim.handler = lambda body: (200, {"ok": True, "result": '{"ok": true}'})
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_cli("run", "--url", shim.url, "--probe", "P-ELM-001",
                                   "--repeat", "2", "--out", tmp)
            self.assertEqual(code, 0)
            data = json.loads((Path(tmp) / "elements" / "P-ELM-001.json").read_text())
            self.assertEqual(data["evidence_level"], "LIVE_DRAFT")
            self.assertEqual(data["stability"], "stable")
            self.assertEqual(data["environment"]["executor"]["kind"], "http")
            self.assertIn("P-ELM-001", out)

    def test_run_exits_nonzero_when_the_shim_is_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = run_cli("run", "--url", "http://127.0.0.1:9/probe", "--probe", "P-ENV-001",
                                 "--repeat", "1", "--out", tmp, "--timeout", "1")
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()


class TokenAndDoctorCliTests(unittest.TestCase):
    def test_run_sends_the_token_header(self):
        shim = StubShim().start()
        self.addCleanup(shim.stop)
        shim.handler = lambda body: (200, {"ok": True, "result": '{"ok": true}'})
        with tempfile.TemporaryDirectory() as tmp:
            run_cli("run", "--url", shim.url, "--probe", "P-ELM-001", "--repeat", "1",
                    "--out", tmp, "--token", "abc")
        self.assertTrue(shim.headers)
        self.assertTrue(all(h.get("x-probe-token") == "abc" for h in shim.headers))

    def test_doctor_passes_on_a_healthy_shim(self):
        from tests.fake_shim import FakeShim
        shim = FakeShim().start()
        self.addCleanup(shim.stop)
        code, out, _ = run_cli("doctor", "--url", shim.url, "--token", "secret")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS  ping", out)

    def test_doctor_exits_nonzero_when_a_check_fails(self):
        from tests.fake_shim import FakeShim
        shim = FakeShim(faults=("no_error_propagation",)).start()
        self.addCleanup(shim.stop)
        code, out, _ = run_cli("doctor", "--url", shim.url, "--token", "secret")
        self.assertEqual(code, 1)
        self.assertIn("FAIL  exception_is_reported", out)

    def test_doctor_reads_the_token_from_the_environment(self):
        import os
        from unittest import mock
        from tests.fake_shim import FakeShim
        shim = FakeShim().start()
        self.addCleanup(shim.stop)
        with mock.patch.dict(os.environ, {"CAMEO_PROBE_TOKEN": "secret"}):
            code, _, _ = run_cli("doctor", "--url", shim.url)
        self.assertEqual(code, 0)
