import json
import pandas as pd
import pytest
from nba_paired_source_coverage import paired_source_coverage
from slate_research import PROPSIMS, DFF, ROTOGRINDERS

def note(source=PROPSIMS,family="propsims",minutes=25,stamp="2026-11-24T11:00:00Z"):
    return dict(source=source,family=family,points=30,paired_minutes=minutes,observed_at=stamp)

def frame(*records):
    return pd.DataFrame([dict(fanduel_id=f"1-{i}",eligible=True,
                         replay_captured_at_utc="2026-11-24T12:00:00Z",
                         projection_sources_json=json.dumps(r)) for i,r in enumerate(records)])

def test_distinct_families_and_points_only():
    f=frame([note(),note(DFF,"daily-fantasy-fuel",None)],
            [note(),note(ROTOGRINDERS,"rotogrinders")],[])
    r=paired_source_coverage(f)
    s={x["family"]:x for x in r["sources"]}
    assert r["eligible_players"]==3
    assert s["propsims"]["fresh_paired_players"]==2
    assert s["daily-fantasy-fuel"]["points_without_positive_minutes"]==1
    assert s["rotogrinders"]["missing_archived_players"]==2
    assert r["player_pair_coverage"]=={"one_pair":1,"two_or_more_pairs":1,"no_pairs":1}
    assert not r["certified"]

def test_duplicate_and_wrong_family_not_corroboration():
    r=paired_source_coverage(frame([note(),note(),note(ROTOGRINDERS,"propsims")]))
    s={x["family"]:x for x in r["sources"]}
    assert s["propsims"]["ambiguous_players"]==1
    assert s["propsims"]["fresh_paired_players"]==0
    assert r["malformed_records_or_payloads"]==1
    assert r["player_pair_coverage"]=={"no_pairs":1}

@pytest.mark.parametrize("stamp",["2026-11-24T04:00:00Z","2026-11-24T13:00:00Z","2026-11-24T11:00:00"])
def test_invalid_time_excluded(stamp):
    r=paired_source_coverage(frame([note(stamp=stamp)]))
    s={x["family"]:x for x in r["sources"]}
    assert s["propsims"]["invalid_or_stale_players"]==1
    assert r["player_pair_coverage"]=={"no_pairs":1}

def test_invalid_capture_and_duplicate_ids():
    f=frame([note()],[note()])
    f.loc[0,"replay_captured_at_utc"]="2026-11-24T12:01:00Z"
    with pytest.raises(ValueError):paired_source_coverage(f)
    f=frame([note()])
    with pytest.raises(ValueError):paired_source_coverage(pd.concat([f,f]))

def test_malformed_payload_and_ineligible():
    f=frame([note()],[note()])
    f.loc[0,"projection_sources_json"]="bad"
    f.loc[1,"eligible"]=False
    r=paired_source_coverage(f)
    assert r["eligible_players"]==1
    assert r["player_pair_coverage"]=={"unreadable":1}
