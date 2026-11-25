package com.nomagic.uml2.ext.magicdraw.classes.mdkernel
class NamedElement extends Element {
  String name
  String getName() { name }
  void setName(String n) { name = n }
  String getHumanName() { metaName() + " " + name }
}
