"""Direct Python parity check against archived November 24 exploratory evidence."""
import json
from pathlib import Path
import pandas as pd
import pytest
from nba_shadow_research import historical_rate_shadow, compare_frozen_history_rate

ROOT=Path(__file__).parent
def load():
    fixture=json.loads((ROOT/'tests/fixtures/nov24_historical_rate_replay.json').read_text())
    expected=json.loads((ROOT/'docs/validation/nov24-historical-rate-exploratory.json').read_text())
    assert fixture['source_blob']==expected['source_blob']
    return pd.DataFrame(fixture['rows']),expected

def test_archive_full_pool_identity_and_chronology():
    frame,expected=load()
    assert len(frame)==105
    assert frame.fanduel_id.is_unique
    assert frame.fanduel_id.str.startswith('137128-').all()
    assert frame.replay_before_full_slate_tip.str.lower().eq('true').all()
    assert frame.replay_timing.eq('before_scheduled_tip').all()
    capture=pd.to_datetime(frame.replay_captured_at_utc,utc=True)
    tip=pd.to_datetime(frame.replay_cutoff_utc,utc=True)
    assert capture.nunique()==1 and (capture<tip).all()

def test_direct_python_shadow_matches_independent_archive_reproduction():
    frame,expected=load()
    original=frame.copy(deep=True)
    result=compare_frozen_history_rate(frame).iloc[0]
    metrics=expected['metrics']
    assert result['Eligible played with baseline']==metrics['eligible_played_baseline']
    assert result['Paired players']==metrics['paired']
    for field,key in [('DAILY MAE','daily_mae'),('Reviewed MAE','reviewed_mae'),
                      ('Shadow MAE','shadow_mae'),('Shadow bias','shadow_bias')]:
        assert result[field]==pytest.approx(metrics[key],abs=1e-9)
    predicted=historical_rate_shadow(frame).set_index('fanduel_id')
    for row in expected['rows']:
        assert predicted.loc[row['id'],'history_rate_fd']==pytest.approx(row['shadow'],abs=1e-9)
        assert predicted.loc[row['id'],'history_rate_weight']==pytest.approx(row['weight'],abs=1e-9)
    pd.testing.assert_frame_equal(frame,original)
