from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from support import BASE_URL, FakeClock, make_jwt

from cinode._client import Cinode
from cinode._config import Settings
from cinode._transport import Transport


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


@pytest.fixture
def settings() -> Settings:
    return Settings(basic="YWJjOmRlZg==", base_url=BASE_URL)


@pytest.fixture
def transport(settings: Settings, clock: FakeClock, api: respx.MockRouter) -> Iterator[Transport]:
    """A transport on the fake clock, with `rng` fixed so backoff runs 0.5, 1, 2, 4."""
    transport = Transport(settings, clock=clock, sleep=clock.sleep, now=clock, rng=lambda: 1.0)
    yield transport
    transport.close()


@pytest.fixture
def client(transport: Transport) -> Cinode:
    """A `Cinode` over the `transport` fixture, which closes it."""
    return Cinode._with_transport(transport)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _no_credentials_file(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point the credentials file at a path that does not exist.

    Without this, a test that finds no credentials in the environment would
    read the developer's own file, and reach a real account.
    """
    monkeypatch.setenv("CINODE_CREDENTIALS_FILE", str(tmp_path / "absent" / "credentials.toml"))
