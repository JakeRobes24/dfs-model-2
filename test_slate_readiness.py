from pathlib import Path
import tempfile

import pandas as pd
import pytest

from history_backup import verify_backup
from history_checkpoint import create_checkpoint
from history_readonly import load_history
from history_recovery import restore_verified
from lineup_challenger import challenge_lineups
from model import consensus, optimize
from prelock import apply_prelock

ROOT = Path(__file__).resolve().parent
AS_OF = '2026-11-21T18:00:00-05:00'


def fixture_pool():
    return pd.read_csv(ROOT / 'nov20_reconciled_example.csv')


def test_prelock_injuries_minutes_and_full_pool_alternative():
    pool = consensus(fixture_pool())
    base = optimize(pool, number=1)
    pid = base.iloc[0].fanduel_id
    target = base.iloc[1].fanduel_id
    cases = [
        (pid, 'NBA injury report', 'nba', '2026-11-21T17:59:00-05:00', True, 'out', '', '', None),
        (target, 'League lineup', 'nba', '2026-11-21T17:55:00-05:00', True, 'available', 'starter', '', None),
        (target, 'Minutes A', 'a', '2026-11-21T17:55:00-05:00', False, '', '', 'primary ball handler', 34),
        (target, 'Minutes B', 'b', '2026-11-21T17:57:00-05:00', False, '', '', '', 36),
        (target, 'Future update', 'nba', '2026-11-21T18:10:00-05:00', True, 'out', '', '', None),
    ]
    columns = 'fanduel_id source independent_group observed_at official status starter role minutes'.split()
    adjusted, audit = apply_prelock(pool, pd.DataFrame(cases, columns=columns), AS_OF)
    assert len(adjusted) == len(pool)
    assert audit.iloc[-1].review == 'After as-of time'
    rows = adjusted.set_index('fanduel_id')
    assert not rows.at[pid, 'eligible']
    assert rows.at[target, 'adjusted_minutes'] == 35
    assert rows.at[target, 'adjusted_fd_points'] == pytest.approx(rows.at[target, 'fppm'] * 35)
    assert rows.at[target, 'prelock_starter'] == 'starter'
    report, summary, alternative = challenge_lineups(adjusted, base)
    assert report.prelock_change.str.contains('status: out').any()
    assert 'ineligible' in summary.iloc[0].issues
    assert len(alternative) == 9 and pid not in set(alternative.fanduel_id)
    assert alternative.salary.sum() <= 60000
    assert summary.iloc[0].alternative_optimal


def test_ceiling_comparison_reports_distinct_ordering_objectives():
    pool = consensus(fixture_pool())
    base = optimize(pool, number=1)
    with pytest.raises(ValueError, match='researched ceiling'):
        challenge_lineups(pool, base, include_ceiling=True)
    pool['ceiling_fd_points'] = pool.adjusted_fd_points + 5
    _, comparison, alternatives = challenge_lineups(pool, base, include_ceiling=True)
    assert list(comparison.objective) == ['adjusted_fd_points', 'ceiling_fd_points']
    for _, lineup in alternatives.groupby('objective'):
        assert len(lineup) == 9 and set(lineup.fanduel_id) != set(base.fanduel_id)


def test_checkpoint_restore_preserves_existing_actuals_and_records_id_candidates():
    source = ROOT.parent / 'nov20_player_history_verified_backup.sqlite'
    sample = pd.read_csv(ROOT / 'data/nov20_research_v33_full.csv', low_memory=False).head(2)
    sample['fanduel_id'] = ['393939-' + sample.iloc[0].fanduel_id.split('-')[1], '393939-999999999']
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        research = directory / 'research.csv'
        sample.to_csv(research, index=False)
        output, _ = create_checkpoint(source, research, '2026-11-21', directory)
        check = output / 'history.sqlite'
        assert verify_backup(check)['tables']['actuals'] == 17
        restore_verified(check, directory / 'restored.sqlite')
        rows, _ = load_history(directory / 'restored.sqlite', '2026-11-21')
        assert len(rows) == 2 and rows.actual_fd_points.isna().all()
        audit = pd.read_csv(output / 'identity_review.csv')
        assert list(audit.identity_status) == ['cross_slate_candidate', 'new_player']


def test_streamlit_upload_to_adjusted_lineup_challenge():
    from streamlit.testing.v1 import AppTest

    source = fixture_pool()
    pool = consensus(source)
    proposed = optimize(pool, number=1)
    evidence = (
        'fanduel_id,source,independent_group,observed_at,official,status,starter,role,minutes\n'
        f"{proposed.iloc[0].fanduel_id},NBA injury report,nba,2026-11-21T17:59:00-05:00,true,out,,,\n"
    )
    app = AppTest.from_file(str(ROOT / 'app_staging.py'), default_timeout=45).run()
    app.file_uploader(key='base').upload('reconciled.csv', source.to_csv(index=False).encode(), 'text/csv').run()
    app.file_uploader(key='prelock_evidence').upload('prelock.csv', evidence.encode(), 'text/csv').run()
    app.text_input(key='prelock_as_of').set_value(AS_OF).run()
    app.file_uploader(key='challenger_proposed').upload(
        'lineup.csv', proposed.to_csv(index=False).encode(), 'text/csv'
    ).run()
    app.button(key='challenger_run').click().run()
    assert not app.exception and not app.error
    comparison = next(table.value for table in app.dataframe if 'alternative_optimal' in table.value)
    assert 'ineligible' in comparison.iloc[0].issues
    assert comparison.iloc[0].alternative_optimal
    app.button(key='base_opt').click().run()
    assert not app.exception and not app.error
    alternatives = [table.value for table in app.dataframe if {'slot', 'fanduel_id'} <= set(table.value)]
    assert len(alternatives) == 4
    assert all(proposed.iloc[0].fanduel_id not in set(lineup.fanduel_id) for lineup in alternatives)
