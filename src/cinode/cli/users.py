"""`cinode users …`: users, and the skills, teams, profile and resumes below them."""

import typer

from cinode.cli._output import (
    Format,
    FormatOption,
    KeywordIdArg,
    ResumeIdArg,
    TreeFormatOption,
    UserArg,
    run,
    user_ref,
)

app = typer.Typer(no_args_is_help=True, help="Users, and their skills, teams, profile and resumes.")
skills_app = typer.Typer(no_args_is_help=True, help="One user's skills.")
teams_app = typer.Typer(no_args_is_help=True, help="The teams one user belongs to.")
profile_app = typer.Typer(no_args_is_help=True, help="One user's profile.")
resumes_app = typer.Typer(no_args_is_help=True, help="One user's resumes.")
app.add_typer(skills_app, name="skills")
app.add_typer(teams_app, name="teams")
app.add_typer(profile_app, name="profile")
app.add_typer(resumes_app, name="resumes")


@app.command("list")
def list_users(format: FormatOption = Format.json) -> None:
    """Every user in the company."""
    run(lambda c: c.users.list(), format=format)


@app.command("get")
def get_user(user: UserArg, format: FormatOption = Format.json) -> None:
    """One user."""
    ref = user_ref(user)
    run(lambda c: c.users.get(ref), format=format)


@skills_app.command("list")
def list_skills(user: UserArg, format: FormatOption = Format.json) -> None:
    """A user's skills."""
    ref = user_ref(user)
    run(lambda c: c.users.skills.list(ref), format=format)


@skills_app.command("get")
def get_skill(user: UserArg, keyword_id: KeywordIdArg, format: FormatOption = Format.json) -> None:
    """One of a user's skills, by keyword id."""
    ref = user_ref(user)
    run(lambda c: c.users.skills.get(ref, keyword_id), format=format)


@teams_app.callback()
def teams() -> None:
    """The teams one user belongs to."""


@teams_app.command("list")
def list_teams(user: UserArg, format: FormatOption = Format.json) -> None:
    """The teams a user belongs to."""
    ref = user_ref(user)
    run(lambda c: c.users.teams.list(ref), format=format)


@profile_app.callback()
def profile() -> None:
    """One user's profile: the data behind their CV."""


@profile_app.command("get")
def get_profile(user: UserArg, format: TreeFormatOption = Format.json) -> None:
    """A user's profile."""
    ref = user_ref(user)
    run(lambda c: c.users.profile.get(ref), format=format)


@resumes_app.command("list")
def list_resumes(user: UserArg, format: FormatOption = Format.json) -> None:
    """A user's resumes, without their content.

    An empty list means no resumes, or no access: Cinode returns an empty list,
    not a 403, for a user whose data you cannot read. `users profile get`
    tells the two apart.
    """
    ref = user_ref(user)
    run(lambda c: c.users.resumes.list(ref), format=format)


@resumes_app.command("get")
def get_resume(
    user: UserArg, resume_id: ResumeIdArg, format: TreeFormatOption = Format.json
) -> None:
    """One of a user's resumes, with its blocks."""
    ref = user_ref(user)
    run(lambda c: c.users.resumes.get(ref, resume_id), format=format)
