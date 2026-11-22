"""Replay descriptive NBA rotation signals against completed, archived outcomes."""
import pandas as pd


def compare_opportunity(outcomes, rotations, absence_splits):
    """Return paired errors for fixed, research-only minutes scenarios.

    Inputs use one contest and must contain its frozen DAILY baseline and final
    minutes. Build rotation evidence using games before the contest date and
    absence labels known before lock. Unplayed and unresolved rows are counted
    by the caller and excluded here to isolate playing-time error.
    """
    played = outcomes.loc[outcomes.actual_minutes.gt(0) & outcomes.actual_minutes.le(60)
                          & outcomes.daily_minutes.gt(0) & outcomes.daily_minutes.le(48)
                          & outcomes.daily_points.gt(0)].copy()
    played['baseline_fd_error'] = (played.daily_points - played.actual_points).abs()
    if rotations.empty:
        return pd.DataFrame()
    paired = played.merge(rotations, on='fanduel_id', validate='one_to_one')
    candidates = {
        'Last five average': (paired, paired['Last 5 minutes']),
        'DAILY plus 25% last five': (paired, .75 * paired.daily_minutes + .25 * paired['Last 5 minutes']),
        'DAILY plus 25% last ten': (paired, .75 * paired.daily_minutes + .25 * paired['Last 10 minutes']),
    }
    if not absence_splits.empty:
        filtered = absence_splits.loc[absence_splits['Games with teammate'].ge(3)
                                      & absence_splits['Games without teammate'].ge(3)]
        unambiguous = filtered.loc[~filtered.fanduel_id.duplicated(keep=False)]
        split = played.merge(unambiguous, on='fanduel_id', validate='one_to_one')
        candidates['DAILY plus one shrunk absence gap'] = (split, split.daily_minutes + split['Minutes gap (shrunk)'])

    results = []
    for label, (frame, candidate) in candidates.items():
        sample = frame.loc[candidate.notna()]
        minutes = candidate.loc[sample.index].clip(0, 48)
        points = minutes * sample.daily_points / sample.daily_minutes
        results.append({
            'scenario': label, 'n': len(sample), 'played_with_baseline': len(played),
            'daily_minutes_mae': (sample.daily_minutes - sample.actual_minutes).abs().mean(),
            'scenario_minutes_mae': (minutes - sample.actual_minutes).abs().mean(),
            'n_fd_points': int(sample.actual_points.notna().sum()),
            'daily_fd_mae': sample.baseline_fd_error.mean(),
            'scenario_fd_mae': (points - sample.actual_points).abs().mean(),
        })
    return pd.DataFrame(results)
