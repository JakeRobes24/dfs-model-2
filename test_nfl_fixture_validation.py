"""Regression checks for the Nov 22, 2026 NFL historical fixture."""
import copy
import json
import unittest
from pathlib import Path
from nfl_fixture_validation import validate

BASE = json.loads((Path(__file__).parent / "tests/fixtures/nov22_2026_nfl_fd_preliminary.json").read_text())


class FixtureTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate(BASE)["passed"])

    def test_duplicate(self):
        data = copy.deepcopy(BASE)
        data["lineup"][1]["player"] = data["lineup"][0]["player"]
        self.assertFalse(validate(data)["passed"])

    def test_salary_cap(self):
        data = copy.deepcopy(BASE)
        data["lineup"][0]["salary"] += 100
        self.assertFalse(validate(data)["passed"])

    def test_missing_projection_not_filled(self):
        data = copy.deepcopy(BASE)
        data["lineup"][2]["prelock_fd"] = 15
        self.assertFalse(validate(data)["passed"])

    def test_actual_mismatch(self):
        data = copy.deepcopy(BASE)
        data["lineup"][0]["actual_fd"] += 1
        self.assertFalse(validate(data)["passed"])

    def test_invalid_slot(self):
        data = copy.deepcopy(BASE)
        data["lineup"][0]["slot"] = "WR"
        self.assertFalse(validate(data)["passed"])

    def test_wrong_aggregate(self):
        data = copy.deepcopy(BASE)
        data["remaining_projected_subtotal"] += 1
        self.assertFalse(validate(data)["passed"])

    def test_nonfinite_projection(self):
        data = copy.deepcopy(BASE)
        data["lineup"][0]["prelock_fd"] = float("nan")
        self.assertFalse(validate(data)["passed"])


if __name__ == "__main__":
    unittest.main()
