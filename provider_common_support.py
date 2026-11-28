"""Descriptive cross-provider diagnostics on exact matched player samples.

Upstream archive reconciliation, score format and publication chronology must
already be validated. Unverified timing is explicitly separated from eligible
timed evidence. No source weight or scoring policy is selected here.
"""
import numpy as np
import pandas as pd


def common_provider_comparison(frame, *, forecasts, actual):
    """Require unique slate/player/metric rows; keep missing evidence visible.

    Input is wide: one exact contest player per date/metric, with timing_scope
    equal to 'timed' or 'recovered'. Do not combine multiple contests per date,
    count duplicate captures, or silently convert missing forecasts to zero.
    """
    keys = ['date','contest_id','player_id','metric']
    forecasts = list(forecasts)
    if (not forecasts or len(set(forecasts)) != len(forecasts)
            or set(forecasts) & set(keys + ['timing_scope',actual])):
        raise ValueError('Distinct forecast columns required')
    needed = set(keys + ['timing_scope',actual] + forecasts)
    if not needed <= set(frame):
        raise ValueError('Missing comparison fields')
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError('Ambiguous player/metric identity')
    if frame.groupby(['date','metric']).contest_id.nunique().gt(1).any():
        raise ValueError('Use one contest per date and metric')
    if not frame.timing_scope.isin(['timed','recovered']).all():
        raise ValueError('Explicit timing scope required')
    if frame.groupby(['date','metric']).timing_scope.nunique().gt(1).any():
        raise ValueError('Conflicting capture scope')
    df = frame.copy()
    cols = [actual,*forecasts]
    df[cols] = df[cols].apply(pd.to_numeric,errors='raise')
    detail=[]
    for (day,contest,metric,scope),g in df.groupby(
            ['date','contest_id','metric','timing_scope'],sort=True):
        outcome = g.loc[np.isfinite(g[actual])]
        common = outcome.loc[np.isfinite(outcome[forecasts]).all(axis=1)]
        for f in forecasts:
            e = common[f] - common[actual]
            detail.append(dict(date=day,contest_id=contest,metric=metric,
                timing_scope=scope,forecast=f,known_outcomes=len(outcome),
                available_forecasts=int(np.isfinite(outcome[f]).sum()),
                common_players=len(common),
                mae=float(e.abs().mean()) if len(e) else None,
                bias=float(e.mean()) if len(e) else None))
    return pd.DataFrame(detail)
