"""Parallel public research acquisition with independently measured task durations."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic


def acquire_research(public_loader, rotation_loader, reference_loader=None):
    """Run independent read-only loaders concurrently; never hide errors.

    Individual providers retain their existing failure isolation, date checks,
    cache policy and evidence rules. Loaders must not mutate UI/session state.
    Timing includes cache access; it does not establish provider publication time.
    """
    jobs = [('Official and independent projections', public_loader),
            ('Recent official rotations', rotation_loader)]
    if reference_loader is not None:
        jobs.append(('Public reference boards', reference_loader))

    def timed(loader):
        start = monotonic()
        value = loader()
        return value, monotonic() - start

    started = monotonic()
    with ThreadPoolExecutor(max_workers=len(jobs)) as workers:
        futures = {name: workers.submit(timed, loader) for name, loader in jobs}
        results = {name: future.result() for name, future in futures.items()}
    elapsed = monotonic() - started
    return (results[jobs[0][0]][0], results[jobs[1][0]][0],
            results[jobs[2][0]][0] if reference_loader is not None else None,
            {'elapsed_seconds': elapsed,
             'tasks': {name: seconds for name, (_, seconds) in results.items()}})


def extended_history_safe(schedule, games, now, slate):
    """Allow a new optional historical fetch only >=90 min before every tip.

    Conservative scheduling guard, not a latency guarantee or lock certificate.
    Ambiguous/incomplete schedules, other dates and started games fail closed.
    Already acquired history can still be retained without a new network fetch.
    """
    import pandas as pd
    from zoneinfo import ZoneInfo
    from slate_import import matchup_key, team_code

    stamp = pd.Timestamp(now)
    if pd.isna(stamp) or stamp.tzinfo is None:
        return False
    if stamp.tz_convert(ZoneInfo('America/New_York')).date() != slate:
        return False
    games = list(games)
    if any(not isinstance(g,str) or g.count('@')!=1 or any(not team_code(t) for t in g.split('@')) for g in games):
        return False
    expected = {matchup_key('@'.join(team_code(t) for t in g.split('@'))) for g in games}
    if not expected or any(not g or len(set(g.split('/')))!=2 or not all(g.split('/')) for g in expected):
        return False
    tips = {}
    for entry in schedule:
        if not isinstance(entry,dict):
            continue
        away, home = (team_code((entry.get(side) or {}).get('teamTricode',''))
                      for side in ('awayTeam','homeTeam'))
        if not away or not home or away==home:
            continue
        key = matchup_key(f'{away}@{home}')
        if key not in expected:
            continue
        if key in tips or entry.get('gameStatus') not in (1,'1'):
            return False
        try:
            tip = pd.Timestamp(entry.get('gameTimeUtc'))
        except (TypeError,ValueError):
            return False
        if pd.isna(tip) or tip.tzinfo is None or tip.tz_convert('America/New_York').date()!=slate:
            return False
        if tip-stamp < pd.Timedelta(minutes=90):
            return False
        actual = entry.get('actualStartTimeUTC')
        if actual:
            try:
                started=pd.Timestamp(actual)
            except (TypeError,ValueError):
                return False
            if pd.isna(started) or started.tzinfo is None or started<=stamp:
                return False
        tips[key]=tip
    return set(tips)==expected
