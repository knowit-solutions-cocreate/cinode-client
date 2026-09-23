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
