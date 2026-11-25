"""Chronological multi-slate evaluation of the fixed candidate ranking experiment."""
from time import monotonic

import numpy as np
import pandas as pd

from nba_candidate_experiment import build_experiment, score_experiment, ENTRIES
from nba_portfolio_stress import STRESS_POLICY, STRESS_DECLARED


def summarize_portfolio_experiments(reports):
    """Equal date weights, identical budgets, and explicit prospective separation."""
    if reports.empty:
        return pd.DataFrame()
    required = {'Policy','Date','Period','Entries','Best actual FD','Average actual FD','Worst actual FD'}
    if not required <= set(reports) or reports.duplicated(['Date','Policy']).any():
        raise ValueError('Use one paired experiment per date.')
    # Keep original two-policy statistics comparable, and separately test
    # the new fixed policy against the same projection portfolio.
    if STRESS_POLICY in set(reports.Policy):
        stress = reports.loc[reports.Policy.eq(STRESS_POLICY)].copy()
        baseline = reports.loc[reports.Policy.eq('Projection ranked') & reports.Date.isin(stress.Date)].copy()
        baseline['Period'] = baseline.Date.map(stress.set_index('Date').Period)
        stress['Policy'] = 'Simulated P90 ranked'
        new = summarize_portfolio_experiments(pd.concat([baseline,stress],ignore_index=True))
        new['Comparison'] = STRESS_POLICY
        original = summarize_portfolio_experiments(reports.loc[~reports.Policy.eq(STRESS_POLICY)])
        original['Comparison'] = 'Simulated P90 ranked'
        return pd.concat([original,new],ignore_index=True)
    policies = ['Projection ranked','Simulated P90 ranked']
    rows = []
    for (period, day), group in reports.groupby(['Period','Date'], sort=True):
        if set(group.Policy) != set(policies) or not group.Entries.eq(ENTRIES).all():
            raise ValueError('Both policies need an identical four-entry budget.')
        metrics = group.set_index('Policy')[['Best actual FD','Average actual FD','Worst actual FD']].apply(
            pd.to_numeric, errors='coerce')
        if not np.isfinite(metrics).all().all():
            raise ValueError('Complete paired actual scores required.')
        delta = metrics.loc[policies[1]] - metrics.loc[policies[0]]
        rows.append({'Period':period,'Date':day, 'Best FD difference':delta.iloc[0],
                     'Average FD difference':delta.iloc[1], 'Worst FD difference':delta.iloc[2]})
    paired = pd.DataFrame(rows)
    if not paired.Date.is_unique:
        raise ValueError('Each date must belong to only one evaluation period.')
    summaries = []
    for period, group in paired.groupby('Period', sort=True):
        n = len(group)
        best = group['Best FD difference']
        status = 'Exploratory only' if period == 'Exploratory' else 'Insufficient prospective dates'
        if period == 'Prospective' and n >= 5:
            status = ('Requires independent validation' if best.mean() > 0 and best.gt(0).sum() > n/2
                      else 'No consistent best-score improvement')
        summaries.append({'Period':period,'Paired dates':n,
                          'Mean best FD difference':best.mean(),
                          'Mean average FD difference':group['Average FD difference'].mean(),
                          'Mean worst FD difference':group['Worst FD difference'].mean(),
                          'Dates simulation better':int(best.gt(0).sum()),
                          'Dates tied':int(best.eq(0).sum()),
                          'Dates projection better':int(best.lt(0).sum()),
                          'Review status':status})
    return pd.DataFrame(summaries)


def walk_forward_portfolios(captures, replays, *, total_budget_seconds=45,
                            builder=build_experiment, scorer=score_experiment):
    """Use earlier dates only, reporting every skipped date and a bounded solve budget."""
    if not 0 < total_budget_seconds <= 90:
        raise ValueError('Use a positive bounded evaluation budget.')
    dates = [item[0] for item in captures]
    if len(dates) != len(set(dates)):
        raise ValueError('Select one verified capture per date.')
    if not captures or replays.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    replay_days = pd.to_datetime(replays.slate_date, errors='coerce').dt.date
    deadline = monotonic() + total_budget_seconds
    reports, coverage = [], []
    for day, contest, version, pool, results in sorted(captures, key=lambda x:x[0]):
        earlier_dates = sorted(set(replay_days.dropna().loc[replay_days.lt(day)]), reverse=True)[:5]
        training = replays.loc[replay_days.isin(earlier_dates)].copy()
        row = {'Date':day.isoformat(),'Contest':contest,'Version':version[:12],
               'Earlier training dates':len(earlier_dates),'Training played rows':0}
        if training.empty:
            row['Status'] = 'No earlier verified training'
        elif deadline-monotonic() <= 0:
            row['Status'] = 'Evaluation solve budget exhausted'
        else:
            try:
                rosters,ranges,selections,count = builder(
                    pool,training,day,time_budget_seconds=min(15,deadline-monotonic()))
                report,_ = scorer(pool,rosters,selections,results,day)
                reports.append(report.assign(Contest=contest,Version=version[:12]))
                row.update({'Training played rows':count,'Status':'Paired evaluation complete'})
            except (ValueError,TypeError,KeyError,OSError) as exc:
                row['Status'] = str(exc)
        coverage.append(row)
    details = pd.concat(reports,ignore_index=True) if reports else pd.DataFrame()
    return details,summarize_portfolio_experiments(details),pd.DataFrame(coverage)
