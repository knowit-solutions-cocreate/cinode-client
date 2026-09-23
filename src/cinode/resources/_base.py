"""The base every resource shares: the transport, the company id and `me` resolution."""

from typing import Any, Literal

from cinode._transport import API_PREFIX, Transport

type UserRef = int | Literal["me"]
"""A user id, or `"me"` for the user who owns the API account."""


class Context:
    """What every resource needs: the transport, and the ids the token carries."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    @property
    def company_id(self) -> int:
        """The company id, from the token's `companySub` claim."""
        return self.transport.token().company_id

    def user_id(self, ref: UserRef) -> int:
        """The id `ref` names: itself, or the token's `sub` for `"me"`."""
        if ref == "me":
            return self.transport.token().user_id
        return ref

    def path(self, path: str) -> str:
        """The full request path of `path` below `companies/{cid}/`, as errors report it."""
        return f"{API_PREFIX}companies/{self.company_id}/{path.lstrip('/')}"

    def get(self, path: str) -> Any:
        """GET `path` below `companies/{cid}/`."""
        return self.transport.get(f"companies/{self.company_id}/{path.lstrip('/')}")


class Resource:
    """One segment of Cinode's URL tree. Sub-resources are attributes of their parent."""

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx
