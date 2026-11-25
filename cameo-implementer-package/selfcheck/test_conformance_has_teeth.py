"""Fault injection: each deliberately broken fake must be caught by the intended test."""
import unittest

from conformance.base import non_loopback_ip

from .helpers import run_suite


class ConformanceHasTeeth(unittest.TestCase):
    def assert_detected(self, fault, scenario, expected_test):
        result = run_suite(scenario, faults=(fault,))
        failing = [t.id() for t, _ in result.failures + result.errors]
        self.assertTrue(any(expected_test in f for f in failing),
                        f"fault {fault!r} was not caught by {expected_test}; failing: {failing}")

    def test_accepting_unknown_types_is_caught(self):
        self.assert_detected("accept_any_type", "sysml-project", "t_elm_001_02b")

    def test_silent_fallback_to_plain_uml_is_caught(self):
        self.assert_detected("sysml_without_profile_ok", "uml-project", "t_elm_001_03")

    def test_wrong_error_precedence_is_caught(self):
        self.assert_detected("check_parent_before_type", "sysml-project", "t_elm_001_10b")

    def test_non_envelope_404_is_caught(self):
        self.assert_detected("html_404", "sysml-project", "t_glb_001_01")

    def test_trimming_names_is_caught(self):
        self.assert_detected("trim_names", "sysml-project", "t_elm_001_01b")

    # ---- v0.4: capabilities, get and query, guarded delete
    def test_unlisted_route_is_caught(self):
        self.assert_detected("capabilities_missing_route", "no-project", "t_hsk_002_03")

    def test_decoding_before_splitting_the_path_is_caught(self):
        self.assert_detected("decode_before_split", "sysml-project", "t_elm_002_02b")

    def test_template_shadowing_a_literal_route_is_caught(self):
        self.assert_detected("template_shadows_literal", "no-project", "t_elm_002_02c")

    def test_get_disagreeing_with_create_is_caught(self):
        self.assert_detected("get_omits_stereotypes", "sysml-project", "t_elm_002_01")

    def test_type_filter_following_subtypes_is_caught(self):
        self.assert_detected("type_filter_follows_subtyping", "sysml-project", "t_elm_002_03b")

    def test_trailing_empty_page_is_caught(self):
        self.assert_detected("query_trailing_empty_page", "uml-project", "t_elm_002_04")

    def test_preview_that_deletes_is_caught(self):
        self.assert_detected("preview_commits", "uml-project", "t_elm_003_01")

    def test_previewing_the_root_is_caught(self):
        self.assert_detected("preview_allows_root", "uml-project", "t_elm_003_04")

    def test_truthy_strings_committing_a_delete_is_caught(self):
        self.assert_detected("truthy_allow_write", "uml-project", "t_elm_003_07")

    def test_orphaned_children_after_delete_are_caught(self):
        self.assert_detected("delete_keeps_children", "uml-project", "t_elm_003_03")

    @unittest.skipIf(non_loopback_ip() is None, "no non-loopback interface in this environment")
    def test_binding_all_interfaces_is_caught(self):
        self.assert_detected("bind_all_interfaces", "sysml-project", "t_hsk_001_05")


if __name__ == "__main__":
    unittest.main()
