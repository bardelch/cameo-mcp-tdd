from ..model import Step

# Removes everything a probe created. Convention (enforced by test_probes.py): every probe creates
# its elements DIRECTLY under the root model, or inside a package that is, named "__probe_<id>__".
# Anything a probe creates elsewhere is not cleaned up and shows up as left_state.
CLEANUP = Step(name="cleanup-probe-elements", code=r'''
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def removed = []
try {
  sm.createSession(project, "probe cleanup")
  def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
  new ArrayList(primaryModel.getOwnedElement()).each { e ->
    if (named.isInstance(e) && e.getName() != null && e.getName().startsWith("__probe_")) {
      removed << e.getName()
      com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().removeElement(e)
    }
  }
  sm.closeSession(project)
} catch (Throwable t) {
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
  return __json([ok: false, error: [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]])
}
return __json([ok: true, removed: removed])
''')


# Fingerprint of the model taken before each run and after its teardown; any difference means the
# probe left state behind (README: INCONCLUSIVE). Counts every element under the root, plus the
# root's direct children by ID and name. Read-only.
STATE_SNAPSHOT = Step(name="state-snapshot", code=r"""
if (primaryModel == null) { return __json([ok: true, project: false]) }
def total = 0
def walk
walk = { e -> e.getOwnedElement().each { total++; walk(it) } }
walk(primaryModel)
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def top = primaryModel.getOwnedElement().collect { (it.getID()) + "|" + (named.isInstance(it) ? it.getName() : "") }.sort()
return __json([ok: true, total: total, top: top])
""")
