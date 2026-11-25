"""Tiny stdlib HTTP client for the conformance suite."""
import json
import urllib.error
import urllib.request
from typing import Any, NamedTuple, Optional


class Response(NamedTuple):
    status: int
    body: Any  # parsed JSON, or None when the reply is not JSON
    raw: bytes


def request(base_url: str, method: str, path: str, json_body: Any = None,
            raw_body: Optional[bytes] = None, timeout: float = 10.0) -> Response:
    data = raw_body if raw_body is not None else (
        None if json_body is None else json.dumps(json_body).encode("utf-8"))
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as reply:
            status, raw = reply.status, reply.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        body = json.loads(raw.decode("utf-8"))
    except ValueError:
        body = None
    return Response(status, body, raw)
