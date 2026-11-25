"""CL-ELM-003 Delete element, guarded."""
import uuid

from contract_constants import PREVIEW_LIMIT

from .base import ConformanceCase, needs


def unique(prefix="conf"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class DeleteTests(ConformanceCase):
    def small_tree(self):
        """pkg -> (a -> a1), b"""
        pkg = self.fresh_package("del")
        a = self.create_ok("Package", "a", pkg)["id"]
        a1 = self.create_ok("Class", "a1", a)["id"]
        b = self.create_ok("Class", "b", pkg)["id"]
        return pkg, a, a1, b

    def assert_gone(self, *ids):
        for element_id in ids:
            self.assert_error(self.get_element(element_id), "ELEMENT_NOT_FOUND", details={"id": element_id})

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_003_01_preview_is_the_default_and_changes_nothing(self):
        pkg, a, a1, b = self.small_tree()
        before = self.query_all(parent_id=pkg)
        data = self.assert_ok(self.delete(pkg))
        self.assertEqual(set(data), {"preview", "would_delete", "count", "truncated"})
        self.assertIs(data["preview"], True)
        self.assertIs(data["truncated"], False)
        self.assertEqual(data["count"], 4)
        # B9: target first, then owned elements depth-first in containment order.
        self.assertEqual([w["id"] for w in data["would_delete"]], [pkg, a, a1, b])
        for entry in data["would_delete"]:
            self.assertEqual(set(entry), {"id", "type", "name"})
        self.assertEqual(self.query_all(parent_id=pkg), before)
        self.assert_ok(self.delete(pkg, {"allow_write": False}))
        self.assertEqual(self.query_all(parent_id=pkg), before)

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_003_02_commit_deletes_and_a_second_delete_is_not_found(self):
        pkg, a, a1, b = self.small_tree()
        data = self.assert_ok(self.delete(b, {"allow_write": True}))
        self.assertEqual(data, {"preview": False, "deleted_count": 1})
        self.assert_gone(b)
        self.assertEqual([i["id"] for i in self.query_all(parent_id=pkg)], [a])
        self.assert_error(self.delete(b, {"allow_write": True}), "ELEMENT_NOT_FOUND", details={"id": b})

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_003_03_owned_elements_go_with_their_owner(self):
        pkg, a, a1, b = self.small_tree()
        self.assertEqual(self.assert_ok(self.delete(a, {"allow_write": True}))["deleted_count"], 2)
        self.assert_gone(a, a1)
        self.assert_ok(self.get_element(b))

    @needs("uml-project", "sysml-project")
    def test_t_elm_003_04_root_is_protected_even_in_preview(self):
        root = self.root_id()
        for body in ({}, {"allow_write": True}):
            with self.subTest(body=body):
                self.assert_error(self.delete(root, body), "PROTECTED_ELEMENT", details={"id": root})
        self.assert_ok(self.get_element(root))

    @needs("uml-project", "sysml-project")
    def test_t_elm_003_05_unknown_id(self):
        missing = "missing-" + uuid.uuid4().hex
        for body in ({}, {"allow_write": True}):
            with self.subTest(body=body):
                self.assert_error(self.delete(missing, body), "ELEMENT_NOT_FOUND", details={"id": missing})

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_003_06_preview_count_matches_the_commit(self):
        pkg, *_ = self.small_tree()
        preview = self.assert_ok(self.delete(pkg))
        commit = self.assert_ok(self.delete(pkg, {"allow_write": True}))
        self.assertEqual(preview["count"], commit["deleted_count"])

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_003_06b_long_previews_are_truncated_but_commits_are_not(self):
        pkg = self.fresh_package("big")
        for i in range(PREVIEW_LIMIT + 1):
            self.create_ok("Class", f"n{i}", pkg)
        preview = self.assert_ok(self.delete(pkg))
        self.assertEqual((preview["count"], len(preview["would_delete"]), preview["truncated"]),
                         (PREVIEW_LIMIT + 2, PREVIEW_LIMIT, True))
        self.assertEqual(self.assert_ok(self.delete(pkg, {"allow_write": True}))["deleted_count"],
                         PREVIEW_LIMIT + 2)
        self.assert_gone(pkg)

    @needs()
    def test_t_elm_003_07_invalid_requests(self):
        cases = [
            ("empty body", b"", {"reason": "not_a_json_object"}),
            ("json array", b"[]", {"reason": "not_a_json_object"}),
            ("unknown field", {"allow_write": True, "force": True}, {"field": "force", "reason": "unknown"}),
            ("string true does not commit", {"allow_write": "true"}, {"field": "allow_write", "reason": "wrong_type"}),
            ("number does not commit", {"allow_write": 1}, {"field": "allow_write", "reason": "wrong_type"}),
            ("null", {"allow_write": None}, {"field": "allow_write", "reason": "wrong_type"}),
        ]
        for label, body, details in cases:
            with self.subTest(case=label):
                resp = self.delete("any-id", raw=body) if isinstance(body, bytes) else self.delete("any-id", body)
                self.assert_error(resp, "INVALID_REQUEST", details=details)

    @needs("no-project")
    def test_t_elm_003_08_no_project(self):
        self.assert_error(self.delete("any-id"), "NO_ACTIVE_PROJECT", details={})
