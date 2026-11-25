package com.nomagic.magicdraw.core
class Application {
  static final Application INSTANCE = new Application()
  static Application getInstance() { INSTANCE }
  Project project = System.getProperty("stub.project", "yes") == "yes" ? new Project() : null
  Project getProject() { project }
  GUILog getGUILog() { new GUILog() }
  String getProductVersion() { "2024x-stub" }
}
