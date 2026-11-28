from research_source_registry import research_checklist

def test_new_research_candidates_remain_visible_without_claiming_numerical_coverage():
    from research_source_registry import predictive_coverage
    nba = research_checklist('NBA').set_index('Source')
    nfl = research_checklist('NFL').set_index('Source')
    assert 'potential assists' in nba.loc['NBA House','Research purpose']
    for name in ('Fantasy Life Utilization', 'ffopportunity / ffverse', 'PFF Usage and Production', 'Fantasy Six Pack'):
        assert name in nfl.index and name not in nba.index
    for sport in ('NBA','NFL'):
        coverage = predictive_coverage(sport).set_index('Source')
        for name in ('SportsDataIO','SpreadModel','FantasyPros'):
            assert coverage.loc[name,'Evidence'] == 'No comparable rows in this archive'
    assert 'not an independent vote' in nfl.loc['Fantasy Six Pack','Research purpose']
    assert not nfl.loc['SpreadModel','Verified access link']
    assert nfl.loc['ffopportunity / ffverse','Verified access link'].startswith('https://')


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
    assert nfl.loc['PropSims','Integration'] == 'Public weekly reference'
    assert nfl.loc['The Fantasy Footballers','Integration'] == 'Manual required'


def test_courtside_and_4for4_have_reference_only_status():
    nba = research_checklist('NBA', [('Courtside', 'claimed estimates')]).set_index('Source')
    nfl = research_checklist('NFL', [('4for4', 'claimed estimates')]).set_index('Source')
    assert 'Courtside' in nba.index and 'Courtside' not in nfl.index
    assert '4for4' in nfl.index and '4for4' not in nba.index
    for table, source, domain in ((nba, 'Courtside', 'https://courtside.higgsfield.app/'),
                                  (nfl, '4for4', 'https://www.4for4.com/')):
        row = table.loc[source]
        expected = 'Public weekly reference' if source == '4for4' else 'Manual research'
        assert row['Integration'] == expected
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
         patch('slate_research.fta_nba_reference', return_value=(fta_rows, now, 'Main', 10)) as fta, \
         patch('matchwiz_reference.matchwiz_reference', return_value=line_rows), \
         patch('slate_research.keelstats_reference', side_effect=OSError('403')), \
         patch('slate_research.edgehalla_slate_reference', return_value=(line_rows, None)) as edge:
        boards, status = get_reference_research(slate, now, ('BOS@NYK',))
        assert set(boards) == {'LineupExperts', 'Fantasy Team Advisors', 'MatchWiz', 'Edgehalla'}
        assert 'unavailable' in status['KeelStats'].lower()
        assert 'unavailable' in status['FantasySportsEdge'].lower()
        assert 'not scoring evidence' in status['LineupExperts']
        assert boards['LineupExperts'] == (line_rows, None)
        fta.assert_called_once_with(slate, now, ('BOS@NYK',))
        edge.assert_called_once_with(slate, ('BOS@NYK',))
    with patch('slate_research.lineupexperts_reference') as line:
        boards, status = get_reference_research(date(2026, 11, 24), now, ('BOS@NYK',))
        assert not boards and len(status) == 6
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


def test_nba_house_uses_explicit_slate_date_and_rejects_historical_as_fresh():
    from datetime import date, datetime, timedelta
    from unittest.mock import patch
    import pytest
    from slate_research import ET, NBA_HOUSE, nba_house_minutes
    slate = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 2, tzinfo=ET)
    html = b"""<main class="minutes-page"><h1>Wednesday 25 November 2026</h1>
    <article class="mins-card" id="bos-at-nyk"><header>
    <time datetime="2026-11-25T19:00:00-05:00"></time></header>
    <div class="mins-team" data-mins-side="away"><table class="mins-table"><tbody>
    <tr><td class="nm-t">Alpha Player</td><td class="mproj"><b>31</b></td></tr>
    </tbody></table></div></article></main>"""
    with patch('slate_research.fetch', return_value=html) as fetch:
        (notes, projections), status = nba_house_minutes(slate, now)
        fetch.assert_called_once_with(f'{NBA_HOUSE}/2026-11-25')
        assert notes[0]['minutes'] == 31 and notes[0]['source'] == NBA_HOUSE
        assert not projections and '1 pre-tip' in status
        with pytest.raises(ValueError, match='Historical'):
            nba_house_minutes(slate - timedelta(days=1), now)
        assert fetch.call_count == 1


def test_lineupexperts_relative_day_must_match_explicit_date():
    from datetime import date
    from unittest.mock import patch
    import pytest
    from slate_research import lineupexperts_reference
    slate = date(2026, 11, 25)
    html = b"""<html><head><title>Utility Players for today</title></head><body>
    <a>Today (11/24)</a></body></html>"""
    with patch('slate_research.fetch', return_value=html):
        with pytest.raises(ValueError, match='filter date'):
            lineupexperts_reference(slate, slate)
    with patch('slate_research.fetch', return_value=html.replace(b'11/24', b'11/25')):
        with pytest.raises(ValueError, match='reference table unavailable'):
            lineupexperts_reference(slate, slate)


def test_propsims_fresh_previous_evening_run_is_valid_for_exact_current_slate():
    from datetime import date, datetime, timedelta
    from unittest.mock import patch
    import pytest
    from slate_research import ET, propsims_research
    slate = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 2, tzinfo=ET)
    html = """<h1>NBA DFS projections: Wednesday, November 25</h1>
    <div class="updstamp"><time datetime="2026-11-24T21:41:00-06:00"></time></div>
    <table><tr><td class="player"><a>Alpha Player</a><span class="msub">BOS · G vs NYK</span></td>
    <td data-f="fd_p50" data-v="34.5"></td><td data-f="min_p50" data-v="31.0"></td></tr></table>"""
    with patch('slate_research.fetch', return_value=html.encode()):
        (notes, points), _ = propsims_research(slate, now)
        assert notes[0]['minutes'] == 31.0
        assert points[0]['points'] == 34.5 and points[0]['paired_minutes'] == 31.0
        assert points[0]['observed_at'] == '2026-11-24T22:41:00-05:00'
        with pytest.raises(ValueError, match='stale'):
            propsims_research(slate, now + timedelta(hours=4))
        with pytest.raises(ValueError, match='date unavailable'):
            propsims_research(slate - timedelta(days=1), now)
    with patch('slate_research.fetch', return_value=html.replace('-06:00', '').encode()):
        with pytest.raises(ValueError, match='timezone-aware'):
            propsims_research(slate, now)
    with patch('slate_research.fetch', return_value=html.replace('21:41:00-06:00', '23:41:00-09:00').encode()):
        with pytest.raises(ValueError, match='stale'):
            propsims_research(slate, now)


def test_propsims_distribution_is_separate_from_weighted_points():
    import json
    from datetime import datetime
    from bs4 import BeautifulSoup
    import pytest
    from slate_research import ET, PROPSIMS, DFF, propsims_distribution, points_consensus
    table = """<table><thead><tr><th>FD median</th><th>Floor</th><th>Ceiling</th>
    <th>If plays</th><th>p(play)</th></tr></thead><tbody>
    <tr><td>30</td><td>12</td><td>44</td><td>33</td><td>90%</td></tr>
    </tbody></table>"""
    soup = BeautifulSoup(table, 'html.parser')
    values = propsims_distribution(soup.select_one('tbody tr'), 30)
    assert values == dict(fd_p10=12, fd_p85=44, conditional_fd_median=33, play_probability=.9)
    wrong = BeautifulSoup(table.replace('FD median','DK median'), 'html.parser')
    assert propsims_distribution(wrong.select_one('tbody tr'), 30) == {}
    invalid = BeautifulSoup(table.replace('<td>12</td>','<td>40</td>'), 'html.parser')
    assert 'fd_p10' not in propsims_distribution(invalid.select_one('tbody tr'), 30)
    now = datetime(2026, 11, 25, 12, tzinfo=ET)
    baseline = dict(fanduel_id='100-1', source=PROPSIMS, points=30, observed_at=now.isoformat())
    other = dict(baseline, source=DFF, points=34)
    initial = points_consensus([baseline, other], [], now)
    enriched = points_consensus([dict(baseline, **values), other], [], now)
    assert enriched.loc['100-1','points'] == pytest.approx(initial.loc['100-1','points'])
    assert enriched.loc['100-1','source_count'] == 2
    data = json.loads(enriched.loc['100-1','propsims_distribution_json'])
    assert len(data) == 1 and data[0]['fd_p85'] == 44
    assert data[0]['fd_median'] == 30 and data[0]['source'] == PROPSIMS
    assert json.loads(initial.loc['100-1','propsims_distribution_json']) == []


def test_recovered_legacy_sources_are_retained_but_not_verified():
    nba = research_checklist('NBA', [('TheCapper','claimed projections')]).set_index('Source')
    nfl = research_checklist('NFL').set_index('Source')
    for name, link in {
        'MatchWiz': 'https://matchwiz.ai/nba/lineups',
        'TheCapper': 'https://thecapper.io/nba/projections/',
        'KeelStats': 'https://keelstats.com/nba/usage',
    }.items():
        assert name in nba.index and name not in nfl.index
        assert nba.loc[name,'Integration'] == ('Reference' if name in ('KeelStats', 'MatchWiz') else 'Manual research')
        assert nba.loc[name,'Historical reference link'] == link
        assert nba.loc[name,'Verified access link'] == link
        assert 'Not verified' in nba.loc[name,'Refresh evidence']
    assert 'partial PTS/REB/AST' in nba.loc['MatchWiz','Research purpose']
    assert 'omits blocks' in nba.loc['TheCapper','Research purpose']


def test_keelstats_minutes_reference_matches_game_and_rejects_stale_dates():
    from datetime import date, datetime, timedelta
    from unittest.mock import patch
    import pandas as pd
    import pytest
    from slate_research import ET, keelstats_reference, compare_keelstats
    slate = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 3, tzinfo=ET)
    html = """<h1>NBA minutes and usage tonight</h1><p>9 NBA games on Wednesday, November 25.</p>
    <p>Updated Nov 25, 2026, 2:33 AM EST</p>
    <h2>Boston Celtics at New York Knicks 7:00 PM</h2><h3>Boston Celtics</h3>
    <table><caption>Boston Celtics: minutes and usage tonight</caption>
    <thead><tr><th>Player</th><th>L10</th><th>Tonight</th><th>USG%</th><th>GS</th></tr></thead>
    <tbody><tr><th>Alpha Player</th><td>25.0</td><td>31.0</td><td>23.5</td><td>8/10</td></tr>
    <tr><td>Invalid Player</td><td>20</td><td>60</td><td>10</td><td>0/10</td></tr></tbody></table>"""
    with patch('slate_research.fetch', return_value=html.encode()):
        rows, stamp = keelstats_reference(slate, now)
        assert len(rows) == 1 and stamp.hour == 2
        assert rows[0]['reference_minutes'] == 31 and rows[0]['reference_l10'] == '25.0'
        assert 'points' not in rows[0] and rows[0]['game'] == 'BOS@NYK'
        with pytest.raises(ValueError, match='stale'):
            keelstats_reference(slate, now + timedelta(hours=7))
        with pytest.raises(ValueError, match='date'):
            keelstats_reference(slate - timedelta(days=1), now)
    pool = pd.DataFrame([
        dict(fanduel_id='100-1', fanduel_name='Alpha Player', team='BOS', game='BOS@NYK',
             eligible=True, adjusted_minutes=25),
        dict(fanduel_id='100-2', fanduel_name='Alpha Player', team='BOS', game='BOS@MIA',
             eligible=True, adjusted_minutes=25)])
    compared = compare_keelstats(pool, rows)
    assert list(compared.fanduel_id) == ['100-1'] and compared.iloc[0].minutes_gap == 6
    assert compare_keelstats(pool, rows+rows).empty


def test_matchwiz_reference_preserves_partial_stats_and_rejects_mismatched_clubs():
    from datetime import date, datetime
    import pandas as pd
    import pytest
    from matchwiz_reference import parse_matchwiz
    from slate_research import ET, compare_keelstats
    now = datetime(2026, 11, 25, 3, tzinfo=ET)
    slate = now.date()
    html = """<p class="subtitle">9 NBA games on Wednesday, November 25, 2026: 9 still projected.</p>
    <article class="nbalu-game"><header><a class="nbalu-matchup">MIA @ PHI</a></header>
    <div class="nbalu-sides"><section class="nbalu-side">
    <h3 class="nbalu-club"><img alt="Miami Heat logo"/></h3>
    <div class="nbalu-table"><div class="nbalu-head"><span>Projected starters</span>
    <span>Min</span><span>Pts</span><span>Reb</span><span>Ast</span></div>
    <ul class="nbalu-rows"><li class="nbalu-row nbalu-starter" data-name="Alpha Player" data-pid="123">
    <span class="nbalu-name"><a>Alpha Player</a></span><span class="nbalu-min">31.2</span>
    <span class="nbalu-stat"><span class="nbalu-statv">15</span><span class="nbalu-bookline">99</span></span>
    <span class="nbalu-stat"><span class="nbalu-statv">6</span></span>
    <span class="nbalu-stat"><span class="nbalu-statv">4</span></span></li></ul></div></section>
    <section class="nbalu-side"><h3 class="nbalu-club"><img alt="Philadelphia 76ers logo"/></h3></section>
    </div></article>"""
    rows = parse_matchwiz(html, slate, now)
    assert len(rows) == 1 and rows[0]['reference_minutes'] == 31.2
    assert rows[0]['reference_pts'] == 15 and rows[0]['reference_ast'] == 4
    assert rows[0]['reference_role'] == 'starter listing'
    assert not {'points','observed_at','official','reference_fd'} & rows[0].keys()
    for bad in (html.replace('November 25, 2026','November 24, 2026'),
                html.replace('Philadelphia 76ers logo','Boston Celtics logo'),
                html.replace('31.2','61.2')):
        with pytest.raises(ValueError):
            parse_matchwiz(bad, slate, now)
    pool = pd.DataFrame([dict(fanduel_id='100-1',fanduel_name='Alpha Player',team='MIA',
                              game='MIA@PHI',eligible=True,adjusted_minutes=25)])
    compared = compare_keelstats(pool, rows)
    assert compared.minutes_gap.iloc[0] == pytest.approx(6.2)
    assert compare_keelstats(pool, rows+rows).empty


def test_minutes_references_join_existing_review_queue_without_scoring_votes():
    from datetime import datetime, timedelta
    import pandas as pd
    from slate_research import ET, reference_review_queue
    now = datetime(2026,11,25,11,tzinfo=ET)
    pool = pd.DataFrame([
        dict(fanduel_id='100-1', fanduel_name='Alpha Player', team='BOS', game='BOS@NYK',
             salary=5000,eligible=True, projected_fd_points=30, adjusted_fd_points=30, adjusted_minutes=24),
        dict(fanduel_id='100-2', fanduel_name='Beta Player', team='NYK', game='BOS@NYK',
             salary=4000,eligible=True, projected_fd_points=None, adjusted_fd_points=None, adjusted_minutes=None)])
    a = dict(player='Alpha Player',team='BOS',game='BOS@NYK',reference_minutes=32,
             retrieved_at=now.isoformat(),slate_date=now.date().isoformat())
    b = dict(player='Beta Player',team='NYK',game='BOS@NYK',reference_minutes=20)
    before = pool.copy(deep=True)
    queue = reference_review_queue(pool,{'MatchWiz':([a],None),'KeelStats':([b],now)},now)
    assert queue.Provider.tolist() == ['KeelStats','MatchWiz']
    assert queue.iloc[0].Review == 'Missing model minutes'
    assert queue.iloc[1]['Minutes gap'] == 8
    assert queue.iloc[1]['Published UTC'] == 'Unverified'
    assert queue['Reference FD'].isna().all()
    stale = dict(a,retrieved_at=(now-timedelta(hours=7)).isoformat())
    assert reference_review_queue(pool,{'MatchWiz':([stale],None)},now).empty
    pd.testing.assert_frame_equal(pool,before)



def test_paired_data_documentation_does_not_promote_manual_providers():
    for sport in ('NBA', 'NFL'):
        rows = research_checklist(sport, [('DraftEdge', 'claimed paired data'),
                                          ('RotoQL / stat-api', 'claimed paired data')]).set_index('Source')
        for name in ('DraftEdge', 'RotoQL / stat-api'):
            row = rows.loc[name]
            assert row['Integration'] == 'Manual research'
            assert 'Not verified' in row['Refresh evidence']
            assert 'claimed paired data' not in row['Refresh evidence']
            assert row['Verified access link'].startswith('https://')
        assert 'count shared provenance once' in rows.loc['RotoQL / stat-api', 'Research purpose']
    nba = research_checklist('NBA').set_index('Source')
    assert 'does not expose projected minutes' in nba.loc['Daily Fantasy Fuel', 'Research purpose']


def test_predictive_coverage_distinguishes_matched_forecasts_from_capture_and_gaps():
    from research_source_registry import predictive_coverage

    nba = predictive_coverage('NBA', matched={('propsims', 'Minutes'): 56,
                                             ('propsims', 'FD points'): 59,
                                             ('lineupexperts', 'Minutes'): 0}).set_index('Source')
    assert nba.index.tolist() == research_checklist('NBA').Source.tolist()
    assert nba.loc['PropSims', 'Matched forecast rows by metric'] == 'FD points (59), Minutes (56)'
    assert nba.loc['LineupExperts', 'Evidence'] == 'No comparable rows in this archive'
    nfl = predictive_coverage('NFL', captured={'4for4': 14}).set_index('Source')
    assert nfl.index.tolist() == research_checklist('NFL').Source.tolist()
    assert nfl.loc['4for4', 'Forecast rows awaiting outcomes'] == 14
    assert nfl.loc['4for4', 'Evidence'] == 'Captured forecasts'


def test_sumersports_is_nfl_context_not_validated_forecast():
    from research_source_registry import predictive_coverage
    nba = research_checklist('NBA').set_index('Source')
    nfl = research_checklist('NFL', [('SumerSports', 'claimed forecast')]).set_index('Source')
    assert 'SumerSports' in nfl.index and 'SumerSports' not in nba.index
    assert nfl.loc['SumerSports', 'Verified access link'].startswith('https://sumersports.com/')
    assert 'not an independent forecast vote' in nfl.loc['SumerSports', 'Research purpose']
    assert 'Not verified' in nfl.loc['SumerSports', 'Refresh evidence']
    assert predictive_coverage('NFL').set_index('Source').loc['SumerSports', 'Evidence'] == 'No comparable rows in this archive'


def test_role_sources_are_candidates_not_scoring_votes():
    from research_source_registry import predictive_coverage
    for sport, names in [('NBA', ('BankrollSZN','Statyx')), ('NFL', ('StatRankings','HeatRadar'))]:
        rows = research_checklist(sport).set_index('Source')
        evidence = predictive_coverage(sport).set_index('Source')
        for name in names:
            assert 'candidate' in rows.loc[name,'Integration']
            assert 'Not verified' in rows.loc[name,'Refresh evidence']
            assert evidence.loc[name,'Evidence'] == 'No comparable rows in this archive'
            assert rows.loc[name,'Verified access link'].startswith('https://')
