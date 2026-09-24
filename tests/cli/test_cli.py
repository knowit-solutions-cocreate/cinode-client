import base64
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import respx
from support import TEAM_ID, member_payload, skill_payload, team_payload, user_payload
from typer.testing import Result

from cinode.errors import FORBIDDEN_HINT

type Cli = Callable[..., Result]

SKILLS = "/v0.1/companies/99/users/1001/skills"


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
