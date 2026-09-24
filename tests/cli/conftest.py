from collections.abc import Callable, Iterator

import httpx
import pytest
import respx
from support import BASE_URL, make_jwt
from typer.testing import CliRunner, Result

from cinode._client import Cinode
from cinode._config import Settings
from cinode._transport import Transport
from cinode.cli import app


def _no_sleep(_seconds: float) -> None:
    pass


@pytest.fixture
def cli_api(monkeypatch: pytest.MonkeyPatch) -> Iterator[respx.MockRouter]:
    """A mocked Cinode that the CLI reaches through its environment.

    The CLI's client is built with a transport whose retries sleep for nothing,
    so a 429 that outlasts them costs no time.
    """
    monkeypatch.setenv("CINODE_BASIC", "YWJjOmRlZg==")
    monkeypatch.setenv("CINODE_BASE_URL", BASE_URL)
    monkeypatch.delenv("CINODE_ACCESS_ID", raising=False)
    monkeypatch.delenv("CINODE_ACCESS_SECRET", raising=False)
    monkeypatch.setattr(
        "cinode.cli._output.client",
        lambda: Cinode._with_transport(Transport(Settings.resolve(), sleep=_no_sleep)),
    )
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.get("/token", name="token").mock(
            return_value=httpx.Response(
                200, json={"access_token": make_jwt(), "refresh_token": "refresh"}
            )
        )
        yield router


@pytest.fixture
def cli() -> Callable[..., Result]:
    """Run `cinode` with the given arguments."""
    runner = CliRunner()
    return lambda *args: runner.invoke(app, list(args))
