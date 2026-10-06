"""Counts requests per key in a sliding window (task 4.6).

Exists so each limit (per IP, per session, per customer on the chat) is enforced exactly: a
key may make at most `limit` requests in any `window`, and a rejected request learns how long
to wait. State lives in memory, which is correct because krtr-web runs a single container
(D8); a second container would need a shared store. Thread-safe, because FastAPI runs sync
routes and dependencies in a pool. Consumed by `krtr/back/web/rate_limit.py`.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import timedelta

from krtr.back.security.rate_limit.config import LimitScope
from krtr.back.security.rate_limit.errors import RateLimited

_SWEEP_EVERY = 1000  # Forget idle keys every this many hits, so memory stays bounded.


class SlidingWindowLimiter:
    """Allows at most `limit` hits per key in any window of `window`.

    Exists as the one counting rule every scope shares. Consumed by `krtr/back/web/rate_limit.py`.
    """

    def __init__(
        self,
        scope: LimitScope,
        limit: int,
        window: timedelta,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Builds a limiter for one scope.

        Args:
            scope: What it counts by, reported when a hit is rejected.
            limit: How many hits a key may make per window.
            window: The window's length.
            clock: Returns monotonic seconds; a fake in tests.
        """
        self._scope = scope
        self._limit = limit
        self._window_seconds = window.total_seconds()
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._hits_since_sweep = 0

    def hit(self, key: str) -> None:
        """Counts one request for `key`, or rejects it if the key is over its limit.

        A rejected request is not counted, so a client that waits the advised time gets in.

        Args:
            key: Who the request counts against (an IP, a session, a customer).

        Returns:
            None.

        Raises:
            RateLimited: with the scope and the seconds until the oldest hit leaves the window.
        """
        now = self._clock()
        with self._lock:
            self._sweep_if_due(now)
            hits = self._hits.setdefault(key, deque())
            _drop_expired(hits, now - self._window_seconds)
            if len(hits) >= self._limit:
                retry_after = hits[0] + self._window_seconds - now
                raise RateLimited(self._scope, max(1, math.ceil(retry_after)))
            hits.append(now)

    def _sweep_if_due(self, now: float) -> None:
        """Forgets keys with no hit inside the window, every `_SWEEP_EVERY` hits.

        Must be called holding the lock.

        Args:
            now: The current clock reading.

        Returns:
            None.
        """
        self._hits_since_sweep += 1
        if self._hits_since_sweep < _SWEEP_EVERY:
            return
        self._hits_since_sweep = 0
        cutoff = now - self._window_seconds
        idle = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in idle:
            del self._hits[key]


def _drop_expired(hits: deque[float], cutoff: float) -> None:
    """Removes the hits at or before `cutoff` from the front of a key's queue.

    Args:
        hits: The key's hit times, oldest first.
        cutoff: The start of the current window.

    Returns:
        None.
    """
    while hits and hits[0] <= cutoff:
        hits.popleft()
