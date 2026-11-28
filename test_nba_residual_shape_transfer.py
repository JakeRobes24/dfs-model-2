from datetime import date
import pytest
from nba_residual_shape_transfer import transfer_shapes

DAY=date(2026,11,28)

def fixture():
    h=[dict(date=f'2026-11-{d:02d}',id=str(i),minutes=m,center=30,actual=y)
       for d in (20,21,22) for i,(m,y) in enumerate([(15,20),(25,34),(35,45)])]
    r=[dict(date='2026-11-28',id='137300-1',minutes=30,center=40,actual=45)]
    return h,r

def test_same_mean_and_no_target_outcome_in_shape():
    h,r=fixture()
    rows=transfer_shapes(h,r,cutoff=DAY,minimum_rows=3)
    assert len(rows)==3
    assert all(x['mean_bias']==pytest.approx(-5) for x in rows)
    changed=transfer_shapes(h,[dict(r[0],actual=99)],cutoff=DAY,minimum_rows=3)
    for a,b in zip(rows,changed):
        assert a['width']==pytest.approx(b['width'])
        assert a['center']==b['center']
        assert a['actual']!=b['actual']

def test_chronology_and_exact_identity_fail_closed():
    h,r=fixture()
    for invalid in (h+[dict(h[0],date='2026-11-28')],h+[h[0]]):
        with pytest.raises(ValueError):
            transfer_shapes(invalid,r,cutoff=DAY,minimum_rows=3)
    with pytest.raises(ValueError):
        transfer_shapes(h,r+r,cutoff=DAY,minimum_rows=3)
    with pytest.raises(ValueError):
        transfer_shapes(h,r,cutoff=DAY)

def test_missing_band_falls_back_to_raw_on_identical_support():
    h,r=fixture()
    h=[dict(x,minutes=15) for x in h]
    rows=transfer_shapes(h,r,cutoff=DAY,minimum_rows=3)
    assert not rows[-1]['band_supported']
    assert rows[-1]['width']==pytest.approx(rows[0]['width'])
    assert rows[-1]['crps']==pytest.approx(rows[0]['crps'])
