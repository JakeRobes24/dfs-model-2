import itertools
import pytest
from nba_availability_bounds import availability_bounds


def test_joint_difference_bounds_equal_enumerated_completions():
    rows=[dict(id='1',outcome='played',base=0.,alt=.2),
          dict(id='2',outcome='unknown',base=.1,alt=.4),
          dict(id='3',outcome='unknown',base=.4,alt=.1),
          dict(id='4',outcome='did_not_play',base=0.,alt=.3)]
    result=availability_bounds(rows,('base','alt'),anchor='base')
    differences=[]
    scores=[]
    for a,b in itertools.product((0,1),repeat=2):
        ys=[0,a,b,1]
        errors={f:sum((r[f]-y)**2 for r,y in zip(rows,ys))/4 for f in ('base','alt')}
        differences.append(errors['alt']-errors['base'])
        scores.append(errors['alt'])
    assert result['possible_dnp_rate']==(.25,.75)
    assert result['comparisons']['alt']['lower']==pytest.approx(min(differences))
    assert result['comparisons']['alt']['upper']==pytest.approx(max(differences))
    assert result['forecasts']['alt']['lower']==pytest.approx(min(scores))
    assert result['forecasts']['alt']['upper']==pytest.approx(max(scores))


def test_unknowns_not_converted_to_dnp_and_empty_support():
    rows=[dict(id='1',outcome='unknown',base=0.,alt=.2)]
    result=availability_bounds(rows,('base','alt'),anchor='base')
    assert result['observed_dnp_rate'] is None
    assert result['possible_dnp_rate']==(0.,1.)
    assert result['comparisons']['alt']['direction']=='direction unresolved'
    empty=availability_bounds([],('base','alt'),anchor='base')
    assert empty['forecasts']['alt']['lower'] is None


def test_complete_known_cohort_and_invalid_inputs():
    row=dict(id='1',outcome='did_not_play',base=0.,alt=.2)
    result=availability_bounds([row],('base','alt'),anchor='base')
    assert result['comparisons']['alt']['direction']=='better for every completion'
    for bad in ([row,row],[dict(row,alt=None)],[dict(row,outcome='not listed')]):
        with pytest.raises(ValueError):
            availability_bounds(bad,('base','alt'),anchor='base')
