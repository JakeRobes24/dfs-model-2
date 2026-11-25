from datetime import date, timedelta
import pandas as pd
import pytest
from nba_portfolio_walkforward import walk_forward_portfolios, summarize_portfolio_experiments


def test_walk_forward_uses_only_prior_dates_and_reports_skips():
    start = date(2026,11,24)
    dates = [start+timedelta(days=i) for i in range(7)]
    captures = [(day,str(i),'version-123456',pd.DataFrame(),pd.DataFrame())
                for i,day in enumerate(dates)]
    replays = pd.DataFrame({'slate_date':[day.isoformat() for day in dates]})
    calls = []
    def builder(pool,training,day,**kwargs):
        assert pd.to_datetime(training.slate_date).dt.date.lt(day).all()
        assert len(training)<=5
        calls.append(day)
        return None,None,None,20
    def scorer(pool,rosters,selection,results,day):
        return pd.DataFrame({'Date':day.isoformat(),'Period':'Prospective',
            'Policy':['Projection ranked','Simulated P90 ranked'],'Entries':4,
            'Best actual FD':[300,310],'Average actual FD':[280,285],
            'Worst actual FD':[260,250]}),None
    details,summary,coverage = walk_forward_portfolios(captures[::-1],replays,
                                                        builder=builder,scorer=scorer)
    assert calls==dates[1:]
    assert len(details)==12
    assert coverage.iloc[0].Status=='No earlier verified training'
    assert coverage.iloc[-1]['Earlier training dates']==5
    assert summary.iloc[0]['Paired dates']==6
    assert summary.iloc[0]['Mean best FD difference']==10
    assert summary.iloc[0]['Mean worst FD difference']==-10
    assert summary.iloc[0]['Review status']=='Requires independent validation'
    with pytest.raises(ValueError,match='one paired'):
        summarize_portfolio_experiments(pd.concat([details,details]))
    with pytest.raises(ValueError,match='four-entry'):
        summarize_portfolio_experiments(details.assign(Entries=5))


def test_stress_comparison_separate_from_original_and_uses_same_date_budget():
    from nba_portfolio_stress import STRESS_POLICY
    frame = pd.DataFrame({'Date':['2026-11-25']*3,
        'Period':['Prospective','Prospective','Exploratory'],
        'Policy':['Projection ranked','Simulated P90 ranked',STRESS_POLICY],
        'Entries':4,'Best actual FD':[300,310,305],
        'Average actual FD':[280,285,283],'Worst actual FD':[260,250,255]})
    result = summarize_portfolio_experiments(frame).set_index('Comparison')
    assert result.loc['Simulated P90 ranked','Mean best FD difference']==10
    assert result.loc[STRESS_POLICY,'Mean best FD difference']==5
    assert result.loc[STRESS_POLICY,'Period']=='Exploratory'
