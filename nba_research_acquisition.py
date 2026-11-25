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
