import httpx
import pytest
import respx
from support import (
    TEAM_ID,
    member_payload,
    profile_payload,
    skill_payload,
    team_payload,
    user_payload,
)

from cinode import Cinode
from cinode.errors import ServerError
from cinode.ops import team_profiles, team_skills

PREFIX = "/v0.1/companies/99"


def mock_team(api: respx.MockRouter, user_ids: list[int]) -> None:
    api.get(f"{PREFIX}/teams/{TEAM_ID}").mock(return_value=httpx.Response(200, json=team_payload()))
    members = [
        member_payload(companyUserId=u, companyUser=user_payload(companyUserId=u, id=u))
        for u in user_ids
    ]
    api.get(f"{PREFIX}/teams/{TEAM_ID}/members").mock(
        return_value=httpx.Response(200, json=members)
    )


def test_forbidden_and_missing_members_are_skipped(client: Cinode, api: respx.MockRouter) -> None:
    mock_team(api, [1, 2, 3])
    api.get(f"{PREFIX}/users/1/skills").mock(
        return_value=httpx.Response(200, json=[skill_payload(companyUserId=1)])
    )
    api.get(f"{PREFIX}/users/2/skills").mock(return_value=httpx.Response(403))
    api.get(f"{PREFIX}/users/3/skills").mock(return_value=httpx.Response(404))

    result = team_skills(client, TEAM_ID)

    assert [m.user.id for m in result.members] == [1]
    assert [(s.user.id, s.reason) for s in result.skipped] == [(2, "forbidden"), (3, "not_found")]


def test_team_profiles_skips_forbidden_and_missing_members(
    client: Cinode, api: respx.MockRouter
) -> None:
    mock_team(api, [1, 2, 3])
    api.get(f"{PREFIX}/users/1/profile").mock(
        return_value=httpx.Response(200, json=profile_payload(companyUserId=1))
    )
    api.get(f"{PREFIX}/users/2/profile").mock(return_value=httpx.Response(403))
    api.get(f"{PREFIX}/users/3/profile").mock(return_value=httpx.Response(404))

    result = team_profiles(client, TEAM_ID)

    assert [m.user.id for m in result.members] == [1]
    assert result.members[0].profile.user_id == 1
    assert [(s.user.id, s.reason) for s in result.skipped] == [(2, "forbidden"), (3, "not_found")]


def test_a_persistent_server_error_ends_the_run(client: Cinode, api: respx.MockRouter) -> None:
    mock_team(api, [1])
    api.get(f"{PREFIX}/users/1/skills").mock(return_value=httpx.Response(500))

    with pytest.raises(ServerError):
        team_skills(client, TEAM_ID)
