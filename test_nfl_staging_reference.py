from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from test_nfl_daily_audit import OFF, export


def test_staging_prop_sims_result_is_bound_to_uploaded_inputs_and_selected_week(monkeypatch):
    contest = ('Id,Nickname,Position,Roster Position,Salary,Team,Game,Injury Indicator\n'
               '136799-1,Dak Prescott,QB,QB,8200,DAL,DAL@NYG,')
    calls = []

    def reference(audit, **kwargs):
        calls.append((audit, kwargs))
        return dict(observed_at='2026-11-27T03:00:00Z', coverage=dict(contest_matched_rows=1, fresh_rows=1),
                    rows=[dict(player='Dak Prescott', game='DAL@NYG', daily_fd=20.8,
                               median_fd=21, p85_fd=29)])

    monkeypatch.setattr('nfl_public_projection_reference.collect_propsims_reference', reference)
    monkeypatch.setattr('nfl_public_projection_reference.collect_daily_tips',
                        lambda audit: dict(observed_at='2026-11-27T03:00:00Z',
                                           rows=[dict(player='Dak Prescott', game='DAL@NYG',
                                                      daily_fd=20.8, reference_fd=21)]))
    app = AppTest.from_file(str(Path(__file__).with_name('app_nfl_staging.py'))).run()
    app.text_input[0].set_value('136799')
    app.file_uploader[0].upload('contest.csv', contest.encode(), 'text/csv')
    app.file_uploader[1].upload('daily.csv', export(OFF).encode(), 'text/csv')
    app.run()
    next(w for w in app.number_input if w.label == 'NFL season').set_value(2026)
    week = next(w for w in app.number_input if w.label == 'Regular-season week')
    week.set_value(12)
    next(w for w in app.date_input if w.label == 'PropSims Sunday slate date (ET)').set_value(date(2026, 11, 29))
    next(w for w in app.text_input if w.label.startswith('Reference cutoff')).set_value('2026-11-29T18:00:00Z').run()
    next(w for w in app.button if w.label == 'Check PropSims').click().run()
    assert not app.exception
    assert calls[0][0]['contest_id'] == '136799'
    assert any('85th percentile FD' in table.value for table in app.dataframe)
    next(w for w in app.number_input if w.label == 'Regular-season week').set_value(13).run()
    assert not app.exception
    assert not any('85th percentile FD' in table.value for table in app.dataframe)
    assert len(calls) == 1
    app.button(key='nfl_daily_tips').click().run()
    assert not app.exception and any('Reference FD' in table.value for table in app.dataframe)
    app.file_uploader[1].upload('new-daily.csv', export(OFF).replace('20.8', '21.8').encode(), 'text/csv').run()
    assert not any('Reference FD' in table.value for table in app.dataframe)


def test_nfl_staging_archive_download_and_restore_are_scoped_to_original_inputs():
    import json

    from nfl_review_archive import restore_nfl_review_archive
    from test_nfl_reviewed_candidates import fixture

    contest, daily, kwargs = fixture()
    kwargs.pop('contest_id')
    kwargs.pop('single_game')
    bundle = json.dumps(kwargs).encode('utf-8')
    app = AppTest.from_file(str(Path(__file__).with_name('app_nfl_staging.py'))).run()
    app.text_input[0].set_value('137123')
    app.file_uploader[0].upload('contest.csv', contest, 'text/csv')
    app.file_uploader[1].upload('daily.csv', daily, 'text/csv').run()
    next(w for w in app.file_uploader if w.label == 'Reviewed candidate bundle JSON').upload(
        'review.json', bundle, 'application/json').run()
    app.button(key='nfl_freeze_review').click().run()
    assert not app.exception and not app.error
    assert any(button.label == 'Download NFL review archive' for button in app.get('download_button'))
    scope, raw, manifest = app.session_state['nfl_review_snapshot']
    assert restore_nfl_review_archive(raw)[2]
    app.run()
    assert app.session_state['nfl_review_snapshot'] == (scope, raw, manifest)
    app.file_uploader(key='nfl_review_recovery').upload('saved.zip', raw, 'application/zip').run()
    assert any('reproduced from original inputs' in status.value for status in app.success)
    app.file_uploader[1].upload('new.csv', daily + b'\n', 'text/csv').run()
    assert not any('Download NFL review archive' == button.label for button in app.get('download_button'))
