from collections.abc import Iterator

import httpx
import pytest
import respx
from support import BASE_URL, FakeClock, make_jwt


@pytest.fixture
def clock() -> FakeClock:
    """One fake clock, to stand in for monotonic time, wall time and sleep alike."""
    return FakeClock()


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    """A mocked Cinode at `BASE_URL`. Its `token` route hands out `make_jwt()`."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.get("/token", name="token").mock(
            return_value=httpx.Response(
                200, json={"access_token": make_jwt(), "refresh_token": "refresh"}
            )
        )
        yield router
