"""The `cinode` command: JSON on stdout, errors as JSON on stderr, documented exit codes."""

from typing import Any

import typer
from typer._click.core import Context
from typer._click.exceptions import NoArgsIsHelpError, UsageError
from typer.core import TyperGroup

from cinode.cli import config, keywords, schema, teams, users
from cinode.cli._output import JsonlOption, RawOption, run, usage_failure


class _Root(TyperGroup):
    """The root group: a usage error anywhere below it becomes a JSON envelope.

    The root's own arguments are parsed in `make_context`, and every
    subcommand's in `invoke`, so both are covered. A group given no arguments
    still prints its help.
    """

    def make_context(
        self, info_name: str | None, args: list[str], parent: Context | None = None, **extra: Any
    ) -> Context:
        try:
            return super().make_context(info_name, args, parent, **extra)
        except NoArgsIsHelpError:
            raise
        except UsageError as error:
            usage_failure(error)

    def invoke(self, ctx: Context) -> Any:
        try:
            return super().invoke(ctx)
        except NoArgsIsHelpError:
            raise
        except UsageError as error:
            usage_failure(error)


app = typer.Typer(
    cls=_Root,
    name="cinode",
    help="A read-only client for the Cinode API. Writes JSON to stdout.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
app.add_typer(users.app, name="users")
app.add_typer(teams.app, name="teams")
app.add_typer(keywords.app, name="keywords")
app.add_typer(config.app, name="config")
app.command("schema")(schema.schema)


@app.command()
def whoami(raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """The account owner's company and user ids."""
    run(lambda c: c.whoami(), raw=raw, jsonl=jsonl)


def main() -> None:
    """The console script's entry point."""
    app()
