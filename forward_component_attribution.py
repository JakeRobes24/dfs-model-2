"""Exact symmetric volume/rate error attribution for frozen component forecasts.

No new forecast, weight or policy selection. Both terms sum to signed error;
absolute terms need not sum to absolute total error.
"""
from math import isfinite
from statistics import mean


def attribute(projected_volume, actual_volume, projected_value, actual_value):
    values = (projected_volume, actual_volume, projected_value, actual_value)
    if any(type(v) not in (int,float) or not isfinite(v) for v in values):
        return None
    if min(projected_volume, actual_volume)<=0:
        return None
    pr=projected_value/projected_volume
    ar=actual_value/actual_volume
    volume=(projected_volume-actual_volume)*(pr+ar)/2
    rate=(pr-ar)*(projected_volume+actual_volume)/2
    return dict(volume=volume,rate=rate,total=projected_value-actual_value)


def summarize_attribution(rows):
    rows=list(rows)
    if not rows:
        return dict(n=0,volume_mae=None,rate_mae=None,volume_bias=None,rate_bias=None,total_mae=None,total_bias=None)
    return dict(n=len(rows),
                volume_mae=mean(abs(r['volume']) for r in rows),
                rate_mae=mean(abs(r['rate']) for r in rows),
                volume_bias=mean(r['volume'] for r in rows),
                rate_bias=mean(r['rate'] for r in rows),
                total_mae=mean(abs(r['total']) for r in rows),
                total_bias=mean(r['total'] for r in rows))
