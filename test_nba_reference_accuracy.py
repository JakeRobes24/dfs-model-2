import json
from datetime import date
import pandas as pd
import pytest
from nba_reference_archive import freeze_reference_boards
from nba_reference_accuracy import review_reference_dates

DAY=date(2026,11,27)
def replay():
    p=pd.DataFrame([dict(fanduel_id='123-1',fanduel_name='Alpha Player',team='BOS',game='BOS@NYK',
        eligible=True,salary=5000,projected_fd_points=20,adjusted_fd_points=22,adjusted_minutes=24),
        dict(fanduel_id='123-2',fanduel_name='Beta Player',team='BOS',game='BOS@NYK',
        eligible=True,salary=5000,projected_fd_points=20,adjusted_fd_points=22,adjusted_minutes=24)])
    row=dict(player='Alpha Player',team='BOS',game='BOS@NYK',reference_salary=5000,
        reference_points=25,reference_minutes=30)
    boards={'Fantasy Team Advisors':([row],'2026-11-27T16:00:00Z'),
            'LineupExperts':([dict(row,reference_fd=26)],None)}
    f,_=freeze_reference_boards(p,boards,{},DAY,'2026-11-27T17:00:00Z')
    return f.assign(slate_date=DAY.isoformat(),daily_points=20,daily_minutes=25,
        actual_points=28,actual_minutes=32,verified_outcome='played',nba_source='NBA final',
        replay_captured_at_utc='2026-11-27T18:00:00Z',replay_cutoff_utc='2026-11-28T00:00:00Z',
        replay_timing='before_scheduled_tip',replay_before_full_slate_tip=True,replay_evidence_json='[]')

def run(f):
    return review_reference_dates(f,date(2026,11,28))

def test_dated_reference_accuracy_and_unknown_separate():
    d,days,s,c=run(replay())
    assert len(d)==len(days)==len(s)==2
    p=s.set_index('metric')
    assert p.loc['FD points','equal_date_source_mae']==3
    assert p.loc['FD points','equal_date_daily_mae']==8
    assert p.loc['Minutes','equal_date_source_mae']==2
    assert c.set_index('provider').loc['LineupExperts','publication_unknown']==1

def test_team_news_invalidates_earlier_reference():
    f=replay()
    f.loc[1,'replay_evidence_json']=json.dumps([dict(official=True,status='out',observed_at='2026-11-27T16:30:00Z')])
    d,_,_,c=run(f)
    assert d.empty
    assert c.set_index('provider').loc['Fantasy Team Advisors','news_or_evidence_hold']==1

def test_unknown_and_dnp_never_imputed():
    for outcome in ('did_not_play','unknown'):
        f=replay()
        f.loc[0,'verified_outcome']=outcome
        assert run(f)[0].empty

def test_duplicate_reference_and_stale_at_capture_excluded():
    f=replay()
    records=json.loads(f.replay_reference_forecasts_json.iloc[0])
    f.loc[0,'replay_reference_forecasts_json']=json.dumps(records+records)
    assert run(f)[0].empty
    f=replay()
    f['replay_captured_at_utc']='2026-11-27T23:00:00Z'
    d,_,_,c=run(f)
    assert d.empty and c.set_index('provider').loc['Fantasy Team Advisors','stale']==1

def test_mixed_contest_and_postlock_rejected():
    f=replay()
    f.loc[1,'fanduel_id']='124-1'
    with pytest.raises(ValueError):run(f)
    f=replay().assign(replay_captured_at_utc='2026-11-28T00:01:00Z')
    with pytest.raises(ValueError):run(f)

def test_old_archives_without_reference_fields_compatible():
    f=replay().drop(columns=['replay_reference_forecasts_json'])
    assert all(x.empty for x in run(f))
