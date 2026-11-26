from datetime import date,datetime,timezone
import json
from urllib.error import HTTPError,URLError
import pytest
from nba_acquisition_receipt import acquisition_receipt
from slate_research import public_source_failure,get_public_research

@pytest.mark.parametrize("failure,expected",[
    (HTTPError("https://example.org",403,"secret",None,None),"access denied"),
    (HTTPError("https://example.org",429,"secret",None,None),"rate limited"),
    (HTTPError("https://example.org",503,"secret",None,None),"provider server error"),
    (TimeoutError("secret"),"transport error"),
    (URLError("secret"),"transport error"),
    (ValueError("RotoGrinders estimates are stale or not for the current slate"),"freshness or slate date mismatch"),
    (ValueError("RotoGrinders update time unavailable"),"timestamp or date evidence missing"),
    (ValueError("No verifiable public RotoGrinders rows"),"no verifiable public rows"),
    (KeyError("secret"),"data or source format could not be validated")])
def test_safe_failure_categories(failure,expected):
    result=public_source_failure(failure)
    assert result=="Unavailable: "+expected
    assert "secret" not in result

def test_receipt_counts_before_matching_and_keeps_empty_provider_status():
    result=json.loads(acquisition_receipt(date(2026,11,24),datetime(2026,11,24,12,tzinfo=timezone.utc),
        [("PropSims","2 records"),("RotoGrinders","Unavailable: access denied")],
        [{"source":"P"},{"source":"P"}],[{"source":"P"}]))
    assert result["returned_note_rows"]=={"P":2}
    assert result["returned_point_rows"]=={"P":1}
    assert result["status"][1]["result"]=="Unavailable: access denied"
    assert "not provider publication time" in result["warning"]

def test_receipt_refuses_naive_or_duplicate_status():
    with pytest.raises(ValueError):
        acquisition_receipt(date(2026,11,24),"2026-11-24T12:00:00",[],[],[])
    with pytest.raises(ValueError):
        acquisition_receipt(date(2026,11,24),"2026-11-24T12:00:00Z",[("A","x"),("A","y")],[],[])
