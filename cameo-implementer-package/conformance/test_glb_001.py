"""CL-GLB-001 Envelope and routing (G-001, G-002)."""
from .base import ConformanceCase, needs


class EnvelopeAndRoutingTests(ConformanceCase):
    @needs()
    def test_t_glb_001_01_unknown_route_is_a_404_envelope(self):
        self.assert_error(self.get("/api/v1/no-such-route"), "ROUTE_NOT_FOUND")

    @needs()
    def test_t_glb_001_02_wrong_method_is_a_405_envelope(self):
        self.assert_error(self.post("/api/v1/status", {}), "METHOD_NOT_ALLOWED")
        self.assert_error(self.get("/api/v1/elements"), "METHOD_NOT_ALLOWED")

    @needs()
    def test_t_glb_001_03_success_replies_use_the_envelope(self):
        self.assert_ok(self.get("/api/v1/status"))

    @needs()
    def test_t_glb_001_04_paths_match_exactly(self):
        """G-011: no trailing-slash or case normalisation."""
        self.assert_error(self.get("/api/v1/status/"), "ROUTE_NOT_FOUND")
        self.assert_error(self.get("/API/v1/status"), "ROUTE_NOT_FOUND")
