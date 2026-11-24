"""Real Streamlit widget-runtime smoke test without private history or live requests.

All player data and source responses are explicitly synthetic.
"""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from slate_import import reconcile_exports
from slate_research import DFF, PROPSIMS, ET
from test_nba_csv_pipeline_integration import synthetic_exports

ROOT = Path(__file__).resolve().parent


def test_current_site_import_review_and_optimize(monkeypatch):
    for key in ('DFS_HISTORY_DB','DFS_HISTORY_SNAPSHOT_URL','DFS_HISTORY_SNAPSHOT_TOKEN',
                'DFS_HISTORY_INTAKE_TOKEN','DFS_HISTORY_OWNER_EMAIL'):
        monkeypatch.delenv(key, raising=False)
    contest, daily = synthetic_exports()
    pool, _, _ = reconcile_exports(contest,daily)
    target = (datetime.now(ET).date()-timedelta(days=1)).isoformat()

    def research(slate, checked_at):
        points = [dict(player=row.fanduel_name, team=row.team, game=row.game,
                       source=source, points=row.projected_fd_points+delta,
                       observed_at=checked_at.isoformat())
                  for row in pool.itertuples() for source,delta in [(DFF,2),(PROPSIMS,4)]]
        return [],points,[('Synthetic test sources','Fixture only')]

    with patch('site_ui.public_research',side_effect=research), patch(
            'site_ui.public_rotations',return_value=([],'Synthetic test: no rotation rows')):
        app = AppTest.from_file(str(ROOT/'app_staging.py'),default_timeout=120).run()
        assert not app.exception
        app.file_uploader(key='slate_contest').upload(f'{target}-fixture.csv',contest,'text/csv')
        app.file_uploader(key='slate_daily').upload('fixture-daily.csv',daily,'text/csv')
        app.run()
        assert not app.exception and not app.error
        assert any('60/40 blend applied: 36/36' in x.value for x in app.caption)
        table = next(t.value for t in app.dataframe if {'Player','Adjusted FD','DAILY FD'} <= set(t.value))
        assert len(table)==36
        assert table['Adjusted FD'].tolist()==pytest.approx((table['DAILY FD']+1.2).tolist())
        app.button(key='slate_optimize').click().run()
        assert not app.exception and not app.error
        comparison = next(t.value for t in app.dataframe if 'Best distinct alternative FD' in t.value)
        assert len(comparison)==4
        assert any('Lineup 1 ·' in x.label for x in app.expander)
        app.radio(key='site_view').set_value('Post-slate review').run()
        assert not app.exception
        assert any('Sign in with the authorized account' in x.value for x in app.info)
