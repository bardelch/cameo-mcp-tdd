# cameo-probe author package: review (2026-11-24)

Scope: the author package (`cameo-probe/`) against contract v0.4. There is no live Cameo here, so the
unmodified Groovy shim was run in Docker (Groovy 2.5.9, 3.0 and 4.0.33) against a stub `com.nomagic`
API (`review/shim-testbed/`). That proves the shim and harness plumbing. It does **not** prove any
Cameo API name the probes use.

## Verdict
The harness is well built and the shim works on its first real run: `doctor` passed 18/18 in both
project and no-project modes, restart keeps the token, and the stop script works. Two defects could
produce **false evidence** or **unannounced model writes**, though, and both should be fixed before
the first live run. The fixes for everything below are applied to `cameo-probe/` in the commit
"Apply author-package review fixes". Tests went from 74 to 87, all green.

## Findings, most severe first
1. **In-snippet failures were recorded as evidence** (`runner.py`). Only transport errors failed a run.
   A snippet returning `{"ok": false, ...}` (session threw, no project, setup missing) came out
   LIVE_DRAFT and "stable". Observed: with a broken stub, P-SES-001's add threw, yet its observe step
   recorded `remaining: 0`, which reads as proof that "cancel leaves nothing behind". After review
   that would have become LIVE. Fix: a top-level `ok:false` in any phase is a probe failure.
2. **The shim's EDT timeout misreported a running snippet as "cancelled before it ran"**
   (`probe_shim.groovy` `dispatch`). `FutureTask.cancel(false)` returns true for a task that is
   already running. Observed: a 28 s snippet was reported cancelled at 25 s, then wrote to the
   model anyway. Fix: an `AtomicBoolean` claim decides which side wins. Re-tested: a running snippet
   is now reported "still running", and a queued one is cancelled and provably never runs.
3. **"Left state behind" was defined but never checked.** Fix: `run` snapshots the model (element
   count plus the root's children) before each run and after teardown; a difference gives the new
   `left_state` outcome, which counts as INCONCLUSIVE. `--no-state-check` turns it off.
4. **Probes ran with no project open** and produced LIVE_DRAFT reports. Fix: `Probe.needs_project`
   (False only for P-ENV-001); `run` refuses with exit 2. A failed fingerprint now stops the run.
5. **The 1 MB body cap was bypassable** with a chunked request (no Content-Length): 3 MB was read and
   compiled. Fix: the stream read itself is capped and over-limit bodies get 413. Re-tested.
6. **P-ELM-021 is destructive if cancel does not roll back**: it removes a standard profile inside a
   cancelled session. The README now documents the run order (P-SES-001 reviewed first).
7. **The cleanup convention was implicit.** It is now documented and linted: everything added to
   the root must be named `__probe_*`.
8. Minor: `skipped_reason` was never normalized (fixed). The shim README said 73 tests
   (stale; updated). `test_cli.py` and `test_probes.py` define test classes after
   `if __name__ == "__main__"` (harmless). The implementer README still says "the slice has no
   delete clause" although CL-ELM-003 exists (implementer package, not patched).

## Still needs a live Cameo
Every Cameo API name in the probes and the shim (SessionManager, ModelElementsManager,
ElementsFactory, StereotypesHelper, ProjectUtilities, getHumanType, eClass, ...). Also the macro menu
path, Cameo's bundled Groovy version and its script classloader. The 7 backlog probes (P-SES-002/003,
P-THR-001/002, P-ELM-004/010/011) are not written.

Optional: a `doctor` check for finding 2 would need to block Cameo's EDT for about 25 s, so it is
left as a manual check (`late_write.py` in the testbed).

## Reproduce
    cd cameo-probe && python3 -m unittest discover -s tests -t .     # 87 tests
    # shim testbed (Docker), from the repo root:
    W=$PWD/review/shim-testbed
    docker run --rm -u $(id -u) -v $W:/w -w /w/stubs groovy:4.0-jdk17 bash -c 'groovyc -d /w/classes $(find . -name "*.groovy")'
    docker run -d --name shim --network host -v $W:/w -v $PWD/cameo-probe/shim:/shim \
      -e JAVA_OPTS="-Djava.awt.headless=true -Dcameo.probe.shim.token=t" \
      groovy:4.0-jdk17 groovy -cp /w/classes /w/run_shim.groovy /shim/probe_shim.groovy
    cd cameo-probe && CAMEO_PROBE_TOKEN=t python3 -m cameo_probe doctor --url http://127.0.0.1:18750/probe --expect-project yes
    python3 ../review/shim-testbed/late_write.py      # EDT timeout honesty (takes ~35 s)
