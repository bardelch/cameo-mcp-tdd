"""CL-ELM-001 Create element (HTTP-observable behaviour only).

Not covered here because they need control of Cameo internals (layer J, fake Cameo
executor): T-ELM-001-05 atomic failure, -06 one session per request, -07 serialization.
"A request that fails creates nothing" is checked through CL-ELM-002 (T-ELM-002-06).
"""
import uuid

from contract_constants import ELEMENT_FIELDS, SUPPORTED_TYPES, SYSML_TYPES

from .base import ConformanceCase, declared_scenario, needs

PATH = "/api/v1/elements"


def unique(prefix="conf"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class CreateElementTests(ConformanceCase):
    def create(self, **body):
        return self.post(PATH, body)

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_001_01_valid_request_returns_the_documented_schema(self):
        token = "Block" if declared_scenario() == "sysml-project" else "Class"
        name, root = unique(), self.root_id()
        data = self.assert_ok(self.create(type=token, name=name, parent_id=root))
        self.assertEqual(set(data), set(ELEMENT_FIELDS))
        self.assertIsInstance(data["id"], str)
        self.assertTrue(data["id"])
        self.assertEqual((data["type"], data["name"], data["parent_id"]), (token, name, root))
        self.assertEqual(data["applied_stereotypes"], ["Block"] if token == "Block" else [])

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_001_01b_name_is_stored_exactly_as_given(self):
        name = f"  \u00e9 {unique()}  "
        data = self.assert_ok(self.create(type="Class", name=name, parent_id=self.root_id()))
        self.assertEqual(data["name"], name)

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_001_02a_no_supported_token_is_rejected_as_unsupported(self):
        root = self.root_id()
        for token in SUPPORTED_TYPES:
            with self.subTest(token=token):
                resp = self.create(type=token, name=unique(), parent_id=root)
                body = self.assert_envelope(resp)
                code = (body.get("error") or {}).get("code")
                self.assertNotIn(code, ("UNSUPPORTED_TYPE", "INTERNAL_ERROR"), body)

    @needs("uml-project", "sysml-project")
    def test_t_elm_001_02b_other_tokens_are_unsupported(self):
        root = self.root_id()
        for token in ("Widget", "block", "BLOCK", "Package ", "uml:Class"):
            with self.subTest(token=token):
                resp = self.create(type=token, name=unique(), parent_id=root)
                self.assert_error(resp, "UNSUPPORTED_TYPE", details={"type": token})

    @needs("uml-project", mutates=True)
    def test_t_elm_001_03_sysml_types_without_the_profile_are_refused(self):
        root = self.root_id()
        for token in SYSML_TYPES:
            with self.subTest(token=token):
                resp = self.create(type=token, name=unique(), parent_id=root)
                self.assert_error(resp, "REQUIRED_PROFILE_MISSING", details={"stereotype": token})

    @needs("uml-project", "sysml-project")
    def test_t_elm_001_04_unknown_parent(self):
        missing = "no-such-element-" + uuid.uuid4().hex
        resp = self.create(type="Class", name=unique(), parent_id=missing)
        self.assert_error(resp, "PARENT_NOT_FOUND", details={"parent_id": missing})

    @needs()
    def test_t_elm_001_09_invalid_requests(self):
        ok = {"type": "Class", "name": "n", "parent_id": "p"}
        cases = [
            ("not json", b"not json", {"reason": "not_a_json_object"}),
            ("json array", b"[]", {"reason": "not_a_json_object"}),
            ("unknown field", {**ok, "extra": 1}, {"field": "extra", "reason": "unknown"}),
            ("first unknown field alphabetically", {**ok, "zz": 1, "aa": 2}, {"field": "aa", "reason": "unknown"}),
            ("missing type", {"name": "n", "parent_id": "p"}, {"field": "type", "reason": "missing"}),
            ("missing name", {"type": "Class", "parent_id": "p"}, {"field": "name", "reason": "missing"}),
            ("missing parent_id", {"type": "Class", "name": "n"}, {"field": "parent_id", "reason": "missing"}),
            ("type not a string", {**ok, "type": 5}, {"field": "type", "reason": "wrong_type"}),
            ("blank type", {**ok, "type": ""}, {"field": "type", "reason": "blank"}),
            ("blank name", {**ok, "name": "   "}, {"field": "name", "reason": "blank"}),
            ("metaclasses on a Class", {**ok, "metaclasses": ["Class"]},
             {"field": "metaclasses", "reason": "not_allowed"}),
            ("metaclasses not an array", {**ok, "type": "Stereotype", "metaclasses": "Class"},
             {"field": "metaclasses", "reason": "wrong_type"}),
        ]
        for label, body, details in cases:
            with self.subTest(case=label):
                resp = self.post(PATH, raw=body) if isinstance(body, bytes) else self.post(PATH, body)
                self.assert_error(resp, "INVALID_REQUEST", details=details)

    @needs("no-project")
    def test_t_elm_001_10a_no_project_is_a_409(self):
        self.assert_error(self.create(type="Class", name=unique(), parent_id="p"), "NO_ACTIVE_PROJECT", details={})

    @needs("uml-project", "sysml-project")
    def test_t_elm_001_10b_type_is_checked_before_parent(self):
        resp = self.create(type="Widget", name=unique(), parent_id="missing-" + uuid.uuid4().hex)
        self.assert_error(resp, "UNSUPPORTED_TYPE", details={"type": "Widget"})

    @needs("uml-project")
    def test_t_elm_001_10c_parent_is_checked_before_the_profile(self):
        missing = "missing-" + uuid.uuid4().hex
        resp = self.create(type="Block", name=unique(), parent_id=missing)
        self.assert_error(resp, "PARENT_NOT_FOUND", details={"parent_id": missing})

    @needs("no-project")
    def test_t_elm_001_10d_validation_precedes_the_project_check(self):
        resp = self.create(type="Class", parent_id="p")
        self.assert_error(resp, "INVALID_REQUEST", details={"field": "name", "reason": "missing"})
