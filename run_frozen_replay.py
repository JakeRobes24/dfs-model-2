"""Score a saved pre-tip NBA contest pool after all its official games are final."""
import argparse
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from market_evidence import review_player_props, summarize_player_props
from nba_projection_review import compare_adjustment_methods, compare_frozen_projections
from slate_import import game_code, matchup_key
from slate_replay_capture import build_replay_rows
from slate_results import SOURCE_ERRORS, collect_final_boxes, compare_results


def run(pool_path, day, output_path):
    raw = pool_path.read_bytes()
    pool = pd.read_csv(BytesIO(raw), dtype={'fanduel_id': str})
    if pool.empty or not {'fanduel_id', 'game', 'team', 'fanduel_name'} <= set(pool):
        raise ValueError('Use the complete saved FanDuel player pool CSV.')
    ids = pool.fanduel_id
    if not ids.is_unique or not ids.str.fullmatch(r'[0-9]{1,12}-[0-9]+', na=False).all():
        raise ValueError('The saved player pool must use distinct FanDuel player IDs.')
    contest = ids.iloc[0].split('-', 1)[0]
    if not ids.str.fullmatch(re.escape(contest) + r'-[0-9]+').all():
        raise ValueError('The saved player pool must cover exactly one contest.')
    games = set(pool.game.map(game_code).map(matchup_key))
    if '' in games:
        raise ValueError('The saved player pool has an invalid matchup.')
    if output_path.exists():
        raise FileExistsError('Choose a new output path for the replay archive.')

    empty_results, _ = compare_results(pool, day, [], {})
    build_replay_rows(pool, empty_results, day)
    boxes = collect_final_boxes(day, games)
    results, finals = compare_results(pool, day, boxes, {})
    summary = {'slate_date': day.isoformat(), 'contest_id': contest, 'contest_games': len(games),
               'verified_final_games': len(finals), 'frozen_pool_sha256': sha256(raw).hexdigest()}
    if finals != games:
        return dict(summary, status='waiting_for_verified_final_box_scores')

    replay = build_replay_rows(pool, results, day)
    accuracy = compare_frozen_projections(replay)
    methods = compare_adjustment_methods(replay)
    props = review_player_props(replay, results)
    prop_summary = summarize_player_props(props)
    counts = {label: int(count) for label, count in replay.verified_outcome.value_counts().items()}
    summary = dict(summary, status='reviewed', player_outcomes=counts)
    with TemporaryDirectory(dir=output_path.parent) as staging:
        archive = Path(staging) / 'replay.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as zipped:
            zipped.writestr('manifest.json', json.dumps(summary, indent=2) + '\n')
            zipped.writestr('player_replay.csv', replay.to_csv(index=False))
            zipped.writestr('projection_comparison.csv', accuracy.to_csv(index=False))
            if not methods.empty:
                zipped.writestr('adjustment_comparison.csv', methods.to_csv(index=False))
            if not props.empty:
                zipped.writestr('player_prop_review.csv', props.to_csv(index=False))
            if not prop_summary.empty:
                zipped.writestr('player_prop_summary.csv', prop_summary.to_csv(index=False))
        output_path.hardlink_to(archive)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pool', type=Path, help='Archived pre-tip full player pool CSV')
    parser.add_argument('slate_date', type=date.fromisoformat)
    parser.add_argument('output', type=Path, help='Path for a new replay ZIP when all games are final')
    args = parser.parse_args()
    try:
        summary = run(args.pool, args.slate_date, args.output)
    except SOURCE_ERRORS as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
