from research_source_registry import research_checklist

def test_saved_sources_remain_visible_with_incomplete_automatic_refresh():
    nba = research_checklist('NBA',[('PropSims','36 estimates')]).set_index('Source')
    for source in ('LineupExperts','RotoGrinders','FantasyProjections','NBA House',
                   'Daily Fantasy Fuel','RotoWire','Fantasy Team Advisors',
                   'FantasySportsEdge','DraftEdge','RotoQL / stat-api','Linemate','WalterPicks'):
        assert source in nba.index
    assert '36 estimates' in nba.loc['PropSims','Refresh evidence']
    assert 'Not checked this refresh' in nba.loc['RotoGrinders','Refresh evidence']
    assert 'Not verified' in nba.loc['LineupExperts','Refresh evidence']
    assert 'Identity not verified' in nba.loc['FantasyProjections','Refresh evidence']
    nfl = research_checklist('NFL').set_index('Source')
    for source in ('The Fantasy Footballers','Fantasy Points','FantasySharks','Upper Hand Fantasy',
                   'RotoQL / stat-api','Linemate','WalterPicks','LineupExperts','Daily Fantasy Fuel'):
        assert source in nfl.index
    assert 'PropSims' not in nfl.index
    assert nfl.loc['The Fantasy Footballers','Integration'] == 'Manual required'


def test_courtside_and_4for4_are_retained_as_manual_references_only():
    nba = research_checklist('NBA', [('Courtside', 'claimed estimates')]).set_index('Source')
    nfl = research_checklist('NFL', [('4for4', 'claimed estimates')]).set_index('Source')
    assert 'Courtside' in nba.index and 'Courtside' not in nfl.index
    assert '4for4' in nfl.index and '4for4' not in nba.index
    for table, source, domain in ((nba, 'Courtside', 'https://courtside.higgsfield.app/'),
                                  (nfl, '4for4', 'https://www.4for4.com/')):
        row = table.loc[source]
        assert row['Integration'] == 'Manual research'
        assert 'Not verified' in row['Refresh evidence']
        assert 'claimed estimates' not in row['Refresh evidence']
        assert row['Verified access link'].startswith(domain)
    assert 'no injury' in nba.loc['Courtside', 'Research purpose']
    assert 'authorized subscription' in nfl.loc['4for4', 'Research purpose']


def test_public_coverage_counts_unique_eligible_exact_matches_and_empty_sources():
    import pandas as pd
    from slate_research import public_coverage, DFF, PROPSIMS, RW_MINUTES, ROTOGRINDERS
    pool = pd.DataFrame([
        dict(fanduel_id='100-1', fanduel_name='Alpha Player', team='BOS', game='BOS@NYK', eligible=True),
        dict(fanduel_id='100-2', fanduel_name='Beta Player', team='NYK', game='BOS@NYK', eligible=False),
        dict(fanduel_id='100-3', fanduel_name='Gamma Player', team='BOS', game='BOS@NYK', eligible=True),
    ])
    alpha = dict(player='Alpha Player', team='BOS', game='BOS@NYK', source=DFF, points=35)
    beta = dict(player='Beta Player', team='NYK', game='BOS@NYK', source=DFF, points=20)
    wrong = dict(alpha, game='BOS@MIA')
    notes = [dict(alpha, source=RW_MINUTES, minutes=30),
             dict(alpha, source=PROPSIMS, minutes=None)]
    coverage = public_coverage(pool, notes, [alpha, alpha, beta, wrong]).set_index(['Evidence','Provider'])
    row = coverage.loc[('Points',DFF)]
    assert row['Returned rows'] == 4
    assert row['Matched rows'] == 3
    assert row['Unmatched rows'] == 1
    assert row['Eligible players matched'] == 1
    assert row['Eligible players missing'] == 1
    assert coverage.loc[('Minutes',RW_MINUTES),'Eligible players matched'] == 1
    assert coverage.loc[('Minutes',PROPSIMS),'Returned rows'] == 0
    assert coverage.loc[('Points',ROTOGRINDERS),'Eligible players missing'] == 2


def test_fantasysportsedge_opponent_only_preview_is_matched_as_reference():
    from datetime import date, datetime
    from unittest.mock import patch
    import pandas as pd
    from slate_research import ET, fantasysportsedge_reference, compare_reference
    html = b"""<p>Projections updated November 25, 2026 at 10:00 AM EST</p>
    <table><thead><tr><th>Player</th><th>Opp</th><th>FD Salary</th><th>Projection</th></tr></thead>
    <tbody><tr><td>Alpha Player</td><td>NYK</td><td>$4,000</td><td>24.5</td></tr>
    <tr><td>Beta Player</td><td>MIA</td><td>$4,000</td><td>18</td></tr>
    <tr><td>Gamma Player</td><td>NYK</td><td>$4,100</td><td>15</td></tr></tbody></table>"""
    with patch('slate_research.fetch', return_value=html):
        rows, stamp = fantasysportsedge_reference(date(2026, 11, 25), datetime(2026, 11, 25, 11, tzinfo=ET))
    assert len(rows) == 3 and 'team' not in rows[0] and 'points' not in rows[0]
    pool = pd.DataFrame([dict(fanduel_id=f'100-{i}', fanduel_name=name, team='BOS', game='BOS@NYK',
                              salary=4000, eligible=True, projected_fd_points=20, adjusted_fd_points=20,
                              adjusted_minutes=22)
                         for i, name in enumerate(('Alpha Player','Beta Player','Gamma Player'), 1)])
    matched = compare_reference(pool, rows)
    assert list(matched.fanduel_id) == ['100-1']
    assert matched.iloc[0].reference_points == 24.5
    duplicate = pd.concat([pool, pool.iloc[[0]].assign(fanduel_id='100-99')], ignore_index=True)
    assert compare_reference(duplicate, rows).empty


def test_reference_refresh_isolated_from_failures_and_scoring():
    from datetime import date, datetime
    from unittest.mock import patch
    from slate_research import ET, get_reference_research

    slate = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 11, tzinfo=ET)
    line_rows = [{'player': 'Alpha Player', 'team': 'BOS', 'game': 'BOS@NYK', 'reference_fd': 24.5}]
    fta_rows = [{'player': 'Beta Player', 'team': 'NYK', 'game': 'BOS@NYK',
                 'reference_salary': 4000, 'reference_points': 20.0}]
    with patch('slate_research.lineupexperts_reference', return_value=line_rows), \
         patch('slate_research.fantasysportsedge_reference', side_effect=OSError('unavailable')), \
         patch('slate_research.fta_nba_reference', return_value=(fta_rows, now, 'Main', 10)) as fta:
        boards, status = get_reference_research(slate, now, ('BOS@NYK',))
        assert set(boards) == {'LineupExperts', 'Fantasy Team Advisors'}
        assert 'unavailable' in status['FantasySportsEdge'].lower()
        assert 'not scoring evidence' in status['LineupExperts']
        assert boards['LineupExperts'] == (line_rows, None)
        fta.assert_called_once_with(slate, now, ('BOS@NYK',))
    with patch('slate_research.lineupexperts_reference') as line:
        boards, status = get_reference_research(date(2026, 11, 24), now, ('BOS@NYK',))
        assert not boards and len(status) == 3
        line.assert_not_called()
    checklist = research_checklist('NBA', [('LineupExperts', 'Reference checked: 1 eligible match'),
                                          ('FantasySportsEdge', 'Reference unavailable'),
                                          ('WalterPicks', 'claimed evidence')]).set_index('Source')
    assert '1 eligible match' in checklist.loc['LineupExperts', 'Refresh evidence']
    assert 'unavailable' in checklist.loc['FantasySportsEdge', 'Refresh evidence']
    assert 'Not verified' in checklist.loc['WalterPicks', 'Refresh evidence']


def test_reference_review_prioritizes_missing_and_preserves_provenance():
    from datetime import datetime, timedelta
    import pandas as pd
    from slate_research import ET, reference_review_queue
    now = datetime(2026, 11, 25, 11, tzinfo=ET)
    pool = pd.DataFrame([
        dict(fanduel_id='100-1', fanduel_name='Alpha Player', team='BOS', game='BOS@NYK',
             salary=4000, eligible=True, projected_fd_points=None, adjusted_fd_points=None, adjusted_minutes=None),
        dict(fanduel_id='100-2', fanduel_name='Beta Player', team='NYK', game='BOS@NYK',
             salary=5000, eligible=True, projected_fd_points=30, adjusted_fd_points=30, adjusted_minutes=30),
        dict(fanduel_id='100-3', fanduel_name='Gamma Player', team='BOS', game='BOS@NYK',
             salary=4000, eligible=False, projected_fd_points=20, adjusted_fd_points=0, adjusted_minutes=0),
    ])
    before = pool.copy(deep=True)
    alpha = dict(player='Alpha Player', team='BOS', game='BOS@NYK', reference_fd=18)
    beta = dict(player='Beta Player', team='NYK', game='BOS@NYK', reference_salary=5000,
                reference_points=37, reference_minutes=24)
    gamma = dict(player='Gamma Player', team='BOS', game='BOS@NYK', reference_fd=20)
    boards = {'LineupExperts': ([alpha, gamma], None),
              'FantasySportsEdge': ([beta], now - timedelta(hours=7)),
              'Fantasy Team Advisors': ([beta], now, 'Main', 1)}
    queue = reference_review_queue(pool, boards, now)
    assert queue.fanduel_id.tolist() == ['100-1','100-2']
    assert queue.Provider.tolist() == ['LineupExperts','Fantasy Team Advisors']
    assert queue.iloc[0]['Published UTC'] == 'Unverified'
    assert 'Missing DAILY points' in queue.iloc[0].Review
    assert 'Missing usable model points' in queue.iloc[0].Review
    assert queue.iloc[1]['FD gap'] == 7 and queue.iloc[1]['Minutes gap'] == -6
    assert 'Minutes discrepancy' in queue.iloc[1].Review
    pd.testing.assert_frame_equal(pool, before)
    assert reference_review_queue(pool, {}, now).empty
