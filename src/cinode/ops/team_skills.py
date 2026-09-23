"""Every member of a team with their skills, skipping members we may not read."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from cinode.errors import ForbiddenError, NotFoundError
from cinode.models import CinodeModel, Skill, Team, UserSummary

if TYPE_CHECKING:
    from cinode._client import Cinode


# The result models are built from keyword arguments, not a Cinode payload, so
# their `.raw` holds those arguments (model instances included) and is not JSON.


class MemberSkills(CinodeModel):
    """One member and their skills."""

    user: UserSummary
    skills: list[Skill]


class Skipped(CinodeModel):
    """A member whose skills could not be read, and why."""

    user: UserSummary
    reason: Literal["forbidden", "not_found"]


class TeamSkills(CinodeModel):
    """A team, the skills of each member, and the members that were skipped."""

    team: Team
    members: list[MemberSkills]
    skipped: list[Skipped]


def team_skills(
    client: Cinode,
    team_id: int,
    *,
    on_progress: Callable[[int, int, MemberSkills | Skipped], None] | None = None,
) -> TeamSkills:
    """Fetch a team and every member's skills.

    A 403 or 404 on one member's skills is recorded in `skipped`; any other error
    ends the run. `on_progress(done, total, entry)` is called after each member,
    with the `MemberSkills` or `Skipped` entry just recorded.
    """
    team = client.teams.get(team_id)
    # Keep each user once, in first-seen order, preferring an entry that has the
    # user inline. Reassigning an existing key keeps its place in the dict.
    inline: dict[int, UserSummary | None] = {}
    for member in client.teams.members.list(team_id):
        if inline.get(member.user_id) is None:
            inline[member.user_id] = member.user
    users = {i: user or UserSummary(id=i) for i, user in inline.items()}

    members: list[MemberSkills] = []
    skipped: list[Skipped] = []
    total = len(users)
    for done, user in enumerate(users.values(), start=1):
        entry: MemberSkills | Skipped
        try:
            entry = MemberSkills(user=user, skills=client.users.skills.list(user.id))
            members.append(entry)
        except ForbiddenError:
            entry = Skipped(user=user, reason="forbidden")
            skipped.append(entry)
        except NotFoundError:
            entry = Skipped(user=user, reason="not_found")
            skipped.append(entry)
        if on_progress is not None:
            on_progress(done, total, entry)
    return TeamSkills(team=team, members=members, skipped=skipped)
