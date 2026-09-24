"""Every member of a team with their skills, skipping members we may not read."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from cinode.models import CinodeModel, Skill, Team, UserSummary
from cinode.ops._members import Skipped, walk_members

if TYPE_CHECKING:
    from cinode._client import Cinode

__all__ = ["MemberSkills", "Skipped", "TeamSkills", "team_skills"]


# The result models are built from keyword arguments, not a Cinode payload, so
# their `.raw` holds those arguments (model instances included) and is not JSON.


class MemberSkills(CinodeModel):
    """One member and their skills."""

    user: UserSummary
    skills: list[Skill]


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
    team, members, skipped = walk_members(
        client,
        team_id,
        lambda u: MemberSkills(user=u, skills=client.users.skills.list(u.id)),
        on_progress,
    )
    return TeamSkills(team=team, members=members, skipped=skipped)
