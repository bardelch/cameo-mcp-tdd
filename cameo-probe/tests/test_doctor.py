import unittest

from cameo_probe.doctor import CHECK_NAMES, run_doctor
from tests.fake_shim import FakeShim

try:
    from cameo_probe.doctor import _non_loopback_ip
except ImportError:  # the red run: doctor does not exist yet
    _non_loopback_ip = lambda: None


def by_name(checks):
    return {c.name: c for c in checks}


class DoctorOnAHealthyShim(unittest.TestCase):
    def setUp(self):
        self.shim = FakeShim().start()
        self.addCleanup(self.shim.stop)

    def test_every_check_passes_or_is_legitimately_skipped(self):
        checks = run_doctor(self.shim.url, token="secret")
        self.assertEqual([c for c in checks if c.status == "fail"], [])
        self.assertGreaterEqual(len([c for c in checks if c.status == "pass"]), 16)

    def test_checks_run_in_the_documented_order(self):
        self.assertEqual([c.name for c in run_doctor(self.shim.url, token="secret")], list(CHECK_NAMES))

    def test_a_wrong_token_stops_after_ping_with_a_clear_message(self):
        checks = run_doctor(self.shim.url, token="wrong")
        self.assertEqual((checks[0].name, checks[0].status), ("ping", "fail"))
        self.assertIn("401", checks[0].detail)
        self.assertTrue(all(c.status == "skip" for c in checks[1:]))

    def test_an_unreachable_shim_stops_after_ping(self):
        checks = run_doctor("http://127.0.0.1:9/probe", token="secret", timeout_s=1)
        self.assertEqual((checks[0].name, checks[0].status), ("ping", "fail"))
        self.assertTrue(all(c.status == "skip" for c in checks[1:]))

    def test_expect_project_yes_fails_when_the_shim_sees_no_project(self):
        shim = FakeShim(project=False).start()
        self.addCleanup(shim.stop)
        checks = by_name(run_doctor(shim.url, token="secret", expect_project="yes"))
        self.assertEqual(checks["project_binding_is_consistent"].status, "fail")

    def test_expect_project_no_passes_when_the_shim_sees_no_project(self):
        shim = FakeShim(project=False).start()
        self.addCleanup(shim.stop)
        checks = by_name(run_doctor(shim.url, token="secret", expect_project="no"))
        self.assertEqual(checks["project_binding_is_consistent"].status, "pass")

    def test_bad_expect_project_value_is_rejected(self):
        with self.assertRaises(ValueError):
            run_doctor(self.shim.url, token="secret", expect_project="maybe")


class DoctorHasTeeth(unittest.TestCase):
    """Each injected shim fault must fail exactly the intended check, and no other."""

    def assert_detected(self, fault, expected):
        shim = FakeShim(faults=(fault,)).start()
        self.addCleanup(shim.stop)
        checks = by_name(run_doctor(shim.url, token="secret"))
        self.assertEqual(checks[expected].status, "fail", f"{fault} not caught by {expected}")
        others = sorted(n for n, c in checks.items() if c.status == "fail" and n != expected)
        self.assertEqual(others, [], f"{fault} also failed {others}")

    def test_swallowed_exceptions(self):
        self.assert_detected("no_error_propagation", "exception_is_reported")

    def test_null_becomes_the_string_null(self):
        self.assert_detected("stringify_null", "null_result_is_null")

    def test_extra_bound_variable(self):
        self.assert_detected("extra_binding", "bound_names_are_the_documented_four")

    def test_half_bound_project(self):
        self.assert_detected("partial_binding", "project_binding_is_consistent")

    def test_edt_request_runs_off_the_edt(self):
        self.assert_detected("run_off_edt_always", "default_thread_is_edt")

    def test_http_request_runs_on_the_edt(self):
        self.assert_detected("run_on_edt_always", "http_thread_is_not_edt")

    def test_missing_token_is_accepted(self):
        self.assert_detected("no_token_check", "rejects_missing_token")

    def test_foreign_host_header_is_accepted(self):
        self.assert_detected("no_host_check", "rejects_foreign_host_header")

    def test_non_json_content_type_is_accepted(self):
        self.assert_detected("no_content_type_check", "rejects_non_json_content_type")

    def test_get_is_accepted(self):
        self.assert_detected("allow_get", "get_is_not_allowed")

    @unittest.skipIf(_non_loopback_ip() is None, "no non-loopback interface in this environment")
    def test_binding_all_interfaces(self):
        self.assert_detected("bind_all_interfaces", "binds_loopback_only")


if __name__ == "__main__":
    unittest.main()
