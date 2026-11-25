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
