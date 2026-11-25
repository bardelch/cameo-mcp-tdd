from ..model import Probe, Step

# Also used by the CLI to fingerprint the target before a run.
ENV_FINGERPRINT = Step(name="fingerprint", code=r'''
def info = [:]
info.java = System.getProperty("java.version")
info.os = System.getProperty("os.name")
info.groovy = GroovySystem.getVersion()
info.boundNames = binding.variables.keySet().collect { String.valueOf(it) }.sort()
info.hasProject = binding.hasVariable("project") && binding.getVariable("project") != null
if (info.hasProject) {
  info.projectName = String.valueOf(project.getName())
  info.hasPrimaryModel = binding.hasVariable("primaryModel") && binding.getVariable("primaryModel") != null
}
def getters = [:]
try {
  def app = com.nomagic.magicdraw.core.Application.getInstance()
  ["getProductVersion", "getVersion", "getProductName", "getName"].each { m ->
    if (app.metaClass.respondsTo(app, m)) {
      try { getters[m] = String.valueOf(app."$m"()) } catch (Throwable t) { getters[m] = "ERROR " + t.getClass().getName() }
    }
  }
} catch (Throwable t) {
  getters["_application"] = "ERROR " + t.getClass().getName()
}
info.applicationGetters = getters
return __json(info)
''')

PROBES = (
    Probe(
        id="P-ENV-001",
        family="env",
        hypothesis=("The shim binds project, application, primaryModel and ef, and the Java, Groovy and "
                    "Application details needed to fingerprint a Cameo build can be read."),
        action=ENV_FINGERPRINT,
        clauses=("CL-HSK-001",),
        needs_project=False,
    ),
)
