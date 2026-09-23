import httpx
import pytest
import respx
from support import FakeClock

from cinode._transport import Transport
from cinode.errors import (
    FORBIDDEN_HINT,
    AuthError,
    BadRequestError,
    CinodeError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    UnexpectedResponseError,
)

PATH = "/v0.1/companies/99/users"


def test_401_refreshes_the_token_once(transport: Transport, api: respx.MockRouter) -> None:
    route = api.get(PATH).mock(side_effect=[httpx.Response(401), httpx.Response(200, json=[])])
    assert transport.get("companies/99/users") == []
    assert (route.call_count, api["token"].call_count) == (2, 2)

    route.side_effect = [httpx.Response(401), httpx.Response(401)]
    with pytest.raises(AuthError):
        transport.get("companies/99/users")


def test_429_and_5xx_are_retried_with_backoff(
    transport: Transport, clock: FakeClock, api: respx.MockRouter
) -> None:
    route = api.get(PATH)
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "3"}),
        httpx.Response(200, json=[]),
    ]
    transport.get("companies/99/users")
    assert clock.sleeps == [3.0]

    clock.sleeps.clear()
    route.side_effect = [httpx.Response(429)] * 5
    with pytest.raises(RateLimitedError):
        transport.get("companies/99/users")
    assert clock.sleeps == [0.5, 1, 2, 4]

    clock.sleeps.clear()
    route.side_effect = [httpx.Response(503)] * 3
    with pytest.raises(ServerError):
        transport.get("companies/99/users")
    assert clock.sleeps == [0.5, 1]


@pytest.mark.parametrize(
    ("response", "error", "expected"),
    [
        (
            httpx.Response(400, json={"errors": {"name": ["Required."]}}),
            BadRequestError,
            {"field_errors": {"name": ["Required."]}},
        ),
        (
            httpx.Response(403, headers={"X-Correlation-Id": "abc-123"}),
            ForbiddenError,
            {"correlation_id": "abc-123", "message": FORBIDDEN_HINT},
        ),
        (httpx.Response(404), NotFoundError, {"status": 404, "path": PATH}),
    ],
    ids=["400", "403", "404"],
)
def test_error_statuses_raise_without_retry(
    transport: Transport,
    clock: FakeClock,
    api: respx.MockRouter,
    response: httpx.Response,
    error: type[CinodeError],
    expected: dict[str, object],
) -> None:
    route = api.get(PATH).mock(return_value=response)
    with pytest.raises(error) as raised:
        transport.get("companies/99/users")
    assert expected.items() <= raised.value.to_dict().items()
    assert route.call_count == 1
    assert clock.sleeps == []


def test_a_body_that_is_not_json_raises(transport: Transport, api: respx.MockRouter) -> None:
    api.get(PATH).mock(return_value=httpx.Response(200, text="<html>Bad gateway</html>"))
    with pytest.raises(UnexpectedResponseError):
        transport.get("companies/99/users")


def test_only_get_is_ever_sent(transport: Transport, api: respx.MockRouter) -> None:
    for name in ("post", "put", "patch", "delete", "request"):
        assert not hasattr(transport, name)
    api.get(PATH).mock(return_value=httpx.Response(200, json=[]))
    api.get("/_whoami").mock(return_value=httpx.Response(200, json={}))
    transport.get("companies/99/users")
    transport.get("_whoami", versioned=False)
    assert api.calls.call_count == 3
    assert {call.request.method for call in api.calls} == {"GET"}
