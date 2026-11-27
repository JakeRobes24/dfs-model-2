from datetime import date
import json
import pandas as pd
from nba_reference_archive import freeze_reference_boards,FIELDS

DAY=date(2026,11,27)
NOW='2026-11-27T17:00:00Z'
def fixture():
    return pd.DataFrame([dict(fanduel_id='123-1',fanduel_name='Alpha Player',team='BOS',
        game='BOS@NYK',eligible=True,salary=5000,projected_fd_points=20,
        adjusted_fd_points=22,adjusted_minutes=24),
        dict(fanduel_id='123-2',fanduel_name='Beta Player',team='NYK',
        game='BOS@NYK',eligible=False,salary=5000,projected_fd_points=20,
        adjusted_fd_points=22,adjusted_minutes=24)])
def le():
    return dict(player='Alpha Player',team='BOS',game='BOS@NYK',reference_fd=30)
def test_unknown_publication_kept_as_reference_only_and_missing_distinguished():
    p=fixture()
    out,report=freeze_reference_boards(p,{'LineupExperts':([le()],None)},
                                     {'LineupExperts':'Returned'},DAY,NOW)
    pd.testing.assert_frame_equal(out[p.columns],p)
    e=json.loads(out[FIELDS[0]].iloc[0])[0]
    assert e['fd_points']==30 and e['published_at'] is None and not e['scoring_accepted']
    r=report.set_index('provider')
    assert r.loc['LineupExperts','publication_unknown_players']==1
    assert pd.isna(r.loc['MatchWiz','matched_players'])
    assert json.loads(out[FIELDS[0]].iloc[1])==[]

def test_duplicate_reference_identity_is_not_accepted():
    out,r=freeze_reference_boards(fixture(),{'LineupExperts':([le(),le()],None)}, {},DAY,NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])==[]
    assert r.loc[r.provider.eq('LineupExperts'),'matched_players'].iloc[0]==0

def test_future_stamp_rejected_and_stale_explicit():
    p=fixture()
    out,_=freeze_reference_boards(p,{'LineupExperts':([le()],'2026-11-27T18:00:00Z')},{},DAY,NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])==[]
    out,_=freeze_reference_boards(p,{'LineupExperts':([le()],'2026-11-27T08:00:00Z')},{},DAY,NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])[0]['freshness']=='Dated but stale'

def test_dated_board_exact_salary_and_match():
    row=dict(player='Alpha Player',team='BOS',game='BOS@NYK',
             reference_salary=5000,reference_points=25,reference_minutes=30)
    p=fixture()
    out,r=freeze_reference_boards(p,{'Fantasy Team Advisors':([row],'2026-11-27T16:00:00Z')},{},DAY,NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])[0]['minutes']==30
    assert r.loc[r.provider.eq('Fantasy Team Advisors'),'fresh_dated_players'].iloc[0]==1
    row['reference_salary']=5100
    out,_=freeze_reference_boards(p,{'Fantasy Team Advisors':([row],'2026-11-27T16:00:00Z')},{},DAY,NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])==[]


def test_lineupexperts_archive_preserves_the_explicit_fanduel_value():
    row = dict(le(), reference_points=4)
    out, _ = freeze_reference_boards(fixture(), {'LineupExperts': ([row], None)}, {}, DAY, NOW)
    assert json.loads(out[FIELDS[0]].iloc[0])[0]['fd_points'] == 30
