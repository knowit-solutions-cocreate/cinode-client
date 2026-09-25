"""`cinode teams …`: teams, their members, and every member's skills or profile."""

import sys
from typing import Annotated

import typer

from cinode.cli._output import BuiltFormatOption, Format, FormatOption, run
from cinode.models import Team
from cinode.ops import MemberProfile, MemberSkills, Skipped, team_profiles, team_skills

app = typer.Typer(no_args_is_help=True, help="Teams, their members, and their skills and profiles.")
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
def list_teams(match: MatchOption = None, format: FormatOption = Format.json) -> None:
    """Every team in the company, or those whose name contains `--match`."""
    run(lambda c: [t for t in c.teams.list() if _matches(t, match)], format=format)


@app.command("get")
def get_team(team_id: TeamIdArg, format: FormatOption = Format.json) -> None:
    """One team."""
    run(lambda c: c.teams.get(team_id), format=format)


@members_app.callback()
def members() -> None:
    """One team's members."""


@members_app.command("list")
def list_members(team_id: TeamIdArg, format: FormatOption = Format.json) -> None:
    """A team's members."""
    run(lambda c: c.teams.members.list(team_id), format=format)


def _progress(done: int, total: int, entry: MemberSkills | MemberProfile | Skipped) -> None:
    status = f"skipped: {entry.reason}" if isinstance(entry, Skipped) else "read"
    sys.stderr.write(f"{done}/{total} {status} (user {entry.user.id})\n")


@app.command("skills")
def skills(team_id: TeamIdArg, format: BuiltFormatOption = Format.json) -> None:
    """A team and every member's skills. Members that cannot be read are listed in `skipped`."""
    on_progress = _progress if sys.stderr.isatty() else None
    run(lambda c: team_skills(c, team_id, on_progress=on_progress), format=format)


@app.command("profiles")
def profiles(team_id: TeamIdArg, format: BuiltFormatOption = Format.json) -> None:
    """A team and every member's profile. Members that cannot be read are listed in `skipped`."""
    on_progress = _progress if sys.stderr.isatty() else None
    run(lambda c: team_profiles(c, team_id, on_progress=on_progress), format=format)
