"""Every member of a team with their profile, skipping members we may not read."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from cinode.models import CinodeModel, Profile, Team, UserSummary
from cinode.ops._members import Skipped, walk_members

if TYPE_CHECKING:
    from cinode._client import Cinode


# The result models are built from keyword arguments, not a Cinode payload, so
# their `.raw` holds those arguments (model instances included) and is not JSON.


class MemberProfile(CinodeModel):
    """One member and their profile."""

    user: UserSummary
    profile: Profile


class TeamProfiles(CinodeModel):
    """A team, the profile of each member, and the members that were skipped."""

    team: Team
    members: list[MemberProfile]
    skipped: list[Skipped]


def team_profiles(
    client: Cinode,
    team_id: int,
    *,
    on_progress: Callable[[int, int, MemberProfile | Skipped], None] | None = None,
) -> TeamProfiles:
    """Fetch a team and every member's profile, one request per member in sequence.

    A 403 or 404 on one member's profile is recorded in `skipped`; any other error
    ends the run. `on_progress(done, total, entry)` is called after each member,
    with the `MemberProfile` or `Skipped` entry just recorded.
    """
    team, members, skipped = walk_members(
        client,
        team_id,
        lambda u: MemberProfile(user=u, profile=client.users.profile.get(u.id)),
        on_progress,
    )
    return TeamProfiles(team=team, members=members, skipped=skipped)
