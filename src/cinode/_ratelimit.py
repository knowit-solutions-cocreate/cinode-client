"""A sliding-window rate limiter with an injectable clock."""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    """Allow at most `limit` calls in any `window` seconds.

    `acquire()` blocks, by calling `sleep`, until a slot is free. Counting is
    per instance, so it covers one process only.
    """

    def __init__(
        self,
        limit: int,
        window: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if limit < 1 or window <= 0:
            raise ValueError("limit must be at least 1 and window must be positive")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        """Take a slot, sleeping first until the oldest call leaves the window if none is free."""
        while True:
            now = self._clock()
            while self._calls and now - self._calls[0] >= self._window:
                self._calls.popleft()
            if len(self._calls) < self._limit:
                self._calls.append(now)
                return
            self._sleep(self._calls[0] + self._window - now)
