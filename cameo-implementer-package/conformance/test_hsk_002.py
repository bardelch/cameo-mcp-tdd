"""CL-HSK-002 Capabilities and compatibility (plugin side).

T-HSK-002-05 (the Python server refuses non-status tools when a route is missing) is a
layer-C test of the Python MCP server and is not part of this black-box suite.
"""
from contract_constants import (API_VERSION, CAPABILITIES_FIELDS, MIN_CLIENT_API_VERSION, ROUTES_V1,
                                SUPPORTED_TYPES)

from .base import ConformanceCase, needs

DUMMY_ID = "conformance-dummy-id"


class CapabilitiesTests(ConformanceCase):
    def capabilities(self):
        return self.assert_ok(self.get("/api/v1/capabilities"))

    @needs()
    def test_t_hsk_002_01_schema(self):
        data = self.capabilities()
        self.assertEqual(set(data), set(CAPABILITIES_FIELDS))
        self.assertIsInstance(data["plugin_version"], str)
        self.assertIs(type(data["api_version"]), int)
        self.assertIs(type(data["min_client_api_version"]), int)
        self.assertLessEqual(data["min_client_api_version"], data["api_version"])
        self.assertIsInstance(data["routes"], list)
        for route in data["routes"]:
            with self.subTest(route=route):
                self.assertEqual(set(route), {"method", "path"})
                self.assertIsInstance(route["method"], str)
                self.assertIsInstance(route["path"], str)
        self.assertIsInstance(data["element_types"], list)

    @needs()
    def test_t_hsk_002_02_every_listed_route_is_served(self):
        """B4: no route is listed that the plugin does not serve. Probes are non-mutating:
        templated IDs are a dummy and every POST body is {} (invalid or preview-only)."""
        for route in self.capabilities()["routes"]:
            with self.subTest(route=route):
                path = route["path"].replace("{id}", DUMMY_ID)
                resp = self.get(path) if route["method"] == "GET" else self.post(path, {})
                body = self.assert_envelope(resp)
                code = (body.get("error") or {}).get("code")
                self.assertNotIn(code, ("ROUTE_NOT_FOUND", "METHOD_NOT_ALLOWED"), body)

    @needs()
    def test_t_hsk_002_03_routes_are_exactly_the_api_v1_catalogue(self):
        data = self.capabilities()
        listed = [(r["method"], r["path"]) for r in data["routes"]]
        self.assertEqual(len(listed), len(set(listed)), "duplicate routes")
        self.assertEqual(set(listed), set(ROUTES_V1))
        self.assertEqual(data["api_version"], API_VERSION)
        self.assertEqual(data["min_client_api_version"], MIN_CLIENT_API_VERSION)

    @needs()
    def test_t_hsk_002_04_element_types_are_the_create_tokens(self):
        types = self.capabilities()["element_types"]
        self.assertEqual(len(types), len(set(types)), "duplicate tokens")
        self.assertEqual(set(types), set(SUPPORTED_TYPES))
