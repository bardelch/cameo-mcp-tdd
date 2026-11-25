"""Regenerate fixtures/*.json from the fake plugin.

These fixtures are ILLUSTRATIVE: they show the DECISION-level schema produced by the fake.
They are replaced by captures from a live Cameo once the probes behind each clause are
reviewed (contract section 2.1). Run: python -m tools.generate_fixtures --write

A fixture may have setup steps; they run first and their results are recorded under
"given". Tokens like <ROOT>, <PKG> and <A> in a later step stand for IDs created earlier.
"""
import json
import os
import sys
from typing import Any, Dict, List

from conformance import client
from contract_constants import DEFAULT_PORT
from fake_plugin.server import FakePlugin

E = "/api/v1/elements"

TREE = [  # <PKG> under the root, <A> (Class) and <B> (Class) inside it
    ("<PKG>", "POST", E, {"type": "Package", "name": "Pkg", "parent_id": "<ROOT>"}),
    ("<A>", "POST", E, {"type": "Class", "name": "A", "parent_id": "<PKG>"}),
    ("<B>", "POST", E, {"type": "Class", "name": "B", "parent_id": "<PKG>"}),
]

# id, clause, scenario, setup, (method, path, body)
FIXTURES = [
    ("F-HSK-001-a", "CL-HSK-001", "sysml-project", [], ("GET", "/api/v1/status", None)),
    ("F-HSK-001-b", "CL-HSK-001", "no-project", [], ("GET", "/api/v1/status", None)),
    ("F-HSK-002-a", "CL-HSK-002", "no-project", [], ("GET", "/api/v1/capabilities", None)),
    ("F-PRJ-001-a", "CL-PRJ-001", "sysml-project", [], ("GET", "/api/v1/project", None)),
    ("F-PRJ-001-b", "CL-PRJ-001", "no-project", [], ("GET", "/api/v1/project", None)),
    ("F-ELM-001-a", "CL-ELM-001", "sysml-project", [],
     ("POST", E, {"type": "Block", "name": "Sensor", "parent_id": "<ROOT>"})),
    ("F-ELM-001-b", "CL-ELM-001", "uml-project", [],
     ("POST", E, {"type": "Block", "name": "Sensor", "parent_id": "<ROOT>"})),
    ("F-ELM-001-c", "CL-ELM-001", "sysml-project", [],
     ("POST", E, {"type": "Widget", "name": "Sensor", "parent_id": "<ROOT>"})),
    ("F-ELM-001-d", "CL-ELM-001", "sysml-project", [],
     ("POST", E, {"type": "Block", "name": "Sensor", "parent_id": "missing-parent"})),
    ("F-ELM-001-e", "CL-ELM-001", "sysml-project", [],
     ("POST", E, {"name": "Sensor", "parent_id": "<ROOT>"})),
    ("F-ELM-002-a", "CL-ELM-002", "sysml-project", TREE[:2], ("GET", E + "/<A>", None)),
    ("F-ELM-002-b", "CL-ELM-002", "sysml-project", [], ("GET", E + "/missing-id", None)),
    ("F-ELM-002-c", "CL-ELM-002", "sysml-project", TREE,
     ("POST", E + "/query", {"parent_id": "<PKG>", "limit": 1})),
    ("F-ELM-002-d", "CL-ELM-002", "sysml-project", TREE,
     ("POST", E + "/query", {"parent_id": "<PKG>", "type": "Class", "name": "B"})),
    ("F-ELM-003-a", "CL-ELM-003", "sysml-project", TREE, ("POST", E + "/<PKG>/delete", {})),
    ("F-ELM-003-b", "CL-ELM-003", "sysml-project", TREE,
     ("POST", E + "/<PKG>/delete", {"allow_write": True})),
    ("F-ELM-003-c", "CL-ELM-003", "sysml-project", [],
     ("POST", E + "/<ROOT>/delete", {"allow_write": True})),
    ("F-ELM-003-d", "CL-ELM-003", "sysml-project", [],
     ("POST", E + "/missing-id/delete", {"allow_write": "true"})),
]


def _replace(value: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(value, str):
        for real, token in mapping.items():
            value = value.replace(real, token)
        return value
    if isinstance(value, dict):
        return {k: _replace(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace(v, mapping) for v in value]
    return value


def _scrub(body: Any) -> Any:
    """Make a reply deterministic: fixed port, opaque cursors, no error messages (D-006)."""
    if not isinstance(body, dict):
        return body
    data = body.get("data")
    if isinstance(data, dict):
        if "port" in data:
            data["port"] = DEFAULT_PORT
        if data.get("next_cursor") is not None:
            data["next_cursor"] = "<CURSOR>"
    if isinstance(body.get("error"), dict):
        body["error"].pop("message", None)
    return body


def _build_one(scenario: str, setup: List[tuple], request: tuple) -> Dict[str, Any]:
    fake = FakePlugin(scenario).start()
    try:
        tokens: Dict[str, str] = {}          # token -> real id
        if fake.model.root_id:
            tokens["<ROOT>"] = fake.model.root_id
        given = []
        for token, method, path, body in setup:
            real_body = _replace(body, tokens)
            reply = client.request(fake.url, method, _replace(path, tokens), json_body=real_body)
            tokens[token] = reply.body["data"]["id"]
            given.append({"as": token, "request": {"method": method, "path": path, "body": body}})
        method, path, body = request
        real_path = _replace(path, tokens)
        real_body = _replace(body, tokens) if body is not None else None
        reply = client.request(fake.url, method, real_path, json_body=real_body)

        reverse = {real: token for token, real in tokens.items()}
        fresh = 0
        def collect(v):
            nonlocal fresh
            if isinstance(v, dict):
                if isinstance(v.get("id"), str) and v["id"] not in reverse and v["id"].startswith("el-"):
                    fresh += 1
                    reverse[v["id"]] = f"<NEW:{fresh}>"
                for x in v.values():
                    collect(x)
            elif isinstance(v, list):
                for x in v:
                    collect(x)
        collect(reply.body)
        return {
            "scenario": scenario, "given": given,
            "request": {"method": method, "path": path, "body": body},
            "response": {"status": reply.status, "body": _scrub(_replace(reply.body, reverse))},
        }
    finally:
        fake.stop()


def build_all() -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for fixture_id, clause, scenario, setup, request in FIXTURES:
        doc = grouped.setdefault(clause, {
            "clause": clause,
            "provenance": ("Produced by fake_plugin from the DECISION-level contract; illustrative until "
                           "replaced by live captures (contract section 2.1)."),
            "placeholders": ("<ROOT>, <PKG>, <A>, <B> are IDs created by the 'given' steps; <NEW:n> is an ID "
                             "first seen in the response; <CURSOR> is an opaque cursor."),
            "notes": "error.message is omitted on purpose: messages are informative and never asserted (D-006).",
            "fixtures": [],
        })
        doc["fixtures"].append({"id": fixture_id, **_build_one(scenario, setup, request)})
    return grouped


def main() -> None:
    target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
    for clause, doc in build_all().items():
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        if "--write" in sys.argv:
            with open(os.path.join(target, f"{clause}.json"), "w", encoding="utf-8") as handle:
                handle.write(text)
            print("wrote", f"fixtures/{clause}.json")
        else:
            print(text)


if __name__ == "__main__":
    main()
