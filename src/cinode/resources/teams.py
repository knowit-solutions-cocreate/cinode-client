"""Teams, and the members below them."""

import builtins

from cinode.models import Team, TeamMember
from cinode.resources._base import Context, Resource, require_id


class TeamMembers(Resource):
    """`teams/{t}/members`: one team's members."""

    def list(self, team_id: int) -> builtins.list[TeamMember]:
        return self._list(TeamMember, f"teams/{require_id(team_id, 'team_id')}/members")


class Teams(Resource):
    """`teams`: the company's teams."""

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.members = TeamMembers(ctx)

    def list(self) -> builtins.list[Team]:
        return self._list(Team, "teams")

    def get(self, team_id: int) -> Team:
        return self._one(Team, f"teams/{require_id(team_id, 'team_id')}")
