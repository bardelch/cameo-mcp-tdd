# Author probe shim (Groovy), authors only

Lets the Python probe harness run Groovy snippets inside a live Cameo. It is **authoring
tooling**: never give it, the harness or the reference repository to implementers.

| File | Purpose |
| --- | --- |
| `probe_shim.groovy` | Starts the shim on `127.0.0.1:18750` and prints a token. Re-running restarts it. |
| `probe_shim_stop.groovy` | Stops it and forgets the token. |

## Run it

1. Copy both files onto the machine running Cameo.
2. Run `probe_shim.groovy` with Cameo's Groovy script or macro engine. The menu differs by
   version; in the versions I know it is Tools > Macros > Organize Macros... (add a macro,
   language Groovy, file `probe_shim.groovy`), then Tools > Macros > your macro. I have not
   confirmed those labels on your install: any way of running a Groovy script inside Cameo works.
3. Copy the token from Cameo's message window or log (`Cameo probe shim listening on ... token=...`).
4. Open a **disposable** project in Cameo, then on the harness machine:

       export CAMEO_PROBE_TOKEN=<token>
       python -m cameo_probe doctor --url http://127.0.0.1:18750/probe --expect-project yes

   `doctor` runs 18 checks with known answers: transport and escaping, errors and nulls, the
   four bindings, EDT versus HTTP thread, the harness prelude, probe P-ENV-001, and the
   security gates. **Do not trust probe results until it shows no FAIL.**
5. Run probes: `python -m cameo_probe run --url ... --probe P-ENV-001 --repeat 3`, then the
   rest. Stop the shim with `probe_shim_stop.groovy` (it also stops itself after 120 minutes).

Cameo and the harness on different machines: use an SSH tunnel to the loopback port. Do not
change `cfg.host` away from `127.0.0.1`.

## What it does

- `POST /probe` with `{"code": "...", "thread": "edt"|"http"}`; the reply is `{"ok": true, "result": "<string or null>", "ran_on": "<thread>"}` or `{"ok": false, "error_type": "...", "error_message": "..."}`.
- Snippets see `application`, `project` (the project active when the request arrives),
  `primaryModel` and `ef`; all are null when no project is open.
- `edt` (default) queues the snippet on the Swing event thread and waits up to 25 s. If the
  EDT never starts it, it is cancelled before it runs, so it cannot change the model after the
  client has given up. A snippet already running cannot be stopped; the reply then says so
  ("still running"), and the model may still change after the client has given up.
- The result is stringified; `null` stays `null`.
- Compile-error line numbers are one higher than in the probe, because the harness prepends a line.

## Security

It executes arbitrary code with your Cameo session's rights. It binds loopback only, requires
the `X-Probe-Token` header, requires `Content-Type: application/json` (a web page cannot send
that cross-origin without a preflight the shim never answers), rejects any `Host` header other
than `127.0.0.1:<port>` or `localhost:<port>` (blocks DNS rebinding), caps bodies at 1 MB, and
stops itself after two hours. The token appears in Cameo's log. Any local process that knows
it can run code as you in Cameo, so use a developer machine and disposable projects.

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `Address already in use` | Another process holds 18750. Run the stop script, or change `cfg.port` and the harness `--url`. |
| `doctor` fails at `ping` with HTTP 401 | Wrong or missing token. |
| `doctor` fails at `ping` with a connection error | The shim is not running; check Cameo's message window. |
| `groovy_json_available` fails | `groovy-json` is not on Cameo's classpath. The harness prelude needs it, so no probe can run until that is solved. |
| `project_binding_is_consistent` fails with `--expect-project yes` | No project is open or active in Cameo. |
| `default_thread_is_edt` or `http_thread_is_not_edt` fails | The shim is ignoring the `thread` field; tell me which one and I will fix it. |

## What is and is not verified

Verified: the Python side (the harness, `doctor` and their tests, including 11 injected shim faults
run against a Python stand-in), and the shim's Groovy itself, run unmodified on Groovy 2.5.9, 3.0
and 4.0.33 against a stub `com.nomagic` API: `doctor` 18/18, every probe completes, an EDT timeout
reports truthfully whether the snippet ran, and chunked bodies over 1 MB are refused.

**Not verified: anything inside a real Cameo.** The macro menu, the classloader Cameo gives the
script, its bundled Groovy version, and every Cameo API name the probes use. Your first `doctor` run
on Cameo is the real test, and each failure names the behavior at fault. Probes stay `draft` until
a live run has been reviewed.
