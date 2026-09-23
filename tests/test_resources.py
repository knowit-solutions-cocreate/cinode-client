import httpx
import respx
from support import make_jwt, skill_payload

from cinode import Cinode


def test_me_resolves_to_the_token_user(client: Cinode, api: respx.MockRouter) -> None:
    route = api.get("/v0.1/companies/99/users/1001/skills").mock(
        return_value=httpx.Response(200, json=[skill_payload()])
    )
    [skill] = client.users.skills.list("me")
    assert route.called
    assert (skill.keyword_id, skill.user_id) == (22070, 1001)


def test_the_first_token_fetch_is_retried(client: Cinode, api: respx.MockRouter) -> None:
    api.routes["token"].side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"access_token": make_jwt(), "refresh_token": "refresh"}),
    ]
    api.get("/v0.1/companies/99/users").mock(return_value=httpx.Response(200, json=[]))
    assert client.users.list() == []
