"""Score the archived public Nov 27 preview on common contest and box identities.

Run from the repository with PYTHONPATH=. and pass the four pinned source paths
in order: forecast ZIP, contest checkpoint ZIP, final ESPN JSON, outcome CSV.
"""
from argparse import ArgumentParser
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from model import SLOTS, allowed_slots
from nba_classic_rules import legal_team_counts
from nba_reference_component_accuracy import WEIGHTS, matched_components
from slate_import import contest_player_keys, reconcile_exports, team_code
from slate_results import result_name


DIGESTS = (
    '337aeb26e12c0ae9ea1af9f2b8b419c416d9536f81322e22fb19003178cffa1e',
    '0545c34e12387efa4094ee359d54b272f8c3725f115c17152b2a6e0a82b1418f',
    'eb34425804b8a8a6f0f395ddb1b41461ebdfb7e2c61db13a7f36f16bf660c8c5',
    '6f770a2bac8a961341392de00abf75f3cf74cac5b9c0cbd5e077f66a4db475f2',
)
STAT_KEYS = dict(points='PTS', rebounds='REB', assists='AST', steals='STL', blocks='BLK', turnovers='TOV')
GAME = 'BKN@TOR'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def replay(paths):
    files = [path.read_bytes() for path in paths]
    require(tuple(sha256(raw).hexdigest() for raw in files) == DIGESTS, 'Archive digest mismatch')
    with ZipFile(BytesIO(files[0])) as archive:
        preview = json.loads(archive.read('drop-nba-public-preview-audit.json'))
        for name, digest in preview['sha256'].items():
            require(sha256(archive.read(name)).hexdigest() == digest, 'Preview source digest mismatch')
    with ZipFile(BytesIO(files[1])) as archive:
        saved = json.loads(archive.read("report_final.json"))
        pool, contest, _ = reconcile_exports(archive.read('FanDuel-NBA-2026-11-27-137257-lineup-upload-template.csv'),
                                             archive.read('DAILY 5(1).csv'))
    require(contest == '137257', 'Unexpected contest')
    outcomes = pd.read_csv(BytesIO(files[3])).set_index('id', verify_integrity=True)
    final = json.loads(files[2])
    event, = final['header']['competitions']
    sides = {row['homeAway']: team_code(row['team']['abbreviation']) for row in event['competitors']}
    require(event['status']['type']['completed'] and f"{sides['away']}@{sides['home']}" == GAME,
            'Expected the completed preview game')
    require(pd.Timestamp(preview['provider_latest_update']) <= pd.Timestamp(preview['observed_at'])
            < pd.Timestamp(event['date']), 'Invalid capture chronology')

    boxes = defaultdict(list)
    for club in final['boxscore']['players']:
        group, = club['statistics']
        for athlete in group['athletes']:
            if athlete['stats'] and not athlete['didNotPlay']:
                boxes[team_code(club['team']['abbreviation']), result_name(athlete['athlete']['displayName'])].append(
                    dict(zip(group['keys'], athlete['stats'], strict=True)))

    candidates = pool.loc[pool.game.eq(GAME)]
    covered = set()
    rows, detail = [], []
    for source in preview['rows']:
        require(source['game_id'] == event['id'] and source['game'] == GAME
                and pd.Timestamp(source['kickoff']) == pd.Timestamp(event['date']), 'Preview game mismatch')
        name = result_name(source['player'])
        matches = [p for p in candidates.itertuples() if p.team == source['team']
                   and name in contest_player_keys(p.fanduel_name, p.fanduel_id)]
        require(len(matches) == 1, f"Expected unique contest identity for {source['player']}")
        p, = matches
        require(p.fanduel_id not in covered, 'Duplicate source player')
        covered.add(p.fanduel_id)
        result = outcomes.loc[p.fanduel_id]
        require((result.game, result.team, result.salary) == (p.game, p.team, p.salary), 'Outcome identity mismatch')
        entry = dict(minutes=source['minutes'], components={k: source['components'][key] for k,key in STAT_KEYS.items()})
        contribution = sum(entry['components'][k] * weight for k, weight in WEIGHTS.items())
        require(abs(contribution-source['weighted_fd']) < .001, 'Component sum mismatch')
        row = dict(id=p.fanduel_id, player=p.fanduel_name, salary=p.salary, source_minutes=entry['minutes'],
                   source_fd=contribution, daily_minutes=p.projected_minutes, daily_fd=p.projected_fd_points,
                   late_minutes=result.in_min, late_fd=result.in_fd, status=result.outcome_status)
        rows.append(row)
        if result.outcome_status != 'played_box':
            continue
        hits = [box for key in contest_player_keys(p.fanduel_name, p.fanduel_id) for box in boxes[p.team, key]]
        require(len(hits) == 1, 'Missing unique independent played box')
        box, = hits
        actual = {k: int(box[k]) for k in WEIGHTS}
        require(abs(sum(actual[k]*w for k,w in WEIGHTS.items()) - result.actual_fd) < .001
                and abs(float(box['minutes']) - result.actual_minutes) <= 1, 'Outcome mismatch')
        row.update(actual_minutes=result.actual_minutes, actual_fd=result.actual_fd)
        if pd.isna(p.projected_minutes) or p.import_issue:
            continue
        fields = {('nba_reboundsTotal' if k=='rebounds' else 'nba_'+k): value for k,value in actual.items()}
        record = pd.Series(dict(p._asdict(), **fields, actual_points=result.actual_fd,
                                actual_minutes=result.actual_minutes, daily_minutes=p.projected_minutes,
                                adjusted_minutes=result.in_min))
        for metric, prediction, observed, daily in matched_components(record, entry):
            detail.append(dict(id=p.fanduel_id, salary=p.salary, metric=metric, actual=observed,
                               source=prediction, daily=daily))
    require(len(covered) == len(preview['rows']), 'Incomplete contest matching')
    # Change only the preview-game forecasts on already saved rosters.
    source_fd = {row['id']: row['source_fd'] for row in rows}
    pool_by_id = pool.set_index('fanduel_id')
    fixed = []
    for label, candidate in saved['candidates'].items():
        ids = [player['id'] for player in candidate['players']]
        slots = [player['slot'].replace('UTIL1', 'UTIL').replace('UTIL2', 'UTIL') for player in candidate['players']]
        roster = pool_by_id.loc[ids]
        require(len(set(ids)) == 9 and sorted(slots) == sorted(SLOTS) and roster.salary.sum() <= 60000
                and legal_team_counts(roster.team)
                and all(s in allowed_slots(e) for s,e in zip(slots, roster.roster_eligibility)),
                'Invalid saved roster')
        results = outcomes.loc[ids]
        require(results.actual_fd.notna().all() and abs(results.in_fd.sum()-candidate['in']) < .001,
                'Saved candidate does not reconcile')
        delta = sum(source_fd[pid]-outcomes.at[pid,'in_fd'] for pid in ids if pid in source_fd)
        fixed.append(dict(candidate=label, actual=results.actual_fd.sum(), late=candidate['in'],
                          substituted=candidate['in']+delta, matched=len(set(ids) & covered)))
    return pd.DataFrame(rows), pd.DataFrame(detail), pd.DataFrame(fixed)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('archive_paths', nargs=4, type=Path)
    args = parser.parse_args()
    players, components, candidates = replay(args.archive_paths)
    print("Fixed-roster MAE", candidates[["late", "substituted"]].sub(candidates.actual, axis=0).abs().mean())
    print("Source-covered slots per roster", candidates.matched.value_counts().to_dict())
    print(players.groupby(['status', players.source_minutes.eq(0)]).size())
    paired = players.loc[players.status.eq('played_box')].dropna(subset=['daily_minutes', 'daily_fd', 'late_fd','late_minutes'])
    for label, sample in [('all', paired), ('under_5000', paired.loc[paired.salary.lt(5000)])]:
        print(label, len(sample))
        for metric in ('minutes', 'fd'):
            errors = {policy: (sample[policy+'_'+metric]-sample['actual_'+metric]).abs().mean()
                      for policy in ('source', 'daily', 'late')}
            print(metric, errors)
        detail = components.loc[components.id.isin(sample.id)].copy()
        for policy in ('source', 'daily'):
            detail[policy] = (detail[policy] - detail.actual).abs()
        print(detail.groupby('metric').agg(n=('id','size'), source=('source','mean'), daily=('daily','mean')).round(4))


if __name__ == '__main__':
    main()
