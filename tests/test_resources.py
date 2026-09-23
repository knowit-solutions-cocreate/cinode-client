import httpx
import pytest
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


@pytest.mark.parametrize("ref", [True, 0, -5, "158773", "../../teams"])
def test_a_bad_user_ref_raises_before_any_request(
    client: Cinode, api: respx.MockRouter, ref: object
) -> None:
    with pytest.raises(ValueError):
        client.users.skills.list(ref)  # pyright: ignore[reportArgumentType]
    assert not api.calls


@pytest.mark.parametrize("term", ["", "  ", ".", "..", 123, None, b"C#"])
def test_a_bad_keyword_term_raises_before_any_request(
    client: Cinode, api: respx.MockRouter, term: object
) -> None:
    with pytest.raises(ValueError):
        client.keywords.search(term)  # pyright: ignore[reportArgumentType]
    assert not api.calls


@pytest.mark.parametrize(
    ("term", "segment"),
    [
        ("C#", "C%23"),
        ("CI/CD", "CI%2FCD"),
        ("Språk", "Spr%C3%A5k"),
        ("machine learning", "machine%20learning"),
    ],
)
def test_a_keyword_term_is_sent_as_one_segment(
    client: Cinode, api: respx.MockRouter, term: str, segment: str
) -> None:
    api.get(url__regex=r"/v0\.1/companies/99/keywords/search/").mock(
        return_value=httpx.Response(200, json=[])
    )
    assert client.keywords.search(f" {term} ") == []
    assert api.calls.last.request.url.raw_path == (
        f"/v0.1/companies/99/keywords/search/{segment}".encode()
    )
