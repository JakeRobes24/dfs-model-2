import pandas as pd
import pytest
from model import optimize
from nba_core_challenge import challenge_shared_core


def fixture():
    ids=[f'123-{i:02d}' for i in range(24)]
    pool=pd.DataFrame(dict(fanduel_id=ids,fanduel_name=ids,salary=6000,
        team=['BOS','NYK','CLE','ORL']*6,
        roster_eligibility='PG/SG/SF/PF/C/G/F/F/C/UTIL',eligible=True,
        confidence='high',minutes_method='DAILY',injury_flag='',adjusted_minutes=30,
        adjusted_fd_points=list(range(20,44))))
    baseline=optimize(pool,number=4,max_overlap=7)
    return pool,baseline


def test_shared_core_challenge_produces_legal_unique_counterfactuals_without_mutating():
    pool,baseline=fixture()
    before=pool.copy(deep=True)
    original=baseline.copy(deep=True)
    report,alternatives=challenge_shared_core(pool,baseline,time_budget_seconds=30)
    assert len(report)==4
    assert report.Status.str.startswith('Certified').all()
    assert report['Affected baseline entries'].between(2,4).all()
    assert report['FD gap vs best baseline'].le(1e-8).all()
    assert not alternatives.empty
    assert alternatives.groupby('lineup').fanduel_id.nunique().eq(9).all()
    memberships={frozenset(g.fanduel_id) for _,g in baseline.groupby('lineup')}
    for label,g in alternatives.groupby('lineup'):
        ids=frozenset(g.fanduel_id)
        omitted=set(report.loc[report.Scenario.eq(label),'Omitted IDs'].iloc[0].split(' | '))
        assert not ids&omitted and ids not in memberships
        memberships.add(ids)
        assert g.salary.sum()<=60000 and g.solver_optimal.all() and g.team_rules_verified.all()
    pd.testing.assert_frame_equal(pool,before)
    pd.testing.assert_frame_equal(baseline,original)


def test_core_challenge_rejects_stale_baseline_and_does_not_accept_partial_solver(monkeypatch):
    pool,baseline=fixture()
    stale=pool.assign(eligible=~pool.fanduel_id.eq(baseline.fanduel_id.iloc[0]))
    with pytest.raises(ValueError,match='no longer eligible'):
        challenge_shared_core(stale,baseline)
    with pytest.raises(ValueError,match='bounded'):
        challenge_shared_core(pool,baseline,max_players=4)
    def partial(*args,**kwargs):
        return baseline.loc[baseline.lineup.eq(1)].assign(solver_optimal=False)
    monkeypatch.setattr('nba_core_challenge.optimize',partial)
    report,alternatives=challenge_shared_core(pool,baseline,max_players=1)
    assert report.Status.tolist()==['Candidate not certified optimal']
    assert alternatives.empty


def test_expanded_review_plans_heavy_exposures_and_discloses_unreviewed(monkeypatch):
    from exposure_challenge_plan import exposure_challenge_plan
    pool,baseline=fixture()
    rosters=[list(g.fanduel_id) for _,g in baseline.groupby('lineup')]
    plan=exposure_challenge_plan(rosters,max_targets=2,
        priority=pool.set_index('fanduel_id').adjusted_fd_points.to_dict())
    omitted=[]
    def partial(restricted,**kwargs):
        omitted.append(tuple(sorted(restricted.loc[~restricted.eligible,'fanduel_id'])))
        return pd.DataFrame()
    monkeypatch.setattr('nba_core_challenge.optimize',partial)
    report,alternatives=challenge_shared_core(pool,baseline,expanded=True,max_players=2,
                                             time_budget_seconds=30)
    assert omitted==[tuple(sorted(x)) for x in plan['scenarios']]
    assert report.loc[report.Status.eq('Not run: target limit'),'Omitted IDs'].tolist()==plan['unreviewed_targets']
    assert alternatives.empty
    assert len(report)==len(plan['scenarios'])+len(plan['unreviewed_targets'])


def test_expanded_review_accepts_nine_target_budget_and_keeps_all_scenario_failures_visible(monkeypatch):
    from exposure_challenge_plan import exposure_challenge_plan
    pool,baseline=fixture()
    rosters=[list(g.fanduel_id) for _,g in baseline.groupby('lineup')]
    plan=exposure_challenge_plan(rosters,max_targets=9,
        priority=pool.set_index('fanduel_id').adjusted_fd_points.to_dict())
    monkeypatch.setattr('nba_core_challenge.optimize',lambda *args,**kwargs: pd.DataFrame())
    report,alternatives=challenge_shared_core(pool,baseline,expanded=True,max_players=9,
                                             time_budget_seconds=30)
    assert len(report)==len(plan['scenarios'])+len(plan['unreviewed_targets'])
    assert not report.Status.str.startswith('Certified').any()
    assert alternatives.empty
