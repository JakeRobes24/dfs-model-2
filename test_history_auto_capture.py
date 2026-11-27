"""Controlled owner archive runtime tests; no production credentials or writes."""
from datetime import datetime, timezone
from io import StringIO
import hashlib
import json
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

NOW = datetime(2026,11,24,20,0,tzinfo=timezone.utc)
OWNER = dict(email='owner@example.org',email_verified=True,is_logged_in=True)
ENV = dict(DFS_HISTORY_OWNER_EMAIL='owner@example.org',DFS_HISTORY_INTAKE_TOKEN='fixture-only')
APP = """
import pandas as pd
from datetime import date
from history_intake_ui import render_slate_archive
from model import optimize
from slate_import import reconcile_exports
from slate_research import historical_context, score_slate, ET
from datetime import datetime
from test_nba_csv_pipeline_integration import synthetic_exports
contest,daily = synthetic_exports()
pool,_,_ = reconcile_exports(contest,daily)
day = date(2026,11,24)
scored,audit = score_slate(pool,historical_context(pool,pd.DataFrame(),[],day),[],[],
                           datetime(2026,11,24,15,0,tzinfo=ET))
lineups = optimize(scored,number=4,max_overlap=7)
render_slate_archive(scored,slate_date=day,generated_lineups=lineups,
                     replay_inputs=(audit,('a'*64,'b'*64)))
"""
SCHEDULE = [dict(awayTeam={'teamTricode':a},homeTeam={'teamTricode':b},
                 gameTimeUtc='2026-11-24T23:00:00Z',gameStatus=1)
            for a,b in [('ATL','BOS'),('NYK','CHI')]]


def test_owner_auto_capture_retries_exact_bytes_and_deduplicates():
    with patch.dict('os.environ',ENV,clear=True), patch.object(st,'user',OWNER), patch(
            'history_intake_ui.datetime') as clock, patch(
            'history_intake_ui.games_for_date',return_value=SCHEDULE) as schedule, patch(
            'history_intake_ui.submit_reviewed_slate',side_effect=[OSError('uncertain'),None]) as send:
        clock.now.side_effect=lambda tz=None: NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
        app=AppTest.from_string(APP,default_timeout=120).run()
        assert not app.exception
        send.assert_not_called()
        app.checkbox(key='history_auto_capture').check().run()
        assert not app.exception and send.call_count==1
        assert app.session_state['history_prepared_packet'] == send.call_args.args[1:]
        app.run()
        assert not app.exception and send.call_count==2
        assert send.call_args_list[0].args==send.call_args_list[1].args
        _,path,raw=send.call_args.args
        assert path.endswith(hashlib.sha256(raw).hexdigest()+'.json')
        packet=json.loads(raw)
        pool=pd.read_csv(StringIO(packet['research_csv']))
        candidates=pd.read_csv(StringIO(packet['lineups_csv']))
        assert pool.replay_before_full_slate_tip.all() and len(pool)==36
        assert candidates.lineup.nunique()==4
        assert candidates.groupby('lineup').fanduel_id.nunique().eq(9).all()
        app.run()
        assert not app.exception and send.call_count==2 and schedule.call_count==1


def test_auto_capture_blocks_unverified_owner_and_started_game():
    with patch.dict('os.environ',ENV,clear=True), patch.object(st,'user',dict(OWNER,email_verified=False)), patch(
            'history_intake_ui.submit_reviewed_slate') as send:
        app=AppTest.from_string(APP,default_timeout=120).run()
        assert not app.exception and all(w.key!='history_auto_capture' for w in app.checkbox)
        send.assert_not_called()
    with patch.dict('os.environ',ENV,clear=True), patch.object(st,'user',OWNER), patch(
            'history_intake_ui.datetime') as clock, patch(
            'history_intake_ui.games_for_date',return_value=[dict(SCHEDULE[0],gameStatus=2),SCHEDULE[1]]), patch(
            'history_intake_ui.submit_reviewed_slate') as send:
        clock.now.side_effect=lambda tz=None: NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
        app=AppTest.from_string(APP,default_timeout=120).run()
        app.checkbox(key='history_auto_capture').check().run()
        assert not app.exception
        send.assert_not_called()
        assert any('pre-tip timing is not verified' in item.value for item in app.info)
