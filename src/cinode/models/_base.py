"""The base class every model shares."""

from typing import Any, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    ModelWrapValidatorHandler,
    PrivateAttr,
    ValidationError,
    model_validator,
)

from cinode.errors import UnexpectedResponseError


class CinodeModel(BaseModel):
    """A frozen model of a Cinode payload that keeps the payload as `.raw`."""

    model_config = ConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )

    _raw: dict[str, Any] = PrivateAttr(default_factory=dict[str, Any])

    @model_validator(mode="wrap")
    @classmethod
    def _keep_raw(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        model = handler(data)
        if isinstance(data, dict):
            # `frozen` covers fields only, so a private attribute can still be set.
            model._raw = data
        return model

    @property
    def raw(self) -> dict[str, Any]:
        """The payload this model was parsed from, untouched."""
        return self._raw

    @classmethod
    def parse(cls, data: Any, *, path: str | None = None) -> Self:
        """Validate one payload, raising `UnexpectedResponseError` if it does not fit."""
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise UnexpectedResponseError(
                f"The response did not fit {cls.__name__}: {exc}", path=path
            ) from exc

    @classmethod
    def parse_list(cls, data: Any, *, path: str | None = None) -> list[Self]:
        """Validate a list of payloads, raising `UnexpectedResponseError` if any does not fit."""
        if not isinstance(data, list):
            raise UnexpectedResponseError(
                f"Expected a list of {cls.__name__}, got {type(data).__name__}.", path=path
            )
        return [cls.parse(item, path=path) for item in cast("list[Any]", data)]
