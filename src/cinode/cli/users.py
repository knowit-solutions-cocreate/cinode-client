"""`cinode users …`: users, and the skills and teams below them."""

import typer

from cinode.cli._output import JsonlOption, KeywordIdArg, RawOption, UserArg, run, user_ref

app = typer.Typer(no_args_is_help=True, help="Users, and their skills and teams.")
skills_app = typer.Typer(no_args_is_help=True, help="One user's skills.")
teams_app = typer.Typer(no_args_is_help=True, help="The teams one user belongs to.")
app.add_typer(skills_app, name="skills")
app.add_typer(teams_app, name="teams")


@app.command("list")
def list_users(raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """Every user in the company."""
    run(lambda c: c.users.list(), raw=raw, jsonl=jsonl)


@app.command("get")
def get_user(user: UserArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """One user."""
    ref = user_ref(user)
    run(lambda c: c.users.get(ref), raw=raw, jsonl=jsonl)


@skills_app.command("list")
def list_skills(user: UserArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """A user's skills."""
    ref = user_ref(user)
    run(lambda c: c.users.skills.list(ref), raw=raw, jsonl=jsonl)


@skills_app.command("get")
def get_skill(
    user: UserArg, keyword_id: KeywordIdArg, raw: RawOption = False, jsonl: JsonlOption = False
) -> None:
    """One of a user's skills, by keyword id."""
    ref = user_ref(user)
    run(lambda c: c.users.skills.get(ref, keyword_id), raw=raw, jsonl=jsonl)


@teams_app.callback()
def teams() -> None:
    """The teams one user belongs to."""


@teams_app.command("list")
def list_teams(user: UserArg, raw: RawOption = False, jsonl: JsonlOption = False) -> None:
    """The teams a user belongs to."""
    ref = user_ref(user)
    run(lambda c: c.users.teams.list(ref), raw=raw, jsonl=jsonl)
