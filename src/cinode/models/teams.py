"""Teams, and the users who are members of them."""

from typing import Any, cast

from pydantic import Field, field_validator, model_validator

from cinode.models._base import CinodeModel
from cinode.models.users import UserSummary


class Team(CinodeModel):
    """A team (`TeamModel`, or `TeamBaseModel` in a user's team list)."""

    id: int
    name: str = ""
    description: str | None = None
    parent_team_id: int | None = Field(default=None, validation_alias="parentTeamId")

    @field_validator("name", mode="before")
    @classmethod
    def _null_name_is_empty(cls, value: object) -> object:
        return "" if value is None else value


class TeamMember(CinodeModel):
    """One user's membership of a team (`TeamMemberModel`)."""

    user_id: int = Field(validation_alias="companyUserId")
    team_id: int | None = Field(default=None, validation_alias="teamId")
    user: UserSummary | None = Field(default=None, validation_alias="companyUser")
    availability_percent: int | None = Field(default=None, validation_alias="availabilityPercent")

    @model_validator(mode="before")
    @classmethod
    def _user_id_from_user(cls, data: Any) -> Any:
        # The spec lets the top-level `companyUserId` be null, or it may be missing.
        # Then the inline user's id is used, which `AliasChoices` alone would not reach.
        if not isinstance(data, dict):
            return data
        payload = cast("dict[str, Any]", data)
        if payload.get("companyUserId") is not None or "user_id" in payload:
            return payload
        user = payload.get("companyUser")
        if not isinstance(user, dict):
            return payload
        inline = cast("dict[str, Any]", user)
        user_id = inline.get("companyUserId")
        if user_id is None:
            user_id = inline.get("id")
        return payload if user_id is None else payload | {"companyUserId": user_id}
