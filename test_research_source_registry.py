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
