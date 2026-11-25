/*
 * probe_shim.groovy: AUTHOR-ONLY probe shim, protocol v0, for the cameo-probe harness.
 *
 * Run this once inside Cameo's Groovy script/macro engine. It starts a small HTTP server on
 * 127.0.0.1 that evaluates the Groovy snippets the harness sends, inside the Cameo JVM.
 *
 * !! It executes arbitrary code with your Cameo session's rights. Use it only on a developer
 * !! machine, with a disposable project, and stop it when you are done (probe_shim_stop.groovy).
 *
 * Protocol v0
 *   POST /probe   Content-Type: application/json   X-Probe-Token: <token>
 *     request   {"code": "<groovy>", "thread": "edt" | "http"}      (thread defaults to edt)
 *     reply     {"ok": true,  "result": "<string or null>", "ran_on": "<thread name>"}
 *               {"ok": false, "error_type": "<class name>", "error_message": "<text>"}
 *   The snippet sees four bindings: application, project (the ACTIVE project when the request
 *   arrives), primaryModel and ef. They are null when no project is open.
 *   Protocol-level problems answer 4xx with the same error shape.
 *
 * Re-running this script restarts the shim and keeps the same token. The shim stops itself
 * after cfg.autoStopMinutes.
 */
import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpServer
import java.security.MessageDigest
import java.util.concurrent.Callable
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import java.util.concurrent.FutureTask
import java.util.concurrent.ThreadFactory
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.atomic.AtomicBoolean
import javax.swing.SwingUtilities
import javax.swing.UIManager

// ---- configuration: edit here --------------------------------------------------------------
def cfg = [
    host           : "127.0.0.1",   // keep on loopback
    port           : 18750,
    edtTimeoutMs   : 25000L,        // stop waiting for the EDT after this long
    maxBodyBytes   : 1048576,
    autoStopMinutes: 120            // the shim shuts itself down after this long
]
// --------------------------------------------------------------------------------------------

// A JVM-wide handle, so a re-run (or the stop script) can find the previous instance.
// UIManager is used because it is a global Object map that never rejects non-String values.
def KEY = "cameo.probe.shim"

def stopHolder = { Object holder ->
    if (holder instanceof Map) {
        try { if (holder.timer != null) { holder.timer.cancel() } } catch (Throwable ignored) { }
        try { if (holder.server != null) { holder.server.stop(0) } } catch (Throwable ignored) { }
        try { if (holder.executor != null) { holder.executor.shutdownNow() } } catch (Throwable ignored) { }
    }
}

def previous = UIManager.get(KEY)
String token = (previous instanceof Map ? previous.token : null) ?: System.getProperty("cameo.probe.shim.token") ?: UUID.randomUUID().toString()
stopHolder(previous)
UIManager.put(KEY, null)

def loader = this.getClass().getClassLoader() ?: Thread.currentThread().getContextClassLoader()

def failure = { String type, String message ->
    return [ok: false, error_type: type, error_message: (message ?: "")]
}

def respond = { HttpExchange ex, int status, Map payload ->
    byte[] bytes = groovy.json.JsonOutput.toJson(payload).getBytes("UTF-8")
    ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8")
    ex.sendResponseHeaders(status, bytes.length)
    ex.getResponseBody().write(bytes)
}

// Reads at most cfg.maxBodyBytes; returns null when the body is longer. The Content-Length check
// alone is not enough: a chunked request carries no Content-Length.
def readAll = { InputStream input ->
    ByteArrayOutputStream buffer = new ByteArrayOutputStream()
    byte[] chunk = new byte[8192]
    int n = input.read(chunk)
    while (n != -1) {
        buffer.write(chunk, 0, n)
        if (buffer.size() > cfg.maxBodyBytes) { return null }
        n = input.read(chunk)
    }
    return buffer.toByteArray()
}

// Browsers cannot reach this server by accident: Content-Type must be JSON (forces a CORS
// preflight we never answer), Host must be loopback (blocks DNS rebinding), and the token
// must match.
def hostAllowed = { HttpExchange ex ->
    String host = ex.getRequestHeaders().getFirst("Host")
    return host != null && (host == "127.0.0.1:${cfg.port}".toString() || host == "localhost:${cfg.port}".toString())
}

def tokenAllowed = { HttpExchange ex ->
    String supplied = ex.getRequestHeaders().getFirst("X-Probe-Token")
    return supplied != null && MessageDigest.isEqual(supplied.getBytes("UTF-8"), token.getBytes("UTF-8"))
}

def jsonContentType = { HttpExchange ex ->
    String type = ex.getRequestHeaders().getFirst("Content-Type")
    return type != null && type.toLowerCase().startsWith("application/json")
}

def runSnippet = { String code ->
    def app = null
    def proj = null
    try { app = com.nomagic.magicdraw.core.Application.getInstance() } catch (Throwable ignored) { }
    try { if (app != null) { proj = app.getProject() } } catch (Throwable ignored) { }
    def scope = new Binding()
    scope.setVariable("application", app)
    scope.setVariable("project", proj)
    scope.setVariable("primaryModel", proj == null ? null : proj.getPrimaryModel())
    scope.setVariable("ef", proj == null ? null : proj.getElementsFactory())
    def value = new GroovyShell(loader, scope).evaluate(code)
    return [value: (value == null ? null : String.valueOf(value)), ranOn: Thread.currentThread().getName()]
}

// "edt" queues the snippet on the Swing event dispatch thread and waits for it. If the EDT is
// busy for longer than cfg.edtTimeoutMs the snippet is cancelled BEFORE it starts, so it cannot
// run late and change the model after the client has given up. A snippet that is already
// running cannot be stopped.
def dispatch = { String thread, Closure work ->
    if (thread == "http") {
        return work.call()
    }
    // FutureTask.cancel(false) also "succeeds" on a task that is already running, so it cannot tell
    // the two timeout cases apart. Whoever claims `started` first decides: the EDT (the snippet
    // runs) or the timeout (the snippet is guaranteed never to run).
    def started = new AtomicBoolean(false)
    def task = new FutureTask({
        if (!started.compareAndSet(false, true)) { return null }
        work.call()
    } as Callable)
    SwingUtilities.invokeLater(task)
    try {
        return task.get(cfg.edtTimeoutMs as long, TimeUnit.MILLISECONDS)
    } catch (TimeoutException ignored) {
        boolean cancelled = started.compareAndSet(false, true)
        if (cancelled) { task.cancel(false) }
        throw new TimeoutException(cancelled
            ? "the EDT did not start the snippet within ${cfg.edtTimeoutMs} ms; it was cancelled before it ran".toString()
            : "the snippet is still running on the EDT after ${cfg.edtTimeoutMs} ms and cannot be stopped".toString())
    } catch (ExecutionException wrapped) {
        throw (wrapped.getCause() != null ? wrapped.getCause() : wrapped)
    }
}

def handler = { HttpExchange ex ->
    try {
        if (ex.getRequestMethod() != "POST") {
            respond(ex, 405, failure("MethodNotAllowed", "use POST"))
        } else if (!hostAllowed(ex)) {
            respond(ex, 403, failure("ForbiddenHost", "the Host header must be 127.0.0.1:${cfg.port} or localhost:${cfg.port}".toString()))
        } else if (!tokenAllowed(ex)) {
            respond(ex, 401, failure("Unauthorized", "missing or wrong X-Probe-Token header"))
        } else if (!jsonContentType(ex)) {
            respond(ex, 415, failure("UnsupportedMediaType", "Content-Type must be application/json"))
        } else {
            int declared = 0
            try { declared = Integer.parseInt(ex.getRequestHeaders().getFirst("Content-Length") ?: "0") } catch (Throwable ignored) { }
            if (declared > cfg.maxBodyBytes) {
                respond(ex, 413, failure("PayloadTooLarge", "the request body is over ${cfg.maxBodyBytes} bytes".toString()))
            } else {
                byte[] raw = readAll(ex.getRequestBody())
                def request = null
                if (raw != null) {
                    try {
                        request = new groovy.json.JsonSlurper().parseText(new String(raw, "UTF-8"))
                    } catch (Throwable ignored) { }
                }
                if (raw == null) {
                    respond(ex, 413, failure("PayloadTooLarge", "the request body is over ${cfg.maxBodyBytes} bytes".toString()))
                } else if (!(request instanceof Map) || !(request.code instanceof CharSequence)) {
                    respond(ex, 400, failure("BadRequest", "expected a JSON object with a string field named code"))
                } else {
                    String thread = request.thread == null ? "edt" : String.valueOf(request.thread)
                    if (thread != "edt" && thread != "http") {
                        respond(ex, 400, failure("BadRequest", "thread must be edt or http"))
                    } else {
                        String code = request.code.toString()
                        def reply
                        try {
                            def out = dispatch(thread, { runSnippet(code) })
                            reply = [ok: true, result: out.value, ran_on: out.ranOn]
                        } catch (Throwable t) {
                            reply = failure(t.getClass().getName(), t.getMessage())
                        }
                        respond(ex, 200, reply)
                    }
                }
            }
        }
    } catch (Throwable t) {
        try { respond(ex, 500, failure(t.getClass().getName(), t.getMessage())) } catch (Throwable ignored) { }
    } finally {
        ex.close()
    }
}

def executor = Executors.newCachedThreadPool({ Runnable r ->
    Thread t = new Thread(r, "cameo-probe-shim-http")
    t.setDaemon(true)
    return t
} as ThreadFactory)

def server
try {
    server = HttpServer.create(new InetSocketAddress(InetAddress.getByName(cfg.host), cfg.port as int), 0)
} catch (java.net.BindException e) {
    executor.shutdownNow()
    throw new IllegalStateException("port ${cfg.port} is busy: stop the other process, run probe_shim_stop.groovy, or change cfg.port".toString(), e)
}
server.createContext("/probe", handler as HttpHandler)
server.setExecutor(executor)
server.start()

def timer = new Timer("cameo-probe-shim-autostop", true)
timer.schedule({
    stopHolder([server: server, executor: executor, timer: timer])
    def current = UIManager.get(KEY)
    if (current instanceof Map && current.server == server) { UIManager.put(KEY, null) }
    println "Cameo probe shim stopped itself after ${cfg.autoStopMinutes} minutes"
} as TimerTask, (cfg.autoStopMinutes as long) * 60000L)

UIManager.put(KEY, [server: server, executor: executor, timer: timer, token: token])

String banner = "Cameo probe shim listening on http://${cfg.host}:${cfg.port}/probe  token=${token}".toString()
println banner
try { com.nomagic.magicdraw.core.Application.getInstance().getGUILog().log(banner) } catch (Throwable ignored) { }
return banner
