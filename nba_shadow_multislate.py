"""Multi-slate prospective evidence for fixed shadow policies; no automatic promotion."""
from datetime import date
import numpy as np
import pandas as pd
from nba_shadow_research import compare_shadow_forecasts, FEATURES, POLICIES
from nba_combined_scoring_shadow import compare_frozen_combined, compare_frozen_paired_rate, PAIRED_RATE_POLICY

# The fixed policy was introduced on this date; earlier replays are exploratory.
POLICY_DECLARED = date(2026, 11, 24)
MIN_DATES = 5
MIN_PAIRS = 100

RATE_COVERAGE_FIELDS = (
    'Eligible players reviewed for rate blend',
    'Eligible with two fresh paired sources',
    'Eligible supported rate forecasts',
    'Eligible rate provenance rejected',
    'Eligible rate invalid team evidence',
    'Eligible rate uncertain availability',
    'Eligible rate minutes policy not met',
    'Eligible rate insufficient paired sources',
    'Eligible rate disagreement',
)


def compare_across_slates(replays):
    """Return per-date and aggregate paired metrics, weighting dates equally as well as players.

    Only one contest and one verified pre-tip capture per date are accepted.
    Fixed-policy prospective results are separated from earlier exploratory evidence.
    No policy is fitted, selected or promoted based on these results.
    """
    if replays.empty:
        return pd.DataFrame(), pd.DataFrame()
    required = {'slate_date', 'fanduel_id', 'replay_captured_at_utc', 'replay_cutoff_utc',
                'replay_before_full_slate_tip', 'replay_timing'}
    if not required <= set(replays):
        raise ValueError('Multi-slate evaluation requires verified frozen replay chronology.')
    data = replays.copy()
    days = pd.to_datetime(data.slate_date, format='%Y-%m-%d', errors='coerce').dt.date
    if days.isna().any() or data.fanduel_id.isna().any():
        raise ValueError('Invalid replay dates or player IDs.')
    data['_day'] = days
    reports = []
    for day, frame in data.groupby('_day', sort=True):
        ids = frame.fanduel_id.astype(str)
        capture = pd.to_datetime(frame.replay_captured_at_utc, utc=True, errors='coerce', format='mixed')
        cutoff = pd.to_datetime(frame.replay_cutoff_utc, utc=True, errors='coerce', format='mixed')
        if (not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+').all()
                or ids.str.split('-').str[0].nunique() != 1
                or capture.nunique() != 1 or not (capture < cutoff).all()
                or not cutoff.dt.tz_convert('America/New_York').dt.date.eq(day).all()
                or not frame.replay_before_full_slate_tip.astype(str).str.lower().eq('true').all()
                or not frame.replay_timing.eq('before_scheduled_tip').all()):
            raise ValueError(f'{day}: use one verified full-slate pre-tip capture.')
        report = compare_shadow_forecasts(frame)
        if report.empty:
            report = pd.DataFrame({'Policy': POLICIES, 'Paired players': 0})
        report = pd.concat([report, compare_frozen_combined(frame), compare_frozen_paired_rate(frame)], ignore_index=True)
        report['Date'] = day.isoformat()
        report['Period'] = 'Prospective' if day > POLICY_DECLARED else 'Exploratory'
        if day <= date(2026,11,25):
            report.loc[report.Policy.eq(PAIRED_RATE_POLICY), 'Period'] = 'Exploratory'
        reports.append(report)
    daily = pd.concat(reports, ignore_index=True)
    for col in ['Eligible played with baseline', 'DAILY MAE', 'Reviewed MAE', 'Shadow MAE',
                'MAE improvement vs reviewed', 'Shadow bias']:
        if col not in daily:
            daily[col] = np.nan
    aggregate = []
    for (period, policy), group in daily.groupby(['Period', 'Policy'], sort=True):
        supported = group.loc[group['Paired players'].gt(0)]
        pairs = int(supported['Paired players'].sum())
        weights = supported['Paired players']
        weighted = lambda col: float(np.average(supported[col], weights=weights)) if pairs else np.nan
        gains = supported['MAE improvement vs reviewed']
        dates = len(supported)
        equal = gains.mean()
        win_days = int(gains.gt(0).sum())
        baseline = group['Eligible played with baseline'].sum(min_count=1)
        status = 'Exploratory only'
        if period == 'Prospective':
            status = 'Insufficient prospective evidence'
            if dates >= MIN_DATES and pairs >= MIN_PAIRS:
                status = 'Needs independent validation'
                if equal <= 0 or weighted('MAE improvement vs reviewed') <= 0:
                    status = 'No consistent accuracy improvement'
        aggregate.append({'Period': period, 'Policy': policy, 'Dates reviewed': len(group),
                          'Dates with paired evidence': dates, 'Paired players': pairs,
                          'Known baseline players': baseline,
                          'DAILY MAE (player weighted)': weighted('DAILY MAE'),
                          'Reviewed MAE (player weighted)': weighted('Reviewed MAE'),
                          'Shadow MAE (player weighted)': weighted('Shadow MAE'),
                          'Improvement (player weighted)': weighted('MAE improvement vs reviewed'),
                          'Improvement (equal date weight)': equal,
                          'Improved dates': win_days, 'Review status': status})
        if policy == PAIRED_RATE_POLICY:
            # Older captures may lack paired-source provenance. Missing counts
            # are unknown, not zero, and do not enter the coverage denominator.
            counts = group.reindex(columns=RATE_COVERAGE_FIELDS)
            known = counts.notna().all(axis=1)
            totals = counts.loc[known].sum(min_count=1)
            aggregate[-1]['Dates with known rate coverage'] = int(known.sum())
            aggregate[-1].update(totals.to_dict())
            denominator = totals.iloc[0]
            aggregate[-1]['Supported rate coverage (%)'] = (
                100 * totals['Eligible supported rate forecasts'] / denominator
                if pd.notna(denominator) and denominator > 0 else np.nan)
    return daily, pd.DataFrame(aggregate)
