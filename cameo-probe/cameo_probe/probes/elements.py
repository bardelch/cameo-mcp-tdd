from ..model import Probe, Step
from .common import CLEANUP

PROBES = (
    Probe(
        id="P-ELM-001",
        family="elements",
        hypothesis=("A plain UML Class added to the root model inside a committed session gets a non-empty "
                    "ID, keeps the requested name and is owned by the root model."),
        clauses=("CL-ELM-001",),
        action=Step("create-class", r'''
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def out = [ok: true]
try {
  sm.createSession(project, "probe P-ELM-001")
  def c = ef.createClassInstance()
  c.setName("__probe_elm001__")
  com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().addElement(c, primaryModel)
  out.id = c.getID()
  out.name = c.getName()
  out.javaType = c.getClass().getName()
  out.rootId = primaryModel.getID()
  out.ownerId = c.getOwner() == null ? null : c.getOwner().getID()
  out.ownerIsRoot = (c.getOwner() == primaryModel)
  sm.closeSession(project)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
'''),
        observe=(Step("find-by-name", r'''
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def found = primaryModel.getOwnedElement().findAll { named.isInstance(it) && it.getName() == "__probe_elm001__" }
return __json([ok: true, count: found.size(), ids: found.collect { it.getID() }])
'''),),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-002",
        family="elements",
        hypothesis=("In a project without the SysML profile the Block stereotype does not resolve, so the "
                    "bridge, not Cameo, must raise REQUIRED_PROFILE_MISSING; the probe also records what "
                    "applying a null stereotype does."),
        clauses=("CL-ELM-001",),
        precondition=Step("sysml-absent", r'''
def st = null
def err = null
try {
  st = com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper.getStereotype(project, "Block", "SysML")
} catch (Throwable t) {
  err = t.getClass().getName() + ": " + t.getMessage()
}
if (err != null) { return __json([ok: false, reason: "stereotype lookup failed: " + err]) }
if (st != null) { return __json([ok: false, reason: "SysML Block stereotype resolves; run against a project without the SysML profile"]) }
return __json([ok: true])
'''),
        action=Step("lookup-and-apply-null", r'''
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def helper = com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper
def out = [ok: true]
try {
  sm.createSession(project, "probe P-ELM-002")
  def c = ef.createClassInstance()
  c.setName("__probe_elm002__")
  com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().addElement(c, primaryModel)
  def st = helper.getStereotype(project, "Block", "SysML")
  out.lookup = (st == null) ? "null" : "found"
  try {
    helper.addStereotype(c, (com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype) st)
    out.applyNull = [threw: false]
  } catch (Throwable t) {
    out.applyNull = [threw: true, type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  }
  out.stereotypesAfter = helper.getStereotypes(c).collect { it.getName() }
  sm.cancelSession(project)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
'''),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-003",
        family="elements",
        hypothesis="Two sibling elements may share the same name under one parent.",
        clauses=("CL-ELM-001",),
        action=Step("create-two-same-name", r'''
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def out = [ok: true, created: []]
try {
  sm.createSession(project, "probe P-ELM-003")
  2.times {
    def c = ef.createClassInstance()
    c.setName("__probe_elm003__")
    com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().addElement(c, primaryModel)
    out.created << c.getID()
  }
  sm.closeSession(project)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
'''),
        observe=(Step("count-by-name", r'''
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def n = primaryModel.getOwnedElement().findAll { named.isInstance(it) && it.getName() == "__probe_elm003__" }.size()
return __json([ok: true, count: n])
'''),),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-012",
        family="elements",
        hypothesis=("A package's owned elements are returned in creation order, and the order is the same "
                    "on every read (CL-ELM-002 B3)."),
        clauses=("CL-ELM-002",),
        action=Step("create-three-then-read-twice", r"""
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def mem = com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance()
def out = [ok: true]
try {
  sm.createSession(project, "probe P-ELM-012")
  def pkg = ef.createPackageInstance()
  pkg.setName("__probe_elm012__")
  mem.addElement(pkg, primaryModel)
  ["c2", "c0", "c1"].each { n ->
    def c = ef.createClassInstance()
    c.setName(n)
    mem.addElement(c, pkg)
  }
  sm.closeSession(project)
  out.firstRead = pkg.getOwnedElement().collect { it.getName() }
  out.secondRead = pkg.getOwnedElement().collect { it.getName() }
  out.packagedRead = pkg.getPackagedElement().collect { it.getName() }
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
"""),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-013",
        family="elements",
        hypothesis=("The root model and plain UML elements expose a metaclass name the bridge can report as "
                    "its type (\"Model\", \"Class\"); records the candidates: EMF eClass name, human type and "
                    "Java class (CL-ELM-002 B5)."),
        clauses=("CL-ELM-002",),
        action=Step("read-type-names", r"""
def describe = { e ->
  def d = [javaClass: e.getClass().getName()]
  try { d.eClass = e.eClass().getName() } catch (Throwable t) { d.eClass = "ERROR " + t.getClass().getName() }
  try { d.humanType = e.getHumanType() } catch (Throwable t) { d.humanType = "ERROR " + t.getClass().getName() }
  try { d.humanName = e.getHumanName() } catch (Throwable t) { d.humanName = "ERROR " + t.getClass().getName() }
  try { d.owner = e.getOwner() == null ? null : e.getOwner().getID() } catch (Throwable t) { d.owner = "ERROR" }
  return d
}
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def out = [ok: true, root: describe(primaryModel)]
try {
  sm.createSession(project, "probe P-ELM-013")
  def c = ef.createClassInstance()
  c.setName("__probe_elm013__")
  com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().addElement(c, primaryModel)
  out.plainClass = describe(c)
  sm.cancelSession(project)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
"""),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-020",
        family="elements",
        hypothesis=("Deleting a class removes a Generalization owned by another class that points at it, "
                    "so a delete preview must list relationships owned elsewhere (CL-ELM-003 B3)."),
        clauses=("CL-ELM-003",),
        setup=(Step("build-a-b-generalization", r"""
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def mem = com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance()
def out = [ok: true]
try {
  sm.createSession(project, "probe P-ELM-020 setup")
  def pkg = ef.createPackageInstance()
  pkg.setName("__probe_elm020__")
  mem.addElement(pkg, primaryModel)
  def a = ef.createClassInstance(); a.setName("A"); mem.addElement(a, pkg)
  def b = ef.createClassInstance(); b.setName("B"); mem.addElement(b, pkg)
  def g = ef.createGeneralizationInstance()
  g.setGeneral(a)
  g.setSpecific(b)
  mem.addElement(g, b)
  sm.closeSession(project)
  out.generalizationsOnB = b.getGeneralization().size()
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
"""),),
        action=Step("delete-a", r"""
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def pkg = primaryModel.getOwnedElement().find { named.isInstance(it) && it.getName() == "__probe_elm020__" }
def out = [ok: true]
if (pkg == null) { return __json([ok: false, reason: "setup package missing"]) }
def a = pkg.getOwnedElement().find { named.isInstance(it) && it.getName() == "A" }
try {
  sm.createSession(project, "probe P-ELM-020 delete")
  com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().removeElement(a)
  sm.closeSession(project)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
"""),
        observe=(Step("what-is-left-on-b", r"""
def named = com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement
def pkg = primaryModel.getOwnedElement().find { named.isInstance(it) && it.getName() == "__probe_elm020__" }
def b = pkg.getOwnedElement().find { named.isInstance(it) && it.getName() == "B" }
def gens = b.getGeneralization()
return __json([ok: true, packageChildren: pkg.getOwnedElement().collect { named.isInstance(it) ? it.getName() : it.getClass().getSimpleName() },
               generalizationsOnB: gens.size(),
               danglingGeneral: gens.collect { it.getGeneral() == null }])
"""),),
        teardown=(CLEANUP,),
    ),
    Probe(
        id="P-ELM-021",
        family="elements",
        hypothesis=("Elements of a used profile are not editable, and Cameo signals an attempt to remove one; "
                    "records isEditable and what removeElement does inside a cancelled session (CL-ELM-003 B8)."),
        clauses=("CL-ELM-003",),
        action=Step("try-remove-profile-element", r"""
def sm = com.nomagic.magicdraw.openapi.uml.SessionManager.getInstance()
def helper = com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper
def profile = null
["UML Standard Profile", "StandardProfile", "MagicDraw Profile"].each { n ->
  if (profile == null) { try { profile = helper.getProfile(project, n) } catch (Throwable ignored) { } }
}
if (profile == null) { return __json([ok: false, reason: "no standard profile found by name"]) }
def out = [ok: true, profile: profile.getName()]
try { out.isEditable = profile.isEditable() } catch (Throwable t) { out.isEditable = "ERROR " + t.getClass().getName() }
try {
  out.inAttachedProject = com.nomagic.magicdraw.core.ProjectUtilities.isElementInAttachedProject(profile)
} catch (Throwable t) { out.inAttachedProject = "ERROR " + t.getClass().getName() }
try {
  sm.createSession(project, "probe P-ELM-021")
  try {
    com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance().removeElement(profile)
    out.remove = [threw: false]
  } catch (Throwable t) {
    out.remove = [threw: true, type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  }
  sm.cancelSession(project)
  out.stillPresent = (helper.getProfile(project, profile.getName()) != null)
} catch (Throwable t) {
  out.ok = false
  out.error = [type: t.getClass().getName(), message: String.valueOf(t.getMessage())]
  try { sm.cancelSession(project) } catch (Throwable ignored) { }
}
return __json(out)
"""),
        teardown=(CLEANUP,),
    ),
)
