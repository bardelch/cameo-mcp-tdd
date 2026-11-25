package com.nomagic.uml2.ext.jmi.helpers
import com.nomagic.uml2.ext.magicdraw.mdprofiles.*
class StereotypesHelper {
  static Stereotype getStereotype(Object project, String name, String profile) { null }
  static void addStereotype(Object e, Stereotype st) { if (st == null) throw new IllegalArgumentException("stereotype is null") }
  static List getStereotypes(Object e) { [] }
  static Profile getProfile(Object project, String name) { project.standard.name == name && project.standard.owner == null ? project.standard : (project.standard.name == name ? project.standard : null) }
}
