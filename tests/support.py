"""Shared test helpers. Tests import from here; pytest puts `tests/` on the path."""


class FakeClock:
    """A clock that only moves when told to: call it for the time, `sleep` to advance it."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds
