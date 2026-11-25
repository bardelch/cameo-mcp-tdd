package com.nomagic.uml2.ext.magicdraw.classes.mdkernel
class Element {
  static int counter = 0
  String id = "_19_0_3_" + Integer.toHexString(++counter + 0x1000) + "_1700000000" + (100 + counter) + "_" + counter + "_" + counter
  Element owner
  List<Element> ownedElement = []
  String getID() { id }
  List<Element> rawOwned() { ownedElement }
  Element getOwner() { owner }
  Collection<Element> getOwnedElement() { Collections.unmodifiableList(ownedElement) }
  def eClass() { [getName: { -> metaName() }] as Object }
  String metaName() { getClass().simpleName.replace("Impl", "") }
  String getHumanType() { metaName() }
  String getHumanName() { metaName() }
  boolean isEditable() { true }
}
