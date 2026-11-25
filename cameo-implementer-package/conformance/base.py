"""Shared plumbing for the black-box conformance suite.

Target:    CAMEO_CONFORMANCE_URL        e.g. http://127.0.0.1:18740
Scenario:  CAMEO_CONFORMANCE_SCENARIO   no-project | uml-project | sysml-project
Mutation:  CAMEO_CONFORMANCE_DISPOSABLE yes   (required by tests that create elements)

Tests that need a different scenario are skipped, never faked. Run the suite once
per scenario to cover everything.
"""
import os
import socket
import unittest
from typing import Any, Dict, Optional

from contract_constants import ERROR_STATUS

from . import client


def target_url() -> str:
    return os.environ.get("CAMEO_CONFORMANCE_URL", "")


def declared_scenario() -> str:
    return os.environ.get("CAMEO_CONFORMANCE_SCENARIO", "")


def disposable_confirmed() -> bool:
    return os.environ.get("CAMEO_CONFORMANCE_DISPOSABLE", "") == "yes"


def non_loopback_ip() -> Optional[str]:
    """An address of this machine that is not loopback, or None when there is none."""
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith("127."):
                return info[4][0]
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1: nothing is sent for UDP connect
            ip = probe.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def needs(*scenarios: str, mutates: bool = False):
    """Declare which scenarios a test can run in, and whether it creates model elements."""
    def decorate(fn):
        fn.conformance_needs = scenarios
        fn.conformance_mutates = mutates
        return fn
    return decorate


class ConformanceCase(unittest.TestCase):
    def setUp(self) -> None:
        if not target_url():
            self.skipTest("set CAMEO_CONFORMANCE_URL (see README)")
        method = getattr(self, self._testMethodName)
        wanted = getattr(method, "conformance_needs", ())
        if wanted and declared_scenario() not in wanted:
            self.skipTest(f"needs scenario {' or '.join(wanted)}; target declares {declared_scenario() or 'none'}")
        if getattr(method, "conformance_mutates", False) and not disposable_confirmed():
            self.skipTest("creates elements: set CAMEO_CONFORMANCE_DISPOSABLE=yes and use a disposable project")

    # ---- transport ----
    def get(self, path: str) -> client.Response:
        return client.request(target_url(), "GET", path)

    def post(self, path: str, body: Any = None, raw: Optional[bytes] = None) -> client.Response:
        return client.request(target_url(), "POST", path, json_body=body, raw_body=raw)

    # ---- contract assertions ----
    def assert_envelope(self, resp: client.Response) -> Dict[str, Any]:
        """G-001: every reply is {ok:true,data:{...}} or {ok:false,error:{code,message,details}}."""
        self.assertIsInstance(resp.body, dict, f"reply is not a JSON object: {resp.raw[:120]!r}")
        self.assertIsInstance(resp.body.get("ok"), bool, f"missing boolean ok: {resp.body}")
        if resp.body["ok"]:
            self.assertIsInstance(resp.body.get("data"), dict)
            self.assertNotIn("error", resp.body)
        else:
            error = resp.body.get("error")
            self.assertIsInstance(error, dict, f"missing error object: {resp.body}")
            self.assertIsInstance(error.get("code"), str)
            self.assertIsInstance(error.get("message"), str)
            self.assertIsInstance(error.get("details"), dict)
            self.assertNotIn("data", resp.body)
        return resp.body

    def assert_ok(self, resp: client.Response) -> Dict[str, Any]:
        body = self.assert_envelope(resp)
        self.assertEqual(resp.status, 200, resp.raw[:200])
        self.assertIs(body["ok"], True, body)
        return body["data"]

    def assert_error(self, resp: client.Response, code: str, details: Optional[Dict[str, Any]] = None) -> None:
        """G-002 status mapping plus G-001 envelope. Messages are never asserted (D-006)."""
        body = self.assert_envelope(resp)
        self.assertIs(body["ok"], False, body)
        self.assertEqual(body["error"]["code"], code, body)
        self.assertEqual(resp.status, ERROR_STATUS[code], body)
        if details is not None:
            self.assertEqual(body["error"]["details"], details)

    def root_id(self) -> str:
        return self.assert_ok(self.get("/api/v1/project"))["root_model_id"]

    # ---- helpers for tests that build a small tree (callers declare mutates=True) ----
    def create_ok(self, type_: str, name: str, parent_id: str) -> Dict[str, Any]:
        return self.assert_ok(self.post("/api/v1/elements", {"type": type_, "name": name, "parent_id": parent_id}))

    def fresh_package(self, prefix: str = "conf-pkg") -> str:
        """A new, empty Package under the root, so a test sees only the children it creates."""
        import uuid
        return self.create_ok("Package", f"{prefix}-{uuid.uuid4().hex[:8]}", self.root_id())["id"]

    def get_element(self, element_id: str) -> client.Response:
        import urllib.parse
        return self.get("/api/v1/elements/" + urllib.parse.quote(element_id, safe=""))

    def query(self, **body: Any) -> client.Response:
        return self.post("/api/v1/elements/query", body)

    def query_all(self, **body: Any) -> list:
        """Follow next_cursor to the end and return every item, asserting no empty trailing page."""
        items, cursor, pages = [], None, 0
        while True:
            page = self.assert_ok(self.query(**body, **({"cursor": cursor} if cursor else {})))
            pages += 1
            self.assertLess(pages, 10000, "paging did not terminate")
            if cursor is not None:
                self.assertTrue(page["items"], "a cursor led to an empty page (B9: no trailing empty page)")
            items.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                return items

    def delete(self, element_id: str, body: Any = None, raw: Optional[bytes] = None) -> client.Response:
        import urllib.parse
        path = "/api/v1/elements/" + urllib.parse.quote(element_id, safe="") + "/delete"
        return self.post(path, {} if body is None and raw is None else body, raw=raw)
