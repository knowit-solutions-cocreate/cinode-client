from support import FakeClock

from cinode._ratelimit import RateLimiter


def test_full_window_sleeps_until_the_oldest_call_leaves() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, 2.0, clock=clock, sleep=clock.sleep)
    limiter.acquire()
    clock.t += 0.5
    limiter.acquire()
    limiter.acquire()
    assert clock.sleeps == [1.5]


def test_rounding_does_not_leave_acquire_spinning_on_zero_sleeps() -> None:
    # Values from review: with mismatched float expressions for the expiry check
    # and the sleep length, the re-check failed and acquire() slept 0.0 forever.
    clock = FakeClock(511.98588985568614)

    def sleep(seconds: float) -> None:
        if len(clock.sleeps) >= 3:
            raise AssertionError(f"acquire() is spinning: {clock.sleeps}")
        clock.sleep(seconds)

    limiter = RateLimiter(2, 2.0, clock=clock, sleep=sleep)
    limiter.acquire()
    clock.t = 513.5762272768609
    limiter.acquire()
    limiter.acquire()
    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] > 0
