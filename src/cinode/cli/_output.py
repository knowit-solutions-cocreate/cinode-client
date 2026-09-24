"""What every command shares: JSON output, the error envelope and exit codes."""

import json
import sys
from collections.abc import Callable, Sequence
from typing import Annotated, Any, NoReturn

import typer
from typer._click.exceptions import UsageError

from cinode._client import Cinode
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

RawOption = Annotated[bool, typer.Option("--raw", help="Write Cinode's payload untouched.")]
JsonlOption = Annotated[bool, typer.Option("--jsonl", help="Write one JSON object per line.")]
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


def run(fetch: Callable[[Cinode], Result], *, raw: bool = False, jsonl: bool = False) -> None:
    """Call `fetch` with a client from `client()`, and write its result to stdout.

    A `CinodeError` is written to stderr as `{"error": ...}`, and the process
    exits with its code. Validate arguments before calling `run()`: anything
    else raised in here is a bug, and surfaces as one.
    """
    try:
        with client() as c:
            result = fetch(c)
    except CinodeError as error:
        fail(error)
    write(result, raw=raw, jsonl=jsonl)


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


def write(result: Result, *, raw: bool, jsonl: bool) -> None:
    """Write `result` to stdout: `model_dump(mode="json")`, or `.raw` when `raw`.

    A list is one JSON array, or one object per line when `jsonl`.
    """

    def dump(model: CinodeModel) -> Any:
        return model.raw if raw else model.model_dump(mode="json")

    if isinstance(result, CinodeModel):
        sys.stdout.write(_dumps(dump(result)) + "\n")
    elif jsonl:
        sys.stdout.writelines(_dumps(dump(model)) + "\n" for model in result)
    else:
        sys.stdout.write(_dumps([dump(model) for model in result]) + "\n")


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)
