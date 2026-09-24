"""The loop over a team's members that every team-level operation shares."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from cinode.errors import ForbiddenError, NotFoundError
from cinode.models import CinodeModel, Team, UserSummary

if TYPE_CHECKING:
    from cinode._client import Cinode


class Skipped(CinodeModel):
    """A member whose data could not be read, and why."""

    user: UserSummary
    reason: Literal["forbidden", "not_found"]


def walk_members[E](
    client: Cinode,
    team_id: int,
    entry: Callable[[UserSummary], E],
    on_progress: Callable[[int, int, E | Skipped], None] | None,
) -> tuple[Team, list[E], list[Skipped]]:
    """Fetch a team, then call `entry(user)` once per member.

    A 403 or 404 from `entry` is recorded as `Skipped`; any other error ends the
    run. `on_progress(done, total, entry)` is called after each member, with the
    entry or `Skipped` just recorded.
    """
    team = client.teams.get(team_id)
    # Keep each user once, in first-seen order, preferring an entry that has the
    # user inline. Reassigning an existing key keeps its place in the dict.
    inline: dict[int, UserSummary | None] = {}
    for member in client.teams.members.list(team_id):
        if inline.get(member.user_id) is None:
            inline[member.user_id] = member.user
    users = {i: user or UserSummary(id=i) for i, user in inline.items()}

    members: list[E] = []
    skipped: list[Skipped] = []
    total = len(users)
    for done, user in enumerate(users.values(), start=1):
        recorded: E | Skipped
        try:
            recorded = entry(user)
            members.append(recorded)
        except ForbiddenError:
            recorded = Skipped(user=user, reason="forbidden")
            skipped.append(recorded)
        except NotFoundError:
            recorded = Skipped(user=user, reason="not_found")
            skipped.append(recorded)
        if on_progress is not None:
            on_progress(done, total, recorded)
    return team, members, skipped
