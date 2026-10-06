"""Defines the error raised when a request goes over a limit (task 4.6).

Exists so the scope and the wait travel to the web layer, which answers 429 with `Retry-After`
and records `rate_limit_exceeded`. Raised by `krtr/back/security/rate_limit/limiter.py`.
"""

from krtr.back.security.rate_limit.config import LimitScope


class RateLimited(Exception):
    """Raised when a request is over its limit.

    Exists so callers handle every scope with one exception. Consumed by
    `krtr/back/web/rate_limit.py`.
    """

    def __init__(self, scope: LimitScope, retry_after_seconds: int) -> None:
        """Builds the error for one scope.

        Args:
            scope: Which limit was exceeded.
            retry_after_seconds: Whole seconds until the next request would be allowed.
        """
        super().__init__(scope.value)
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
