"""Conservative, read-only cross-slate FanDuel identity audit. No automatic merges."""
import re
import pandas as pd

def audit(left, right):
    for df in (left,right):
        if not {'fanduel_id','name'} <= set(df.columns):
            raise ValueError('Required columns: fanduel_id, name')
        if df.fanduel_id.isna().any() or df.name.isna().any() or df.fanduel_id.duplicated().any():
            raise ValueError('Missing or duplicate IDs/names')
    def prepare(df):
        x=df[['fanduel_id','name']].copy()
        x['suffix']=x.fanduel_id.astype(str).str.extract(r'^\d+-(\d+)$')[0]
        if x.suffix.isna().any(): raise ValueError('Unexpected ID format')
        if x.suffix.duplicated().any(): raise ValueError('Duplicate suffix within slate')
        x['normalized_name']=x.name.astype(str).str.strip().str.casefold()
        return x
    a,b=prepare(left),prepare(right)
    joined=a.merge(b,on='suffix',how='inner',suffixes=('_left','_right'),validate='one_to_one')
    joined['name_agrees']=joined.normalized_name_left.eq(joined.normalized_name_right)
    joined['review_status']=joined.name_agrees.map({True:'candidate_same_player_not_verified',False:'conflicting_name_do_not_merge'})
    return joined
