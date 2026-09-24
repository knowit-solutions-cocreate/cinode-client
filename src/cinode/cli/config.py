"""`cinode config`: where the credentials come from."""

import stat
from typing import Literal

import typer

from cinode._config import Settings, credentials_path
from cinode.cli._output import fail, write
from cinode.errors import CinodeError
from cinode.models import CinodeModel

app = typer.Typer(no_args_is_help=True, help="Where the credentials come from.")


class ConfigReport(CinodeModel):
    """Where the credentials in use come from. It never holds the secret."""

    source: Literal["env", "file"]
    access_id: str | None
    path: str
    file_exists: bool
    file_mode: str | None
    file_private: bool | None


@app.callback()
def config() -> None:
    """Where the credentials come from."""


@app.command("show")
def show() -> None:
    """Where the credentials in use come from, without a network call."""
    try:
        settings = Settings.resolve()
    except CinodeError as error:
        fail(error)
    if settings.source == "argument":
        raise AssertionError("resolve() without arguments never takes them from arguments")

    path = credentials_path()
    try:
        mode: int | None = path.stat().st_mode
    except OSError:
        mode = None
    report = ConfigReport(
        source=settings.source,
        access_id=settings.access_id,
        path=str(path),
        file_exists=mode is not None,
        file_mode=None if mode is None else f"{stat.S_IMODE(mode):04o}",
        file_private=None if mode is None else (mode & 0o077) == 0,
    )
    write(report, raw=False, jsonl=False)
