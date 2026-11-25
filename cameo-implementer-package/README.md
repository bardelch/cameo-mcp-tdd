# Cameo MCP Bridge: implementer package v0.4

Everything you may use, besides the contract document, to build the bridge. Build from the
contract alone: there is no reference repository and no probe harness in this package, and
you must not look for them.

## Contents

| Path | What it is |
| --- | --- |
| `contract_constants.py` | Machine-readable extract of the contract: routes' field sets, type tokens, error-to-status map. The document wins if they differ. |
| `conformance/` | Black-box tests for the plugin's HTTP boundary: every Phase 1 clause (CL-GLB-001, CL-HSK-001, CL-HSK-002, CL-PRJ-001, CL-ELM-001, CL-ELM-002, CL-ELM-003) plus the Phase 1 end-to-end scenario T-PH1-001. Test names carry the contract test IDs. |
| `fake_plugin/` | A contract-derived fake of the plugin, for building the Python MCP server without Cameo. |
| `fixtures/` | Request/response pairs per clause (illustrative until replaced by live captures). |
| `selfcheck/` | Tests of this package itself: the fake passes the suite in every scenario, every test runs in at least one scenario, the suite catches 16 injected faults, fixtures match the fake. |

Python 3.10+, standard library only.

## Build the Python server against the fake

    python -m fake_plugin --scenario sysml-project --port 18740

Scenarios: `no-project`, `uml-project` (no SysML profile), `sysml-project`.

## Check a plugin against the contract

    CAMEO_CONFORMANCE_URL=http://127.0.0.1:18740 \
    CAMEO_CONFORMANCE_SCENARIO=sysml-project \
    CAMEO_CONFORMANCE_DISPOSABLE=yes \
    python -m unittest discover -s conformance -t . -v

Run it once per scenario: tests that need another scenario are skipped, never faked.
`CAMEO_CONFORMANCE_DISPOSABLE=yes` is required by the tests that create elements, because the
slice has no delete clause; use a disposable project.

## Check this package

    python -m unittest discover -s selfcheck -t .

## Rules

- Never edit a conformance test to make it pass. A test you believe is wrong is a contract
  defect: write it down (contract section 11) and ask.
- The fake answers `501 UNMODELED` where the contract still lists behaviour as OPEN
  (duplicate sibling names, parent/type compatibility). Do not rely on or reproduce it.
- The fake never models read-only elements (CL-ELM-003 B8) or references owned elsewhere
  (B3); both wait on probes.
- Error `message` text is informative; tests assert `code` and `details` only.

## Not in this package yet

- The fake Cameo executor (test layer J). It must be built from probe evidence, and no live
  probe has run yet.
- Tests that need control of Cameo internals: T-ELM-001-05 (atomic failure), -06 (one session
  per request), -07 (serialization), T-HSK-001-03 (answers while the EDT is busy).
- Python-server tests (layer C): T-HSK-001-04 and T-HSK-002-05.
- Phase 2 clauses (relationships and diagrams), which are not written yet.
