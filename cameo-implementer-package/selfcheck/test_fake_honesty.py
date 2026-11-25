"""The fake must refuse to invent behaviour the contract still lists as OPEN."""
import unittest

from conformance import client
from fake_plugin.server import FakePlugin


class FakeHonesty(unittest.TestCase):
    def setUp(self):
        self.fake = FakePlugin("sysml-project").start()
        self.addCleanup(self.fake.stop)

    def create(self, **body):
        return client.request(self.fake.url, "POST", "/api/v1/elements", json_body=body)

    def root(self):
        return client.request(self.fake.url, "GET", "/api/v1/project").body["data"]["root_model_id"]

    def test_duplicate_sibling_names_are_unmodeled_b5(self):
        root = self.root()
        self.assertEqual(self.create(type="Class", name="dup", parent_id=root).status, 200)
        again = self.create(type="Class", name="dup", parent_id=root)
        self.assertEqual(again.status, 501)
        self.assertEqual(again.body["error"]["details"], {"open_item": "B5"})

    def test_parent_type_compatibility_is_unmodeled_b6(self):
        resp = self.create(type="Stereotype", name="s", parent_id=self.root())
        self.assertEqual(resp.status, 501)
        self.assertEqual(resp.body["error"]["details"], {"open_item": "B6"})


if __name__ == "__main__":
    unittest.main()


class ContractConstantsAreConsistent(unittest.TestCase):
    def test_aliases_map_to_supported_tokens(self):
        from contract_constants import CANONICAL_TYPE, SUPPORTED_TYPES
        for alias, canonical in CANONICAL_TYPE.items():
            self.assertIn(alias, SUPPORTED_TYPES)
            self.assertIn(canonical, SUPPORTED_TYPES)

    def test_error_codes_are_unique_to_one_side(self):
        from contract_constants import ERROR_STATUS, SERVER_ERRORS
        self.assertEqual(set(ERROR_STATUS) & set(SERVER_ERRORS), set())

    def test_every_route_in_the_catalogue_is_served_by_the_fake(self):
        from contract_constants import ROUTES_V1
        from fake_plugin.server import resolve
        for method, path in ROUTES_V1:
            with self.subTest(route=(method, path)):
                match = resolve(path.replace("{id}", "x"))
                self.assertIsNotNone(match)
                self.assertIn(method, match[0])
