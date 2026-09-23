"""The `cinode` command: JSON on stdout, errors as JSON on stderr, documented exit codes."""

import typer

from cinode.cli import users
from cinode.cli._output import JsonlOption, RawOption, run

app = typer.Typer(
    name="cinode",
    help="A read-only client for the Cinode API. Writes JSON to stdout.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)
app.add_typer(users.app, name="users")


@app.command()
def whoami(raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """The account owner's company and user ids."""
    run(lambda c: c.whoami(), raw=raw, jsonl=jsonl)


def main() -> None:
    """The console script's entry point."""
    app()
