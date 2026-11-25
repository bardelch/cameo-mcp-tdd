"""CL-HSK-001 Status."""
import socket
import urllib.parse

from contract_constants import STATUS_FIELDS

from .base import ConformanceCase, declared_scenario, needs, non_loopback_ip, target_url


class StatusTests(ConformanceCase):
    @needs()
    def test_t_hsk_001_01_status_schema(self):
        data = self.assert_ok(self.get("/api/v1/status"))
        self.assertEqual(set(data), set(STATUS_FIELDS))
        self.assertIsInstance(data["plugin_version"], str)
        self.assertIs(type(data["api_version"]), int)
        self.assertTrue(data["cameo_version"] is None or isinstance(data["cameo_version"], str))
        self.assertIsInstance(data["project_open"], bool)
        self.assertIs(type(data["port"]), int)
        if declared_scenario():
            self.assertEqual(data["project_open"], declared_scenario() != "no-project")

    @needs("no-project")
    def test_t_hsk_001_02_status_works_without_a_project(self):
        data = self.assert_ok(self.get("/api/v1/status"))
        self.assertIs(data["project_open"], False)

    @needs()
    def test_t_hsk_001_05_binds_loopback_only(self):
        """A-004: the plugin must not be reachable on a non-loopback address."""
        parsed = urllib.parse.urlparse(target_url())
        if parsed.hostname not in ("127.0.0.1", "localhost"):
            self.skipTest("target is not a loopback URL")
        ip = non_loopback_ip()
        if ip is None:
            self.skipTest("this machine has no non-loopback address to try")
        with self.assertRaises(OSError, msg=f"plugin answered on {ip}:{parsed.port}"):
            socket.create_connection((ip, parsed.port), timeout=1).close()
