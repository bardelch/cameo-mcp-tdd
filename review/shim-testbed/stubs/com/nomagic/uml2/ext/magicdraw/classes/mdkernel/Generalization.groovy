package com.nomagic.uml2.ext.magicdraw.classes.mdkernel
class Generalization extends Element {
  Element general
  Element specific
  Element getGeneral() { general }
  void setGeneral(Element g) { general = g }
  void setSpecific(Element s) { specific = s }
}
