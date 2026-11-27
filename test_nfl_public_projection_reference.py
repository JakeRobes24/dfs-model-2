from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

from nfl_public_projection_reference import collect_4for4_reference, parse_4for4_page
import pytest

PAGE = '''<h1>2026 Fantasy Football Projections - FanDuel - RB - Week 12</h1>
<p>Projections as of Wednesday, November 25, 2026 at 7:40 PM EST</p>
<table class="table_4for4"><thead><tr><th>Player</th><th>Team</th><th>Opp</th>
<th>FF Pts</th><th>RuAtt</th></tr></thead><tbody>
<tr><td><a href="/player/james-cook">James Cook</a><small>Injury popup</small></td>
<td>BUF</td><td>KC</td><td>16.3</td><td>18.2</td></tr></tbody></table>'''
OBS = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


def test_public_table_uses_player_link_and_checks_header_date_format():
    published, rows = parse_4for4_page(PAGE, season=2026, week=12, position='RB')
    assert published.isoformat() == '2026-11-25T19:40:00-05:00'
    assert rows[0]['player'] == 'James Cook' and rows[0]['game'] == 'KC@BUF'
    assert rows[0]['components'] == {'rushing_attempts': 18.2}
    for invalid in [PAGE.replace('FanDuel','DraftKings'), PAGE.replace('EST','EDT')]:
        with pytest.raises(ValueError):
            parse_4for4_page(invalid, season=2026, week=12, position='RB')


def test_exact_contest_and_unbackdated_reference():
    def response(request, **kwargs):
        out = BytesIO(PAGE.encode())
        out.geturl = lambda: request.full_url
        return out
    player = dict(player_id='123-91626', player='James Cook III', team='BUF', game='KC@BUF',
                  positions=['RB'], status='', projection_fd=17.9)
    audit = dict(players=[player], contest_id='123', contest_sha256='cont', daily_sha256='daily')
    with patch('nfl_public_projection_reference.urlopen', side_effect=response):
        report = collect_4for4_reference(audit, season=2026, week=12,
                                         cutoff_utc='2026-11-26T17:30:00Z', now=lambda: OBS)
        assert report['rows'][0]['daily_fd'] == 17.9
        assert report['rows'][0]['observed_at'] == OBS.isoformat()
        assert not collect_4for4_reference(audit, season=2026, week=12,
                                          cutoff_utc='2026-11-26T09:00:00Z', now=lambda: OBS)['rows']
        audit['players'] = [dict(player, game='BUF@KC')]
        assert not collect_4for4_reference(audit, season=2026, week=12,
                                          cutoff_utc='2026-11-26T17:30:00Z', now=lambda: OBS)['rows']


def test_propsims_exact_sunday_schedule_and_timestamp():
    from nfl_public_projection_reference import parse_propsims_fanduel

    html = '''<h1>FanDuel projections: Week 12 main slate</h1>
    <time datetime="2026-11-27T01:00:00Z"></time>
    <table id="dfstable"><thead><tr><th>Player</th><th>Salary</th><th>Median</th>
    <th>Ceiling</th><th>Value</th></tr></thead><tbody>
    <tr><td><span class="pn"><a href="/players/sample/">Sample Player</a></span>
    <span class="psub">RB · SF vs SEA</span></td><td>$6000</td>
    <td>12</td><td>19</td><td>2</td></tr></tbody></table>'''
    args = dict(week=12, observed_at='2026-11-27T03:00:00Z')
    rows = parse_propsims_fanduel(html, **args, games={'SEA@SF':'2026-11-29T21:25:00Z'})
    assert len(rows) == 1 and (rows[0]['median_fd'], rows[0]['p85_fd']) == (12, 19)
    wrong_orientation = html.replace('SF vs SEA', 'SF @ SEA')
    assert parse_propsims_fanduel(wrong_orientation, **args, games={'SEA@SF':'2026-11-29T21:25:00Z'}) == []
    assert parse_propsims_fanduel(html, **args, games={}) == []
    assert parse_propsims_fanduel(html, **args, games={'SEA@SF':'2026-11-26T21:25:00Z'}) == []
