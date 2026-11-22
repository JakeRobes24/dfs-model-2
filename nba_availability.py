"""Research-only pre-lock availability estimates from explicitly verified outcomes."""
import numpy as np
import pandas as pd

from nba_simulation import MINUTE_BANDS, MIN_COHORT, OutcomeDraws


HARD_EXCLUSIONS = {'out', 'waived', 'inactive', 'suspended'}
STATUS_GROUPS = {'available': 'available', 'probable': 'available',
                 'questionable': 'uncertain', 'doubtful': 'uncertain'}
PRIOR_WEIGHT = 20


def _status(values):
    return values.fillna('').astype(str).str.strip().str.lower()


def _known_outcomes(history):
    rows = history.copy()
    rows['slate_date'] = pd.to_datetime(rows.slate_date, errors='coerce').dt.normalize()
    rows['daily_minutes'] = pd.to_numeric(rows.daily_minutes, errors='coerce')
    rows['daily_points'] = pd.to_numeric(rows.daily_points, errors='coerce')
    rows['prelock_status'] = _status(rows.prelock_status)
    unique = ~rows.duplicated(['slate_date', 'fanduel_id'], keep=False)
    return rows.loc[unique & rows.slate_date.notna() & rows.fanduel_id.notna()
                    & rows.eligible.eq(True) & rows.daily_minutes.gt(0) & rows.daily_minutes.le(48)
                    & np.isfinite(rows.daily_points) & rows.daily_points.gt(0)
                    & ~rows.prelock_status.isin(HARD_EXCLUSIONS)
                    & rows.verified_outcome.isin(['played', 'did_not_play'])].copy()


def estimate_dnp(history, pool, slate_date):
    """Estimate DNP probability with prior-date minutes and pre-lock status groups."""
    known = _known_outcomes(history)
    prior = known.loc[known.slate_date.lt(pd.Timestamp(slate_date).normalize())].copy()
    if len(prior) < MIN_COHORT:
        raise ValueError('Insufficient earlier verified availability outcomes.')
    prior['dnp'] = prior.verified_outcome.eq('did_not_play')
    prior['band'] = np.digitize(prior.daily_minutes, MINUTE_BANDS)
    prior['group'] = prior.prelock_status.map(STATUS_GROUPS).fillna('no firm status')

    minutes = pd.to_numeric(pool.projected_minutes, errors='coerce')
    if (pool.empty or not pool.fanduel_id.is_unique or pool.fanduel_id.isna().any()
            or not (minutes.gt(0) & minutes.le(48)).all()):
        raise ValueError('Availability estimates require distinct players and valid positive minutes.')
    status = _status(pool.prelock_status)
    if status.isin(HARD_EXCLUSIONS).any():
        raise ValueError('Exclude players already ruled out before estimating availability.')
    bands = prior.groupby('band').dnp.agg(['sum', 'size'])
    cohorts = prior.groupby(['band', 'group']).dnp.agg(['sum', 'size'])
    global_rate = (prior.dnp.sum() + .5) / (len(prior) + 1)
    overall_band_rates = (bands['sum'] + PRIOR_WEIGHT * global_rate) / (bands['size'] + PRIOR_WEIGHT)
    # Back off to the other statuses within the band before falling back to the full sample.
    cohort_bands = cohorts.index.get_level_values('band')
    other_counts = bands['size'].reindex(cohort_bands).to_numpy() - cohorts['size']
    other_dnps = bands['sum'].reindex(cohort_bands).to_numpy() - cohorts['sum']
    other_rate = (other_dnps + PRIOR_WEIGHT * global_rate) / (other_counts + PRIOR_WEIGHT)
    cohort_rates = (cohorts['sum'] + PRIOR_WEIGHT * other_rate) / (cohorts['size'] + PRIOR_WEIGHT)
    target_bands = np.digitize(minutes, MINUTE_BANDS)
    target_groups = status.map(STATUS_GROUPS).fillna('no firm status')
    keys = pd.MultiIndex.from_arrays([target_bands, target_groups], names=['band', 'group'])
    band_default = overall_band_rates.reindex(target_bands).fillna(global_rate).to_numpy()
    rates = cohort_rates.reindex(keys).to_numpy()
    return pd.DataFrame({'fanduel_id': pool.fanduel_id.to_numpy(),
                         'dnp_probability': np.where(np.isnan(rates), band_default, rates),
                         'cohort_rows': cohorts['size'].reindex(keys, fill_value=0).to_numpy(),
                         'historical_dnp_probability': global_rate})


def apply_availability(draws, risk, *, seed=43):
    """Apply a reproducible zero outcome for DNP draws without mutating inputs."""
    probabilities = (risk.set_index('fanduel_id', verify_integrity=True)
                     .reindex(draws.fanduel_ids).dnp_probability)
    if not probabilities.between(0, 1).all():
        raise ValueError('Supply a valid DNP probability for every simulated player.')
    plays = np.random.default_rng(seed).random(draws.minutes.shape) >= probabilities.to_numpy()
    return OutcomeDraws(draws.fanduel_ids, np.where(plays, draws.minutes, 0),
                        np.where(plays, draws.fd_points, 0))


def walk_forward_availability(history):
    """Compare availability estimates with a flat prior and assuming everyone plays."""
    known = _known_outcomes(history)
    reports = []
    for day, heldout in known.groupby('slate_date', sort=True):
        earlier = known.loc[known.slate_date.lt(day)]
        if len(earlier) < MIN_COHORT:
            continue
        pool = heldout.rename(columns={'daily_minutes': 'projected_minutes'})
        estimates = estimate_dnp(earlier, pool, day)
        paired = heldout.merge(estimates, on='fanduel_id', validate='one_to_one')
        actual = paired.verified_outcome.eq('did_not_play').astype(float)
        reports.append({'slate_date': day.date().isoformat(), 'training_players': len(earlier),
                        'test_players': len(actual), 'verified_dnps': int(actual.sum()),
                        'observed_dnp_rate': actual.mean(),
                        'estimated_dnp_rate': paired.dnp_probability.mean(),
                        'cohort_brier': ((paired.dnp_probability - actual) ** 2).mean(),
                        'flat_prior_brier': ((paired.historical_dnp_probability - actual) ** 2).mean(),
                        'always_plays_brier': actual.mean()})
    return pd.DataFrame(reports)
