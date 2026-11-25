import json
import os
import unittest

from tools.generate_fixtures import build_all

from .helpers import ROOT


class FixturesMatchTheFake(unittest.TestCase):
    def test_committed_fixtures_are_what_the_fake_produces(self):
        for clause, expected in build_all().items():
            with self.subTest(clause=clause):
                path = os.path.join(ROOT, "fixtures", f"{clause}.json")
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle), expected)


if __name__ == "__main__":
    unittest.main()
