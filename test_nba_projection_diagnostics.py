import unittest
import pandas as pd
from nba_projection_diagnostics import decompose_played_errors, summarize_decomposition


def row(pid='a', outcome='played', eligible=True, dm=20, am=25, actualm=30,
        dp=20, ap=25, actualp=45):
    return dict(fanduel_id=pid, eligible=eligible, verified_outcome=outcome,
                daily_minutes=dm, adjusted_minutes=am, actual_minutes=actualm,
                daily_points=dp, adjusted_fd_points=ap, actual_points=actualp)


class DiagnosticsTests(unittest.TestCase):
    def test_exact_decomposition(self):
        d = decompose_played_errors(pd.DataFrame([row()]))
        self.assertEqual(len(d), 2)
        self.assertAlmostEqual(d.loc[0, 'minutes_contribution'], -10)
        self.assertAlmostEqual(d.loc[0, 'rate_contribution'], -15)
        self.assertAlmostEqual(d.loc[0, 'point_error'], -25)
        self.assertAlmostEqual(d.loc[1, 'minutes_contribution'], -5)
        self.assertAlmostEqual(d.loc[1, 'rate_contribution'], -15)
        self.assertAlmostEqual(d.loc[1, 'point_error'], -20)
        self.assertEqual(set(summarize_decomposition(d).players), {1})

    def test_no_unresolved_or_dnp_leakage(self):
        data = pd.DataFrame([row(), row('b', 'did_not_play'), row('c', 'needs_review'),
                             row('d', eligible=False), row('e', actualm=0),
                             row('f', dp=None)])
        self.assertEqual(set(decompose_played_errors(data).fanduel_id), {'a'})

    def test_missing_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            decompose_played_errors(pd.DataFrame([row(), row()]))
        with self.assertRaises(ValueError):
            decompose_played_errors(pd.DataFrame([row(pid=None)]))

    def test_rate_error_can_offset_minutes_error(self):
        d = decompose_played_errors(pd.DataFrame([row(dm=20, am=20, actualm=30,
                                                      dp=40, ap=40, actualp=40)]))
        self.assertAlmostEqual(d.iloc[0].point_error, 0)
        self.assertAlmostEqual(d.iloc[0].minutes_contribution, -20)
        self.assertAlmostEqual(d.iloc[0].rate_contribution, 20)


if __name__ == '__main__':
    unittest.main()
