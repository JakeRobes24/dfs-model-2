from datetime import date

import pandas as pd

from nba_archive_training import load_prior_replays, prior_contests
from slate_replay_capture import capture_pool


def frozen(day, hour):
    pool = pd.DataFrame({
        'fanduel_id': ['123-1', '123-2'], 'fanduel_name': ['A', 'B'],
        'team': 'BOS', 'game': 'BOS@NYK', 'eligible': True,
        'prelock_status': '', 'prelock_starter': '', 'projected_minutes': 30,
        'projected_fd_points': 25, 'adjusted_minutes': 31, 'adjusted_fd_points': 28,
    })
    schedule = [dict(awayTeam={'teamTricode': 'BOS'}, homeTeam={'teamTricode': 'NYK'},
                     gameTimeUtc=f'{day}T23:00:00Z')]
    return capture_pool(pool, pd.DataFrame(), schedule, day, f'{day}T{hour}:00:00Z',
                        ('a' * 64, 'b' * 64))


def test_prior_contests_excludes_target_and_prefers_broadest_per_day():
    history = pd.DataFrame({
        'slate_date': ['2026-11-22'] * 4 + ['2026-11-23', '2026-11-24', 'bad'],
        'fanduel_id': ['123-1', '123-2', '456-1', '123-2', '789-1', '999-1', 'invalid'],
    })
    assert prior_contests(history, date(2026, 11, 24)) == [
        (date(2026, 11, 23), '789'), (date(2026, 11, 22), '123')]


def test_archive_loader_chooses_latest_valid_capture_and_official_outcomes(monkeypatch):
    day = date(2026, 11, 22)
    target = date(2026, 11, 23)
    old, newest, posttip = (frozen(day, hour) for hour in ['18', '22', '23'])
    newest['adjusted_fd_points'] = 32
    history = pd.DataFrame({'slate_date': str(day), 'fanduel_id': ['123-1', '123-2']})
    versions = {'z-old': old, 'a-new': newest, 'posttip': posttip}
    calls = []
    def list_packets(token, day_arg, contest):
        assert (day_arg, contest) == (day, '123')
        return 'commit', 'folder', list(versions)
    def load_packet(token, commit, folder, version):
        return versions[version], None
    def boxes(day_arg, games):
        calls.append((day_arg, games))
        return ['official']
    def compare(pool, day_arg, supplied, recorded):
        assert supplied == ['official'] and recorded == {}
        assert pool.adjusted_fd_points.eq(32).all()
        return pd.DataFrame({
            'fanduel_id': pool.fanduel_id, 'outcome': ['Played', 'Did not play'],
            'nba_actual_minutes': [31, None], 'nba_fd_points': [34, None],
            'nba_source': ['NBA box', 'NBA box'], 'recorded_fd_points': [None, None],
        }), {'BOS/NYK'}
    monkeypatch.setattr('nba_archive_training.compare_results', compare)
    replay, report = load_prior_replays(history, target, 'token', list_packets=list_packets,
                                       load_packet=load_packet, final_boxes=boxes)
    assert calls == [(day, {'BOS/NYK'})]
    assert replay.verified_outcome.tolist() == ['played', 'did_not_play']
    assert replay.daily_points.eq(25).all()
    assert replay.adjusted_fd_points.eq(32).all()
    assert report.loc[0, 'version'] == 'a-new' and report.loc[0, 'played_rows'] == 1

    # No training from incomplete final games, ambiguous latest saves or excess versions.
    monkeypatch.setattr('nba_archive_training.compare_results',
                        lambda *args: (pd.DataFrame(), set()))
    assert load_prior_replays(history, target, 'token', list_packets=list_packets,
                             load_packet=load_packet, final_boxes=boxes)[0].empty
    calls.clear()
    versions['conflict'] = newest.assign(adjusted_fd_points=33)
    assert load_prior_replays(history, target, 'token', list_packets=list_packets,
                             load_packet=load_packet, final_boxes=boxes)[0].empty
    assert not calls
    assert load_prior_replays(history, target, 'token', version_limit=1,
                             list_packets=list_packets, load_packet=load_packet,
                             final_boxes=boxes)[0].empty
    assert not calls
