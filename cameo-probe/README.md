# cameo-probe (authors only)

Probe harness for the Cameo MCP Bridge TDD contract. It runs small experiments against a
live Cameo and records the observations the contract cites as evidence.

**Authoring tooling. Never give this package, the probe shim or the reference repository to
implementers** (contract section 2.4). Python 3.10+, standard library only.

## Run

    python -m unittest discover -s tests -t . -v      # harness tests, no Cameo needed
    python -m cameo_probe list
    python -m cameo_probe doctor --url http://127.0.0.1:18750/probe --expect-project yes   # trust no probe before this is clean
    python -m cameo_probe run --url http://127.0.0.1:18750/probe --family elements --repeat 3 --out evidence

Both need the shim's token: `--token <token>` or `CAMEO_PROBE_TOKEN`. The shim is in `shim/`
(see `shim/README.md`).

## How a probe works

A probe is a hypothesis plus Groovy snippets: optional precondition, setup, one action,
observation steps, and teardown (always run). Each snippet `return`s a JSON string
(`return __json([...])`). Behaviour under test is caught inside the snippet and returned;
anything that escapes is a probe failure, not an observation. A snippet that returns a top-level
`"ok": false` is also a probe failure (it could not do its job); put the behaviour under test in other
fields, as P-ELM-002's `applyNull` does. Snippets use fully qualified
names and no `import` lines, because the harness prepends a one-line prelude defining `__json`.

The runner repeats each probe, replaces IDs with `<ID:n>` and timestamps with `<TS>`
(`normalize.py`), compares runs, and writes `evidence/<family>/<probe>.json`. Reports carry no
wall-clock time, so re-runs diff cleanly.

## Evidence levels

| Level | Meaning |
| --- | --- |
| `SCRIPTED` | From a test double. Written only to `evidence/_scratch/`, never counted. |
| `LIVE_DRAFT` | Live run of a probe a human has not reviewed. |
| `LIVE` | Live, reviewed probe, stable across repeats. Only this upgrades a contract tag to LIVE. |
| `INCONCLUSIVE` | Live but failed, flaky or left state behind (`run` snapshots the model before each run and after its teardown; `--no-state-check` turns that off). |
| `SKIPPED` | Precondition not met on every run. |

Run order on a new Cameo: `doctor`, then P-ENV-001 and P-SES-001, and review P-SES-001 before the
rest. P-ELM-021 calls `removeElement` on a standard profile and relies on `cancelSession` to undo it,
which is exactly what P-SES-001 establishes. `run` refuses probes that need a project when none is
open (only P-ENV-001 runs without one).

Cleanup convention: a probe creates its elements directly under the root model, or inside a package
there, named `__probe_<id>__`; `CLEANUP` removes only those (checked by `tests/test_hardening.py`).

Review workflow: run the draft live, read the evidence, fix the snippet if it misbehaved, then
set `status="reviewed"` in the probe, re-run, and update the contract clause.

## Probe shim protocol v0

`HttpExecutor` POSTs `{"code": "<groovy>", "thread": "edt"|"http"}` with an `X-Probe-Token`
header and expects
`{"ok": true, "result": "<string>"}` or `{"ok": false, "error_type": "...", "error_message": "..."}`.
The shim runs the snippet inside the Cameo JVM with `project`, `application`, `primaryModel`
and `ef` bound. It executes arbitrary code: bind 127.0.0.1 only and probe disposable projects.
The shim is a Groovy macro, `shim/probe_shim.groovy` (contract D-005).

## Known gaps

- No Groovy snippet has been run: they use Cameo API names written from general knowledge
  and are all `draft`. The Python harness itself is tested (including with mutation checks).
- The shim's Groovy has run outside Cameo (Groovy 2.5.9, 3.0 and 4.0.33 in Docker, against a stub
  `com.nomagic` API): `doctor` passes 18/18 and every probe completes. Nothing has run against a live
  Cameo, so the Cameo API names are still unverified. `doctor` is the acceptance test for the shim.
- The default ID patterns in `normalize.py` are assumptions to confirm with P-ELM-001.
