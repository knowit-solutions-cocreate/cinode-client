"""`cinode keywords …`: the keyword catalogue."""

from typing import Annotated

import typer

from cinode.cli._output import JsonlOption, RawOption, run

app = typer.Typer(no_args_is_help=True, help="The keyword catalogue.")

TermArg = Annotated[str, typer.Argument(help="Text to search keywords for.")]


def search_term(value: str) -> str:
    """`value`, stripped, if `Keywords.search` would accept it.

    Raises `typer.BadParameter` (exit 2) for an empty or dots-only term, before
    any request: inside `run()` the resource's `ValueError` would be a traceback.
    """
    stripped = value.strip()
    if not stripped:
        raise typer.BadParameter("must not be empty.")
    if not stripped.strip("."):
        raise typer.BadParameter("must not be made only of dots.")
    return stripped


@app.callback()
def keywords() -> None:
    """The keyword catalogue."""


@app.command("search")
def search(term: TermArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """The keywords matching a term."""
    checked = search_term(term)
    run(lambda c: c.keywords.search(checked), raw=raw, jsonl=jsonl)
