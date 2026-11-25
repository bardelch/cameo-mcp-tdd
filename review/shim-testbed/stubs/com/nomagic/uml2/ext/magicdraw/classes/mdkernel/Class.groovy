package com.nomagic.uml2.ext.magicdraw.classes.mdkernel
class Class extends NamedElement {
  Collection getGeneralization() { rawOwned().findAll { it instanceof Generalization } }
}
