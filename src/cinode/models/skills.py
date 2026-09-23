"""Skills on a user's profile, and the keywords they are rated against."""

from datetime import datetime

from pydantic import AliasChoices, AliasPath, Field, computed_field, field_validator

from cinode.models._base import CinodeModel


class Keyword(CinodeModel):
    """A skill keyword from Cinode's shared vocabulary (`KeywordModel`)."""

    id: int
    name: str = Field(default="", validation_alias="masterSynonym")
    synonym_id: int | None = Field(default=None, validation_alias="masterSynonymId")
    type: int | None = None
    synonyms: list[str] = Field(default_factory=list[str])
    verified: bool | None = None


class Skill(CinodeModel):
    """One skill on a user's profile (`CompanyUserSkillModel`).

    `level` 0 means unrated, so it becomes None rather than a level below 1.
    """

    keyword_id: int = Field(validation_alias=AliasChoices("id", AliasPath("keyword", "id")))
    name: str = Field(default="", validation_alias=AliasPath("keyword", "masterSynonym"))
    synonym_id: int | None = Field(
        default=None, validation_alias=AliasPath("keyword", "masterSynonymId")
    )
    keyword_type: int | None = Field(default=None, validation_alias=AliasPath("keyword", "type"))
    level: int | None = None
    level_goal: int | None = Field(default=None, validation_alias="levelGoal")
    level_goal_deadline: datetime | None = Field(default=None, validation_alias="levelGoalDeadline")
    days_experience: int = Field(default=0, validation_alias="numberOfDaysWorkExperience")
    favourite: bool = False
    user_id: int = Field(validation_alias="companyUserId")

    @field_validator("level")
    @classmethod
    def _unrated_is_none(cls, value: int | None) -> int | None:
        return None if value == 0 else value

    @field_validator("days_experience", mode="before")
    @classmethod
    def _null_days_is_zero(cls, value: object) -> object:
        return 0 if value is None else value

    @field_validator("favourite", mode="before")
    @classmethod
    def _null_favourite_is_false(cls, value: object) -> object:
        return False if value is None else value

    @computed_field
    @property
    def is_rated(self) -> bool:
        """Whether the user has set a level for this skill."""
        return self.level is not None

    @computed_field
    @property
    def years_experience(self) -> float:
        """`days_experience` in years, to one decimal."""
        return round(self.days_experience / 365.25, 1)
