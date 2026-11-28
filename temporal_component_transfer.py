"""Offline fixed-grid blend transfer on identical archived component forecasts."""
import numpy as np
import pandas as pd

GRID = (0., .25, .5, .75, 1.)


def paired_archive(frame, keys, policies, *, actual, forecast):
    """Strict common support. No imputation, duplicate identities or mixed outcomes."""
    if len(set(keys)) != len(keys) or len(set(policies)) != len(policies) or not policies:
        raise ValueError('Distinct keys and policies required')
    rows = frame.loc[frame.policy.isin(policies), [*keys, 'policy', actual, forecast]].copy()
    if rows[keys].isna().any().any() or rows.duplicated([*keys, 'policy']).any():
        raise ValueError('Duplicate or missing archive identity')
    if not np.isfinite(rows[[actual, forecast]].to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite archived forecast or outcome')
    if rows.groupby(keys, dropna=False)[actual].nunique().ne(1).any():
        raise ValueError('Mismatched outcomes')
    wide = rows.pivot(index=keys, columns='policy', values=forecast)
    if set(wide.columns) != set(policies) or wide.isna().any().any():
        raise ValueError('Unequal forecast support')
    outcome = rows.drop_duplicates(keys).set_index(keys)[actual]
    return wide.assign(actual=outcome).reset_index()


def _score(rows, estimate, period):
    error = estimate - rows.actual
    values = pd.DataFrame({'period': rows[period], 'abs': error.abs(), 'signed': error})
    grouped = values.groupby('period', sort=True).mean()
    return dict(n=len(rows), periods=len(grouped), mae=float(grouped['abs'].mean()),
                bias=float(grouped.signed.mean()))


def transfer_grid(train, test, baseline, challenger, *, period, chronology,
                  minimum_rows=40, minimum_periods=4):
    """Fit a fixed grid with earlier periods only, evaluate on later exact rows.

    Equal-period MAE is the fitting criterion; ties prefer less change.
    A missing/insufficient training sample cannot select a weight.
    """
    if train.empty or test.empty:
        return None
    if train[chronology].isna().any() or test[chronology].isna().any():
        raise ValueError('Missing chronology')
    if pd.to_datetime(train[chronology]).max() >= pd.to_datetime(test[chronology]).min():
        raise ValueError('Training must end before evaluation begins')
    fields = [baseline, challenger, 'actual']
    for rows in (train, test):
        if rows[period].isna().any() or not np.isfinite(rows[fields].to_numpy(dtype=float)).all():
            raise ValueError('Missing paired evaluation data')
    if len(train) < minimum_rows or train[period].nunique() < minimum_periods:
        return None
    def grid(rows):
        return {w: _score(rows, (1-w)*rows[baseline]+w*rows[challenger], period) for w in GRID}
    training = grid(train)
    weight = min(GRID, key=lambda w: (training[w]['mae'], w))
    testing = grid(test)
    return dict(weight=weight, training=training, testing=testing,
                selected=testing[weight], training_end=str(train[chronology].max()),
                evaluation_start=str(test[chronology].min()))
