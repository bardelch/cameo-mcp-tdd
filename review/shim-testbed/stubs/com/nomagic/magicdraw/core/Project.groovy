package com.nomagic.magicdraw.core
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.*
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile
class Project {
  Model primaryModel = new Model(name: "Data")
  ElementsFactory elementsFactory = new ElementsFactory()
  Profile standard = new Profile(name: "UML Standard Profile")
  String getName() { "StubProject" }
  Model getPrimaryModel() { primaryModel }
  ElementsFactory getElementsFactory() { elementsFactory }
  String getFileName() { null }
  boolean isRemote() { false }
}
