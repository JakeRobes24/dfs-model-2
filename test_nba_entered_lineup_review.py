import unittest
from nba_entered_lineup_review import review_entered_lineups


class EnteredLineupReviewTests(unittest.TestCase):
    def setUp(self):
        self.csv = "player,salary,daily_fd,consensus_scenario_fd\n" + "\n".join(
            f"P{i},5000,10,9" for i in range(1, 11))
        self.entries = [
            {"label": "A", "slots": {str(i): f"P{i}" for i in range(1, 10)},
             "actual_fd": {f"P{i}": i for i in range(1, 10)}},
            {"label": "B", "slots": {str(i): f"P{i}" for i in range(2, 11)},
             "actual_fd": {f"P{i}": i for i in range(2, 11)}},
        ]

    def test_reconciles_unique_players(self):
        result = review_entered_lineups(self.csv, self.entries)
        self.assertEqual(len(result["shared_players"]), 8)
        self.assertEqual(result["lineups"][0]["daily_fd"], 90)
        self.assertEqual(result["lineups"][0]["actual_fd"], 45)

    def test_missing_player_rejected(self):
        self.entries[0]["slots"]["1"] = "Missing"
        self.entries[0]["actual_fd"].pop("P1")
        self.entries[0]["actual_fd"]["Missing"] = 1
        with self.assertRaises(ValueError):
            review_entered_lineups(self.csv, self.entries)

    def test_duplicate_roster_rejected(self):
        self.entries[0]["slots"]["1"] = "P2"
        with self.assertRaises(ValueError):
            review_entered_lineups(self.csv, self.entries)

    def test_duplicate_scenario_name_rejected(self):
        with self.assertRaises(ValueError):
            review_entered_lineups(self.csv + "\nP1,5000,10,9", self.entries)


if __name__ == "__main__":
    unittest.main()
