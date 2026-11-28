import unittest
from nfl_contest_import import import_nfl_contest, attach_nfl_projections

HEADER = "Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator"
ROWS = [
    "136799-1,Dak Prescott,QB,QB,8200,DAL,DAL@NYG,",
    "136799-2,Emmett Johnson,RB,RB/FLEX,6200,SEA,SEA@SF,",
    "136799-3,Buffalo Bills,D,DEF,4900,BUF,BUF@MIA,O",
]


def sample(rows=None):
    return HEADER + "\n" + "\n".join(ROWS if rows is None else rows)


class NFLContestImportTests(unittest.TestCase):
    def test_import_preserves_out_player(self):
        pool = import_nfl_contest(sample(), expected_contest_id="136799")
        self.assertEqual(len(pool), 3)
        self.assertEqual(pool[-1]["status"], "out")
        self.assertEqual(pool[-1]["positions"], ["DEF"])

    def test_bom_and_intro(self):
        raw = "\ufeffFanDuel export\n" + sample()
        self.assertEqual(len(import_nfl_contest(raw)), 3)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample(ROWS + [ROWS[0]]))

    def test_mixed_contest_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample(ROWS + [ROWS[0].replace("136799", "136800")]))

    def test_wrong_expected_contest_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample(), expected_contest_id="999999")

    def test_invalid_position_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample([ROWS[0].replace(",QB,QB,", ",PG,PG,")]))

    def test_invalid_roster_eligibility_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample([ROWS[0].replace(",QB,QB,", ",QB,FLEX,")]))

    def test_wrong_game_rejected(self):
        with self.assertRaises(ValueError):
            import_nfl_contest(sample([ROWS[0].replace("DAL@NYG", "SEA@SF")]))

    def test_missing_projection_is_not_invented(self):
        pool = import_nfl_contest(sample())
        joined = attach_nfl_projections(pool, [{"player_id": "136799-1", "projection_fd": 20.8,
             "asof_utc": "2026-11-22T16:00:00Z"}], slate_date="2026-11-22", source_version="DAILY")
        self.assertEqual(joined[0]["projection_fd"], 20.8)
        self.assertIsNone(joined[1]["projection_fd"])
        self.assertIsNone(joined[2]["projection_fd"])

    def test_duplicate_projection_rejected(self):
        pool = import_nfl_contest(sample())
        with self.assertRaises(ValueError):
            attach_nfl_projections(pool, [{"player_id": "136799-1"}, {"player_id": "136799-1"}],
                                   slate_date="2026-11-22", source_version="DAILY")

    def test_out_of_contest_projection_rejected(self):
        pool = import_nfl_contest(sample())
        with self.assertRaises(ValueError):
            attach_nfl_projections(pool, [{"player_id": "other"}],
                                   slate_date="2026-11-22", source_version="DAILY")


if __name__ == "__main__":
    unittest.main()


class NFLSingleGameImportTests(unittest.TestCase):
    def test_exact_mvp_salary_and_kicker_preserved(self):
        raw = HEADER + ",MVP 1.5x Salary\n136799-1,Kicker,K,MVP - 1.5X Points/AnyFLEX,6200,DAL,DAL@NYG,,9300"
        p = import_nfl_contest(raw,single_game=True)[0]
        self.assertEqual(p["mvp_salary"],9300)
        self.assertEqual(p["positions"],["K"])
        with self.assertRaises(ValueError):
            import_nfl_contest(raw)
        with self.assertRaises(ValueError):
            import_nfl_contest(raw.replace("9300","9000"),single_game=True)
        with self.assertRaises(ValueError):
            import_nfl_contest(raw.replace("AnyFLEX","FLEX"),single_game=True)


    def test_upload_template_padding_columns_not_mistaken_for_duplicate_fields(self):
        raw = ('MVP - 1.5X Points,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX,,Instructions\n'
               ',,,,,,,Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator,MVP 1.5x Salary,,\n'
               ',,,,,,,137104-1,Running Back,RB,MVP - 1.5X Points/AnyFLEX,9600,LAR,GB@LAR,,14400,,')
        pool = import_nfl_contest(raw,single_game=True,expected_contest_id='137104')
        self.assertEqual(len(pool),1)
        self.assertEqual(pool[0]['mvp_salary'],14400)
        with self.assertRaises(ValueError):
            import_nfl_contest(raw.replace('Injury Indicator,MVP','Salary,MVP'),single_game=True)
