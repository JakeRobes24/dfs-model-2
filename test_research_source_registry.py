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
