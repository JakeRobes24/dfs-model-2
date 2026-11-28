from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from model import SLOTS
from nba_recovered_contest_review import load_recovered_contest, verify_recovered_lineups
from slate_import import reconcile_exports
from test_nba_csv_pipeline_integration import synthetic_exports


def test_recovery_checks_original_digests_and_authoritative_lineup_constraints():
    contest, daily = synthetic_exports()
    pool, contest_id, _ = reconcile_exports(contest, daily)
    reviewed = pool.assign(eligible=True, adjusted_fd_points=pool.projected_fd_points)
    lineup = reviewed.iloc[[0, 1, 2, 3, 4, 5, 9, 7, 8]][['fanduel_id', 'salary', 'adjusted_fd_points']].assign(
        lineup=1, slot=SLOTS)
    files = {'FanDuel.csv': contest, 'DAILY.csv': daily,
             'reviewed_pool.csv': reviewed.to_csv(index=False).encode(),
             'four_lineups.csv': lineup.to_csv(index=False).encode()}
    manifest = {'contest': contest_id, 'files': {name: {'bytes': len(data),
                'sha256': sha256(data).hexdigest()} for name, data in files.items()}}

    def archive(contents):
        result = BytesIO()
        with ZipFile(result, 'w') as zipped:
            zipped.writestr('manifest.json', json.dumps(manifest))
            for name, data in contents.items():
                zipped.writestr(name, data)
        return result

    meta, original, saved_pool, saved_lineup = load_recovered_contest(archive(files))
    verify_recovered_lineups(original, saved_pool, saved_lineup, contest_id=meta['contest'])
    slots = saved_lineup.copy()
    slots.loc[slots.index[-1], 'slot'] = 'PG'
    with pytest.raises(ValueError, match='nine unique'):
        verify_recovered_lineups(original, saved_pool, slots, contest_id=contest_id)
    with pytest.raises(ValueError, match='metadata'):
        verify_recovered_lineups(original, saved_pool.assign(team='BOS'), saved_lineup, contest_id=contest_id)
    with pytest.raises(ValueError, match='checksum'):
        load_recovered_contest(archive(dict(files, **{'DAILY.csv': daily+b' '})))
