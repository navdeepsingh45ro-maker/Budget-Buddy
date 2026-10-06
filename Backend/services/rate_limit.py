"""Small in-memory rate limiter for login, sign-up, password reset and AI endpoints.

Counts events per key inside a sliding time window. State lives in this
process, which matches the rest of the app (the scheduler is single-process
too); with several server processes each would count separately, so move this
to Redis or the database before scaling out.

Usage:
    LOGIN = Limit("login", max_events=10, window_seconds=15 * 60)
    LOGIN.check(email)   # raises HTTP 429 if the key is over the limit
    LOGIN.hit(email)     # record one event (e.g. a failed attempt)
    LOGIN.reset(email)   # forget the key (e.g. after a successful login)
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_events: dict[tuple, deque] = defaultdict(deque)


def _minutes(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes >= 90:
        hours = round(minutes / 60)
        return f"{hours} hours"
    return "a minute" if minutes == 1 else f"{minutes} minutes"


class Limit:
    def __init__(self, name: str, max_events: int, window_seconds: int, message: str | None = None):
        self.name, self.max_events, self.window = name, max_events, window_seconds
        self.message = message or "Too many attempts. Please try again in {wait}."

    def _recent(self, key, now: float) -> deque:
        events = _events[(self.name, key)]
        while events and events[0] <= now - self.window:
            events.popleft()
        return events

    def check(self, key) -> None:
        """Raise 429 if this key has already used up its allowance."""
        now = time.monotonic()
        with _lock:
            events = self._recent(key, now)
            if len(events) >= self.max_events:
                wait = self.window - (now - events[0])
                raise HTTPException(status_code=429, detail=self.message.format(wait=_minutes(wait)),
                                    headers={"Retry-After": str(int(wait) + 1)})
            if not events:
                _events.pop((self.name, key), None)

    def hit(self, key) -> None:
        with _lock:
            self._recent(key, time.monotonic()).append(time.monotonic())

    def use(self, key) -> None:
        """check() then hit(): for actions where every call counts, not only failures."""
        self.check(key)
        self.hit(key)

    def reset(self, key) -> None:
        with _lock:
            _events.pop((self.name, key), None)


def client_ip(request: Request) -> str:
    """The caller's IP. In production run uvicorn with --proxy-headers so this is
    the real visitor and not the hosting provider's proxy."""
    return request.client.host if request.client else "unknown"


def reset_all() -> None:
    """For tests."""
    with _lock:
        _events.clear()
