import numpy as np
import pytest
from nba_group_dependence import compare_groups, correlation_matrix, normal_scores


def test_relationship_matrix_remains_positive_definite():
    c=correlation_matrix(['A']*4+['B']*4,-.35,.35)
    assert np.linalg.eigvalsh(c)[0]>=.01-1e-12
    assert np.diag(c)==pytest.approx(np.ones(8))
    assert correlation_matrix(['A','A','B','B'],0,0)==pytest.approx(np.eye(4))


def test_group_comparison_uses_identical_players_and_strictly_prior_dates():
    rows=[]
    for d in range(1,7):
        for game in range(5):
            for i in range(4):
                rows.append(dict(date=f'2026-11-{d:02}',game=f'game{game}',team=['A','B'][i//2],
                                 nba_id=str(game*4+i),minutes=25+i,fd=30+i,actual_fd=30+i+(d+i)%5))
    result=compare_groups(rows)
    assert result['rows'] and not result['certified']
    assert {r['groups'] for r in result['summary'] if r['kind']=='four_same_game'}=={5}
    assert {r['groups'] for r in result['summary'] if r['kind']=='two_teammates'}=={10}
    changed=[dict(r,actual_fd=r['actual_fd']+100) if r['date']=='2026-11-06' else r for r in rows]
    other=compare_groups(changed)
    for a,b in zip(result['rows'],other['rows']):
        assert a['training_latest']<a['date']
        assert (a['players'],a['center'],a['width'])==(b['players'],b['center'],b['width'])


def test_normal_scores_are_finite():
    r=normal_scores(10,10,2)
    assert r['coverage']==1 and r['crps']>0
    assert r['interval_score']==r['width']
