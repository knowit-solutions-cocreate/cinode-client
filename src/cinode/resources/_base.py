"""The base every resource shares: the transport, the company id, id checks and `me`."""

from typing import Any, Literal

from cinode._transport import API_PREFIX, Transport
from cinode.models import CinodeModel

type UserRef = int | Literal["me"]
"""A user id, or `"me"` for the user who owns the API account."""


def require_id(value: object, name: str) -> int:
    """`value` if it is a positive `int` (not a `bool`); otherwise raise `ValueError`.

    Ids come from callers such as agents, and the type hints do nothing at run
    time, so every id is checked before it goes into a path.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive int, not {value!r}.")
    return value


class Context:
    """What every resource needs: the transport, and the ids the token carries."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    @property
    def company_id(self) -> int:
        """The company id, from the token's `companySub` claim."""
        return self.transport.token().company_id

    def user_id(self, ref: UserRef) -> int:
        """The id `ref` names: itself, or the token's `sub` for `"me"`.

        Raises `ValueError` unless `ref` is exactly `"me"` or a positive `int`.
        """
        if ref == "me":
            return self.transport.token().user_id
        if isinstance(ref, str):
            raise ValueError(f'user must be "me" or a positive int, not {ref!r}.')
        return require_id(ref, "user")

    def get(self, path: str) -> tuple[Any, str]:
        """GET `path` below `companies/{cid}/`.

        Returns the decoded body and the full request path, as errors report it.
        """
        relative = f"companies/{self.company_id}/{path.lstrip('/')}"
        return self.transport.get(relative), API_PREFIX + relative


class Resource:
    """One segment of Cinode's URL tree. Sub-resources are attributes of their parent."""

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx

    def _one[M: CinodeModel](self, model: type[M], path: str) -> M:
        """GET `path` below `companies/{cid}/` and parse it as one `model`."""
        body, full = self._ctx.get(path)
        return model.parse(body, path=full)

    def _list[M: CinodeModel](self, model: type[M], path: str) -> list[M]:
        """GET `path` below `companies/{cid}/` and parse it as a list of `model`."""
        body, full = self._ctx.get(path)
        return model.parse_list(body, path=full)
