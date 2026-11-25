"""Deterministic checks for a bounded optimizer run."""
import pandas as pd
import pytest
import model

def fixture():
    return pd.DataFrame([
        dict(fanduel_id=str(i), fanduel_name=str(i), salary=6000,
             roster_eligibility=slot, eligible=True, confidence='high',
             adjusted_fd_points=25., adjusted_minutes=30.,
             minutes_method='fixture', injury_flag='')
        for i,slot in enumerate(model.SLOTS)
    ])

def test_budget_expiry_before_solver(monkeypatch):
    ticks=iter([0., 2.])
    monkeypatch.setattr(model,'monotonic',lambda:next(ticks))
    def should_not_run(*args, **kwargs):
        pytest.fail('Solver ran after deadline')
    monkeypatch.setattr(model,'milp',should_not_run)
    assert model.optimize(fixture(), time_budget_seconds=1).empty

@pytest.mark.parametrize('budget',[0,-1,float('nan'),float('inf'),True])
def test_bad_budget(budget):
    with pytest.raises(ValueError,match='time budget'):
        model.optimize(fixture(),time_budget_seconds=budget)

def test_budgeted_legal_candidate():
    rows=model.optimize(fixture(),number=1,time_budget_seconds=10)
    assert len(rows)==9 and rows.fanduel_id.nunique()==9
    assert rows.salary.sum()<=60000


def test_portfolio_budget_reserves_distinct_alternative_time(monkeypatch):
    import site_ui
    from test_nba_optimizer_integration import fixture_pool
    pool = fixture_pool()
    lineups = model.optimize(pool, number=4, max_overlap=7)
    alternative = model.optimize(pool, number=1, exclude_rosters=(lineups.loc[lineups.lineup.eq(1),'fanduel_id'],))
    clock = [0.]
    calls = []
    def fake_optimize(_pool, **kwargs):
        calls.append(kwargs)
        if kwargs['number'] == 4:
            clock[0] += kwargs['time_budget_seconds']
            return lineups
        return alternative
    monkeypatch.setattr(site_ui,'monotonic',lambda: clock[0])
    monkeypatch.setattr(site_ui,'optimize',fake_optimize)
    result = site_ui.generate_and_challenge(pool,7,False,time_budget_seconds=60)
    assert calls[0]['time_budget_seconds'] == pytest.approx(48)
    assert calls[1]['time_budget_seconds'] == pytest.approx(12)
    assert len(result[1]) == 4
    assert set(result[2].fanduel_id) != set(result[0].loc[result[0].lineup.eq(1),'fanduel_id'])
