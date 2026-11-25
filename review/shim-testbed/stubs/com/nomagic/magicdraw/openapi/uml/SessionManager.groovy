package com.nomagic.magicdraw.openapi.uml
class SessionManager {
  static final SessionManager INSTANCE = new SessionManager()
  static SessionManager getInstance() { INSTANCE }
  List<Closure> journal = null
  void createSession(Object project, String name) {
    if (journal != null) throw new IllegalStateException("Session already created")
    journal = []
  }
  boolean isSessionCreated(Object project) { journal != null }
  void closeSession(Object project) {
    if (journal == null) throw new IllegalStateException("No session")
    journal = null
  }
  void cancelSession(Object project) {
    if (journal == null) throw new IllegalStateException("No session")
    journal.reverse().each { it.call() }
    journal = null
  }
  void record(Closure undo) {
    if (journal == null) throw new IllegalStateException("Not in session")
    journal << undo
  }
}
