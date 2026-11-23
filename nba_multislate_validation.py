"""Read-only multi-slate evaluation of immutable NBA frozen replay archives.

Never changes projections, optimizer objectives, or production release gates.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from nba_projection_review import compare_frozen_projections


def evaluate_archives(paths):
    """Require distinct, fully final archived slates and report paired MAE by slate."""
    paths = [Path(path) for path in paths]
    if not paths:
        raise ValueError('Provide at least one frozen replay archive.')
    seen = set()
    records = []
    for path in paths:
        with ZipFile(path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            if (manifest.get('status') != 'reviewed'
                    or manifest.get('verified_final_games') != manifest.get('contest_games')
                    or not isinstance(manifest.get('contest_games'), int)
                    or manifest['contest_games'] < 1):
                raise ValueError(f'{path}: replay is not fully verified and final.')
            day = str(manifest.get('slate_date', ''))
            contest = str(manifest.get('contest_id', ''))
            if (not day or not contest.isdigit() or pd.isna(pd.to_datetime(day, errors='coerce'))
                    or (day, contest) in seen):
                raise ValueError(f'{path}: missing or repeated slate identity.')
            seen.add((day, contest))
            replay = pd.read_csv(archive.open('player_replay.csv'),
                                 dtype={'fanduel_id': str})
        if (replay.empty or replay.fanduel_id.isna().any() or not replay.fanduel_id.is_unique
                or not replay.fanduel_id.str.fullmatch(contest + r'-[0-9]+').all()):
            raise ValueError(f'{path}: replay player IDs must be distinct and belong to the archived contest.')
        comparison = compare_frozen_projections(replay)
        for _, metric in comparison.loc[comparison['Sample'].eq('All paired players')].iterrows():
            count = int(metric['Paired players'])
            records.append({
                'slate_date': day, 'contest_id': contest,
                'metric': metric['Metric'], 'paired_players': count,
                'eligible_verified_outcomes': int(metric['Eligible with verified outcome']),
                'daily_mae': metric['DAILY MAE'],
                'adjusted_mae': metric['Adjusted MAE'],
                'mae_improvement': metric['MAE improvement'],
            })
    by_slate = pd.DataFrame(records).sort_values(['slate_date', 'contest_id', 'metric']).reset_index(drop=True)
    summary = []
    for metric, rows in by_slate.groupby('metric', sort=True):
        paired = rows.loc[rows.paired_players.gt(0)].copy()
        n = int(paired.paired_players.sum())
        if n:
            baseline = float(np.average(paired.daily_mae, weights=paired.paired_players))
            adjusted = float(np.average(paired.adjusted_mae, weights=paired.paired_players))
        else:
            baseline = adjusted = float('nan')
        summary.append({
            'metric': metric, 'archived_slates': len(rows),
            'slates_with_pairs': len(paired), 'paired_players': n,
            'weighted_daily_mae': baseline, 'weighted_adjusted_mae': adjusted,
            'weighted_mae_improvement': baseline - adjusted,
            'slates_adjusted_better': int(paired.mae_improvement.gt(0).sum()),
            'slates_adjusted_worse': int(paired.mae_improvement.lt(0).sum()),
            'evidence_status': 'descriptive_only_no_release_authorization',
        })
    return by_slate, pd.DataFrame(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+', type=Path)
    args = parser.parse_args()
    by_slate, summary = evaluate_archives(args.archives)
    print(by_slate.to_csv(index=False))
    print(summary.to_csv(index=False))


if __name__ == '__main__':
    main()
