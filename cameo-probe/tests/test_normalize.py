import unittest

from cameo_probe.normalize import Normalizer

UUID_A = "123e4567-e89b-12d3-a456-426614174000"
UUID_B = "9b2f6a3e-1c4d-4e5f-8a7b-0123456789ab"
MD_ID = "_17_0_5_1_b9f02e5_1394028174441_581693_20347"


class NormalizerTests(unittest.TestCase):
    def test_same_id_maps_to_same_placeholder_across_values(self):
        a, b = Normalizer().normalize_run([{"id": UUID_A}, {"parent": UUID_A, "other": UUID_B}])
        self.assertEqual(a, {"id": "<ID:1>"})
        self.assertEqual(b, {"parent": "<ID:1>", "other": "<ID:2>"})

    def test_runs_with_different_real_ids_normalize_equal(self):
        first = Normalizer().normalize_run([{"id": UUID_A, "name": "X"}])
        second = Normalizer().normalize_run([{"id": UUID_B, "name": "X"}])
        self.assertEqual(first, second)

    def test_ids_inside_longer_strings_are_replaced(self):
        (out,) = Normalizer().normalize_run(["created " + UUID_A + " ok"])
        self.assertEqual(out, "created <ID:1> ok")

    def test_timestamps_are_replaced(self):
        (out,) = Normalizer().normalize_run([{"at": "2026-11-09T12:34:56.789Z"}])
        self.assertEqual(out, {"at": "<TS>"})

    def test_non_string_values_pass_through(self):
        value = {"n": 3, "ok": True, "x": None, "l": [1, 2.5]}
        self.assertEqual(Normalizer().normalize_run([value]), [value])

    def test_keys_and_nested_lists_are_normalized(self):
        (out,) = Normalizer().normalize_run([{UUID_A: [UUID_B, {"k": UUID_A}]}])
        self.assertEqual(out, {"<ID:1>": ["<ID:2>", {"k": "<ID:1>"}]})

    def test_custom_id_patterns(self):
        (out,) = Normalizer(id_patterns=[r"EL-\d+"]).normalize_run(["EL-12 and EL-12 and EL-7"])
        self.assertEqual(out, "<ID:1> and <ID:1> and <ID:2>")

    def test_magicdraw_style_ids_use_the_default_pattern(self):
        # Starting assumption about Cameo's ID format; P-ELM-001 must confirm it live.
        (out,) = Normalizer().normalize_run(["owner " + MD_ID])
        self.assertEqual(out, "owner <ID:1>")


if __name__ == "__main__":
    unittest.main()
