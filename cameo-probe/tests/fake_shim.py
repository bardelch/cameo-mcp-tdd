"""A Python stand-in for the Groovy shim, used ONLY to test the doctor.

It cannot evaluate Groovy. It recognises the doctor's own snippets and answers the way a
correct shim would; each named fault makes it misbehave in exactly one way.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cameo_probe.doctor import SNIPPETS
from cameo_probe.probes.env import ENV_FINGERPRINT
from cameo_probe.runner import PRELUDE

FAULTS = (
    "no_error_propagation", "stringify_null", "extra_binding", "partial_binding",
    "run_off_edt_always", "run_on_edt_always", "no_token_check", "no_host_check",
    "no_content_type_check", "allow_get", "bind_all_interfaces",
)


class _Failure(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type, self.message = error_type, message


class FakeShim:
    def __init__(self, token="secret", faults=(), project=True):
        unknown = set(faults) - set(FAULTS)
        if unknown:
            raise ValueError(f"unknown faults {sorted(unknown)}")
        self.token, self.faults, self.project = token, frozenset(faults), project
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, status, payload):
                data = json.dumps(payload).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _error(self, status, error_type, message):
                self._reply(status, {"ok": False, "error_type": error_type, "error_message": message})

            def do_GET(self):
                if "allow_get" in outer.faults:
                    return self._reply(200, {"ok": True, "result": "pong"})
                self._error(405, "MethodNotAllowed", "use POST")

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                host = self.headers.get("Host")
                if "no_host_check" not in outer.faults and host not in (
                        f"127.0.0.1:{outer.port}", f"localhost:{outer.port}"):
                    return self._error(403, "ForbiddenHost", "bad Host header")
                if "no_token_check" not in outer.faults and self.headers.get("X-Probe-Token") != outer.token:
                    return self._error(401, "Unauthorized", "missing or wrong token")
                ctype = (self.headers.get("Content-Type") or "").lower()
                if "no_content_type_check" not in outer.faults and not ctype.startswith("application/json"):
                    return self._error(415, "UnsupportedMediaType", "need application/json")
                try:
                    request = json.loads(raw.decode("utf-8"))
                    code, thread = request["code"], request.get("thread", "edt")
                except (ValueError, KeyError, TypeError):
                    return self._error(400, "BadRequest", "expected {code, thread}")
                try:
                    result = outer.evaluate(code, thread)
                except _Failure as failure:
                    return self._reply(200, {"ok": False, "error_type": failure.error_type,
                                             "error_message": failure.message})
                self._reply(200, {"ok": True, "result": result})

            def log_message(self, *args):
                pass

        host = "0.0.0.0" if "bind_all_interfaces" in self.faults else "127.0.0.1"
        self._server = ThreadingHTTPServer((host, 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/probe"

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def evaluate(self, code, thread):
        body = code[len(PRELUDE):] if code.startswith(PRELUDE) else code
        s, f = SNIPPETS, self.faults
        if body == s["ping"]:
            return "pong"
        if body == s["escapes"]:
            return "\u00e9\n\"q\" \U0001F600"
        if body == s["throws"]:
            if "no_error_propagation" in f:
                return ""
            raise _Failure("java.lang.IllegalStateException", "boom")
        if body == s["syntax_error"]:
            raise _Failure("org.codehaus.groovy.control.MultipleCompilationErrorsException", "unexpected token")
        if body == s["null_result"]:
            return "null" if "stringify_null" in f else None
        if body == s["int_result"]:
            return "42"
        if body == s["bound_names"]:
            return "application,ef,primaryModel,project" + (",shim" if "extra_binding" in f else "")
        if body == s["project_consistency"]:
            if "partial_binding" in f:
                return "true,false,true"
            return "true,true,true" if self.project else "false,false,false"
        if body == s["on_edt"]:
            if "run_off_edt_always" in f:
                on = False
            elif "run_on_edt_always" in f:
                on = True
            else:
                on = thread == "edt"
            return "true" if on else "false"
        if body == s["groovy_json"]:
            return '{"a":1}'
        if body == "return __json([ok: true])":
            return '{"ok":true}'
        if body == ENV_FINGERPRINT.code:
            return json.dumps({"java": "17.0.9", "groovy": "3.0.9", "hasProject": self.project,
                               "boundNames": ["application", "ef", "primaryModel", "project"]})
        raise _Failure("FakeShimLimit", "the fake shim cannot evaluate this snippet")
