// Evaluates the UNMODIFIED shim inside this JVM, then keeps the JVM alive (Cameo would).
evaluate(new File(args[0]))
Thread.sleep(Long.MAX_VALUE)
