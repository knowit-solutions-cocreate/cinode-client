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
    on_progress: Callable[[int, int, UserSummary], None] | None = None,
) -> TeamSkills:
    """Fetch a team and every member's skills.

    A 403 or 404 on one member's skills is recorded in `skipped`; any other error
    ends the run. `on_progress(done, total, user)` is called after each member.
    """
    team = client.teams.get(team_id)
    users: dict[int, UserSummary] = {}
    for member in client.teams.members.list(team_id):
        if member.user_id not in users:
            users[member.user_id] = member.user or UserSummary(id=member.user_id)

    members: list[MemberSkills] = []
    skipped: list[Skipped] = []
    total = len(users)
    for done, user in enumerate(users.values(), start=1):
        try:
            members.append(MemberSkills(user=user, skills=client.users.skills.list(user.id)))
        except ForbiddenError:
            skipped.append(Skipped(user=user, reason="forbidden"))
        except NotFoundError:
            skipped.append(Skipped(user=user, reason="not_found"))
        if on_progress is not None:
            on_progress(done, total, user)
    return TeamSkills(team=team, members=members, skipped=skipped)
