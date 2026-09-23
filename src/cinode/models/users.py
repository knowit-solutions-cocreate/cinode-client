"""Users of the company: the summary every listing returns, and the full profile."""

from datetime import datetime
from typing import Any, cast

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator

from cinode.models._base import CinodeModel


class UserSummary(CinodeModel):
    """A user as listings and team members show them (`CompanyUserBaseModel`)."""

    id: int = Field(validation_alias=AliasChoices("companyUserId", "id"))
    first_name: str = Field(default="", validation_alias="firstName")
    last_name: str = Field(default="", validation_alias="lastName")
    seo_id: str | None = Field(default=None, validation_alias="seoId")
    user_type: int | None = Field(default=None, validation_alias="companyUserType")

    @model_validator(mode="before")
    @classmethod
    def _id_from_either_key(cls, data: Any) -> Any:
        # The spec lets both `companyUserId` and `id` be null. `AliasChoices` would
        # stop at a null `companyUserId`, so drop it and let `id` be tried.
        if not isinstance(data, dict):
            return data
        payload = cast("dict[str, Any]", data)
        if "companyUserId" in payload and payload["companyUserId"] is None:
            return {k: v for k, v in payload.items() if k != "companyUserId"}
        return payload

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _null_name_is_empty(cls, value: object) -> object:
        return "" if value is None else value

    @computed_field
    @property
    def full_name(self) -> str:
        """First and last name, joined by a space, leaving out an empty one."""
        return " ".join(part for part in (self.first_name, self.last_name) if part)


class User(UserSummary):
    """A user's full profile (`CompanyUserModel`)."""

    title: str | None = None
    email: str | None = Field(default=None, validation_alias="companyUserEmail")
    location: str | None = Field(default=None, validation_alias="locationName")
    status: int | None = None
    employment_start: datetime | None = Field(default=None, validation_alias="employmentStartDate")
