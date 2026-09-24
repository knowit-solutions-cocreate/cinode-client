"""The CLI drives the live API: `cinode` as a subprocess, its output checked with `jq`.

Assertions are on ids and counts, facts that stay put when the owner's profile
is edited in normal use. Nothing read here is written to disk, and no assert
refers to live output directly: each check is bound to a name first, so a
failure shows only the message, never the document (pytest's assertion
rewriting would otherwise print the call's arguments).
"""

import json
import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from cinode.models import Profile, Skill

if TYPE_CHECKING:
    from live.conftest import Cinode, Jq, Owner

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CINODE_LIVE_TESTS") != "1", reason="set CINODE_LIVE_TESTS=1"
    ),
]


def ok(cinode: Cinode, *args: str | int) -> str:
    """Run `cinode` with `args`, and return its stdout after checking it succeeded."""
    result = cinode(*args)
    code = result.returncode
    assert code == 0, result.stderr  # stderr holds only the error envelope
    return result.stdout


def test_whoami(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    found = jq(".user_id == $id", ok(cinode, "whoami"), id=owner.user_id)
    assert found, "whoami is not the owner"


def test_users_get_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "get", "me")
    found = jq(".id == $id and (.full_name | length > 0)", out, id=owner.user_id)
    assert found, "users get me is not the owner, or has no name"


def test_users_skills_list_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "list", "me")
    found = jq(
        "any(.[]; .keyword_id == $kid and .synonym_id == $sid)",
        out,
        kid=owner.keyword_id,
        sid=owner.synonym_id,
    )
    assert found, "owner's keyword and synonym not in skills list"
    for index, element in enumerate(json.loads(out)):
        errors = None
        try:
            Skill.model_validate(element)
        except ValidationError as error:
            errors = [(e["loc"], e["type"]) for e in error.errors(include_input=False)]
        assert errors is None, f"skill {index} does not validate"


def test_users_skills_get_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "get", "me", owner.keyword_id)
    found = jq(".name == $name", out, name=owner.keyword_name)
    assert found, "skill name is not the owner's keyword name"


def test_raw_skill_keeps_the_payload(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "get", "me", owner.keyword_id, "--raw")
    found = jq(".keyword.masterSynonym == $name", out, name=owner.keyword_name)
    assert found, "--raw lost .keyword.masterSynonym"


def test_keywords_search(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "keywords", "search", owner.keyword_name)
    found = jq("any(.[]; .id == $kid)", out, kid=owner.keyword_id)
    assert found, "keyword not in search results"


def test_teams_members_list(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "teams", "members", "list", owner.team_id)
    found = jq("any(.[]; .user_id == $id)", out, id=owner.user_id)
    assert found, "owner not in team members"


def test_teams_get_then_list_match(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    team = json.loads(ok(cinode, "teams", "get", owner.team_id))
    same = team["id"] == owner.team_id
    assert same, "teams get returned another team"
    out = ok(cinode, "teams", "list", "--match", team["name"])
    found = jq("any(.[]; .id == $id)", out, id=owner.team_id)
    assert found, "team not in teams list --match"


def test_users_profile_get_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "profile", "get", "me")
    found = jq(".user_id == $id", out, id=owner.user_id)
    assert found, "users profile get me is not the owner"
    errors = None
    try:
        Profile.model_validate(json.loads(out))
    except ValidationError as error:
        errors = [(e["loc"], e["type"]) for e in error.errors(include_input=False)]
    assert errors is None, "profile does not validate"


def test_users_resumes_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "resumes", "list", "me")
    mine = jq("all(.[]; .user_id == $id)", out, id=owner.user_id)
    assert mine, "a listed resume is not the owner's"
    ids = [resume["id"] for resume in json.loads(out)]
    if not ids:
        pytest.skip("the owner has no resumes")
    resume = ok(cinode, "users", "resumes", "get", "me", ids[0])
    found = jq(".id == $id and (.blocks | length > 0)", resume, id=ids[0])
    assert found, "resumes get is not the listed resume, or has no blocks"


@pytest.mark.parametrize("command", [("skills", "list"), ("profile", "get")])
def test_unreadable_user(cinode: Cinode, owner: Owner, command: tuple[str, str]) -> None:
    result = cinode("users", *command, owner.unreadable_user_id)
    code = result.returncode
    assert code in (4, 5)
    empty = result.stdout == ""
    assert empty, "stdout is not empty"
    error = json.loads(result.stderr)["error"]
    assert error["type"] in ("ForbiddenError", "NotFoundError")


@pytest.mark.slow
def test_teams_skills(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    listed = json.loads(ok(cinode, "teams", "members", "list", owner.team_id))
    out = ok(cinode, "teams", "skills", owner.team_id)
    same = jq(
        "([.members[].user.id] + [.skipped[].user.id] | unique) == ($ids | unique)",
        out,
        ids=[member["user_id"] for member in listed],
    )
    assert same, "members and skipped do not match teams members list"
    found = jq("any(.members[]; .user.id == $id)", out, id=owner.user_id)
    assert found, "owner not in team skills members"


@pytest.mark.slow
def test_teams_profiles(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    listed = json.loads(ok(cinode, "teams", "members", "list", owner.team_id))
    out = ok(cinode, "teams", "profiles", owner.team_id)
    same = jq(
        "([.members[].user.id] + [.skipped[].user.id] | unique) == ($ids | unique)",
        out,
        ids=[member["user_id"] for member in listed],
    )
    assert same, "members and skipped do not match teams members list"
    found = jq(
        "any(.members[]; .user.id == $id and .profile.user_id == $id)", out, id=owner.user_id
    )
    assert found, "owner's profile not in team profiles members"
