"""Per-key locks so concurrent background tasks don't duplicate work for the same user.

Several things can trigger the same job at once (adding an expense, opening the
dashboard, opening a report). Without a lock, both would call Gemini and both
would try to insert the same row, and the second insert would crash.
"""
import threading
from collections import defaultdict
from contextlib import contextmanager

_guard = threading.Lock()
_locks: dict = defaultdict(threading.Lock)


@contextmanager
def keyed_lock(key):
    with _guard:
        lock = _locks[key]
    with lock:
        yield
