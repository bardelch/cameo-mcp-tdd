import http.client, json, time
H = {"Content-Type": "application/json", "X-Probe-Token": "testtoken"}
def post(code, thread="edt"):
    c = http.client.HTTPConnection("127.0.0.1", 18750, timeout=60)
    c.request("POST", "/probe", json.dumps({"code": code, "thread": thread}), H)
    r = c.getresponse(); return json.loads(r.read())
post("System.clearProperty('probe.late')", "http")
# Snippet starts immediately, overruns the 25 s EDT wait, then writes.
print("reply:", post("Thread.sleep(28000); System.setProperty('probe.late','WROTE AFTER CLIENT GAVE UP'); return 1"))
time.sleep(5)
print("marker:", post("return System.getProperty('probe.late')", "http")["result"])
