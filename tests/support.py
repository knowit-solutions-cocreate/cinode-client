"""Shared test helpers. Tests import from here; pytest puts `tests/` on the path."""

import base64
import json

BASE_URL = "https://api.test"
USER_ID = 1001
COMPANY_ID = 99


def make_jwt(
    *, iat: int = 0, lifetime: int = 120, sub: int = USER_ID, company: int = COMPANY_ID
) -> str:
    """An unsigned JWT with Cinode's claims. Only the payload is ever read."""

    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {"sub": str(sub), "companySub": str(company), "iat": iat, "exp": iat + lifetime}
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}.signature"


class FakeClock:
    """A clock that only moves when told to: call it for the time, `sleep` to advance it."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.sleeps.append(seconds)
        self.t += seconds
