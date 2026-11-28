from datetime import date,datetime,timezone
import pytest
from nba_next_day_preview import preview_next_day
from slate_research import _parse_propsims_board
DAY=date(2026,11,27)
NOW=datetime(2026,11,26,12,tzinfo=timezone.utc)
SCHEDULE=[dict(awayTeam={'teamTricode':'BOS'},homeTeam={'teamTricode':'NYK'},gameTimeUtc='2026-11-28T00:00:00Z')]
HTML="""<meta charset='utf-8'><h1>NBA DFS projections for Friday, November 27</h1>
<div class="updstamp"><time datetime="2026-11-26T11:00:00Z"></time></div>
<table><tr><td class="player"><a>Alpha Player</a><span class="msub">BOS · PG @ NYK</span></td>
<td data-f="fd_p50" data-v="32">32</td><td data-f="min_p50" data-v="30">30</td></tr></table>""".encode('utf-8')
def house(day,now):
    return ([dict(player='Alpha Player',team='BOS',game='BOS@NYK',minutes=34)],[]),'ok'
def test_live_parser_still_rejects_next_day():
    with pytest.raises(ValueError):_parse_propsims_board(HTML,DAY,NOW)
def test_next_day_preview_exact_match_only():
    r=preview_next_day(DAY,NOW,SCHEDULE,propsims_loader=lambda:HTML,house_loader=house)
    assert r['coverage']['NBA House']['players']==1
    assert r['coverage']['PropSims']['players']==1
    assert r['overlap'][0]['minute_gap']==-4
    assert r['forecasts']['PropSims'][0]['scoring_accepted'] is False
def test_future_publication_and_wrong_schedule_rejected():
    r=preview_next_day(DAY,NOW,SCHEDULE,propsims_loader=lambda:HTML.replace(b'T11:00',b'T13:00'),house_loader=house)
    assert not r['forecasts']['PropSims']
    with pytest.raises(ValueError):preview_next_day(DAY,NOW,SCHEDULE+SCHEDULE,house_loader=house)
def test_duplicate_house_estimates_are_not_votes():
    def duplicate(day,now):
        (rows,_),status=house(day,now)
        return (rows+rows,[]),status
    r=preview_next_day(DAY,NOW,SCHEDULE,propsims_loader=lambda:HTML,house_loader=duplicate)
    assert not r['overlap'] and not r['forecasts']['NBA House']
