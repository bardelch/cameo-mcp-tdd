package com.nomagic.magicdraw.openapi.uml
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.*
class ModelElementsManager {
  static final ModelElementsManager INSTANCE = new ModelElementsManager()
  static ModelElementsManager getInstance() { INSTANCE }
  void addElement(Element e, Element owner) {
    def sm = SessionManager.getInstance()
    if (!owner.isEditable()) throw new ReadOnlyElementException("owner is read-only")
    owner.rawOwned() << e
    e.owner = owner
    sm.record { owner.rawOwned().remove(e); e.owner = null }
  }
  void removeElement(Element e) {
    def sm = SessionManager.getInstance()
    if (!e.isEditable()) throw new ReadOnlyElementException("Element is read-only: " + e.getID())
    def owner = e.owner
    int idx = owner.rawOwned().indexOf(e)
    owner.rawOwned().remove(e)
    e.owner = null
    sm.record { owner.rawOwned().add(idx, e); e.owner = owner }
    // remove generalizations elsewhere that point at e (mimics Cameo's referential cleanup)
    def root = owner; while (root.owner != null) root = root.owner
    def all = []; def walk; walk = { x -> x.rawOwned().each { all << it; walk(it) } }; walk(root)
    all.findAll { it instanceof Generalization && it.general == e }.each { g -> removeElement(g) }
  }
}
