"""Compact, read-only pregame evidence readiness for every eligible NBA player."""
from datetime import date
import json
import pandas as pd
from nba_component_history import _day
from nba_window_shadow import _row_predictions
from nba_pooled_history_shadow import pooled_prediction


def history_readiness(pool,slate):
    """Separate attached histories from usable forecasts and freshness.

    The seven-day label is a review safeguard, not a new eight-window
    prediction policy. No player is excluded or scores changed.
    """
    required={'fanduel_id','eligible','fanduel_name','team','adjusted_minutes',
              'adjusted_fd_points','shadow_hw_history_json','shadow_hw_slate',
              'pooled_hw_history_json','pooled_hw_slate'}
    if type(slate) is not date or not required<=set(pool):
        raise ValueError('Require current dated reviewed pool and attached histories')
    if pool.fanduel_id.isna().any() or not pool.fanduel_id.is_unique:
        raise ValueError('Unique contest IDs required')
    def inspect(raw,n):
        try:
            logs=json.loads(raw)
            if not isinstance(logs,list) or len(logs)!=n:
                return False,None
            days=[_day(r['game_date']) for r in logs]
            if days!=sorted(set(days)) or days[-1]>=slate:
                return False,None
            return True,(slate-days[-1]).days
        except (TypeError,ValueError,KeyError,AttributeError):
            return False,None
    rows=[]
    for r in pool.itertuples():
        if str(r.eligible).lower()!='true':
            continue
        a,age8=inspect(r.shadow_hw_history_json,8)
        b,age4=inspect(r.pooled_hw_history_json,4)
        eight=_row_predictions(r,slate) is not None
        four=pooled_prediction(r,slate) is not None
        rows.append(dict(fanduel_id=r.fanduel_id,history_eight_attached=a,
            history_eight_age_days=age8,history_eight_usable=eight,
            history_eight_recent_usable=eight and age8 is not None and age8<=7,
            history_four_attached=b,history_four_age_days=age4,history_pooled_usable=four))
    return pd.DataFrame(rows,columns=['fanduel_id','history_eight_attached','history_eight_age_days',
        'history_eight_usable','history_eight_recent_usable','history_four_attached',
        'history_four_age_days','history_pooled_usable'])
