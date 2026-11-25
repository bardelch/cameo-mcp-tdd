package com.nomagic.magicdraw.core
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.*
class ElementsFactory {
  def createClassInstance() { new com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class() }
  def createPackageInstance() { new com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package() }
  def createGeneralizationInstance() { new Generalization() }
}
