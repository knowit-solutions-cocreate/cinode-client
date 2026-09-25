"""`cinode teams …`: teams, their members, and every member's skills or profile."""

import sys
from collections import Counter
from collections.abc import Sequence
from typing import Annotated

import typer

from cinode.cli._output import (
    BuiltFormatOption,
    ColumnsOption,
    Format,
    FormatOption,
    TeamSkillsFormatOption,
    fetched,
    run,
    table_columns,
    write,
)
from cinode.cli._table import MemberSkillRow, member_skill_rows
from cinode.models import Team, TeamMember
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
def list_teams(
    match: MatchOption = None, format: FormatOption = Format.json, columns: ColumnsOption = None
) -> None:
    """Every team in the company, or those whose name contains `--match`."""
    shown = table_columns(format, columns, Team)
    run(
        lambda c: [t for t in c.teams.list() if _matches(t, match)],
        format=format,
        model=Team,
        columns=shown,
    )


@app.command("get")
def get_team(
    team_id: TeamIdArg, format: FormatOption = Format.json, columns: ColumnsOption = None
) -> None:
    """One team."""
    shown = table_columns(format, columns, Team)
    run(lambda c: c.teams.get(team_id), format=format, model=Team, columns=shown)


@members_app.callback()
def members() -> None:
    """One team's members."""


@members_app.command("list")
def list_members(
    team_id: TeamIdArg, format: FormatOption = Format.json, columns: ColumnsOption = None
) -> None:
    """A team's members."""
    shown = table_columns(format, columns, TeamMember)
    run(lambda c: c.teams.members.list(team_id), format=format, model=TeamMember, columns=shown)


def _progress(done: int, total: int, entry: MemberSkills | MemberProfile | Skipped) -> None:
    status = f"skipped: {entry.reason}" if isinstance(entry, Skipped) else "read"
    sys.stderr.write(f"{done}/{total} {status} (user {entry.user.id})\n")


def _skipped_caption(skipped: Sequence[Skipped]) -> str | None:
    """The caption counting skipped members by reason, or None when none was skipped."""
    if not skipped:
        return None
    counts = Counter(entry.reason for entry in skipped)
    reasons = ", ".join(f"{r} {counts[r]}" for r in ("forbidden", "not_found") if counts[r])
    noun = "member" if len(skipped) == 1 else "members"
    return f"{len(skipped)} {noun} skipped: {reasons}"


@app.command("skills")
def skills(
    team_id: TeamIdArg,
    format: TeamSkillsFormatOption = Format.json,
    columns: ColumnsOption = None,
) -> None:
    """A team and every member's skills. Members that cannot be read are listed in `skipped`."""
    shown = table_columns(format, columns, MemberSkillRow)
    on_progress = _progress if sys.stderr.isatty() else None
    result = fetched(lambda c: team_skills(c, team_id, on_progress=on_progress))
    if format is Format.table:
        write(
            member_skill_rows(result),
            format=format,
            model=MemberSkillRow,
            columns=shown,
            title=result.team.name,
            caption=_skipped_caption(result.skipped),
        )
    else:
        write(result, format=format)


@app.command("profiles")
def profiles(team_id: TeamIdArg, format: BuiltFormatOption = Format.json) -> None:
    """A team and every member's profile. Members that cannot be read are listed in `skipped`."""
    on_progress = _progress if sys.stderr.isatty() else None
    run(lambda c: team_profiles(c, team_id, on_progress=on_progress), format=format)
