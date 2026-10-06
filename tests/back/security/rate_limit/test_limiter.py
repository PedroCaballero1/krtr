"""Tests SlidingWindowLimiter: an exact limit per key over any window, and the advised wait."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from krtr.back.security.rate_limit.config import LimitScope
from krtr.back.security.rate_limit.errors import RateLimited
from krtr.back.security.rate_limit.limiter import SlidingWindowLimiter

MINUTE = timedelta(minutes=1)


class FakeMonotonicClock:
    """A monotonic clock the test moves forward by hand."""

    def __init__(self) -> None:
        """Starts at an arbitrary reading."""
        self.now = 1000.0

    def __call__(self) -> float:
        """Returns the current reading."""
        return self.now


def limiter(limit: int, clock: FakeMonotonicClock) -> SlidingWindowLimiter:
    """Builds a chat-scoped limiter on the fake clock."""
    return SlidingWindowLimiter(LimitScope.CHAT, limit, MINUTE, clock)


def test_the_hit_after_the_limit_is_rejected_with_its_scope() -> None:
    """20 messages pass and the 21st is refused (G3)."""
    chat = limiter(20, FakeMonotonicClock())
    for _ in range(20):
        chat.hit("C1")

    with pytest.raises(RateLimited) as raised:
        chat.hit("C1")

    assert raised.value.scope == LimitScope.CHAT


def test_the_wait_is_until_the_oldest_hit_leaves_the_window() -> None:
    """Retry-After must be honest: waiting that long gets the next request in."""
    clock = FakeMonotonicClock()
    chat = limiter(2, clock)
    chat.hit("C1")
    clock.now += 45
    chat.hit("C1")

    with pytest.raises(RateLimited) as raised:
        chat.hit("C1")
    clock.now += raised.value.retry_after_seconds
    chat.hit("C1")

    assert raised.value.retry_after_seconds == 15


def test_the_window_slides_instead_of_resetting() -> None:
    """A burst across a minute boundary must not get twice the limit."""
    clock = FakeMonotonicClock()
    chat = limiter(3, clock)
    for _ in range(3):
        chat.hit("C1")
    clock.now += 59

    with pytest.raises(RateLimited):
        chat.hit("C1")


def test_a_rejected_hit_is_not_counted() -> None:
    """Hammering while limited must not push the wait further out."""
    clock = FakeMonotonicClock()
    chat = limiter(1, clock)
    chat.hit("C1")
    for _ in range(50):
        with pytest.raises(RateLimited):
            chat.hit("C1")
    clock.now += 60

    chat.hit("C1")


def test_keys_are_limited_independently() -> None:
    """One customer's burst must not limit another customer."""
    chat = limiter(1, FakeMonotonicClock())
    chat.hit("C1")

    chat.hit("C2")


def test_the_wait_is_at_least_one_second() -> None:
    """Retry-After is a whole number of seconds; 0 would invite an immediate retry."""
    clock = FakeMonotonicClock()
    chat = limiter(1, clock)
    chat.hit("C1")
    clock.now += 59.9

    with pytest.raises(RateLimited) as raised:
        chat.hit("C1")

    assert raised.value.retry_after_seconds == 1


def test_idle_keys_are_forgotten() -> None:
    """Thousands of one-off IPs must not grow memory forever."""
    clock = FakeMonotonicClock()
    per_ip = SlidingWindowLimiter(LimitScope.IP, 600, MINUTE, clock)
    for number in range(999):
        per_ip.hit(f"10.0.{number // 256}.{number % 256}")
    clock.now += 120

    per_ip.hit("10.9.9.9")

    assert set(per_ip._hits) == {"10.9.9.9"}


def test_concurrent_hits_never_exceed_the_limit() -> None:
    """Sync routes run in a thread pool; the count must stay exact under contention."""
    chat = limiter(20, FakeMonotonicClock())

    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(_hit_or_refuse, [chat] * 200))

    assert outcomes.count(True) == 20


def _hit_or_refuse(chat: SlidingWindowLimiter) -> bool:
    """Hits the limiter once and reports whether the hit was allowed."""
    try:
        chat.hit("C1")
    except RateLimited:
        return False
    return True
