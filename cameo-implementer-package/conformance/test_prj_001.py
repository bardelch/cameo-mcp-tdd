"""CL-PRJ-001 Get project."""
from contract_constants import PROJECT_FIELDS

from .base import ConformanceCase, needs


class ProjectTests(ConformanceCase):
    @needs("uml-project", "sysml-project")
    def test_t_prj_001_01_project_schema(self):
        data = self.assert_ok(self.get("/api/v1/project"))
        self.assertEqual(set(data), set(PROJECT_FIELDS))
        self.assertIsInstance(data["name"], str)
        self.assertTrue(data["file_path"] is None or isinstance(data["file_path"], str))
        self.assertIsInstance(data["root_model_id"], str)
        self.assertTrue(data["root_model_id"])

    @needs("no-project")
    def test_t_prj_001_02_no_project_is_a_409(self):
        self.assert_error(self.get("/api/v1/project"), "NO_ACTIVE_PROJECT", details={})
