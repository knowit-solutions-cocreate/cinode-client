"""`cinode config` and `cinode init`: where the credentials come from, and saving them.

This module holds the only code in the project that writes a file.
"""

import contextlib
import json
import os
import stat
import sys
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

import typer
from typer._click.exceptions import UsageError

from cinode._client import Cinode
from cinode._config import Settings, credentials_path, decode_basic
from cinode.cli._output import fail, write
from cinode.errors import CinodeError
from cinode.models import CinodeModel

_FILE_HEADER = "# Written by `cinode init`. It holds a secret: keep it private (chmod 600).\n"

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
    if mode is not None and not stat.S_ISREG(mode):
        mode = None  # a directory or other non-file is not a credentials file
    report = ConfigReport(
        source=settings.source,
        access_id=settings.access_id,
        path=str(path),
        file_exists=mode is not None,
        file_mode=None if mode is None else f"{stat.S_IMODE(mode):04o}",
        file_private=None if mode is None else (mode & 0o077) == 0,
    )
    write(report, raw=False, jsonl=False)


class InitResult(CinodeModel):
    """What `cinode init` saved, and whose account it is. It never holds the secret."""

    path: str
    access_id: str
    company_id: int
    user_id: int


AccessIdOption = Annotated[
    str | None,
    typer.Option(
        "--access-id",
        help="The AccessId. Without a terminal, the secret is the first line of stdin.",
    ),
]
FromEnvOption = Annotated[
    bool,
    typer.Option(
        "--from-env",
        help="Take the credentials from CINODE_ACCESS_ID and CINODE_ACCESS_SECRET, "
        "or CINODE_BASIC.",
    ),
]
ForceOption = Annotated[bool, typer.Option("--force", help="Replace an existing file.")]


def init(
    access_id: AccessIdOption = None, from_env: FromEnvOption = False, force: ForceOption = False
) -> None:
    """Check a set of credentials against Cinode, and save them to the credentials file."""
    path = credentials_path()
    if path.exists() and not force:
        fail(
            CinodeError(f"A credentials file already exists at {path}. Pass --force to replace it.")
        )

    if from_env:
        if access_id is not None:
            raise UsageError("--from-env and --access-id cannot be used together.")
        access_id, access_secret = _from_env(os.environ)
    elif sys.stdin.isatty():
        if access_id is None:
            access_id = str(typer.prompt("AccessId", err=True))
        access_secret = str(typer.prompt("AccessSecret", hide_input=True, err=True))
    else:
        if access_id is None:
            raise UsageError(
                "Pass --access-id when stdin is not a terminal, with the secret as its first line."
            )
        try:
            access_secret = sys.stdin.readline()
        except UnicodeDecodeError:
            raise typer.BadParameter("the secret on stdin is not valid UTF-8.") from None
    access_id = _checked("the AccessId", access_id.strip())
    access_secret = _checked("the secret", access_secret.strip())

    try:
        with Cinode(access_id, access_secret) as c:
            who = c.whoami()
    except CinodeError as error:
        fail(error)

    try:
        _write_credentials(path, access_id, access_secret)
    except CinodeError as error:
        fail(error)
    except OSError as error:
        fail(CinodeError(f"Cannot write the credentials file at {path}: {error.strerror}."))
    result = InitResult(
        path=str(path), access_id=access_id, company_id=who.company_id, user_id=who.user_id
    )
    write(result, raw=False, jsonl=False)


def _from_env(env: Mapping[str, str]) -> tuple[str, str]:
    """The credentials in the environment, for `--from-env`: the pair, else `CINODE_BASIC`."""
    access_id = env.get("CINODE_ACCESS_ID")
    access_secret = env.get("CINODE_ACCESS_SECRET")
    if access_id and access_secret:
        return access_id, access_secret
    if access_id or access_secret:
        raise typer.BadParameter("--from-env needs both CINODE_ACCESS_ID and CINODE_ACCESS_SECRET.")
    basic = env.get("CINODE_BASIC") or ""
    decoded = decode_basic(basic) if basic.strip() else None
    if decoded is None:
        raise typer.BadParameter(
            "--from-env found no usable credentials: set CINODE_ACCESS_ID and "
            "CINODE_ACCESS_SECRET, or CINODE_BASIC to base64(access_id:access_secret)."
        )
    return decoded


def _checked(name: str, value: str) -> str:
    """`value`, if it is a non-empty UTF-8 string with no control character.

    The message names the value, never quotes it.
    """
    if not value:
        raise typer.BadParameter(f"{name} is empty.")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise typer.BadParameter(f"{name} contains a control character.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise typer.BadParameter(f"{name} is not valid UTF-8.") from None
    return value


def _write_credentials(path: Path, access_id: str, access_secret: str) -> None:
    """Write the credentials file atomically, private from the moment it exists.

    The text is written to a temporary file in the same directory, which
    `mkstemp` creates with mode 0600, and renamed over `path`. The temporary
    file is removed if anything fails.
    """
    values = {"access_id": access_id, "access_secret": access_secret}
    text = _FILE_HEADER + "".join(
        f"{key} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items()
    )
    read_back: dict[str, object] | None = None
    with contextlib.suppress(tomllib.TOMLDecodeError):  # its message may quote the secret
        read_back = tomllib.loads(text)
    if read_back != values:
        raise CinodeError("The credentials do not survive a round trip through TOML.")

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".credentials-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
