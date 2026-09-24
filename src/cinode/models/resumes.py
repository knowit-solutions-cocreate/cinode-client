"""A user's resumes: the summary `users/{u}/resumes` lists, and one resume's blocks.

The resume's template and PDF settings, and the copies of its blocks under
named keys, are left out on purpose; `.raw` still holds them. Block items are
passed through untouched, with Cinode's camelCase keys, since their shape
depends on the block type and the template.
"""

from datetime import datetime
from typing import Any

from pydantic import AliasPath, Field, field_validator

from cinode.models._base import CinodeModel


def _null_is_empty(value: object) -> object:
    return [] if value is None else value


class ResumeBlock(CinodeModel):
    """One block of a resume. `block_type` is open: no enum names the types.

    The inline texts are set only on blocks that carry their content inline;
    the others hold theirs in `items`.
    """

    block_id: str = Field(validation_alias="blockId")
    block_type: int | None = Field(default=None, validation_alias="blockType")
    name: str | None = Field(default=None, validation_alias="friendlyBlockName")
    heading: str | None = None
    order: int | None = None
    title: str | None = None
    description: str | None = None
    personal_description: str | None = Field(default=None, validation_alias="personalDescription")
    text: str | None = None
    items: list[dict[str, Any]] = Field(
        default_factory=list[dict[str, Any]], validation_alias="data"
    )

    @field_validator("items", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)


class ResumeSummary(CinodeModel):
    """A resume's metadata (`CompanyUserResumeBaseModel`)."""

    id: int
    user_id: int | None = Field(default=None, validation_alias="companyUserId")
    title: str | None = None
    description: str | None = None
    language: str | None = Field(default=None, validation_alias=AliasPath("language", "culture"))
    template_id: int | None = Field(default=None, validation_alias=AliasPath("template", "id"))
    template_name: str | None = Field(default=None, validation_alias=AliasPath("template", "title"))
    created: datetime | None = Field(default=None, validation_alias=AliasPath("created", "time"))
    updated: datetime | None = Field(default=None, validation_alias=AliasPath("updated", "time"))
    is_public: bool = Field(default=False, validation_alias="isPublic")
    profile_translation_id: int | None = Field(
        default=None, validation_alias="profileTranslationId"
    )
    view_url: str | None = Field(default=None, validation_alias="viewUrl")
    public_view_url: str | None = Field(default=None, validation_alias="publicViewUrl")

    @field_validator("is_public", mode="before")
    @classmethod
    def _null_is_not_public(cls, value: object) -> object:
        return False if value is None else value


class Resume(ResumeSummary):
    """A resume with its blocks, in Cinode's order."""

    blocks: list[ResumeBlock] = Field(
        default_factory=list[ResumeBlock], validation_alias=AliasPath("resume", "blocks")
    )

    @field_validator("blocks", mode="before")
    @classmethod
    def _null_lists_are_empty(cls, value: object) -> object:
        return _null_is_empty(value)
