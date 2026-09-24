"""Users, and the skills, teams, profile and resumes below them."""

import builtins

from cinode.models import Profile, Resume, ResumeSummary, Skill, Team, User, UserSummary
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


class UserProfile(Resource):
    """`users/{u}/profile`: one user's profile, the data behind their CV."""

    def get(self, user: UserRef) -> Profile:
        return self._one(Profile, f"users/{self._ctx.user_id(user)}/profile")


class UserResumes(Resource):
    """`users/{u}/resumes`: one user's resumes."""

    def list(self, user: UserRef) -> builtins.list[ResumeSummary]:
        """The user's resumes, without their content.

        An empty list means no resumes, or no access: for a user whose data the
        owner cannot read, Cinode returns an empty list, not a 403. To tell the
        two apart, call `users.profile.get(user)`, which raises `ForbiddenError`.
        """
        return self._list(ResumeSummary, f"users/{self._ctx.user_id(user)}/resumes")

    def get(self, user: UserRef, resume_id: int) -> Resume:
        """One resume, with its blocks (read from `resume.blocks` in the payload)."""
        resume = require_id(resume_id, "resume_id")
        return self._one(Resume, f"users/{self._ctx.user_id(user)}/resumes/{resume}")


class Users(Resource):
    """`users`: the company's users."""

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx)
        self.skills = UserSkills(ctx)
        self.teams = UserTeams(ctx)
        self.profile = UserProfile(ctx)
        self.resumes = UserResumes(ctx)

    def list(self) -> builtins.list[UserSummary]:
        return self._list(UserSummary, "users")

    def get(self, user: UserRef) -> User:
        return self._one(User, f"users/{self._ctx.user_id(user)}")
