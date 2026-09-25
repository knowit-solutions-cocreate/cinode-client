"""What every command shares: output formats, the error envelope and exit codes."""

import json
import sys
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Annotated, Any, NoReturn

import typer
from typer._click.exceptions import UsageError
from typer._types import TyperChoice

from cinode._client import Cinode
from cinode.cli._table import Column, render
from cinode.errors import (
    AuthError,
    CinodeError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
)
from cinode.models import CinodeModel
from cinode.resources import UserRef

type Result = CinodeModel | Sequence[CinodeModel]


class Format(StrEnum):
    """What a command writes to stdout."""

    json = "json"
    jsonl = "jsonl"
    raw = "raw"
    table = "table"


_FORMAT_HELP = {
    Format.json: "json: one JSON document",
    Format.jsonl: "jsonl: one JSON object per line",
    Format.raw: "raw: Cinode's payload untouched",
    Format.table: "table: a table for a human to read",
}


def _format_option(*formats: Format) -> Any:
    """A `--format` option that takes exactly `formats`, and parses to a `Format`."""
    return typer.Option(
        "--format",
        click_type=TyperChoice(formats),
        help="; ".join(_FORMAT_HELP[f] for f in formats) + ".",
    )


FormatOption = Annotated[
    Format, _format_option(Format.json, Format.jsonl, Format.raw, Format.table)
]
TreeFormatOption = Annotated[Format, _format_option(Format.json, Format.jsonl, Format.raw)]
BuiltFormatOption = Annotated[Format, _format_option(Format.json, Format.jsonl)]
ObjectFormatOption = Annotated[Format, _format_option(Format.json, Format.table)]
UserArg = Annotated[str, typer.Argument(help="A numeric user id, or `me`.")]
KeywordIdArg = Annotated[int, typer.Argument(min=1, help="A keyword id.")]
ResumeIdArg = Annotated[int, typer.Argument(min=1, help="A resume id.")]


def exit_code(error: CinodeError) -> int:
    """The exit code the output contract gives `error`."""
    match error:
        case AuthError():
            return 3
        case ForbiddenError():
            return 4
        case NotFoundError():
            return 5
        case RateLimitedError():
            return 6
        case _:
            return 1


def user_ref(value: str) -> UserRef:
    """`value` as a `UserRef`: `"me"`, or a positive numeric id.

    Raises `typer.BadParameter` (exit 2) for anything else, before any request.
    """
    if value == "me":
        return "me"
    if value.isascii() and value.isdigit() and int(value) > 0:
        return int(value)
    raise typer.BadParameter(f'must be a numeric user id or "me", not {value!r}.')


def client() -> Cinode:
    """The client every command uses: credentials from the environment, else the file."""
    return Cinode()


def fetched[R](fetch: Callable[[Cinode], R]) -> R:
    """Call `fetch` with a client from `client()`, and return its result.

    A `CinodeError` is written to stderr as `{"error": ...}`, and the process
    exits with its code. Validate arguments before calling `fetched()`:
    anything else raised in here is a bug, and surfaces as one.
    """
    try:
        with client() as c:
            return fetch(c)
    except CinodeError as error:
        fail(error)


def run(
    fetch: Callable[[Cinode], Result],
    *,
    format: Format = Format.json,
    model: type[CinodeModel] | None = None,
    columns: tuple[Column, ...] | None = None,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """Write the result of `fetched(fetch)` to stdout, as `write` does."""
    result = fetched(fetch)
    write(result, format=format, model=model, columns=columns, title=title, caption=caption)


def fail(error: CinodeError) -> NoReturn:
    """Write `error`'s envelope to stderr and exit with its code."""
    sys.stderr.write(_dumps({"error": error.to_dict()}) + "\n")
    raise typer.Exit(exit_code(error))


def usage_failure(error: UsageError) -> NoReturn:
    """Write a usage error's envelope to stderr and exit 2."""
    envelope = {
        "type": "UsageError",
        "status": None,
        "path": None,
        "message": error.format_message(),
        "correlation_id": None,
    }
    sys.stderr.write(_dumps({"error": envelope}) + "\n")
    raise typer.Exit(2)


def write(
    result: Result,
    *,
    format: Format,
    model: type[CinodeModel] | None = None,
    columns: tuple[Column, ...] | None = None,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """Write `result` to stdout in `format`.

    `json` and `jsonl` write `model_dump(mode="json")`, and `raw` writes `.raw`.
    A list is one JSON array, or one object per line for `jsonl`. `table`
    renders `result` with rows of `model`, which a command offering `table`
    must pass; `columns`, `title` and `caption` are used only by `table`.
    """
    if format is Format.table:
        if model is None:
            raise AssertionError("a command that offers --format table passes its row model")
        render(result, model=model, columns=columns, title=title, caption=caption)
        return

    def dump(model: CinodeModel) -> Any:
        return model.raw if format is Format.raw else model.model_dump(mode="json")

    if isinstance(result, CinodeModel):
        sys.stdout.write(_dumps(dump(result)) + "\n")
    elif format is Format.jsonl:
        sys.stdout.writelines(_dumps(dump(model)) + "\n" for model in result)
    else:
        sys.stdout.write(_dumps([dump(model) for model in result]) + "\n")


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)
