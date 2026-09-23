"""Every member of a team with their skills, skipping members we may not read."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from cinode.errors import ForbiddenError, NotFoundError
from cinode.models import Skill, Team, UserSummary

if TYPE_CHECKING:
    from cinode._client import Cinode


class _Result(BaseModel):
    """A frozen result model. We build it ourselves, so unlike `CinodeModel` it has no `.raw`."""

    model_config = ConfigDict(frozen=True)


class MemberSkills(_Result):
    """One member and their skills."""

    user: UserSummary
    skills: list[Skill]


class Skipped(_Result):
    """A member whose skills could not be read, and why."""

    user: UserSummary
    reason: Literal["forbidden", "not_found"]


class TeamSkills(_Result):
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
