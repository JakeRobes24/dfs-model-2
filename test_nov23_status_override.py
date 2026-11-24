"""Guard stale OUT corrections without inventing projections."""
import numpy as np
import pandas as pd
import pytest
from prelock import apply_prelock

def inputs(status="available", official=True, at="2026-11-23T18:50:00-05:00"):
    pool=pd.DataFrame([dict(fanduel_id="137108-84680", injury_flag="O",
        eligible=False, adjusted_minutes=0., adjusted_fd_points=0., fppm=1.35,
        projected_minutes=24.55, minutes_method="contest_out", confidence="excluded")])
    evidence=pd.DataFrame([dict(fanduel_id="137108-84680", source="official report",
        independent_group="nba", observed_at=at, official=official, status=status,
        starter="", role="", minutes=np.nan)])
    return pool,evidence

def test_fresh_official_available_restores_baseline():
    p,e=inputs()
    r,_=apply_prelock(p,e,"2026-11-23T18:55:00-05:00")
    assert r.eligible.iloc[0]
    assert r.adjusted_fd_points.iloc[0]==pytest.approx(24.55*1.35)
    assert r.injury_flag.iloc[0]=="O"

@pytest.mark.parametrize("status,official,at",[
    ("available",False,"2026-11-23T18:50:00-05:00"),
    ("available",True,"2026-11-23T18:56:00-05:00"),
    ("available",True,"2026-11-23T08:00:00-05:00"),
    ("questionable",True,"2026-11-23T18:50:00-05:00"),
    ("out",True,"2026-11-23T18:50:00-05:00"),
])
def test_unsafe_override_rejected(status,official,at):
    p,e=inputs(status,official,at)
    r,_=apply_prelock(p,e,"2026-11-23T18:55:00-05:00")
    assert not r.eligible.iloc[0]

def test_missing_baseline_not_invented():
    p,e=inputs();p["projected_minutes"]=np.nan;p["fppm"]=np.nan
    r,_=apply_prelock(p,e,"2026-11-23T18:55:00-05:00")
    assert r.eligible.iloc[0]
    assert pd.isna(r.adjusted_fd_points.iloc[0])
