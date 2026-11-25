from ..model import Probe, Step
from .common import CLEANUP

PROBES = (
    Probe(
        id="P-SES-001",
        family="sessions",
        hypothesis=("An element added inside a session that is then cancelled is absent from its owner "
                    "afterwards, so a cancelled write leaves no partial state."),
        clauses=("CL-ELM-001",),
        action=Step("add-then-cancel", r'''
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def out = [ok: true, opened: false, cancelled: false]
try {
  sm.createSession(project, "probe P-SES-001")
  out.opened = true
  def c = ef.createClassInstance()
  c.setName("__probe_ses001__")
  com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().addElement(c, primaryModel)
  out.addedInSession = true
  sm.cancelSession(project)
  out.cancelled = true
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  if (out.opened && !out.cancelled) { try { sm.cancelSession(project) } catch (Throwable ignored) { } }
}
return __json(out)
'''),
        observe=(Step("count-leftovers", r'''
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def n = primaryModel.getOwnedElement().findAll { named.isInstance(it) && it.getName() == "__probe_ses001__" }.size()
return __json([ok: true, remaining: n])
'''),),
        teardown=(CLEANUP,),
    ),
)
