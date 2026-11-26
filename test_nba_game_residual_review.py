import json
from pathlib import Path
import pandas as pd
import pytest
from nba_game_residual_review import game_residual_review

def archive():
    return pd.DataFrame(json.loads((Path(__file__).parent/'tests/fixtures/nov24_historical_rate_replay.json').read_text())['rows'])

def test_real_archive_game_coverage():
    frame=archive()
    original=frame.copy(deep=True)
    detail,summary=game_residual_review(frame,target_day='2026-11-26')
    assert summary['dates']==1
    assert summary['games']==3
    assert summary['status']=='Insufficient descriptive coverage'
    assert not summary['certified']
    assert detail.players.sum()==50
    assert set(detail.game)=={'DAL@DEN','DET@ORL','BOS@WAS'}
    assert detail.teammate_pairs.gt(0).all() and detail.opponent_pairs.gt(0).all()
    assert summary['equal_game_teammate_cross_product']==pytest.approx(detail.teammate_cross_product.mean())
    pd.testing.assert_frame_equal(frame,original)

def test_exact_date_centering_and_group_weight():
    rows=[]
    for i,(team,actual) in enumerate([('AA',12),('AA',12),('BB',8),('BB',8)]):
        rows.append(dict(slate_date='2026-11-24',fanduel_id=f'1-{i}',team=team,game='AA@BB',
                         eligible=True,verified_outcome='played',nba_source='official',
                         actual_minutes=20,actual_points=actual,adjusted_minutes=20,adjusted_fd_points=10,
                         replay_captured_at_utc='2026-11-24T18:00:00Z',replay_cutoff_utc='2026-11-24T23:00:00Z',
                         replay_before_full_slate_tip=True,replay_timing='before_scheduled_tip'))
    detail,summary=game_residual_review(pd.DataFrame(rows),target_day='2026-11-25')
    assert detail.iloc[0].teammate_cross_product==4
    assert detail.iloc[0].opponent_cross_product==-4
    assert detail.iloc[0].teammate_pairs==2 and detail.iloc[0].opponent_pairs==4

@pytest.mark.parametrize('change', ['duplicate','mixed_contest','late','naive','target_day'])
def test_reject_ambiguous_or_unverified_date(change):
    frame=archive()
    target='2026-11-26'
    if change=='duplicate':frame=pd.concat([frame,frame.iloc[[0]]])
    elif change=='mixed_contest':frame.loc[0,'fanduel_id']='999-123'
    elif change=='late':frame.loc[0,'replay_captured_at_utc']='2026-11-26T23:00:00Z'
    elif change=='naive':frame['replay_captured_at_utc']='2026-11-24T11:00:00'
    else:target='2026-11-24'
    detail,summary=game_residual_review(frame,target_day=target)
    assert detail.empty
    assert len(summary['rejected_dates'])==1

def test_unverified_outcome_not_zero():
    frame=archive()
    frame['verified_outcome']='unknown'
    detail,summary=game_residual_review(frame,target_day='2026-11-26')
    assert detail.empty
    assert summary['rejected_dates'][0]['reason']=='no_supported_played_rows'
