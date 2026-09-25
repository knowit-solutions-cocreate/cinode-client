import base64
import json
import tomllib
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import respx
from support import (
    TEAM_ID,
    keyword_payload,
    member_payload,
    skill_payload,
    team_payload,
    user_payload,
)
from typer.testing import Result

from cinode.cli._table import DEFAULT_COLUMNS, MemberSkillRow, cells, column_paths
from cinode.errors import FORBIDDEN_HINT
from cinode.models import CinodeModel, Resume, Skill, TeamMember

type Cli = Callable[..., Result]

SKILLS = "/v0.1/companies/99/users/1001/skills"
SKILL_LABELS = ["Keyword id", "Name", "Level", "Goal", "Years", "Favourite"]


@pytest.fixture
def wide(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal wide enough that no table cell folds."""
    monkeypatch.setenv("COLUMNS", "200")


def is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def test_skills_list_writes_the_output_contract(cli: Cli, cli_api: respx.MockRouter) -> None:
    cli_api.get(SKILLS).mock(return_value=httpx.Response(200, json=[skill_payload()]))
    result = cli("users", "skills", "list", "me")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == [
        {
            "keyword_id": 22070,
            "name": "Python",
            "synonym_id": 2930,
            "keyword_type": 1,
            "level": 4,
            "level_goal": 5,
            "level_goal_deadline": "2027-06-30T00:00:00",
            "days_experience": 1461,
            "favourite": True,
            "user_id": 1001,
            "is_rated": True,
            "years_experience": 4.0,
        }
    ]


@pytest.mark.parametrize("format", ["jsonl", "raw"])
def test_skills_list_writes_jsonl_and_raw(cli: Cli, cli_api: respx.MockRouter, format: str) -> None:
    payloads = [skill_payload(), skill_payload(id=22071)]
    cli_api.get(SKILLS).mock(return_value=httpx.Response(200, json=payloads))
    result = cli("users", "skills", "list", "me", "--format", format)
    assert result.exit_code == 0
    if format == "jsonl":
        lines = result.stdout.splitlines()
        assert len(lines) == 2
        assert all(isinstance(json.loads(line), dict) for line in lines)
    else:
        assert json.loads(result.stdout) == payloads


@pytest.mark.parametrize(
    "args",
    [
        ["users", "skills", "list", "me", "--raw"],
        ["users", "skills", "list", "me", "--jsonl"],
        ["teams", "skills", str(TEAM_ID), "--format", "raw"],
        ["users", "profile", "get", "me", "--format", "table"],
    ],
    ids=["raw-flag", "jsonl-flag", "teams-skills-raw", "profile-table"],
)
def test_a_format_a_command_does_not_take_is_a_usage_error(
    cli: Cli, cli_api: respx.MockRouter, args: list[str]
) -> None:
    result = cli(*args)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]["type"] == "UsageError"
    assert not cli_api.calls


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (
            200,
            1,
            {
                "type": "UnexpectedResponseError",
                "message": "Cinode returned a body that is not JSON (HTTP 200).",
            },
        ),
        (403, 4, {"type": "ForbiddenError", "message": FORBIDDEN_HINT}),
        (404, 5, {"type": "NotFoundError", "message": f"Cinode has nothing at {SKILLS}."}),
        (
            429,
            6,
            {
                "type": "RateLimitedError",
                "message": "Cinode is still rate-limiting after every retry.",
                "retry_after": 7.0,
            },
        ),
    ],
)
def test_an_api_error_is_an_envelope_and_an_exit_code(
    cli: Cli, cli_api: respx.MockRouter, status: int, code: int, error: dict[str, object]
) -> None:
    cli_api.get(SKILLS).mock(
        return_value=httpx.Response(
            status,
            headers={"Retry-After": "7", "X-Correlation-Id": "corr-1"},
            text="<html>A proxy page</html>",
        )
    )
    result = cli("users", "skills", "list", "me")
    assert result.exit_code == code
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {"status": status, "path": SKILLS, "correlation_id": "corr-1", **error}
    }


def test_no_credentials_is_an_auth_error(
    cli: Cli, cli_api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CINODE_BASIC")
    result = cli("users", "skills", "list", "me")
    assert result.exit_code == 3
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]["type"] == "AuthError"
    assert not cli_api.calls


def test_a_user_that_is_not_an_id_is_a_usage_error(cli: Cli, cli_api: respx.MockRouter) -> None:
    result = cli("users", "get", "Fredrik")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "UsageError",
            "status": None,
            "path": None,
            "message": "Invalid value: must be a numeric user id or \"me\", not 'Fredrik'.",
            "correlation_id": None,
        }
    }
    assert not cli_api.calls


def test_teams_skills_exits_0_and_lists_a_forbidden_member(
    cli: Cli, cli_api: respx.MockRouter
) -> None:
    prefix = "/v0.1/companies/99"
    members = [
        member_payload(companyUserId=u, companyUser=user_payload(companyUserId=u, id=u))
        for u in (1, 2)
    ]
    cli_api.get(f"{prefix}/teams/{TEAM_ID}").mock(
        return_value=httpx.Response(200, json=team_payload())
    )
    cli_api.get(f"{prefix}/teams/{TEAM_ID}/members").mock(
        return_value=httpx.Response(200, json=members)
    )
    cli_api.get(f"{prefix}/users/1/skills").mock(
        return_value=httpx.Response(200, json=[skill_payload(companyUserId=1)])
    )
    cli_api.get(f"{prefix}/users/2/skills").mock(return_value=httpx.Response(403))
    result = cli("teams", "skills", str(TEAM_ID))
    assert result.exit_code == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)
    assert [m["user"]["id"] for m in output["members"]] == [1]
    assert [(s["user"]["id"], s["reason"]) for s in output["skipped"]] == [(2, "forbidden")]


@pytest.mark.parametrize("empty", [False, True], ids=["two-skills", "empty"])
@pytest.mark.usefixtures("wide")
def test_skills_list_as_a_table(cli: Cli, cli_api: respx.MockRouter, empty: bool) -> None:
    markup = "[/x] :smile:"
    payloads = [
        skill_payload(level=0),
        skill_payload(id=22071, keyword=keyword_payload(id=22071, masterSynonym=markup)),
    ]
    cli_api.get(SKILLS).mock(return_value=httpx.Response(200, json=[] if empty else payloads))
    result = cli("users", "skills", "list", "me", "--format", "table")
    assert result.exit_code == 0
    assert all(label in result.stdout for label in SKILL_LABELS)
    if not empty:
        assert "Python" in result.stdout
        assert markup in result.stdout
        assert not is_json(result.stdout)


def test_cells_of_the_default_columns() -> None:
    unrated = Skill.parse(skill_payload(level=0, favourite=False))
    assert cells(unrated, DEFAULT_COLUMNS[Skill]) == ["22070", "Python", "", "5", "4.0", "false"]
    assert cells(Skill.parse(skill_payload()), DEFAULT_COLUMNS[Skill])[5] == "true"
    member = TeamMember.parse(member_payload(companyUser=None))
    assert cells(member, DEFAULT_COLUMNS[TeamMember]) == ["1001", "", "100"]


@pytest.mark.parametrize(
    ("model", "included", "excluded"),
    [
        (TeamMember, {"user.full_name", "user.id"}, set[str]()),
        (Resume, set[str](), {"blocks"}),
        (MemberSkillRow, {"skill.years_experience"}, set[str]()),
    ],
    ids=["nested-optional", "stops-at-lists", "computed-under-optional"],
)
def test_column_paths(model: type[CinodeModel], included: set[str], excluded: set[str]) -> None:
    paths = column_paths(model)
    assert included <= set(paths)
    assert not any(p.split(".")[0] in excluded for p in paths)


@pytest.mark.usefixtures("wide")
def test_users_get_as_a_table(cli: Cli, cli_api: respx.MockRouter) -> None:
    payload = user_payload(companyUserEmail="ada@example.test")
    cli_api.get("/v0.1/companies/99/users/1001").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = cli("users", "get", "me", "--format", "table")
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert any("Field" in line and "Value" in line for line in lines)
    assert any("Full name" in line and "Ada Example" in line for line in lines)
    assert any("Email" in line and "ada@example.test" in line for line in lines)


@pytest.mark.usefixtures("wide")
def test_an_error_under_table_stays_json_on_stderr(cli: Cli, cli_api: respx.MockRouter) -> None:
    cli_api.get(SKILLS).mock(return_value=httpx.Response(403))
    result = cli("users", "skills", "list", "me", "--format", "table")
    assert result.exit_code == 4
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]["type"] == "ForbiddenError"


@pytest.mark.parametrize("all_skipped", [False, True], ids=["mixed", "all-skipped"])
@pytest.mark.usefixtures("wide")
def test_teams_skills_as_a_table(cli: Cli, cli_api: respx.MockRouter, all_skipped: bool) -> None:
    prefix = "/v0.1/companies/99"
    names = {1: ("Ada", "Example"), 2: ("Bo", "Sample"), 3: ("Cy", "Hidden")}
    ids = [3] if all_skipped else [1, 2, 3]
    members = [
        member_payload(
            companyUserId=u,
            companyUser=user_payload(
                companyUserId=u, id=u, firstName=names[u][0], lastName=names[u][1]
            ),
        )
        for u in ids
    ]
    cli_api.get(f"{prefix}/teams/{TEAM_ID}").mock(
        return_value=httpx.Response(200, json=team_payload())
    )
    cli_api.get(f"{prefix}/teams/{TEAM_ID}/members").mock(
        return_value=httpx.Response(200, json=members)
    )
    rust = keyword_payload(id=22071, masterSynonym="Rust")
    cli_api.get(f"{prefix}/users/1/skills").mock(
        return_value=httpx.Response(
            200, json=[skill_payload(companyUserId=1), skill_payload(id=22071, keyword=rust)]
        )
    )
    cli_api.get(f"{prefix}/users/2/skills").mock(return_value=httpx.Response(200, json=[]))
    cli_api.get(f"{prefix}/users/3/skills").mock(return_value=httpx.Response(403))
    result = cli("teams", "skills", str(TEAM_ID), "--format", "table")
    assert result.exit_code == 0
    assert "1 member skipped: forbidden 1" in result.stdout
    if all_skipped:
        labels = ["User id", "Name", "Keyword id", "Skill", "Level", "Years"]
        assert all(label in result.stdout for label in labels)
    else:
        assert "Example Team" in result.stdout
        assert all(name in result.stdout for name in ("Python", "Rust", "Bo Sample"))


@pytest.mark.parametrize(("mode", "private"), [(0o600, True), (0o644, False)])
def test_credentials_come_from_the_file_and_config_show_reports_it(
    cli: Cli,
    cli_api: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: int,
    private: bool,
) -> None:
    path = tmp_path / "credentials.toml"
    path.write_text('access_id = "id-1.app.cinode.com"\naccess_secret = "s3cret-value"\n')
    path.chmod(mode)
    monkeypatch.delenv("CINODE_BASIC")
    monkeypatch.setenv("CINODE_CREDENTIALS_FILE", str(path))

    cli_api.get(SKILLS).mock(return_value=httpx.Response(200, json=[skill_payload()]))
    result = cli("users", "skills", "list", "me")
    assert result.exit_code == 0
    basic = base64.b64encode(b"id-1.app.cinode.com:s3cret-value").decode()
    assert cli_api["token"].calls.last.request.headers["Authorization"] == f"Basic {basic}"

    result = cli("config", "show")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "source": "file",
        "access_id": "id-1.app.cinode.com",
        "path": str(path),
        "file_exists": True,
        "file_mode": f"{mode:04o}",
        "file_private": private,
    }
    assert "s3cret-value" not in result.stdout + result.stderr


WHOAMI = "/_whoami"


@pytest.fixture
def new_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A credentials file path, in a directory that does not exist yet."""
    path = tmp_path / "new" / "credentials.toml"
    monkeypatch.setenv("CINODE_CREDENTIALS_FILE", str(path))
    return path


@pytest.fixture
def whoami_api(cli_api: respx.MockRouter) -> respx.MockRouter:
    cli_api.get(WHOAMI, name="whoami").mock(
        return_value=httpx.Response(200, json={"companyId": 99, "companyUserId": 1001})
    )
    return cli_api


def test_init_saves_verified_credentials_privately(
    cli: Cli, whoami_api: respx.MockRouter, new_path: Path
) -> None:
    secret = 's3cret-"\\:value'
    result = cli("init", "--access-id", "id-1.app.cinode.com", input=secret + "\n")
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "path": str(new_path),
        "access_id": "id-1.app.cinode.com",
        "company_id": 99,
        "user_id": 1001,
    }
    assert new_path.stat().st_mode & 0o777 == 0o600
    assert new_path.parent.stat().st_mode & 0o777 == 0o700
    assert tomllib.loads(new_path.read_text())["access_secret"] == secret
    basic = base64.b64encode(f"id-1.app.cinode.com:{secret}".encode()).decode()
    assert whoami_api["token"].calls.last.request.headers["Authorization"] == f"Basic {basic}"
    assert "s3cret" not in result.stdout + result.stderr
    assert [p.name for p in new_path.parent.iterdir()] == ["credentials.toml"]


def test_init_writes_nothing_for_rejected_credentials(
    cli: Cli, whoami_api: respx.MockRouter, new_path: Path
) -> None:
    whoami_api["token"].mock(return_value=httpx.Response(401))
    result = cli("init", "--access-id", "id-1.app.cinode.com", input="s3cret-value\n")
    assert result.exit_code == 3
    assert json.loads(result.stderr)["error"]["type"] == "AuthError"
    assert not new_path.parent.exists() or not any(new_path.parent.iterdir())


@pytest.mark.parametrize("force", [False, True])
def test_init_replaces_a_file_only_with_force(
    cli: Cli, whoami_api: respx.MockRouter, new_path: Path, force: bool
) -> None:
    new_path.parent.mkdir()
    new_path.write_text('access_id = "old"\naccess_secret = "old"\n')
    args = ["init", "--access-id", "id-1.app.cinode.com", *(["--force"] if force else [])]
    result = cli(*args, input="s3cret-value\n")
    saved = tomllib.loads(new_path.read_text())
    if force:
        assert result.exit_code == 0, result.stderr
        assert saved == {"access_id": "id-1.app.cinode.com", "access_secret": "s3cret-value"}
    else:
        assert result.exit_code == 1
        assert "--force" in json.loads(result.stderr)["error"]["message"]
        assert saved == {"access_id": "old", "access_secret": "old"}
        assert not whoami_api.calls


def test_init_from_env_splits_basic_at_the_first_colon(
    cli: Cli, whoami_api: respx.MockRouter, new_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CINODE_BASIC", base64.b64encode(b"id-2.app.cinode.com:pa:ss").decode())
    result = cli("init", "--from-env")
    assert result.exit_code == 0, result.stderr
    saved = tomllib.loads(new_path.read_text())
    assert saved == {"access_id": "id-2.app.cinode.com", "access_secret": "pa:ss"}


@pytest.mark.parametrize(
    ("args", "stdin"),
    [
        (["--from-env", "--access-id", "x"], None),
        ([], "s3cret-value\n"),
        (["--access-id", "id-1.app.cinode.com"], ""),
    ],
    ids=["from-env-and-access-id", "no-access-id", "empty-stdin"],
)
def test_init_usage_errors(
    cli: Cli, whoami_api: respx.MockRouter, new_path: Path, args: list[str], stdin: str | None
) -> None:
    result = cli("init", *args, input=stdin)
    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["type"] == "UsageError"
    assert not whoami_api.calls
    assert not new_path.parent.exists()
