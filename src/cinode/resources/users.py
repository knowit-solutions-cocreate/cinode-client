"""Users, and the skills and teams below them."""

import builtins

from cinode.models import Skill, Team, User, UserSummary
from cinode.resources._base import Context, Resource, UserRef, require_id


class UserSkills(Resource):
    """`users/{u}/skills`: one user's skills."""

    def list(self, user: UserRef) -> builtins.list[Skill]:
        return self._list(Skill, f"users/{self._ctx.user_id(user)}/skills")

    def get(self, user: UserRef, keyword_id: int) -> Skill:
        keyword = require_id(keyword_id, "keyword_id")
        return self._one(Skill, f"users/{self._ctx.user_id(user)}/skills/{keyword}")


class UserTeams(Resource):
    """`users/{u}/teams`: the teams one user belongs to."""

    def list(self, user: UserRef) -> builtins.list[Team]:
        return self._list(Team, f"users/{self._ctx.user_id(user)}/teams")


class Users(Resource):
    """`users`: the company's users."""

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.skills = UserSkills(ctx)
        self.teams = UserTeams(ctx)

    def list(self) -> builtins.list[UserSummary]:
        return self._list(UserSummary, "users")

    def get(self, user: UserRef) -> User:
        return self._one(User, f"users/{self._ctx.user_id(user)}")
