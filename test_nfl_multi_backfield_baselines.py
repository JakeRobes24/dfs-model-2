import json
from pathlib import Path
import pytest
from nfl_history_baseline_review import compare_history_baselines

def test_additional_official_log_cohorts_and_equal_pair_summary():
    f=json.loads((Path(__file__).parent/'docs/validation/nfl-multi-backfield-baselines.json').read_text())
    out=[]
    for cohort,expected in zip(f['cohorts'],f['expected_by_pair']):
        r=compare_history_baselines(cohort['history'],player_ids=cohort['player_ids'],
                                    team=cohort['team'],target_day=cohort['target_day'])
        assert not r['certified']
        assert len(r['rows'])==3*(len(cohort['history'])-4)
        for a,b in zip(r['summary'],expected['summary']):
            assert a['policy']==b['policy']
            assert a['dates']==b['dates']
            for k in ('carry_mae','volume_abs_error','share_abs_error_pp'):
                assert a[k]==pytest.approx(b[k])
        out.append(r['summary'])
    for expected in f['expected_equal_pair_summary']:
        rr=[next(r for r in result if r['policy']==expected['policy']) for result in out]
        assert sum(r['dates'] for r in rr)==expected['pair_game_dates']
        for k in ('carry_mae','volume_abs_error','share_abs_error_pp'):
            assert sum(r[k] for r in rr)/len(rr)==pytest.approx(expected['equal_pair_'+k])
