import pandas as pd
from cross_slate_identity import audit

def test_matches_and_conflicts():
    a=pd.DataFrame({'fanduel_id':['111-1','111-2'],'name':['A Player','B Player']})
    b=pd.DataFrame({'fanduel_id':['222-1','222-2'],'name':['A Player','C Player']})
    x=audit(a,b)
    assert len(x)==2 and x.name_agrees.sum()==1
    assert x.review_status.tolist()==['candidate_same_player_not_verified','conflicting_name_do_not_merge']

def test_reject_duplicate():
    a=pd.DataFrame({'fanduel_id':['111-1','111-1'],'name':['A','B']})
    try: audit(a,a)
    except ValueError: return
    raise AssertionError('Duplicate IDs accepted')
if __name__=='__main__':
    test_matches_and_conflicts();test_reject_duplicate();print('Cross-slate tests passed')
