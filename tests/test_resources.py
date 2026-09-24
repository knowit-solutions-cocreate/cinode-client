from collections.abc import Callable

import httpx
import pytest
import respx
from support import (
    make_jwt,
    profile_payload,
    resume_payload,
    resume_summary_payload,
    skill_payload,
)

from cinode import Cinode
from cinode.models import CinodeModel, Profile, Resume, ResumeSummary


def test_me_resolves_to_the_token_user(client: Cinode, api: respx.MockRouter) -> None:
    route = api.get("/v0.1/companies/99/users/1001/skills").mock(
        return_value=httpx.Response(200, json=[skill_payload()])
    )
    [skill] = client.users.skills.list("me")
    assert route.called
    assert (skill.keyword_id, skill.user_id) == (22070, 1001)


@pytest.mark.parametrize(
    ("call", "path", "body", "model"),
    [
        (lambda c: c.users.profile.get("me"), "profile", profile_payload(), Profile),
        (
            lambda c: c.users.resumes.list("me"),
            "resumes",
            [resume_summary_payload()],
            ResumeSummary,
        ),
        # The content comes from `resume.blocks`; `resumes/7/dynamic` is never called.
        (lambda c: c.users.resumes.get("me", 7), "resumes/7", resume_payload(), Resume),
    ],
)
def test_profile_and_resume_paths(
    client: Cinode,
    api: respx.MockRouter,
    call: Callable[[Cinode], CinodeModel | list[CinodeModel]],
    path: str,
    body: object,
    model: type[CinodeModel],
) -> None:
    api.get(f"/v0.1/companies/99/users/1001/{path}").mock(
        return_value=httpx.Response(200, json=body)
    )
    result = call(client)
    [parsed] = result if isinstance(result, list) else [result]
    assert isinstance(parsed, model)
    assert [c.request.url.path for c in api.calls if "/token" not in c.request.url.path] == [
        f"/v0.1/companies/99/users/1001/{path}"
    ]
    if isinstance(parsed, Resume):
        assert [block.block_id for block in parsed.blocks] == ["b-1", "b-2", "b-3"]


@pytest.mark.parametrize("resume_id", [True, 0, "5"])
def test_a_bad_resume_id_raises_before_any_request(
    client: Cinode, api: respx.MockRouter, resume_id: object
) -> None:
    with pytest.raises(ValueError):
        client.users.resumes.get("me", resume_id)  # pyright: ignore[reportArgumentType]
    assert not api.calls


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
