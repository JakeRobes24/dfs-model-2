"""Research-only total-score blend following independently corroborated minutes.

Do not multiply the independent point estimates by a second minutes adjustment.
Require agreement in points, corroborated reviewed minutes, and a same-source
points/minutes pair near reviewed minutes. This is not a validated live policy.
"""
import json
import math

import pandas as pd

FIELDS = ('projection_sources_json','projection_source_count','projection_source_spread',
          'independent_fd_points','minutes_method','adjusted_minutes','adjusted_fd_points',
          'eligible','injury_flag','prelock_status','blend_status')


def reviewed_minutes_shadow(pool):
    if not set(FIELDS) <= set(pool) or not pool.fanduel_id.is_unique:
        raise ValueError('Use a unique reviewed full pool with source provenance.')
    output = []
    for r in pool.itertuples():
        row = {'fanduel_id':r.fanduel_id,'shadow_combined_fd':None,
               'shadow_combined_status':'Unsupported or excluded'}
        if (str(r.eligible).lower() != 'true' or str(r.injury_flag).upper() in {'O','OUT','Q','D','GTD'}
                or str(r.prelock_status).lower() in {'out','inactive','suspended','questionable','doubtful'}
                or r.minutes_method != 'prelock_independent_consensus'
                or r.blend_status != 'Minutes/status adjustment takes priority'):
            output.append(row)
            continue
        try:
            base, minutes, consensus, count = map(float,(r.adjusted_fd_points,r.adjusted_minutes,
                                                          r.independent_fd_points,r.projection_source_count))
            if not all(map(math.isfinite,(base,minutes,consensus,count))) or not (base>0 and 0<minutes<=48 and count>=2):
                raise ValueError
            estimates = json.loads(r.projection_sources_json)
            if not isinstance(estimates,list) or len(estimates)!=count:
                raise ValueError
            families = {e['family'] for e in estimates}
            points = [float(e['points']) for e in estimates]
            weights = [float(e['weight']) for e in estimates]
            if (len(families)!=count or not all(families) or
                    not all(math.isfinite(p) and 0<p<=150 for p in points) or
                    not all(math.isfinite(w) and w>0 for w in weights) or max(points)-min(points)>=5):
                raise ValueError
            if not math.isclose(sum(p*w for p,w in zip(points,weights))/sum(weights),consensus,abs_tol=1e-6):
                raise ValueError
            paired = [float(e['paired_minutes']) for e in estimates if e.get('paired_minutes') is not None]
            if not paired or not all(math.isfinite(m) and 0<m<=48 and abs(m-minutes)<=2 for m in paired):
                raise ValueError
            row.update(shadow_combined_fd=.6*base+.4*consensus,
                       shadow_combined_status='Exploratory total-score blend')
        except (ValueError,TypeError,KeyError,OverflowError):
            pass
        output.append(row)
    return pd.DataFrame(output)
