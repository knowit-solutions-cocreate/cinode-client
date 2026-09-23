"""The CLI drives the live API: `cinode` as a subprocess, its output checked with `jq`.

Assertions are on ids and counts, facts that stay put when the owner's profile
is edited in normal use. Nothing read here is written to disk.
"""

import json
import os
from typing import TYPE_CHECKING

import pytest

from cinode.models import Skill

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
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_whoami(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    assert jq(".user_id == $id", ok(cinode, "whoami"), id=owner.user_id)


def test_users_get_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "get", "me")
    assert jq(".id == $id and (.full_name | length > 0)", out, id=owner.user_id)


def test_users_skills_list_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "list", "me")
    assert jq(
        "any(.[]; .keyword_id == $kid and .synonym_id == $sid)",
        out,
        kid=owner.keyword_id,
        sid=owner.synonym_id,
    )
    for element in json.loads(out):
        Skill.model_validate(element)


def test_users_skills_get_me(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "get", "me", owner.keyword_id)
    assert jq(".name == $name", out, name=owner.keyword_name)


def test_raw_skill_keeps_the_payload(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "users", "skills", "get", "me", owner.keyword_id, "--raw")
    assert jq(".keyword.masterSynonym == $name", out, name=owner.keyword_name)


def test_keywords_search(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "keywords", "search", owner.keyword_name)
    assert jq("any(.[]; .id == $kid)", out, kid=owner.keyword_id)


def test_teams_members_list(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    out = ok(cinode, "teams", "members", "list", owner.team_id)
    assert jq("any(.[]; .user_id == $id)", out, id=owner.user_id)


def test_teams_get_then_list_match(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    team = json.loads(ok(cinode, "teams", "get", owner.team_id))
    assert team["id"] == owner.team_id
    out = ok(cinode, "teams", "list", "--match", team["name"])
    assert jq("any(.[]; .id == $id)", out, id=owner.team_id)


def test_unreadable_user(cinode: Cinode, owner: Owner) -> None:
    result = cinode("users", "skills", "list", owner.unreadable_user_id)
    assert result.returncode in (4, 5)
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["type"] in ("ForbiddenError", "NotFoundError")


@pytest.mark.slow
def test_teams_skills(cinode: Cinode, jq: Jq, owner: Owner) -> None:
    listed = json.loads(ok(cinode, "teams", "members", "list", owner.team_id))
    out = ok(cinode, "teams", "skills", owner.team_id)
    assert jq(
        "([.members[].user.id] + [.skipped[].user.id] | unique) == ($ids | unique)",
        out,
        ids=[member["user_id"] for member in listed],
    )
    assert jq("any(.members[]; .user.id == $id)", out, id=owner.user_id)
