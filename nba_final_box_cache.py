"""Bounded, thread-safe reuse of previously retrieved public final box scores."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic


class FinalBoxCache:
    def __init__(self, max_entries=512, ttl_seconds=1800, clock=monotonic):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._items = OrderedDict()
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stamp, rows = entry
            if self.clock() - stamp >= self.ttl_seconds:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return deepcopy(rows)

    def put(self, key, rows):
        # A successful retrieval is not necessarily a complete final box.
        # Require both expected teams; never retain empty/one-sided responses.
        day, game_id, away, home = key
        if not rows or {row.get('team') for row in rows} != {away, home}:
            return
        if any(row.get('game_date') != day or row.get('game') != f'{away}@{home}'
               for row in rows):
            return
        with self._lock:
            self._items[key] = (self.clock(), deepcopy(rows))
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


FINAL_BOX_CACHE = FinalBoxCache()
