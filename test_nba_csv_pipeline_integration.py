"""Synthetic CSV -> full-pool reconciliation -> minutes -> legal optimizer contract.

No live projections or real contest results are inferred from this fixture.
"""
import csv
import io
import unittest
import pandas as pd

from model import SLOTS, allowed_slots, consensus, optimize
from slate_import import reconcile_exports


def export_bytes(headers, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def synthetic_exports(*, missing_daily=False, salary_mismatch=False):
    # Position coverage mirrors all nine FanDuel classic slots.
    positions = ["PG", "SG", "SF", "PF", "C"]
    contest, daily = [], []
    for i in range(36):
        pos = positions[i % 5]
        name = f"Fixture Player {i}"
        salary = 6000
        team, game = [("ATL","ATL@BOS"),("BOS","ATL@BOS"),("NYK","NYK@CHI"),("CHI","NYK@CHI")][i%4]
        contest.append({
            "Id": f"99999-{i+1000}", "Nickname": name,
            "Game": game, "Team": team,
            "Salary": str(salary), "Position": pos,
            "Roster Position": f"{pos}/G/F/UTIL" if pos != "C" else "C/F/UTIL",
            "Injury Indicator": "",
        })
        if not (missing_daily and i == 0):
            daily.append({
                "player": name, "team": team, "gameInfo": game,
                "salary": str(salary + (100 if salary_mismatch and i == 0 else 0)),
                "minutes": "30", "fantasy": str(50-i),
            })
    return (export_bytes(list(contest[0]), contest),
            export_bytes(list(daily[0]), daily))


class CsvToLineupsTests(unittest.TestCase):
    def test_reconcile_score_and_generate_four_legal_lineups(self):
        contest, daily = synthetic_exports()
        matched, contest_id, extras = reconcile_exports(contest, daily)
        self.assertEqual(contest_id, "99999")
        self.assertEqual(extras, 0)
        self.assertEqual(len(matched), 36)
        self.assertTrue(matched.import_issue.eq("").all())
        self.assertTrue(matched.identity_match.eq("exact").all())
        scored = consensus(matched)
        result = optimize(scored, number=4, max_overlap=7)
        self.assertEqual(len(result), 36)
        self.assertEqual(result.lineup.nunique(), 4)
        sets = []
        for _, group in result.groupby("lineup"):
            self.assertEqual(len(group), 9)
            self.assertEqual(group.fanduel_id.nunique(), 9)
            self.assertEqual(sorted(group.slot), sorted(SLOTS))
            self.assertLessEqual(group.salary.sum(), 60000)
            for row in group.itertuples():
                eligibility = scored.loc[scored.fanduel_id.eq(row.fanduel_id), "roster_eligibility"].iloc[0]
                self.assertIn(row.slot, allowed_slots(eligibility))
            sets.append(set(group.fanduel_id))
        for i, left in enumerate(sets):
            for right in sets[i+1:]:
                self.assertLessEqual(len(left & right), 7)

    def test_missing_daily_row_is_flagged_and_not_optimized(self):
        contest, daily = synthetic_exports(missing_daily=True)
        matched, _, _ = reconcile_exports(contest, daily)
        missing = matched.loc[matched.fanduel_id.eq("99999-1000")].iloc[0]
        self.assertEqual(missing.identity_match, "unmatched")
        self.assertIn("No verified DAILY", missing.import_issue)
        scored = consensus(matched)
        lineup = optimize(scored, number=1)
        self.assertNotIn("99999-1000", set(lineup.fanduel_id))

    def test_salary_disagreement_preserves_contest_salary(self):
        contest, daily = synthetic_exports(salary_mismatch=True)
        matched, _, _ = reconcile_exports(contest, daily)
        player = matched.loc[matched.fanduel_id.eq("99999-1000")].iloc[0]
        self.assertEqual(player.salary, 6000)
        self.assertIn("DAILY salary differs", player.import_issue)

    def test_duplicate_daily_identity_is_flagged_not_silently_matched(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(daily.decode("utf-8"))))
        rows.append(dict(rows[0]))
        daily = export_bytes(list(rows[0]), rows)
        matched, _, extras = reconcile_exports(contest, daily)
        player = matched.loc[matched.fanduel_id.eq("99999-1000")].iloc[0]
        self.assertEqual(player.identity_match, "ambiguous")
        self.assertEqual(player.import_issue, "Ambiguous identity")
        self.assertTrue(pd.isna(player.projected_fd_points))
        self.assertEqual(extras, 0)
        lineup = optimize(consensus(matched), number=1)
        self.assertNotIn("99999-1000", set(lineup.fanduel_id))

    def test_mixed_contest_ids_are_rejected(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(contest.decode("utf-8"))))
        rows[0]["Id"] = "88888-1000"
        contest = export_bytes(list(rows[0]), rows)
        with self.assertRaisesRegex(ValueError, "mixes FanDuel contest IDs"):
            reconcile_exports(contest, daily)

    def test_invalid_daily_minutes_flagged_and_excluded(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(daily.decode("utf-8"))))
        rows[0]["minutes"] = "0"
        daily = export_bytes(list(rows[0]), rows)
        matched, _, _ = reconcile_exports(contest, daily)
        player = matched.loc[matched.fanduel_id.eq("99999-1000")].iloc[0]
        self.assertIn("Missing or invalid DAILY minutes/points", player.import_issue)
        self.assertTrue(pd.isna(player.projected_minutes))
        lineup = optimize(consensus(matched), number=1)
        self.assertNotIn("99999-1000", set(lineup.fanduel_id))

    def test_negative_daily_fantasy_projection_is_flagged(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(daily.decode("utf-8"))))
        rows[0]["fantasy"] = "-15"
        daily = export_bytes(list(rows[0]), rows)
        matched, _, _ = reconcile_exports(contest, daily)
        player = matched.loc[matched.fanduel_id.eq("99999-1000")].iloc[0]
        self.assertTrue(pd.isna(player.projected_fd_points))
        self.assertIn("Missing or invalid DAILY minutes/points", player.import_issue)
        lineup = optimize(consensus(matched), number=1)
        self.assertNotIn("99999-1000", set(lineup.fanduel_id))

    def test_extra_daily_player_count_does_not_expand_contest(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(daily.decode("utf-8"))))
        extra = dict(rows[0])
        extra["player"] = "Outside Contest"
        rows.append(extra)
        daily = export_bytes(list(rows[0]), rows)
        matched, contest_id, extras = reconcile_exports(contest, daily)
        self.assertEqual(contest_id, "99999")
        self.assertEqual(extras, 1)
        self.assertEqual(len(matched), 36)
        self.assertNotIn("Outside Contest", set(matched.fanduel_name))

    def test_invalid_contest_salary_fails_closed(self):
        contest, daily = synthetic_exports()
        rows = list(csv.DictReader(io.StringIO(contest.decode("utf-8"))))
        rows[0]["Salary"] = "-1"
        contest = export_bytes(list(rows[0]), rows)
        with self.assertRaises(ValueError):
            reconcile_exports(contest, daily)


def test_independent_blend_reaches_optimizer_and_reviewed_simulation():
    from datetime import datetime
    import pytest
    from nba_simulation import simulate_reviewed_candidates
    from slate_research import DFF, PROPSIMS, ET, historical_context, score_slate

    contest, daily = synthetic_exports()
    pool, _, _ = reconcile_exports(contest, daily)
    now = datetime(2026, 11, 23, 18, 0, tzinfo=ET)
    estimates = [
        dict(fanduel_id=row.fanduel_id, source=source,
             points=row.projected_fd_points + delta, observed_at=now.isoformat())
        for row in pool.itertuples()
        for source, delta in [(DFF, 2), (PROPSIMS, 4)]
    ]
    reviewed, _ = score_slate(pool, historical_context(pool, pd.DataFrame(), [], now.date()),
                              [], estimates, now)
    assert reviewed.blend_status.eq('60/40 blend applied').all()
    assert reviewed.adjusted_fd_points.tolist() == pytest.approx(
        (reviewed.projected_fd_points + 1.2).tolist())
    candidates = optimize(reviewed, number=4, max_overlap=7)
    assert len(candidates) == 36
    lookup = reviewed.set_index('fanduel_id')
    assert candidates.adjusted_fd_points.tolist() == pytest.approx(
        lookup.loc[candidates.fanduel_id, 'adjusted_fd_points'].tolist())
    history = pd.DataFrame({
        'slate_date': '2026-11-22', 'fanduel_id': [f'old-{i}' for i in range(24)],
        'eligible': True, 'daily_minutes': 30, 'daily_points': 30,
        'actual_minutes': 30, 'actual_points': 30, 'verified_outcome': 'played',
        'nba_source': 'NBA official box', 'replay_before_full_slate_tip': True,
        'replay_captured_at_utc': '2026-11-22T18:00:00Z',
        'replay_cutoff_utc': '2026-11-22T23:00:00Z',
    })
    ranges, pairs, count = simulate_reviewed_candidates(
        history, reviewed, candidates, now.date(), draws=32)
    expected = candidates.groupby('lineup').adjusted_fd_points.sum()
    assert count == 24 and len(pairs) == 6
    assert ranges.reviewed_fd.tolist() == pytest.approx(ranges.lineup.map(expected).tolist())
    # Zero-residual fixture: every outcome should equal the reviewed score,
    # rather than the lower DAILY score or the lineup selection objective.
    assert ranges.fd_p50.tolist() == pytest.approx(ranges.reviewed_fd.tolist())


if __name__ == "__main__":
    unittest.main()


def test_optional_component_forecasts_retained_without_changing_contest_authority():
    contest,daily=synthetic_exports()
    rows=list(csv.DictReader(io.StringIO(daily.decode('utf-8'))))
    for r in rows:
        r.update(fieldGoalsAttempted='12',freeThrowsAttempted='4',turnovers='2',points='18')
    rows[1]['fieldGoalsAttempted']=''
    rows[2]['turnovers']='-1'
    matched,_,_=reconcile_exports(contest,export_bytes(list(rows[0]),rows))
    assert matched.daily_box_fieldGoalsAttempted.iloc[0]==12
    assert matched.daily_box_freeThrowsAttempted.iloc[0]==4
    assert pd.isna(matched.daily_box_fieldGoalsAttempted.iloc[1])
    assert pd.isna(matched.daily_box_turnovers.iloc[2])
    assert matched.salary.eq(6000).all()
