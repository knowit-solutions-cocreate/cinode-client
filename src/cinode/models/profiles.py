"""A user's profile: a lean projection of `CompanyUserProfileFullModel`.

Only the sections verified live are typed. The profile's `skills`,
`references`, `extSkills` and `commitments` are left out on purpose; `.raw`
still holds them. Texts stay in per-language `translations` lists, as Cinode
sends them: never flattened, never filled in, and `""` stays `""`.
"""

from datetime import datetime
from typing import Any

from pydantic import AliasPath, Field, field_validator, model_validator

from cinode.models._base import CinodeModel
from cinode.models.skills import resolve_keyword_id

_CULTURE = ("languageBranch", "language", "culture")


def _null_is_empty(value: object) -> object:
    return [] if value is None else value


def _null_is_false(value: object) -> object:
    return False if value is None else value


class _ProfileText(CinodeModel):
    """One language's texts for a profile element."""

    profile_translation_id: int | None = Field(
        default=None, validation_alias="profileTranslationId"
    )
    language: str | None = Field(
        default=None, validation_alias=AliasPath("profileTranslation", *_CULTURE)
    )


class PresentationText(_ProfileText):
    """The presentation's texts in one language."""

    title: str | None = None
    description: str | None = None
    personal_description: str | None = Field(default=None, validation_alias="personalDescription")


class WorkExperienceText(_ProfileText):
    """A work experience's texts in one language."""

    employer: str | None = None
    title: str | None = None
    description: str | None = None


class EducationText(_ProfileText):
    """An education's texts in one language."""

    school_name: str | None = Field(default=None, validation_alias="schoolName")
    program_name: str | None = Field(default=None, validation_alias="programName")
    degree: str | None = None
    description: str | None = None


class EmployerText(_ProfileText):
    """An employer's texts in one language."""

    name: str | None = None
    title: str | None = None
    description: str | None = None


class TrainingText(_ProfileText):
    """A training's texts in one language."""

    title: str | None = None
    description: str | None = None
    issuer: str | None = None
    supplier: str | None = None


class SkillRef(CinodeModel):
    """A skill reduced to its keyword; `users.skills.get` has the rest."""

    keyword_id: int = Field(validation_alias="id")
    name: str = Field(default="", validation_alias=AliasPath("keyword", "masterSynonym"))

    @model_validator(mode="before")
    @classmethod
    def _keyword_id_from_keyword(cls, data: Any) -> Any:
        return resolve_keyword_id(data)

    @field_validator("name", mode="before")
    @classmethod
    def _null_name_is_empty(cls, value: object) -> object:
        return "" if value is None else value


class Presentation(CinodeModel):
    """The profile's presentation."""

    id: int
    translations: list[PresentationText] = Field(default_factory=list[PresentationText])

    @field_validator("translations", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)


class WorkExperience(CinodeModel):
    """One work experience. `end_date` is None for a current one."""

    id: int
    start_date: datetime | None = Field(default=None, validation_alias="startDate")
    end_date: datetime | None = Field(default=None, validation_alias="endDate")
    is_current: bool = Field(default=False, validation_alias="isCurrent")
    translations: list[WorkExperienceText] = Field(default_factory=list[WorkExperienceText])
    skills: list[SkillRef] = Field(default_factory=list[SkillRef])

    @field_validator("translations", "skills", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)

    @field_validator("is_current", mode="before")
    @classmethod
    def _null_is_not_current(cls, value: object) -> object:
        return _null_is_false(value)


class Education(CinodeModel):
    """One education."""

    id: int
    start_date: datetime | None = Field(default=None, validation_alias="startDate")
    end_date: datetime | None = Field(default=None, validation_alias="endDate")
    translations: list[EducationText] = Field(default_factory=list[EducationText])

    @field_validator("translations", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)


class ProfileLanguage(CinodeModel):
    """A language the user speaks. The `level` scale is passed through as it comes."""

    id: int
    language_id: int | None = Field(
        default=None, validation_alias=AliasPath("language", "languageId")
    )
    name: str | None = Field(default=None, validation_alias=AliasPath("language", "name"))
    culture: str | None = Field(default=None, validation_alias=AliasPath("language", "culture"))
    level: int | None = None


class Employer(CinodeModel):
    """One employer. `end_date` is None for a current one."""

    id: int
    start_date: datetime | None = Field(default=None, validation_alias="startDate")
    end_date: datetime | None = Field(default=None, validation_alias="endDate")
    is_current: bool = Field(default=False, validation_alias="isCurrent")
    translations: list[EmployerText] = Field(default_factory=list[EmployerText])

    @field_validator("translations", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)

    @field_validator("is_current", mode="before")
    @classmethod
    def _null_is_not_current(cls, value: object) -> object:
        return _null_is_false(value)


class Training(CinodeModel):
    """One course or certification. `training_type` is open: 0 course, 1 certification."""

    id: int
    training_type: int | None = Field(default=None, validation_alias="trainingType")
    year: int | None = None
    expires: datetime | None = Field(default=None, validation_alias="expireDate")
    code: str | None = None
    translations: list[TrainingText] = Field(default_factory=list[TrainingText])

    @field_validator("translations", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)


class Profile(CinodeModel):
    """A user's profile (`CompanyUserProfileFullModel`), lean.

    `language` is the profile's default translation.
    """

    id: int
    user_id: int | None = Field(default=None, validation_alias="companyUserId")
    language: str | None = Field(
        default=None, validation_alias=AliasPath("profileTranslation", *_CULTURE)
    )
    created: datetime | None = Field(default=None, validation_alias="createdWhen")
    updated: datetime | None = Field(default=None, validation_alias="updatedWhen")
    presentation: Presentation | None = None
    work_experience: list[WorkExperience] = Field(
        default_factory=list[WorkExperience], validation_alias="workExperience"
    )
    education: list[Education] = Field(default_factory=list[Education])
    languages: list[ProfileLanguage] = Field(default_factory=list[ProfileLanguage])
    employers: list[Employer] = Field(default_factory=list[Employer])
    training: list[Training] = Field(default_factory=list[Training])

    @field_validator(
        "work_experience", "education", "languages", "employers", "training", mode="before"
    )
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)
