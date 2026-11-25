/* probe_shim_stop.groovy: stops the author probe shim and forgets its token. */
import javax.swing.UIManager

def KEY = "cameo.probe.shim"
def holder = UIManager.get(KEY)
if (holder instanceof Map) {
    try { if (holder.timer != null) { holder.timer.cancel() } } catch (Throwable ignored) { }
    try { if (holder.server != null) { holder.server.stop(0) } } catch (Throwable ignored) { }
    try { if (holder.executor != null) { holder.executor.shutdownNow() } } catch (Throwable ignored) { }
    UIManager.put(KEY, null)
    return "Cameo probe shim stopped"
}
return "Cameo probe shim was not running"
