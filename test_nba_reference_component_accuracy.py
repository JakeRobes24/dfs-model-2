import json
from datetime import date
import pytest
import pandas as pd
from nba_reference_accuracy import review_reference_components,review_reference_dates
from research_source_registry import RESEARCH_LINKS
from test_nba_reference_accuracy import replay

DAY=date(2026,11,28)

def fixture():
    f=replay().assign(replay_contest_sha256='a'*64,replay_daily_sha256='b'*64',
        nba_points=12,nba_reboundsTotal=4,nba_assists=2,
        daily_box_points=10,daily_box_rebounds=5,daily_box_assists=3)
    e=dict(provider='MatchWiz',source=RESEARCH_LINKS['MatchWiz'],scoring_accepted=False,
        slate_date='2026-11-27',observed_at='2026-11-27T17:00:00Z',published_at=None,
        minutes=30,fd_points=None,components=dict(points=15,rebounds=4,assists=2))
    f['replay_reference_forecasts_json']=[json.dumps([e]),'[]']
    return f,e

def test_partial_subtotal_rate_and_common_minutes_separate_from_full_fd():
    f,e=fixture()
    d,days,s,c=review_reference_components(f,DAY)
    assert len(d)==12
    rows=d.set_index('metric')
    pra='PRA FD-weighted subtotal'
    assert rows.loc[pra,'forecast']==pytest.approx(22.8)
    assert rows.loc[pra,'actual']==pytest.approx(19.8)
    assert rows.loc[pra,'daily']==pytest.approx(20.5)
    assert rows.loc[pra+' per minute','forecast']==pytest.approx(22.8/30)
    assert rows.loc[pra+' at shared reviewed minutes','forecast']==pytest.approx(24*22.8/30)
    assert rows.loc[pra+' at shared reviewed minutes','daily']==pytest.approx(24*20.5/25)
    assert not d.metric.str.contains('Full six-component').any()
    assert d.timing_basis.str.contains('exploratory').all()
    assert review_reference_dates(f,DAY)[0].empty
    # Separate distinct timing categories, even for same provider.
    e['published_at']='2026-11-27T16:30:00Z'
    f.loc[0,'replay_reference_forecasts_json']=json.dumps([e])
    assert review_reference_components(f,DAY)[2].timing_basis.eq('Dated fresh publication').all()

def test_real_zero_and_full_score_reconciliation():
    f,e=fixture()
    f=f.assign(nba_steals=0,nba_blocks=1,nba_turnovers=2,actual_points=20.8,
               daily_box_steals=1,daily_box_blocks=0,daily_box_turnovers=2)
    e['components'].update(steals=0,blocks=1,turnovers=2)
    f.loc[0,'replay_reference_forecasts_json']=json.dumps([e])
    d=review_reference_components(f,DAY)[0].set_index('metric')
    assert d.loc['steals','forecast']==0
    assert d.loc['Full six-component FD','actual']==pytest.approx(20.8)
    assert review_reference_components(f.assign(actual_points=99),DAY)[0].empty
    f.loc[0,'daily_box_blocks']=None
    d=review_reference_components(f,DAY)[0]
    assert not d.metric.str.contains('Full six-component').any()

def test_missing_and_news_timing_reject_without_imputation():
    f,e=fixture()
    assert review_reference_components(f.assign(verified_outcome='did_not_play'),DAY)[0].empty
    f.loc[1,'replay_evidence_json']=json.dumps([dict(official=True,status='out',observed_at='2026-11-27T17:30:00Z')])
    assert review_reference_components(f,DAY)[0].empty
    f.loc[1,'replay_evidence_json']='[]'
    e['observed_at']='2026-11-27T18:30:00Z'
    f.loc[0,'replay_reference_forecasts_json']=json.dumps([e])
    assert review_reference_components(f,DAY)[0].empty
    with pytest.raises(ValueError,match='fingerprints'):
        review_reference_components(f.assign(replay_daily_sha256='invalid'),DAY)
    f,e=fixture()
    d=review_reference_components(f.assign(actual_minutes=5),DAY)[0]
    assert len(d)==4
    assert not d.metric.str.contains('per minute|shared reviewed').any()
