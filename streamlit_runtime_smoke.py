"""Exercise the recovered DFS app using Streamlit's real widget runtime."""
from collections import Counter
from importlib.util import find_spec
from itertools import combinations
from pathlib import Path
import os
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app_staging.py'
DB = ROOT.parent / 'nov20_player_history.sqlite'
RESEARCH = ROOT / 'data' / 'nov20_research_v33_full.csv'


def main():
    if find_spec('streamlit') is None:
        print('BLOCKED: Streamlit is not installed. Install requirements.txt.')
        return 2

    import pandas as pd
    from streamlit.testing.v1 import AppTest
    from history_backup import sha256
    from pool_coverage import audit_pool

    expected_slots = Counter(['PG', 'SG', 'SF', 'PF', 'C', 'G/F', 'F/C', 'UTIL', 'UTIL'])
    research = pd.read_csv(RESEARCH, low_memory=False)
    contest = research[['fanduel_id', 'fanduel_name', 'salary', 'injury_flag', 'roster_eligibility', 'position']]
    reconciled = pd.read_csv(ROOT / 'nov20_reconciled_example.csv')
    pool = audit_pool(contest, reconciled)
    original_hash = sha256(DB)

    def check_portfolio(app, pool_by_name):
        assert not app.exception and not app.error, (app.exception, app.error)
        lineups = [table.value for table in app.dataframe if {'slot', 'salary', 'player'} <= set(table.value)]
        check_lineups(lineups, pool_by_name)

    def check_lineups(lineups, pool_by_name):
        assert len(lineups) == 4
        for lineup in lineups:
            assert Counter(lineup.slot) == expected_slots
            assert lineup.player.nunique() == 9
            assert lineup.salary.sum() <= 60000
            for row in lineup.itertuples():
                player = pool_by_name.loc[row.player]
                assert row.salary == player.salary
                assert str(player.injury_flag).upper() != 'O'
                assert row.adjusted_fd_points > 0
                assert row.slot in player.roster_eligibility if row.slot in {'G/F', 'F/C', 'UTIL'} else row.slot in player.position.split('/')
        for left, right in combinations(lineups, 2):
            assert len(set(left.player) & set(right.player)) <= 7

    with patch.dict(os.environ, {'DFS_HISTORY_DB': str(DB)}):
        app = AppTest.from_file(str(APP), default_timeout=120).run()
        assert not app.exception
        metrics = {item.label: int(item.value) for item in app.metric}
        assert metrics['Research rows'] == metrics['Historical research rows'] == 247
        assert metrics['Rows with verified actual FD points'] == 17
        print('PASS: bundled research and read-only SQLite rendered with 247 rows and 17 actuals')

        app.button(key='research_opt').click().run()
        check_portfolio(app, contest.set_index('fanduel_name'))
        print('PASS: four legal research lineups from the bundled slate')

        app.button(key='research_scenarios').click().run()
        assert not app.exception and not app.error
        scenario_teams = [table.value for table in app.dataframe if 'slot' in table.value]
        assert len(scenario_teams) == 12
        for offset in range(0, len(scenario_teams), 4):
            check_lineups(scenario_teams[offset:offset + 4], contest.set_index('fanduel_name'))
        print('PASS: three GitHub sensitivity modes each returned four legal lineups')

        app.file_uploader(key='base').upload('invalid.csv', b'name\nMissing Fields\n', 'text/csv').run()
        assert not app.exception and any('Missing columns' in item.value for item in app.error)
        assert not any('Lineup optimizer' == item.value for item in app.subheader)
        app.file_uploader(key='base').clear().upload('reconciled.csv', pool.to_csv(index=False).encode(), 'text/csv').run()
        assert not app.exception and not app.error
        assert next(item for item in app.metric if item.label == 'Players in reconciliation').value == '247'
        output = next(table.value for table in app.dataframe if 'minutes_method' in table.value)
        assert len(output) == 247
        assert output.adjusted_fd_points.isna().any()
        assert output.loc[pool.projected_fd_points.isna(), 'adjusted_fd_points'].isna().all()
        app.button(key='base_opt').click().run()
        check_portfolio(app, contest.set_index('fanduel_name'))
        print('PASS: malformed CSV rejected, all 247 reconciled rows displayed, missing projections preserved, and four legal CSV lineups generated')

    with patch.dict(os.environ, {'DFS_HISTORY_DB': str(DB.with_name('missing-history.sqlite'))}):
        app = AppTest.from_file(str(APP), default_timeout=120).run()
        assert not app.exception
        assert any('History database unavailable' in item.value for item in app.caption)
        assert not any(item.label == 'Historical research rows' for item in app.metric)
    assert sha256(DB) == original_hash
    print('PASS: missing database fallback and unchanged SQLite checksum')
    return 0


if __name__ == '__main__':
    sys.exit(main())
