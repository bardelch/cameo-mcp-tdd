# Cameo MCP Bridge: TDD Contract

*v0.4 draft · Phase 1 (basic functions) written at full depth · prepared with Claude*

## 1. Purpose and status

This contract is the only specification an implementer receives. Together with its fixtures, the fake Cameo executor and the conformance tests, it must be enough to build a working Cameo MCP bridge without seeing the reference implementation (github.com/ajhcs/cameo-mcp-bridge). The reference informed the authoring; it is not an input to the build.

The exercise tests one thesis: a TDD contract can carry enough scope and detail for an AI implementer to build correct software from it alone, and the contract's defect log measures how much detail that takes.

**Where things stand (v0.4).** Phase 1, the basic functions, is written at full depth: seven clauses in Sections 5.2, 6 and 7, with a conformance test behind every DECISION statement and a contract-derived fake plugin that passes them all. What keeps Phase 1 from READY is evidence: its remaining REF and ASSUMED statements wait on probes, and nothing has run on a live Cameo yet, so no statement is tagged LIVE. Phase 2 (diagrams from scratch) is scoped in 5.1 but not yet written.

## 2. How to read this contract

### 2.1 Evidence tags

Every normative statement carries one tag.

| Tag | Meaning | May a clause be READY with it? |
| --- | --- | --- |
| LIVE | Observed on a live Cameo through a reviewed, stable probe; Cameo version recorded | Yes |
| DECISION | Chosen by the contract authors; needs review, not observation | Yes |
| REF | Stated by the reference project's documentation, not yet observed | No: upgrade to LIVE or restate as DECISION |
| ASSUMED | Believed but not observed anywhere | No |

### 2.2 Clause status

DRAFT (written, open items remain) → PROBED (probes run, no ASSUMED left) → READY (all statements LIVE or DECISION, every statement has a test) → FROZEN (survived a blind build with zero new defects).

### 2.3 Detail tiers

Every clause has five tiers. A clause is not done until each tier exists and each normative statement maps to at least one test ID.

- **T1 Intent**: why the capability exists, in two or three sentences.
- **T2 Interface**: names, routes, request and response schemas, error codes.
- **T3 Behavior**: numbered rules covering preconditions, postconditions, invariants and failure effects.
- **T4 Examples**: fixtures covering success, edge and failure cases, normalized (IDs become `<ID:n>`, timestamps `<TS>`).
- **T5 Non-functional**: timeouts, threading, size limits, security.

### 2.4 Roles and information barrier

- **Authors** read the reference, run the probes against a live Cameo and write the contract.
- **Implementers** (the AI) receive only this contract, the fixtures, the fake Cameo executor and the conformance tests.
- **Never given to implementers:** the reference source, the probe harness and its shim.
- Cameo's own vendor API documentation is permitted to both roles.

## 3. Architecture contract

Three layers, as in the reference: an MCP server speaking stdio to the client (Python), an HTTP/JSON boundary on loopback, and a plugin running inside the Cameo JVM.

`MCP client <-stdio/MCP-> Python MCP server <-HTTP/JSON-> Java plugin (Cameo JVM)`

- **A-001 (DECISION).** The HTTP boundary is the contract surface between the two implementations. It is specified in full (Section 4 and each clause); neither side may rely on behavior not written here.
- **A-002 (REF).** Default port 18740, set in the plugin by system property `cameo.mcp.port` and in the Python server by environment variable `CAMEO_BRIDGE_PORT`; both sides must agree.
- **A-003 (REF).** The plugin binds to 127.0.0.1 only and has no authentication; it is for local development.
- **A-004 (DECISION).** Binding to any non-loopback address is a contract violation, enforced by a test (T-HSK-001-05).

## 4. Global conventions

- **G-001 (DECISION) Envelope.** Success: `{"ok": true, "data": {...}}`. Failure: `{"ok": false, "error": {"code": "...", "message": "...", "details": {...}}}`. Tests assert `code` and `details`, never `message` text.
- **G-002 (DECISION) Status mapping.** 200 success; 400 INVALID\_REQUEST and UNSUPPORTED\_TYPE; 404 ROUTE\_NOT\_FOUND and PARENT\_NOT\_FOUND; 405 METHOD\_NOT\_ALLOWED; 409 NO\_ACTIVE\_PROJECT and SESSION\_CONFLICT; 422 REQUIRED\_PROFILE\_MISSING and INVALID\_PARENT\_FOR\_TYPE; 500 INTERNAL\_ERROR; 504 TIMEOUT.
- **G-003 (DECISION) Identity.** Element IDs are opaque strings. Clients must not parse or construct them. Their observed format is recorded by probe P-ENV-001 for fixture normalization only.
- **G-004 (REF) Write sessions.** Every mutating request runs in exactly one Cameo session on the Swing EDT, and write sessions are serialized.
- **G-005 (REF) Reads.** Read requests run on the HTTP thread pool, not the EDT. The reference states that model reads are thread-safe; this needs a probe (P-THR-001).
- **G-006 (DECISION) Atomicity.** A failed write leaves the model unchanged and no session open. Depends on P-SES-001.
- **G-007 (REF) Guarded writes.** Families marked guarded default to preview and refuse to write unless the request carries `allow_write=true`. The reference applies this to report generation and requirements import.
- **G-008 (DECISION) Timeouts.** Python-side request timeout is 30 s for writes and 10 s for reads. The plugin must return TIMEOUT rather than hold a session open (needs P-THR-002).
- **G-009 (REF) Fail closed.** Optional capabilities (for example Teamwork, DataHub, simulation) report as unavailable with a structured refusal when the product or licence is missing. The refusal payload is part of the contract.

* **G-010 (DECISION) Error precedence.** When several errors apply, INVALID\_REQUEST comes first, then NO\_ACTIVE\_PROJECT, then the clause's own checks in the order the clause gives (CL-ELM-001 B11, CL-ELM-002 B11, CL-ELM-003 B11). Tests: T-ELM-001-10a to -10d and each clause's no-project tests.
* **G-011 (DECISION) Routing.** An unknown route returns 404 ROUTE\_NOT\_FOUND, and a known route called with the wrong method returns 405 METHOD\_NOT\_ALLOWED, both in the G-001 envelope with empty `details`. Paths match exactly and case-sensitively, with no trailing-slash normalisation. The raw path is split on "/" before each segment is percent-decoded, so an ID may contain an encoded "/". Where a literal segment and a `{id}` template both match, the literal wins, so `/api/v1/elements/query` is never an element ID (D-013). Tests: T-GLB-001-01 to -04, T-ELM-002-02b and -02c.

- **G-012 (DECISION) Phase 1 error codes.** Added to the G-002 mapping: 404 ELEMENT\_NOT\_FOUND; 422 PROTECTED\_ELEMENT and ELEMENT\_READ\_ONLY. PLUGIN\_INCOMPATIBLE is raised by the Python server, never by the plugin.
- **G-013 (DECISION) No browser access.** Unlike the reference, which sends a wildcard CORS header, the plugin sends no CORS headers and accepts request bodies only as `application/json`, so a web page in a local browser cannot drive it (D-011).

* **G-014 (DECISION) Validation does not depend on key order.** JSON key order carries no meaning, because not every JSON library preserves it. When several fields are unknown, the alphabetically first is reported; otherwise the order each clause gives decides. JSON null counts as `wrong_type` for every field except a query `cursor` (D-014). Tests: T-ELM-001-09 and T-ELM-002-09.

## 5. Clause catalogue (vertical slice)

| ID | Clause | Phase | Class of tool it calibrates | Status |
| --- | --- | --- | --- | --- |
| CL-GLB-001 | Envelope and routing | 1 Basics | Cross-cutting reply rules | DRAFT (tests written, 6.2) |
| CL-HSK-001 | Status | 1 Basics | Health check, no model access | DRAFT (tests written, 6) |
| CL-HSK-002 | Capabilities and compatibility | 1 Basics | Versioning, fail-fast | DRAFT (tests written, 5.2) |
| CL-PRJ-001 | Get project | 1 Basics | Read that supplies the root model ID | DRAFT (tests written, 6.1) |
| CL-ELM-001 | Create element | 1 Basics | Session-wrapped write | DRAFT (tests written, 7) |
| CL-ELM-002 | Get and query elements | 1 Basics | Read with paging | DRAFT (tests written, 5.2) |
| CL-ELM-003 | Delete element, guarded | 1 Basics | Guarded write (absorbs CL-GRD-001) | DRAFT (tests written, 5.2) |
| CL-REL-001 | Create relationship (Generalization and Composition first) | 2 Diagrams | Write with ownership rules | Not started |
| CL-DGM-001 | Create diagram (BDD first) | 2 Diagrams | Diagram as a model element | Not started |
| CL-DGM-002 | Add element to diagram | 2 Diagrams | Presentation objects and geometry | Not started |
| CL-DGM-003 | Add relationship path to diagram | 2 Diagrams | Paths between shapes | Not started |
| CL-DGM-004 | Get diagram contents | 2 Diagrams | Reading presentation state | Not started |
| CL-VER-001 | Verify requirement quality | 3 Later | Pure-logic heuristic over readback | Outline |

Calibration note for CL-VER-001: the reference describes this check only as testing requirement IDs, non-blank text and basic measurability. A contract for a heuristic tool must contain the rule table itself (each rule, its input, its threshold and its finding code). Otherwise the implementer invents the heuristic.

### 5.1 Delivery phases

The slice is built in three phases (D-009). Each phase ends with a blind build round, so the defect log measures contract detail per phase.

**Phase 1, Basics.** A client can check health and compatibility, find the root, create an element, read it back, and delete it safely. Exit criteria:

- Every Phase 1 clause is READY: all statements LIVE or DECISION, every statement tested.
- The conformance suite covers every Phase 1 clause and passes against the fake plugin in all three scenarios.
- An end-to-end run on a live Cameo passes (automated as conformance test T-PH1-001): status, capabilities, project, create a Package and a Block inside it, get both back, query the Package's children, preview the Package's deletion, commit it, and confirm both elements are gone.
- One blind build round with its defects logged in Section 11.

**Phase 2, Diagrams from scratch.** The local requirement: build a BDD with blocks and relationships on it, then read it back. Its acceptance scenario creates a Package, three Blocks, a Generalization and a Composition, then a BDD; adds three shapes and two paths; reads the diagram back and checks it; then deletes the Package. Open questions to probe first: element ID versus presentation ID (and adding the same element twice), geometry (origin, units, default and minimum sizes, auto-resize), which element types each diagram type accepts, and whether a diagram must be open in the UI to be edited.

**Phase 3, Later.** CL-VER-001, then other diagram types. Deferred with no phase: move, resize and auto-layout, image export, IBDs (ports and nested parts are a large probe family), matrices and tables, Relation Maps, reports, import and export, Teamwork, DataHub, simulation, and arbitrary macro execution, which has no place in a bridge built from a contract.

### 5.2 Phase 1 clauses: capabilities, read, delete

These three clauses are written at full depth. Every test ID below is a test method in the implementer package's conformance suite, and the fake plugin passes all of them. Fixtures are illustrative until live captures replace them. The open items left are ASSUMED statements waiting on probes; each names its probe.

#### CL-HSK-002 Capabilities and compatibility

**T1 Intent.** The Python server and the Java plugin are built and deployed separately. A mismatch must be detected before any model call, instead of surfacing later as a confusing 404 (the failure the reference warns about after updates).

**T2 Interface.** MCP tool `cameo_get_capabilities` (REF). HTTP `GET /api/v1/capabilities` (REF; the legacy `/capabilities` alias is optional, as for status, D-002).

| Field | Type | Rule | Tag |
| --- | --- | --- | --- |
| plugin\_version | string | Free text, for display only | DECISION |
| api\_version | integer | 1 for this contract | DECISION |
| min\_client\_api\_version | integer | Lowest Python-server API version the plugin accepts; never above api\_version; 1 for this contract | DECISION |
| routes | array of `{method, path}` | Exactly the 5.2.1 catalogue, in any order, no duplicates | DECISION |
| element\_types | array of string | Exactly the 7.2.1 tokens, in any order, no duplicates | DECISION |

**5.2.1 Route catalogue for api\_version 1 (DECISION).** Path templates use `{id}` for one percent-encoded path segment (G-011).

| Method | Path | Clause |
| --- | --- | --- |
| GET | /api/v1/status | CL-HSK-001 |
| GET | /api/v1/capabilities | CL-HSK-002 |
| GET | /api/v1/project | CL-PRJ-001 |
| POST | /api/v1/elements | CL-ELM-001 |
| GET | /api/v1/elements/{id} | CL-ELM-002 |
| POST | /api/v1/elements/query | CL-ELM-002 |
| POST | /api/v1/elements/{id}/delete | CL-ELM-003 |

**T3 Behavior.**

- B1 (DECISION): before its first non-status tool call, the Python server reads capabilities. If its own API version is below `min_client_api_version`, or a route it needs is missing, it refuses every non-status tool with PLUGIN\_INCOMPATIBLE, with `details` `{"plugin_api_version": n, "missing_routes": [...]}`.
- B2 (REF): `compatibility.clientCompatible` in the status tool (CL-HSK-001 B3) is the result of this check.
- B3 (DECISION): works with no project open and never opens a session.
- B4 (DECISION): `routes` lists exactly the routes the plugin serves. A listed route never answers ROUTE\_NOT\_FOUND or METHOD\_NOT\_ALLOWED for its listed method.
- B5 (DECISION): adding a route raises `api_version`; removing or changing one also raises `min_client_api_version`.

**T4 Examples.** F-HSK-002-a (no project open).

**T5 Non-functional.** Read only; local response under 1 s.

| Test | Layer | Asserts |
| --- | --- | --- |
| T-HSK-002-01 | P | Field set and types; min\_client\_api\_version at most api\_version |
| T-HSK-002-02 | P | Every listed route is served (probed with a dummy ID and `{}` bodies, which never mutate) |
| T-HSK-002-03 | P | Routes equal the 5.2.1 catalogue exactly, with no duplicates |
| T-HSK-002-04 | P | element\_types equal the 7.2.1 tokens exactly |
| T-HSK-002-05 | C | The Python server refuses non-status tools when a route is missing (not built yet) |

Needs no probes: it describes the bridge, not Cameo.

#### CL-ELM-002 Get and query elements

**T1 Intent.** Read back what was created, by ID or by listing a parent's children. It also makes "a failed write left nothing behind" observable over HTTP, which closes defect CD-005.

**T2 Interface.** MCP tools `cameo_get_element` and `cameo_query_elements` (REF; the reference queries by type, name, package and stereotype, with paging and compact or full views; compact and full views are deferred here).

- `GET /api/v1/elements/{id}` (DECISION) returns an element object: the five fields of the create response in 7.2.
- `POST /api/v1/elements/query` (DECISION; POST so filters travel as a JSON body). Response: `items` (array of element objects) and `next_cursor` (string, or null).

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| parent\_id | string | yes | Direct children of this element only |
| type | string | no | Exact match on the reported type (B5); no subtyping |
| name | string | no | Exact, case-sensitive match |
| stereotype | string | no | The element's applied\_stereotypes contains it |
| limit | integer | no | 1 to 500; default 100 |
| cursor | string or null | no | A previous page's next\_cursor; absent or null means the first page |

Errors: INVALID\_REQUEST, NO\_ACTIVE\_PROJECT, ELEMENT\_NOT\_FOUND (get), PARENT\_NOT\_FOUND (query).

**T3 Behavior.**

- **B1 Unknown ID.** (DECISION) 404 ELEMENT\_NOT\_FOUND with `details` `{"id": ...}`, the ID after percent-decoding.
- **B2 Round trip.** (DECISION) For any element a create returned, a get returns an identical object, field for field.
- **B3 Order.** (ASSUMED; P-ELM-012) Children come back in Cameo's containment order, and repeated reads give the same order.
- **B4 Unknown parent.** (DECISION) 404 PARENT\_NOT\_FOUND with `details` `{"parent_id": ...}`.
- **B5 Reported type.** (DECISION) An element created from a 7.2.1 token reports that token in canonical form (D-012); a SysML element reports its SysML token, so a Block is "Block" and never "Class"; the root model reports "Model" with `parent_id` null. Any other element reports its UML metaclass name (ASSUMED until P-ELM-013 shows which name Cameo exposes).
- **B6 Threading.** (REF) Reads run off the EDT (G-005).
- **B7 Stereotype order.** (DECISION) `applied_stereotypes` is sorted by name, in create, get and query alike.
- **B8 Cursors.** (DECISION) Opaque strings. A cursor is bound to `parent_id` and the three filters, not to `limit`, so the limit may change between pages. A cursor the plugin did not issue, or one reused with a different parent or filter, returns INVALID\_REQUEST with `details` `{"field": "cursor", "reason": "invalid"}`.
- **B9 Paging.** (DECISION) A page holds at most `limit` items. `next_cursor` is null exactly when no matching items remain, so there is never an empty last page. Paging is consistent only while the parent's children do not change: if they change between pages, items may be skipped or repeated, and a client that needs a consistent list queries again from the first page.
- **B10 Validation.** (DECISION) The first failing check returns INVALID\_REQUEST: (1) the body is not a JSON object (`not_a_json_object`); (2) an unknown field (`unknown`, G-014); (3) `parent_id` missing, `wrong_type` or `blank`; (4) `type`, `name` and `stereotype`, in that order, when present: `wrong_type` (null included) or `blank`; (5) `limit`: `wrong_type` unless a JSON integer (booleans and fractions are `wrong_type`), `out_of_range` outside 1 to 500; (6) `cursor`: `wrong_type` unless a string or null.
- **B11 Precedence.** (DECISION) INVALID\_REQUEST from B10, then NO\_ACTIVE\_PROJECT, then PARENT\_NOT\_FOUND, then INVALID\_REQUEST for an invalid cursor (B8).
- **B12 Filters.** (DECISION) Filters combine with AND. A `type` value outside the known tokens is allowed and simply matches nothing.

**T4 Examples.** F-ELM-002-a get, F-ELM-002-b unknown ID, F-ELM-002-c a first page with `limit` 1 and a `next_cursor`, F-ELM-002-d two filters combined.

**T5 Non-functional.** Read only. Pages are capped at 500 items; response time is not asserted.

| Test | Layer | Asserts | Backed by |
| --- | --- | --- | --- |
| T-ELM-002-01 | P | For every token that can be created under the root, the create type is canonical and a get returns the identical object | B2, B5, D-012 |
| T-ELM-002-01b | P | The root reports type Model and parent\_id null | B5 |
| T-ELM-002-02 | P | Unknown ID | B1 |
| T-ELM-002-02b | P | An encoded "/" stays inside one ID | B1, G-011 |
| T-ELM-002-02c | P | GET /api/v1/elements/query is METHOD\_NOT\_ALLOWED, never a lookup of an element called "query" | G-011 |
| T-ELM-002-03 | P | Name and type filters, combined with AND, case-sensitive, unknown type matches nothing; queried items equal their get | B2, B12 |
| T-ELM-002-03b | P | Type and stereotype filters do not follow subtyping (sysml-project) | B5, B12 |
| T-ELM-002-04 | P | Paging with limits 1 to 100 returns every child once, with no empty last page | B9 |
| T-ELM-002-04b | P | Order is the same between queries | B3 |
| T-ELM-002-05 | P | Foreign, cross-parent and cross-filter cursors are invalid; changing the limit is allowed | B8 |
| T-ELM-002-06 | P | A refused create (REQUIRED\_PROFILE\_MISSING) leaves nothing to find | CL-ELM-001 B1, B2 |
| T-ELM-002-07 | P | No project open | B11 |
| T-ELM-002-08 | P | Unknown parent | B4 |
| T-ELM-002-09 | P | Sixteen invalid bodies, each with its exact details | B10, G-014 |
| T-ELM-002-09b | P | A null cursor and the maximum limit are accepted | B9, B10 |

#### CL-ELM-003 Delete element, guarded

**T1 Intent.** Remove an element and everything it owns. It gives tests and users a cleanup path, and it is the first function to apply the guarded-write rule (G-007), which is why it absorbs the old CL-GRD-001 outline (D-010).

**T2 Interface.** MCP tool `cameo_delete_element` (REF; the reference deletes an element and its children with no preview step, so the guard is a DECISION here). HTTP `POST /api/v1/elements/{id}/delete` (DECISION). The body is a required JSON object; `{}` previews.

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| allow\_write | JSON boolean | no | Default false. Only `true` commits |

- Preview reply: `preview` (true), `would_delete` (array of `{id, type, name}`), `count` (integer, always the full total), `truncated` (boolean).
- Commit reply: exactly `{"preview": false, "deleted_count": n}`.

Errors: INVALID\_REQUEST, NO\_ACTIVE\_PROJECT, ELEMENT\_NOT\_FOUND, PROTECTED\_ELEMENT, ELEMENT\_READ\_ONLY, SESSION\_CONFLICT, TIMEOUT.

**T3 Behavior.**

- **B1 Preview by default.** (DECISION) Without `allow_write` true nothing changes, and a preview opens no write session.
- **B2 Ownership.** (REF) Owned elements are deleted with their owner.
- **B3 References owned elsewhere.** (ASSUMED; P-ELM-020) Whether Cameo also removes relationships and diagram shapes owned elsewhere that point at a deleted element. Whatever it removes, the preview must list.
- **B4 Protected root.** (DECISION) The root model returns 422 PROTECTED\_ELEMENT with `details` `{"id": ...}`, for a preview as well as a commit, so a preview never promises what a commit would refuse.
- **B5 Atomic.** (DECISION; G-006) A commit deletes everything or nothing, in one session (one undo step pending P-SES-002).
- **B6 Unknown ID.** (DECISION) 404 ELEMENT\_NOT\_FOUND with `details` `{"id": ...}`; deleting the same element again gives the same error.
- **B7 Caps and counts.** (DECISION) A preview lists at most 500 entries and sets `truncated` when `count` exceeds 500. Commits are not capped. A preview's `count` equals the next commit's `deleted_count` when nothing changed in between.
- **B8 Read-only elements.** (ASSUMED; P-ELM-021) Elements Cameo will not let you delete, such as those in a used profile, return 422 ELEMENT\_READ\_ONLY with `details` `{"id": ...}`.
- **B9 Listing order.** (DECISION) `would_delete` lists the target first, then its owned elements depth-first in containment order.
- **B10 Validation.** (DECISION) The first failing check returns INVALID\_REQUEST: (1) the body is not a JSON object, an empty body included (`not_a_json_object`); (2) an unknown field (`unknown`, G-014); (3) `allow_write` is not a JSON boolean (`wrong_type`), so the string "true", the number 1 and null never commit.
- **B11 Precedence.** (DECISION) INVALID\_REQUEST, NO\_ACTIVE\_PROJECT, ELEMENT\_NOT\_FOUND, PROTECTED\_ELEMENT, ELEMENT\_READ\_ONLY.

**T4 Examples.** F-ELM-003-a preview of a three-element tree, F-ELM-003-b its commit, F-ELM-003-c the protected root, F-ELM-003-d the string "true" rejected.

**T5 Non-functional.** Write timeout as G-008. Previews are capped at 500 entries.

| Test | Layer | Asserts | Backed by |
| --- | --- | --- | --- |
| T-ELM-003-01 | P | `{}` and `allow_write` false preview, list in B9 order and change nothing | B1, B9 |
| T-ELM-003-02 | P | A commit returns exactly `{preview: false, deleted_count: 1}`; a second delete is not found | B6 |
| T-ELM-003-03 | P | Owned elements are gone; siblings remain | B2 |
| T-ELM-003-04 | P | The root is protected in preview and commit | B4 |
| T-ELM-003-05 | P | Unknown ID in preview and commit | B6 |
| T-ELM-003-06 | P | Preview count equals the commit's deleted\_count | B7 |
| T-ELM-003-06b | P | 502 elements: the preview lists 500 and is truncated; the commit deletes all 502 | B7 |
| T-ELM-003-07 | P | Six invalid bodies, including non-boolean values that must not commit | B10 |
| T-ELM-003-08 | P | No project open | B11 |
| T-PH1-001 | P | The Phase 1 exit scenario in 5.1, end to end through every Phase 1 route | 5.1 |

## 6. Worked clause: CL-HSK-001 Status

**T1 Intent.** Let a client learn, cheaply and without touching the model, whether the plugin is alive and whether it matches the client.

**T2 Interface.**

- MCP tool `cameo_status` (REF), no parameters.
- HTTP `GET /api/v1/status` (REF). The reference also serves a legacy `/status` alias; this contract does not require it (D-002).
- Success data (DECISION; field set partly pending probes): `plugin_version` (string), `api_version` (integer), `cameo_version` (string or null), `project_open` (boolean), `port` (integer).
- The MCP tool returns that data plus `compatibility.clientCompatible` (boolean; field name REF).

**T3 Behavior.**

- B1 (DECISION): status works with no project open and reports `project_open=false`.
- B2 (DECISION): status never touches the EDT or a session, so it answers while the EDT is busy. The reference notes that Relation Map refresh can block the EDT.
- B3 (DECISION): when `clientCompatible` is false, the Python server refuses every non-status tool until the plugin is redeployed. The reference tells the operator to stop and redeploy in that case.
- B4 (DECISION): an unreachable plugin yields PLUGIN\_UNREACHABLE. HTTP 404 on a route the client knows yields PLUGIN\_OUT\_OF\_SYNC; the reference diagnoses a 404 after an update as a client and plugin mismatch.
- B5 (ASSUMED): how the plugin obtains the Cameo version string. Probe P-ENV-001 explores the candidates.

**T4 Examples.** F-HSK-001-a healthy with a project; F-HSK-001-b healthy with no project; F-HSK-001-c incompatible client; F-HSK-001-d plugin down. Payloads are captured after the first reviewed live run.

**T5 Non-functional.** Loopback bind only; local response under 1 s (DECISION).

**Tests.** T-HSK-001-01 schema validates (contract layer). T-HSK-001-02 no-project case (Java handler against the fake executor). T-HSK-001-03 answers while the fake EDT is blocked. T-HSK-001-04 mismatch refuses other tools. T-HSK-001-05 non-loopback bind is rejected. T-HSK-001-06 live conformance of -01 and -02.

### 6.1 CL-PRJ-001 Get project

**T1 Intent.** Tell a client which project is open and hand it the root model ID that every create request needs as its first parent (defect CD-002).

**T2 Interface.** MCP tool `cameo_get_project` (REF; the reference returns the project name, file path and root model ID). HTTP `GET /api/v1/project` (DECISION). Success data (DECISION): `name` (string), `file_path` (string, or null for a project never saved), `root_model_id` (string).

**T3 Behavior.** B1 (DECISION): with no project open the reply is 409 NO\_ACTIVE\_PROJECT with empty `details`. B2 (DECISION): read only, served off the EDT (G-005). B3 (ASSUMED): `file_path` is null for an unsaved project; needs a probe (P-PRJ-001, backlog).

**T4 Examples and T5 Non-functional.** F-PRJ-001-a and -b (illustrative). Local response under 1 s (DECISION).

**Tests.** T-PRJ-001-01 schema. T-PRJ-001-02 no project returns 409.

### 6.2 CL-GLB-001 Envelope and routing

**T1 Intent.** Make every reply, including failures and unroutable requests, machine-readable in one envelope with a stable status mapping.

**T2 Interface.** Rules G-001, G-002, G-010 and G-011 apply to every route under `/api/v1`.

**T3 Behavior.** B1 (DECISION): an unknown route returns 404 ROUTE\_NOT\_FOUND in the envelope, never an HTML page. B2 (DECISION): a known route with the wrong method returns 405 METHOD\_NOT\_ALLOWED. B3 (DECISION): every success reply is `ok` true with an object `data`; every failure has string `code` and `message` and object `details`; an unexpected failure is 500 INTERNAL\_ERROR with no stack trace.

**T4 Examples and T5 Non-functional.** None needed beyond the envelope in G-001.

**Tests.** T-GLB-001-01 unknown route. T-GLB-001-02 wrong method. T-GLB-001-03 success envelope.

## 7. Worked clause: CL-ELM-001 Create element

### 7.1 T1 Intent

Create one model element of a supported type under a given parent, as a single undoable change, and return its identity. Every later modeling capability depends on this one.

### 7.2 T2 Interface

MCP tool `cameo_create_element` (REF). HTTP `POST /api/v1/elements` (DECISION).

| Field | Type | Required | Rule | Tag |
| --- | --- | --- | --- | --- |
| type | string | yes | Exactly one token from 7.2.1, case-sensitive; otherwise UNSUPPORTED\_TYPE | DECISION |
| name | string | see B8 | Stored exactly as given, no trimming | DECISION |
| parent\_id | string | yes | ID of an existing element in the active project | REF (the reference example uses the root model ID) |
| metaclasses | array of string | only for Stereotype | UML metaclass names to bind; allowed values OPEN | REF |

Response `data` (DECISION): `id`, `type` (canonical token), `name`, `parent_id`, `applied_stereotypes` (array of names).

Error codes (all DECISION; mapping from Cameo exceptions is OPEN): INVALID\_REQUEST, UNSUPPORTED\_TYPE, PARENT\_NOT\_FOUND, NO\_ACTIVE\_PROJECT, REQUIRED\_PROFILE\_MISSING, INVALID\_PARENT\_FOR\_TYPE, SESSION\_CONFLICT, TIMEOUT, INTERNAL\_ERROR.

**7.2.1 Supported type tokens (REF, from the reference README):** Package, Profile, Stereotype, Class, Block, Property, FlowProperty, Port, Interface, Activity, UseCase, Actor, StateMachine, State, Pseudostate, InitialState, Requirement, InterfaceBlock, ConstraintBlock, ValueType, DataType, Signal, Enumeration, Component, Comment, Constraint, CallBehaviorAction, OpaqueAction, ActivityPartition, InitialNode, ActivityFinalNode, FlowFinalNode, DecisionNode, MergeNode, ForkNode, JoinNode, InputPin, OutputPin, Operation. The SysML aliases the reference names are Block, Requirement, ConstraintBlock, InterfaceBlock, ValueType and FlowProperty; the complete SysML set is OPEN.

### 7.3 T3 Behavior

- **B1 SysML types need their stereotype.** (REF; LIVE pending P-ELM-002 and P-ELM-004) For each SysML type the element is created with the matching SysML stereotype applied. If the stereotype cannot be resolved the request fails with REQUIRED\_PROFILE\_MISSING and creates nothing. It must never fall back to a plain UML element. Cameo supplies the lookup; the error is a bridge rule layered on top of it.
- **B2 Atomic on failure.** (DECISION; depends on P-SES-001) Any failure after the session opens cancels it and leaves the model unchanged.
- **B3 One session, one undo step.** (REF; needs P-SES-002) Each request opens and closes exactly one session, so Cameo's undo reverts the whole creation.
- **B4 Pseudostate.** (REF plus DECISION D-004) Creates an initial pseudostate and echoes type Pseudostate. InitialState creates the same thing and is an alias: the create response and every later read report it as Pseudostate (D-012). Other pseudostate kinds are out of scope and are rejected with UNSUPPORTED\_TYPE.
- **B5 Duplicate names.** (ASSUMED; P-ELM-003) Whether two siblings may share a name. The contract adopts whatever Cameo allows.
- **B6 Parent compatibility.** (ASSUMED; P-ELM-010) The table of (type, parent type) pairs Cameo accepts. Incompatible pairs fail with INVALID\_PARENT\_FOR\_TYPE.
- **B7 Not idempotent.** (DECISION) Repeating a request creates another element, subject to B5.
- **B8 Names.** (ASSUMED; P-ELM-011) Which types may be created without a name, and what Cameo does with empty or whitespace names. Until probed, name is required and non-blank.
- **B9 Serialization.** (REF) Concurrent create requests are serialized; the second waits, and neither interleaves with the other's session.

* **B10 Request validation.** (DECISION) The first failing check returns INVALID\_REQUEST with `details` `{"reason": ...}`, plus `"field"` where a field applies. In order: (1) the body is not a JSON object (`not_a_json_object`, no field); (2) a field other than type, name, parent\_id or metaclasses is present, the alphabetically first one reported (G-014) (`unknown`); (3) for type, name and parent\_id in that order, the field is absent (`missing`), is not a string (`wrong_type`) or is blank after trimming (`blank`); (4) metaclasses is present on a type other than Stereotype (`not_allowed`) or is not an array of strings (`wrong_type`). Tests: T-ELM-001-09.
* **B11 Error precedence.** (DECISION) First match wins, in this order: INVALID\_REQUEST, NO\_ACTIVE\_PROJECT, UNSUPPORTED\_TYPE, PARENT\_NOT\_FOUND, REQUIRED\_PROFILE\_MISSING, INVALID\_PARENT\_FOR\_TYPE. Tests: T-ELM-001-10a to -10d.

### 7.4 T4 Examples

Illustrative payloads in the DECISION schema. They are replaced by captured payloads after the first reviewed live run.

- **F-ELM-001-a, success.** Request `{"type":"Block","name":"Sensor","parent_id":"<ID:1>"}`. Response `{"ok":true,"data":{"id":"<ID:2>","type":"Block","name":"Sensor","parent_id":"<ID:1>","applied_stereotypes":["Block"]}}`.
- **F-ELM-001-b, no SysML profile.** Same request. Response `{"ok":false,"error":{"code":"REQUIRED_PROFILE_MISSING","details":{"stereotype":"Block"}}}`, and the model is unchanged.
- **F-ELM-001-c, unsupported type.** Request type `Widget`. Response error code UNSUPPORTED\_TYPE with details `{"type":"Widget"}`.
- **F-ELM-001-d, unknown parent.** Response error code PARENT\_NOT\_FOUND with details `{"parent_id":"<ID:9>"}`.

### 7.5 T5 Non-functional

- Write timeout is 30 s (G-008). On timeout the plugin returns TIMEOUT with no session left open.
- Requests are accepted only on loopback (A-004).
- Size limits on names are OPEN and not asserted.

### 7.6 Test obligations

Layers: C is the Python server against the fake plugin, J is the Java handler against the fake Cameo executor, L is live conformance, and P is the black-box conformance suite against a plugin's HTTP boundary (it runs against the fake plugin, the implementer's plugin and a live Cameo).

| Test | Layer | Asserts | Backed by |
| --- | --- | --- | --- |
| T-ELM-001-01 | C, J | A valid request returns the schema in 7.2 | F-ELM-001-a |
| T-ELM-001-02 | C | No token in 7.2.1 is rejected as UNSUPPORTED\_TYPE (acceptance also depends on B6); any other token is | 7.2.1, F-ELM-001-c |
| T-ELM-001-03 | J | A SysML type without the profile fails with REQUIRED\_PROFILE\_MISSING and creates nothing | B1, F-ELM-001-b |
| T-ELM-001-04 | C, J | An unknown parent returns PARENT\_NOT\_FOUND | F-ELM-001-d |
| T-ELM-001-05 | J | A forced mid-request failure leaves the model unchanged and no open session | B2 |
| T-ELM-001-06 | J | One session is opened and closed per request | B3 |
| T-ELM-001-07 | J | Two concurrent requests are serialized | B9 |
| T-ELM-001-08 | L | T-ELM-001-01 and -03 pass on a live Cameo | every LIVE statement |
| T-ELM-001-01b | P | The name is returned exactly as given, including spaces and accents | 7.2 name rule |
| T-ELM-001-09 | P | Each invalid body listed in B10 returns INVALID\_REQUEST with the stated details | B10 |
| T-ELM-001-10a to -10d | P | Error precedence: validation, then project, then type, then parent, then profile | B11, G-010 |

### 7.7 Open items blocking READY

- B1 needs P-ELM-002 (written, draft) and P-ELM-004 (mirror case with SysML present, backlog).
- B2 needs P-SES-001 (written, draft).
- B3 needs P-SES-002 (backlog).
- B5 needs P-ELM-003 (written, draft).
- B6 and B8 need P-ELM-010 and P-ELM-011 (backlog).
- The mapping from Cameo exceptions to error codes needs the failing cases from the probes above.

* Closed in v0.4: whether a failed create left nothing behind is now checked through CL-ELM-002 (T-ELM-002-06), which closes CD-005.

## 8. Probe backlog

| Probe | Hypothesis | Informs | Phase | State |
| --- | --- | --- | --- | --- |
| P-ENV-001 | Environment fingerprint: Java, Groovy, bound variables, available Application getters | G-003, CL-HSK-001 | 1 | Draft written |
| P-PRJ-001 | Name, file path and root ID can be read; the file path is null or empty for an unsaved project | CL-PRJ-001 B3 | 1 | Draft written |
| P-SES-001 | A cancelled session leaves no element behind | G-006, CL-ELM-001 B2 | 1 | Draft written |
| P-ELM-001 | A plain Class created in the root model returns an ID and is owned by the root | CL-ELM-001 | 1 | Draft written |
| P-ELM-002 | Without the SysML profile the Block stereotype does not resolve and applying it fails | CL-ELM-001 B1 | 1 | Draft written |
| P-ELM-003 | Two siblings can share a name | CL-ELM-001 B5 | 1 | Draft written |
| P-ELM-012 | Children come back in creation order, the same on every read | CL-ELM-002 B3 | 1 | Draft written |
| P-ELM-013 | Type names Cameo exposes for the root Model and plain UML elements (eClass, human type, Java class) | CL-ELM-002 B5 | 1 | Draft written |
| P-ELM-020 | Deleting a class removes a Generalization owned by another class that points at it | CL-ELM-003 B3 | 1 | Draft written |
| P-ELM-021 | Elements of a used profile are not editable, and how Cameo signals an attempt to remove one | CL-ELM-003 B8 | 1 | Draft written |
| P-SES-002 | Closing a session commits one undo step | CL-ELM-001 B3, CL-ELM-003 B5 | 1 | Backlog |
| P-SES-003 | Stuck-session and reset behavior, including the double-commit exception | G-006 | 1 | Backlog |
| P-THR-001 | Reads off the EDT are safe while a write is in flight | G-005 | 1 | Backlog |
| P-THR-002 | An EDT dispatch that overruns the timeout can be abandoned cleanly | G-008 | 1 | Backlog |
| P-ELM-004 | With SysML present, Block creation applies the stereotype | CL-ELM-001 B1 | 1 | Backlog |
| P-ELM-010 | (type, parent type) compatibility matrix | CL-ELM-001 B6 | 1 | Backlog |
| P-ELM-011 | Unnamed and blank-name creation by type | CL-ELM-001 B8 | 1 | Backlog |

The draft probes use Cameo API names written from general knowledge. They are unverified until a human reviews them against a live run.

## 9. Traceability matrix

| Requirement | Clause | Tests | Probes and fixtures |
| --- | --- | --- | --- |
| Create a typed element atomically | CL-ELM-001 | T-ELM-001-01 to -08 | P-ELM-001, P-SES-001; F-ELM-001-a |
| Reject SysML elements without a profile | CL-ELM-001 B1 | T-ELM-001-03 | P-ELM-002; F-ELM-001-b |
| Health check without model access | CL-HSK-001 | T-HSK-001-01 to -06 | P-ENV-001; F-HSK-001-a to -d |
| Every reply uses one envelope and a stable status mapping | CL-GLB-001 | T-GLB-001-01 to -03 | None needed |
| A client can learn the root model ID | CL-PRJ-001 | T-PRJ-001-01, -02 | F-PRJ-001-a, -b |
| Discover the plugin's routes and refuse a mismatch | CL-HSK-002 | T-HSK-002-01 to -05 | None needed; F-HSK-002-a |
| Read back an element and list a parent's children | CL-ELM-002 | T-ELM-002-01 to -09b | P-ELM-012, P-ELM-013; F-ELM-002-a to -d |
| Delete safely: preview first, root protected | CL-ELM-003 | T-ELM-003-01 to -08 | P-ELM-020, P-ELM-021; F-ELM-003-a to -d |
| Phase 1 works end to end | 5.1 exit criteria | T-PH1-001 | All Phase 1 probes |

## 10. Decisions log

| ID | Decision | State |
| --- | --- | --- |
| D-001 | Clean-room: the reference may inform the contract; implementation is built only from the contract | Decided |
| D-002 | The legacy `/status` alias is optional | Proposed |
| D-003 | Response envelope in G-001 | Proposed |
| D-004 | `Pseudostate` means initial pseudostate only | Proposed |
| D-005 | Probe executor transport: a Groovy macro shim run inside Cameo (authors only). The implementers' deliverable remains a Java plugin | Decided |
| D-006 | Tests assert error `code` and `details`, never `message` | Proposed |
| D-007 | The contract defines its own envelope, routes and error codes, so the reference cannot pass the conformance suite without an adapter. Decide whether to write one (the reference then validates the tests) or to validate the tests only on the fake and a live Cameo | Open |
| D-008 | Two packages with no shared code: cameo-probe for authors, and an implementer package (conformance suite, fake plugin, fixtures) | Proposed |
| D-009 | Deliver in phases: Basics, then Diagrams from scratch, then later work (5.1) | Decided |
| D-010 | Guarded delete (CL-ELM-003) replaces the separate guarded-write outline CL-GRD-001 | Proposed |
| D-011 | No CORS headers and JSON-only bodies, unlike the reference (G-013) | Proposed |
| D-012 | InitialState is an alias of Pseudostate; responses and reads report the canonical Pseudostate | Proposed |
| D-013 | Exact path matching; split the raw path before decoding; literal segments beat templates (G-011) | Proposed |
| D-014 | Validation is independent of JSON key order; the alphabetically first unknown field is reported (G-014) | Proposed |
| D-015 | Query semantics: exact filters with no subtyping, cursors bound to parent and filters but not limit, no empty last page, paging consistent only while children are unchanged (CL-ELM-002 B8, B9, B12) | Proposed |
| D-016 | Delete: a body is required, only a JSON boolean true commits, and the root is protected in preview too (CL-ELM-003 B4, B10) | Proposed |
| D-017 | The Phase 1 exit scenario is itself a conformance test (T-PH1-001), run against the fake and later against a live Cameo | Decided |

## 11. Contract defect log (blind builds)

One row per question, assumption or deviation raised by an implementer.

| Defect | Build round | Clause | Symptom | Fix | Closed in |
| --- | --- | --- | --- | --- | --- |
| CD-001 | Author build 1 | G-002 | Unknown routes had a status but no error code | Added ROUTE\_NOT\_FOUND and METHOD\_NOT\_ALLOWED (G-002, G-011) | v0.2 |
| CD-002 | Author build 1 | CL-ELM-001 | No clause told a client how to obtain the root model ID that parent\_id needs | Added CL-PRJ-001 | v0.2 |
| CD-003 | Author build 1 | CL-ELM-001 | INVALID\_REQUEST was listed but nothing defined an invalid request or its details | Added B10 | v0.2 |
| CD-004 | Author build 1 | CL-ELM-001 | No order was given when several errors apply | Added B11 and G-010 | v0.2 |
| CD-005 | Author build 1 | CL-ELM-001 B1, B2 | "Creates nothing" and "model unchanged" could not be observed over HTTP | CL-ELM-002 and T-ELM-002-06 | v0.4 |
| CD-006 | Author build 1 | CL-ELM-001 test -02 | "Every token is accepted" depends on parent compatibility (B6), which is OPEN | Reworded to "no token is rejected as UNSUPPORTED\_TYPE" | v0.2 |
| CD-007 | Author build 2 | CL-ELM-001 B4 | Pseudostate and InitialState create the same thing, so a get could not round-trip both | InitialState is an alias reported as Pseudostate (D-012) | v0.4 |
| CD-008 | Author build 2 | G-011 | `/api/v1/elements/query` also matched `/api/v1/elements/{id}`, so "query" could be read as an element ID | Literal segments win; raw path split before decoding (D-013) | v0.4 |
| CD-009 | Author build 2 | CL-ELM-001 B10 | "The first unknown field" depended on JSON key order, which not every library keeps | Alphabetically first is reported (G-014) | v0.4 |
| CD-010 | Author build 2 | CL-ELM-002 | Nothing said whether a cursor survives a changed limit or filter, whether a last page can be empty, or what happens if children change mid-paging | B8 and B9 (D-015) | v0.4 |
| CD-011 | Author build 2 | CL-ELM-003 | Nothing said whether a root preview succeeds, or whether `"true"` as a string commits | B4 and B10 (D-016) | v0.4 |
| CD-012 | Author build 2 | T-ELM-002-03 (a test) | The test itself relied on duplicate sibling names, an OPEN item (CL-ELM-001 B5); the fake refused with 501 UNMODELED | Test rewritten with distinct names | v0.4 |

## 12. Feasibility metrics

- Share of normative statements tagged LIVE or DECISION.
- Defects per clause per blind-build round, by tier.
- Share of fake-executor behaviors confirmed on a live Cameo.
- Probe-discovered behaviors that no reference documentation mentions.
- Implementer edits to approved tests (target: zero).

## 13. Executable artifacts (status at v0.4)

Two packages, built tests first and each verified from a fresh unzip. Nothing has run against a live Cameo yet.

| Artifact | Package | Covers | Result |
| --- | --- | --- | --- |
| Conformance suite | Implementer | 49 black-box test methods: CL-GLB-001 (4), CL-HSK-001 (3), CL-HSK-002 (4), CL-PRJ-001 (2), CL-ELM-001 (11), CL-ELM-002 (15), CL-ELM-003 (9) and T-PH1-001 (1) | Every test runs in at least one of the three scenarios |
| Fake plugin | Implementer | All seven Phase 1 routes per the contract; 501 UNMODELED where CL-ELM-001 B5 and B6 are OPEN | Passes the suite in all three scenarios |
| Fixtures | Implementer | 18 request and response pairs for six clauses, some with setup steps | Illustrative; a test checks they match the fake, and regeneration is byte-identical |
| Fault injection | Implementer | 16 deliberate defects in the fake, each breaking one rule | All 16 caught by the intended test |
| Probe harness | Authors | 10 draft probes: P-ENV-001, P-PRJ-001, P-SES-001, P-ELM-001 to -003, -012, -013, -020 and -021 | 74 harness tests pass; no probe has run live |
| Probe shim and doctor | Authors | A Groovy macro that runs the harness's snippets inside Cameo, and 18 acceptance checks (doctor) for it | Doctor and its tests pass against a Python stand-in that catches 11 injected shim faults. The Groovy itself has not been run |

Test names carry the contract test IDs (`test_t_elm_001_09_invalid_requests` is T-ELM-001-09). Still to build: the fake Cameo executor (layer J, from probe evidence), tests T-ELM-001-05 to -07 and T-HSK-001-03 and -04, and the clauses still marked Outline.


