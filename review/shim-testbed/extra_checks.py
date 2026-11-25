"""Targeted checks against a running shim on 127.0.0.1:18750 (token testtoken)."""
import http.client, json, threading, time, sys
H = {"Content-Type": "application/json", "X-Probe-Token": "testtoken"}

def post(code, thread="edt", timeout=60):
    c = http.client.HTTPConnection("127.0.0.1", 18750, timeout=timeout)
    c.request("POST", "/probe", json.dumps({"code": code, "thread": thread}), H)
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, json.loads(body)

which = sys.argv[1]
if which == "chunked":
    # 3 MB body sent chunked, no Content-Length: the 1 MB cap is checked against the header only.
    big = json.dumps({"code": "return 'x'.size() + " + "0+" * 1_500_000 + "0", "thread": "http"}).encode()
    c = http.client.HTTPConnection("127.0.0.1", 18750, timeout=120)
    c.putrequest("POST", "/probe"); [c.putheader(k, v) for k, v in H.items()]
    c.putheader("Transfer-Encoding", "chunked"); c.endheaders()
    for i in range(0, len(big), 65536):
        part = big[i:i+65536]; c.send(b"%x\r\n" % len(part) + part + b"\r\n")
    c.send(b"0\r\n\r\n")
    r = c.getresponse(); body = r.read()
    print("chunked body bytes:", len(big), "-> HTTP", r.status, body[:200])
    # same size with Content-Length
    c = http.client.HTTPConnection("127.0.0.1", 18750, timeout=60)
    c.request("POST", "/probe", big, H); r = c.getresponse()
    print("Content-Length body -> HTTP", r.status, r.read()[:120])
elif which == "edt":
    post("System.clearProperty('probe.late'); return 'ok'", "http")
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("blocker", post("Thread.sleep(40000); return 'slept'")))
    t1.start(); time.sleep(1)
    t0 = time.time()
    res["queued"] = post("System.setProperty('probe.late', 'RAN'); return 'ran'")
    res["queued_s"] = round(time.time() - t0, 1)
    t1.join()
    time.sleep(2)
    res["late_marker_after_blocker"] = post("return System.getProperty('probe.late')", "http")
    for k, v in res.items(): print(k, v)
elif which == "status_while_busy":
    # http thread must answer while the EDT is blocked
    t1 = threading.Thread(target=lambda: post("Thread.sleep(8000); return 1")); t1.start(); time.sleep(1)
    t0 = time.time(); print("http while EDT busy:", post("return 'alive'", "http"), round(time.time()-t0, 2), "s"); t1.join()
