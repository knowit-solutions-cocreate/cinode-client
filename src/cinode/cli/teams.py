"""`cinode teams …`: teams, their members, and every member's skills."""

import sys
from typing import Annotated

import typer

from cinode.cli._output import JsonlOption, RawOption, run
from cinode.models import Team, UserSummary
from cinode.ops import team_skills

app = typer.Typer(no_args_is_help=True, help="Teams, their members, and their skills.")
members_app = typer.Typer(no_args_is_help=True, help="One team's members.")
app.add_typer(members_app, name="members")

TeamIdArg = Annotated[int, typer.Argument(min=1, help="A team id.")]
MatchOption = Annotated[
    str | None,
    typer.Option("--match", help="Keep only teams whose name contains TEXT, ignoring case."),
]


def _matches(team: Team, text: str | None) -> bool:
    return text is None or text.casefold() in team.name.casefold()


@app.command("list")
def list_teams(
    match: MatchOption = None, raw: RawOption = False, jsonl: JsonlOption = False
) -> None:
    """Every team in the company, or those whose name contains `--match`."""
    run(lambda c: [t for t in c.teams.list() if _matches(t, match)], raw=raw, jsonl=jsonl)


@app.command("get")
def get_team(team_id: TeamIdArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """One team."""
    run(lambda c: c.teams.get(team_id), raw=raw, jsonl=jsonl)


@members_app.callback()
def members() -> None:
    """One team's members."""


@members_app.command("list")
def list_members(team_id: TeamIdArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """A team's members."""
    run(lambda c: c.teams.members.list(team_id), raw=raw, jsonl=jsonl)


def _progress(done: int, total: int, user: UserSummary) -> None:
    sys.stderr.write(f"{done}/{total} members read (user {user.id})\n")


@app.command("skills")
def skills(team_id: TeamIdArg, jsonl: JsonlOption = False) -> None:
    """A team and every member's skills. Members that cannot be read are listed in `skipped`."""
    on_progress = _progress if sys.stderr.isatty() else None
    run(lambda c: team_skills(c, team_id, on_progress=on_progress), jsonl=jsonl)
