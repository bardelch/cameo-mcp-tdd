import socket
import time
import unittest

from cameo_probe.executors import HttpExecutor, ScriptedExecutor
from cameo_probe.model import ExecResult
from tests.stub_shim import StubShim


class ScriptedExecutorTests(unittest.TestCase):
    def test_returns_queue_in_order_and_records_calls(self):
        ex = ScriptedExecutor(["a", ExecResult(ok=False, error_type="Boom")])
        self.assertEqual(ex.execute("one"), ExecResult(ok=True, value="a"))
        self.assertEqual(ex.execute("two").error_type, "Boom")
        self.assertEqual(ex.calls, ["one", "two"])

    def test_fails_loudly_when_unscripted(self):
        with self.assertRaisesRegex(AssertionError, "unscripted"):
            ScriptedExecutor([]).execute("x")

    def test_accepts_a_callable(self):
        self.assertEqual(ScriptedExecutor(lambda code: code.upper()).execute("abc").value, "ABC")

    def test_is_not_live_unless_pretending(self):
        self.assertFalse(ScriptedExecutor([]).is_live)
        self.assertTrue(ScriptedExecutor([], pretend_live=True).is_live)


class HttpExecutorTests(unittest.TestCase):
    def setUp(self):
        self.shim = StubShim().start()
        self.addCleanup(self.shim.stop)

    def test_success(self):
        self.shim.handler = lambda body: (200, {"ok": True, "result": '{"a": 1}'})
        ex = HttpExecutor(self.shim.url, thread="edt")
        res = ex.execute("return 1")
        self.assertTrue(res.ok)
        self.assertEqual(res.value, '{"a": 1}')
        self.assertGreaterEqual(res.duration_ms, 0)
        self.assertEqual(self.shim.requests, [{"code": "return 1", "thread": "edt"}])
        self.assertTrue(ex.is_live)

    def test_remote_error_is_reported(self):
        self.shim.handler = lambda body: (
            200, {"ok": False, "error_type": "MissingMethodException", "error_message": "no such method"})
        res = HttpExecutor(self.shim.url).execute("x")
        self.assertEqual((res.ok, res.error_type, res.error_message),
                         (False, "MissingMethodException", "no such method"))

    def test_http_errors_are_reported(self):
        self.shim.handler = lambda body: (500, {"oops": True})
        res = HttpExecutor(self.shim.url).execute("x")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_type, "HttpError")
        self.assertIn("500", res.error_message)

    def test_malformed_protocol_is_reported(self):
        self.shim.handler = lambda body: (200, {"unexpected": 1})
        res = HttpExecutor(self.shim.url).execute("x")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_type, "ProtocolError")

    def test_connection_refused(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        res = HttpExecutor(f"http://127.0.0.1:{port}/probe", timeout_s=1).execute("x")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_type, "ConnectionError")

    def test_timeout(self):
        def slow(body):
            time.sleep(0.6)
            return 200, {"ok": True, "result": "{}"}

        self.shim.handler = slow
        res = HttpExecutor(self.shim.url, timeout_s=0.1).execute("x")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_type, "Timeout")

    def test_describe_names_the_protocol(self):
        info = HttpExecutor("http://127.0.0.1:1/probe", thread="http").describe()
        self.assertEqual(info["kind"], "http")
        self.assertEqual(info["thread"], "http")
        self.assertEqual(info["protocol"], "probe-shim-v0")


if __name__ == "__main__":
    unittest.main()
