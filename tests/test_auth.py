from collections.abc import Iterator

import httpx
import pytest
import respx
from support import BASE_URL, COMPANY_ID, USER_ID, FakeClock, make_jwt

from cinode._auth import TokenManager
from cinode._ratelimit import RateLimiter
from cinode.errors import AuthError


@pytest.fixture
def tokens(clock: FakeClock, api: respx.MockRouter) -> Iterator[TokenManager]:
    with httpx.Client(base_url=BASE_URL) as http:
        limiter = RateLimiter(2, 2.0, clock=clock, sleep=clock.sleep)
        yield TokenManager(http, "YWJjOmRlZg==", limiter, now=clock)


def test_token_is_cached_until_30_s_remain(
    tokens: TokenManager, clock: FakeClock, api: respx.MockRouter
) -> None:
    token = tokens.get()
    tokens.get()
    assert api["token"].call_count == 1
    assert (token.user_id, token.company_id) == (USER_ID, COMPANY_ID)
    assert api["token"].calls[0].request.headers["Authorization"] == "Basic YWJjOmRlZg=="

    clock.t += 91
    tokens.get()
    assert api["token"].call_count == 2


def test_lifetime_is_counted_on_the_local_clock(
    tokens: TokenManager, clock: FakeClock, api: respx.MockRouter
) -> None:
    # By Cinode's clock the token was issued and expired long ago; ours
    # disagrees. It must still be cached for its full lifetime.
    clock.t = 1_800_000_000.0
    api["token"].return_value = httpx.Response(200, json={"access_token": make_jwt(iat=1000)})
    tokens.get()
    clock.t += 89
    tokens.get()
    assert api["token"].call_count == 1


def test_rejected_credentials_raise_auth_error(tokens: TokenManager, api: respx.MockRouter) -> None:
    api["token"].return_value = httpx.Response(401)
    with pytest.raises(AuthError):
        tokens.get()
