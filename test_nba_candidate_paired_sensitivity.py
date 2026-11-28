import json
import pandas as pd
import pytest
from model import SLOTS
from slate_research import PROPSIMS, ROTOGRINDERS
from nba_candidate_paired_sensitivity import candidate_paired_sensitivity

NOW='2026-11-28T21:00:00Z'


def fixture():
    def note(source,family,points,minutes,stamp='2026-11-28T20:00:00Z'):
        return dict(source=source,family=family,points=points,paired_minutes=minutes,observed_at=stamp)
    rows=[]
    for i in range(10):
        rows.append(dict(fanduel_id=f'137300-{i+1}',team=['ORL','WAS','BOS'][i%3],
                         salary=4000 if i==0 else 6000,
                         roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',
                         eligible=True,adjusted_fd_points=30.,adjusted_minutes=30.,
                         injury_flag='',prelock_status='',projection_sources_json='[]'))
    rows[0]['projection_sources_json']=json.dumps([
        note(PROPSIMS,'propsims',36,24),note(ROTOGRINDERS,'rotogrinders',24,30)])
    rows[9]['projection_sources_json']=json.dumps([note(PROPSIMS,'propsims',36,36)])
    pool=pd.DataFrame(rows)
    entries=pd.DataFrame([dict(lineup=j,slot=slot,fanduel_id=pid)
                          for j,ids in [(1,pool.fanduel_id.iloc[:9]),(2,pool.fanduel_id.iloc[1:])]
                          for slot,pid in zip(SLOTS,ids)])
    return pool,entries


def test_exact_rate_minutes_and_same_family_fallback():
    pool,entries=fixture()
    before=pool.copy(deep=True)
    r=candidate_paired_sensitivity(pool,entries,NOW).set_index(['Provider','Lineup'])
    a=r.loc[('propsims',1)]
    assert a['Reviewed FD']==270
    assert a['Rate only FD']==285
    assert a['Half rate FD']==277.5
    assert a['Minutes only FD']==264
    assert a['Source paired FD']==276
    assert a['Salary below 5000 supported']==1
    assert a['Unchanged fallback players']==8
    b=r.loc[('propsims',2)]
    assert b['Rate only FD']==270 and b['Minutes only FD']==276
    c=r.loc[('rotogrinders',2)]
    assert c['Supported players']==0 and c['Rate only FD']==270
    pd.testing.assert_frame_equal(pool,before)


def test_news_uncertain_and_missing_minutes_do_not_create_rate_support():
    pool,entries=fixture()
    news=pd.DataFrame([{'fanduel_id':'137300-1','Latest confirmation UTC':'2026-11-28T20:30:00Z'}])
    r=candidate_paired_sensitivity(pool,entries,NOW,team_review=news)
    assert set(r.Provider)=={'propsims'}
    assert r.loc[r.Lineup.eq(1),'Supported players'].iloc[0]==0
    pool.loc[0,'adjusted_minutes']=None
    pool.loc[9,'injury_flag']='Q'
    assert candidate_paired_sensitivity(pool,entries,NOW).empty
    with pytest.raises(ValueError,match='timestamp'):
        candidate_paired_sensitivity(pool,entries,NOW,team_review=news.assign(
            **{'Latest confirmation UTC':'2026-11-28T22:00:00Z'}))


def test_invalid_or_duplicate_candidates_rejected():
    pool,entries=fixture()
    with pytest.raises(ValueError,match='ineligible'):
        candidate_paired_sensitivity(pool.assign(eligible=pool.fanduel_id.ne('137300-1')),entries,NOW)
    one=entries.loc[entries.lineup.eq(1)]
    with pytest.raises(ValueError,match='Distinct'):
        candidate_paired_sensitivity(pool,pd.concat([one,one.assign(lineup=2)]),NOW)
