import pandas as pd
import pytest

from nba_rotation_audit import final_rotation, forward_minutes_shadow, rotation_watch


def _event():
    players = []
    for club, ids in [('MIL',range(1,7)),('DET',range(7,13))]:
        team_id = '1' if club == 'MIL' else '2'
        roster = []
        for index, pid in enumerate(ids):
            roster.append(dict(athlete=dict(id=str(pid),displayName=f'Player {pid}'),
                               starter=index<5,stats=[str(48 if index<4 else 6 if index==4 else 42)]))
        players.append(dict(team=dict(id=team_id,abbreviation=club),
                            statistics=[dict(labels=['MIN'],athletes=roster)]))
    def tick(pid, period, clock, text, away=0, home=0):
        return dict(id=pid,period={'number':period},clock={'displayValue':clock},
                    type={'text':text},awayScore=away,homeScore=home)
    plays = [tick('start',1,'12:00','Start Period')]
    for team, incoming,outgoing in [('1','6','5'),('2','12','11')]:
        plays.append(dict(tick(f'sub-{team}',1,'6:00','Substitution'),team={'id':team},
                          participants=[{'athlete': {'id':pid}} for pid in (incoming,outgoing)]))
    plays.extend(tick(f'end-{quarter}',quarter,'0.0','End Period',
                      away=20 if quarter>=3 else 0) for quarter in range(1,5))
    plays.append(tick('end',4,'0.0','End Game',away=20))
    return dict(header=dict(id='123',competitions=[dict(status={'type':{'completed':True}},competitors=[
        dict(homeAway='away',team={'id':'1','abbreviation':'MIL'},score='20'),
        dict(homeAway='home',team={'id':'2','abbreviation':'DET'},score='0')])]),
        boxscore={'players':players},plays=plays)


def test_reconstructed_minutes_match_final_boxes_and_margin():
    game = _event()
    results = {row['key']:row for row in final_rotation(game,'123','MIL','DET')}
    assert results['player5']['seconds'] == 360
    assert results['player6']['seconds'] == 2520
    assert results['player6']['q4_large_margin_seconds'] == 720
    assert sum(row['seconds'] for row in results.values() if row['team']=='DET') == 14400


def test_reconciled_player_trace_does_not_certify_invalid_team_timeline():
    game = _event()
    game['plays'][2]['participants'].reverse()
    with pytest.raises(ValueError,match='active lineup'):
        final_rotation(game,'123','MIL','DET')
    row, = final_rotation(game,'123','MIL','DET',only_player='Player 6')
    assert row['seconds'] == 2520 and row['scope'] == 'one player'
    with pytest.raises(ValueError,match='active lineup'):
        final_rotation(game,'123','MIL','DET',only_player='Player 12')


def test_minutes_shadow_uses_eligible_earlier_dates_only_and_holds_rate_fixed():
    data = pd.DataFrame([
        dict(date=f'2026-11-{day:02d}',id='1-8',history_latest=f'2026-11-{day-1:02d}',
             forecast_minutes=32.,actual_minutes=actual,recent_minutes=24.,prior_minutes_sd=4.,
             forecast_fd=48.,actual=actual)
        for day,actual in ((22,28.),(23,28.),(24,32.))
    ])
    watch = rotation_watch(data)
    assert watch.expanded_role.all() and not watch.volatile_role.any()
    assert forward_minutes_shadow(watch).empty
    result = forward_minutes_shadow(watch,minimum_training=2).iloc[0]
    assert result.fraction_removed == .5 and result.shadow_minutes == 28
    assert result.shadow_fd == 42
    data.loc[2,'actual_minutes'] = 22.
    changed = forward_minutes_shadow(rotation_watch(data),minimum_training=2).iloc[0]
    assert changed.fraction_removed == result.fraction_removed
    data.loc[2,'history_latest'] = data.loc[2,'date']
    with pytest.raises(ValueError,match='earlier history'):
        rotation_watch(data)
