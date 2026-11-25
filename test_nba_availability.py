import numpy as np
import pandas as pd
import pytest

from nba_availability import apply_availability, estimate_dnp, walk_forward_availability
from nba_simulation import OutcomeDraws


def availability_history(day):
    return pd.DataFrame({
        'slate_date': day, 'fanduel_id': [f'{day}-{n}' for n in range(30)],
        'eligible': True, 'daily_minutes': [12] * 15 + [24] * 15, 'daily_points': 20,
        'prelock_status': ['questionable'] * 5 + [''] * 25,
        'verified_outcome': ['did_not_play'] * 5 + ['played'] * 25,
    })


def test_availability_uses_explicit_prior_outcomes_and_softens_sparse_status():
    earlier = availability_history('2026-11-18')
    later = availability_history('2026-11-20').assign(verified_outcome='did_not_play')
    unresolved = earlier.iloc[:1].assign(fanduel_id='unknown', verified_outcome='needs_review')
    pool = pd.DataFrame({'fanduel_id': ['q', 'unlisted'], 'projected_minutes': [12, 12],
                         'prelock_status': ['questionable', '']})
    estimates = estimate_dnp(earlier, pool, '2026-11-20')
    pd.testing.assert_frame_equal(estimates, estimate_dnp(
        pd.concat([earlier, later, unresolved], ignore_index=True), pool, '2026-11-20'))
    assert estimates.loc[0, 'cohort_rows'] == 5
    assert 0 < estimates.loc[1, 'dnp_probability'] < estimates.loc[0, 'dnp_probability'] < 1
    with pytest.raises(ValueError, match='already ruled out'):
        estimate_dnp(earlier, pool.assign(prelock_status='out'), '2026-11-20')


def test_availability_mask_keeps_player_alignment_and_shared_draws():
    draws = OutcomeDraws(pd.Index(['plays', 'out']), np.full((32, 2), 24), np.full((32, 2), 30))
    risk = pd.DataFrame({'fanduel_id': ['out', 'plays'], 'dnp_probability': [1, 0]})
    adjusted = apply_availability(draws, risk)
    assert (adjusted.fd_points[:, 0] == 30).all()
    assert (adjusted.minutes[:, 1] == 0).all()
    assert (adjusted.fd_points[:, 1] == 0).all()
    assert (draws.fd_points == 30).all()
    with pytest.raises(ValueError, match='every simulated player'):
        apply_availability(draws, risk.iloc[:1])


def test_walk_forward_omits_hard_outs_and_unknown_results():
    earlier = availability_history('2026-11-18')
    later = availability_history('2026-11-20')
    later.loc[0, 'prelock_status'] = 'out'
    later.loc[1, 'verified_outcome'] = 'needs_review'
    report = walk_forward_availability(pd.concat([later, earlier])).iloc[0]
    assert report.training_players == 30
    assert report.test_players == 28
    assert report.verified_dnps == 3
