"""CL-ELM-002 Get and query elements."""
import uuid

from contract_constants import (CANONICAL_TYPE, ELEMENT_FIELDS, QUERY_LIMIT_MAX, ROOT_TYPE,
                                SUPPORTED_TYPES)

from .base import ConformanceCase, declared_scenario, needs

QUERY = "/api/v1/elements/query"


def unique(prefix="conf"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class GetElementTests(ConformanceCase):
    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_002_01_get_returns_exactly_what_create_returned(self):
        root = self.root_id()
        checked = 0
        for token in SUPPORTED_TYPES:
            with self.subTest(token=token):
                resp = self.post("/api/v1/elements", {"type": token, "name": unique(), "parent_id": root})
                if resp.status != 200:
                    continue  # B6 and B1 decide which tokens a root parent accepts; not this test's concern
                created = self.assert_ok(resp)
                self.assertEqual(created["type"], CANONICAL_TYPE.get(token, token))
                self.assertEqual(self.assert_ok(self.get_element(created["id"])), created)
                checked += 1
        self.assertGreater(checked, 0, "no token could be created under the root")

    @needs("uml-project", "sysml-project")
    def test_t_elm_002_01b_root_is_reported_as_model(self):
        root = self.root_id()
        data = self.assert_ok(self.get_element(root))
        self.assertEqual(set(data), set(ELEMENT_FIELDS))
        self.assertEqual((data["id"], data["type"], data["parent_id"]), (root, ROOT_TYPE, None))
        self.assertIsInstance(data["applied_stereotypes"], list)

    @needs("uml-project", "sysml-project")
    def test_t_elm_002_02_unknown_id(self):
        missing = "no-such-element-" + uuid.uuid4().hex
        self.assert_error(self.get_element(missing), "ELEMENT_NOT_FOUND", details={"id": missing})

    @needs("uml-project", "sysml-project")
    def test_t_elm_002_02b_ids_are_one_percent_encoded_path_segment(self):
        """G-011: split the raw path on '/', then percent-decode each segment."""
        self.assert_error(self.get("/api/v1/elements/no%2Fsuch%20id"), "ELEMENT_NOT_FOUND",
                          details={"id": "no/such id"})

    @needs()
    def test_t_elm_002_02c_literal_segments_win_over_templates(self):
        """G-011: /api/v1/elements/query is the query route, never an element ID."""
        self.assert_error(self.get("/api/v1/elements/query"), "METHOD_NOT_ALLOWED")

    @needs("no-project")
    def test_t_elm_002_07_no_project(self):
        self.assert_error(self.get_element("any-id"), "NO_ACTIVE_PROJECT", details={})
        self.assert_error(self.query(parent_id="any-id"), "NO_ACTIVE_PROJECT", details={})


class QueryTests(ConformanceCase):
    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_002_03_filters_narrow_exactly(self):
        # Sibling names stay distinct: duplicate names are OPEN (CL-ELM-001 B5).
        pkg = self.fresh_package()
        a = self.create_ok("Class", "alpha", pkg)
        g = self.create_ok("Interface", "gamma", pkg)
        b = self.create_ok("Class", "beta", pkg)
        ids = lambda items: sorted(i["id"] for i in items)

        self.assertEqual(ids(self.query_all(parent_id=pkg)), sorted([a["id"], g["id"], b["id"]]))
        self.assertEqual(ids(self.query_all(parent_id=pkg, name="alpha")), [a["id"]])
        self.assertEqual(ids(self.query_all(parent_id=pkg, type="Class")), sorted([a["id"], b["id"]]))
        self.assertEqual(ids(self.query_all(parent_id=pkg, type="Class", name="beta")), [b["id"]])
        self.assertEqual(self.query_all(parent_id=pkg, type="Interface", name="alpha"), [], "filters combine with AND")
        self.assertEqual(self.query_all(parent_id=pkg, name="ALPHA"), [], "name match is case-sensitive")
        self.assertEqual(self.query_all(parent_id=pkg, type="Widget"), [], "unknown type values match nothing")
        for item in self.query_all(parent_id=pkg):
            self.assertEqual(self.assert_ok(self.get_element(item["id"])), item)

    @needs("sysml-project", mutates=True)
    def test_t_elm_002_03b_type_and_stereotype_filters_do_not_follow_subtyping(self):
        pkg = self.fresh_package()
        block = self.create_ok("Block", unique(), pkg)
        cls = self.create_ok("Class", unique(), pkg)
        self.assertEqual([i["id"] for i in self.query_all(parent_id=pkg, type="Class")], [cls["id"]])
        self.assertEqual([i["id"] for i in self.query_all(parent_id=pkg, type="Block")], [block["id"]])
        self.assertEqual([i["id"] for i in self.query_all(parent_id=pkg, stereotype="Block")], [block["id"]])

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_002_04_paging_returns_every_child_once_with_no_empty_last_page(self):
        pkg = self.fresh_package()
        created = [self.create_ok("Class", f"c{i}", pkg)["id"] for i in range(5)]
        for limit in (1, 2, 4, 5, 6, 100):
            with self.subTest(limit=limit):
                items = self.query_all(parent_id=pkg, limit=limit)
                got = [i["id"] for i in items]
                self.assertEqual(len(got), len(set(got)), "an item was returned twice")
                self.assertEqual(sorted(got), sorted(created))
                first = self.assert_ok(self.query(parent_id=pkg, limit=limit))
                self.assertEqual(len(first["items"]), min(limit, 5))
                self.assertEqual(first["next_cursor"] is None, limit >= 5)

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_002_04b_order_is_stable_between_queries(self):
        pkg = self.fresh_package()
        for i in range(4):
            self.create_ok("Class", f"s{i}", pkg)
        first = [i["id"] for i in self.query_all(parent_id=pkg, limit=3)]
        again = [i["id"] for i in self.query_all(parent_id=pkg)]
        self.assertEqual(first, again)

    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_elm_002_05_invalid_cursors(self):
        pkg = self.fresh_package()
        for i in range(3):
            self.create_ok("Class", f"k{i}", pkg)
        cursor = self.assert_ok(self.query(parent_id=pkg, limit=1))["next_cursor"]
        self.assertIsInstance(cursor, str)
        bad = {"field": "cursor", "reason": "invalid"}
        self.assert_error(self.query(parent_id=pkg, cursor="not-a-cursor"), "INVALID_REQUEST", details=bad)
        self.assert_error(self.query(parent_id=pkg, name="k1", cursor=cursor), "INVALID_REQUEST", details=bad)
        other = self.fresh_package()
        self.assert_error(self.query(parent_id=other, cursor=cursor), "INVALID_REQUEST", details=bad)
        # B8: the limit may change between pages.
        self.assert_ok(self.query(parent_id=pkg, limit=2, cursor=cursor))

    @needs("uml-project", mutates=True)
    def test_t_elm_002_06_a_refused_create_leaves_nothing_behind(self):
        """Closes CD-005: CL-ELM-001 B1 and B2 are now observable over HTTP."""
        pkg = self.fresh_package()
        name = unique("refused")
        resp = self.post("/api/v1/elements", {"type": "Block", "name": name, "parent_id": pkg})
        self.assert_error(resp, "REQUIRED_PROFILE_MISSING")
        self.assertEqual(self.query_all(parent_id=pkg), [])

    @needs("uml-project", "sysml-project")
    def test_t_elm_002_08_unknown_parent(self):
        missing = "missing-" + uuid.uuid4().hex
        self.assert_error(self.query(parent_id=missing), "PARENT_NOT_FOUND", details={"parent_id": missing})

    @needs()
    def test_t_elm_002_09_invalid_requests(self):
        ok = {"parent_id": "p"}
        cases = [
            ("not json", b"nope", {"reason": "not_a_json_object"}),
            ("json array", b"[]", {"reason": "not_a_json_object"}),
            ("unknown field", {**ok, "page": 2}, {"field": "page", "reason": "unknown"}),
            ("first unknown field alphabetically", {**ok, "zeta": 1, "alpha": 2},
             {"field": "alpha", "reason": "unknown"}),
            ("missing parent_id", {}, {"field": "parent_id", "reason": "missing"}),
            ("parent_id not a string", {"parent_id": 7}, {"field": "parent_id", "reason": "wrong_type"}),
            ("blank parent_id", {"parent_id": " "}, {"field": "parent_id", "reason": "blank"}),
            ("type null", {**ok, "type": None}, {"field": "type", "reason": "wrong_type"}),
            ("blank name", {**ok, "name": ""}, {"field": "name", "reason": "blank"}),
            ("stereotype not a string", {**ok, "stereotype": ["Block"]},
             {"field": "stereotype", "reason": "wrong_type"}),
            ("limit not an integer", {**ok, "limit": "10"}, {"field": "limit", "reason": "wrong_type"}),
            ("limit boolean", {**ok, "limit": True}, {"field": "limit", "reason": "wrong_type"}),
            ("limit fraction", {**ok, "limit": 2.5}, {"field": "limit", "reason": "wrong_type"}),
            ("limit zero", {**ok, "limit": 0}, {"field": "limit", "reason": "out_of_range"}),
            ("limit too big", {**ok, "limit": QUERY_LIMIT_MAX + 1}, {"field": "limit", "reason": "out_of_range"}),
            ("cursor not a string", {**ok, "cursor": 3}, {"field": "cursor", "reason": "wrong_type"}),
        ]
        for label, body, details in cases:
            with self.subTest(case=label):
                resp = self.post(QUERY, raw=body) if isinstance(body, bytes) else self.post(QUERY, body)
                self.assert_error(resp, "INVALID_REQUEST", details=details)

    @needs("uml-project", "sysml-project")
    def test_t_elm_002_09b_null_cursor_means_first_page_and_max_limit_is_allowed(self):
        root = self.root_id()
        self.assert_ok(self.query(parent_id=root, cursor=None))
        self.assert_ok(self.query(parent_id=root, limit=QUERY_LIMIT_MAX))
