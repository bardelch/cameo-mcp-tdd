"""Acceptance checks for a probe shim (protocol v0).

Run `python -m cameo_probe doctor` before trusting any probe result. It proves the shim
behaves as the protocol says (errors reported, null kept, EDT versus HTTP thread, the four
bindings, the security gates) by running fixed snippets with known answers.
"""
from __future__ import annotations

import http.client
import json
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional

from .executors import HttpExecutor
from .runner import PRELUDE, capture_environment

TOKEN_HEADER = "X-Probe-Token"
BOUND_NAMES = "application,ef,primaryModel,project"
EXPECTED_ESCAPES = "\u00e9\n\"q\" \U0001F600"

# Plain Groovy, no prelude. Each returns a string (or null) with a known expected value.
SNIPPETS: Dict[str, str] = {
    "ping": 'return "pong"',
    "escapes": 'return "\u00e9\\n\\"q\\" \U0001F600"',
    "throws": 'throw new IllegalStateException("boom")',
    "syntax_error": "def = 1 +",
    "null_result": "return null",
    "int_result": "return 42",
    "bound_names": 'return binding.variables.keySet().collect { String.valueOf(it) }.sort().join(",")',
    "project_consistency": ('return [binding.getVariable("project") != null, '
                            'binding.getVariable("primaryModel") != null, '
                            'binding.getVariable("ef") != null].join(",")'),
    "on_edt": "return javax.swing.SwingUtilities.isEventDispatchThread().toString()",
    "groovy_json": "return groovy.json.JsonOutput.toJson([a: 1])",
}

CHECK_NAMES = (
    "ping",
    "json_escapes_roundtrip",
    "exception_is_reported",
    "compile_error_is_reported",
    "null_result_is_null",
    "non_string_result_is_stringified",
    "bound_names_are_the_documented_four",
    "project_binding_is_consistent",
    "default_thread_is_edt",
    "http_thread_is_not_edt",
    "groovy_json_available",
    "harness_prelude_works",
    "probe_p_env_001_runs",
    "rejects_missing_token",
    "rejects_non_json_content_type",
    "rejects_foreign_host_header",
    "get_is_not_allowed",
    "binds_loopback_only",
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "pass" | "fail" | "skip"
    detail: str = ""


def _non_loopback_ip() -> Optional[str]:
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


def _raw(url: str, method: str, *, body: bytes = b"", headers: Optional[Dict[str, str]] = None,
         host: Optional[str] = None, timeout_s: float = 10.0) -> int:
    """One HTTP request with full control of the Host and Content-Type headers; returns the status."""
    parts = urllib.parse.urlparse(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout_s)
    try:
        conn.putrequest(method, parts.path or "/", skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or f"{parts.hostname}:{parts.port}")
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        if method == "POST":
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body if method == "POST" else None)
        response = conn.getresponse()
        response.read()
        return response.status
    finally:
        conn.close()


def _describe(result) -> str:
    return f"{result.error_type}: {result.error_message}" if not result.ok else f"got {result.value!r}"


def run_doctor(url: str, *, token: Optional[str] = None, timeout_s: float = 30.0,
               expect_project: str = "any") -> List[Check]:
    if expect_project not in ("any", "yes", "no"):
        raise ValueError("expect_project must be any, yes or no")
    auth = {TOKEN_HEADER: token} if token else {}
    on_edt = HttpExecutor(url, timeout_s=timeout_s, thread="edt", headers=auth)
    off_edt = HttpExecutor(url, timeout_s=timeout_s, thread="http", headers=auth)
    checks: List[Check] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(name, "pass" if ok else "fail", detail))

    def skip(name: str, reason: str) -> None:
        checks.append(Check(name, "skip", reason))

    ping = on_edt.execute(SNIPPETS["ping"])
    answered = ping.ok and ping.value == "pong"
    record("ping", answered, _describe(ping))
    if not answered:
        for name in CHECK_NAMES[1:]:
            skip(name, "the shim did not answer ping; fix that first")
        return checks

    res = on_edt.execute(SNIPPETS["escapes"])
    record("json_escapes_roundtrip", res.ok and res.value == EXPECTED_ESCAPES, _describe(res))

    res = on_edt.execute(SNIPPETS["throws"])
    record("exception_is_reported",
           (not res.ok) and res.error_type == "java.lang.IllegalStateException"
           and "boom" in (res.error_message or ""), _describe(res))

    res = on_edt.execute(SNIPPETS["syntax_error"])
    record("compile_error_is_reported", (not res.ok) and bool(res.error_type), _describe(res))

    res = on_edt.execute(SNIPPETS["null_result"])
    record("null_result_is_null", res.ok and res.value is None, _describe(res))

    res = on_edt.execute(SNIPPETS["int_result"])
    record("non_string_result_is_stringified", res.ok and res.value == "42", _describe(res))

    res = on_edt.execute(SNIPPETS["bound_names"])
    record("bound_names_are_the_documented_four", res.ok and res.value == BOUND_NAMES, _describe(res))

    res = on_edt.execute(SNIPPETS["project_consistency"])
    seen = {"true,true,true": "yes", "false,false,false": "no"}.get(res.value) if res.ok else None
    record("project_binding_is_consistent", seen is not None and expect_project in ("any", seen),
           _describe(res) + ("" if seen is None else f" (project: {seen})"))

    res = on_edt.execute(SNIPPETS["on_edt"])
    record("default_thread_is_edt", res.ok and res.value == "true", _describe(res))

    res = off_edt.execute(SNIPPETS["on_edt"])
    record("http_thread_is_not_edt", res.ok and res.value == "false", _describe(res))

    res = on_edt.execute(SNIPPETS["groovy_json"])
    record("groovy_json_available", res.ok and res.value == '{"a":1}', _describe(res))

    res = on_edt.execute(PRELUDE + "return __json([ok: true])")
    record("harness_prelude_works", res.ok and res.value == '{"ok":true}', _describe(res))

    fingerprint = capture_environment(on_edt)
    if "error" in fingerprint:
        record("probe_p_env_001_runs", False, f"{fingerprint.get('error')}: {fingerprint.get('message')}")
    else:
        record("probe_p_env_001_runs", True,
               f"java={fingerprint.get('java')}, groovy={fingerprint.get('groovy')}, "
               f"project={fingerprint.get('hasProject')}")

    payload = json.dumps({"code": SNIPPETS["ping"], "thread": "edt"}).encode("utf-8")
    json_type = {"Content-Type": "application/json"}

    def status_check(name, accepted, **request) -> None:
        try:
            status = _raw(url, timeout_s=timeout_s, **request)
        except OSError as exc:
            record(name, False, f"{type(exc).__name__}: {exc}")
            return
        record(name, accepted(status), f"HTTP {status}")

    status_check("rejects_missing_token", lambda s: s in (401, 403),
                 method="POST", body=payload, headers=json_type)
    status_check("rejects_non_json_content_type", lambda s: 400 <= s < 500,
                 method="POST", body=payload, headers={**auth, "Content-Type": "text/plain"})
    status_check("rejects_foreign_host_header", lambda s: 400 <= s < 500,
                 method="POST", body=payload, headers={**auth, **json_type}, host="evil.example")
    status_check("get_is_not_allowed", lambda s: s == 405, method="GET", headers=auth)

    parts = urllib.parse.urlparse(url)
    ip = _non_loopback_ip()
    if parts.hostname not in ("127.0.0.1", "localhost"):
        skip("binds_loopback_only", "the URL is not a loopback address")
    elif ip is None:
        skip("binds_loopback_only", "this machine has no non-loopback address to try")
    else:
        try:
            socket.create_connection((ip, parts.port), timeout=1).close()
            record("binds_loopback_only", False, f"the shim answered on {ip}:{parts.port}")
        except OSError:
            record("binds_loopback_only", True, f"nothing answered on {ip}:{parts.port}")
    return checks
