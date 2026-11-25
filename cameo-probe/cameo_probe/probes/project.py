from ..model import Probe, Step

PROBES = (
    Probe(
        id="P-PRJ-001",
        family="project",
        hypothesis=("A project's name, file path and root model ID can be read, and the file path is null or "
                    "empty for a project that has never been saved (CL-PRJ-001 B3)."),
        clauses=("CL-PRJ-001",),
        action=Step("read-project", r'''
def out = [ok: true, name: String.valueOf(project.getName()), rootId: primaryModel.getID()]
["getFileName", "getFilePath", "getLocationURI"].each { m ->
  if (project.metaClass.respondsTo(project, m)) {
    try { def v = project."$m"(); out[m] = (v == null ? null : String.valueOf(v)) } catch (Throwable t) { out[m] = "ERROR " + t.getClass().getName() }
  }
}
try { out.isRemote = project.isRemote() } catch (Throwable t) { out.isRemote = "ERROR " + t.getClass().getName() }
return __json(out)
'''),
    ),
)
