"""A contract-derived fake of the Cameo plugin's HTTP boundary (test layer C).

Use it to build and test the Python MCP server without Cameo. Every behaviour cites
the contract clause it implements. Behaviour the contract still lists as OPEN answers
501 UNMODELED instead of guessing, so nothing here can be mistaken for evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from contract_constants import (API_VERSION, CANONICAL_TYPE, DELETE_FIELDS, ERROR_STATUS,
                                MIN_CLIENT_API_VERSION, PREVIEW_LIMIT, QUERY_FIELDS, QUERY_LIMIT_DEFAULT,
                                QUERY_LIMIT_MAX, REQUEST_FIELDS, ROOT_TYPE, ROUTES_V1, SCENARIOS,
                                SUPPORTED_TYPES, SYSML_TYPES)

# Deliberate defects, used by selfcheck/ to prove the conformance suite catches them.
FAULTS = (
    # v0.2
    "accept_any_type", "sysml_without_profile_ok", "check_parent_before_type",
    "html_404", "trim_names", "bind_all_interfaces",
    # v0.4
    "capabilities_missing_route", "decode_before_split", "template_shadows_literal",
    "get_omits_stereotypes", "type_filter_follows_subtyping", "query_trailing_empty_page",
    "preview_commits", "preview_allows_root", "truthy_allow_write", "delete_keeps_children",
)

# Creatable directly under a Model or Package. ASSUMED until probe P-ELM-010 (contract B6 is OPEN).
CREATABLE_UNDER_PACKAGE = frozenset({
    "Package", "Profile", "Class", "Block", "Interface", "Activity", "UseCase", "Actor", "StateMachine",
    "Requirement", "InterfaceBlock", "ConstraintBlock", "ValueType", "DataType", "Signal",
    "Enumeration", "Component", "Comment", "Constraint",
})
# Only used by the type_filter_follows_subtyping fault.
_CLASS_SUBTYPES = {"Block", "ConstraintBlock", "InterfaceBlock", "Requirement"}


def _new_id() -> str:
    return "el-" + uuid.uuid4().hex[:12]


class ApiError(Exception):
    def __init__(self, code: str, message: str, details: Dict[str, Any] = None, status: int = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}
        self.status = status if status is not None else ERROR_STATUS[code]

    def payload(self) -> Dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": self.message, "details": self.details}}


def _ok(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    return 200, {"ok": True, "data": data}


def _unmodeled(item: str) -> ApiError:
    return ApiError("UNMODELED", f"not modeled by the fake: contract item {item} is OPEN",
                    {"open_item": item}, status=501)


def _invalid(reason: str, field: str = None) -> ApiError:
    details = {"reason": reason} if field is None else {"field": field, "reason": reason}
    return ApiError("INVALID_REQUEST", f"invalid request: {reason}", details)


# ---------------------------------------------------------------- validation (G-014)

def _json_object(raw: bytes, allowed: Iterable[str]) -> Dict[str, Any]:
    """Body must be a JSON object; the alphabetically first unknown field is reported (G-014)."""
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _invalid("not_a_json_object")
    if not isinstance(body, dict):
        raise _invalid("not_a_json_object")
    unknown = sorted(k for k in body if k not in allowed)
    if unknown:
        raise _invalid("unknown", unknown[0])
    return body


def _required_string(body: Dict[str, Any], field: str) -> None:
    if field not in body:
        raise _invalid("missing", field)
    _optional_string(body, field)


def _optional_string(body: Dict[str, Any], field: str) -> None:
    if field in body:
        if not isinstance(body[field], str):
            raise _invalid("wrong_type", field)
        if not body[field].strip():
            raise _invalid("blank", field)


def validate_create(raw: bytes) -> Dict[str, Any]:
    """CL-ELM-001 B10: object, unknown field, then type/name/parent_id (missing, wrong_type, blank),
    then metaclasses."""
    body = _json_object(raw, REQUEST_FIELDS)
    for field in ("type", "name", "parent_id"):
        _required_string(body, field)
    if "metaclasses" in body:
        if body["type"] != "Stereotype":
            raise _invalid("not_allowed", "metaclasses")
        value = body["metaclasses"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise _invalid("wrong_type", "metaclasses")
    return body


def validate_query(raw: bytes) -> Dict[str, Any]:
    """CL-ELM-002 B10: object, unknown field, parent_id, type, name, stereotype, limit, cursor."""
    body = _json_object(raw, QUERY_FIELDS)
    _required_string(body, "parent_id")
    for field in ("type", "name", "stereotype"):
        _optional_string(body, field)
    if "limit" in body:
        limit = body["limit"]
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise _invalid("wrong_type", "limit")
        if not 1 <= limit <= QUERY_LIMIT_MAX:
            raise _invalid("out_of_range", "limit")
    if body.get("cursor") is not None and not isinstance(body["cursor"], str):
        raise _invalid("wrong_type", "cursor")
    return body


def validate_delete(raw: bytes, faults: frozenset) -> bool:
    """CL-ELM-003 B10: object, unknown field, allow_write must be a JSON boolean."""
    body = _json_object(raw, DELETE_FIELDS)
    if "allow_write" not in body:
        return False
    value = body["allow_write"]
    if "truthy_allow_write" in faults:
        return bool(value)
    if not isinstance(value, bool):
        raise _invalid("wrong_type", "allow_write")
    return value


# ---------------------------------------------------------------- the model

class FakeModel:
    def __init__(self, scenario: str, faults: Iterable[str] = ()) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}; expected one of {SCENARIOS}")
        self.faults = frozenset(faults)
        unknown = self.faults - set(FAULTS)
        if unknown:
            raise ValueError(f"unknown faults {sorted(unknown)}")
        self.scenario = scenario
        self.project_open = scenario != "no-project"
        self.sysml = scenario == "sysml-project"
        self.port = 0
        self.lock = threading.RLock()
        self.elements: Dict[str, Dict[str, Any]] = {}
        self.root_id: Optional[str] = None
        if self.project_open:
            self.root_id = _new_id()
            self.elements[self.root_id] = {"type": ROOT_TYPE, "name": "Model", "parent_id": None,
                                           "stereotypes": [], "children": []}

    # -- helpers
    def _require_project(self) -> None:
        if not self.project_open:
            raise ApiError("NO_ACTIVE_PROJECT", "no project is open")

    def _public(self, element_id: str) -> Dict[str, Any]:
        e = self.elements[element_id]
        stereotypes = sorted(e["stereotypes"])  # CL-ELM-002 B7: sorted by name
        return {"id": element_id, "type": e["type"], "name": e["name"], "parent_id": e["parent_id"],
                "applied_stereotypes": stereotypes}

    def _find(self, element_id: str) -> Dict[str, Any]:
        if element_id not in self.elements:
            raise ApiError("ELEMENT_NOT_FOUND", "element not found", {"id": element_id})
        return self.elements[element_id]

    def _subtree(self, element_id: str) -> List[str]:
        """Target first, then owned elements depth-first in containment order (CL-ELM-003 B9)."""
        order = [element_id]
        for child in self.elements[element_id]["children"]:
            order.extend(self._subtree(child))
        return order

    # -- CL-HSK-001
    def status(self) -> Tuple[int, Dict[str, Any]]:
        return _ok({"plugin_version": "fake-0.2.0", "api_version": API_VERSION, "cameo_version": None,
                    "project_open": self.project_open, "port": self.port})

    # -- CL-HSK-002
    def capabilities(self) -> Tuple[int, Dict[str, Any]]:
        routes = [{"method": m, "path": p} for m, p in ROUTES_V1]
        if "capabilities_missing_route" in self.faults:
            routes = [r for r in routes if not r["path"].endswith("/delete")]
        return _ok({"plugin_version": "fake-0.2.0", "api_version": API_VERSION,
                    "min_client_api_version": MIN_CLIENT_API_VERSION, "routes": routes,
                    "element_types": list(SUPPORTED_TYPES)})

    # -- CL-PRJ-001
    def project(self) -> Tuple[int, Dict[str, Any]]:
        self._require_project()
        return _ok({"name": "Fake Project", "file_path": None, "root_model_id": self.root_id})

    # -- CL-ELM-001
    def create_element(self, raw: bytes) -> Tuple[int, Dict[str, Any]]:
        body = validate_create(raw)                       # B10, and B11 step 1
        with self.lock:                                   # B9: writes are serialized
            self._require_project()                       # B11 step 2
            kind, name, parent_id = body["type"], body["name"], body["parent_id"]

            def check_type():                             # B11 step 3
                if "accept_any_type" not in self.faults and kind not in SUPPORTED_TYPES:
                    raise ApiError("UNSUPPORTED_TYPE", f"unsupported type {kind!r}", {"type": kind})

            def check_parent():                           # B11 step 4
                if parent_id not in self.elements:
                    raise ApiError("PARENT_NOT_FOUND", "parent not found", {"parent_id": parent_id})

            order = (check_parent, check_type) if "check_parent_before_type" in self.faults else (check_type, check_parent)
            for check in order:
                check()
            if kind in SYSML_TYPES and not self.sysml and "sysml_without_profile_ok" not in self.faults:
                # B1 / B11 step 5: never fall back to a plain UML element.
                raise ApiError("REQUIRED_PROFILE_MISSING", f"profile for {kind} is not available",
                               {"stereotype": kind})
            parent = self.elements[parent_id]
            if parent["type"] not in (ROOT_TYPE, "Package") or kind not in CREATABLE_UNDER_PACKAGE:
                raise _unmodeled("B6")                    # parent/type compatibility is OPEN
            if any(self.elements[c]["name"] == name for c in parent["children"]):
                raise _unmodeled("B5")                    # duplicate sibling names are OPEN
            stored = name.strip() if "trim_names" in self.faults else name   # 7.2: stored exactly as given
            new_id = _new_id()
            self.elements[new_id] = {
                "type": CANONICAL_TYPE.get(kind, kind),   # B4, D-012
                "name": stored, "parent_id": parent_id,
                "stereotypes": [kind] if kind in SYSML_TYPES and self.sysml else [],
                "children": [],
            }
            parent["children"].append(new_id)
            return _ok(self._public(new_id))

    # -- CL-ELM-002
    def get_element(self, element_id: str) -> Tuple[int, Dict[str, Any]]:
        self._require_project()
        self._find(element_id)
        data = self._public(element_id)
        if "get_omits_stereotypes" in self.faults:
            data["applied_stereotypes"] = []
        return _ok(data)

    @staticmethod
    def _query_key(body: Dict[str, Any]) -> str:
        """What a cursor is bound to (B8): the parent and the filters, not the limit."""
        key = json.dumps([body["parent_id"], body.get("type"), body.get("name"), body.get("stereotype")])
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _encode_cursor(offset: int, key: str) -> str:
        return base64.urlsafe_b64encode(json.dumps({"o": offset, "q": key}).encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str, key: str) -> int:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
            offset = data["o"]
            if data["q"] != key or not isinstance(offset, int) or isinstance(offset, bool) or offset < 1:
                raise ValueError
            return offset
        except Exception:
            raise _invalid("invalid", "cursor")

    def query(self, raw: bytes) -> Tuple[int, Dict[str, Any]]:
        body = validate_query(raw)                                    # B10 (INVALID_REQUEST first)
        self._require_project()                                       # G-010
        with self.lock:
            parent_id = body["parent_id"]
            if parent_id not in self.elements:                        # B4
                raise ApiError("PARENT_NOT_FOUND", "parent not found", {"parent_id": parent_id})
            key = self._query_key(body)
            offset = 0 if body.get("cursor") is None else self._decode_cursor(body["cursor"], key)
            limit = body.get("limit", QUERY_LIMIT_DEFAULT)

            def matches(element_id: str) -> bool:
                e = self.elements[element_id]
                if "type" in body:
                    wanted = body["type"]
                    if "type_filter_follows_subtyping" in self.faults and wanted == "Class":
                        if e["type"] not in ({"Class"} | _CLASS_SUBTYPES):
                            return False
                    elif e["type"] != wanted:                         # B5: exact, no subtyping
                        return False
                if "name" in body and e["name"] != body["name"]:      # exact, case-sensitive
                    return False
                if "stereotype" in body and body["stereotype"] not in e["stereotypes"]:
                    return False
                return True

            hits = [c for c in self.elements[parent_id]["children"] if matches(c)]
            page = hits[offset:offset + limit]
            end = offset + limit
            more = end <= len(hits) if "query_trailing_empty_page" in self.faults else end < len(hits)
            return _ok({"items": [self._public(i) for i in page],
                        "next_cursor": self._encode_cursor(end, key) if more else None})   # B9

    # -- CL-ELM-003
    def delete_element(self, element_id: str, raw: bytes) -> Tuple[int, Dict[str, Any]]:
        allow_write = validate_delete(raw, self.faults)               # B10
        self._require_project()
        with self.lock:                                               # G-004: serialized with writes
            self._find(element_id)                                    # B6
            is_root = element_id == self.root_id
            if is_root and not ("preview_allows_root" in self.faults and not allow_write):
                raise ApiError("PROTECTED_ELEMENT", "the root model cannot be deleted", {"id": element_id})
            doomed = self._subtree(element_id)
            if allow_write or "preview_commits" in self.faults:
                self._remove(element_id, doomed)
            if not allow_write:                                       # B1: preview by default
                listed = [{"id": i, "type": self.elements[i]["type"] if i in self.elements else "?",
                           "name": self.elements[i]["name"] if i in self.elements else None}
                          for i in doomed[:PREVIEW_LIMIT]]
                return _ok({"preview": True, "would_delete": listed, "count": len(doomed),
                            "truncated": len(doomed) > PREVIEW_LIMIT})
            return _ok({"preview": False, "deleted_count": len(doomed)})

    def _remove(self, element_id: str, doomed: List[str]) -> None:
        parent_id = self.elements[element_id]["parent_id"]
        if parent_id is not None:
            self.elements[parent_id]["children"].remove(element_id)
        targets = [element_id] if "delete_keeps_children" in self.faults else doomed
        for i in targets:
            self.elements.pop(i, None)


# ---------------------------------------------------------------- routing (G-011)

Handler = Callable[[FakeModel, Dict[str, str], bytes], Tuple[int, Dict[str, Any]]]
ROUTES: List[Tuple[str, Dict[str, Handler]]] = [
    ("/api/v1/status", {"GET": lambda m, p, raw: m.status()}),
    ("/api/v1/capabilities", {"GET": lambda m, p, raw: m.capabilities()}),
    ("/api/v1/project", {"GET": lambda m, p, raw: m.project()}),
    ("/api/v1/elements", {"POST": lambda m, p, raw: m.create_element(raw)}),
    ("/api/v1/elements/query", {"POST": lambda m, p, raw: m.query(raw)}),
    ("/api/v1/elements/{id}", {"GET": lambda m, p, raw: m.get_element(p["id"])}),
    ("/api/v1/elements/{id}/delete", {"POST": lambda m, p, raw: m.delete_element(p["id"], raw)}),
]


def _segments(raw_path: str, faults: frozenset) -> List[str]:
    """Split the RAW path on '/', then percent-decode each segment (G-011)."""
    if "decode_before_split" in faults:
        return unquote(raw_path).split("/")[1:]
    return [unquote(s) for s in raw_path.split("/")[1:]]


def resolve(raw_path: str, faults: frozenset = frozenset()) -> Optional[Tuple[Dict[str, Handler], Dict[str, str]]]:
    """Exact, case-sensitive match. A literal segment beats a {param} at the first position where
    two matching templates differ (G-011)."""
    segs = _segments(raw_path, faults)
    found = []
    for template, methods in ROUTES:
        parts = template.split("/")[1:]
        if len(parts) != len(segs):
            continue
        params, rank = {}, []
        for part, seg in zip(parts, segs):
            if part.startswith("{"):
                if not seg:
                    break
                params[part[1:-1]] = seg
                rank.append(1)
            elif part == seg:
                rank.append(0)
            else:
                break
        else:
            found.append((rank, methods, params))
    if not found:
        return None
    found.sort(key=lambda f: f[0], reverse="template_shadows_literal" in faults)
    _, methods, params = found[0]
    return methods, params


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeCameoPlugin/0.2"

    def _send(self, status: int, content_type: str, data: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _dispatch(self, method: str) -> None:
        model = self.server.model
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        raw_path = urlparse(self.path).path
        try:
            match = resolve(raw_path, model.faults)
            if match is None:
                if "html_404" in model.faults:
                    return self._send(404, "text/html", b"<html><body>404 Not Found</body></html>")
                raise ApiError("ROUTE_NOT_FOUND", f"no route {raw_path}")
            methods, params = match
            if method not in methods:
                raise ApiError("METHOD_NOT_ALLOWED", f"{method} is not allowed on {raw_path}")
            status, payload = methods[method](model, params, raw)
        except ApiError as exc:
            status, payload = exc.status, exc.payload()
        except Exception:  # the contract promises INTERNAL_ERROR, never a stack trace
            status, payload = 500, ApiError("INTERNAL_ERROR", "unexpected failure").payload()
        self._send(status, "application/json", json.dumps(payload).encode("utf-8"))

    def do_GET(self): self._dispatch("GET")
    def do_POST(self): self._dispatch("POST")
    def do_PUT(self): self._dispatch("PUT")
    def do_DELETE(self): self._dispatch("DELETE")
    def do_PATCH(self): self._dispatch("PATCH")

    def log_message(self, *args) -> None:
        pass


class FakePlugin:
    def __init__(self, scenario: str = "sysml-project", port: int = 0, faults: Iterable[str] = ()) -> None:
        self.model = FakeModel(scenario, faults)
        host = "0.0.0.0" if "bind_all_interfaces" in self.model.faults else "127.0.0.1"  # A-004
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._server.model = self.model
        self.model.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.model.port}"

    def start(self) -> "FakePlugin":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
