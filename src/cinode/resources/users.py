"""Users, and the skills and teams below them."""

import builtins

from cinode.models import Skill, Team, User, UserSummary
from cinode.resources._base import Context, Resource, UserRef


class UserSkills(Resource):
    """`users/{u}/skills`: one user's skills."""

    def list(self, user: UserRef) -> builtins.list[Skill]:
        path = f"users/{self._ctx.user_id(user)}/skills"
        return Skill.parse_list(self._ctx.get(path), path=self._ctx.path(path))

    def get(self, user: UserRef, keyword_id: int) -> Skill:
        path = f"users/{self._ctx.user_id(user)}/skills/{keyword_id}"
        return Skill.parse(self._ctx.get(path), path=self._ctx.path(path))


class UserTeams(Resource):
    """`users/{u}/teams`: the teams one user belongs to."""

    def list(self, user: UserRef) -> builtins.list[Team]:
        path = f"users/{self._ctx.user_id(user)}/teams"
        return Team.parse_list(self._ctx.get(path), path=self._ctx.path(path))


class Users(Resource):
    """`users`: the company's users."""

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.skills = UserSkills(ctx)
        self.teams = UserTeams(ctx)

    def list(self) -> builtins.list[UserSummary]:
        return UserSummary.parse_list(self._ctx.get("users"), path=self._ctx.path("users"))

    def get(self, user: UserRef) -> User:
        path = f"users/{self._ctx.user_id(user)}"
        return User.parse(self._ctx.get(path), path=self._ctx.path(path))
