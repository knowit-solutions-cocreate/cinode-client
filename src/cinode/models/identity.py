"""Who the API account belongs to."""

from pydantic import Field

from cinode.models._base import CinodeModel


class WhoAmI(CinodeModel):
    """The account owner's company and user ids (`WhoAmIResponseModel`)."""

    company_id: int = Field(validation_alias="companyId")
    user_id: int = Field(validation_alias="companyUserId")
