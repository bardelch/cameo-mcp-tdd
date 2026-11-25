"""T-PH1-001: the Phase 1 exit scenario (contract 5.1), end to end through every basic route."""
import uuid

from .base import ConformanceCase, declared_scenario, needs


class PhaseOneEndToEnd(ConformanceCase):
    @needs("uml-project", "sysml-project", mutates=True)
    def test_t_ph1_001_create_read_back_and_delete_safely(self):
        status = self.assert_ok(self.get("/api/v1/status"))
        self.assertIs(status["project_open"], True)
        caps = self.assert_ok(self.get("/api/v1/capabilities"))
        self.assertEqual(caps["api_version"], status["api_version"])
        root = self.root_id()

        token = "Block" if declared_scenario() == "sysml-project" else "Class"
        pkg = self.create_ok("Package", f"ph1-{uuid.uuid4().hex[:8]}", root)
        part = self.create_ok(token, "Sensor", pkg["id"])

        self.assertEqual(self.assert_ok(self.get_element(pkg["id"])), pkg)
        self.assertEqual(self.assert_ok(self.get_element(part["id"])), part)
        self.assertEqual(self.query_all(parent_id=pkg["id"]), [part])

        preview = self.assert_ok(self.delete(pkg["id"]))
        self.assertEqual([w["id"] for w in preview["would_delete"]], [pkg["id"], part["id"]])
        self.assertEqual(self.assert_ok(self.get_element(part["id"])), part, "a preview deleted something")

        self.assertEqual(self.assert_ok(self.delete(pkg["id"], {"allow_write": True}))["deleted_count"], 2)
        for element_id in (pkg["id"], part["id"]):
            self.assert_error(self.get_element(element_id), "ELEMENT_NOT_FOUND")
        self.assertNotIn(pkg["id"], [i["id"] for i in self.query_all(parent_id=root)])
