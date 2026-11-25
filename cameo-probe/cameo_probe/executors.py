"""Executors run a Groovy snippet somewhere and return its raw result.

ScriptedExecutor is a test double for the harness itself. It is NOT a model of
Cameo: the contract's fake Cameo executor is a separate artifact built from
probe evidence.

HttpExecutor speaks "probe shim protocol v0" to something running inside the
Cameo JVM (decision D-005 in the contract is still open on what that is).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Any, Callable, Dict, Iterable, Optional, Protocol, Union

from .model import ExecResult


class Executor(Protocol):
    is_live: bool

    def describe(self) -> Dict[str, Any]: ...

    def execute(self, code: str) -> ExecResult: ...


ScriptItem = Union[str, ExecResult]


class ScriptedExecutor:
    """Replays queued responses, or computes them from a callable. Fails loudly when unscripted."""

    def __init__(self, script: Union[Callable[[str], ScriptItem], Iterable[ScriptItem]], *,
                 pretend_live: bool = False, name: str = "scripted") -> None:
        # pretend_live exists only so harness tests can exercise live-only code paths.
        self._callable: Optional[Callable[[str], ScriptItem]] = script if callable(script) else None
        self._queue = None if callable(script) else deque(script)
        self.is_live = bool(pretend_live)
        self.name = name
        self.calls: list = []

    def describe(self) -> Dict[str, Any]:
        return {"kind": "scripted", "name": self.name}

    def execute(self, code: str) -> ExecResult:
        self.calls.append(code)
        if self._callable is not None:
            item = self._callable(code)
        else:
            if not self._queue:
                raise AssertionError(f"unscripted call #{len(self.calls)}")
            item = self._queue.popleft()
        return item if isinstance(item, ExecResult) else ExecResult(ok=True, value=item)


class HttpExecutor:
    """POST {"code": ..., "thread": "edt"|"http"} -> {"ok": true, "result": "<string>"}
    or {"ok": false, "error_type": "...", "error_message": "..."}."""

    is_live = True

    def __init__(self, url: str, *, timeout_s: float = 30.0, thread: str = "edt",
                 headers: Optional[Dict[str, str]] = None) -> None:
        self.url = url
        self.timeout_s = timeout_s
        self.thread = thread
        self.headers = dict(headers or {})

    def describe(self) -> Dict[str, Any]:
        return {"kind": "http", "url": self.url, "thread": self.thread, "protocol": "probe-shim-v0"}

    def execute(self, code: str) -> ExecResult:
        body = json.dumps({"code": code, "thread": self.thread}).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json", **self.headers})
        started = time.perf_counter()

        def elapsed() -> float:
            return (time.perf_counter() - started) * 1000.0

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            return ExecResult(False, error_type="HttpError",
                              error_message=f"HTTP {exc.code}: {exc.reason}", duration_ms=elapsed())
        except TimeoutError:
            return ExecResult(False, error_type="Timeout",
                              error_message=f"no response within {self.timeout_s}s", duration_ms=elapsed())
        except urllib.error.URLError as exc:
            kind = "Timeout" if isinstance(exc.reason, TimeoutError) else "ConnectionError"
            return ExecResult(False, error_type=kind, error_message=str(exc.reason), duration_ms=elapsed())
        except OSError as exc:
            return ExecResult(False, error_type="ConnectionError", error_message=str(exc),
                              duration_ms=elapsed())

        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or "ok" not in payload:
            return ExecResult(False, error_type="ProtocolError",
                              error_message="shim reply is not {'ok': ...} JSON", duration_ms=elapsed())
        if payload["ok"] is True:
            result = payload.get("result")
            return ExecResult(True, value=None if result is None else str(result), duration_ms=elapsed())
        return ExecResult(False, error_type=str(payload.get("error_type") or "RemoteError"),
                          error_message=payload.get("error_message"), duration_ms=elapsed())
