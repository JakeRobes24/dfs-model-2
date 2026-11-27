from datetime import date

import pandas as pd
import pytest

from nba_possession_validation import compare_possession_forecasts, official_possession_rows
from nfl_first_read_validation import charted_target_totals
from nfl_public_projection_reference import compare_daily_tips


def test_nfl_chart_counts_only_receiver_directed_primary_reads():
    plays = pd.DataFrame(dict(game_id='G', play_id=[1, 2, 3], season_type='REG', game_date='2026-09-12',
                              posteam='NYJ', play_type=['pass', 'pass', 'run'], pass_attempt=[1, 1, 0],
                              two_point_attempt=0, receiver_player_id=['A', 'B', None]))
    chart = pd.DataFrame(dict(nflverse_game_id='G', nflverse_play_id=[1, 2, 3],
                              read_thrown=['0', '1', '0'], date_pulled='2026-09-14T10:00:00Z'))
    teams, players = charted_target_totals(plays, chart)
    assert teams.iloc[0].primary_targets == 1 and teams.iloc[0].qualified
    assert players.set_index('receiver_player_id').player_primary.to_dict() == {'A': 1, 'B': 0}
    duplicated = pd.concat([chart, chart.iloc[:1]])
    assert not charted_target_totals(plays, duplicated)[0].iloc[0].qualified


def test_nba_official_box_is_joined_by_exact_ids_and_minutes():
    counting = dict(minutes='30:00', points=20, reboundsTotal=5, assists=4, steals=1, blocks=0, turnovers=2)
    advanced = dict(minutes='30:00', possessions=60, usagePercentage=.25)
    schedule = ('2026-11-20', '001', 'BOS', 'NYK')

    def box(prefix, stats):
        return {prefix: dict(gameId='001',
                             awayTeam=dict(teamId=1, teamTricode='BOS', players=[dict(personId=22, statistics=stats)]),
                             homeTeam=dict(teamId=2, teamTricode='NYK', players=[]))}

    adv, trad = box('boxScoreAdvanced', advanced), box('boxScoreTraditional', counting)
    row, = official_possession_rows(schedule, adv, trad)
    assert row['fd'] == 33 and row['usage'] == 25 and row['possessions'] == 60
    changes = box('boxScoreTraditional', dict(counting, minutes='29:00'))
    assert not official_possession_rows(schedule, adv, changes)
    with pytest.raises(ValueError, match='schedule'):
        official_possession_rows(('2026-11-20', '002', 'BOS', 'NYK'), adv, trad)


def test_nba_missing_prior_scheduled_team_game_breaks_the_window():
    schedule = [(date(2026, 11, i).isoformat(), str(i), 'BOS', 'NYK') for i in range(1, 7)]
    rows = pd.DataFrame([dict(date=day, game_id=pid, team='BOS', nba_id='202',
                              minutes=30, fd=float(pid)*2, possessions=60, usage=27)
                         for day, pid, *_ in schedule])
    reviewed = compare_possession_forecasts(rows, schedule)
    assert len(reviewed) == 2
    assert reviewed.baseline_fd_error.equals(reviewed.possession_fd_error)
    assert compare_possession_forecasts(rows.drop(1), schedule).empty
    duplicate = pd.concat([rows, rows.iloc[[4]]], ignore_index=True)
    with pytest.raises(ValueError, match='duplicate NBA player-game'):
        compare_possession_forecasts(duplicate, schedule)
    conflicting = duplicate.copy()
    conflicting.loc[len(conflicting)-1, 'fd'] = 99.
    with pytest.raises(ValueError, match='duplicate NBA player-game'):
        compare_possession_forecasts(conflicting, schedule)


def test_daily_tips_requires_exact_contest_id_and_matching_details():
    headers = ''.join(f'<th>{x}</th>' for x in ('Player','Pos','Team','Opp','Salary','Proj','Value','FD ID'))
    cells = ''.join(f'<td>{x}</td>' for x in ('Provider Name','WR','NYJ','BUF','$5000','13','2.6','200-1'))
    html = f'<table><thead><tr>{headers}</tr></thead><tbody><tr>{cells}</tr></tbody></table>'
    player = dict(player_id='200-1', player='Contest Name', team='NYJ', game='NYJ@BUF', positions=['WR'],
                  status='', salary=5000, projection_fd=12)
    audit = dict(players=[player], contest_id='200', single_game=False, contest_sha256='a', daily_sha256='b')
    comparison = compare_daily_tips(html, audit)
    assert comparison['published_at'] is None and comparison['rows'][0]['reference_fd'] == 13
    assert not compare_daily_tips(html.replace('$5000', '$5100'), audit)['rows']
    with pytest.raises(ValueError, match='different contest'):
        compare_daily_tips(html.replace('200-1', '201-1'), audit)
