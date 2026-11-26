"""Direct parity check of fixed NFL workload hypothesis using archived evidence."""
import json
from pathlib import Path
import pytest
from nfl_workload_scenarios import historical_backfield_prior

def test_nov25_backfield_prior_from_four_earlier_games():
    evidence=json.loads((Path(__file__).parent/'docs/validation/nov25-backfield-exploratory.json').read_text())
    result=historical_backfield_prior(evidence['contest'],evidence['pair'],evidence['history'],target_day=evidence['date'])
    expected=evidence['results']
    assert result['supported'] and result['games']==4
    assert result['historical_pair_volume']==pytest.approx(expected['historical_pair_volume'])
    assert result['historical_first_share']==pytest.approx(expected['historical_corum_share'])
    assert result['blended_pair_volume']==pytest.approx(expected['blended_pair_volume'])
    assert result['blended_first_share']==pytest.approx(expected['blended_corum_share'])
    assert [p['carries'] for p in result['players']]==pytest.approx(expected['blended_carries'])
    assert sum(abs(p['carries']-a) for p,a in zip(result['players'],expected['actual_carries']))/2==pytest.approx(expected['shadow_carry_mae'])
